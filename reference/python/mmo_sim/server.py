"""Begegnungsverwaltung: der Server vergibt IDs, bestimmt Gegner, Stufe und Tag und erzeugt
den Begegnungsbericht aus der Simulation. Der Client liefert ausschließlich Eingabebefehle.

Schließt die in ADR-0003 beschriebene Vertrauensgrenze für den Bericht: Die Berichte der CEE
stammen aus dieser Komponente, nicht von außen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mmo_cee.history import Event
from mmo_cee.service import CharacterService

from .errors import SimError
from .fight import EncounterResult, simulate


@dataclass(frozen=True)
class FinishResult:
    result: EncounterResult
    event: Event | None  # None, wenn die Begegnung keine bewertbaren Aktionen enthielt


def build_report(cfg: dict[str, Any], encounter_id: str, opponent_type: str, day: int,
                 result: EncounterResult) -> dict[str, Any]:
    ticks_per_second = cfg["ticks_per_second"]
    duration = max(cfg["report"]["min_duration_s"], -(-result.ticks // ticks_per_second))
    return {
        "encounter_id": encounter_id,
        "opponent_type": opponent_type,
        "opponent_level": cfg["opponents"][opponent_type]["level"],
        "outcome": result.outcome,
        "duration_s": duration,
        "day": day,
        "actions": dict(result.actions),
    }


class EncounterServer:
    def __init__(self, cfg: dict[str, Any], service: CharacterService,
                 day_provider: Callable[[], int], server_id: str = "srv1") -> None:
        self.cfg, self.service, self.day_provider, self.server_id = cfg, service, day_provider, server_id
        self._counter = 0
        self._pending: dict[str, tuple[str, str, int]] = {}  # id -> (Charakter, Gegner, Tag)
        self._finished: set[str] = set()

    def start(self, character_id: str, opponent_type: str) -> str:
        if opponent_type not in self.cfg["opponents"]:
            raise SimError(f"unbekannter Gegner: {opponent_type}")
        if self.service.state(character_id).parts["identity"]["kind"] is None:
            raise SimError("Charakter existiert nicht")
        self._counter += 1
        eid = f"{self.server_id}-enc-{self._counter:08d}"
        self._pending[eid] = (character_id, opponent_type, self.day_provider())
        return eid

    def finish(self, character_id: str, encounter_id: str, inputs: Any) -> FinishResult:
        if encounter_id in self._finished:
            raise SimError("Begegnung bereits abgeschlossen")
        entry = self._pending.get(encounter_id)
        if entry is None or entry[0] != character_id:
            raise SimError("Begegnung unbekannt oder gehört einem anderen Charakter")
        _, opponent_type, day = entry
        level = self.service.state(character_id).parts["identity"]["level"]
        allowed = self.service.allowed_commands(character_id)  # Fähigkeiten der Figur (ab Regeln v9), sonst alle Befehle
        result = simulate(self.cfg, opponent_type, level, inputs, allowed)  # bei ungültigen Eingaben bleibt die Begegnung offen
        del self._pending[encounter_id]
        self._finished.add(encounter_id)
        if not result.actions:
            return FinishResult(result, None)
        report = build_report(self.cfg, encounter_id, opponent_type, day, result)
        event = self.service.record(character_id, "combat.encounter_resolved", report)
        return FinishResult(result, event)
