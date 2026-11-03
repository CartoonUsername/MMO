"""Deterministische 1:1-Kampfsimulation (Ganzzahlen, kein Zufall).

Der Client liefert nur Befehle (Absichten) mit Tick-Zeitpunkt. Ob ein Befehl ausgeführt wird
und ob er trifft, ausweicht oder pariert, entscheidet allein diese Simulation anhand von
Zuständen (Ausdauer, Busy-Zeit, Abklingzeit, Zeitfenster). Aus dem Ergebnis entstehen die
Aktionszähler des Begegnungsberichts – niemals aus Client-Angaben.

Tick-Reihenfolge: 1. Spielerbefehle  2. Schwerer Angriff trifft  3. Sieg-Prüfung
4. Gegner (Anlauf beginnen / Treffer auflösen)  5. Niederlage-Prüfung  6. Ausdauer regenerieren.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import SimError
from .rules import COMMANDS


@dataclass(frozen=True)
class EncounterResult:
    outcome: str
    ticks: int
    actions: dict[str, int]
    player_hp: int
    opponent_hp: int
    ignored_inputs: int
    damage_ticks: tuple[int, ...] = field(default_factory=tuple)


def validate_inputs(cfg: dict[str, Any], inputs: Any) -> list[tuple[int, str]]:
    if not isinstance(inputs, (list, tuple)):
        raise SimError("inputs muss eine Liste sein")
    if len(inputs) > cfg["max_inputs"]:
        raise SimError("zu viele Eingaben")
    out: list[tuple[int, str]] = []
    last = 0
    for item in inputs:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise SimError("jede Eingabe muss [tick, befehl] sein")
        tick, cmd = item
        if not isinstance(tick, int) or isinstance(tick, bool) or not 0 <= tick < cfg["max_ticks"]:
            raise SimError("tick außerhalb des gültigen Bereichs")
        if tick < last:
            raise SimError("Eingaben müssen nach Tick sortiert sein")
        if cmd not in COMMANDS:
            raise SimError(f"unbekannter Befehl: {cmd!r}")
        last = tick
        out.append((tick, cmd))
    return out


class _Fight:
    def __init__(self, cfg: dict[str, Any], opponent_type: str, player_level: int, allowed: Any = None) -> None:
        if opponent_type not in cfg["opponents"]:
            raise SimError(f"unbekannter Gegner: {opponent_type}")
        if not isinstance(player_level, int) or isinstance(player_level, bool) or player_level < 1:
            raise SimError("player_level muss eine positive ganze Zahl sein")
        self.cfg, self.A = cfg, cfg["actions"]
        self.allowed = None if allowed is None else frozenset(allowed)  # None: alle Befehle; sonst nur diese (und immer flee)
        self.opp = cfg["opponents"][opponent_type]
        p = cfg["player"]
        self.hp = p["base_hp"] + p["hp_per_level"] * player_level
        self.stam = p["stamina_max"]
        self.opp_hp = self.opp["hp"]
        self.counts: dict[str, int] = {}
        self.ignored = 0
        self.damage_ticks: list[int] = []
        self.busy_until = 0
        self.cd: dict[str, int] = {"heavy": 0, "dodge": 0, "block": 0, "stun": 0, "slow": 0}
        self.dodge_start = self.dodge_until = self.block_start = self.block_until = -1
        self.heavy_pending: tuple[int, int] | None = None
        self.stun_until = self.slow_until = self.stagger_until = 0
        interval = self.opp["attack_interval"]
        self.next_start: int | None = interval if interval > 0 else None
        self.hit_tick: int | None = None

    # -- Hilfen ------------------------------------------------------------------
    def _count(self, name: str, n: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + n

    def _interval(self, at: int) -> int:
        base = self.opp["attack_interval"]
        return base * self.A["slow"]["interval_permille"] // 1000 if at < self.slow_until else base

    def _vulnerable(self, t: int) -> bool:
        return t < self.stagger_until or t < self.stun_until

    # -- Spielerbefehle ------------------------------------------------------------
    def command(self, t: int, cmd: str) -> None:
        name = "light" if cmd == "light" else cmd
        a = self.A[name]
        if t < self.busy_until or self.stam < a["cost"] or (name in self.cd and t < self.cd[name]):
            self.ignored += 1
            return
        if cmd == "light":
            if self._vulnerable(t):
                a = self.A["precise"]
                self._count("precise_hit")
            else:
                self._count("light_hit")
            self.opp_hp -= a["damage"]
        elif cmd == "heavy":
            self.heavy_pending = (t + a["windup"], a["damage"])
        elif cmd == "dodge":
            self.dodge_start, self.dodge_until = t, t + a["active"]
        elif cmd == "block":
            self.block_start, self.block_until = t, t + a["active"]
        elif cmd == "stun":
            self.stun_until = t + a["ticks"]
            self.hit_tick = None
            if self.next_start is not None:
                self.next_start = self.stun_until + self._interval(t)
            self._count("stun_applied")
        elif cmd == "slow":
            self.slow_until = t + a["ticks"]
            self._count("slow_applied")
        self.stam -= a["cost"]
        self.busy_until = t + a["busy"]
        if name in self.cd:
            self.cd[name] = t + a["cooldown"]

    # -- Gegner -------------------------------------------------------------------
    def opponent(self, t: int) -> None:
        if self.next_start is None:
            return
        if self.hit_tick is None and t >= self.next_start:
            if t < self.stun_until:
                self.next_start = self.stun_until
            else:
                self.hit_tick = t + self.opp["windup"]
        if self.hit_tick == t:
            self._resolve_hit(t)

    def _resolve_hit(self, t: int) -> None:
        a, extra = self.A, 0
        if self.dodge_start <= t < self.dodge_until:
            self._count("perfect_dodge" if t - self.dodge_start < a["dodge"]["perfect_window"] else "dodge")
        elif self.block_start <= t < self.block_until:
            if t - self.block_start < a["block"]["parry_window"]:
                self._count("parry")
                self.stagger_until = t + self.opp["stagger"]
                extra = self.opp["stagger"]
            else:
                self._count("block")
                self.hp -= self.opp["damage"] * a["block"]["damage_permille"] // 1000
                self.damage_ticks.append(t)
        else:
            self.hp -= self.opp["damage"]
            self.damage_ticks.append(t)
        self.hit_tick = None
        self.next_start = t + self._interval(t) + extra

    # -- Ablauf ---------------------------------------------------------------------
    def run(self, inputs: list[tuple[int, str]]) -> EncounterResult:
        cfg, i = self.cfg, 0
        for t in range(cfg["max_ticks"]):
            while i < len(inputs) and inputs[i][0] == t:
                cmd = inputs[i][1]
                i += 1
                if cmd == "flee":
                    return self._result("fled", t)
                if self.allowed is not None and cmd not in self.allowed:  # Fähigkeit nicht ausgerüstet: Befehl wird ignoriert
                    self.ignored += 1
                    continue
                self.command(t, cmd)
            if self.heavy_pending and self.heavy_pending[0] == t:
                self.opp_hp -= self.heavy_pending[1]
                self._count("heavy_hit")
                self.heavy_pending = None
            if self.opp_hp <= 0:
                return self._result("victory", t + 1)
            self.opponent(t)
            if self.hp <= 0:
                return self._result("defeat", t + 1)
            self.stam = min(cfg["player"]["stamina_max"], self.stam + cfg["player"]["stamina_regen_per_tick"])
        return self._result("fled", cfg["max_ticks"])  # Zeitlimit zählt als Rückzug (Vorschlag)

    def _result(self, outcome: str, ticks: int) -> EncounterResult:
        return EncounterResult(outcome, ticks, dict(sorted(self.counts.items())), self.hp,
                               self.opp_hp, self.ignored, tuple(self.damage_ticks))


def simulate(cfg: dict[str, Any], opponent_type: str, player_level: int, inputs: Any, allowed: Any = None) -> EncounterResult:
    """`allowed`: erlaubte Befehle (aus der Kampfausrüstung der Figur) oder None für alle."""
    if allowed is not None and (not isinstance(allowed, (list, tuple, set, frozenset)) or any(c not in COMMANDS for c in allowed)):
        raise SimError("allowed muss eine Liste bekannter Befehle sein")
    return _Fight(cfg, opponent_type, player_level, allowed).run(validate_inputs(cfg, inputs))
