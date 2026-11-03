"""Herstellung auf dem Server: deterministisch, atomar, ohne Zufall. Siehe ADR-0010.

Ablauf: Voraussetzungen prüfen -> Qualität berechnen -> Eingaben verbrauchen -> Bericht an die CEE ->
Ausgaben erzeugen -> Berufserfahrung aus den *gedeckelten* CEE-Punkten. Jeder Schritt, der scheitert,
macht die vorherigen rückgängig; Herstell-IDs vergibt der Server und gelten einmalig.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mmo_cee.crafting import CRAFT_EVENT, craft_blockers, craft_gains, quality_score, quality_tier
from mmo_cee.history import Event
from mmo_cee.service import CharacterService

from .errors import WorldError
from .inventory import Inventory, key


@dataclass(frozen=True)
class CraftResult:
    event: Event
    quality: str
    consumed: dict[str, int]
    produced: dict[str, int]
    profession_xp: int


def required_inputs(rules: Any, recipe_id: str, quantity: int, technique_id: str | None) -> dict[str, int]:
    """Eingabemengen (Material je Gütestufe wird erst bei der Entnahme angehängt), aufgerundet."""
    cfg = rules["crafting"]
    perm = cfg["techniques"][technique_id]["input_permille"] if technique_id else 1000
    return {m: max(1, -(-quantity * n * perm // 1000)) for m, n in cfg["recipes"][recipe_id]["inputs"].items()}


class CraftingService:
    XP_DIVISOR = 10  # Berufserfahrung = gedeckelte Mengenpunkte / 10 (Vorschlag)

    def __init__(self, service: CharacterService, inventory: Inventory, day_provider: Callable[[], int],
                 server_id: str = "srv1") -> None:
        self.cee, self.inv, self.day, self.server_id = service, inventory, day_provider, server_id
        self.rules = service.rules
        self._counter = 0

    def craft(self, character_id: str, recipe_id: str, quantity: int, material_grade: str,
              technique_id: str | None = None, element: str | None = None) -> CraftResult:
        cfg = self.rules["crafting"]
        if not isinstance(material_grade, str) or material_grade not in cfg["material_grades"]:
            raise WorldError("Unbekannte Materialgüte")
        state = self.cee.state(character_id)
        blockers = craft_blockers(state, self.rules, recipe_id, technique_id, element, quantity)
        if blockers:
            raise WorldError(f"Herstellung nicht möglich: {blockers}")
        recipe = cfg["recipes"][recipe_id]
        score = quality_score(state, self.rules, recipe_id, technique_id, cfg["material_grades"][material_grade])
        quality = quality_tier(self.rules, score)
        needed = {key(m, material_grade): n for m, n in required_inputs(self.rules, recipe_id, quantity, technique_id).items()}
        produced = {key(recipe["output"]["item"], quality): recipe["output"]["qty"] * quantity}

        day = self.day()
        self._counter += 1
        craft_id = f"{self.server_id}-craft-{self._counter:08d}"
        payload = {"craft_id": craft_id, "recipe_id": recipe_id, "technique_id": technique_id, "element": element,
                   "quantity": quantity, "quality": quality, "day": day}
        self.cee.projector.validate(state, CRAFT_EVENT, payload)  # Ablehnung vor jeder Bestandsänderung
        xp = craft_gains(state, self.rules, payload)["volume"] // self.XP_DIVISOR

        self.inv.apply(character_id, needed, {})  # wirft bei zu wenig Material; verändert dann nichts
        try:
            event = self.cee.record(character_id, CRAFT_EVENT, payload)
        except Exception:
            self.inv.apply(character_id, {}, needed)  # Rückgabe der Eingaben
            raise
        self.inv.apply(character_id, {}, produced)
        if xp > 0:  # Berufsfortschritt nur aus gedeckelten Punkten -> kein unbegrenztes Hochfarmen
            self.cee.record(character_id, "profession.work", {"profession": recipe["profession"], "xp": xp})
        return CraftResult(event, quality, needed, produced, xp)
