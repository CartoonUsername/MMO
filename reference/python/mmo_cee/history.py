"""Character History Engine: append-only Ereignislog mit Hash-Kette je Charakter."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .errors import IntegrityError

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64


def _canonical(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True)
class Event:
    character_id: str
    seq: int
    type: str
    payload: dict[str, Any]
    rules_version: str
    prev_hash: str
    hash: str
    schema_version: int = SCHEMA_VERSION

    def body(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "seq": self.seq,
            "type": self.type,
            "payload": self.payload,
            "rules_version": self.rules_version,
            "prev_hash": self.prev_hash,
            "schema_version": self.schema_version,
        }


def compute_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(body)).hexdigest()


class EventLog:
    def __init__(self) -> None:
        self._events: dict[str, list[Event]] = {}

    def append(self, character_id: str, type: str, payload: dict[str, Any], rules_version: str) -> Event:
        chain = self._events.setdefault(character_id, [])
        prev = chain[-1].hash if chain else GENESIS_HASH
        body = {
            "character_id": character_id,
            "seq": len(chain),
            "type": type,
            # JSON-Roundtrip: erzwingt serialisierbare, von außen entkoppelte Payload
            "payload": json.loads(json.dumps(payload)),
            "rules_version": rules_version,
            "prev_hash": prev,
            "schema_version": SCHEMA_VERSION,
        }
        event = Event(hash=compute_hash(body), **body)
        chain.append(event)
        return event

    def events(self, character_id: str) -> list[Event]:
        return list(self._events.get(character_id, []))

    def character_ids(self) -> list[str]:
        return sorted(self._events)

    def adopt(self, character_id: str, events: list[Event]) -> None:
        """Übernimmt eine geladene Kette (z. B. aus dem Speicher) und prüft sie sofort; bei Fehler bleibt der Log unverändert."""
        if character_id in self._events:
            raise IntegrityError(f"Historie von {character_id} ist bereits geladen")
        self._events[character_id] = list(events)
        try:
            self.verify(character_id)
        except IntegrityError:
            del self._events[character_id]
            raise

    def has(self, character_id: str) -> bool:
        return character_id in self._events

    def verify(self, character_id: str) -> None:
        prev = GENESIS_HASH
        for i, e in enumerate(self._events.get(character_id, [])):
            if e.seq != i or e.prev_hash != prev or compute_hash(e.body()) != e.hash:
                raise IntegrityError(f"Historie von {character_id} ungültig bei seq={i}")
            prev = e.hash

    def to_json(self, character_id: str) -> str:
        return json.dumps([{**e.body(), "hash": e.hash} for e in self.events(character_id)], sort_keys=True)

    @classmethod
    def from_json(cls, character_id: str, data: str) -> "EventLog":
        log = cls()
        log._events[character_id] = [Event(**row) for row in json.loads(data)]
        log.verify(character_id)
        return log
