"""Firmenservice: führt Register, Inventar (Münzen) und CEE-Ereignisse zusammen. Siehe ADR-0012.

Grundsätze: Berechtigungen vor jeder Änderung prüfen; CEE-Ereignisse vorab validieren (Ablehnung ändert nichts);
Münzen nur über das atomare Inventar bewegen; bei Ausfall rückbuchen. Mehrere Ereignisse über verschiedene
Figuren sind nicht atomar (append-only Logs) – das ist eine dokumentierte Grenze (ADR-0012).
"""
from __future__ import annotations

from typing import Any, Callable

from mmo_cee.economy import best_mastery
from mmo_cee.errors import RuleViolation
from mmo_cee.service import CharacterService

from .company import (CompanyRegistry, building, disclosure, disclosure_hash, employee_status, evaluate_offer,
                      goal_of, next_loyalty, next_warning_days, quits, satisfaction_delta, tally, wage_demand,
                      validate_company_rules)
from .errors import WorldError
from .inventory import Inventory, key

CAREER, FOUNDED, CLOSED = "economy.career_changed", "economy.company_founded", "economy.company_closed"
SINK = "world:sink"


class CompanyService:
    def __init__(self, service: CharacterService, inventory: Inventory, registry: CompanyRegistry,
                 day_provider: Callable[[], int], server_id: str = "srv1") -> None:
        validate_company_rules(registry.cr, service.rules)
        self.cee, self.inv, self.reg, self.day, self.server_id = service, inventory, registry, day_provider, server_id
        self.cr = registry.cr
        cur = service.rules["economy"]["currency"]
        self.coin = key(cur["item"], cur["grade"])
        self.roles = service.rules["economy"]["career"]["roles"]
        self.day_hooks: list[Callable[..., Any]] = []  # (Firma, Tag, bezahlt-Karte) -> Ereignisse; z. B. Produktion
        self.close_hooks: list[Callable[[dict[str, Any]], None]] = []  # (Firma) vor der Auszahlung

    # ------------------------------------------------------------------ Hilfen -----------
    def _today(self) -> int:
        d = self.day()
        if not isinstance(d, int) or isinstance(d, bool) or d < 0 or d < self.reg.last_day:
            raise WorldError("Ungültiger oder zurückliegender Tag")
        return d

    def _validate(self, character_id: str, type_: str, payload: dict[str, Any]) -> None:
        try:
            self.cee.projector.validate(self.cee.state(character_id), type_, payload)
        except RuleViolation as e:
            raise WorldError(f"CEE lehnt ab: {e}") from e

    def _career(self, character_id: str) -> dict[str, Any]:
        return self.cee.state(character_id).parts["economy"]["career"]

    def _treasury(self, c: dict[str, Any]) -> str:
        return self.reg.treasury_owner(c["id"])

    def balance(self, company_id: str) -> int:
        return self.inv.balance(self._treasury(self.reg.get(company_id)), self.coin)

    def _controlling(self, c: dict[str, Any], actor: str) -> bool:
        return c["shares"].get(actor, 0) * 1000 > c["constitution"]["decision_threshold_permille"] * self.reg.total_shares(c)

    def _is_owner(self, c: dict[str, Any], actor: str) -> bool:
        if self._controlling(c, actor):
            return True
        return actor == c["founder"] and not any(self._controlling(c, h) for h in c["shares"])

    def can_manage(self, company_id: str, actor: str) -> bool:
        """Verwalten (einstellen/entlassen/Verträge/Beförderung bis Manager): Geschäftsführer oder Eigentümer."""
        c = self.reg.get_open(company_id)
        return actor == c["ceo"] or self._is_owner(c, actor)

    def _need_manage(self, company_id: str, actor: str) -> dict[str, Any]:
        c = self.reg.get_open(company_id)
        if not (actor == c["ceo"] or self._is_owner(c, actor)):
            raise WorldError("Keine Berechtigung (Geschäftsführer oder Eigentümer erforderlich)")
        return c

    def _employee(self, c: dict[str, Any], character_id: str) -> dict[str, Any]:
        if character_id not in c["employees"]:
            raise WorldError("Figur ist hier nicht angestellt")
        return c["employees"][character_id]

    def _pay(self, payer: str, payee: str, amount: int) -> None:
        self.inv.apply_many([(payer, {self.coin: amount}, {}), (payee, {}, {self.coin: amount})])

    def _new_employee(self, character_id: str, wage: int, profit_share: int, day: int) -> dict[str, Any]:
        return {"since_day": day, "wage": wage, "profit_share_permille": profit_share,
                "satisfaction": self.cr["satisfaction"]["initial"], "loyalty": self.cr["loyalty"]["initial"],
                "goal": goal_of(self.cr, character_id), "warning_days": 0, "status": "ok", "promoted_day": None}

    def _check_contract(self, c: dict[str, Any], wage: int, profit_share: int, exclude: str | None = None) -> None:
        w = self.cr["wages"]
        for v in (wage, profit_share):
            if not isinstance(v, int) or isinstance(v, bool):
                raise WorldError("Vertragswerte müssen ganze Zahlen sein")
        if wage < w["min_daily"]:
            raise WorldError(f"Gehalt unter dem Minimum ({w['min_daily']})")
        if not 0 <= profit_share <= w["max_profit_share_permille"]:
            raise WorldError("Gewinnbeteiligung außerhalb der Grenze")
        others = sum(e["profit_share_permille"] for k, e in c["employees"].items() if k != exclude)
        if others + profit_share > w["max_total_profit_share_permille"]:
            raise WorldError("Summe der Gewinnbeteiligungen überschreitet die Grenze")

    # ------------------------------------------------------------------ Gründung / Schließung
    def found(self, founder_id: str, capital: int) -> str:
        day = self._today()
        f = self.cr["founding"]
        if not isinstance(capital, int) or isinstance(capital, bool) or capital < f["capital_min"]:
            raise WorldError(f"Startkapital mindestens {f['capital_min']}")
        if self.inv.balance(founder_id, self.coin) < capital:
            raise WorldError("Gründer besitzt nicht genug Münzen")
        company_id = f"{self.server_id}-co-{self.reg._counters['company'] + 1:08d}"
        payload = {"company_id": company_id, "day": day}
        self._validate(founder_id, FOUNDED, payload)
        treasury = self.reg.treasury_owner(company_id)
        self._pay(founder_id, treasury, capital)
        try:
            self.cee.record(founder_id, FOUNDED, payload)
        except Exception:
            self._pay(treasury, founder_id, capital)
            raise
        self.reg._counters["company"] += 1
        c = self.reg.create(company_id, founder_id, day)
        self.reg.log(c, day, "founded", founder=founder_id, capital=capital)
        return company_id

    def close_company(self, actor: str, company_id: str) -> dict[str, int]:
        """Schließt das Unternehmen: alle Mitarbeiter scheiden aus, die Kasse wird anteilig an die Gesellschafter ausgezahlt."""
        day = self._today()
        c = self.reg.get_open(company_id)
        if not self._is_owner(c, actor):
            raise WorldError("Nur der Eigentümer kann das Unternehmen schließen")
        leaves = [(e, {"company_id": None, "role": None, "day": day}) for e in sorted(c["employees"])]
        for cid, pl in leaves:
            self._validate(cid, CAREER, pl)
        closed = {"company_id": company_id, "day": day}
        self._validate(c["founder"], CLOSED, closed)
        for cid, pl in leaves:
            self.cee.record(cid, CAREER, pl)
            self.reg.remove_employee(c, cid)
        self.cee.record(c["founder"], CLOSED, closed)
        for hook in self.close_hooks:
            hook(c)
        payout: dict[str, int] = {}
        treasury = self._treasury(c)
        bal = self.inv.balance(treasury, self.coin)
        total = self.reg.total_shares(c)
        for holder in sorted(c["shares"]):
            payout[holder] = bal * c["shares"][holder] // total
        payout[c["founder"]] = payout.get(c["founder"], 0) + bal - sum(payout.values())  # Rest (Rundung) an den Gründer
        if bal:
            self.inv.apply_many([(treasury, {self.coin: bal}, {})] + [(h, {}, {self.coin: v}) for h, v in payout.items() if v])
        for o in c["offers"].values():
            o["remaining"] = 0
        for p in c["proposals"].values():
            if p["status"] == "pending":
                p["status"] = "cancelled"
        c["open"] = False
        c["ceo"] = None
        self.reg.log(c, day, "closed", payout=dict(sorted(payout.items())))
        return payout

    # ------------------------------------------------------------------ Mitarbeiter ---------
    def hire(self, actor: str, company_id: str, character_id: str, wage: int, profit_share: int = 0) -> None:
        day = self._today()
        c = self._need_manage(company_id, actor)
        self._check_contract(c, wage, profit_share)
        if character_id in self.reg.employer:
            raise WorldError("Figur ist bereits angestellt")
        if len(c["employees"]) >= building(self.cr, c["building_level"])["max_employees"]:
            raise WorldError("Gebäudekapazität erreicht (Gebäude ausbauen)")
        pl = {"company_id": company_id, "role": self.roles[0], "day": day}
        self._validate(character_id, CAREER, pl)
        self.cee.record(character_id, CAREER, pl)
        self.reg.add_employee(c, character_id, self._new_employee(character_id, wage, profit_share, day))
        self.reg.log(c, day, "hired", character=character_id, wage=wage)

    def _leave(self, c: dict[str, Any], character_id: str, day: int, kind: str) -> None:
        pl = {"company_id": None, "role": None, "day": day}
        self._validate(character_id, CAREER, pl)
        self.cee.record(character_id, CAREER, pl)
        self.reg.remove_employee(c, character_id)
        self.reg.log(c, day, kind, character=character_id)

    def fire(self, actor: str, company_id: str, character_id: str) -> None:
        day = self._today()
        c = self._need_manage(company_id, actor)
        self._employee(c, character_id)
        if character_id == c["ceo"]:
            raise WorldError("Der Geschäftsführer kann nur per Gesellschafterbeschluss abberufen werden")
        self._leave(c, character_id, day, "fired")

    def resign(self, character_id: str, company_id: str) -> None:
        day = self._today()
        c = self.reg.get_open(company_id)
        self._employee(c, character_id)
        self._leave(c, character_id, day, "resigned")

    def set_contract(self, actor: str, company_id: str, character_id: str, wage: int | None = None,
                     profit_share: int | None = None) -> None:
        self._today()
        c = self._need_manage(company_id, actor)
        e = self._employee(c, character_id)
        new_wage = e["wage"] if wage is None else wage
        new_share = e["profit_share_permille"] if profit_share is None else profit_share
        self._check_contract(c, new_wage, new_share, exclude=character_id)
        e["wage"], e["profit_share_permille"] = new_wage, new_share

    def _change_role(self, c: dict[str, Any], character_id: str, new_role: str, day: int) -> None:
        pl = {"company_id": c["id"], "role": new_role, "day": day}
        self._validate(character_id, CAREER, pl)
        self.cee.record(character_id, CAREER, pl)

    def promote(self, actor: str, company_id: str, character_id: str) -> str:
        """Befördert um genau eine Stufe, höchstens bis Manager (Geschäftsführer nur per Gesellschafterbeschluss)."""
        day = self._today()
        c = self._need_manage(company_id, actor)
        e = self._employee(c, character_id)
        idx = self.roles.index(self._career(character_id)["role"])
        if idx + 1 >= len(self.roles) - 1:
            raise WorldError("Weitere Beförderung nur per Gesellschafterbeschluss (Geschäftsführer)")
        self._change_role(c, character_id, self.roles[idx + 1], day)
        e["promoted_day"] = day
        self.reg.log(c, day, "promoted", character=character_id, role=self.roles[idx + 1])
        return self.roles[idx + 1]

    def demote(self, actor: str, company_id: str, character_id: str) -> str:
        day = self._today()
        c = self._need_manage(company_id, actor)
        self._employee(c, character_id)
        if character_id == c["ceo"]:
            raise WorldError("Der Geschäftsführer kann nur per Gesellschafterbeschluss abberufen werden")
        idx = self.roles.index(self._career(character_id)["role"])
        if idx == 0:
            raise WorldError("Bereits auf der untersten Stufe")
        self._change_role(c, character_id, self.roles[idx - 1], day)
        self.reg.log(c, day, "demoted", character=character_id, role=self.roles[idx - 1])
        return self.roles[idx - 1]

    # ------------------------------------------------------------------ Gebäude & Einnahmen --
    def upgrade_building(self, actor: str, company_id: str) -> int:
        day = self._today()
        c = self._need_manage(company_id, actor)
        nxt = c["building_level"] + 1
        if nxt > len(self.cr["building_levels"]):
            raise WorldError("Höchste Gebäudestufe erreicht")
        cost = building(self.cr, nxt)["upgrade_cost"]
        if self.balance(company_id) < cost:
            raise WorldError("Kasse reicht für den Ausbau nicht aus")
        self._pay(self._treasury(c), SINK, cost)  # Münzen verlassen den Kreislauf (Geldsenke), bleiben aber bilanziert
        c["building_level"] = nxt
        self.reg.log(c, day, "building_upgraded", level=nxt, cost=cost)
        return nxt

    def record_revenue(self, company_id: str, amount: int) -> None:
        """Serverinterne Einnahmequelle (später: Märkte/Produktion). Clients können das nie aufrufen."""
        self._today()
        c = self.reg.get_open(company_id)
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
            raise WorldError("Betrag muss eine positive ganze Zahl sein")
        self.inv.deposit(self._treasury(c), self.coin, amount)
        c["revenue_today"] += amount
        c["revenue_total"] += amount

    # ------------------------------------------------------------------ Tagesabschluss -------
    def advance_day(self, day: int) -> list[dict[str, Any]]:
        """Verarbeitet jeden Tag seit dem letzten Abschluss bis einschließlich `day` (begrenzt durch max_catch_up_days)."""
        if not isinstance(day, int) or isinstance(day, bool) or day <= self.reg.last_day:
            raise WorldError("day muss größer als der letzte verarbeitete Tag sein")
        if day - self.reg.last_day > self.cr["max_catch_up_days"]:
            raise WorldError("Zu viele Tage auf einmal")
        events: list[dict[str, Any]] = []
        for d in range(self.reg.last_day + 1, day + 1):
            for cid in sorted(self.reg.companies):
                c = self.reg.companies[cid]
                if c["open"]:
                    events += self._tick(c, d)
            self.reg.last_day = d
        return events

    def _tick(self, c: dict[str, Any], d: int) -> list[dict[str, Any]]:
        cr, out = self.cr, []
        emps = sorted(c["employees"])
        treasury = self._treasury(c)
        paid: dict[str, bool] = {}
        wages = 0
        for e in emps:  # Gehalt in fester Reihenfolge (Figur-ID); reicht die Kasse nicht, bleibt es unbezahlt
            w = c["employees"][e]["wage"]
            paid[e] = self.inv.balance(treasury, self.coin) >= w
            if paid[e]:
                self._pay(treasury, e, w)
                wages += w
        c["costs_today"] += wages
        profit = c["revenue_today"] - c["costs_today"]
        profit_paid: dict[str, bool] = {e: False for e in emps}
        if profit > 0:
            for e in emps:
                share = min(profit * c["employees"][e]["profit_share_permille"] // 1000, self.inv.balance(treasury, self.coin))
                if share > 0 and paid[e]:
                    self._pay(treasury, e, share)
                    profit_paid[e] = True
        for hook in self.day_hooks:
            out += hook(c, d, paid)
        headcount = len(emps) * 1000 // building(cr, c["building_level"])["max_employees"]
        sats = []
        for e in emps:
            emp = c["employees"][e]
            st = self.cee.state(e)
            role = st.parts["economy"]["career"]["role"]
            demand = wage_demand(cr, role, best_mastery(st, self.cee.rules))
            ratio = emp["wage"] * 1000 // demand if paid[e] else 0
            recent = emp["promoted_day"] is not None and d - emp["promoted_day"] < cr["satisfaction"]["growth_window_days"]
            delta = satisfaction_delta(cr, paid_ratio=ratio, paid=paid[e], profit_paid=profit_paid[e],
                                       headcount_permille=headcount, reputation=c["reputation"], goal=emp["goal"],
                                       promoted_recently=recent)
            emp["satisfaction"] = max(0, min(1000, emp["satisfaction"] + delta))
            emp["loyalty"] = next_loyalty(cr, emp["loyalty"], emp["satisfaction"], d - emp["since_day"])
            emp["warning_days"] = next_warning_days(cr, emp["warning_days"], emp["satisfaction"])
            status = employee_status(cr, emp["warning_days"])
            if status != emp["status"]:
                out.append({"day": d, "company": c["id"], "kind": status, "character": e})
                self.reg.log(c, d, status, character=e)
            emp["status"] = status
            sats.append(emp["satisfaction"])
            if quits(cr, emp["warning_days"], emp["loyalty"]):
                out.append({"day": d, "company": c["id"], "kind": "resigned", "character": e})
                self._leave(c, e, d, "resigned")
        rep = cr["reputation"]
        if emps:
            c["reputation"] = max(0, min(1000, c["reputation"] + (rep["paid_gain"] if all(paid.values()) else -rep["unpaid_loss"])
                                         + (rep["happy_gain"] if sats and sum(sats) // len(sats) >= rep["happy_satisfaction"] else 0)))
        c["revenue_today"] = c["costs_today"] = 0
        for p in c["proposals"].values():  # Abstimmungsfrist abgelaufen
            if p["status"] == "pending" and d >= p["deadline"]:
                p["status"] = "expired"
        return out

    # ------------------------------------------------------------------ Abwerben ----------
    def poach(self, actor: str, offering_company: str, character_id: str, offer_wage: int) -> dict[str, Any]:
        """Konkurrenzangebot: deterministische Entscheidung des Mitarbeiters; bei Annahme Wechsel (Austritt + Einstellung)."""
        day = self._today()
        new = self._need_manage(offering_company, actor)
        if character_id not in self.reg.employer:
            raise WorldError("Figur ist nicht angestellt")
        old = self.reg.get(self.reg.employer[character_id])
        if old["id"] == new["id"]:
            raise WorldError("Figur arbeitet bereits hier")
        self._check_contract(new, offer_wage, 0)
        if len(new["employees"]) >= building(self.cr, new["building_level"])["max_employees"]:
            raise WorldError("Gebäudekapazität erreicht (Gebäude ausbauen)")
        emp = old["employees"][character_id]
        st = self.cee.state(character_id)
        demand = wage_demand(self.cr, st.parts["economy"]["career"]["role"], best_mastery(st, self.cee.rules))
        res = evaluate_offer(self.cr, goal=emp["goal"], demand=demand, loyalty=emp["loyalty"], satisfaction=emp["satisfaction"],
                             current_wage=emp["wage"], offer_wage=offer_wage, current_reputation=old["reputation"],
                             offer_reputation=new["reputation"], current_level=self.reg.level(old), offer_level=self.reg.level(new))
        if not res["accept"]:
            self.reg.log(new, day, "offer_declined", character=character_id, **{k: v for k, v in res.items() if k != "accept"})
            return res
        if character_id == old["ceo"]:
            raise WorldError("Der Geschäftsführer kann nicht abgeworben werden (erst abberufen)")
        self._leave(old, character_id, day, "poached_away")
        pl = {"company_id": new["id"], "role": self.roles[0], "day": day}
        self._validate(character_id, CAREER, pl)
        self.cee.record(character_id, CAREER, pl)
        self.reg.add_employee(new, character_id, self._new_employee(character_id, offer_wage, 0, day))
        self.reg.log(new, day, "poached", character=character_id, wage=offer_wage)
        return res

    # ------------------------------------------------------------------ Anteile -------------
    def disclosure(self, company_id: str) -> dict[str, Any]:
        c = self.reg.get(company_id)
        return {**disclosure(c), "hash": disclosure_hash(c)}

    def offer_shares(self, seller: str, company_id: str, qty: int, price_per_share: int) -> str:
        day = self._today()
        c = self.reg.get_open(company_id)
        for v in (qty, price_per_share):
            if not isinstance(v, int) or isinstance(v, bool) or v < 1:
                raise WorldError("Menge und Preis müssen positive ganze Zahlen sein")
        if self.reg.free_shares(c, seller) < qty:
            raise WorldError("Nicht genug freie Anteile")
        c["counters"]["offer"] += 1
        oid = f"{company_id}-offer-{c['counters']['offer']}"
        c["offers"][oid] = {"seller": seller, "qty": qty, "remaining": qty, "price": price_per_share, "day": day,
                            "deadline": day + c["constitution"]["preemption_days"]}
        self.reg.log(c, day, "shares_offered", seller=seller, qty=qty, price=price_per_share)
        return oid

    def _offer(self, c: dict[str, Any], offer_id: str) -> dict[str, Any]:
        o = c["offers"].get(offer_id)
        if o is None or o["remaining"] <= 0:
            raise WorldError("Angebot unbekannt oder erledigt")
        return o

    def _settle(self, c: dict[str, Any], o: dict[str, Any], buyer: str, qty: int) -> None:
        if not isinstance(qty, int) or isinstance(qty, bool) or not 1 <= qty <= o["remaining"]:
            raise WorldError("Ungültige Menge")
        price = qty * o["price"]
        if self.inv.balance(buyer, self.coin) < price:
            raise WorldError("Käufer besitzt nicht genug Münzen")
        self._pay(buyer, o["seller"], price)
        try:
            o["remaining"] -= qty  # gesperrte Anteile freigeben, dann übertragen
            self.reg.move_shares(c, o["seller"], buyer, qty)
        except Exception:
            o["remaining"] += qty
            self._pay(o["seller"], buyer, price)
            raise

    def preempt(self, holder: str, company_id: str, offer_id: str, qty: int) -> None:
        """Vorkaufsrecht: nur bestehende Gesellschafter, nur innerhalb der Frist, zum Angebotspreis."""
        day = self._today()
        c = self.reg.get_open(company_id)
        o = self._offer(c, offer_id)
        if day >= o["deadline"]:
            raise WorldError("Die Vorkaufsfrist ist abgelaufen")
        if holder == o["seller"] or c["shares"].get(holder, 0) < 1:
            raise WorldError("Nur bestehende Gesellschafter (außer dem Verkäufer) haben ein Vorkaufsrecht")
        self._settle(c, o, holder, qty)
        self.reg.log(c, day, "shares_preempted", holder=holder, qty=qty)

    def purchase(self, buyer: str, company_id: str, offer_id: str, qty: int, disclosure_hash_ack: str) -> None:
        """Kauf durch beliebige Käufer nach Ablauf der Vorkaufsfrist; der Käufer muss die aktuelle Offenlegung bestätigen."""
        day = self._today()
        c = self.reg.get_open(company_id)
        o = self._offer(c, offer_id)
        if day < o["deadline"]:
            raise WorldError("Die Vorkaufsfrist läuft noch")
        if buyer == o["seller"]:
            raise WorldError("Käufer und Verkäufer müssen verschieden sein")
        if disclosure_hash_ack != disclosure_hash(c):
            raise WorldError("Offenlegung nicht (aktuell) bestätigt: Rechte und Beschränkungen vor dem Kauf einsehen")
        self._settle(c, o, buyer, qty)
        self.reg.log(c, day, "shares_purchased", buyer=buyer, qty=qty)

    def withdraw_offer(self, seller: str, company_id: str, offer_id: str) -> None:
        c = self.reg.get_open(company_id)
        o = self._offer(c, offer_id)
        if o["seller"] != seller:
            raise WorldError("Nur der Verkäufer kann sein Angebot zurückziehen")
        o["remaining"] = 0

    def grant_equity(self, grantor: str, company_id: str, employee_id: str, qty: int) -> None:
        """Mitarbeiterbeteiligung als Vergütung: Schenkung eigener freier Anteile an Angestellte (mit Obergrenze je Person)."""
        day = self._today()
        c = self.reg.get_open(company_id)
        self._employee(c, employee_id)
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1 or self.reg.free_shares(c, grantor) < qty:
            raise WorldError("Ungültige Menge oder nicht genug freie Anteile")
        cap = self.cr["governance"]["max_employee_equity_permille"] * self.reg.total_shares(c) // 1000
        if c["shares"].get(employee_id, 0) + qty > cap:
            raise WorldError(f"Mitarbeiterbeteiligung ist auf {cap} Anteile je Person begrenzt")
        self.reg.move_shares(c, grantor, employee_id, qty)
        self.reg.log(c, day, "equity_granted", grantor=grantor, employee=employee_id, qty=qty)

    # ------------------------------------------------------------------ Gesellschafterbeschlüsse
    def propose(self, proposer: str, company_id: str, kind: str, candidate: str | None = None) -> str:
        day = self._today()
        c = self.reg.get_open(company_id)
        if c["shares"].get(proposer, 0) < 1:
            raise WorldError("Nur Gesellschafter können Anträge stellen")
        if kind == "appoint_ceo":
            if c["ceo"] is not None:
                raise WorldError("Es gibt bereits einen Geschäftsführer")
            self._employee(c, candidate)
            if self._career(candidate)["role"] != self.roles[-2]:
                raise WorldError(f"Kandidat muss die Stufe {self.roles[-2]!r} haben")
        elif kind == "dismiss_ceo":
            if c["ceo"] is None:
                raise WorldError("Es gibt keinen Geschäftsführer")
            candidate = c["ceo"]
        else:
            raise WorldError("Unbekannte Antragsart")
        if any(p["status"] == "pending" and p["kind"] == kind for p in c["proposals"].values()):
            raise WorldError("Es läuft bereits ein Antrag dieser Art")
        con, total = c["constitution"], self.reg.total_shares(c)
        veto = c["founder"] if con["founder_veto"] and c["shares"].get(c["founder"], 0) * 1000 >= con["founder_veto_min_permille"] * total else None
        c["counters"]["proposal"] += 1
        pid = f"{company_id}-prop-{c['counters']['proposal']}"
        c["proposals"][pid] = {"kind": kind, "candidate": candidate, "proposer": proposer, "day": day,
                               "deadline": day + con["vote_days"], "weights": dict(sorted(c["shares"].items())),
                               "votes": {}, "veto_holder": veto, "status": "pending", "result": None}
        return pid

    def vote(self, voter: str, company_id: str, proposal_id: str, yes: bool) -> str:
        day = self._today()
        c = self.reg.get_open(company_id)
        p = c["proposals"].get(proposal_id)
        if p is None or p["status"] != "pending":
            raise WorldError("Antrag unbekannt oder nicht mehr offen")
        if day >= p["deadline"]:
            p["status"] = "expired"
            raise WorldError("Die Abstimmungsfrist ist abgelaufen")
        if voter not in p["weights"]:
            raise WorldError("Nur Gesellschafter zum Zeitpunkt des Antrags dürfen abstimmen")
        if voter in p["votes"] or not isinstance(yes, bool):
            raise WorldError("Stimme bereits abgegeben oder ungültig")
        p["votes"][voter] = yes
        state = tally(p["weights"], p["votes"], c["constitution"]["decision_threshold_permille"], veto_holder=p["veto_holder"])
        if state == "rejected":
            p["status"] = "rejected"
        elif state == "passed":
            self._execute(c, p, day)
        return p["status"]

    def _execute(self, c: dict[str, Any], p: dict[str, Any], day: int) -> None:
        try:
            if p["kind"] == "appoint_ceo":
                self._change_role(c, p["candidate"], self.roles[-1], day)
                c["ceo"] = p["candidate"]
            else:
                self._change_role(c, p["candidate"], self.roles[-2], day)
                c["ceo"] = None
        except WorldError as e:
            p["status"], p["result"] = "execution_failed", str(e)
            self.reg.log(c, day, "proposal_failed", proposal=p["kind"], reason=str(e))
            return
        p["status"] = "passed"
        self.reg.log(c, day, p["kind"], candidate=p["candidate"])
