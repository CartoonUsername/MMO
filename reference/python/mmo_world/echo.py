"""Kampfechos und Resonanz +0..+30 (AP 7, ADR-0046). Serverautoritativ, atomar, ohne Cliententscheidung über Erfolg.

* Ein Echo ist ein einzigartiges Objekt (kein Stapel): Definition, Besitzer, Bindung, Resonanzstufe, Pechschutzzähler.
* Zustände: unaktiviert (handelbar) -> aktiviert + charaktergebunden -> mit Resonanzsiegel wieder handelbar (Stufe bleibt).
* Upgrade: ein Versuch kostet Material und Münzen (immer), Erfolg erhöht die Stufe, Fehlschlag verliert nur die Kosten; ab
  `drop_from_level` sinkt die Stufe um 1, außer ein Schutzgegenstand verhindert es. Ein Echo wird nie zerstört. Pechschutz hebt die
  Chance nach Fehlschlägen schrittweise. Der Wurf ist ein serverseitiger, deterministisch nachvollziehbarer Hash aus geheimem Seed,
  Echo und Versuchszähler. `request_id` macht Wiederholungen idempotent (Replay-Schutz).
* Persönliche Meisterschaft gehört der Figur und der Tradition, nicht dem Objekt: sie wechselt beim Verkauf nicht den Besitzer.
Alle Zahlen sind Platzhalter (Blueprint-Fragen 7-9 offen).
"""
from __future__ import annotations

import hashlib
import json
import secrets
from importlib import resources
from typing import Any, Callable

from mmo_cee.service import CharacterService

from .errors import WorldError
from .inventory import Inventory

SINK = "world:sink"
# Wirkungen, die die Kampfsimulation kennt: Schlüssel -> (Art, Mindestwert, Höchstwert) – wie mmo_sim.rules.EFFECT_KEYS
COMBAT_KEYS = {"heavy_damage_permille": ("mul", 1, 10000), "light_damage_permille": ("mul", 1, 10000),
               "damage_taken_permille": ("mul", 1, 10000), "block_damage_permille": ("min", 0, 1000), "dodge_cost_delta": ("add", -100, 100)}


def load_echo_rules(name: str = "echo_rules_v2.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_echo_rules(r: dict[str, Any]) -> None:
    m = r["max_resonance"]
    if not _is_int(m) or m < 1 or len(r["success_permille"]) != m or any(not _is_int(x) or not 0 <= x <= 1000 for x in r["success_permille"]):
        raise WorldError("echo_rules: success_permille muss je Stufe einen Wert 0..1000 haben")
    if not r["bands"] or r["bands"][0]["from"] != 0 or [b["from"] for b in r["bands"]] != sorted({b["from"] for b in r["bands"]}):
        raise WorldError("echo_rules: bands müssen bei 0 beginnen und aufsteigen")
    if not 1 <= r["drop_from_level"] <= m:
        raise WorldError("echo_rules: drop_from_level ungültig")
    if r["slots"]["main"] < 1 or r["slots"]["hybrid"] < 0:
        raise WorldError("echo_rules: slots ungültig")
    c = r.get("combat")
    if c is not None:
        if not _is_int(c["hybrid_permille"]) or not 0 <= c["hybrid_permille"] <= 1000 or not _is_int(c["mastery_permille_per_level"]) or c["mastery_permille_per_level"] < 0:
            raise WorldError("echo_rules: combat ungültig")
        for trad, prof in c["profiles"].items():
            if trad not in r["echoes"] or not prof or any(k not in COMBAT_KEYS or not _is_int(v) or v == 0 for k, v in prof.items()):
                raise WorldError(f"echo_rules: combat.profiles.{trad} ungültig")
    for k in ("dust", "protect", "seal"):
        if "@" not in r["items"][k]:
            raise WorldError("echo_rules: items ungültig")


class EchoService:
    def __init__(self, service: CharacterService, inventory: Inventory, coin: str, rules: dict[str, Any],
                 day_provider: Callable[[], int], seed: str | None = None) -> None:
        validate_echo_rules(rules)
        self.cee, self.inv, self.coin, self.R, self.day = service, inventory, coin, rules, day_provider
        self.seed = seed or secrets.token_hex(16)
        self.echoes: dict[str, dict[str, Any]] = {}
        self.listings: dict[str, dict[str, Any]] = {}
        self.equipped: dict[str, dict[str, Any]] = {}
        self.mastery: dict[str, dict[str, int]] = {}
        self.mastery_day: dict[str, list[int]] = {}
        self.awards: dict[str, list[str]] = {}
        self._counter = 0
        self._listing_counter = 0
        self.notify: Callable[[str, str, dict[str, Any]], None] = lambda recipient, kind, data: None

    @property
    def active(self) -> bool:
        return self._counter > 0

    # -- Hilfen -------------------------------------------------------------------
    def _get(self, eid: str) -> dict[str, Any]:
        e = self.echoes.get(eid) if isinstance(eid, str) else None
        if e is None:
            raise WorldError("Kampfecho unbekannt")
        return e

    def _mine(self, char: str, eid: str) -> dict[str, Any]:
        e = self._get(eid)
        if e["owner"] != char:
            raise WorldError("Dieses Kampfecho gehört dir nicht")
        return e

    def _class_ok(self, char: str, e: dict[str, Any]) -> None:
        allowed = self.R["echoes"][e["def"]]["classes"]
        if allowed is None:
            return
        base = self.cee.state(char).parts["identity"].get("base_class")
        if base is None:
            raise WorldError("Wähle zuerst eine Grundklasse")
        if base not in allowed:
            raise WorldError("Deine Klasse kann dieses Kampfecho nicht nutzen")

    def band(self, level: int) -> dict[str, Any]:
        return [b for b in self.R["bands"] if b["from"] <= level][-1]

    def tradable(self, e: dict[str, Any]) -> bool:
        return e["bound_to"] is None and e["listing"] is None

    def cost(self, level: int) -> dict[str, int]:
        c = self.R["cost"]
        return {"dust": c["dust_base"] + level // c["dust_per_levels"], "coins": c["coins_per_level"] * (level + 1)}

    def chance(self, e: dict[str, Any]) -> int:
        p = self.R["pity"]
        return min(1000, self.R["success_permille"][e["resonance"]] + min(p["cap_permille"], e["pity"] * p["step_permille"]))

    def _roll(self, e: dict[str, Any]) -> int:
        h = hashlib.sha256(f"{self.seed}|{e['id']}|{e['attempts']}".encode()).hexdigest()
        return int(h[:12], 16) % 1000

    # -- Entstehung (nur serverintern) -----------------------------------------------
    def mint(self, def_id: str, owner: str) -> str:
        if def_id not in self.R["echoes"]:
            raise WorldError("Unbekannte Echo-Definition")
        self._counter += 1
        eid = f"echo-{self._counter:08d}"
        self.echoes[eid] = {"id": eid, "def": def_id, "owner": owner, "bound_to": None, "activated": False, "resonance": 0,
                            "pity": 0, "attempts": 0, "listing": None, "requests": {}}
        return eid

    def award_once(self, char: str, def_id: str) -> str | None:
        """Schenkt einer Figur ein Echo einer Definition genau einmal (auch nach Verkauf nicht erneut). Rückgabe: Echo-ID oder None."""
        got = self.awards.setdefault(char, [])
        if def_id in got:
            return None
        got.append(def_id)
        return self.mint(def_id, char)

    # -- Aktivierung / Bindung -------------------------------------------------------
    def activate(self, char: str, eid: str) -> dict[str, Any]:
        e = self._mine(char, eid)
        if e["bound_to"] is not None:
            raise WorldError("Bereits an dich gebunden")
        if e["listing"] is not None:
            raise WorldError("Das Kampfecho steht zum Verkauf")
        self._class_ok(char, e)
        e["activated"], e["bound_to"] = True, char
        return self._public(e)

    def release(self, char: str, eid: str) -> dict[str, Any]:
        e = self._mine(char, eid)
        if e["bound_to"] != char:
            raise WorldError("Das Kampfecho ist nicht gebunden")
        if self._slot_of(char, eid):
            raise WorldError("Rüste das Kampfecho zuerst ab")
        self.inv.apply(char, {self.R["items"]["seal"]: 1}, {})
        e["bound_to"] = None
        return self._public(e)

    # -- Ausrüsten ---------------------------------------------------------------------
    def _slot_of(self, char: str, eid: str) -> str | None:
        eq = self.equipped.get(char)
        if not eq:
            return None
        return "main" if eq.get("main") == eid else "hybrid" if eid in eq.get("hybrid", []) else None

    def equip(self, char: str, eid: str, role: str) -> dict[str, Any]:
        e = self._mine(char, eid)
        if e["bound_to"] != char:
            raise WorldError("Nur aktivierte, gebundene Kampfechos lassen sich ausrüsten")
        if role not in ("main", "hybrid"):
            raise WorldError("Rolle muss main oder hybrid sein")
        if self._slot_of(char, eid):
            raise WorldError("Bereits ausgerüstet")
        self._class_ok(char, e)
        eq = self.equipped.setdefault(char, {"main": None, "hybrid": []})
        if role == "main":
            if eq["main"] is not None:
                raise WorldError("Haupttradition ist belegt")
            eq["main"] = eid
        else:
            if len(eq["hybrid"]) >= self.R["slots"]["hybrid"]:
                raise WorldError("Keine freien Hybrid-Plätze")
            tradition = e["def"]
            if any(self.echoes[x]["def"] == tradition for x in eq["hybrid"]) or (eq["main"] and self.echoes[eq["main"]]["def"] == tradition):
                raise WorldError("Diese Tradition ist schon ausgerüstet")
            eq["hybrid"].append(eid)
        return self.loadout(char)

    def unequip(self, char: str, eid: str) -> dict[str, Any]:
        self._mine(char, eid)
        slot = self._slot_of(char, eid)
        if slot is None:
            raise WorldError("Nicht ausgerüstet")
        eq = self.equipped[char]
        if slot == "main":
            eq["main"] = None
        else:
            eq["hybrid"].remove(eid)
        return self.loadout(char)

    def loadout(self, char: str) -> dict[str, Any]:
        eq = self.equipped.get(char) or {"main": None, "hybrid": []}
        return {"main": eq["main"], "hybrid": list(eq["hybrid"]), "slots": dict(self.R["slots"])}

    # -- Resonanz ----------------------------------------------------------------------
    def upgrade(self, char: str, eid: str, protect: bool = False, request_id: str | None = None) -> dict[str, Any]:
        e = self._mine(char, eid)
        if request_id is not None:
            if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
                raise WorldError("request_id ungültig")
            if request_id in e["requests"]:
                return {**e["requests"][request_id], "replayed": True}
        if e["bound_to"] != char:
            raise WorldError("Nur aktivierte, gebundene Kampfechos lassen sich verbessern")
        lvl, it = e["resonance"], self.R["items"]
        if lvl >= self.R["max_resonance"]:
            raise WorldError("Höchste Resonanzstufe erreicht")
        cost = self.cost(lvl)
        remove = {it["dust"]: cost["dust"], self.coin: cost["coins"]}
        if protect and self.inv.balance(char, it["protect"]) < 1:
            raise WorldError("Kein Schutzgegenstand vorhanden")
        for k, n in remove.items():                       # alles prüfen, bevor etwas verändert wird
            if self.inv.balance(char, k) < n:
                raise WorldError(f"Nicht genug {k}: {self.inv.balance(char, k)} < {n}")
        chance, roll = self.chance(e), self._roll(e)
        success = roll < chance
        protected = False
        if not success and lvl >= self.R["drop_from_level"] and protect:
            protected = True
            remove[it["protect"]] = 1
        self.inv.apply(char, remove, {})                  # atomar: Kosten abbuchen (wirft vorher, wenn etwas fehlt)
        e["attempts"] += 1
        before = lvl
        if success:
            e["resonance"], e["pity"] = lvl + 1, 0
        else:
            e["pity"] += 1
            if lvl >= self.R["drop_from_level"] and not protected:
                e["resonance"] = lvl - 1
        res = {"echo": eid, "success": success, "before": before, "after": e["resonance"], "chance_permille": chance, "protected": protected,
               "cost": cost, "band": self.band(e["resonance"])["key"], "pity": e["pity"]}
        if request_id is not None:
            e["requests"][request_id] = res
            while len(e["requests"]) > 20:
                e["requests"].pop(next(iter(e["requests"])))
        return res

    # -- Handel ------------------------------------------------------------------------
    def list_for_sale(self, char: str, eid: str, price: int) -> str:
        e = self._mine(char, eid)
        m = self.R["market"]
        if not self.tradable(e):
            raise WorldError("Gebundene oder bereits angebotene Kampfechos sind nicht handelbar")
        if not _is_int(price) or not 1 <= price <= m["max_price"]:
            raise WorldError("Ungültiger Preis")
        if sum(1 for x in self.listings.values() if x["seller"] == char) >= m["max_listings_per_character"]:
            raise WorldError("Zu viele Angebote")
        self._listing_counter += 1
        lid = f"echo-listing-{self._listing_counter:08d}"
        self.listings[lid] = {"id": lid, "echo": eid, "seller": char, "price": price, "day": self.day()}
        e["listing"] = lid
        return lid

    def cancel_listing(self, char: str, lid: str) -> None:
        li = self.listings.get(lid) if isinstance(lid, str) else None
        if li is None or li["seller"] != char:
            raise WorldError("Angebot unbekannt oder nicht deins")
        self.echoes[li["echo"]]["listing"] = None
        del self.listings[lid]

    def buy(self, buyer: str, lid: str) -> dict[str, Any]:
        li = self.listings.get(lid) if isinstance(lid, str) else None
        if li is None:
            raise WorldError("Angebot unbekannt oder bereits verkauft")
        seller, price, e = li["seller"], li["price"], self.echoes[li["echo"]]
        if buyer == seller:
            raise WorldError("Käufer und Verkäufer müssen verschieden sein")
        fee = price * self.R["market"]["fee_permille"] // 1000
        self.inv.apply_many([(buyer, {self.coin: price}, {}), (seller, {}, {self.coin: price - fee})])  # wirft vor jeder Änderung
        e["owner"], e["listing"] = buyer, None                  # Stufe, Aktivierung und Pechschutz bleiben; Bindung ist gelöst
        del self.listings[lid]
        return {"echo": e["id"], "price": price, "fee": fee, "resonance": e["resonance"]}

    # -- Meisterschaft (persönlich, nicht am Objekt) -----------------------------------
    def grant_mastery(self, char: str, points: int) -> int:
        """Punkte für die Tradition des ausgerüsteten Haupt-Echos; Tageslimit. Gibt die tatsächlich gutgeschriebenen Punkte zurück."""
        eq = self.equipped.get(char)
        if not eq or eq["main"] is None or not _is_int(points) or points <= 0:
            return 0
        day = self.day()
        d = self.mastery_day.get(char)
        used = d[1] if d and d[0] == day else 0
        n = max(0, min(points, self.R["mastery"]["daily_cap"] - used))
        if n:
            t = self.echoes[eq["main"]]["def"]
            self.mastery.setdefault(char, {})[t] = self.mastery.get(char, {}).get(t, 0) + n
            self.mastery_day[char] = [day, used + n]
        return n

    def mastery_level(self, char: str, tradition: str) -> int:
        pts = self.mastery.get(char, {}).get(tradition, 0)
        return sum(1 for t in self.R["mastery"]["thresholds"] if pts >= t)

    # -- Kampfwirkung (AP 17, ADR-0056) --------------------------------------------------
    def _combat_echoes(self, char: str) -> list[tuple[dict[str, Any], int]]:
        """Ausgerüstete Echos mit ihrer Wirkstärke (Promille: Haupt 1000, Hybrid hybrid_permille)."""
        c = self.R.get("combat")
        eq = self.equipped.get(char)
        if not c or not eq:
            return []
        out = []
        if eq.get("main"):
            out.append((self.echoes[eq["main"]], 1000))
        out += [(self.echoes[x], c["hybrid_permille"]) for x in eq.get("hybrid", [])]
        return out

    def sim_effects(self, char: str) -> dict[str, int]:
        """Zusammengefasste Kampfwirkungen der ausgerüsteten Echos (Schlüssel wie EFFECT_KEYS der Simulation); leer ohne Echos."""
        c = self.R.get("combat")
        out: dict[str, int] = {}
        for e, share in self._combat_echoes(char):
            prof = c["profiles"].get(e["def"], {})
            ml = self.mastery_level(char, e["def"])
            power = e["resonance"] * (1000 + c["mastery_permille_per_level"] * ml) // 1000 * share // 1000
            for key, step in prof.items():
                kind, lo, hi = COMBAT_KEYS[key]
                val = step * power // 10 if kind == "add" else 1000 + step * power
                val = max(lo, min(hi, val))
                if key not in out:
                    out[key] = val
                elif kind == "mul":
                    out[key] = max(lo, min(hi, out[key] * val // 1000))
                elif kind == "min":
                    out[key] = min(out[key], val)
                else:
                    out[key] = max(lo, min(hi, out[key] + val))
        return {k: v for k, v in out.items() if v != (0 if COMBAT_KEYS[k][0] == "add" else 1000)}

    def granted_abilities(self, char: str) -> list[str]:
        """Fähigkeiten der ausgerüsteten Traditionen: Haupt-Echo immer, Hybrid-Echo ab Meisterschaftsstufe."""
        c = self.R.get("combat")
        out: list[str] = []
        for e, share in self._combat_echoes(char):
            if share == 1000 or self.mastery_level(char, e["def"]) >= c["hybrid_ability_mastery"]:
                out += [a for a in self.R["echoes"][e["def"]]["abilities"] if a not in out]
        return out

    # -- Sicht -------------------------------------------------------------------------
    def _public(self, e: dict[str, Any]) -> dict[str, Any]:
        d = self.R["echoes"][e["def"]]
        out = {"id": e["id"], "def": e["def"], "name": d["name"], "text": d["text"], "element": d["element"], "classes": d["classes"],
               "abilities": d["abilities"], "owner": e["owner"], "activated": e["activated"], "bound": e["bound_to"] is not None,
               "tradable": self.tradable(e), "listing": e["listing"], "resonance": e["resonance"], "band": self.band(e["resonance"]),
               "visual": f"echo/{e['def']}/{self.band(e['resonance'])['key']}", "pity": e["pity"]}
        if e["resonance"] < self.R["max_resonance"]:
            out["next"] = {"chance_permille": self.chance(e), "cost": self.cost(e["resonance"]),
                           "drop_risk": e["resonance"] >= self.R["drop_from_level"]}
        return out

    def view(self, char: str) -> dict[str, Any]:
        mine = [self._public(e) for e in self.echoes.values() if e["owner"] == char]
        market = [{**li, "echo": self._public(self.echoes[li["echo"]])} for li in self.listings.values() if li["seller"] != char]
        return {"echoes": mine, "loadout": self.loadout(char), "market": market, "items": dict(self.R["items"]),
                "mastery": {t: {"points": p, "level": self.mastery_level(char, t)} for t, p in self.mastery.get(char, {}).items()},
                "max_resonance": self.R["max_resonance"], "bands": self.R["bands"],
                "combat": {"effects": self.sim_effects(char), "abilities": self.granted_abilities(char)}}

    # -- Konsistenz / Persistenz ---------------------------------------------------------
    def check(self) -> list[str]:
        errs: list[str] = []
        for eid, e in self.echoes.items():
            if not 0 <= e["resonance"] <= self.R["max_resonance"]:
                errs.append(f"{eid}: Resonanzstufe außerhalb des Bereichs")
            if e["bound_to"] is not None and (e["bound_to"] != e["owner"] or not e["activated"]):
                errs.append(f"{eid}: Bindung passt nicht zu Besitzer/Aktivierung")
            if e["listing"] is not None and (e["listing"] not in self.listings or self.listings[e["listing"]]["echo"] != eid or e["bound_to"] is not None):
                errs.append(f"{eid}: Angebot inkonsistent")
        for lid, li in self.listings.items():
            if self.echoes.get(li["echo"], {}).get("listing") != lid:
                errs.append(f"{lid}: Angebot ohne passendes Echo")
        for char, eq in self.equipped.items():
            for eid in ([eq["main"]] if eq["main"] else []) + list(eq["hybrid"]):
                x = self.echoes.get(eid)
                if x is None or x["owner"] != char or x["bound_to"] != char:
                    errs.append(f"{char}: ausgerüstetes Echo {eid} nicht gebunden/eigen")
        return errs

    def to_json(self) -> str:
        return json.dumps({"seed": self.seed, "counter": self._counter, "listing_counter": self._listing_counter, "echoes": self.echoes,
                           "listings": self.listings, "equipped": self.equipped, "awards": self.awards, "mastery": self.mastery, "mastery_day": self.mastery_day},
                          sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        d = json.loads(text)
        self.seed, self._counter, self._listing_counter = d["seed"], d["counter"], d["listing_counter"]
        self.echoes, self.listings, self.equipped = d["echoes"], d["listings"], d["equipped"]
        self.mastery, self.mastery_day, self.awards = d["mastery"], d["mastery_day"], d.get("awards", {})
