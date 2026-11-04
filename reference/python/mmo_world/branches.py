"""Filialen und Offline-Betrieb mit Deckel (AP 10, ADR-0049). Serverautoritativ; ergänzt Firmen und Produktion, ohne sie umzuschreiben.

* Eine Filiale gehört zu einer Firma und liegt in einer Region. Sie bringt zusätzliche Produktionslinien und Lager, kostet aber bei der
  Eröffnung (Geldsenke) und täglich (Betriebskosten aus der Firmenkasse). Reicht die Kasse mehrere Tage nicht, wird sie ruhend.
* Die Zahl der Filialen hängt von der Unternehmensstufe ab. Pro Region höchstens eine Filiale je Firma.
* Offline-Deckel: War niemand aus der Leitung (Gründer, Geschäftsführer, Betriebsleiter) in den letzten Tagen aktiv, laufen nur
  `offline_lines` Aufträge weiter. Figuren ohne bekannte Aktivität gelten als aktiv (alte Welten/Tests unverändert).
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable

from .company import company_level
from .company_service import CompanyService
from .errors import WorldError

SINK = "world:sink"


def load_branch_rules(name: str = "branch_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


class BranchService:
    def __init__(self, companies: CompanyService, rules: dict[str, Any], day_provider: Callable[[], int]) -> None:
        for k in ("open_cost", "reopen_cost", "upkeep_per_day", "extra_lines", "extra_storage", "dormant_after_unpaid_days"):
            if not _is_int(rules[k]) or rules[k] < 0:
                raise WorldError(f"branch_rules.{k} ungültig")
        if rules["dormant_after_unpaid_days"] < 1 or not rules["regions"]:
            raise WorldError("branch_rules ungültig")
        self.cs, self.R, self.day = companies, rules, day_provider
        self.branches: dict[str, dict[str, Any]] = {}
        self.last_active: dict[str, int] = {}
        self._counter = 0
        companies.day_hooks.append(self._tick)
        companies.close_hooks.append(lambda c: [self.branches.pop(b["id"]) for b in self.of(c["id"])])

    @property
    def active(self) -> bool:
        return bool(self.branches or self.last_active)

    # -- Aktivität ------------------------------------------------------------------
    def touch(self, char: str, day: int | None = None) -> None:
        """Merkt den letzten aktiven Tag - nur für Figuren, die in einer offenen Firma leiten oder angestellt sind (Datensparsamkeit)."""
        if day is not None or char in self.last_active or any(
                c["open"] and (c["founder"] == char or c["ceo"] == char or char in c["employees"]) for c in self.cs.reg.companies.values()):
            self.last_active[char] = self.day() if day is None else day

    def _leaders(self, c: dict[str, Any]) -> list[str]:
        out = {x for x in (c["founder"], c["ceo"]) if x}
        out |= {e for e in c["employees"] if self.cs.cee.state(e).parts["economy"]["career"]["role"] in ("manager", "executive", "department_head")}
        return sorted(out)

    def owner_active(self, c: dict[str, Any], today: int) -> bool:
        known = [self.last_active[x] for x in self._leaders(c) if x in self.last_active]
        if not known:
            return True
        return today - max(known) <= self.R["offline"]["active_within_days"]

    def offline_cap(self, c: dict[str, Any], today: int) -> int | None:
        """Höchstzahl gleichzeitig laufender Aufträge heute; None = kein Deckel."""
        return None if self.owner_active(c, today) else self.R["offline"]["offline_lines"]

    # -- Wirkung ---------------------------------------------------------------------
    def of(self, company_id: str) -> list[dict[str, Any]]:
        return [b for _, b in sorted(self.branches.items()) if b["company"] == company_id]

    def extra_lines(self, c: dict[str, Any]) -> int:
        return self.R["extra_lines"] * sum(1 for b in self.of(c["id"]) if b["status"] == "open")

    def extra_storage(self, c: dict[str, Any]) -> int:
        return self.R["extra_storage"] * sum(1 for b in self.of(c["id"]) if b["status"] == "open")

    def limit(self, c: dict[str, Any]) -> int:
        lv = company_level(self.cs.cr, c["revenue_total"])
        t = self.R["max_branches_by_company_level"]
        return t[min(lv, len(t)) - 1]

    # -- Aktionen ---------------------------------------------------------------------
    def open_branch(self, actor: str, company_id: str, region: str) -> str:
        today = self.day()
        c = self.cs._need_manage(company_id, actor)
        if region not in self.R["regions"]:
            raise WorldError("In dieser Region sind keine Filialen möglich")
        mine = self.of(company_id)
        if any(b["region"] == region for b in mine):
            raise WorldError("In dieser Region gibt es schon eine Filiale")
        if len(mine) >= self.limit(c):
            raise WorldError("Die Unternehmensstufe erlaubt keine weitere Filiale")
        cost = self.R["open_cost"]
        if self.cs.balance(company_id) < cost:
            raise WorldError("Kasse reicht für die Eröffnung nicht aus")
        self.cs._pay(self.cs._treasury(c), SINK, cost)
        self._counter += 1
        bid = f"{self.cs.server_id}-br-{self._counter:06d}"
        self.branches[bid] = {"id": bid, "company": company_id, "region": region, "opened": today, "status": "open", "unpaid": 0}
        self.cs.reg.log(c, today, "branch_opened", branch=bid, region=region, cost=cost)
        return bid

    def close_branch(self, actor: str, company_id: str, branch_id: str) -> None:
        c = self.cs._need_manage(company_id, actor)
        b = self.branches.get(branch_id) if isinstance(branch_id, str) else None
        if b is None or b["company"] != company_id:
            raise WorldError("Filiale unbekannt")
        del self.branches[branch_id]
        self.cs.reg.log(c, self.day(), "branch_closed", branch=branch_id)

    def reopen_branch(self, actor: str, company_id: str, branch_id: str) -> None:
        c = self.cs._need_manage(company_id, actor)
        b = self.branches.get(branch_id) if isinstance(branch_id, str) else None
        if b is None or b["company"] != company_id:
            raise WorldError("Filiale unbekannt")
        if b["status"] != "dormant":
            raise WorldError("Die Filiale ist nicht ruhend")
        if self.cs.balance(company_id) < self.R["reopen_cost"]:
            raise WorldError("Kasse reicht für die Wiedereröffnung nicht aus")
        self.cs._pay(self.cs._treasury(c), SINK, self.R["reopen_cost"])
        b["status"], b["unpaid"] = "open", 0
        self.cs.reg.log(c, self.day(), "branch_reopened", branch=branch_id)

    def _tick(self, c: dict[str, Any], d: int, paid: dict[str, bool]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for b in self.of(c["id"]):
            if b["status"] != "open":
                continue
            up = self.R["upkeep_per_day"]
            if self.cs.balance(c["id"]) >= up:
                self.cs._pay(self.cs._treasury(c), SINK, up)
                c["costs_today"] += up
                b["unpaid"] = 0
            else:
                b["unpaid"] += 1
                if b["unpaid"] >= self.R["dormant_after_unpaid_days"]:
                    b["status"] = "dormant"
                    self.cs.reg.log(c, d, "branch_dormant", branch=b["id"])
                    out.append({"day": d, "company": c["id"], "kind": "branch_dormant", "branch": b["id"]})
        return out

    def view(self, company_id: str) -> dict[str, Any]:
        c = self.cs.reg.companies[company_id]
        return {"branches": [dict(b) for b in self.of(company_id)], "limit": self.limit(c), "open_cost": self.R["open_cost"],
                "upkeep_per_day": self.R["upkeep_per_day"], "reopen_cost": self.R["reopen_cost"], "regions": list(self.R["regions"]),
                "extra_lines": self.extra_lines(c), "extra_storage": self.extra_storage(c),
                "owner_active": self.owner_active(c, self.day()), "offline_lines": self.R["offline"]["offline_lines"]}

    def check(self) -> list[str]:
        errs = []
        for bid, b in self.branches.items():
            if b["company"] not in self.cs.reg.companies:
                errs.append(f"{bid}: Firma {b['company']} unbekannt")
            elif not self.cs.reg.companies[b["company"]]["open"]:
                errs.append(f"{bid}: Firma geschlossen, Filiale besteht weiter")
        return errs

    def to_json(self) -> str:
        return json.dumps({"counter": self._counter, "branches": self.branches, "last_active": self.last_active}, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        d = json.loads(text)
        self._counter, self.branches, self.last_active = d["counter"], d["branches"], d["last_active"]
