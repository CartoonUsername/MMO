"""Gruppenkampf: mehrere Spieler gegen einen Gegner, mit Unterstützung (Heilen, Schild). Siehe ADR-0022.

Deterministisch, ganzzahlig, ohne Zufall; jeder Spieler liefert nur seine eigenen Eingabebefehle. Mit genau einem Spieler und
ohne Gruppenbefehle ist das Ergebnis bit-identisch zur Einzelsimulation (`fight.simulate`; durch Tests über viele Eingaben
abgesichert). Neu gegenüber dem 1:1-Kampf:

* **Gegnerleben** wächst mit der Gruppengröße (`opponent_hp_per_extra_member_permille`).
* **Ziel des Gegners:** Beim Beginn eines Angriffs wählt der Gegner unter den kämpfenden Spielern den mit der höchsten
  Bedrohung (verursachter Schaden + gewirkte Heilung), bei Gleichstand den mit dem kleinsten Index; ist das Ziel bis zur Auflösung
  ausgefallen oder geflohen, wird neu gewählt. Ausweichen/Blocken/Parieren zählen beim getroffenen Spieler.
* **Heilen (`heal`):** heilt den verbündeten Kämpfer mit dem kleinsten Anteil an Lebenspunkten (Gleichstand: kleinster Index),
  höchstens bis zum Maximum. Hat niemand etwas zu heilen, wird der Befehl ignoriert (kein Farmen von Unterstützungspunkten).
* **Schild (`shield`):** legt auf den verbündeten Kämpfer mit der höchsten Bedrohung (ohne aktives Schild) ein Schild, das
  Schaden absorbiert; sonst ignoriert.
* **Ausgang je Spieler:** `victory` (kämpfte bis zum Sieg), `defeat` (Lebenspunkte erschöpft), `fled` (geflohen oder Zeitlimit).
  Jeder Spieler erhält seinen eigenen Bericht mit nur seinen Aktionszählern.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SimError
from .fight import EncounterResult, validate_inputs
from .rules import COMMANDS, GROUP_COMMANDS, combine_effects


@dataclass(frozen=True)
class GroupResult:
    outcome: str  # Ausgang der Gruppe: victory | defeat | fled
    ticks: int
    opponent_hp: int
    players: tuple[EncounterResult, ...]  # je Spieler, in der Reihenfolge der Eingabe


class _P:
    """Zustand eines Spielers im Gruppenkampf (Spiegel von `fight._Fight` für die Spielerseite)."""

    def __init__(self, cfg: dict[str, Any], level: int, spec: dict[str, Any], inputs: list[tuple[int, str]]) -> None:
        p = cfg["player"]
        self.max_hp = p["base_hp"] + p["hp_per_level"] * level
        self.hp, self.stam = self.max_hp, p["stamina_max"]
        self.fx = combine_effects(cfg, spec.get("equipped"))
        allowed = spec.get("allowed")
        self.allowed = None if allowed is None else frozenset(allowed)
        self.inputs, self.i = inputs, 0
        self.counts: dict[str, int] = {}
        self.ignored = 0
        self.damage_ticks: list[int] = []
        self.busy_until = 0
        self.cd = {"heavy": 0, "dodge": 0, "block": 0, "stun": 0, "slow": 0, "heal": 0, "shield": 0}
        self.dodge_start = self.dodge_until = self.block_start = self.block_until = -1
        self.heavy_pending: tuple[int, int] | None = None
        self.shield_hp = 0
        self.shield_until = 0
        self.threat = 0
        self.state = "active"  # active | fled | down | done
        self.end_tick = 0

    def count(self, name: str, n: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + n

    def scaled(self, base: int, key: str) -> int:
        return base * self.fx.get(key, 1000) // 1000

    def fx_get(self, key: str) -> int:
        return self.fx.get(key, 0)

    @property
    def active(self) -> bool:
        return self.state == "active"


def _validated(cfg: dict[str, Any], players: Any, extra_commands: tuple[str, ...] = ()) -> list[tuple[dict[str, Any], int, list[tuple[int, str]]]]:
    g = cfg.get("group")
    if g is None:
        raise SimError("Diese Regeln kennen keinen Gruppenkampf")
    if not isinstance(players, (list, tuple)) or not 1 <= len(players) <= g["max_party"]:
        raise SimError(f"Die Gruppe muss aus 1..{g['max_party']} Spielern bestehen")
    out = []
    for spec in players:
        if not isinstance(spec, dict) or set(spec) - {"level", "inputs", "allowed", "equipped"} or not {"level", "inputs"} <= set(spec):
            raise SimError("Spieler: level und inputs erforderlich, optional allowed/equipped")
        level = spec["level"]
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            raise SimError("level muss eine positive ganze Zahl sein")
        allowed = spec.get("allowed")
        if allowed is not None and (not isinstance(allowed, (list, tuple, set, frozenset))
                                    or any(c not in COMMANDS + GROUP_COMMANDS + extra_commands for c in allowed)):
            raise SimError("allowed muss eine Liste bekannter Befehle sein")
        combine_effects(cfg, spec.get("equipped"))  # prüft equipped
        out.append((spec, level, validate_inputs(cfg, spec["inputs"], COMMANDS + GROUP_COMMANDS + extra_commands)))
    return out


class _Group:
    def __init__(self, cfg: dict[str, Any], opponent_type: str, specs: list[tuple[dict[str, Any], int, list[tuple[int, str]]]]) -> None:
        if opponent_type not in cfg["opponents"]:
            raise SimError(f"unbekannter Gegner: {opponent_type}")
        self.cfg, self.A, self.G = cfg, cfg["actions"], cfg["group"]
        self.opp = cfg["opponents"][opponent_type]
        self.ps = [_P(cfg, lvl, spec, inputs) for spec, lvl, inputs in specs]
        extra = len(self.ps) - 1
        self.opp_hp = self.opp["hp"] * (1000 + self.G["opponent_hp_per_extra_member_permille"] * extra) // 1000
        self.stun_until = self.slow_until = self.stagger_until = 0
        interval = self.opp["attack_interval"]
        self.next_start: int | None = interval if interval > 0 else None
        self.hit_tick: int | None = None
        self.hit_target: int | None = None

    # -- Hilfen ------------------------------------------------------------------
    def _interval(self, at: int) -> int:
        base = self.opp["attack_interval"]
        return base * self.A["slow"]["interval_permille"] // 1000 if at < self.slow_until else base

    def _vulnerable(self, t: int) -> bool:
        return t < self.stagger_until or t < self.stun_until

    def _target(self) -> int | None:
        cands = [(-p.threat, i) for i, p in enumerate(self.ps) if p.active]
        return min(cands)[1] if cands else None

    def _damage_to(self, p: _P, amount: int, t: int) -> None:
        dmg, absorbed = amount, 0
        if p.shield_hp > 0 and t < p.shield_until:
            absorbed = min(p.shield_hp, dmg)
            p.shield_hp -= absorbed
            dmg -= absorbed
        p.hp -= dmg
        if not (absorbed > 0 and dmg == 0):  # ein vollständig vom Schild geschluckter Schlag zählt nicht als Schadenstick
            p.damage_ticks.append(t)

    # -- Spielerbefehle ------------------------------------------------------------
    def command(self, idx: int, t: int, cmd: str) -> None:
        p = self.ps[idx]
        if cmd in GROUP_COMMANDS:
            return self._support(idx, t, cmd)
        a = self.A[cmd]
        cost = max(0, a["cost"] + (p.fx_get("dodge_cost_delta") if cmd == "dodge" else 0))
        cooldown = max(0, a["cooldown"] + (p.fx_get("dodge_cooldown_delta") if cmd == "dodge" else 0))
        if t < p.busy_until or p.stam < cost or (cmd in p.cd and t < p.cd[cmd]):
            p.ignored += 1
            return
        if cmd == "light":
            if self._vulnerable(t):
                a = self.A["precise"]
                p.count("precise_hit")
            else:
                p.count("light_hit")
            dealt = p.scaled(a["damage"], "light_damage_permille")
            self.opp_hp -= dealt
            p.threat += dealt
        elif cmd == "heavy":
            p.heavy_pending = (t + a["windup"], p.scaled(a["damage"], "heavy_damage_permille"))
        elif cmd == "dodge":
            p.dodge_start, p.dodge_until = t, t + a["active"]
        elif cmd == "block":
            p.block_start, p.block_until = t, t + a["active"]
        elif cmd == "stun":
            self.stun_until = t + a["ticks"] + p.fx_get("stun_ticks_bonus")
            self.hit_tick = None
            if self.next_start is not None:
                self.next_start = self.stun_until + self._interval(t)
            p.count("stun_applied")
        elif cmd == "slow":
            self.slow_until = t + a["ticks"] + p.fx_get("slow_ticks_bonus")
            p.count("slow_applied")
        p.stam -= cost
        p.busy_until = t + a["busy"]
        if cmd in p.cd:
            p.cd[cmd] = t + cooldown

    def _support(self, idx: int, t: int, cmd: str) -> None:
        p, g = self.ps[idx], self.G[cmd]
        others = [(i, q) for i, q in enumerate(self.ps) if i != idx and q.active]
        if cmd == "heal":
            targets = [(q.hp * 1000 // q.max_hp, i) for i, q in others if q.hp < q.max_hp]
        else:
            targets = [(-q.threat, i) for i, q in others if not (q.shield_hp > 0 and t < q.shield_until)]
        if t < p.busy_until or p.stam < g["cost"] or t < p.cd[cmd] or not targets:
            p.ignored += 1
            return
        tgt = self.ps[min(targets)[1]]
        if cmd == "heal":
            healed = min(g["amount"], tgt.max_hp - tgt.hp)
            tgt.hp += healed
            p.threat += healed * self.G["threat"]["heal_permille"] // 1000
            p.count("ally_heal")
        else:
            tgt.shield_hp, tgt.shield_until = g["absorb"], t + g["ticks"]
            p.count("ally_shield")
        p.stam -= g["cost"]
        p.busy_until = t + g["busy"]
        p.cd[cmd] = t + g["cooldown"]

    # -- Gegner --------------------------------------------------------------------
    def opponent(self, t: int) -> None:
        if self.next_start is None:
            return
        if self.hit_tick is None and t >= self.next_start:
            if t < self.stun_until:
                self.next_start = self.stun_until
            else:
                self.hit_tick = t + self.opp["windup"]
                self.hit_target = self._target()
        if self.hit_tick == t:
            self._resolve_hit(t)

    def _resolve_hit(self, t: int) -> None:
        a, extra = self.A, 0
        tgt = self.hit_target
        if tgt is None or not self.ps[tgt].active:
            tgt = self._target()
        if tgt is not None:
            p = self.ps[tgt]
            if p.dodge_start <= t < p.dodge_until:
                p.count("perfect_dodge" if t - p.dodge_start < a["dodge"]["perfect_window"] else "dodge")
            elif p.block_start <= t < p.block_until:
                if t - p.block_start < a["block"]["parry_window"]:
                    p.count("parry")
                    extra = self.opp["stagger"] + p.fx_get("parry_stagger_bonus")
                    self.stagger_until = t + extra
                else:
                    p.count("block")
                    self._damage_to(p, p.scaled(self.opp["damage"] * min(a["block"]["damage_permille"], p.fx.get("block_damage_permille", 1000)) // 1000,
                                                "damage_taken_permille"), t)
            else:
                self._damage_to(p, p.scaled(self.opp["damage"], "damage_taken_permille"), t)
        self.hit_tick = None
        self.hit_target = None
        self.next_start = t + self._interval(t) + extra

    # -- Ablauf --------------------------------------------------------------------
    def run(self) -> GroupResult:
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
                return self._result(t, "none")
            for p in self.ps:
                if p.active and p.heavy_pending and p.heavy_pending[0] == t:
                    self.opp_hp -= p.heavy_pending[1]
                    p.threat += p.heavy_pending[1]
                    p.count("heavy_hit")
                    p.heavy_pending = None
            if self.opp_hp <= 0:
                return self._result(t + 1, "victory")
            self.opponent(t)
            for p in self.ps:
                if p.active and p.hp <= 0:
                    p.state, p.end_tick, p.heavy_pending = "down", t + 1, None
            if not any(p.active for p in self.ps):
                return self._result(t + 1, "none")
            for p in self.ps:
                if p.active:
                    p.stam = min(cfg["player"]["stamina_max"], p.stam + cfg["player"]["stamina_regen_per_tick"] + p.fx_get("stamina_regen_bonus"))
        return self._result(cfg["max_ticks"], "timeout")

    def _result(self, ticks: int, how: str) -> GroupResult:
        res = []
        for p in self.ps:
            if p.state == "fled":
                outcome, end = "fled", p.end_tick
            elif p.state == "down":
                outcome, end = "defeat", p.end_tick
            elif how == "victory":
                outcome, end = "victory", ticks
            else:  # Zeitlimit zählt als Rückzug
                outcome, end = "fled", ticks
            res.append(EncounterResult(outcome, end, dict(sorted(p.counts.items())), p.hp, self.opp_hp, p.ignored, tuple(p.damage_ticks)))
        if how == "victory":
            team = "victory"
        elif how == "none":  # alle ausgefallen oder geflohen
            team = "defeat" if any(p.state == "down" for p in self.ps) else "fled"
        else:
            team = "fled"
        return GroupResult(team, ticks, self.opp_hp, tuple(res))


def simulate_group(cfg: dict[str, Any], opponent_type: str, players: Any) -> GroupResult:
    """`players`: Liste von `{level, inputs, [allowed], [equipped]}` (1..max_party). Fehler -> SimError, nichts wird simuliert."""
    return _Group(cfg, opponent_type, _validated(cfg, players)).run()
