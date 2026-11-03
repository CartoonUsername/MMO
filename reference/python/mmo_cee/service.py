"""CharacterService: validiert, zeichnet auf, projiziert. Gleiche Pipeline für Spieler und NPCs."""
from __future__ import annotations

from typing import Any

from .combat import CombatEngine, reached_directions
from .discovery import DiscoveryEngine, discovery_progress, known_discoveries
from .elements import ElementEngine
from .engine import CharacterState, Projector
from .essence import EssenceEngine, eligible_forms, essence_profile, form_scores
from .history import Event, EventLog
from .identity import IdentityEngine
from .professions import ProfessionEngine
from .rules import Rules, load_rules
from .visual import VisualEvolution


def default_projector(rules: Rules) -> Projector:
    engines = [IdentityEngine(rules), ElementEngine(rules), ProfessionEngine(rules), EssenceEngine(rules)]
    if "combat" in rules:  # rules_v1 kennt keine Kampfentwicklung
        engines.append(CombatEngine(rules))
    if "discovery" in rules:  # ab rules_v5
        engines.append(DiscoveryEngine(rules))
    return Projector(engines, rules)


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

    def combat_directions(self, character_id: str) -> dict[str, int]:
        """Erreichte Entwicklungsrichtungen -> Stufe (mehrere gleichzeitig möglich)."""
        return reached_directions(self.state(character_id), self.rules)

    def essence_scores(self, character_id: str) -> dict[str, dict]:
        """Punktzahl/Beiträge/Prüfbarkeit der Bewertungsformen (leer bei Regeln ohne Bewertungsformen)."""
        return form_scores(self.state(character_id), self.rules)

    def essence_profile(self, character_id: str) -> dict:
        """Vor-/Nachteile der angenommenen Wesensform."""
        return essence_profile(self.state(character_id), self.rules)

    def appearance(self, character_id: str) -> dict:
        """Erscheinungsparameter (Visual Evolution): reine, serverseitige Ableitung aus dem Zustand."""
        if not hasattr(self, "_visual"):
            self._visual = VisualEvolution(self.rules)
        return self._visual.appearance(self.state(character_id))

    def known_discoveries(self, character_id: str) -> list[str]:
        return known_discoveries(self.state(character_id))

    def discovery_progress(self, character_id: str, discovery_id: str) -> dict:
        """Beweise, fehlende Voraussetzungen und Abschlussbereitschaft einer Entdeckung."""
        return discovery_progress(self.state(character_id), self.rules, discovery_id)
