"""Markt: Orderbuch je Gegenstand+Güteklasse, Preis-Zeit-Priorität, Preisindex. Siehe ADR-0015.

* Orders sind Limit-Orders (Stückpreis, ganzzahlig). Ware (Verkauf) bzw. Münzen (Kauf) liegen bis zur Ausführung im
  Treuhandkonto `market:escrow` – eine Order ist also immer gedeckt.
* Ausführung: Preis-Zeit-Priorität; es gilt der Preis der wartenden Order. Teilausführung möglich. Eigene Orders werden
  nicht gegeneinander ausgeführt. Jede Ausführung läuft durch den `TradeService` (CEE-Handelsberichte, Plausibilität,
  Wash-Trading-Schutz bleiben unverändert).
* Preisbildung: Preise entstehen aus Angebot und Nachfrage innerhalb eines Bandes um den Referenzwert der Regeltabelle
  (`band_permille`); der Index (letzter Preis, gleitender Durchschnitt, Tagesverlauf) ist reine Information.
* Gebühr: Anteil des Erlöses (`fee_permille`, abgerundet) geht an die Geldsenke `world:sink`.
* Orders verfallen nach `order_days`; `expire(day)` räumt auf (serverinterner Tagesschritt).
Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Callable

from mmo_cee.economy import reference_value
from mmo_cee.service import CharacterService

from .errors import WorldError
from .inventory import Inventory
from .market import TradeService

ESCROW = "market:escrow"
SINK = "world:sink"
SIDES = ("buy", "sell")


def load_market_rules(name: str = "market_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_market_rules(mr: dict[str, Any], cee_rules: Any) -> None:
    if int(cee_rules.version) < mr["requires_cee_rules_min"]:
        raise WorldError(f"market_rules benötigen CEE-Regeln >= v{mr['requires_cee_rules_min']}")
    for k in ("fee_permille", "band_permille", "ema_alpha_permille"):
        if not _is_int(mr[k]) or not 0 <= mr[k] <= 1000:
            raise WorldError(f"{k} muss 0..1000 sein")
    for k in ("order_days", "max_open_orders", "history_days"):
        if not _is_int(mr[k]) or mr[k] < 1:
            raise WorldError(f"{k} muss >= 1 sein")


@dataclass(frozen=True)
class Fill:
    trade_id: str
    item_key: str
    quantity: int
    unit_price: int
    total: int
    fee: int
    seller: str
    buyer: str
    buy_order: str
    sell_order: str


@dataclass(frozen=True)
class PlaceResult:
    order_id: str | None  # None, wenn nichts in das Buch gestellt wurde
    fills: list[Fill]
    remaining: int


class Exchange:
    def __init__(self, service: CharacterService, inventory: Inventory, trading: TradeService, rules: dict[str, Any],
                 day_provider: Callable[[], int], server_id: str = "srv1") -> None:
        validate_market_rules(rules, service.rules)
        self.cee, self.inv, self.trading, self.mr, self.day, self.server_id = service, inventory, trading, rules, day_provider, server_id
        self.coin = trading.coin
        self.orders: dict[str, dict[str, Any]] = {}
        self.stats: dict[str, dict[str, Any]] = {}
        self._counter = 0

    @property
    def active(self) -> bool:
        return self._counter > 0

    # -- Hilfen ------------------------------------------------------------------------
    def _check_item(self, item_key: str) -> tuple[str, str]:
        return self.trading.parse(item_key)

    def _band(self, item_key: str, unit_price: int) -> None:
        item, grade = self._check_item(item_key)
        ref = reference_value(self.cee.rules, item, grade, 1)
        if abs(unit_price - ref) * 1000 > self.mr["band_permille"] * ref:
            raise WorldError(f"Preis außerhalb des Preisbandes (Referenz {ref}, Band ±{self.mr['band_permille']}‰)")

    def open_orders(self, character_id: str) -> list[str]:
        return sorted(k for k, o in self.orders.items() if o["char"] == character_id)

    def _book(self, item_key: str, side: str) -> list[dict[str, Any]]:
        os = [o for o in self.orders.values() if o["item_key"] == item_key and o["side"] == side]
        # Kauf: höchster Preis zuerst, Verkauf: niedrigster zuerst; bei Gleichstand die ältere Order
        return sorted(os, key=lambda o: (-o["price"] if side == "buy" else o["price"], o["seq"]))

    def quote(self, item_key: str) -> dict[str, Any]:
        self._check_item(item_key)
        bids, asks = self._book(item_key, "buy"), self._book(item_key, "sell")
        st = self.stats.get(item_key)
        depth = lambda side: sum(o["remaining"] for o in self._book(item_key, side))  # noqa: E731
        return {"best_bid": bids[0]["price"] if bids else None, "best_ask": asks[0]["price"] if asks else None,
                "bid_depth": depth("buy"), "ask_depth": depth("sell"),
                "last": st["last"] if st else None, "ema": st["ema_milli"] // 1000 if st else None}

    def _escrow_cost(self, o: dict[str, Any], qty: int) -> tuple[str, int]:
        return (o["item_key"], qty) if o["side"] == "sell" else (self.coin, qty * o["price"])

    # -- Order stellen ------------------------------------------------------------------
    def place(self, character_id: str, side: str, item_key: str, quantity: int, unit_price: int, ioc: bool = False) -> PlaceResult:
        today = self.day()
        if side not in SIDES:
            raise WorldError("side muss 'buy' oder 'sell' sein")
        if not self.cee.log.has(character_id):
            raise WorldError("Unbekannte Figur")
        self._check_item(item_key)
        t = self.cee.rules["economy"]["trade"]
        if not _is_int(quantity) or not 1 <= quantity <= t["max_quantity"]:
            raise WorldError("Ungültige Menge")
        if not _is_int(unit_price) or unit_price < 1 or unit_price * quantity > t["max_value"]:
            raise WorldError("Ungültiger Preis")
        if not isinstance(ioc, bool):
            raise WorldError("ioc muss bool sein")
        self._band(item_key, unit_price)
        if len(self.open_orders(character_id)) >= self.mr["max_open_orders"] and not ioc:
            raise WorldError("Zu viele offene Orders")
        self._counter += 1
        oid = f"{self.server_id}-ord-{self._counter:08d}"
        order = {"id": oid, "seq": self._counter, "char": character_id, "side": side, "item_key": item_key, "qty": quantity,
                 "remaining": quantity, "price": unit_price, "day": today, "expires": today + self.mr["order_days"]}
        key, amount = self._escrow_cost(order, quantity)
        try:
            self.inv.apply_many([(character_id, {key: amount}, {}), (ESCROW, {}, {key: amount})])
        except WorldError:
            self._counter -= 1
            raise
        self.orders[oid] = order
        fills: list[Fill] = []
        try:
            self._match(order, fills)
        except Exception:
            self._remove(order, refund=True)  # die laufende Order wird zurückgenommen, bisherige Ausführungen bleiben
            raise
        if order["remaining"] > 0 and ioc:
            self._remove(order, refund=True)
        return PlaceResult(oid if oid in self.orders else None, fills, order["remaining"])

    def _remove(self, order: dict[str, Any], refund: bool) -> None:
        if order["id"] not in self.orders:
            return
        if refund and order["remaining"] > 0:
            key, amount = self._escrow_cost(order, order["remaining"])
            self.inv.apply_many([(ESCROW, {key: amount}, {}), (order["char"], {}, {key: amount})])
        del self.orders[order["id"]]

    def cancel(self, character_id: str, order_id: str) -> None:
        self.day()
        o = self.orders.get(order_id) if isinstance(order_id, str) else None
        if o is None:
            raise WorldError("Order unbekannt oder erledigt")
        if o["char"] != character_id:
            raise WorldError("Nur der Besitzer kann die Order zurücknehmen")
        self._remove(o, refund=True)

    def expire(self, day: int) -> list[str]:
        """Serverinterner Tagesschritt: räumt verfallene Orders ab (Rückgabe der Hinterlegung)."""
        if not _is_int(day) or day < 0:
            raise WorldError("day ungültig")
        gone = sorted(k for k, o in self.orders.items() if o["expires"] <= day)
        for k in gone:
            self._remove(self.orders[k], refund=True)
        return gone

    # -- Ausführung ---------------------------------------------------------------------
    def _match(self, inc: dict[str, Any], fills: list[Fill]) -> None:
        opp = "sell" if inc["side"] == "buy" else "buy"
        for rest in self._book(inc["item_key"], opp):
            if inc["remaining"] <= 0:
                break
            crosses = rest["price"] <= inc["price"] if inc["side"] == "buy" else rest["price"] >= inc["price"]
            if not crosses:
                break  # Buch ist nach Preis sortiert: dahinter kreuzt nichts mehr
            if rest["char"] == inc["char"]:
                continue  # keine Selbstausführung
            buy, sell = (inc, rest) if inc["side"] == "buy" else (rest, inc)
            q = min(inc["remaining"], rest["remaining"])
            fills.append(self._execute(buy, sell, q, rest["price"]))

    def _execute(self, buy: dict[str, Any], sell: dict[str, Any], q: int, unit: int) -> Fill:
        total = q * unit
        item_key = buy["item_key"]
        # Hinterlegtes an die Parteien zurück, dann regulärer Handel (vollständig validiert; bei Fehler wird zurückgebucht)
        release = [(ESCROW, {item_key: q, self.coin: q * buy["price"]}, {}), (sell["char"], {}, {item_key: q}),
                   (buy["char"], {}, {self.coin: q * buy["price"]})]
        self.inv.apply_many(release)
        try:
            res = self.trading.trade(sell["char"], buy["char"], item_key, q, total)
        except Exception:
            self.inv.apply_many([(sell["char"], {item_key: q}, {}), (buy["char"], {self.coin: q * buy["price"]}, {}),
                                 (ESCROW, {}, {item_key: q, self.coin: q * buy["price"]})])
            raise
        fee = total * self.mr["fee_permille"] // 1000
        if fee:
            self.inv.apply(sell["char"], {self.coin: fee}, {})
            self.inv.deposit(SINK, self.coin, fee)
        for o in (buy, sell):
            o["remaining"] -= q
            if o["remaining"] == 0:
                del self.orders[o["id"]]
        self._record_price(item_key, unit, q)
        return Fill(res.trade_id, item_key, q, unit, total, fee, sell["char"], buy["char"], buy["id"], sell["id"])

    def _record_price(self, item_key: str, unit: int, q: int) -> None:
        today, a = self.day(), self.mr["ema_alpha_permille"]
        st = self.stats.get(item_key)
        if st is None:
            st = self.stats[item_key] = {"last": unit, "ema_milli": unit * 1000, "day": today, "open": unit, "high": unit,
                                         "low": unit, "volume": 0, "closes": []}
        if st["day"] != today:  # Tagesabschluss der vorigen Handelstage
            st["closes"] = (st["closes"] + [[st["day"], st["last"], st["volume"]]])[-self.mr["history_days"]:]
            st.update(day=today, open=unit, high=unit, low=unit, volume=0)
        st["last"] = unit
        st["ema_milli"] = (st["ema_milli"] * (1000 - a) + unit * 1000 * a) // 1000
        st["high"], st["low"] = max(st["high"], unit), min(st["low"], unit)
        st["volume"] += q

    # -- Invarianten und Persistenz -------------------------------------------------------
    def check(self) -> list[str]:
        errs: list[str] = []
        need: dict[str, int] = {}
        for o in self.orders.values():
            if not 0 < o["remaining"] <= o["qty"]:
                errs.append(f"{o['id']}: Restmenge ungültig")
            key, amount = self._escrow_cost(o, o["remaining"])
            need[key] = need.get(key, 0) + amount
        held = self.inv.holdings(ESCROW)
        if dict(sorted(held.items())) != dict(sorted(need.items())):
            errs.append(f"Treuhandkonto {held} deckt die offenen Orders {need} nicht exakt")
        return errs

    def to_json(self) -> str:
        return json.dumps({"counter": self._counter, "orders": self.orders, "stats": self.stats}, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        data = json.loads(text)
        self._counter, self.orders, self.stats = data["counter"], data["orders"], data["stats"]
        problems = self.check()
        if problems:
            raise WorldError("; ".join(problems))
