"""Identity Engine: Spieler/NPC, Grundklasse, Erfahrung und Stufe."""
from __future__ import annotations

import math
from typing import Any

from .engine import CharacterState, Engine
from .errors import RuleViolation
from .history import Event


class IdentityEngine(Engine):
    name = "identity"

    def initial(self) -> dict[str, Any]:
        return {"kind": None, "base_class": None, "xp": 0, "level": 1}

    def level_for(self, xp: int) -> int:
        unit = self.rules["identity"]["level_xp_unit"]
        cap = self.rules["identity"]["max_level"]
        return min(cap, 1 + math.isqrt(xp // unit))

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        part = state.parts["identity"]
        if type == "identity.created":
            if payload.get("kind") not in ("player", "npc"):
                raise RuleViolation("kind muss 'player' oder 'npc' sein")
        elif type == "identity.class_chosen":
            if part["base_class"] is not None:
                raise RuleViolation("Grundklasse bereits gewählt")
            if payload.get("base_class") not in self.rules["identity"]["classes"]:
                raise RuleViolation("Unbekannte Grundklasse")
        elif type == "identity.xp_gained":
            amount = payload.get("amount")
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                raise RuleViolation("amount muss eine positive ganze Zahl sein")
        else:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")

    def apply(self, state: CharacterState, event: Event) -> None:
        part = state.parts["identity"]
        if event.type == "identity.created":
            part["kind"] = event.payload["kind"]
        elif event.type == "identity.class_chosen":
            part["base_class"] = event.payload["base_class"]
        elif event.type == "identity.xp_gained":
            part["xp"] += event.payload["amount"]
            part["level"] = self.level_for(part["xp"])
