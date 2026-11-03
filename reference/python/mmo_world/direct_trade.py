"""Direkter Handel zwischen zwei Figuren mit Zustimmung beider Seiten (Angebot -> Annahme). Siehe ADR-0023.

* Ein Angebot richtet sich an genau eine andere Figur und ist unveränderlich. Der Anbieter hinterlegt seine Leistung sofort
  im Treuhandkonto `trade:escrow` (Ware beim Verkaufsangebot, Münzen beim Kaufangebot) – ein Angebot ist also immer gedeckt.
* Die Gegenseite kann annehmen (nur sie), ablehnen; der Anbieter kann zurücknehmen; nach `offer_days` verfällt es.
* Die Annahme läuft durch den `TradeService` (beide CEE-Handelsberichte, Plausibilität, Wiederholungsabnahme je Partner);
  scheitert sie (z. B. zu wenig Münzen/Ware der Gegenseite, Regelablehnung), bleibt das Angebot unverändert bestehen.
* Preise sind frei (die CEE wertet nur Preise nahe am Referenzwert); die Gebühr (Anteil des Erlöses) geht an die Geldsenke.
Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Callable

from mmo_cee.service import CharacterService

from .errors import WorldError
from .inventory import Inventory
from .market import TradeResult, TradeService

ESCROW = "trade:escrow"
SINK = "world:sink"
SIDES = ("sell", "buy")


def load_trade_rules(name: str = "trade_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_trade_rules(tr: dict[str, Any], cee_rules: Any) -> None:
    if int(cee_rules.version) < tr["requires_cee_rules_min"]:
        raise WorldError(f"trade_rules benötigen CEE-Regeln >= v{tr['requires_cee_rules_min']}")
    if not _is_int(tr["fee_permille"]) or not 0 <= tr["fee_permille"] <= 1000:
        raise WorldError("fee_permille muss 0..1000 sein")
    for k in ("offer_days", "max_open_offers", "max_incoming_offers"):
        if not _is_int(tr[k]) or tr[k] < 1:
            raise WorldError(f"{k} muss >= 1 sein")


@dataclass(frozen=True)
class Settlement:
    trade: TradeResult
    fee: int


class DirectTrade:
    def __init__(self, service: CharacterService, inventory: Inventory, trading: TradeService, rules: dict[str, Any],
                 day_provider: Callable[[], int], server_id: str = "srv1") -> None:
        validate_trade_rules(rules, service.rules)
        self.cee, self.inv, self.trading, self.tr, self.day, self.server_id = service, inventory, trading, rules, day_provider, server_id
        self.coin = trading.coin
        self.offers: dict[str, dict[str, Any]] = {}
        self._counter = 0

    @property
    def active(self) -> bool:
        return self._counter > 0

    # -- Hilfen ------------------------------------------------------------------------
    def _escrow_of(self, o: dict[str, Any]) -> tuple[str, int]:
        return (o["item_key"], o["qty"]) if o["side"] == "sell" else (self.coin, o["price"])

    def open_offers(self, character_id: str) -> dict[str, list[str]]:
        """Offene Angebote einer Figur: ausgehende und eingehende (sortiert)."""
        return {"outgoing": sorted(k for k, o in self.offers.items() if o["from"] == character_id),
                "incoming": sorted(k for k, o in self.offers.items() if o["to"] == character_id)}

    def get(self, offer_id: str) -> dict[str, Any]:
        o = self.offers.get(offer_id) if isinstance(offer_id, str) else None
        if o is None:
            raise WorldError("Angebot unbekannt oder erledigt")
        return o

    # -- Angebot stellen -----------------------------------------------------------------
    def make(self, proposer: str, counterparty: str, side: str, item_key: str, qty: int, price: int) -> str:
        today = self.day()
        if side not in SIDES:
            raise WorldError("side muss 'sell' oder 'buy' sein")
        if not isinstance(counterparty, str) or not self.cee.log.has(proposer) or not self.cee.log.has(counterparty):
            raise WorldError("Unbekannte Figur")
        if proposer == counterparty:
            raise WorldError("Angebote an sich selbst sind unzulässig")
        self.trading.parse(item_key)
        t = self.cee.rules["economy"]["trade"]
        if not _is_int(qty) or not 1 <= qty <= t["max_quantity"]:
            raise WorldError("Ungültige Menge")
        if not _is_int(price) or not 1 <= price <= t["max_value"]:
            raise WorldError("Ungültiger Preis")
        mine, theirs = self.open_offers(proposer), self.open_offers(counterparty)
        if len(mine["outgoing"]) >= self.tr["max_open_offers"]:
            raise WorldError("Zu viele offene Angebote")
        if len(theirs["incoming"]) >= self.tr["max_incoming_offers"]:
            raise WorldError("Die Gegenseite hat zu viele offene Angebote")
        self._counter += 1
        oid = f"{self.server_id}-off-{self._counter:08d}"
        o = {"id": oid, "from": proposer, "to": counterparty, "side": side, "item_key": item_key, "qty": qty, "price": price,
             "day": today, "expires": today + self.tr["offer_days"]}
        key, amount = self._escrow_of(o)
        try:
            self.inv.apply_many([(proposer, {key: amount}, {}), (ESCROW, {}, {key: amount})])
        except WorldError:
            self._counter -= 1
            raise
        self.offers[oid] = o
        return oid

    def _refund(self, o: dict[str, Any]) -> None:
        key, amount = self._escrow_of(o)
        self.inv.apply_many([(ESCROW, {key: amount}, {}), (o["from"], {}, {key: amount})])
        del self.offers[o["id"]]

    # -- Antwort -----------------------------------------------------------------------------
    def accept(self, character_id: str, offer_id: str) -> Settlement:
        today = self.day()
        o = self.get(offer_id)
        if o["to"] != character_id:
            raise WorldError("Nur die angesprochene Figur kann annehmen")
        if today >= o["expires"]:
            raise WorldError("Das Angebot ist abgelaufen")
        seller, buyer = (o["from"], o["to"]) if o["side"] == "sell" else (o["to"], o["from"])
        key, amount = self._escrow_of(o)
        self.inv.apply_many([(ESCROW, {key: amount}, {}), (o["from"], {}, {key: amount})])  # Leistung zurück an den Anbieter ...
        try:
            res = self.trading.trade(seller, buyer, o["item_key"], o["qty"], o["price"])  # ... dann regulärer, voll validierter Handel
        except Exception:
            self.inv.apply_many([(o["from"], {key: amount}, {}), (ESCROW, {}, {key: amount})])
            raise
        fee = o["price"] * self.tr["fee_permille"] // 1000
        if fee:
            self.inv.apply(seller, {self.coin: fee}, {})
            self.inv.deposit(SINK, self.coin, fee)
        del self.offers[offer_id]
        return Settlement(res, fee)

    def decline(self, character_id: str, offer_id: str) -> None:
        self.day()
        o = self.get(offer_id)
        if o["to"] != character_id:
            raise WorldError("Nur die angesprochene Figur kann ablehnen")
        self._refund(o)

    def cancel(self, character_id: str, offer_id: str) -> None:
        self.day()
        o = self.get(offer_id)
        if o["from"] != character_id:
            raise WorldError("Nur der Anbieter kann das Angebot zurücknehmen")
        self._refund(o)

    def expire(self, day: int) -> list[str]:
        """Serverinterner Tagesschritt: räumt verfallene Angebote ab (Rückgabe der Hinterlegung)."""
        if not _is_int(day) or day < 0:
            raise WorldError("day ungültig")
        gone = sorted(k for k, o in self.offers.items() if o["expires"] <= day)
        for k in gone:
            self._refund(self.offers[k])
        return gone

    # -- Invarianten und Persistenz -------------------------------------------------------------
    def check(self) -> list[str]:
        errs: list[str] = []
        need: dict[str, int] = {}
        for o in self.offers.values():
            if o["from"] == o["to"]:
                errs.append(f"{o['id']}: Angebot an sich selbst")
            key, amount = self._escrow_of(o)
            need[key] = need.get(key, 0) + amount
        held = self.inv.holdings(ESCROW)
        if dict(sorted(held.items())) != dict(sorted(need.items())):
            errs.append(f"Treuhandkonto {held} deckt die offenen Angebote {need} nicht exakt")
        return errs

    def to_json(self) -> str:
        return json.dumps({"counter": self._counter, "offers": self.offers}, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        data = json.loads(text)
        self._counter, self.offers = data["counter"], data["offers"]
        problems = self.check()
        if problems:
            raise WorldError("; ".join(problems))
