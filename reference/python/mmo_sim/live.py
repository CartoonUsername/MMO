"""Live-Begegnung: dieselbe Simulation wie `simulate_pack`, aber Tick für Tick, mit Eingaben während des Kampfes (ADR-0028).

Der Server weist jeder Eingabe den aktuellen Tick zu (der Client kann keinen Tick wählen). Das Eingabeprotokoll
(`inputs_of`) ergibt, durch `simulate_pack` neu abgespielt, exakt dasselbe Ergebnis (durch Tests abgesichert); der Bericht für die
CEE entsteht daher aus dem Protokoll und nicht aus dem Live-Zustand.
"""
from __future__ import annotations

from typing import Any

from .errors import SimError
from .pack import PackResult, _Pack, _validated
from .enemies import extra_commands
from .rules import COMMANDS, GROUP_COMMANDS, MULTI_COMMANDS, skill_commands


class LiveEncounter:
    def __init__(self, cfg: dict[str, Any], opponent_types: Any, players: Any, abilities: Any = None) -> None:
        """`players`: wie bei `simulate_pack`, aber ohne vorab bekannte Eingaben (`inputs` wird auf [] gesetzt); `abilities` je Gegner (ADR-0033)."""
        self.commands = COMMANDS + GROUP_COMMANDS + MULTI_COMMANDS + skill_commands(cfg) + extra_commands(cfg)
        self.abilities = abilities
        specs = [{**p, "inputs": []} for p in players] if isinstance(players, (list, tuple)) and all(isinstance(p, dict) for p in players) else players
        self.opponent_types = list(opponent_types)
        self._sim = _Pack(cfg, opponent_types, _validated(cfg, specs, MULTI_COMMANDS + skill_commands(cfg) + extra_commands(cfg)), abilities)
        self._seen_events = 0
        self.cfg, self.t = cfg, 0
        self.result: PackResult | None = None

    @property
    def done(self) -> bool:
        return self.result is not None

    @property
    def player_count(self) -> int:
        return len(self._sim.ps)

    def submit(self, player: int, cmd: str) -> bool:
        """Nimmt einen Befehl für den nächsten zu verarbeitenden Tick an. False: unbekannt/abgeschlossen/Spieler nicht mehr dabei."""
        if self.done or not isinstance(player, int) or isinstance(player, bool) or not 0 <= player < len(self._sim.ps):
            return False
        p = self._sim.ps[player]
        if cmd not in self.commands or not p.active or len(p.inputs) >= self.cfg["max_inputs"]:
            return False
        p.inputs.append((self.t, cmd))
        return True

    def advance(self) -> PackResult | None:
        """Verarbeitet einen Tick; Ergebnis, sobald der Kampf endet."""
        if self.result is not None:
            return self.result
        res = self._sim.tick(self.t)
        self.t += 1
        if res is None and self.t >= self.cfg["max_ticks"]:
            res = self._sim._pack_result(self.cfg["max_ticks"], "timeout")
        self.result = res
        return res

    def _types(self) -> list[str]:
        return self.opponent_types + [e.type for e in self._sim.es[len(self.opponent_types):]]

    def _ai_view(self, e: Any) -> dict[str, Any]:
        if not self._sim.EA:
            return {}
        c = e.cast
        return {"casting": ({"ability": c["name"], "ticks": max(0, c["end"] - self.t)} if c else None),
                "shield": e.shield_hp if self.t < e.shield_until else 0, "hasted": self.t < e.haste_until}

    def drain_events(self) -> list[dict[str, Any]]:
        """Neue Ankündigungen/Ergebnisse der Gegnerfähigkeiten seit dem letzten Aufruf (für die Anzeige)."""
        new = self._sim.events[self._seen_events:]
        self._seen_events = len(self._sim.events)
        return [dict(e) for e in new]

    def inputs_of(self, player: int) -> list[list[Any]]:
        return [[t, c] for t, c in self._sim.ps[player].inputs]

    def view(self) -> dict[str, Any]:
        """Zustand für die Anzeige (nur, was Spieler sehen dürfen; keine Bedrohung/Zielwahl)."""
        sim, a = self._sim, self.cfg["actions"]
        return {
            "tick": self.t,
            "opponents": [{"type": t, "hp": max(0, e.hp), "alive": e.alive, **self._ai_view(e)} for t, e in zip(self._types(), sim.es)],
            "players": [{"hp": max(0, p.hp), "max_hp": p.max_hp, "stamina": p.stam, "state": p.state,
                         "cooldowns": {k: max(0, v - self.t) for k, v in p.cd.items() if v > self.t},
                         "busy": max(0, p.busy_until - self.t), "focus": p.focus,
                         **({"stunned": max(0, p.stunned_until - self.t), "slowed": max(0, p.slowed_until - self.t), "burning": p.burn is not None} if sim.EA else {})}
                        for p in sim.ps],
            "stagger": [self.t < e.stagger_until or self.t < e.stun_until for e in sim.es],
        } if a else {}


def replay_equals_live(cfg: dict[str, Any], enc: LiveEncounter, players: Any) -> bool:
    """Hilfe für Tests: Das Eingabeprotokoll ergibt beim Neuabspielen dasselbe Ergebnis."""
    from .pack import simulate_pack
    specs = [{**p, "inputs": enc.inputs_of(i)} for i, p in enumerate(players)]
    return simulate_pack(cfg, enc.opponent_types, specs, enc.abilities) == enc.result
