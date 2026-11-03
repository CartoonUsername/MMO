"""Verbindet CEE (Wissen je Figur) und Registry (Weltzustand) transaktional."""
from __future__ import annotations

from typing import Callable

from mmo_cee.errors import RuleViolation
from mmo_cee.history import Event
from mmo_cee.service import CharacterService

from .discovery import DiscoveryRegistry
from .errors import WorldError


class DiscoveryService:
    def __init__(self, service: CharacterService, registry: DiscoveryRegistry, day_provider: Callable[[], int]) -> None:
        self.cee, self.registry, self.day = service, registry, day_provider

    def gather(self, character_id: str, discovery_id: str, evidence_id: str) -> Event:
        """Beweis sammeln (vom Server ausgelöst, jede Beweis-ID je Figur nur einmal)."""
        return self.cee.record(character_id, "discovery.evidence_gathered",
                               {"discovery_id": discovery_id, "evidence_id": evidence_id})

    def complete(self, character_id: str, discovery_id: str) -> Event:
        """Schließt die eigenständige Entdeckung ab; Anerkennung (Pionier/Entdecker) bestimmt die Registry."""
        if discovery_id not in self.registry.records:
            raise WorldError("Unbekannte Entdeckung")
        prog = self.cee.discovery_progress(character_id, discovery_id)
        if not prog["ready"]:
            raise WorldError(f"Entdeckung nicht abschlussreif: {prog}")
        day = self.day()
        credit = self.registry.claim(character_id, discovery_id, day)
        try:
            event = self.cee.record(character_id, "discovery.made",
                                    {"discovery_id": discovery_id, "day": day, "credit": credit})
        except Exception:
            self.registry.release(character_id, discovery_id)  # Registry und Log dürfen nie auseinanderlaufen
            raise
        self.registry.commit()
        return event

    def teach(self, teacher_id: str, learner_id: str, discovery_id: str) -> Event:
        """Lehren: nur teilbare Entdeckungen, Pioniervorsprung beachten, Voraussetzungen des Schülers prüfen."""
        if teacher_id == learner_id:
            raise WorldError("Lehrer und Schüler müssen verschiedene Figuren sein")
        day = self.day()
        ok, reason = self.registry.can_teach(teacher_id, discovery_id, day)
        if not ok:
            raise WorldError(f"Lehren nicht möglich: {reason}")
        if discovery_id not in self.cee.known_discoveries(teacher_id):
            raise WorldError("Inkonsistenz: Registry kennt Lehrer als Halter, die Figur aber nicht")
        try:
            event = self.cee.record(learner_id, "discovery.learned",
                                    {"discovery_id": discovery_id, "day": day, "from_character": teacher_id})
        except RuleViolation as e:
            raise WorldError(f"Schüler erfüllt die Voraussetzungen nicht: {e}") from e
        self.registry.note_learned(learner_id, discovery_id, teacher_id, day)
        return event
