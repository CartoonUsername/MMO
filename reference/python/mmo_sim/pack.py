"""Kampf gegen mehrere Gegner (Gruppe oder Einzelner gegen ein Rudel). Siehe ADR-0026.

Erweitert den Gruppenkampf (`group.py`) um 1..`max_opponents` Gegner. Deterministisch, ganzzahlig, ohne Zufall. Mit genau einem
Gegner und ohne die neuen Befehle ist das Ergebnis bit-identisch zu `simulate_group` (durch Tests über viele Eingaben gesichert).

* **Gegner** haben je ihren eigenen Zustand (Leben, Betäubung, Verlangsamung, Taumeln, Angriffstakt, Ziel). Das Leben jedes Gegners
  wächst wie im Gruppenkampf mit der Gruppengröße.
* **Fokus:** Jeder Spieler hat einen Fokusgegner (zu Beginn der erste). `target_1`..`target_3` wählen ihn (kostenlos, ohne
  Sperrzeit; ein nicht vorhandener oder gefallener Gegner wird ignoriert). Ist der Fokusgegner gefallen, gilt der erste lebende.
  Leichter/schwerer Schlag, Betäubung und Verlangsamung wirken auf den Fokusgegner (der schwere Schlag auf den bei Beginn gewählten).
* **Flächenangriff (`sweep`):** verursacht allen lebenden Gegnern festen Schaden (`multi.sweep.damage`), zählt als ein `light_hit`
  (kein Vervielfachen von Punkten) und erhöht die Bedrohung um den gesamten Schaden.
* **Gegnerziele:** wie im Gruppenkampf (höchste Bedrohung, Gleichstand kleinster Index), je Gegner beim Beginn des Angriffs.
* **Sieg:** wenn alle Gegner gefallen sind. `opponent_hp` ist die Summe der Lebenspunkte aller Gegner (bei Sieg ≤ 0).
* **Gegnerfähigkeiten (ADR-0033, ab `sim_rules_v6`):** Ein Gegner setzt statt eines normalen Angriffs die erste bereite, sinnvolle Fähigkeit seiner
  Liste ein (feste Reihenfolge = festes Muster); jede wird mit Vorwarnzeit angekündigt (`events`). Wuchtschlag, Flächenschlag und Zustandsangriffe
  gehen durch dieselbe Abwehr wie normale Treffer (Ausweichen, Blocken, Parieren); Zauber und Heilen sind unterbrechbar (Betäubung oder schwerer Treffer);
  Gegnerschilde brechen durch Parade oder präzise/schwere Treffer; Phasen fügen ab einem Lebensanteil Fähigkeiten hinzu und beschleunigen (mit Boden);
  beschworene Gegner zählen für den Sieg. Ohne `enemy_abilities` in den Regeln (oder ohne Fähigkeiten) ändert sich nichts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SimError
from .fight import EncounterResult
from .group import _Group, _P, _validated
from .enemies import abilities_at, effective_interval, extra_commands
from .rules import COMMANDS, GROUP_COMMANDS, MULTI_COMMANDS, skill_commands, skills


@dataclass(frozen=True)
class PackResult:
    outcome: str  # victory | defeat | fled
    ticks: int
    opponent_hp: int  # Summe über alle Gegner
    opponents: tuple[int, ...]  # Lebenspunkte je Gegner (≤ 0: gefallen)
    players: tuple[EncounterResult, ...]
    events: tuple[dict[str, Any], ...] = ()  # Ankündigungen/Ergebnisse der Gegnerfähigkeiten (ADR-0033)


class _E:
    """Zustand eines Gegners."""

    def __init__(self, hp: int, spec: dict[str, Any], type_name: str = "", base_abilities: list[str] | None = None, summoner: int | None = None) -> None:
        self.spec, self.hp, self.max_hp = spec, hp, hp
        self.type, self.base_abil, self.summoner = type_name, list(base_abilities or []), summoner
        self.cds: dict[str, int] = {}
        self.cast: dict[str, Any] | None = None
        self.shield_hp = self.shield_until = self.haste_until = self.phase_idx = 0
        self.haste_factor = 1000
        self.shield_breakers: tuple[str, ...] = ()
        self.stun_until = self.slow_until = self.stagger_until = 0
        interval = spec["attack_interval"]
        self.next_start: int | None = interval if interval > 0 else None
        self.hit_tick: int | None = None
        self.hit_target: int | None = None
        self.burn: list[int] | None = None  # [Ende, nächster Tick, Schaden, Abstand, Verursacher]

    @property
    def alive(self) -> bool:
        return self.hp > 0


class _Pack(_Group):
    def __init__(self, cfg: dict[str, Any], opponent_types: Any, specs: list[Any], abilities: Any = None) -> None:
        m = cfg.get("multi")
        if m is None:
            raise SimError("Diese Regeln kennen keinen Kampf gegen mehrere Gegner")
        if not isinstance(opponent_types, (list, tuple)) or not 1 <= len(opponent_types) <= m["max_opponents"]:
            raise SimError(f"Es müssen 1..{m['max_opponents']} Gegner sein")
        for t in opponent_types:
            if not isinstance(t, str) or t not in cfg["opponents"]:
                raise SimError(f"unbekannter Gegner: {t!r}")
        self.cfg, self.A, self.G, self.M = cfg, cfg["actions"], cfg["group"], m
        self.ps = [_P(cfg, lvl, spec, inputs) for spec, lvl, inputs in specs]
        self.SK = skills(cfg)
        for p in self.ps:
            p.cd["sweep"] = 0
            p.focus = 0
            p.evade_until = p.mit_until = -1
            p.mit_permille = 1000
            for name in self.SK:
                p.cd[name] = 0
        self.scale = 1000 + self.G["opponent_hp_per_extra_member_permille"] * (len(self.ps) - 1)
        self.EA = cfg.get("enemy_abilities")
        self.AT = self.EA["abilities"] if self.EA else {}
        self.events: list[dict[str, Any]] = []
        base = self._base_abilities(opponent_types, abilities)
        self.es = [_E(cfg["opponents"][t]["hp"] * self.scale // 1000, cfg["opponents"][t], t, base[i]) for i, t in enumerate(opponent_types)]
        for p in self.ps:
            p.stunned_until = p.slowed_until = 0
            p.burn = None

    def _base_abilities(self, types: Any, abilities: Any) -> list[list[str]]:
        if abilities is None:
            return [list(self.cfg["opponents"][t].get("abilities", [])) if self.EA else [] for t in types]
        if (not self.EA or not isinstance(abilities, (list, tuple)) or len(abilities) != len(types)
                or any(not isinstance(a, (list, tuple)) or len(set(a)) != len(a) or any(x not in self.AT for x in a) for a in abilities)):
            raise SimError("abilities muss je Gegner eine Liste eindeutiger bekannter Fähigkeiten sein (und braucht enemy_abilities)")
        return [list(a) for a in abilities]

    # -- Hilfen ------------------------------------------------------------------
    def _focus(self, p: Any) -> _E:
        if self.es[p.focus].alive:
            return self.es[p.focus]
        # Fällt der letzte Gegner mitten im Tick, wirken spätere Schläge desselben Ticks noch (wie im Gruppenkampf)
        return next((e for e in self.es if e.alive), self.es[p.focus])

    def _first_alive(self) -> int | None:
        return next((i for i, e in enumerate(self.es) if e.alive), None)

    def _interval_of(self, e: _E, at: int) -> int:
        base = e.spec["attack_interval"]
        if self.EA and e.type:
            _, factor = abilities_at(self.cfg, e.type, e.base_abil, self._hp_permille(e))
            if at < e.haste_until:
                factor = factor * self._haste_factor(e) // 1000
            if factor != 1000:
                base = effective_interval(self.cfg, e.type, factor)
        return base * self.A["slow"]["interval_permille"] // 1000 if at < e.slow_until else base

    def _hp_permille(self, e: _E) -> int:
        return max(0, e.hp) * 1000 // e.max_hp

    def _haste_factor(self, e: _E) -> int:
        return e.haste_factor

    @staticmethod
    def _vulnerable_e(e: _E, t: int) -> bool:
        return t < e.stagger_until or t < e.stun_until

    # -- Spielerbefehle ------------------------------------------------------------
    def command(self, idx: int, t: int, cmd: str) -> None:
        p = self.ps[idx]
        if cmd in GROUP_COMMANDS:
            return self._support(idx, t, cmd)
        if cmd.startswith("target_"):
            n = int(cmd[-1]) - 1
            if n < len(self.es) and self.es[n].alive:
                p.focus = n
            else:
                p.ignored += 1
            return
        a = self.M["sweep"] if cmd == "sweep" else self.SK[cmd] if cmd in self.SK else self.A[cmd]
        cost = max(0, a["cost"] + (p.fx_get("dodge_cost_delta") if cmd == "dodge" else 0))
        cooldown = max(0, a["cooldown"] + (p.fx_get("dodge_cooldown_delta") if cmd == "dodge" else 0))
        if t < p.busy_until or p.stam < cost or (cmd in p.cd and t < p.cd[cmd]):
            p.ignored += 1
            return
        e = self._focus(p)
        if cmd == "light":
            precise = self._vulnerable_e(e, t)
            if precise:
                a = self.A["precise"]
                p.count("precise_hit")
            else:
                p.count("light_hit")
            dealt = p.scaled(a["damage"], "light_damage_permille")
            self._hurt(e, dealt, t, "precise_hit" if precise else "light")
            p.threat += dealt
        elif cmd == "sweep":
            for x in self.es:
                if x.alive:
                    self._hurt(x, a["damage"], t, "sweep")
                    p.threat += a["damage"]
            p.count("light_hit")
        elif cmd in self.SK:
            self._skill(idx, e, cmd, a, t)
        elif cmd == "heavy":
            p.heavy_pending = (t + a["windup"], p.scaled(a["damage"], "heavy_damage_permille"), self.es.index(e))
        elif cmd == "dodge":
            p.dodge_start, p.dodge_until = t, t + a["active"]
        elif cmd == "block":
            p.block_start, p.block_until = t, t + a["active"]
        elif cmd == "stun":
            e.stun_until = t + a["ticks"] + p.fx_get("stun_ticks_bonus")
            e.hit_tick = None
            self._interrupt(e, t)
            if e.next_start is not None:
                e.next_start = e.stun_until + self._interval_of(e, t)
            p.count("stun_applied")
        elif cmd == "slow":
            e.slow_until = t + a["ticks"] + p.fx_get("slow_ticks_bonus")
            p.count("slow_applied")
        busy = a["busy"]
        if t < p.slowed_until:                                      # Verlangsamung durch einen Gegner (ADR-0033)
            pm = self.EA["player_slow_permille"]
            busy, cooldown = busy * pm // 1000, cooldown * pm // 1000
        p.stam -= cost
        p.busy_until = t + busy
        if cmd in p.cd:
            p.cd[cmd] = t + cooldown

    def _skill(self, idx: int, e: _E, cmd: str, a: dict[str, Any], t: int) -> None:
        """Eigene Fähigkeitsbefehle (ADR-0027)."""
        p, kind = self.ps[idx], a["kind"]
        if kind == "burst_dot":
            self._hurt(e, a["damage"], t, "skill")
            p.threat += a["damage"]
            d = a["dot"]
            e.burn = [t + d["ticks"], t + d["interval"], d["damage"], d["interval"], idx]  # neuer Einsatz ersetzt den alten
        elif kind == "evade":
            p.evade_until = t + a["ticks"]
        elif kind == "mitigate":
            p.mit_until, p.mit_permille = t + a["ticks"], a["damage_permille"]
        else:
            p.stam = min(self.cfg["player"]["stamina_max"], p.stam + a["amount"])
        if a["counts_as"]:
            p.count(a["counts_as"])

    def _burn(self, t: int) -> None:
        for e in self.es:
            b = e.burn
            if b is None or not e.alive:
                continue
            if t >= b[1]:
                self._hurt(e, b[2], t, "dot")
                self.ps[b[4]].threat += b[2]
                b[1] += b[3]
                if b[1] > b[0]:
                    e.burn = None

    def _taken_by(self, p: Any, amount: int, t: int) -> int:
        return amount * p.mit_permille // 1000 if t < p.mit_until else amount

    # -- Gegner --------------------------------------------------------------------
    def opponents(self, t: int) -> None:
        for e in list(self.es):                                     # beschworene Gegner kommen erst im nächsten Tick an die Reihe
            if not e.alive:
                continue
            if e.cast is not None:
                if t >= e.cast["end"]:
                    self._resolve_cast(e, t)
                continue
            if e.next_start is None:
                continue
            if e.hit_tick is None and t >= e.next_start:
                if t < e.stun_until:
                    e.next_start = e.stun_until
                elif not (self.EA and self._start_ability(e, t)):
                    e.hit_tick = t + e.spec["windup"]
                    e.hit_target = self._target()
            if e.hit_tick == t:
                self._resolve_hit_of(e, t)

    def _hit_player(self, e: _E, tgt: int, amount: int, t: int) -> tuple[str, int]:
        """Ein Treffer des Gegners `e` auf Spieler `tgt` mit Grundschaden `amount`; Rückgabe: (Ausgang, zusätzliches Taumeln)."""
        a, extra = self.A, 0
        p = self.ps[tgt]
        if t < p.evade_until:
            outcome = "evade"
        elif p.dodge_start <= t < p.dodge_until:
            outcome = "perfect_dodge" if t - p.dodge_start < a["dodge"]["perfect_window"] else "dodge"
            p.count(outcome)
        elif p.block_start <= t < p.block_until:
            if t - p.block_start < a["block"]["parry_window"]:
                outcome = "parry"
                p.count("parry")
                extra = e.spec["stagger"] + p.fx_get("parry_stagger_bonus")
                e.stagger_until = t + extra
                self._break_shield(e, "parry", t)
            else:
                outcome = "block"
                p.count("block")
                self._damage_to(p, self._taken_by(p, p.scaled(amount * min(a["block"]["damage_permille"], p.fx.get("block_damage_permille", 1000)) // 1000,
                                                              "damage_taken_permille"), t), t)
        else:
            outcome = "hit"
            self._damage_to(p, self._taken_by(p, p.scaled(amount, "damage_taken_permille"), t), t)
        return outcome, extra

    def _resolve_hit_of(self, e: _E, t: int) -> None:
        extra = 0
        tgt = e.hit_target
        if tgt is None or not self.ps[tgt].active:
            tgt = self._target()
        if tgt is not None:
            _, extra = self._hit_player(e, tgt, e.spec["damage"], t)
        e.hit_tick = None
        e.hit_target = None
        e.next_start = t + self._interval_of(e, t) + extra

    # -- Gegnerfähigkeiten (ADR-0033) ----------------------------------------------------
    def _hurt(self, e: _E, amount: int, t: int, kind: str) -> None:
        """Schaden an einem Gegner; ein aktives Schild schluckt ihn, brechende Arten (Parade, präzise/schwere Treffer) nehmen es weg."""
        if e.shield_hp > 0 and t < e.shield_until:
            if kind in e.shield_breakers:
                e.shield_hp = 0
                self.events.append({"t": t, "type": "shield_broken", "enemy": self.es.index(e), "by": kind})
            else:
                absorbed = min(e.shield_hp, amount)
                e.shield_hp -= absorbed
                amount -= absorbed
        e.hp -= amount

    def _break_shield(self, e: _E, kind: str, t: int) -> None:
        if e.shield_hp > 0 and t < e.shield_until and kind in e.shield_breakers:
            e.shield_hp = 0
            self.events.append({"t": t, "type": "shield_broken", "enemy": self.es.index(e), "by": kind})

    def _interrupt(self, e: _E, t: int) -> None:
        """Betäubung oder schwerer Treffer unterbricht eine unterbrechbare Fähigkeit: sie entfällt, der Gegner taumelt."""
        c = e.cast
        if c is None or not self.AT[c["name"]]["interruptible"]:
            return
        e.cast = None
        e.stagger_until = max(e.stagger_until, t + e.spec["stagger"])
        e.next_start = t + self._interval_of(e, t)
        self.events.append({"t": t, "type": "interrupted", "enemy": self.es.index(e), "ability": c["name"]})

    def _ready(self, e: _E, name: str, t: int) -> bool:
        ab = self.AT[name]
        if t < e.cds.get(name, 0):
            return False
        kind = ab["kind"]
        idx = self.es.index(e)
        alive_allies = [x for x in self.es if x.alive and x is not e]
        if kind in ("slam", "area", "state", "cast"):
            return self._target() is not None
        if kind == "shield":
            return not (e.shield_hp > 0 and t < e.shield_until)
        if kind == "heal_ally":
            return self._heal_target(e) is not None
        if kind == "buff_allies":
            return bool(alive_allies) and any(x.alive and t >= x.haste_until for x in self.es)
        if kind == "summon":
            mine = sum(1 for x in self.es if x.alive and x.summoner == idx and x.type == ab["summon"])
            return (mine + ab["count"] <= ab["max_alive"] and sum(1 for x in self.es if x.alive) + ab["count"] <= self.EA["max_enemies"]
                    and len(self.es) + ab["count"] <= self.EA["max_enemies"] * 4)
        return False

    def _heal_target(self, e: _E) -> int | None:
        best = None
        for i, x in enumerate(self.es):
            if x.alive and x is not e and x.hp * 1000 < self.EA["heal_threshold_permille"] * x.max_hp:
                if best is None or x.hp * 1000 // x.max_hp < self.es[best].hp * 1000 // self.es[best].max_hp:
                    best = i
        return best

    def _start_ability(self, e: _E, t: int) -> bool:
        abilities, _ = abilities_at(self.cfg, e.type, e.base_abil, self._hp_permille(e))
        for name in abilities:
            if not self._ready(e, name, t):
                continue
            ab = self.AT[name]
            e.cds[name] = t + ab["cooldown"]
            target = self._target() if ab["kind"] in ("slam", "state", "cast") else None
            e.cast = {"name": name, "end": t + ab["windup"], "target": target}
            e.hit_tick = None
            self.events.append({"t": t, "type": "telegraph", "enemy": self.es.index(e), "ability": name, "kind": ab["kind"],
                                "ticks": ab["windup"], "target": target, "answers": list(ab["answers"])})
            return True
        return False

    def _apply_state(self, p: Any, ab: dict[str, Any], t: int) -> None:
        if ab["state"] == "stun":
            p.stunned_until = max(p.stunned_until, t + ab["ticks"])
            p.heavy_pending = None
        elif ab["state"] == "slow":
            p.slowed_until = max(p.slowed_until, t + ab["ticks"])

    def _resolve_cast(self, e: _E, t: int) -> None:
        c = e.cast
        assert c is not None
        e.cast = None
        ab = self.AT[c["name"]]
        kind, extra, idx = ab["kind"], 0, self.es.index(e)
        res: dict[str, Any] = {"t": t, "type": "resolved", "enemy": idx, "ability": c["name"]}
        if kind in ("slam", "state"):
            tgt = c["target"]
            if tgt is None or not self.ps[tgt].active:
                tgt = self._target()
            if tgt is not None:
                outcome, extra = self._hit_player(e, tgt, e.spec["damage"] * ab["damage_permille"] // 1000, t)
                res.update(target=tgt, outcome=outcome)
                if kind == "state" and outcome == "hit":
                    self._apply_state(self.ps[tgt], ab, t)
        elif kind == "area":
            outcomes = {}
            for i, p in enumerate(self.ps):
                if p.active:
                    outcome, ex = self._hit_player(e, i, e.spec["damage"] * ab["damage_permille"] // 1000, t)
                    outcomes[str(i)] = outcome
                    extra = max(extra, ex)
            res["outcomes"] = outcomes
        elif kind == "cast":
            tgt = c["target"]
            if tgt is None or not self.ps[tgt].active:
                tgt = self._target()
            if tgt is not None:
                self.ps[tgt].burn = [t + ab["ticks"], t + ab["interval"], ab["tick_damage"], ab["interval"]]
                res["target"] = tgt
        elif kind == "shield":
            e.shield_hp, e.shield_until, e.shield_breakers = ab["absorb"], t + ab["ticks"], tuple(ab["breakable_by"])
        elif kind == "heal_ally":
            ally = self._heal_target(e)
            if ally is not None:
                x = self.es[ally]
                x.hp = min(x.max_hp, x.hp + x.max_hp * ab["amount_permille"] // 1000)
                res["ally"] = ally
        elif kind == "buff_allies":
            for x in self.es:
                if x.alive:
                    x.haste_until, x.haste_factor = t + ab["ticks"], ab["attack_interval_permille"]
        elif kind == "summon":
            spec = self.cfg["opponents"][ab["summon"]]
            made = []
            for _ in range(ab["count"]):
                n = _E(spec["hp"] * self.scale // 1000, spec, ab["summon"], list(spec.get("abilities", [])), idx)
                n.next_start = t + self._interval_of(n, t) if spec["attack_interval"] > 0 else None
                self.es.append(n)
                made.append(len(self.es) - 1)
            res["summoned"] = made
        e.next_start = t + self._interval_of(e, t) + extra if e.spec["attack_interval"] > 0 else None
        self.events.append(res)

    def _player_burn(self, t: int) -> None:
        for p in self.ps:
            b = p.burn
            if b is None or not p.active:
                continue
            if t >= b[1]:
                self._damage_to(p, b[2], t)
                b[1] += b[3]
                if b[1] > b[0]:
                    p.burn = None

    def _phases(self, t: int) -> None:
        for i, e in enumerate(self.es):
            ph = self.cfg["opponents"][e.type].get("phases") if e.type else None
            if not ph or not e.alive:
                continue
            reached = sum(1 for x in ph if self._hp_permille(e) < x["at_permille"])
            if reached > e.phase_idx:
                e.phase_idx = reached
                self.events.append({"t": t, "type": "phase", "enemy": i, "phase": reached})

    # -- Ablauf --------------------------------------------------------------------
    def tick(self, t: int) -> PackResult | None:
        """Ein Simulationstick; Ergebnis, wenn der Kampf in diesem Tick endet (sonst None)."""
        cfg = self.cfg
        for idx, p in enumerate(self.ps):
            while p.active and p.i < len(p.inputs) and p.inputs[p.i][0] == t:
                cmd = p.inputs[p.i][1]
                p.i += 1
                if cmd == "flee":
                    p.state, p.end_tick, p.heavy_pending = "fled", t, None
                    break
                if p.allowed is not None and cmd not in p.allowed:
                    p.ignored += 1
                    continue
                if t < p.stunned_until:                                   # betäubt: alle Befehle außer Flucht werden ignoriert
                    p.ignored += 1
                    continue
                self.command(idx, t, cmd)
        if not any(p.active for p in self.ps):
            return self._pack_result(t, "none")
        for p in self.ps:
            if p.active and p.heavy_pending and p.heavy_pending[0] == t:
                e = self.es[p.heavy_pending[2]]
                if not e.alive:
                    e = self.es[self._first_alive()] if self._first_alive() is not None else e
                self._hurt(e, p.heavy_pending[1], t, "heavy_hit")
                p.threat += p.heavy_pending[1]
                p.count("heavy_hit")
                p.heavy_pending = None
                self._interrupt(e, t)
        self._burn(t)
        if not any(e.alive for e in self.es):
            return self._pack_result(t + 1, "victory")
        if self.EA:
            self._phases(t)
            self._player_burn(t)
        self.opponents(t)
        for p in self.ps:
            if p.active and p.hp <= 0:
                p.state, p.end_tick, p.heavy_pending = "down", t + 1, None
        if not any(p.active for p in self.ps):
            return self._pack_result(t + 1, "none")
        for p in self.ps:
            if p.active:
                p.stam = min(cfg["player"]["stamina_max"], p.stam + cfg["player"]["stamina_regen_per_tick"] + p.fx_get("stamina_regen_bonus"))
        return None

    def run(self) -> PackResult:  # type: ignore[override]
        for t in range(self.cfg["max_ticks"]):
            res = self.tick(t)
            if res is not None:
                return res
        return self._pack_result(self.cfg["max_ticks"], "timeout")

    def _pack_result(self, ticks: int, how: str) -> PackResult:
        self.opp_hp = sum(e.hp for e in self.es)
        g = self._result(ticks, how)
        return PackResult(g.outcome, g.ticks, g.opponent_hp, tuple(e.hp for e in self.es), g.players, tuple(self.events))


def simulate_pack(cfg: dict[str, Any], opponent_types: Any, players: Any, abilities: Any = None) -> PackResult:
    """`opponent_types`: Liste von 1..max_opponents Gegnertypen; `players` wie bei `simulate_group`; `abilities` optional je Gegner die Fähigkeiten
    (sonst die festen der Vorlage, ADR-0033). Fehler -> SimError."""
    return _Pack(cfg, opponent_types, _validated(cfg, players, MULTI_COMMANDS + skill_commands(cfg) + extra_commands(cfg)), abilities).run()


def strongest(cfg: dict[str, Any], opponent_types: Any) -> str:
    """Gegnertyp für den Bericht: höchste Stufe, bei Gleichstand der erste."""
    return max(opponent_types, key=lambda t: (cfg["opponents"][t]["level"], -list(opponent_types).index(t)))
