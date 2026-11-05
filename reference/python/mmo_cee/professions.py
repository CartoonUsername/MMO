"""Profession Engine: Erfahrung je Beruf → Meisterschaftsstufe."""
from __future__ import annotations

import bisect
from typing import Any

from .engine import CharacterState, Engine
from .errors import RuleViolation
from .history import Event


SPEC_EVENT = "profession.specialize"  # ab rules_v10 (AP 33, ADR-0068)
_SPEC_KEYS = {"profession", "branch", "day"}


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


class ProfessionEngine(Engine):
    name = "profession"

    def initial(self) -> dict[str, Any]:
        return {"xp": {}}

    def mastery_level(self, xp: int) -> int:
        """Stufe 0..len(thresholds); thresholds[i] = XP für Stufe i+1."""
        return bisect.bisect_right(self.rules["professions"]["mastery_thresholds"], xp)

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        if type == SPEC_EVENT and "specialization" in self.rules["professions"]:
            return self._validate_spec(state, payload)
        if type != "profession.work":
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")
        if payload.get("profession") not in self.rules["professions"]["all"]:
            raise RuleViolation("Unbekannter Beruf")
        amount = payload.get("xp")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise RuleViolation("xp muss eine positive ganze Zahl sein")

    def _validate_spec(self, state: CharacterState, p: dict[str, Any]) -> None:
        from .branches import load_profession_rules
        if set(p) != _SPEC_KEYS:
            raise RuleViolation(f"Ungültige Felder (unzulässig: {sorted(set(p) - _SPEC_KEYS)}, fehlend: {sorted(_SPEC_KEYS - set(p))})")
        prof, branch, day = p["profession"], p["branch"], p["day"]
        if not isinstance(prof, str) or prof not in self.rules["professions"]["all"]:
            raise RuleViolation("Unbekannter Beruf")
        known = load_profession_rules()["professions"].get(prof, {}).get("branches", {})
        if not isinstance(branch, str) or branch not in known:
            raise RuleViolation("Unbekannter Zweig für diesen Beruf")
        if not _is_int(day) or day < 0:
            raise RuleViolation("day muss eine nichtnegative ganze Zahl sein")
        if state.parts["profession"]["xp"].get(prof, 0) <= 0:
            raise RuleViolation("Zweigwahl braucht Erfahrung im Beruf")
        cur = state.parts["profession"].get("spec", {}).get(prof)
        if cur is not None:
            if cur["branch"] == branch:
                raise RuleViolation("Zweig bereits gewählt")
            if day < cur["day"]:
                raise RuleViolation("day darf nicht zurückspringen")
            if day < cur["day"] + self.rules["professions"]["specialization"]["cooldown_days"]:
                raise RuleViolation("Abklingzeit für den Zweigwechsel läuft noch")

    def apply(self, state: CharacterState, event: Event) -> None:
        if event.type == SPEC_EVENT:
            pl = event.payload
            state.parts["profession"].setdefault("spec", {})[pl["profession"]] = {"branch": pl["branch"], "day": pl["day"]}
            return
        xp = state.parts["profession"]["xp"]
        p = event.payload["profession"]
        xp[p] = xp.get(p, 0) + event.payload["xp"]
