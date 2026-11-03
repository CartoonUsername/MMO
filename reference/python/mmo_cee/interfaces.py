"""Schnittstellen der noch NICHT implementierten Engines (Roadmap Prio 4-8).

Bewusst nur Verträge: Sie sind nicht in den Projector eingehängt und
liefern keine Funktion. Implementierungen folgen jeweils mit Tests.
"""
from __future__ import annotations

from typing import Any, Protocol

from .engine import CharacterState


class CombatDevelopment(Protocol):
    """Prefix 'combat.': Teilweise umgesetzt in combat.py (Metriken, Entwicklungsrichtungen).

    Offen bleibt nur diese Schnittstelle: konkrete Fähigkeiten sind noch nicht beschlossen.
    """

    def unlocked_abilities(self, state: CharacterState) -> list[str]: ...


class Discovery(Protocol):
    """Prefix 'discovery.': Entdeckungen (Wissen, Orte, Verfahren)."""

    def discovered(self, state: CharacterState) -> list[str]: ...


class Crafting(Protocol):
    """Prefix 'crafting.': persönliche Herstellungsverfahren und Techniken."""

    def known_techniques(self, state: CharacterState) -> list[str]: ...


class EconomicProfile(Protocol):
    """Prefix 'economy.': Handels-/Unternehmensspezialisierung und Karriere."""

    def specializations(self, state: CharacterState) -> list[str]: ...


class VisualEvolution(Protocol):
    """Reine Ableitung State -> Erscheinungsparameter (deterministisch, kein eigener Zustand)."""

    def appearance(self, state: CharacterState) -> dict[str, Any]: ...
