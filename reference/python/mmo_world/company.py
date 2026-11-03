"""Firmensimulation – reine Regeln und Register (Weltzustand). Siehe ADR-0012.

Alles ganzzahlig und deterministisch (Divisionen als Floor, Reihenfolgen sortiert). Mitarbeiter sind Figuren
(Spieler und NPCs laufen durch dieselbe Pipeline). Dieses Modul enthält keine CEE-/Inventar-Zugriffe; die
Orchestrierung (Berechtigungen, Münzen, CEE-Ereignisse, Rollback) liegt in `company_service.py`.
Alle Zahlen und Regeln sind Platzhalter (ADR-0012).
"""
from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import Any

from mmo_cee.rules import Rules

from .errors import WorldError


def load_company_rules(name: str = "company_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_company_rules(cr: dict[str, Any], cee_rules: Rules) -> None:
    if int(cee_rules.version) < cr["requires_cee_rules_min"]:
        raise WorldError(f"company_rules benötigen CEE-Regeln >= v{cr['requires_cee_rules_min']}")
    roles = cee_rules["economy"]["career"]["roles"]
    w = cr["wages"]
    if set(w["base_by_role"]) != set(roles) or any(not _is_int(v) or v < w["min_daily"] for v in w["base_by_role"].values()):
        raise WorldError("wages.base_by_role muss genau die Laufbahn-Rollen abdecken und >= min_daily sein")
    if not _is_int(w["min_daily"]) or w["min_daily"] < 1 or not _is_int(w["per_mastery"]) or w["per_mastery"] < 0:
        raise WorldError("wages ungültig")
    if not 0 <= w["max_profit_share_permille"] <= w["max_total_profit_share_permille"] <= 1000:
        raise WorldError("wages.profit_share-Grenzen ungültig")
    f = cr["founding"]
    if not _is_int(f["capital_min"]) or f["capital_min"] < 1 or not _is_int(f["total_shares"]) or f["total_shares"] < 1:
        raise WorldError("founding ungültig")
    lv = cr["building_levels"]
    if not lv or [x["level"] for x in lv] != list(range(1, len(lv) + 1)) or lv[0]["upgrade_cost"] != 0:
        raise WorldError("building_levels müssen bei 1 beginnen, lückenlos sein und Stufe 1 kostenlos")
    for a, b in zip(lv, lv[1:]):
        if b["max_employees"] <= a["max_employees"] or b["upgrade_cost"] <= 0 or b["storage"] < a["storage"]:
            raise WorldError("building_levels müssen aufsteigend wachsen")
    th = cr["company_level_thresholds"]
    if th[0] != 0 or any(b <= a for a, b in zip(th, th[1:])):
        raise WorldError("company_level_thresholds müssen bei 0 beginnen und streng aufsteigen")
    if len(set(cr["goals"])) != len(cr["goals"]) or not cr["goals"]:
        raise WorldError("goals ungültig")
    wn = cr["warnings"]
    if not 0 < wn["warned_days"] <= wn["intent_days"] <= wn["quit_base_days"]:
        raise WorldError("warnings: warned_days <= intent_days <= quit_base_days erforderlich")
    g = cr["governance"]
    if not 0 < g["decision_threshold_permille"] < 1000 or g["preemption_days"] < 1 or g["vote_days"] < 1:
        raise WorldError("governance ungültig")
    if not 0 <= g["founder_veto_min_permille"] <= 1000 or not 0 <= g["max_employee_equity_permille"] <= 1000:
        raise WorldError("governance: Promille-Werte ungültig")
    if cr["max_catch_up_days"] < 1 or cr["log_limit"] < 1:
        raise WorldError("max_catch_up_days/log_limit ungültig")


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------- reine Regeln ----------
def wage_demand(cr: dict[str, Any], role: str, best_mastery: int) -> int:
    return cr["wages"]["base_by_role"][role] + cr["wages"]["per_mastery"] * best_mastery


def goal_of(cr: dict[str, Any], character_id: str) -> str:
    """Persönliches Ziel (Platzhalter): stabil aus der Figur-ID abgeleitet; die Inhalte sind Content-Aufgabe."""
    return cr["goals"][hashlib.sha256(character_id.encode()).digest()[0] % len(cr["goals"])]


def company_level(cr: dict[str, Any], revenue_total: int) -> int:
    return sum(1 for t in cr["company_level_thresholds"] if revenue_total >= t)


def building(cr: dict[str, Any], level: int) -> dict[str, Any]:
    return cr["building_levels"][level - 1]


def satisfaction_delta(cr: dict[str, Any], *, paid_ratio: int, paid: bool, profit_paid: bool, headcount_permille: int,
                       reputation: int, goal: str, promoted_recently: bool) -> int:
    s = cr["satisfaction"]
    d = _clamp((paid_ratio - 1000) // s["wage_ratio_step"], s["wage_delta_min"], s["wage_delta_max"])
    if goal == "wage":
        d = d * s["wage_goal_numer"] // s["wage_goal_denom"]
    if not paid:
        d -= s["unpaid_penalty"]
    if profit_paid:
        d += s["profit_share_bonus"]
    if headcount_permille > s["crowding_threshold_permille"]:
        d -= s["crowding_penalty"]
    d += reputation // s["reputation_divisor"]
    if goal == "stability" and paid:
        d += s["goal_stability_bonus"]
    if goal == "growth":
        d += s["goal_growth_bonus"] if promoted_recently else -s["goal_growth_penalty"]
    return d


def next_loyalty(cr: dict[str, Any], loyalty: int, satisfaction: int, tenure_days: int) -> int:
    l = cr["loyalty"]
    if satisfaction >= l["high_satisfaction"]:
        loyalty += l["gain"]
    elif satisfaction < l["low_satisfaction"]:
        loyalty -= l["loss"]
    if tenure_days > 0 and tenure_days % l["tenure_bonus_every_days"] == 0:
        loyalty += l["tenure_bonus"]
    return _clamp(loyalty, 0, 1000)


def next_warning_days(cr: dict[str, Any], warning_days: int, satisfaction: int) -> int:
    w = cr["warnings"]
    return warning_days + 1 if satisfaction < w["warn_satisfaction"] else max(0, warning_days - w["decay"])


def employee_status(cr: dict[str, Any], warning_days: int) -> str:
    w = cr["warnings"]
    if warning_days >= w["intent_days"]:
        return "intends_to_resign"
    return "warned" if warning_days >= w["warned_days"] else "ok"


def quits(cr: dict[str, Any], warning_days: int, loyalty: int) -> bool:
    """Kündigung: nach quit_base_days Warntagen, treue Mitarbeiter halten länger durch."""
    w = cr["warnings"]
    return warning_days >= w["quit_base_days"] + loyalty // w["quit_loyalty_divisor"]


def evaluate_offer(cr: dict[str, Any], *, goal: str, demand: int, loyalty: int, satisfaction: int, current_wage: int,
                   offer_wage: int, current_reputation: int, offer_reputation: int, current_level: int,
                   offer_level: int) -> dict[str, Any]:
    """Abwerben: transparente, zufallsfreie Entscheidung aus Lohn, Bedingungen, Ziel, Loyalität und Zufriedenheit."""
    p, s = cr["poaching"], cr["satisfaction"]
    cap = p["max_ratio"]
    gain = min(cap, offer_wage * 1000 // demand) - min(cap, current_wage * 1000 // demand)
    if goal == "wage":
        gain = gain * s["wage_goal_numer"] // s["wage_goal_denom"]
    conditions = (offer_reputation - current_reputation) // p["reputation_divisor"]
    goal_bonus = 0
    if goal == "stability" and offer_reputation > current_reputation:
        goal_bonus = p["stability_bonus"]
    elif goal == "growth" and offer_level > current_level:
        goal_bonus = p["growth_bonus"]
    value = gain + conditions + goal_bonus
    barrier = p["switch_cost"] + loyalty // p["loyalty_divisor"] + satisfaction // p["satisfaction_divisor"]
    return {"accept": value > barrier, "value": value, "barrier": barrier, "wage_gain": gain,
            "conditions": conditions, "goal_bonus": goal_bonus}


def tally(weights: dict[str, int], votes: dict[str, bool], threshold_permille: int, *, veto_holder: str | None) -> str:
    """Abstimmungsstand: 'passed' | 'rejected' | 'pending'. Gewichte sind der Anteilsstand bei Antragstellung."""
    total = sum(weights.values())
    yes = sum(w for h, w in weights.items() if votes.get(h) is True)
    no = sum(w for h, w in weights.items() if votes.get(h) is False)
    if veto_holder is not None and votes.get(veto_holder) is False:
        return "rejected"
    if yes * 1000 > threshold_permille * total and (veto_holder is None or votes.get(veto_holder) is True):
        return "passed"
    if (total - no) * 1000 <= threshold_permille * total:
        return "rejected"  # selbst mit allen offenen Stimmen nicht mehr erreichbar
    return "pending"


# ---------------------------------------------------------------- Register ---------------
class CompanyRegistry:
    """Weltzustand aller Unternehmen (deterministisch, JSON-serialisierbar). Hält Invarianten, trifft keine
    Berechtigungs- oder Geldentscheidungen."""

    def __init__(self, cr: dict[str, Any]) -> None:
        self.cr = cr
        self.companies: dict[str, dict[str, Any]] = {}
        self.employer: dict[str, str] = {}  # Figur -> Unternehmen (höchstens eines)
        self.last_day = 0
        self._counters = {"company": 0}

    # -- Zugriff ---------------------------------------------------------------------
    def get(self, company_id: str) -> dict[str, Any]:
        if not isinstance(company_id, str) or company_id not in self.companies:
            raise WorldError("Unbekanntes Unternehmen")
        return self.companies[company_id]

    def get_open(self, company_id: str) -> dict[str, Any]:
        c = self.get(company_id)
        if not c["open"]:
            raise WorldError("Unternehmen ist geschlossen")
        return c

    def treasury_owner(self, company_id: str) -> str:
        return f"company:{company_id}"

    def next_company_id(self, server_id: str) -> str:
        self._counters["company"] += 1
        return f"{server_id}-co-{self._counters['company']:08d}"

    def total_shares(self, c: dict[str, Any]) -> int:
        return self.cr["founding"]["total_shares"]

    def locked_shares(self, c: dict[str, Any], holder: str) -> int:
        return sum(o["remaining"] for o in c["offers"].values() if o["seller"] == holder and o["remaining"] > 0)

    def free_shares(self, c: dict[str, Any], holder: str) -> int:
        return c["shares"].get(holder, 0) - self.locked_shares(c, holder)

    def level(self, c: dict[str, Any]) -> int:
        return company_level(self.cr, c["revenue_total"])

    # -- Änderungen ---------------------------------------------------------------------
    def create(self, company_id: str, founder: str, day: int) -> dict[str, Any]:
        gov = self.cr["governance"]
        c = {"id": company_id, "founder": founder, "founded_day": day, "open": True, "building_level": 1,
             "reputation": self.cr["reputation"]["initial"], "revenue_total": 0, "revenue_today": 0, "costs_today": 0,
             "ceo": None, "shares": {founder: self.cr["founding"]["total_shares"]}, "employees": {}, "offers": {},
             "proposals": {}, "counters": {"offer": 0, "proposal": 0}, "log": [],
             "constitution": {"decision_threshold_permille": gov["decision_threshold_permille"],
                              "founder_veto": gov["founder_veto"], "founder_veto_min_permille": gov["founder_veto_min_permille"],
                              "preemption_days": gov["preemption_days"], "vote_days": gov["vote_days"]}}
        self.companies[company_id] = c
        return c

    def move_shares(self, c: dict[str, Any], seller: str, buyer: str, qty: int) -> None:
        if qty < 1 or c["shares"].get(seller, 0) < qty:
            raise WorldError("Nicht genug Anteile")
        c["shares"][seller] -= qty
        if c["shares"][seller] == 0:
            del c["shares"][seller]
        c["shares"][buyer] = c["shares"].get(buyer, 0) + qty
        self.check(c)

    def add_employee(self, c: dict[str, Any], character_id: str, emp: dict[str, Any]) -> None:
        if character_id in self.employer:
            raise WorldError("Figur ist bereits angestellt")
        c["employees"][character_id] = emp
        self.employer[character_id] = c["id"]

    def remove_employee(self, c: dict[str, Any], character_id: str) -> dict[str, Any]:
        emp = c["employees"].pop(character_id)
        del self.employer[character_id]
        if c["ceo"] == character_id:
            c["ceo"] = None
        return emp

    def log(self, c: dict[str, Any], day: int, kind: str, **details: Any) -> None:
        c["log"].append({"day": day, "kind": kind, **details})
        del c["log"][:-self.cr["log_limit"]]

    def check(self, c: dict[str, Any]) -> None:
        """Invarianten: Anteile summieren sich zur Gesamtzahl, keine negativen/leeren Bestände."""
        if sum(c["shares"].values()) != self.cr["founding"]["total_shares"] or any(v <= 0 for v in c["shares"].values()):
            raise WorldError("Invariante verletzt: Anteilsbilanz")

    # -- Persistenz ------------------------------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({"last_day": self.last_day, "counters": self._counters, "companies": self.companies,
                           "employer": self.employer}, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, cr: dict[str, Any], text: str) -> "CompanyRegistry":
        data = json.loads(text)
        reg = cls(cr)
        reg.companies, reg.employer, reg.last_day, reg._counters = data["companies"], data["employer"], data["last_day"], data["counters"]
        for c in reg.companies.values():
            reg.check(c)
        return reg


def disclosure(c: dict[str, Any]) -> dict[str, Any]:
    """Was ein Käufer vor dem Kauf sehen muss: Verfassung (Rechte/Beschränkungen), Anteilsverteilung, Geschäftsführer."""
    return {"company_id": c["id"], "constitution": dict(c["constitution"]), "founder": c["founder"], "ceo": c["ceo"],
            "holders": dict(sorted(c["shares"].items())), "open": c["open"]}


def disclosure_hash(c: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(disclosure(c), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
