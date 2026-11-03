"""Minimales, atomares Inventar (serverautoritativ). Verhindert negative Bestände und Duplikation.

Schlüssel `item@stufe` (Material: Güteklasse, Erzeugnis: Qualitätsstufe). Alle Mengen positive Ganzzahlen.
Änderungen laufen ausschließlich über `apply` (alles-oder-nichts) bzw. `deposit` (nur für
serverinterne Quellen wie Sammeln/Handel; nicht für Clients). Siehe ADR-0010.
"""
from __future__ import annotations

import json
from typing import Any

from .errors import WorldError


def key(item: str, grade: str) -> str:
    return f"{item}@{grade}"


class Inventory:
    def __init__(self) -> None:
        self._stacks: dict[str, dict[str, int]] = {}

    @staticmethod
    def _check(items: dict[str, int]) -> None:
        for k, n in items.items():
            if not isinstance(k, str) or "@" not in k or isinstance(n, bool) or not isinstance(n, int) or n <= 0:
                raise WorldError(f"Ungültiger Eintrag: {k!r}: {n!r}")

    def balance(self, owner: str, item_key: str) -> int:
        return self._stacks.get(owner, {}).get(item_key, 0)

    def holdings(self, owner: str) -> dict[str, int]:
        return dict(sorted(self._stacks.get(owner, {}).items()))

    def total(self, item_key: str) -> int:
        return sum(s.get(item_key, 0) for s in self._stacks.values())

    def deposit(self, owner: str, item_key: str, qty: int) -> None:
        self.apply(owner, {}, {item_key: qty})

    def apply(self, owner: str, remove: dict[str, int], add: dict[str, int]) -> None:
        """Entfernt und fügt hinzu – vollständig oder gar nicht."""
        self._check(remove)
        self._check(add)
        stacks = self._stacks.setdefault(owner, {})
        for k, n in remove.items():
            if stacks.get(k, 0) < n:
                raise WorldError(f"Nicht genug {k}: {stacks.get(k, 0)} < {n}")
        for k, n in remove.items():
            stacks[k] -= n
            if stacks[k] == 0:
                del stacks[k]
        for k, n in add.items():
            stacks[k] = stacks.get(k, 0) + n

    def to_json(self) -> str:
        return json.dumps(self._stacks, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, text: str) -> "Inventory":
        inv = cls()
        data: dict[str, Any] = json.loads(text)
        for owner, stacks in data.items():
            inv._check(stacks)
            inv._stacks[owner] = dict(stacks)
        return inv
