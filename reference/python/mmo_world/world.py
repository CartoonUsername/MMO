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
from .equipment import EquipmentService, load_equipment_rules
from .community import Chronicle, GuildService, load_community_rules
from .research import ResearchService, load_research_rules
from .settlements import SettlementService, load_settlement_rules
from .branches import BranchService, load_branch_rules
from .echo import EchoService, load_echo_rules
from .direct_trade import DirectTrade, load_trade_rules
from .discovery import DiscoveryRegistry
from .errors import WorldError
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
ECHO_RULES = "echo_rules_v2.json"
EQUIPMENT_RULES = "equipment_rules_v2.json"      # v2: Setboni (AP 61, ADR-0076); v1 bleibt erhalten
BRANCH_RULES = "branch_rules_v1.json"
SETTLEMENT_RULES = "settlement_rules_v2.json"      # v2: Marktplatz-Rabatt 250/500 ‰ (ADR-0067); v1 bleibt erhalten
RESEARCH_RULES = "research_rules_v2.json"      # v2: Marktrecht, Lagerwesen, Stadtrecht (AP 70, ADR-0079); v1 bleibt erhalten
COMMUNITY_RULES = "community_rules_v3.json"      # v3: Chronikart masterpiece_first (AP 46, ADR-0074); v2 bleibt erhalten


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

    def _masterpiece_made(self, char: str, recipe_id: str) -> None:
        if "masterpiece_first" in self.chronicle.R["kinds"]:                                     # ältere Gemeinschaftsregeln kennen die Art nicht
            self.chronicle.record("masterpiece_first", [char], key=f"masterpiece:{recipe_id}", name=recipe_id.replace("_", " "), recipe=recipe_id)

    def specialize(self, char: str, profession: str, branch: str) -> dict[str, Any]:
        """Zweigwahl / Respezialisierung eines Berufs (AP 33, ADR-0068): CEE prüft Erfahrung, Zweig und Abklingzeit, die Welt nimmt die Münzen (Senke)."""
        from mmo_cee.professions import SPEC_EVENT
        cfg = self.svc.rules_of(char)["professions"].get("specialization")
        if cfg is None:
            raise WorldError("Zweigwahl gibt es in dieser Regelversion nicht")
        payload = {"profession": profession, "branch": branch, "day": self.day[0]}
        state = self.svc.state(char)
        self.svc.projector.validate(state, SPEC_EVENT, payload)                 # vorab prüfen, damit nichts bezahlt wird, was abgelehnt würde
        cost = cfg["cost_change" if state.parts["profession"].get("spec", {}).get(profession) else "cost_first"]
        if cost and self.inv.balance(char, self.trading.coin) < cost:
            raise WorldError(f"Zu wenig Münzen ({cost} nötig)")
        if cost:
            self.inv.apply(char, {self.trading.coin: cost}, {})
        self.svc.record(char, SPEC_EVENT, payload)
        return {"profession": profession, "branch": branch, "day": payload["day"], "paid": cost}

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
        oldb = getattr(self, "branches", None)
        self.branches = BranchService(self.company, load_branch_rules(BRANCH_RULES), clock)    # vor der Produktion: Betriebskosten zuerst
        if oldb is not None:
            self.branches._counter, self.branches.branches, self.branches.last_active = oldb._counter, oldb.branches, oldb.last_active
        olds = getattr(self, "settlements", None)
        self.settlements = SettlementService(self.inv, self.trading.coin, load_settlement_rules(SETTLEMENT_RULES), clock,
                                             lambda c: c in set(self.svc.log.character_ids()))
        if olds is not None:
            self.settlements.founded, self.settlements.plots, self.settlements.projects = olds.founded, olds.plots, olds.projects
            self.settlements.contrib, self.settlements.last_day = olds.contrib, olds.last_day
            self.settlements.sales = olds.sales
        self.exchange.order_bonus = lambda c: self.settlements.order_bonus(c)                  # Hafen: mehr offene Orders (AP 41)
        self.exchange.fee_discount = lambda c: self.settlements.fee_discount_permille(c)      # Marktplatz-Rabatt (AP 29)
        oldr = getattr(self, "research", None)
        self.research = ResearchService(self.settlements, self.inv, self.trading.coin, load_research_rules(RESEARCH_RULES), clock)
        if oldr is not None:
            for a in ("epoch", "known", "projects", "world", "titles", "history", "last_day"):
                setattr(self.research, a, getattr(oldr, a))
        crules = load_community_rules(COMMUNITY_RULES)
        oldc, oldg2 = getattr(self, "chronicle", None), getattr(self, "guilds", None)
        self.chronicle = Chronicle(crules, clock)
        self.guilds = GuildService(self.inv, self.trading.coin, crules, clock, lambda c: c in set(self.svc.log.character_ids()))
        if oldc is not None:
            self.chronicle.entries, self.chronicle.firsts, self.chronicle.titles = oldc.entries, oldc.firsts, oldc.titles
        if oldg2 is not None:
            self.guilds._counter, self.guilds.guilds, self.guilds.member_of, self.guilds.invites = oldg2._counter, oldg2.guilds, oldg2.member_of, oldg2.invites
        self.settlements.record = self.research.record = self.guilds.record = self.chronicle.record
        self.crafting.masterpiece = self._masterpiece_made                                       # erstes Meisterstück je Rezept (AP 46)
        oldp = getattr(self, "production", None)
        self.production = ProductionService(self.svc, self.inv, self.company, load_production_rules(PRODUCTION_RULES), clock, sid, self.trading)
        self.production.extra_lines, self.production.extra_storage, self.production.offline_cap = (
            self.branches.extra_lines, self.branches.extra_storage, self.branches.offline_cap)
        if oldp is not None:
            self.production._counter, self.production.jobs, self.production.npc_sold = oldp._counter, oldp.jobs, oldp.npc_sold
        oldq = getattr(self, "pricing", None)
        self.pricing = None
        if "dynamic_reference" in self.svc.rules["economy"]:  # ab CEE-Regeln v8
            self.pricing = PricingService(self.svc, self.inv, self.trading, self.exchange, load_pricing_rules(PRICING_RULES), clock)
            if oldq is not None:
                self.pricing.factors, self.pricing.shocks = oldq.factors, oldq.shocks
                self.pricing.maker_used, self.pricing.last_day = oldq.maker_used, oldq.last_day
        olde = getattr(self, "echo", None)
        self.echo = EchoService(self.svc, self.inv, self.trading.coin, load_echo_rules(ECHO_RULES), clock, olde.seed if olde else None)
        if olde is not None:
            for a in ("_counter", "_listing_counter", "echoes", "listings", "equipped", "mastery", "mastery_day", "awards"):
                setattr(self.echo, a, getattr(olde, a))
        oldq2 = getattr(self, "equipment", None)
        self.equipment = EquipmentService(self.svc, self.inv, load_equipment_rules(EQUIPMENT_RULES))
        if oldq2 is not None:
            self.equipment.worn, self.equipment.look, self.equipment.wardrobe = oldq2.worn, oldq2.look, oldq2.wardrobe
        for svc in (self.discovery, self.company, self.exchange, self.offers, self.production, self.parties, self.echo, self.settlements):
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
        if self.branches.active:
            snap["branches"] = json.loads(self.branches.to_json())
        if self.settlements.active:
            snap["settlements"] = json.loads(self.settlements.to_json())
        if self.chronicle.active:
            snap["chronicle"] = json.loads(self.chronicle.to_json())
        if self.guilds.active:
            snap["guilds"] = json.loads(self.guilds.to_json())
        if self.research.active:
            snap["research"] = json.loads(self.research.to_json())
        if self.equipment.active:
            snap["equipment"] = json.loads(self.equipment.to_json())
        if self.echo.active:
            snap["echoes"] = json.loads(self.echo.to_json())
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
