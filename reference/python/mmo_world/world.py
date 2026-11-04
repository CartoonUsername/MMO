"""Die Welt als Ganzes: CEE + Inventar + Register + Dienste, verdrahtet mit einer gemeinsamen Serverzeit.

Der Zusammenbau steht an einer Stelle, damit Golden Vectors (`golden.py`) und Persistenz (`persistence.py`)
dieselbe Welt beschreiben. Der Weltzustand (`snapshot`) ist genau das, was die Golden Vectors hashen.
"""
from __future__ import annotations

import json
from typing import Any

from mmo_cee.golden import state_hash
from mmo_cee.history import _canonical as canonical_bytes
from mmo_cee.rules import load_rules, older_rules
from mmo_cee.service import CharacterService

from .company import CompanyRegistry, load_company_rules
from .company_service import CompanyService
from .crafting import CraftingService
from .direct_trade import DirectTrade, load_trade_rules
from .discovery import DiscoveryRegistry
from .notifications import Outbox
from .party import PartyService, load_party_rules
from .exchange import Exchange, load_market_rules
from .inventory import Inventory
from .market import TradeService
from .pricing import PricingService, load_pricing_rules
from .production import ProductionService, load_production_rules
from .service import DiscoveryService

CEE_RULES = "rules_v7.json"
COMPANY_RULES = "company_rules_v1.json"
MARKET_RULES = "market_rules_v1.json"
PRODUCTION_RULES = "production_rules_v1.json"
PRICING_RULES = "pricing_rules_v1.json"
TRADE_RULES = "trade_rules_v1.json"
PARTY_RULES = "party_rules_v1.json"


class World:
    def __init__(self, cee_rules: str = CEE_RULES, company_rules: str = COMPANY_RULES, server_id: str = "srv1") -> None:
        self.cee_rules_file, self.company_rules_file, self.server_id = cee_rules, company_rules, server_id
        rules = load_rules(cee_rules)
        self.svc = CharacterService(rules=rules, history_rules=older_rules(rules))
        self.inv = Inventory()
        self.day = [1]
        clock = lambda: self.day[0]  # noqa: E731
        self.outbox = Outbox(clock)
        self.discovery_registry = DiscoveryRegistry(self.svc.rules)
        self.company_rules = load_company_rules(company_rules)
        self.company_registry = CompanyRegistry(self.company_rules)
        self._wire(clock)

    def _wire(self, clock: Any) -> None:
        """(Neu) verdrahtet die Dienste mit den aktuellen Registern; Zähler der Dienste bleiben erhalten, wenn vorhanden."""
        sid = self.server_id
        self.discovery = DiscoveryService(self.svc, self.discovery_registry, clock)
        self.crafting = CraftingService(self.svc, self.inv, clock, sid)
        self.trading = TradeService(self.svc, self.inv, clock, sid)
        self.company = CompanyService(self.svc, self.inv, self.company_registry, clock, sid)
        old = getattr(self, "exchange", None)
        self.exchange = Exchange(self.svc, self.inv, self.trading, load_market_rules(MARKET_RULES), clock, sid)
        if old is not None:
            self.exchange._counter, self.exchange.orders, self.exchange.stats = old._counter, old.orders, old.stats
        oldg = getattr(self, "parties", None)
        self.parties = PartyService(self.svc, self.inv, self.trading, load_party_rules(PARTY_RULES), clock, sid)
        if oldg is not None:
            self.parties._counters, self.parties.parties, self.parties.invites = oldg._counters, oldg.parties, oldg.invites
            self.parties.member_of = oldg.member_of
        oldt = getattr(self, "offers", None)
        self.offers = DirectTrade(self.svc, self.inv, self.trading, load_trade_rules(TRADE_RULES), clock, sid)
        if oldt is not None:
            self.offers._counter, self.offers.offers = oldt._counter, oldt.offers
        oldp = getattr(self, "production", None)
        self.production = ProductionService(self.svc, self.inv, self.company, load_production_rules(PRODUCTION_RULES), clock, sid, self.trading)
        if oldp is not None:
            self.production._counter, self.production.jobs, self.production.npc_sold = oldp._counter, oldp.jobs, oldp.npc_sold
        oldq = getattr(self, "pricing", None)
        self.pricing = None
        if "dynamic_reference" in self.svc.rules["economy"]:  # ab CEE-Regeln v8
            self.pricing = PricingService(self.svc, self.inv, self.trading, self.exchange, load_pricing_rules(PRICING_RULES), clock)
            if oldq is not None:
                self.pricing.factors, self.pricing.shocks = oldq.factors, oldq.shocks
                self.pricing.maker_used, self.pricing.last_day = oldq.maker_used, oldq.last_day
        for svc in (self.discovery, self.company, self.exchange, self.offers, self.production, self.parties):
            svc.notify = self.outbox.emit  # Benachrichtigungen (abgeleitet, nicht Teil des Weltzustands/der Vektor-Hashes)

    def snapshot(self) -> dict[str, Any]:
        snap = self._base_snapshot()
        if self.exchange.active:  # ältere Snapshots/Vektoren ohne Markt bleiben unverändert
            snap["exchange"] = json.loads(self.exchange.to_json())
        if self.parties.active:
            snap["parties"] = json.loads(self.parties.to_json())
        if self.offers.active:
            snap["trade_offers"] = json.loads(self.offers.to_json())
        if self.production.active:
            snap["production"] = json.loads(self.production.to_json())
        if self.pricing is not None and self.pricing.active:
            snap["pricing"] = json.loads(self.pricing.to_json())
        return snap

    def _base_snapshot(self) -> dict[str, Any]:
        return {"day": self.day[0], "inventory": json.loads(self.inv.to_json()),
                "discovery": json.loads(self.discovery_registry.to_json()),
                "companies": json.loads(self.company_registry.to_json()),
                "counters": {"trade": self.trading._counter, "craft": self.crafting._counter},
                "characters": {c: state_hash(json.loads(canonical_bytes(self.svc.state(c).parts)))
                               for c in self.svc.log.character_ids()}}
