"""Engine-Basis, Charakterzustand und Projector (Replay)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .errors import RuleViolation
from .history import Event
from .rules import Rules


@dataclass
class CharacterState:
    character_id: str
    rules_version: str
    parts: dict[str, dict[str, Any]] = field(default_factory=dict)


class Engine(ABC):
    """Eine Engine besitzt genau einen Teilzustand und ein Ereignis-Präfix."""

    name: str

    def __init__(self, rules: Rules) -> None:
        self.rules = rules

    @abstractmethod
    def initial(self) -> dict[str, Any]: ...

    @abstractmethod
    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        """Wirft RuleViolation, ohne den Zustand zu verändern."""

    @abstractmethod
    def apply(self, state: CharacterState, event: Event) -> None:
        """Deterministische Zustandsableitung; vertraut dem Log."""


class Projector:
    def __init__(self, engines: list[Engine], rules: Rules) -> None:
        self.rules = rules
        self.engines = {e.name: e for e in engines}

    def new_state(self, character_id: str) -> CharacterState:
        return CharacterState(
            character_id, self.rules.version, {n: e.initial() for n, e in self.engines.items()}
        )

    def _engine_for(self, type: str) -> Engine:
        prefix = type.split(".", 1)[0]
        if prefix not in self.engines:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")
        return self.engines[prefix]

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        engine = self._engine_for(type)
        created = state.parts["identity"]["kind"] is not None
        if type == "identity.created" and created:
            raise RuleViolation("Charakter existiert bereits")
        if type != "identity.created" and not created:
            raise RuleViolation("Charakter wurde noch nicht erstellt")
        engine.validate(state, type, payload)

    def apply(self, state: CharacterState, event: Event) -> None:
        self._engine_for(event.type).apply(state, event)

    def replay(self, character_id: str, events: list[Event]) -> CharacterState:
        state = self.new_state(character_id)
        for e in events:
            self.apply(state, e)
        return state
