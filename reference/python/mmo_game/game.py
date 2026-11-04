"""Serverautoritativer Spielserver ohne Netzwerk (deterministisch, tickgetrieben). Der Transport (`net.py`) ruft nur `connect`,
`handle`, `tick`, `drain` und `disconnect` auf. Siehe ADR-0028.

Der Client sendet ausschließlich Absichten: Bewegungsrichtung, Sammeln, Kampfbefehle und die bekannten Weltbefehle
(`mmo_server`). Positionen, Gegner, Kampf, Beute und Zeit entstehen allein hier; der Kampf nutzt dieselbe Simulation wie die
Referenz (`mmo_sim.pack`), die Berichte laufen durch die CEE.
"""
from __future__ import annotations

import json
import os
import re
from importlib import resources
from pathlib import Path
from typing import Any

from mmo_cee.errors import RuleViolation
from mmo_game import progression
from mmo_server import Gateway, Sessions
from mmo_server.gateway import ID_RE, _fail
from mmo_sim import EncounterServer, SimError
from mmo_sim.live import LiveEncounter
from mmo_sim.enemies import roll_abilities
from mmo_sim.rules import load_sim_rules
from mmo_world import WorldError
from mmo_world.persistence import PersistenceError, Store

from .navigation import Navigator
from .terrain import Terrain, TerrainError
from mmo_world.world import World

COIN = "coin@gold"
MAX_LINE = 4096


def load_game_rules(name: str = "game_rules_v3.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_game").joinpath("data", name).read_text(encoding="utf-8"))


def _dist2(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _max_encounter_counter(world: World) -> int:
    """Höchster vergebener Begegnungszähler (aus den Berichten der Figuren) – damit nach einem Neustart keine ID doppelt vergeben wird."""
    pat = re.compile(re.escape(world.server_id) + r"-enc-(\d+)$")
    best = 0
    for c in world.svc.log.character_ids():
        for ev in world.svc.log.events(c):
            if ev.type == "combat.encounter_resolved":
                m = pat.match(str(ev.payload.get("encounter_id", "")))
                if m:
                    best = max(best, int(m.group(1)))
    return best


def _ok(req_id: Any, result: Any) -> dict[str, Any]:
    return {"v": 1, "id": req_id if isinstance(req_id, str) else None, "ok": True, "result": result}


class _Err(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class GameServer:
    def __init__(self, rules: dict[str, Any] | None = None, world: World | None = None, saved: dict[str, Any] | None = None) -> None:
        self.R = rules or load_game_rules()
        self.world = world if world is not None else World(self.R["cee_rules"])
        self.sim = load_sim_rules(self.R["sim_rules"])
        self.tick_no = 0
        self.sessions = Sessions()
        self.gateway = Gateway(self.world, self.sessions, lambda: self.tick_no)
        self.encounters = EncounterServer(self.sim, self.world.svc, lambda: self.world.day[0])
        self.players: dict[str, dict[str, Any]] = {}     # Figur -> Zustand im Raum
        self.sess_of: dict[str, str] = {}                # Figur -> Sitzung
        self.queues: dict[str, list[dict[str, Any]]] = {}
        self.fights: dict[str, dict[str, Any]] = {}
        self.fight_of: dict[str, str] = {}               # Figur -> Kampf
        self.enemies = [{"id": f"e{i + 1}", "type": e["type"], "pos": tuple(e["at"]), "home": tuple(e["at"]), "alive": True,
                         "respawn_at": 0, "fight": None, "state": "idle", "target": None, "path": [], "repath_at": 0, "stuck": 0}
                        for i, e in enumerate(self.R["enemies"])]
        self.nodes = [{**n, "pos": tuple(n["at"]), "ready_at": 0} for n in self.R["nodes"]]
        self.terrain = Terrain(self.R["terrain"], self.R["zone"], self.R["speed_cm_per_tick"])
        self.nav = Navigator(self.terrain, self.R["enemy_ai"]["grid_cm"])
        for what, pos in [("Startpunkt", tuple(self.R["zone"]["spawn"]))] + [(f"Gegner {e['id']}", e["pos"]) for e in self.enemies] + [(f"Sammelpunkt {n['id']}", n["pos"]) for n in self.nodes]:
            if self.terrain.blocked(*pos):
                raise TerrainError(f"{what} liegt im Blockierten: {pos}")
        self._fight_counter = 0
        self._bucket: dict[str, int] = {}
        self.log: list[str] = []
        self.saved_pos: dict[str, tuple[int, int]] = {}
        self.daily: dict[str, int] = {}                    # Tageszähler der Progression (Sammeln, Fähigkeits-Exposition); beginnt jeden Tag neu
        self.kills: dict[str, int] = {}                  # "Figur|Gegnerart" -> Kills am aktuellen Tag (Beuteabnahme, ADR-0035)
        if world is not None:                                # Neustart: Zähler und Zustand aus dem gespeicherten Spiel
            self.encounters._counter = _max_encounter_counter(world)
        if saved:
            self.tick_no = int(saved.get("tick", 0))
            for e in self.enemies:
                st = saved.get("enemies", {}).get(e["id"])
                if st:
                    e["alive"], e["respawn_at"] = bool(st["alive"]), int(st["respawn_at"])
            for n in self.nodes:
                n["ready_at"] = int(saved.get("nodes", {}).get(n["id"], 0))
            self.saved_pos = {c: (int(x), int(y)) for c, (x, y) in saved.get("positions", {}).items()}
            if saved.get("kills_day") == self.world.day[0]:
                self.kills = {k: int(v) for k, v in saved.get("kills", {}).items()}
                self.daily = {k: int(v) for k, v in saved.get("daily", {}).items()}

    # ---------------------------------------------------------------- Speichern ----
    def save(self, store: Store) -> int:
        """Schreibt eine neue Generation der Welt (CEE, Inventar, Märkte, Gruppen ...) und den Zustand der Spielschicht."""
        gen = store.commit(self.world)
        state = {"generation": gen, "tick": self.tick_no, "format": 1,
                 "nodes": {n["id"]: n["ready_at"] for n in self.nodes},
                 "enemies": {e["id"]: {"alive": e["alive"], "respawn_at": e["respawn_at"]} for e in self.enemies},
                 "kills_day": self.world.day[0], "kills": dict(sorted(self.kills.items())), "daily": dict(sorted(self.daily.items())),
                 "positions": {**{c: list(p) for c, p in self.saved_pos.items()}, **{c: list(p["pos"]) for c, p in self.players.items()}}}
        tmp = store.path / "game_state.json.tmp"
        tmp.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, store.path / "game_state.json")
        return gen

    @classmethod
    def load(cls, store: Store, rules: dict[str, Any] | None = None) -> "GameServer":
        """Stellt den letzten gültigen Speicherpunkt wieder her; fehlt der Spielzustand oder gehört er zu einer anderen Generation, starten
        Gegner, Sammelpunkte und Positionen frisch (die Welt selbst bleibt vollständig)."""
        gen, world = store.load_latest_valid()
        saved = None
        f = store.path / "game_state.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("generation") == gen and data.get("format") == 1:
                    saved = data
            except ValueError:
                saved = None
        return cls(rules, world=world, saved=saved)

    # ---------------------------------------------------------------- Verbindung ----
    def connect(self, account: str) -> tuple[str, list[str]]:
        """Entwicklungs-Anmeldung: Konto = Figurenname (keine Passwörter; echte Anmeldung kommt später). Neue Figur: Mensch, Startmünzen."""
        if not isinstance(account, str) or not ID_RE.fullmatch(account):
            raise ValueError("Ungültiger Kontoname")
        if any(self.sessions.get(s) and self.sessions.get(s)["account"] == account for s in list(self.queues)):
            raise ValueError("Konto ist schon verbunden")
        if not self.world.svc.log.has(account):
            self.world.svc.create(account, "player")
            self.world.inv.deposit(account, COIN, self.R["start_coins"])
        sid = self.sessions.open(account, [account])
        self.queues[sid] = []
        self.gateway.on_push(sid, lambda char, item, sid=sid: self._emit(sid, {"ev": "notify", "char": char, "item": item}))
        return sid, [account]

    def disconnect(self, sid: str) -> None:
        sess = self.sessions.get(sid)
        if sess is not None:
            for c in sess["characters"]:
                self._leave(c)
        self.sessions.close(sid)
        self.queues.pop(sid, None)

    def drain(self, sid: str) -> list[dict[str, Any]]:
        q = self.queues.get(sid, [])
        self.queues[sid] = []
        return q

    def _emit(self, sid: str | None, ev: dict[str, Any]) -> None:
        if sid in self.queues:
            self.queues[sid].append(ev)

    def _emit_to(self, char: str, ev: dict[str, Any]) -> None:
        self._emit(self.sess_of.get(char), ev)

    # ---------------------------------------------------------------- Eingang ----
    def handle(self, sid: str, raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
        sess = self.sessions.get(sid)
        if sess is None:
            return _fail(None, "unknown_session", "Unbekannte Sitzung")
        req = raw
        if isinstance(raw, (str, bytes)):
            if len(raw) > MAX_LINE:
                return _fail(None, "bad_request", "Nachricht zu groß")
            try:
                req = json.loads(raw)
            except ValueError:
                return _fail(None, "bad_request", "Kein gültiges JSON")
        if not isinstance(req, dict) or not isinstance(req.get("cmd"), str):
            return _fail(None, "bad_request", "cmd fehlt")
        if not req["cmd"].startswith("game."):
            return self.gateway.handle(sid, req)           # Weltbefehle: Handel, Markt, Gruppen, Herstellen ...
        rid = req.get("id")
        args = req.get("args", {})
        try:
            if not isinstance(args, dict):
                raise _Err("bad_request", "args muss ein Objekt sein")
            char = args.get("char")
            if char not in sess["characters"]:
                raise _Err("forbidden", "Figur gehört nicht zu dieser Sitzung")
            if not self._take_token(char):
                raise _Err("rate_limited", "Zu viele Befehle")
            handler = getattr(self, "_cmd_" + req["cmd"][5:], None)
            if handler is None or not req["cmd"][5:].isidentifier():
                raise _Err("unknown_command", "Unbekannter Befehl")
            return _ok(rid, handler(sid, char, args))
        except _Err as e:
            return _fail(rid, e.code, e.message)

    def _take_token(self, char: str) -> bool:
        cap = self.R["game_commands_per_burst"]
        n = self._bucket.get(char, cap)
        if n <= 0:
            return False
        self._bucket[char] = n - 1
        return True

    # ---------------------------------------------------------------- Befehle ----
    def _cmd_join(self, sid: str, char: str, a: dict[str, Any]) -> dict[str, Any]:
        if char not in self.players:
            sp = self.saved_pos.pop(char, None) or tuple(self.R["zone"]["spawn"])
            if self.terrain.blocked(*sp):                       # z. B. nach einer Kartenänderung
                sp = self.terrain.nearest_walkable(sp)
            self.players[char] = {"pos": sp, "dir": (0, 0), "immune_until": 0}
            self.sess_of[char] = sid
        return self._snapshot_for(char)

    def _cmd_move(self, sid: str, char: str, a: dict[str, Any]) -> dict[str, Any]:
        self._need_joined(char)
        dx, dy = a.get("dx"), a.get("dy")
        if any(not isinstance(v, int) or isinstance(v, bool) or not -1 <= v <= 1 for v in (dx, dy)):
            raise _Err("bad_request", "dx und dy müssen -1, 0 oder 1 sein")
        self.players[char]["dir"] = (dx, dy)
        return {"dir": [dx, dy]}

    def _cmd_gather(self, sid: str, char: str, a: dict[str, Any]) -> dict[str, Any]:
        self._need_joined(char)
        if char in self.fight_of:
            raise _Err("rejected", "Im Kampf nicht möglich")
        node = next((n for n in self.nodes if n["id"] == a.get("node")), None)
        if node is None:
            raise _Err("rejected", "Unbekannter Sammelpunkt")
        if _dist2(self.players[char]["pos"], node["pos"]) > self.R["gather_reach"] ** 2:
            raise _Err("rejected", "Zu weit entfernt")
        if self.tick_no < node["ready_at"]:
            raise _Err("rejected", "Sammelpunkt erschöpft")
        node["ready_at"] = self.tick_no + self.R["node_cooldown_ticks"]
        self.world.inv.deposit(char, node["item"], node["qty"])
        out: dict[str, Any] = {"item": node["item"], "qty": node["qty"]}
        P = self.R.get("progression")
        if P:
            key = f"{char}|gather"
            g = progression.gather_gain(P, node["item"], self.daily.get(key, 0))
            self.daily[key] = self.daily.get(key, 0) + 1
            if g is not None:
                self._record(char, "profession.work", {"profession": g[0], "xp": g[1]})
                out["gains"] = {"profession": g[0], "xp": g[1]}
        return out

    def _cmd_fight(self, sid: str, char: str, a: dict[str, Any]) -> dict[str, Any]:
        fid = self.fight_of.get(char)
        if fid is None:
            raise _Err("rejected", "Nicht im Kampf")
        f = self.fights[fid]
        if not isinstance(a.get("input"), str) or not f["live"].submit(f["chars"].index(char), a["input"]):
            raise _Err("rejected", "Befehl nicht angenommen")
        return {"tick": f["live"].t}

    # ------------------------------------------------------------- Kampf-Kit ----
    def _kit_abilities(self, char: str) -> list[str]:
        """Fähigkeiten, die die Grundklasse der Figur im Kampf von Anfang an nutzt (Spielregeln v2, Platzhalter)."""
        cls = self.world.svc.state(char).parts["identity"]["base_class"]
        return list(self.R.get("class_kits", {}).get(cls, [])) if cls else []

    def _cmd_info(self, cmd: str) -> dict[str, Any]:
        """Kosten und Zeiten eines Kampfbefehls aus den Simulationsregeln (reine Anzeige)."""
        sim = self.sim
        a = sim["actions"].get(cmd) or sim.get("skills", {}).get(cmd) or sim.get("group", {}).get(cmd) \
            or (sim.get("multi", {}).get("sweep") if cmd == "sweep" else None) or {}
        kind = a.get("kind") or ("attack" if a.get("damage") else "defense" if cmd in ("dodge", "block") else "control" if cmd in ("stun", "slow") else "support")
        return {"cmd": cmd, "cost": a.get("cost", 0), "busy": a.get("busy", 0), "cooldown": a.get("cooldown", 0), "kind": kind}

    def _kit_for(self, char: str) -> list[dict[str, Any]]:
        spec = self.encounters.pack_specs([char], {}, {char: self._kit_abilities(char)})[0]
        order = ["light", "heavy", "stun", "slow", "cast_ember", "heal", "shield", "dash", "veil", "focus_surge", "sweep", "dodge", "block", "flee"]
        cmds = set(spec.get("allowed") or order) - {"target_1", "target_2", "target_3", "target_4", "target_5", "target_6"}
        return [self._cmd_info(c) for c in order if c in cmds] + [self._cmd_info(c) for c in sorted(cmds - set(order))]

    def _cmd_kit(self, sid: str, char: str, a: dict[str, Any]) -> dict[str, Any]:
        return {"commands": self._kit_for(char), "stamina_max": self.sim["player"]["stamina_max"]}

    # ------------------------------------------------------------ Progression ----
    def _record(self, char: str, type: str, payload: dict[str, Any]) -> bool:
        """Zeichnet ein Entwicklungsereignis auf; Regelverstöße (z. B. Grenzen der CEE) werden nicht zum Spielfehler."""
        try:
            self.world.svc.record(char, type, payload)
            return True
        except (RuleViolation, WorldError) as e:
            self.log.append(f"Progression abgelehnt ({char}, {type}): {e}")
            return False

    def _progress_fight(self, chars: list[str], result: Any, types: list[str], inputs: dict[str, list]) -> dict[str, dict[str, Any]]:
        """Erfahrung und Elementexposition eines Sieges je Teilnehmer mit Beitrag (vor der Beuteabnahme berechnet)."""
        P = self.R.get("progression")
        gains: dict[str, dict[str, Any]] = {}
        if not P or result.outcome != "victory":
            return gains
        for i, c in enumerate(chars):
            pr = result.players[i]
            if pr.outcome != "victory" or not pr.actions:
                continue
            factors = {t: self._decay([c], t) for t in types}
            xp = progression.fight_xp(P, self.sim, types, factors)
            elements = progression.element_exposure(P, self.sim, types, factors)
            used = [cmd for _, cmd in inputs.get(c, [])]
            key = f"{c}|skillexp"
            sk = progression.skill_exposure(P, used, self.daily.get(key, 0))
            self.daily[key] = self.daily.get(key, 0) + sum(1 for cmd in used if cmd in P["skill_exposure"])
            for el, n in sk.items():
                elements[el] = elements.get(el, 0) + n
            before = self.world.svc.state(c).parts["identity"]["level"]
            g: dict[str, Any] = {"xp": 0, "elements": {}}
            if xp > 0 and self._record(c, "identity.xp_gained", {"amount": xp}):
                g["xp"] = xp
            for el, n in sorted(elements.items()):
                if n > 0 and self._record(c, "element.exposure", {"element": el, "amount": n}):
                    g["elements"][el] = n
            after = self.world.svc.state(c).parts["identity"]["level"]
            if after > before:
                g["level"] = after
            gains[c] = g
        return gains

    def _check_pois(self) -> None:
        """Erkundung: Hinweise an festen Orten (je Figur einmalig); Entdeckungen der CEE schließt der Spieler selbst ab."""
        P = self.R.get("progression")
        if not P:
            return
        for c, p in self.players.items():
            if c in self.fight_of:
                continue
            for poi in P["pois"]:
                if _dist2(p["pos"], tuple(poi["at"])) > poi["radius"] ** 2:
                    continue
                try:
                    self.world.discovery.gather(c, poi["discovery"], poi["evidence"])
                except (RuleViolation, WorldError):
                    continue                                    # schon gesammelt oder Voraussetzung fehlt
                self._emit_to(c, {"ev": "poi", "poi": poi["id"], "name": poi["name"], "discovery": poi["discovery"]})

    def _cmd_attune(self, sid: str, char: str, a: dict[str, Any]) -> dict[str, Any]:
        return self._attune(char, a.get("element"))

    def _attune(self, char: str, element: Any) -> dict[str, Any]:
        try:
            self.world.svc.record(char, "element.attuned", {"element": element})
        except RuleViolation as e:
            raise _Err("rejected", str(e))
        return {"element": element}

    def _cmd_map(self, sid: str, char: str, a: dict[str, Any]) -> dict[str, Any]:
        return self.terrain.export()

    def _cmd_state(self, sid: str, char: str, a: dict[str, Any]) -> dict[str, Any]:
        self._need_joined(char)
        return self._snapshot_for(char)

    def _need_joined(self, char: str) -> None:
        if char not in self.players:
            raise _Err("rejected", "Erst game.join")

    # ---------------------------------------------------------------- Zeit ----
    def tick(self) -> None:
        self.tick_no += 1
        for c in self._bucket:                              # Befehlsbudget füllt sich ein Befehl je Tick
            self._bucket[c] = min(self.R["game_commands_per_burst"], self._bucket[c] + 1)
        if self.tick_no % self.R["ticks_per_day"] == 0:
            self._new_day(self.world.day[0] + 1)
        self._move_players()
        self._respawn()
        self._alert()
        self._enemies_act()
        self._advance_fights()
        if self.tick_no % 5 == 0:
            self._check_pois()
        if self.tick_no % self.R["state_every_ticks"] == 0:
            for c in list(self.players):
                self._emit_to(c, {"ev": "state", **self._snapshot_for(c)})

    def _new_day(self, day: int) -> None:
        w = self.world
        w.day[0] = day
        self.kills = {}                                  # Beuteabnahme beginnt jeden Tag neu
        self.daily = {}
        w.company.advance_day(day)
        w.exchange.expire(day)
        w.offers.expire(day)
        w.parties.expire(day)
        if w.pricing is not None:
            w.pricing.advance(day)

    def _move_players(self) -> None:
        for c, p in self.players.items():
            if c in self.fight_of or p["dir"] == (0, 0):
                continue
            dx, dy = p["dir"]
            p["pos"] = self.terrain.step(p["pos"], dx, dy)

    def _respawn(self) -> None:
        for e in self.enemies:
            if not e["alive"] and self.tick_no >= e["respawn_at"]:
                e.update(alive=True, pos=e["home"], state="idle", target=None, path=[], stuck=0)

    # ---------------------------------------------------------------- Gegner-KI (ADR-0031) ----
    def _speed_of(self, e: dict[str, Any]) -> int:
        sp = self.R["enemy_ai"]["speed_cm_per_tick"]
        return sp.get(e["type"], sp["default"])

    def _alert(self) -> None:
        """Ruhende Gegner bemerken Spieler im Alarmradius (freie Strecke) und beginnen die Verfolgung; ihr Rudel schließt sich an."""
        R = self.R
        for c in list(self.players):
            p = self.players[c]
            if c in self.fight_of or self.tick_no < p["immune_until"]:
                continue
            for e in self.enemies:
                if (e["alive"] and e["fight"] is None and e["state"] == "idle"
                        and _dist2(p["pos"], e["pos"]) <= R["aggro_radius"] ** 2 and self.terrain.clear_line(p["pos"], e["pos"])):
                    self._begin_chase(e, c)
                    for o in self.enemies:
                        if (o is not e and o["alive"] and o["fight"] is None and o["state"] == "idle"
                                and _dist2(e["pos"], o["pos"]) <= R["pack_radius"] ** 2):
                            self._begin_chase(o, c)

    def _begin_chase(self, e: dict[str, Any], char: str) -> None:
        e.update(state="chase", target=char, path=[], repath_at=0, stuck=0)

    def _begin_return(self, e: dict[str, Any]) -> None:
        e.update(state="return", target=None, path=[], repath_at=0, stuck=0)

    def _enemies_act(self) -> None:
        ai = self.R["enemy_ai"]
        for e in self.enemies:
            if not e["alive"] or e["fight"] is not None:
                continue
            if e["state"] == "chase":
                c = e["target"]
                p = self.players.get(c)
                if (p is None or c in self.fight_of or self.tick_no < p["immune_until"]
                        or _dist2(e["pos"], e["home"]) > ai["leash_radius"] ** 2):
                    self._begin_return(e)                       # Ziel verloren oder zu weit von zu Hause
                elif _dist2(e["pos"], p["pos"]) <= ai["engage_radius"] ** 2 and self.terrain.clear_line(e["pos"], p["pos"]):
                    maxo = self.sim["multi"]["max_opponents"]
                    pack = [e] + [o for o in self.enemies if o is not e and o["alive"] and o["fight"] is None and o["state"] in ("idle", "chase")
                                  and _dist2(e["pos"], o["pos"]) <= self.R["pack_radius"] ** 2]
                    self._start_fight(c, pack[:maxo])
                    continue
                else:
                    self._walk(e, p["pos"])
            if e["state"] == "return":
                if _dist2(e["pos"], e["home"]) <= ai["home_radius"] ** 2:
                    e.update(state="idle", pos=e["home"], path=[], stuck=0)
                else:
                    self._walk(e, e["home"])

    def _walk(self, e: dict[str, Any], goal: tuple[int, int]) -> None:
        """Ein Schritt entlang des Weges zum Ziel; der Weg wird regelmäßig oder bei Hängenbleiben neu berechnet und geglättet."""
        ai = self.R["enemy_ai"]
        if not e["path"] or self.tick_no >= e["repath_at"] or e["stuck"] >= ai["stuck_limit"]:
            path = self.nav.find_path(e["pos"], goal)
            e["repath_at"], e["stuck"] = self.tick_no + ai["repath_ticks"], 0
            if path is None:
                if e["state"] == "chase":
                    self._begin_return(e)                       # kein Weg zum Spieler (z. B. Insel)
                return
            e["path"] = path
            self._smooth(e)
        speed = self._speed_of(e)
        while e["path"]:
            wp = e["path"][0]
            if len(e["path"]) > 1 and _dist2(e["pos"], wp) <= speed * speed:
                e["path"].pop(0)                                # Wegpunkt erreicht
                self._smooth(e)
                continue
            new = self.terrain.move_toward(e["pos"], wp, speed)
            e["stuck"] = e["stuck"] + 1 if new == e["pos"] else 0
            e["pos"] = new
            if new == wp and len(e["path"]) > 1:
                e["path"].pop(0)
            return

    def _smooth(self, e: dict[str, Any]) -> None:
        """Überspringt Wegpunkte, wenn der übernächste in freier Strecke liegt (kürzere, geradere Wege)."""
        path = e["path"]
        while len(path) > 1 and self.terrain.clear_line(e["pos"], path[1]):
            path.pop(0)

    # ---------------------------------------------------------------- Kampfbeginn ----
    def _start_fight(self, trigger_char: str, pack: list[dict[str, Any]]) -> None:
        R = self.R
        chars = [trigger_char]
        view = self.world.parties.view(trigger_char)
        if view is not None:
            for m in view["members"]:
                mp = self.players.get(m)
                if (m != trigger_char and mp is not None and m not in self.fight_of
                        and _dist2(mp["pos"], self.players[trigger_char]["pos"]) <= R["join_radius"] ** 2):
                    chars.append(m)
        chars = chars[: self.sim["group"]["max_party"]]
        specs = self.encounters.pack_specs(chars, {}, {c: self._kit_abilities(c) for c in chars})
        types = [e["type"] for e in pack]
        # Fähigkeiten: feste der Vorlage plus Baukasten je Spawn-Punkt und Tag (reproduzierbar, ADR-0032/0033)
        abilities = [roll_abilities(self.sim, e["type"], e["id"], self.world.day[0]) for e in pack] if "enemy_abilities" in self.sim else None
        live = LiveEncounter(self.sim, types, specs, abilities)
        self._fight_counter += 1
        fid = f"fight-{self._fight_counter:06d}"
        self.fights[fid] = {"id": fid, "live": live, "chars": chars, "enemies": [e["id"] for e in pack], "types": types, "abilities": abilities, "specs": specs, "started": self.tick_no}
        for e in pack:
            e["fight"] = fid
            e["state"], e["target"], e["path"] = "fight", None, []
        for c in chars:
            self.fight_of[c] = fid
            self.players[c]["dir"] = (0, 0)
            self._emit_to(c, {"ev": "fight_start", "fight": fid, "opponents": types, "abilities": abilities, "party": chars, "you": chars.index(c), "kit": self._kit_for(c), "enemy_ids": [e["id"] for e in pack]})

    def _advance_fights(self) -> None:
        for fid in list(self.fights):
            f = self.fights[fid]
            live = f["live"]
            # Spieler, die geflohen oder ausgefallen sind, verlassen den Kampf sofort
            res = live.advance()
            for ev in live.drain_events():                            # Ankündigungen und Ergebnisse der Gegnerfähigkeiten (Vorwarnzeit sichtbar)
                kind = "telegraph" if ev["type"] == "telegraph" else "enemy_event"
                for c in f["chars"]:
                    if self.fight_of.get(c) == fid:
                        self._emit_to(c, {"ev": kind, "fight": fid, **ev})
            for i, c in enumerate(f["chars"]):
                st = live._sim.ps[i].state
                if st != "active" and self.fight_of.get(c) == fid:
                    self._leave_fight(c, fid, st)
            if res is not None:
                self._end_fight(fid)
            elif live.t % self.R["fight_every_ticks"] == 0:
                for c in f["chars"]:
                    if self.fight_of.get(c) == fid:
                        self._emit_to(c, {"ev": "fight", "fight": fid, **live.view()})

    def _leave_fight(self, char: str, fid: str, state: str) -> None:
        del self.fight_of[char]
        p = self.players.get(char)
        if p is None:                                        # Verbindung schon getrennt
            return
        p["immune_until"] = self.tick_no + self.R["aggro_immunity_ticks"]
        if state == "down":                                  # Niederlage: zurück zum Startpunkt
            p["pos"] = tuple(self.R["zone"]["spawn"])
        else:                                                # Flucht: ein Stück vom Gegner weg
            away = (max(0, p["pos"][0] - self.R["aggro_radius"]), max(0, p["pos"][1] - self.R["aggro_radius"]))
            p["pos"] = self.terrain.nearest_walkable(away)
        self._emit_to(char, {"ev": "fight_left", "fight": fid, "reason": "defeat" if state == "down" else "fled"})

    def _end_fight(self, fid: str) -> None:
        f = self.fights.pop(fid)
        live, chars = f["live"], f["chars"]
        result = live.result
        assert result is not None
        # Bericht und Entwicklung: aus dem Eingabeprotokoll, durch dieselbe Simulation (muss mit dem Live-Ergebnis übereinstimmen)
        inputs = {c: live.inputs_of(i) for i, c in enumerate(chars)}
        report: dict[str, Any] = {}
        try:
            eid = self.encounters.start_pack(chars, f["types"], f["abilities"], f["specs"])
            fin = self.encounters.finish_pack(eid, inputs)
            if fin.result != result:
                self.log.append(f"{fid}: Live-Ergebnis weicht von der Neuberechnung ab")
            report = {c: (ev.payload if ev is not None else None) for c, ev in fin.events.items()}
        except (SimError, RuleViolation, WorldError) as e:
            self.log.append(f"{fid}: Bericht abgelehnt: {e}")
        for c in chars:
            self.fight_of.pop(c, None)
        killed = [e for e in self.enemies if e["id"] in f["enemies"]]
        for e in killed:
            e["fight"] = None
            if result.outcome == "victory":
                e["alive"], e["respawn_at"] = False, self.tick_no + self.R.get("respawn_ticks_by_type", {}).get(e["type"], self.R["respawn_ticks"])
            else:
                self._begin_return(e)                           # Kampf ohne Sieg: zurück nach Hause
        gains = self._progress_fight(chars, result, f["types"], inputs)
        loot, factors = self._loot(chars, result, f["types"]) if result.outcome == "victory" else ({}, {})
        for i, c in enumerate(chars):
            if c in self.players:
                pr = result.players[i]
                self._emit_to(c, {"ev": "fight_end", "fight": fid, "outcome": pr.outcome, "ticks": result.ticks,
                                  "actions": pr.actions, "report": report.get(c), "loot": loot.get(c, {}), "loot_factor": factors, "gains": gains.get(c, {})})

    def _decay(self, chars: list[str], t: str) -> int:
        """Beutefaktor in Promille für das Töten der Art `t`: Mittel der Faktoren aller beteiligten Figuren (je nach ihren bisherigen Kills heute)."""
        table = self.R["loot_decay_permille"]
        return sum(table[min(self.kills.get(f"{c}|{t}", 0), len(table) - 1)] for c in chars) // len(chars)

    def _loot(self, chars: list[str], result: Any, types: list[str]) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
        """Beute eines Sieges: Münzen gleichmäßig, Gegenstände nach Gruppenmodus; nur Teilnehmer mit Beitrag. Die Menge je Gegnerart sinkt mit den
        bisherigen Kills der Beteiligten am selben Tag (Rückgabe: Beute je Figur, Faktor je Gegnerart)."""
        eligible = [c for i, c in enumerate(chars) if result.players[i].outcome == "victory" and result.players[i].actions]
        out: dict[str, dict[str, int]] = {}
        factors: dict[str, int] = {}
        if not eligible:
            return out, factors
        totals: dict[str, int] = {}
        for t in types:
            f = self._decay(eligible, t)
            factors[t] = f
            for key, qty in self.R["drops"].get(t, {}).items():
                totals[key] = totals.get(key, 0) + qty * f // 1000
        for t in types:
            for c in eligible:
                self.kills[f"{c}|{t}"] = self.kills.get(f"{c}|{t}", 0) + 1
        view = self.world.parties.view(eligible[0]) if len(chars) > 1 else None
        for key, qty in sorted(totals.items()):
            if qty <= 0:
                continue
            if key == COIN:                                 # Münzen: gleichmäßig an alle mit Beitrag, Rest der Reihe nach
                share, rest = divmod(qty, len(eligible))
                alloc = {c: share + (1 if i < rest else 0) for i, c in enumerate(eligible)}
                for c, n in alloc.items():
                    if n:
                        self.world.inv.deposit(c, COIN, n)
                alloc = {c: n for c, n in alloc.items() if n}
            elif view is not None:                          # Gruppe: Beuteverteilung nach Modus, nur Teilnehmer mit Beitrag
                alloc = self.world.parties.distribute_loot(view["id"], key, qty, eligible, finder=eligible[0])
            else:
                self.world.inv.deposit(eligible[0], key, qty)
                alloc = {eligible[0]: qty}
            for c, n in alloc.items():
                out.setdefault(c, {})[key] = n
        return out, factors

    def _leave(self, char: str) -> None:
        fid = self.fight_of.get(char)
        if fid is not None:                                 # Verbindungsabbruch im Kampf = Flucht
            f = self.fights[fid]
            f["live"].submit(f["chars"].index(char), "flee")
        gone = self.players.pop(char, None)
        if gone is not None:
            self.saved_pos[char] = gone["pos"]
        self.sess_of.pop(char, None)

    # ---------------------------------------------------------------- Ansicht ----
    def _snapshot_for(self, char: str) -> dict[str, Any]:
        me = self.players[char]
        r2 = self.R["view_radius"] ** 2
        others = [{"char": c, "pos": list(p["pos"]), "fight": c in self.fight_of} for c, p in sorted(self.players.items())
                  if c != char and _dist2(p["pos"], me["pos"]) <= r2]
        enemies = [{"id": e["id"], "type": e["type"], "pos": list(e["pos"]), "alive": e["alive"], "fight": e["fight"] is not None, "state": e["state"]}
                   for e in self.enemies if _dist2(e["pos"], me["pos"]) <= r2]
        nodes = [{"id": n["id"], "item": n["item"], "pos": list(n["pos"]), "ready": self.tick_no >= n["ready_at"]}
                 for n in self.nodes if _dist2(n["pos"], me["pos"]) <= r2]
        return {"tick": self.tick_no, "day": self.world.day[0], "you": {"char": char, "pos": list(me["pos"]), "fight": self.fight_of.get(char), "ground": self.terrain.kind_at(*me["pos"])},
                "players": others, "enemies": enemies, "nodes": nodes,
                "zone": {"w": self.R["zone"]["width"], "h": self.R["zone"]["height"]}}
