"""Benachrichtigungen (Push-Ereignisse) an Figuren: Postfach mit Folgenummern, Abruf, Quittung, Stummschaltung. Siehe ADR-0024.

Grundsätze:
* Benachrichtigungen sind **abgeleitet und nicht maßgeblich**: Die Wahrheit liegt in Welt und Historien. Eine Benachrichtigung
  sagt „schau nach“ und trägt nur Kennungen (Angebot, Auftrag, Firma, Figur) – nie Inventar, Salden oder Geheimnisse.
* **Zuverlässig durch Abruf:** Jede Figur hat ein Postfach mit fortlaufender Folgenummer (`seq`). Der Server kann zusätzlich live
  schieben (`listeners`), der Client holt Verpasstes mit `fetch(nach_seq)` und quittiert mit `ack`. Zustellung mindestens einmal,
  der Client entdoppelt über `seq`. Das Postfach ist begrenzt; verdrängte Einträge werden als Lücke (`gap`) gemeldet.
* Der Spieler kann Arten stummschalten (`mute`); stumme Arten werden gar nicht erst abgelegt.
Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .errors import WorldError

KINDS = (
    "market.fill", "market.expired",
    "trade.offer_received", "trade.offer_accepted", "trade.offer_declined", "trade.offer_cancelled", "trade.offer_expired",
    "company.hired", "company.left", "company.employee_left", "company.promoted", "company.demoted", "company.warning",
    "company.closed", "company.shares_offered", "company.proposal_opened", "company.proposal_resolved",
    "production.job_done", "discovery.taught",
    "party.invited", "party.invite_declined", "party.joined", "party.left", "party.kicked", "party.leader_changed",
    "party.disbanded", "party.loot",
)
MAILBOX_LIMIT = 200
FETCH_DEFAULT, FETCH_MAX = 50, 100


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


class Outbox:
    def __init__(self, day_provider: Callable[[], int], mailbox_limit: int = MAILBOX_LIMIT) -> None:
        self.day, self.limit = day_provider, mailbox_limit
        self.boxes: dict[str, dict[str, Any]] = {}
        self.listeners: list[Callable[[str, dict[str, Any]], None]] = []

    # -- Erzeugen (Weltdienste) -----------------------------------------------------------
    def emit(self, recipient: str, kind: str, data: dict[str, Any]) -> None:
        if kind not in KINDS:
            raise ValueError(f"Unbekannte Benachrichtigungsart {kind!r}")
        box = self.boxes.get(recipient)
        if box is not None and kind in box["muted"]:
            return
        if box is None:
            box = self.boxes[recipient] = {"next": 1, "dropped_through": 0, "muted": [], "items": []}
        item = {"seq": box["next"], "day": self.day(), "kind": kind, "data": json.loads(json.dumps(data))}
        box["next"] += 1
        box["items"].append(item)
        while len(box["items"]) > self.limit:
            box["dropped_through"] = box["items"].pop(0)["seq"]
        for fn in self.listeners:
            fn(recipient, item)

    # -- Abrufen (Gateway) ----------------------------------------------------------------------
    def fetch(self, character_id: str, after: int = 0, limit: int = FETCH_DEFAULT) -> dict[str, Any]:
        if not _is_int(after) or after < 0 or not _is_int(limit) or not 1 <= limit <= FETCH_MAX:
            raise WorldError(f"after >= 0 und limit 1..{FETCH_MAX} erforderlich")
        box = self.boxes.get(character_id)
        if box is None:
            return {"items": [], "latest": 0, "gap": False}
        items = [dict(i) for i in box["items"] if i["seq"] > after][:limit]
        return {"items": items, "latest": box["next"] - 1, "gap": after < box["dropped_through"]}

    def ack(self, character_id: str, upto: int) -> int:
        box = self.boxes.get(character_id)
        latest = box["next"] - 1 if box else 0
        if not _is_int(upto) or not 0 <= upto <= latest:
            raise WorldError("upto muss zwischen 0 und der letzten Folgenummer liegen")
        if box is not None:
            box["items"] = [i for i in box["items"] if i["seq"] > upto]
            box["dropped_through"] = max(box["dropped_through"], min(box["dropped_through"], upto))
        return len(box["items"]) if box else 0

    def mute(self, character_id: str, kinds: Any) -> list[str]:
        self._check_kinds(kinds)
        box = self.boxes.setdefault(character_id, {"next": 1, "dropped_through": 0, "muted": [], "items": []})
        box["muted"] = sorted(set(box["muted"]) | set(kinds))
        return list(box["muted"])

    def unmute(self, character_id: str, kinds: Any) -> list[str]:
        self._check_kinds(kinds)
        box = self.boxes.get(character_id)
        if box is not None:
            box["muted"] = sorted(set(box["muted"]) - set(kinds))
        return list(box["muted"]) if box else []

    @staticmethod
    def _check_kinds(kinds: Any) -> None:
        if not isinstance(kinds, list) or not kinds or any(k not in KINDS for k in kinds):
            raise WorldError("kinds muss eine nichtleere Liste bekannter Benachrichtigungsarten sein")

    # -- Persistenz ---------------------------------------------------------------------------------
    @property
    def active(self) -> bool:
        return bool(self.boxes)

    def check(self) -> list[str]:
        errs: list[str] = []
        for cid, b in self.boxes.items():
            seqs = [i["seq"] for i in b["items"]]
            if seqs != sorted(set(seqs)) or (seqs and seqs[-1] != b["next"] - 1) or len(seqs) > self.limit:
                errs.append(f"{cid}: Postfach inkonsistent")
            if any(i["kind"] not in KINDS for i in b["items"]) or any(k not in KINDS for k in b["muted"]):
                errs.append(f"{cid}: unbekannte Art")
            if b["dropped_through"] >= (seqs[0] if seqs else b["next"]):
                errs.append(f"{cid}: Lückenmarke widerspricht den Einträgen")
        return errs

    def to_json(self) -> str:
        return json.dumps(self.boxes, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        self.boxes = json.loads(text)
        problems = self.check()
        if problems:
            self.boxes = {}
            raise WorldError("; ".join(problems))
