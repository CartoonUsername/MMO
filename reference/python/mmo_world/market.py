"""Handel zwischen zwei Figuren: atomare Übertragung von Ware und Münzen, Berichte an die CEE.

Ablauf: Eingaben prüfen -> beide CEE-Berichte vorab validieren (keine Bestandsänderung bei Ablehnung) ->
Ware und Münzen in EINER atomaren Inventaroperation übertragen -> beide Berichte aufzeichnen. Münzen entstehen
nur durch serverinterne Quellen (`Inventory.deposit`, z. B. Quests/NPC-Händler später), nie durch Clients.
Siehe ADR-0011. Bekannte Grenze: Die Logs sind append-only; ein Ausfall *zwischen* den beiden Aufzeichnungen
wird durch Rückbuchung des Inventars aufgefangen, ein bereits geschriebener Verkäuferbericht bliebe bestehen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mmo_cee.economy import TRADE, reference_value
from mmo_cee.history import Event
from mmo_cee.service import CharacterService

from .errors import WorldError
from .inventory import Inventory, key


@dataclass(frozen=True)
class TradeResult:
    trade_id: str
    seller_event: Event
    buyer_event: Event
    item_key: str
    quantity: int
    price: int
    reference: int


class TradeService:
    def __init__(self, service: CharacterService, inventory: Inventory, day_provider: Callable[[], int],
                 server_id: str = "srv1") -> None:
        self.cee, self.inv, self.day, self.server_id = service, inventory, day_provider, server_id
        self.rules = service.rules
        cur = self.rules["economy"]["currency"]
        self.coin = key(cur["item"], cur["grade"])
        self._counter = 0

    def parse(self, item_key: str) -> tuple[str, str]:
        cfg = self.rules["economy"]
        if not isinstance(item_key, str) or item_key.count("@") != 1:
            raise WorldError("Ungültiger Gegenstandsschlüssel")
        item, grade = item_key.split("@")
        if item not in cfg["items"] or grade not in cfg["grade_permille"]:
            raise WorldError("Gegenstand ist nicht handelbar")
        return item, grade

    def trade(self, seller_id: str, buyer_id: str, item_key: str, quantity: int, price: int) -> TradeResult:
        if seller_id == buyer_id:
            raise WorldError("Käufer und Verkäufer müssen verschiedene Figuren sein")
        item, grade = self.parse(item_key)
        t = self.rules["economy"]["trade"]
        if not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= t["max_quantity"]:
            raise WorldError("Ungültige Menge")
        if not isinstance(price, int) or isinstance(price, bool) or not 1 <= price <= t["max_value"]:
            raise WorldError("Ungültiger Preis")
        if self.inv.balance(seller_id, item_key) < quantity:
            raise WorldError("Verkäufer besitzt nicht genug")
        if self.inv.balance(buyer_id, self.coin) < price:
            raise WorldError("Käufer besitzt nicht genug Münzen")

        self._counter += 1
        trade_id = f"{self.server_id}-trade-{self._counter:08d}"
        day = self.day()
        base = {"trade_id": trade_id, "item_id": item, "grade": grade, "quantity": quantity, "value": price, "day": day}
        seller_pl = {**base, "role": "seller", "counterparty": buyer_id}
        buyer_pl = {**base, "role": "buyer", "counterparty": seller_id}
        for cid, pl in ((seller_id, seller_pl), (buyer_id, buyer_pl)):  # vor jeder Bestandsänderung
            self.cee.projector.validate(self.cee.state(cid), TRADE, pl)

        self.inv.apply_many([(seller_id, {item_key: quantity}, {self.coin: price}),
                             (buyer_id, {self.coin: price}, {item_key: quantity})])
        try:
            seller_ev = self.cee.record(seller_id, TRADE, seller_pl)
            buyer_ev = self.cee.record(buyer_id, TRADE, buyer_pl)
        except Exception:
            self.inv.apply_many([(seller_id, {self.coin: price}, {item_key: quantity}),
                                 (buyer_id, {item_key: quantity}, {self.coin: price})])
            raise
        return TradeResult(trade_id, seller_ev, buyer_ev, item_key, quantity, price,
                           reference_value(self.rules, item, grade, quantity))
