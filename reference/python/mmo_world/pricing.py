"""Preisdynamik: Referenzwerte folgen dem Markt, Schocks, NPC-Händler. Siehe ADR-0017.

* Je Gegenstand+Güte gibt es einen Faktor (Promille, 1000 = Tabellenwert). Der aktuelle Referenzwert ist
  `Tabellenwert x Faktor // 1000`; der Handelsdienst meldet ihn mit jedem Handel an die CEE (ab Regeln v8), die ihn nur
  innerhalb einer festen Spanne um den Tabellenwert akzeptiert.
* Tagesschritt (`advance`): Der Faktor nähert sich dem Marktsignal (gleitender Durchschnitt der Orderbuchpreise im
  Verhältnis zum Tabellenwert; ohne frischen Handel: Rückkehr zu 1000) mal einem eventuellen Schock. Schritt = Abstand x
  Glättung (Richtung Ziel abgeschnitten, mindestens 1 Promille); je Tag begrenzte Schrittweite, begrenzte Spanne – so bewegen einzelne Handel den Referenzwert nur langsam und beschränkt.
* Schocks (Angebots-/Nachfrageänderungen) setzt der Server (`set_shock`), zeitlich begrenzt; sie sind die Schnittstelle für
  spätere Weltereignisse.
* NPC-Händler: kauft/verkauft einfache Güter zum Referenzwert -/+ Spanne mit Tagesmenge je Gut und Seite. Er ist eine
  Figur wie alle (CEE-Berichte, Wiederholungsabnahme je Gegenpartei), nimmt Ware aus dem Kreislauf bzw. schafft sie und
  begrenzt so Extrempreise nach beiden Seiten.
Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable

from mmo_cee.economy import reference_value
from mmo_cee.service import CharacterService

from .errors import WorldError
from .exchange import Exchange
from .inventory import Inventory
from .market import TradeResult, TradeService

SINK = "world:sink"


def load_pricing_rules(name: str = "pricing_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_pricing_rules(pr: dict[str, Any], cee_rules: Any) -> None:
    if int(cee_rules.version) < pr["requires_cee_rules_min"] or "dynamic_reference" not in cee_rules["economy"]:
        raise WorldError("pricing_rules benötigen CEE-Regeln mit economy.dynamic_reference (>= v8)")
    cee_shift = cee_rules["economy"]["dynamic_reference"]["max_shift_permille"]
    for k in ("alpha_permille", "max_step_permille", "max_shift_permille"):
        if not _is_int(pr[k]) or not 0 <= pr[k] <= 1000:
            raise WorldError(f"{k} muss 0..1000 sein")
    if pr["max_shift_permille"] > cee_shift:
        raise WorldError("max_shift_permille darf die Spanne der CEE nicht überschreiten")
    for k in ("stale_days", "max_catch_up_days"):
        if not _is_int(pr[k]) or pr[k] < 1:
            raise WorldError(f"{k} muss >= 1 sein")
    sh = pr["shock"]
    if not _is_int(sh["max_permille"]) or not 0 <= sh["max_permille"] <= 900 or not _is_int(sh["max_days"]) or sh["max_days"] < 1:
        raise WorldError("shock ungültig")
    m = pr["maker"]
    items = cee_rules["economy"]["items"]
    if not m["items"] or any(i not in items for i in m["items"]) or len(set(m["items"])) != len(m["items"]):
        raise WorldError("maker.items muss handelbare Gegenstände ohne Doppelungen nennen")
    if not _is_int(m["spread_permille"]) or not 0 <= m["spread_permille"] <= 900 or not _is_int(m["daily_qty_per_side"]) or m["daily_qty_per_side"] < 1:
        raise WorldError("maker ungültig")
    if not isinstance(m["character_id"], str) or not 1 <= len(m["character_id"]) <= 64:
        raise WorldError("maker.character_id ungültig")


class PricingService:
    def __init__(self, service: CharacterService, inventory: Inventory, trading: TradeService, exchange: Exchange,
                 rules: dict[str, Any], day_provider: Callable[[], int]) -> None:
        validate_pricing_rules(rules, service.rules)
        self.cee, self.inv, self.trading, self.exchange, self.pr, self.day = service, inventory, trading, exchange, rules, day_provider
        self.factors: dict[str, int] = {}
        self.shocks: dict[str, dict[str, int]] = {}
        self.maker_used: dict[str, dict[str, Any]] = {}
        self.last_day = 0
        self.coin = trading.coin
        self.maker_id = rules["maker"]["character_id"]
        trading.reference_provider = self.reference

    @property
    def active(self) -> bool:
        return bool(self.factors or self.shocks or self.maker_used or self.last_day)

    # -- Referenzwert ---------------------------------------------------------------------
    def factor(self, item_key: str) -> int:
        return self.factors.get(item_key, 1000)

    def reference(self, item: str, grade: str, quantity: int) -> int:
        table = reference_value(self.cee.rules, item, grade, quantity)
        return table * self.factor(f"{item}@{grade}") // 1000

    # -- Schocks ------------------------------------------------------------------------------
    def set_shock(self, item_key: str, permille: int, days: int) -> None:
        today = self.day()
        self.trading.parse(item_key)
        sh = self.pr["shock"]
        if not _is_int(permille) or abs(permille - 1000) > sh["max_permille"] or permille == 1000:
            raise WorldError(f"Schock muss 1000 ± höchstens {sh['max_permille']} (und ungleich 1000) sein")
        if not _is_int(days) or not 1 <= days <= sh["max_days"]:
            raise WorldError(f"Dauer 1..{sh['max_days']} Tage")
        self.shocks[item_key] = {"permille": permille, "until": today + days}

    # -- Tagesschritt --------------------------------------------------------------------------
    def advance(self, day: int) -> dict[str, int]:
        if not _is_int(day) or day <= self.last_day:
            raise WorldError("day muss größer als der letzte verarbeitete Tag sein")
        if day - self.last_day > self.pr["max_catch_up_days"]:
            raise WorldError("Zu viele Tage auf einmal")
        for d in range(self.last_day + 1, day + 1):
            self._step(d)
        self.last_day = day
        return {k: v for k, v in sorted(self.factors.items())}

    def _step(self, d: int) -> None:
        pr = self.pr
        shift = pr["max_shift_permille"]
        for k in sorted(set(self.exchange.stats) | set(self.factors) | set(self.shocks)):
            item, grade = self.trading.parse(k)
            table_unit = reference_value(self.cee.rules, item, grade, 1)
            if table_unit < 1:
                continue
            st = self.exchange.stats.get(k)
            fresh = st is not None and d - st["day"] <= pr["stale_days"]
            target = st["ema_milli"] // table_unit if fresh else 1000  # Promille des Tabellenwerts
            shock = self.shocks.get(k)
            if shock is not None:
                if shock["until"] < d:
                    del self.shocks[k]
                else:
                    target = target * shock["permille"] // 1000
            cur = self.factor(k)
            raw = (target - cur) * pr["alpha_permille"]
            step = raw // 1000 if raw >= 0 else -(-raw // 1000)  # Richtung Ziel, Rest abgeschnitten (symmetrisch)
            if step == 0 and target != cur:
                step = 1 if target > cur else -1  # mindestens 1 Promille, damit der Faktor sein Ziel auch erreicht
            step = max(-pr["max_step_permille"], min(pr["max_step_permille"], step))
            new = max(1000 - shift, min(1000 + shift, cur + step))
            if new == 1000:
                self.factors.pop(k, None)
            else:
                self.factors[k] = new

    # -- NPC-Händler ----------------------------------------------------------------------------
    def _maker(self) -> str:
        if not self.cee.log.has(self.maker_id):
            self.cee.create(self.maker_id, "npc")
        return self.maker_id

    def _check(self, character_id: str, item_key: str, qty: int, side: str) -> tuple[str, str, int]:
        today = self.day()
        item, grade = self.trading.parse(item_key)
        if item not in self.pr["maker"]["items"]:
            raise WorldError("Der Händler handelt nicht mit diesem Gegenstand")
        if not _is_int(qty) or qty < 1:
            raise WorldError("Menge muss eine positive ganze Zahl sein")
        if not self.cee.log.has(character_id) or character_id == self.maker_id:
            raise WorldError("Unbekannte Figur")
        rec = self.maker_used.get(f"{item_key}|{side}")
        used = rec["qty"] if rec and rec["day"] == today else 0
        if used + qty > self.pr["maker"]["daily_qty_per_side"]:
            raise WorldError("Tagesmenge des Händlers erschöpft")
        return item, grade, used

    def quote(self, item_key: str, qty: int, side: str) -> int:
        """Preis des Händlers für `qty`: side 'sell' = er kauft von dir (abgerundet), 'buy' = er verkauft an dich (aufgerundet)."""
        item, grade = self.trading.parse(item_key)
        ref = self.reference(item, grade, qty)
        sp = self.pr["maker"]["spread_permille"]
        return ref * (1000 - sp) // 1000 if side == "sell" else -(-ref * (1000 + sp) // 1000)

    def sell_to_maker(self, character_id: str, item_key: str, qty: int) -> TradeResult:
        item, grade, used = self._check(character_id, item_key, qty, "sell")
        price = self.quote(item_key, qty, "sell")
        if price < 1:
            raise WorldError("Preis wäre 0")
        if self.inv.balance(character_id, item_key) < qty:
            raise WorldError("Verkäufer besitzt nicht genug")
        maker = self._maker()
        self.inv.deposit(maker, self.coin, price)  # Der Händler zahlt aus dem Nichts ...
        try:
            res = self.trading.trade(character_id, maker, item_key, qty, price)
        except Exception:
            self.inv.apply(maker, {self.coin: price}, {})
            raise
        self.inv.apply(maker, {item_key: qty}, {})  # ... und nimmt die Ware aus dem Kreislauf
        self.maker_used[f"{item_key}|sell"] = {"day": self.day(), "qty": used + qty}
        return res

    def buy_from_maker(self, character_id: str, item_key: str, qty: int) -> TradeResult:
        item, grade, used = self._check(character_id, item_key, qty, "buy")
        price = self.quote(item_key, qty, "buy")
        if self.inv.balance(character_id, self.coin) < price:
            raise WorldError("Käufer besitzt nicht genug Münzen")
        maker = self._maker()
        self.inv.deposit(maker, item_key, qty)  # Der Händler liefert aus dem Nichts ...
        try:
            res = self.trading.trade(maker, character_id, item_key, qty, price)
        except Exception:
            self.inv.apply(maker, {item_key: qty}, {})
            raise
        self.inv.apply(maker, {self.coin: price}, {})  # ... und nimmt die Münzen aus dem Kreislauf
        self.inv.deposit(SINK, self.coin, price)  # (als Geldsenke bilanziert)
        self.maker_used[f"{item_key}|buy"] = {"day": self.day(), "qty": used + qty}
        return res

    # -- Persistenz ---------------------------------------------------------------------------------
    def check(self) -> list[str]:
        errs: list[str] = []
        shift = self.pr["max_shift_permille"]
        for k, v in self.factors.items():
            if not _is_int(v) or v == 1000 or abs(v - 1000) > shift:
                errs.append(f"{k}: Faktor {v} ungültig")
        for k, s in self.shocks.items():
            if abs(s["permille"] - 1000) > self.pr["shock"]["max_permille"]:
                errs.append(f"{k}: Schock ungültig")
        held = self.inv.holdings(self.maker_id)
        if held:
            errs.append(f"Händler hält Bestände {held}")
        return errs

    def to_json(self) -> str:
        return json.dumps({"factors": self.factors, "shocks": self.shocks, "maker_used": self.maker_used, "last_day": self.last_day},
                          sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        data = json.loads(text)
        self.factors, self.shocks, self.maker_used, self.last_day = data["factors"], data["shocks"], data["maker_used"], data["last_day"]
        problems = self.check()
        if problems:
            raise WorldError("; ".join(problems))
