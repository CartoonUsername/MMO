"""Essence Engine: Wesensentwicklung. Start als Mensch; Annahme per Prüfung + Entscheidung, dauerhaft."""
from __future__ import annotations

from typing import Any

from .engine import CharacterState, Engine
from .errors import RuleViolation
from .history import Event
from .professions import ProfessionEngine
from .rules import Rules


def eligible_forms(state: CharacterState, rules: Rules) -> list[str]:
    """Wesensformen, deren Voraussetzungen die Spielhistorie derzeit erfüllt."""
    if state.parts["essence"]["form"] != "human":
        return []
    prof = ProfessionEngine(rules)
    level = state.parts["identity"]["level"]
    attuned = set(state.parts["element"]["attuned"])
    result = []
    for form, req in rules["essence"]["forms"].items():
        if level < req.get("min_level", 1):
            continue
        if not set(req.get("attuned_all", [])) <= attuned:
            continue
        mastery = {p: prof.mastery_level(x) for p, x in state.parts["profession"]["xp"].items()}
        if any(mastery.get(p, 0) < m for p, m in req.get("professions", {}).items()):
            continue
        result.append(form)
    return sorted(result)


class EssenceEngine(Engine):
    name = "essence"

    def initial(self) -> dict[str, Any]:
        return {"form": "human", "trials_passed": [], "adopted_at_seq": None}

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        part = state.parts["essence"]
        form = payload.get("form")
        if form not in self.rules["essence"]["forms"]:
            raise RuleViolation("Unbekannte Wesensform")
        if part["form"] != "human":
            raise RuleViolation("Wesensform ist dauerhaft und bereits angenommen")
        if type == "essence.trial_passed":
            if form not in eligible_forms(state, self.rules):
                raise RuleViolation("Voraussetzungen für diese Wesensprüfung nicht erfüllt")
            if form in part["trials_passed"]:
                raise RuleViolation("Prüfung bereits bestanden")
        elif type == "essence.adopted":
            if form not in part["trials_passed"]:
                raise RuleViolation("Wesensprüfung nicht bestanden")
        else:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")

    def apply(self, state: CharacterState, event: Event) -> None:
        part = state.parts["essence"]
        if event.type == "essence.trial_passed":
            part["trials_passed"].append(event.payload["form"])
        elif event.type == "essence.adopted":
            part["form"] = event.payload["form"]
            part["adopted_at_seq"] = event.seq
