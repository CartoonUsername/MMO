"""Element Engine: neun Elemente, freie Kombination, 2 reguläre + 1 Endgame-Element."""
from __future__ import annotations

from typing import Any

from .engine import CharacterState, Engine
from .errors import RuleViolation
from .history import Event


def combination_key(attuned: list[str]) -> tuple[str, ...]:
    """Kombinationen sind frei und reihenfolgeunabhängig."""
    return tuple(sorted(attuned))


class ElementEngine(Engine):
    name = "element"

    def initial(self) -> dict[str, Any]:
        return {"affinity": {e: 0 for e in self.rules["elements"]["all"]}, "attuned": []}

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        cfg = self.rules["elements"]
        part = state.parts["element"]
        element = payload.get("element")
        if element not in cfg["all"]:
            raise RuleViolation("Unbekanntes Element")
        if type == "element.exposure":
            amount = payload.get("amount")
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                raise RuleViolation("amount muss eine positive ganze Zahl sein")
        elif type == "element.attuned":
            if element in part["attuned"]:
                raise RuleViolation("Element bereits geprägt")
            if part["affinity"][element] < cfg["attunement_threshold"]:
                raise RuleViolation("Affinität zu gering für Prägung")
            count = len(part["attuned"])
            if count >= cfg["max_total"]:
                raise RuleViolation("Maximale Elementzahl erreicht")
            if count >= cfg["max_regular"] and state.parts["identity"]["level"] < cfg["third_element_min_level"]:
                raise RuleViolation("Drittes Element ist Endgame-Entwicklung (Mindeststufe nicht erreicht)")
        else:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")

    def apply(self, state: CharacterState, event: Event) -> None:
        part = state.parts["element"]
        e = event.payload["element"]
        if event.type == "element.exposure":
            part["affinity"][e] += event.payload["amount"]
        elif event.type == "element.attuned":
            part["attuned"].append(e)
