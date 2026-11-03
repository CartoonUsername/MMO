"""Die Welt als Ganzes: CEE + Inventar + Register + Dienste, verdrahtet mit einer gemeinsamen Serverzeit.

Der Zusammenbau steht an einer Stelle, damit Golden Vectors (`golden.py`) und Persistenz (`persistence.py`)
dieselbe Welt beschreiben. Der Weltzustand (`snapshot`) ist genau das, was die Golden Vectors hashen.
"""
from __future__ import annotations

import json
from typing import Any

from mmo_cee.golden import state_hash
from mmo_cee.history import _canonical as canonical_bytes
from mmo_cee.rules import load_rules
from mmo_cee.service import CharacterService

from .company import CompanyRegistry, load_company_rules
from .company_service import CompanyService
from .crafting import CraftingService
from .discovery import DiscoveryRegistry
from .inventory import Inventory
from .market import TradeService
from .service import DiscoveryService

CEE_RULES = "rules_v7.json"
COMPANY_RULES = "company_rules_v1.json"


class World:
    def __init__(self, cee_rules: str = CEE_RULES, company_rules: str = COMPANY_RULES, server_id: str = "srv1") -> None:
        self.cee_rules_file, self.company_rules_file, self.server_id = cee_rules, company_rules, server_id
        self.svc = CharacterService(rules=load_rules(cee_rules))
        self.inv = Inventory()
        self.day = [1]
        clock = lambda: self.day[0]  # noqa: E731
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

    def snapshot(self) -> dict[str, Any]:
        return {"day": self.day[0], "inventory": json.loads(self.inv.to_json()),
                "discovery": json.loads(self.discovery_registry.to_json()),
                "companies": json.loads(self.company_registry.to_json()),
                "counters": {"trade": self.trading._counter, "craft": self.crafting._counter},
                "characters": {c: state_hash(json.loads(canonical_bytes(self.svc.state(c).parts)))
                               for c in self.svc.log.character_ids()}}
