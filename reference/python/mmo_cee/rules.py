"""Lädt versionierte Regeldaten (datengetrieben, nicht im Code)."""
from __future__ import annotations

import hashlib
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

    def __contains__(self, key: str) -> bool:
        return key in self.data

    @property
    def sha256(self) -> str:
        """Fingerabdruck der Regeln (kanonisches JSON); bindet z. B. Migrationsereignisse an die exakten Regeln."""
        return hashlib.sha256(json.dumps(self.data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load_rules(name: str = "rules_v7.json") -> Rules:
    text = resources.files("mmo_cee").joinpath("data", name).read_text(encoding="utf-8")
    return Rules(json.loads(text))


def available_rules() -> dict[str, str]:
    """Alle mitgelieferten Regelversionen: Version -> Dateiname (aus dem Paket, nie aus Ereignisdaten)."""
    out: dict[str, str] = {}
    for f in resources.files("mmo_cee").joinpath("data").iterdir():
        if f.name.startswith("rules_v") and f.name.endswith(".json"):
            out[json.loads(f.read_text(encoding="utf-8"))["version"]] = f.name
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def older_rules(rules: Rules) -> dict[str, Rules]:
    """Alle mitgelieferten Regelversionen unterhalb der gegebenen (für das Abspielen älterer Historien)."""
    return {v: load_rules(f) for v, f in available_rules().items() if int(v) < int(rules.version)}
