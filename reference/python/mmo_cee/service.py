"""CharacterService: validiert, zeichnet auf, projiziert. Gleiche Pipeline für Spieler und NPCs."""
from __future__ import annotations

from typing import Any

from .elements import ElementEngine
from .engine import CharacterState, Projector
from .essence import EssenceEngine, eligible_forms
from .history import Event, EventLog
from .identity import IdentityEngine
from .professions import ProfessionEngine
from .rules import Rules, load_rules


def default_projector(rules: Rules) -> Projector:
    return Projector(
        [IdentityEngine(rules), ElementEngine(rules), ProfessionEngine(rules), EssenceEngine(rules)], rules
    )


class CharacterService:
    def __init__(self, rules: Rules | None = None, log: EventLog | None = None) -> None:
        self.rules = rules or load_rules()
        self.log = log or EventLog()
        self.projector = default_projector(self.rules)
        self._states: dict[str, CharacterState] = {}

    def create(self, character_id: str, kind: str) -> CharacterState:
        return self._record(character_id, "identity.created", {"kind": kind})[1]

    def record(self, character_id: str, type: str, payload: dict[str, Any]) -> Event:
        return self._record(character_id, type, payload)[0]

    def _record(self, character_id: str, type: str, payload: dict[str, Any]) -> tuple[Event, CharacterState]:
        state = self.state(character_id)
        self.projector.validate(state, type, payload)
        event = self.log.append(character_id, type, payload, self.rules.version)
        self.projector.apply(state, event)
        return event, state

    def state(self, character_id: str) -> CharacterState:
        if character_id not in self._states:
            self.log.verify(character_id)
            self._states[character_id] = self.projector.replay(character_id, self.log.events(character_id))
        return self._states[character_id]

    def rebuild(self, character_id: str) -> CharacterState:
        """Verifiziert die Kette und leitet den Zustand frisch aus der Historie ab."""
        self._states.pop(character_id, None)
        return self.state(character_id)

    def eligible_essences(self, character_id: str) -> list[str]:
        return eligible_forms(self.state(character_id), self.rules)
