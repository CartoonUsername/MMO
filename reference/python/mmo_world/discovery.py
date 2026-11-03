"""Weltseite der Entdeckungen: Pionierstatus, Lehrfenster, Halter. Siehe ADR-0009.

Die Registry ist serverseitiger Weltzustand (nicht Teil des Logs einer einzelnen Figur). Sie ist
deterministisch (Reihenfolge der Aufrufe + Serverzeit `day`) und serialisierbar.

Fairness-Regeln (bestätigte Leitlinie, Zahlen vorläufig):
* Der erste Entdecker erhält Anerkennung (`credit = "pioneer"`) und innerhalb eines *endlichen* Fensters
  das alleinige Lehrrecht (zeitlich begrenzter Vorsprung).
* Unabhängige Forschung ist jederzeit möglich; niemand kann eine Entdeckung dauerhaft blockieren.
* Nach Ablauf des Fensters darf jeder Halter lehren (sofern die Entdeckung teilbar ist).
"""
from __future__ import annotations

import json
from typing import Any

from mmo_cee.discovery import validate_discovery_rules
from mmo_cee.rules import Rules

from .errors import WorldError


class DiscoveryRegistry:
    def __init__(self, rules: Rules) -> None:
        validate_discovery_rules(rules)
        self.cfg = rules["discovery"]
        self.disc = self.cfg["discoveries"]
        self.last_day = 0
        # discovery_id -> {"pioneer": str|None, "pioneer_day": int|None, "holders": {character_id: {...}}}
        self.records: dict[str, dict[str, Any]] = {d: {"pioneer": None, "pioneer_day": None, "holders": {}} for d in self.disc}
        self._claims: list[tuple[str, str, int]] = []  # (Charakter, Entdeckung, Vorgänger-last_day) für Rollback

    # -- Hilfen --------------------------------------------------------------------
    def _rec(self, discovery_id: str) -> dict[str, Any]:
        if not isinstance(discovery_id, str) or discovery_id not in self.records:
            raise WorldError("Unbekannte Entdeckung")
        return self.records[discovery_id]

    def _check_day(self, day: Any) -> None:
        if not isinstance(day, int) or isinstance(day, bool) or day < 0:
            raise WorldError("day muss eine nichtnegative ganze Zahl sein")
        if day < self.last_day:
            raise WorldError("Serverzeit darf nicht zurückspringen")

    def window_days(self, discovery_id: str) -> int:
        return self.disc[discovery_id].get("pioneer_window_days", self.cfg["default_pioneer_window_days"])

    # -- Abfragen -------------------------------------------------------------------
    def pioneer(self, discovery_id: str) -> str | None:
        return self._rec(discovery_id)["pioneer"]

    def holders(self, discovery_id: str) -> list[str]:
        return sorted(self._rec(discovery_id)["holders"])

    def knows(self, character_id: str, discovery_id: str) -> bool:
        return character_id in self._rec(discovery_id)["holders"]

    def window_end(self, discovery_id: str) -> int | None:
        """Erster Tag, an dem jeder Halter lehren darf (None, solange niemand die Entdeckung hat)."""
        rec = self._rec(discovery_id)
        return None if rec["pioneer_day"] is None else rec["pioneer_day"] + self.window_days(discovery_id)

    def can_teach(self, teacher_id: str, discovery_id: str, day: int) -> tuple[bool, str]:
        rec = self._rec(discovery_id)
        if not self.disc[discovery_id]["shareable"]:
            return False, "nicht teilbar"
        if teacher_id not in rec["holders"]:
            return False, "Lehrer kennt die Entdeckung nicht"
        if teacher_id != rec["pioneer"] and day < self.window_end(discovery_id):
            return False, f"Pioniervorsprung bis Tag {self.window_end(discovery_id)}"
        return True, "ok"

    # -- Änderungen ------------------------------------------------------------------
    def claim(self, character_id: str, discovery_id: str, day: int) -> str:
        """Registriert eine eigenständige Entdeckung; Rückgabe: 'pioneer' (Erster) oder 'discoverer'."""
        rec = self._rec(discovery_id)
        self._check_day(day)
        if character_id in rec["holders"]:
            raise WorldError("Figur kennt die Entdeckung bereits")
        credit = "pioneer" if rec["pioneer"] is None else "discoverer"
        if credit == "pioneer":
            rec["pioneer"], rec["pioneer_day"] = character_id, day
        rec["holders"][character_id] = {"how": "researched", "credit": credit, "day": day}
        self._claims.append((character_id, discovery_id, self.last_day))
        self.last_day = day
        return credit

    def release(self, character_id: str, discovery_id: str) -> None:
        """Nimmt die jüngste Registrierung zurück (nur für Transaktions-Rollback)."""
        if not self._claims or self._claims[-1][:2] != (character_id, discovery_id):
            raise WorldError("Nur die jüngste Registrierung kann zurückgenommen werden")
        _, _, prev_day = self._claims.pop()
        rec = self._rec(discovery_id)
        was = rec["holders"].pop(character_id)
        if was["credit"] == "pioneer":
            rec["pioneer"] = rec["pioneer_day"] = None
        self.last_day = prev_day

    def note_learned(self, learner_id: str, discovery_id: str, teacher_id: str, day: int) -> None:
        rec = self._rec(discovery_id)
        self._check_day(day)
        if learner_id in rec["holders"]:
            raise WorldError("Figur kennt die Entdeckung bereits")
        rec["holders"][learner_id] = {"how": "learned", "credit": "learner", "day": day, "from": teacher_id}
        self._claims.clear()  # Rollback nur für unmittelbar vorherige Registrierung
        self.last_day = day

    def commit(self) -> None:
        """Beendet die Transaktion (macht `release` für frühere Registrierungen unmöglich)."""
        self._claims.clear()

    # -- Persistenz (deterministisch) ---------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({"last_day": self.last_day, "records": self.records}, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, rules: Rules, text: str) -> "DiscoveryRegistry":
        data = json.loads(text)
        reg = cls(rules)
        if set(data["records"]) != set(reg.records):
            raise WorldError("Gespeicherte Registry passt nicht zu den Regeln")
        reg.records, reg.last_day = data["records"], data["last_day"]
        return reg
