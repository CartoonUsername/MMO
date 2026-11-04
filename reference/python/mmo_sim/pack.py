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
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SimError
from .fight import EncounterResult
from .group import _Group, _P, _validated
from .rules import COMMANDS, GROUP_COMMANDS, MULTI_COMMANDS, skill_commands, skills


@dataclass(frozen=True)
class PackResult:
    outcome: str  # victory | defeat | fled
    ticks: int
    opponent_hp: int  # Summe über alle Gegner
    opponents: tuple[int, ...]  # Lebenspunkte je Gegner (≤ 0: gefallen)
    players: tuple[EncounterResult, ...]


class _E:
    """Zustand eines Gegners."""

    def __init__(self, hp: int, spec: dict[str, Any]) -> None:
        self.spec, self.hp = spec, hp
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
    def __init__(self, cfg: dict[str, Any], opponent_types: Any, specs: list[Any]) -> None:
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
        scale = 1000 + self.G["opponent_hp_per_extra_member_permille"] * (len(self.ps) - 1)
        self.es = [_E(cfg["opponents"][t]["hp"] * scale // 1000, cfg["opponents"][t]) for t in opponent_types]

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
        return base * self.A["slow"]["interval_permille"] // 1000 if at < e.slow_until else base

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
            if self._vulnerable_e(e, t):
                a = self.A["precise"]
                p.count("precise_hit")
            else:
                p.count("light_hit")
            dealt = p.scaled(a["damage"], "light_damage_permille")
            e.hp -= dealt
            p.threat += dealt
        elif cmd == "sweep":
            for x in self.es:
                if x.alive:
                    x.hp -= a["damage"]
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
            if e.next_start is not None:
                e.next_start = e.stun_until + self._interval_of(e, t)
            p.count("stun_applied")
        elif cmd == "slow":
            e.slow_until = t + a["ticks"] + p.fx_get("slow_ticks_bonus")
            p.count("slow_applied")
        p.stam -= cost
        p.busy_until = t + a["busy"]
        if cmd in p.cd:
            p.cd[cmd] = t + cooldown

    def _skill(self, idx: int, e: _E, cmd: str, a: dict[str, Any], t: int) -> None:
        """Eigene Fähigkeitsbefehle (ADR-0027)."""
        p, kind = self.ps[idx], a["kind"]
        if kind == "burst_dot":
            e.hp -= a["damage"]
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
                e.hp -= b[2]
                self.ps[b[4]].threat += b[2]
                b[1] += b[3]
                if b[1] > b[0]:
                    e.burn = None

    def _taken_by(self, p: Any, amount: int, t: int) -> int:
        return amount * p.mit_permille // 1000 if t < p.mit_until else amount

    # -- Gegner --------------------------------------------------------------------
    def opponents(self, t: int) -> None:
        for e in self.es:
            if not e.alive or e.next_start is None:
                continue
            if e.hit_tick is None and t >= e.next_start:
                if t < e.stun_until:
                    e.next_start = e.stun_until
                else:
                    e.hit_tick = t + e.spec["windup"]
                    e.hit_target = self._target()
            if e.hit_tick == t:
                self._resolve_hit_of(e, t)

    def _resolve_hit_of(self, e: _E, t: int) -> None:
        a, extra = self.A, 0
        tgt = e.hit_target
        if tgt is None or not self.ps[tgt].active:
            tgt = self._target()
        if tgt is not None:
            p = self.ps[tgt]
            if t < p.evade_until:
                pass
            elif p.dodge_start <= t < p.dodge_until:
                p.count("perfect_dodge" if t - p.dodge_start < a["dodge"]["perfect_window"] else "dodge")
            elif p.block_start <= t < p.block_until:
                if t - p.block_start < a["block"]["parry_window"]:
                    p.count("parry")
                    extra = e.spec["stagger"] + p.fx_get("parry_stagger_bonus")
                    e.stagger_until = t + extra
                else:
                    p.count("block")
                    self._damage_to(p, self._taken_by(p, p.scaled(e.spec["damage"] * min(a["block"]["damage_permille"], p.fx.get("block_damage_permille", 1000)) // 1000,
                                                                  "damage_taken_permille"), t), t)
            else:
                self._damage_to(p, self._taken_by(p, p.scaled(e.spec["damage"], "damage_taken_permille"), t), t)
        e.hit_tick = None
        e.hit_target = None
        e.next_start = t + self._interval_of(e, t) + extra

    # -- Ablauf --------------------------------------------------------------------
    def run(self) -> PackResult:  # type: ignore[override]
        cfg = self.cfg
        for t in range(cfg["max_ticks"]):
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
                    self.command(idx, t, cmd)
            if not any(p.active for p in self.ps):
                return self._pack_result(t, "none")
            for p in self.ps:
                if p.active and p.heavy_pending and p.heavy_pending[0] == t:
                    e = self.es[p.heavy_pending[2]]
                    if not e.alive:
                        e = self.es[self._first_alive()] if self._first_alive() is not None else e
                    e.hp -= p.heavy_pending[1]
                    p.threat += p.heavy_pending[1]
                    p.count("heavy_hit")
                    p.heavy_pending = None
            self._burn(t)
            if not any(e.alive for e in self.es):
                return self._pack_result(t + 1, "victory")
            self.opponents(t)
            for p in self.ps:
                if p.active and p.hp <= 0:
                    p.state, p.end_tick, p.heavy_pending = "down", t + 1, None
            if not any(p.active for p in self.ps):
                return self._pack_result(t + 1, "none")
            for p in self.ps:
                if p.active:
                    p.stam = min(cfg["player"]["stamina_max"], p.stam + cfg["player"]["stamina_regen_per_tick"] + p.fx_get("stamina_regen_bonus"))
        return self._pack_result(cfg["max_ticks"], "timeout")

    def _pack_result(self, ticks: int, how: str) -> PackResult:
        self.opp_hp = sum(e.hp for e in self.es)
        g = self._result(ticks, how)
        return PackResult(g.outcome, g.ticks, g.opponent_hp, tuple(e.hp for e in self.es), g.players)


def simulate_pack(cfg: dict[str, Any], opponent_types: Any, players: Any) -> PackResult:
    """`opponent_types`: Liste von 1..max_opponents Gegnertypen; `players` wie bei `simulate_group`. Fehler -> SimError."""
    return _Pack(cfg, opponent_types, _validated(cfg, players, MULTI_COMMANDS + skill_commands(cfg))).run()


def strongest(cfg: dict[str, Any], opponent_types: Any) -> str:
    """Gegnertyp für den Bericht: höchste Stufe, bei Gleichstand der erste."""
    return max(opponent_types, key=lambda t: (cfg["opponents"][t]["level"], -list(opponent_types).index(t)))
