"""Lädt versionierte Regeldaten (datengetrieben, nicht im Code)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class Rules:
    data: dict[str, Any]

    @property
    def version(self) -> str:
        return self.data["version"]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


def load_rules(name: str = "rules_v1.json") -> Rules:
    text = resources.files("mmo_cee").joinpath("data", name).read_text(encoding="utf-8")
    return Rules(json.loads(text))
