"""Profession Engine: Erfahrung je Beruf → Meisterschaftsstufe."""
from __future__ import annotations

import bisect
from typing import Any

from .engine import CharacterState, Engine
from .errors import RuleViolation
from .history import Event


class ProfessionEngine(Engine):
    name = "profession"

    def initial(self) -> dict[str, Any]:
        return {"xp": {}}

    def mastery_level(self, xp: int) -> int:
        """Stufe 0..len(thresholds); thresholds[i] = XP für Stufe i+1."""
        return bisect.bisect_right(self.rules["professions"]["mastery_thresholds"], xp)

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        if type != "profession.work":
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")
        if payload.get("profession") not in self.rules["professions"]["all"]:
            raise RuleViolation("Unbekannter Beruf")
        amount = payload.get("xp")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise RuleViolation("xp muss eine positive ganze Zahl sein")

    def apply(self, state: CharacterState, event: Event) -> None:
        xp = state.parts["profession"]["xp"]
        p = event.payload["profession"]
        xp[p] = xp.get(p, 0) + event.payload["xp"]
