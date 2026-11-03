import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.rules import load_rules
from mmo_world import CompanyRegistry, CompanyService, Inventory, WorldError, load_company_rules
from mmo_world.company import disclosure_hash, goal_of

RULES = load_rules("rules_v7.json")
CR = load_company_rules()
COIN = "coin@gold"
CAREER = "economy.career_changed"


def id_with_goal(goal, prefix="e"):
    i = 0
    while goal_of(CR, f"{prefix}{i}") != goal:
        i += 1
    return f"{prefix}{i}"


class CWorld:
    def __init__(self):
        self.svc = CharacterService(rules=RULES)
        self.inv = Inventory()
        self.reg = CompanyRegistry(CR)
        self.day = [1]
        self.cs = CompanyService(self.svc, self.inv, self.reg, lambda: self.day[0])
        self.minted = 0

    def char(self, cid, kind="player", xp=10000, coins=0, **prof):
        self.svc.create(cid, kind)
        self.svc.record(cid, "identity.xp_gained", {"amount": xp})
        for p, x in prof.items():
            self.svc.record(cid, "profession.work", {"profession": p, "xp": x})
        if coins:
            self.give(cid, coins)

    def give(self, owner, coins):
        self.inv.deposit(owner, COIN, coins)
        self.minted += coins

    def founder(self, cid="boss", coins=20000):
        self.char(cid, coins=coins, trade=700)

    def company(self, founder="boss", capital=5000, coins=20000):
        if founder not in [e for e in self.svc.log._events]:
            self.founder(founder, coins)
        return self.cs.found(founder, capital)

    def goto(self, day):
        self.day[0] = day
        return self.cs.advance_day(day)

    def career(self, cid):
        return self.svc.state(cid).parts["economy"]["career"]

    def coins(self, owner):
        return self.inv.balance(owner, COIN)

    def total_coins(self):
        return sum(self.inv.balance(o, COIN) for o in list(self.inv._stacks))


def make_manager(w, cid, company_id, hired_day=1):
    """Fixture: bringt eine Figur direkt in der CEE bis 'manager' (alle Gates erfüllt) und trägt sie im Register ein.
    Gibt den ersten Tag zurück, an dem sie die Voraussetzungen für 'executive' erfüllt (Dienstzeit 30 Tage)."""
    w.char(cid, trade=48000)
    rec = w.svc.record
    d = hired_day
    rec(cid, CAREER, {"company_id": company_id, "role": "employee", "day": d})
    rec(cid, CAREER, {"company_id": company_id, "role": "specialist", "day": d + 7})
    rec(cid, CAREER, {"company_id": company_id, "role": "department_head", "day": d + 21})
    big = {"item_id": "iron_blade", "grade": "masterwork", "quantity": 100, "value": 30000, "role": "seller"}
    rec(cid, "economy.trade_completed", {**big, "trade_id": "fx0", "counterparty": "market-0", "day": d + 21})
    rec(cid, CAREER, {"company_id": company_id, "role": "manager", "day": d + 42})
    for i in range(1, 6):  # Volumen >= 10000 und Netzwerk >= 1000 für die Geschäftsführung
        rec(cid, "economy.trade_completed", {**big, "trade_id": f"fx{i}", "counterparty": f"market-{i}", "day": d + 42 + i})
    c = w.reg.get(company_id)
    w.reg.add_employee(c, cid, w.cs._new_employee(cid, 100, 0, d + 42))
    return d + 42 + 30


class FoundTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.w.founder()

    def test_found_success(self):
        cid = self.w.cs.found("boss", 5000)
        c = self.w.reg.get(cid)
        self.assertEqual((cid, self.w.cs.balance(cid), self.w.coins("boss")), ("srv1-co-00000001", 5000, 15000))
        self.assertEqual((c["shares"], c["founder"], c["building_level"], c["open"]), ({"boss": 1000}, "boss", 1, True))
        self.assertEqual(self.w.svc.state("boss").parts["economy"]["founded"][cid]["open"], True)
        self.assertEqual(c["log"][0]["kind"], "founded")

    def test_failures_change_nothing(self):
        before = (self.w.inv.to_json(), len(self.w.svc.log.events("boss")), self.w.reg.to_json())
        for capital in (999, 0, -5, True, 5000.5, "5000", 10**9):
            with self.subTest(capital=capital):
                with self.assertRaises(WorldError):
                    self.w.cs.found("boss", capital)
        self.w.char("low", xp=100, coins=5000, trade=700)  # Stufe zu niedrig für die Gründung
        self.w.char("unskilled", coins=5000)  # Meisterschaft fehlt
        for cid in ("low", "unskilled"):
            with self.assertRaisesRegex(WorldError, "CEE lehnt ab"):
                self.w.cs.found(cid, 2000)
        with self.assertRaises(WorldError):
            self.w.cs.found("ghost", 2000)
        self.assertEqual((self.w.inv.to_json(), len(self.w.svc.log.events("boss")), self.w.reg.to_json())[1:], before[1:])
        self.assertEqual(self.w.coins("low"), 5000)

    def test_cee_limit_of_open_companies(self):
        for _ in range(3):
            self.w.cs.found("boss", 1000)
        before = self.w.inv.to_json()
        with self.assertRaisesRegex(WorldError, "CEE lehnt ab"):
            self.w.cs.found("boss", 1000)
        self.assertEqual(self.w.inv.to_json(), before)

    def test_rollback_when_recording_fails(self):
        before = (self.w.inv.to_json(), self.w.reg._counters["company"])
        original = self.w.svc.record
        self.w.svc.record = lambda *a, **k: (_ for _ in ()).throw(RuleViolation("Ausfall"))
        with self.assertRaises(RuleViolation):
            self.w.cs.found("boss", 3000)
        self.w.svc.record = original
        self.assertEqual((self.w.inv.to_json(), self.w.reg._counters["company"], self.w.reg.companies), (before[0], before[1], {}))

    def test_ids_are_sequential(self):
        ids = [self.w.cs.found("boss", 1000) for _ in range(3)]
        self.assertEqual(ids, [f"srv1-co-0000000{i}" for i in (1, 2, 3)])

    def test_past_day_is_rejected(self):
        self.w.cs.found("boss", 1000)
        self.w.goto(5)
        self.w.day[0] = 3
        with self.assertRaises(WorldError):
            self.w.cs.found("boss", 1000)


class HireTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.cid = self.w.company()
        self.w.char("w1")
        self.w.char("w2")

    def test_hire_success_and_defaults(self):
        self.w.cs.hire("boss", self.cid, "w1", 30, 100)
        e = self.w.reg.get(self.cid)["employees"]["w1"]
        self.assertEqual((e["wage"], e["profit_share_permille"], e["satisfaction"], e["loyalty"], e["status"], e["since_day"]),
                         (30, 100, 600, 300, "ok", 1))
        self.assertEqual(e["goal"], goal_of(CR, "w1"))
        self.assertEqual((self.w.career("w1")["company_id"], self.w.career("w1")["role"]), (self.cid, "employee"))
        self.assertEqual(self.w.reg.employer, {"w1": self.cid})

    def test_permissions(self):
        for actor in ("w2", "stranger"):
            with self.assertRaisesRegex(WorldError, "Berechtigung"):
                self.w.cs.hire(actor, self.cid, "w1", 30)
        self.assertEqual(self.w.reg.get(self.cid)["employees"], {})

    def test_contract_validation(self):
        for wage, share in ((4, 0), (0, 0), (-5, 0), (30, 301), (30, -1), (True, 0), (30, True), (30.5, 0), ("30", 0), (30, "5")):
            with self.subTest(wage=wage, share=share):
                with self.assertRaises(WorldError):
                    self.w.cs.hire("boss", self.cid, "w1", wage, share)
        for i in range(2):  # Summe der Gewinnbeteiligungen <= 500
            self.w.char(f"p{i}")
            self.w.cs.hire("boss", self.cid, f"p{i}", 30, 250)
        with self.assertRaisesRegex(WorldError, "Summe"):
            self.w.cs.hire("boss", self.cid, "w1", 30, 1)

    def test_capacity_and_upgrade(self):
        for i in range(5):
            self.w.char(f"c{i}")
            self.w.cs.hire("boss", self.cid, f"c{i}", 30)
        with self.assertRaisesRegex(WorldError, "Gebäudekapazität"):
            self.w.cs.hire("boss", self.cid, "w1", 30)
        self.w.cs.upgrade_building("boss", self.cid)  # Kasse 5000 genügt für Stufe 2 (5000)
        self.w.cs.hire("boss", self.cid, "w1", 30)
        self.assertEqual(len(self.w.reg.get(self.cid)["employees"]), 6)

    def test_already_employed_and_unknown(self):
        self.w.cs.hire("boss", self.cid, "w1", 30)
        with self.assertRaisesRegex(WorldError, "bereits angestellt"):
            self.w.cs.hire("boss", self.cid, "w1", 30)
        other = self.w.cs.found("boss", 1000)
        with self.assertRaisesRegex(WorldError, "bereits angestellt"):
            self.w.cs.hire("boss", other, "w1", 30)
        before = self.w.reg.to_json()
        with self.assertRaisesRegex(WorldError, "CEE lehnt ab"):
            self.w.cs.hire("boss", self.cid, "ghost", 30)
        self.assertEqual(self.w.reg.to_json(), before)

    def test_npc_hire_and_closed_company(self):
        self.w.char("npc1", kind="npc")
        self.w.cs.hire("boss", self.cid, "npc1", 25)
        self.assertEqual(self.w.svc.state("npc1").parts["identity"]["kind"], "npc")
        self.w.cs.close_company("boss", self.cid)
        with self.assertRaisesRegex(WorldError, "geschlossen"):
            self.w.cs.hire("boss", self.cid, "w1", 30)


class FireResignContractTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.cid = self.w.company()
        for c in ("w1", "w2"):
            self.w.char(c)
            self.w.cs.hire("boss", self.cid, c, 30, 100)

    def test_fire_and_resign_record_leave_events_and_free_the_character(self):
        self.w.cs.fire("boss", self.cid, "w1")
        self.assertEqual((self.w.career("w1")["role"], self.w.reg.employer), (None, {"w2": self.cid}))
        self.w.cs.resign("w2", self.cid)
        self.assertEqual((self.w.career("w2")["role"], self.w.reg.employer), (None, {}))
        kinds = [x["kind"] for x in self.w.reg.get(self.cid)["log"]]
        self.assertEqual(kinds[-2:], ["fired", "resigned"])
        other = self.w.cs.found("boss", 1000)
        self.w.cs.hire("boss", other, "w1", 30)  # wieder einstellbar

    def test_unauthorized_and_unknown(self):
        with self.assertRaises(WorldError):
            self.w.cs.fire("w2", self.cid, "w1")
        with self.assertRaises(WorldError):
            self.w.cs.fire("boss", self.cid, "nobody")
        with self.assertRaises(WorldError):
            self.w.cs.resign("nobody", self.cid)

    def test_set_contract(self):
        self.w.cs.set_contract("boss", self.cid, "w1", wage=45)
        self.w.cs.set_contract("boss", self.cid, "w1", profit_share=250)
        e = self.w.reg.get(self.cid)["employees"]["w1"]
        self.assertEqual((e["wage"], e["profit_share_permille"]), (45, 250))
        self.w.cs.set_contract("boss", self.cid, "w1", profit_share=300)  # eigene Beteiligung zählt nicht doppelt (100 + 300 <= 500)
        with self.assertRaisesRegex(WorldError, "Summe"):
            self.w.cs.set_contract("boss", self.cid, "w2", profit_share=300)  # 300 + 300 > 500
        for kw in ({"wage": 1}, {"profit_share": 999}, {"wage": True}, {"wage": 3.5}):
            with self.assertRaises(WorldError):
                self.w.cs.set_contract("boss", self.cid, "w1", **kw)
        with self.assertRaises(WorldError):
            self.w.cs.set_contract("w2", self.cid, "w1", wage=50)


class PromoteTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.cid = self.w.company()
        self.w.char("w1", trade=3000)  # Meisterschaft 5
        self.w.cs.hire("boss", self.cid, "w1", 40)

    def test_promotion_gates_are_enforced_by_the_cee(self):
        with self.assertRaisesRegex(WorldError, "Dienstzeit|tenure"):
            self.w.cs.promote("boss", self.cid, "w1")  # Dienstzeit 0 < 7
        self.w.goto(8)
        self.assertEqual(self.w.cs.promote("boss", self.cid, "w1"), "specialist")
        self.assertEqual(self.w.reg.get(self.cid)["employees"]["w1"]["promoted_day"], 8)
        with self.assertRaises(WorldError):
            self.w.cs.promote("boss", self.cid, "w1")  # department_head braucht 14 Tage
        self.w.goto(22)
        self.assertEqual(self.w.cs.promote("boss", self.cid, "w1"), "department_head")
        self.assertEqual(self.w.career("w1")["role"], "department_head")

    def test_no_executive_by_promotion_and_permissions(self):
        with self.assertRaises(WorldError):
            self.w.cs.promote("w1", self.cid, "w1")  # ein Mitarbeiter darf nicht befördern
        self.assertIsNone(self.w.reg.get(self.cid)["employees"]["w1"]["promoted_day"])
        ready = make_manager(self.w, "m1", self.cid, hired_day=1)
        self.w.day[0] = ready
        with self.assertRaisesRegex(WorldError, "Gesellschafterbeschluss"):
            self.w.cs.promote("boss", self.cid, "m1")  # Geschäftsführer nur per Beschluss
        self.assertEqual(self.w.career("m1")["role"], "manager")

    def test_demote_and_bounds(self):
        self.w.goto(8)
        self.w.cs.promote("boss", self.cid, "w1")
        self.assertEqual(self.w.cs.demote("boss", self.cid, "w1"), "employee")
        with self.assertRaisesRegex(WorldError, "untersten"):
            self.w.cs.demote("boss", self.cid, "w1")

    def test_promotion_raises_demand_and_creates_pressure(self):
        self.w.goto(8)
        self.w.cs.promote("boss", self.cid, "w1")
        st = self.w.svc.state("w1")
        from mmo_cee.economy import best_mastery
        from mmo_world.company import wage_demand
        self.assertEqual(wage_demand(CR, "specialist", best_mastery(st, RULES)), 40 + 3 * 5)  # Anspruch 55 > Lohn 40


class BuildingRevenueTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.cid = self.w.company(capital=30000, coins=40000)

    def test_upgrade_costs_go_to_the_sink_and_levels_are_limited(self):
        self.assertEqual(self.w.cs.upgrade_building("boss", self.cid), 2)
        self.assertEqual((self.w.cs.balance(self.cid), self.w.coins("world:sink")), (25000, 5000))
        self.assertEqual(self.w.cs.upgrade_building("boss", self.cid), 3)
        self.assertEqual(self.w.cs.balance(self.cid), 5000)
        with self.assertRaisesRegex(WorldError, "Höchste"):
            self.w.cs.upgrade_building("boss", self.cid)
        self.assertEqual(self.w.total_coins(), self.w.minted)  # Münzen gehen nur in die Senke, nicht verloren

    def test_upgrade_needs_money_and_rights(self):
        poor = CWorld()
        pid = poor.company(capital=1000)
        with self.assertRaisesRegex(WorldError, "Kasse"):
            poor.cs.upgrade_building("boss", pid)
        with self.assertRaises(WorldError):
            self.w.cs.upgrade_building("stranger", self.cid)

    def test_revenue_levels_and_validation(self):
        self.w.cs.record_revenue(self.cid, 10000)
        c = self.w.reg.get(self.cid)
        self.assertEqual((c["revenue_total"], c["revenue_today"], self.w.reg.level(c)), (10000, 10000, 2))
        self.assertEqual(self.w.cs.balance(self.cid), 40000)
        for bad in (0, -1, True, 1.5, "5"):
            with self.assertRaises(WorldError):
                self.w.cs.record_revenue(self.cid, bad)
        self.w.cs.record_revenue(self.cid, 40000)
        self.assertEqual(self.w.reg.level(c), 3)  # Unternehmens- und Gebäudelevel sind getrennte Systeme
        self.assertEqual(c["building_level"], 1)


class PayrollTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.cid = self.w.company(capital=1000)

    def hire(self, cid, wage, share=0, goal=None):
        self.w.char(cid)
        self.w.cs.hire("boss", self.cid, cid, wage, share)

    def test_exact_payroll(self):
        self.hire("a", 30)
        self.hire("b", 50)
        self.w.goto(1)
        self.assertEqual((self.w.coins("a"), self.w.coins("b"), self.w.cs.balance(self.cid)), (30, 50, 920))
        self.w.goto(2)
        self.assertEqual((self.w.coins("a"), self.w.coins("b"), self.w.cs.balance(self.cid)), (60, 100, 840))

    def test_unpaid_when_the_treasury_runs_out_in_id_order(self):
        for cid, wage in (("a", 600), ("b", 600)):
            self.hire(cid, wage)
        self.w.goto(1)
        self.assertEqual((self.w.coins("a"), self.w.coins("b"), self.w.cs.balance(self.cid)), (600, 0, 400))
        self.assertEqual(self.w.reg.get(self.cid)["reputation"], 500 - 25)  # nicht alle bezahlt
        self.assertLess(self.w.reg.get(self.cid)["employees"]["b"]["satisfaction"], self.w.reg.get(self.cid)["employees"]["a"]["satisfaction"])

    def test_profit_share_is_paid_from_the_day_profit(self):
        self.hire("a", 30, 200)
        self.hire("b", 50, 0)
        self.w.cs.record_revenue(self.cid, 1000)
        self.w.goto(1)
        # Gewinn = 1000 - (30 + 50) = 920; a erhält 20 % = 184 zusätzlich
        self.assertEqual((self.w.coins("a"), self.w.coins("b")), (30 + 184, 50))
        self.assertEqual(self.w.cs.balance(self.cid), 1000 + 1000 - 80 - 184)
        c = self.w.reg.get(self.cid)
        self.assertEqual((c["revenue_today"], c["costs_today"], c["revenue_total"]), (0, 0, 1000))
        self.w.goto(2)  # kein Umsatz -> kein Gewinn -> keine Beteiligung
        self.assertEqual(self.w.coins("a"), 30 + 184 + 30)

    def test_no_profit_share_without_profit_or_when_unpaid(self):
        self.hire("a", 30, 300)
        self.w.cs.record_revenue(self.cid, 20)  # Umsatz 20 < Lohn 30 -> kein Gewinn
        self.w.goto(1)
        self.assertEqual(self.w.coins("a"), 30)

    def test_unpaid_employee_gets_no_profit_share(self):
        self.hire("broke", 100_000, 300)  # Gehalt unbezahlbar, Gewinnbeteiligung vereinbart
        self.hire("fine", 30, 0)
        self.w.cs.record_revenue(self.cid, 500)  # Gewinn 500 - 30 = 470 > 0
        self.w.goto(1)
        self.assertEqual((self.w.coins("broke"), self.w.coins("fine")), (0, 30))  # kein Gehalt, deshalb auch keine Beteiligung

    def test_satisfaction_and_loyalty_progression_for_a_stable_employee(self):
        eid = id_with_goal("stability")
        self.hire(eid, 20)  # Anspruch 20 (Mitarbeiter, Meisterschaft 0) -> Lohnverhältnis 1000
        sats, loys = [], []
        for d in (1, 2, 3):
            self.w.goto(d)
            e = self.w.reg.get(self.cid)["employees"][eid]
            sats.append(e["satisfaction"])
            loys.append(e["loyalty"])
        self.assertEqual(sats, [605, 610, 615])  # +0 (Lohn) +2 (Ruf 500..) +3 (Stabilitätsziel)
        self.assertEqual(loys, [302, 304, 306])
        self.assertEqual(self.w.reg.get(self.cid)["reputation"], 500 + 3 * 3)  # +2 bezahlt, +1 zufrieden je Tag

    def test_unpaid_employee_warns_then_resigns_with_cee_leave(self):
        eid = id_with_goal("stability")
        self.hire(eid, 100_000)  # unbezahlbar: jeden Tag unbezahlt
        log = []
        quit_day = None
        for d in range(1, 25):
            ev = self.w.goto(d)
            log += ev
            if eid not in self.w.reg.get(self.cid)["employees"]:
                quit_day = d
                break
            e = self.w.reg.get(self.cid)["employees"][eid]
            if d == 1:
                self.assertEqual((e["satisfaction"], e["warning_days"]), (600 - 40 - 30 + 2, 0))  # 532
            if d == 5:
                self.assertEqual(e["status"], "warned")
            if d == 9:
                self.assertEqual((e["status"], e["satisfaction"]), ("intends_to_resign", 0))
        self.assertEqual(quit_day, 14)
        self.assertEqual([x["kind"] for x in log], ["warned", "intends_to_resign", "resigned"])
        self.assertEqual((self.w.career(eid)["role"], self.w.reg.employer), (None, {}))  # CEE-Austritt + Register konsistent
        self.assertEqual(self.w.reg.get(self.cid)["log"][-1]["kind"], "resigned")
        self.assertLess(self.w.reg.get(self.cid)["reputation"], 500)  # unbezahlte Löhne kosten Ruf

    def test_loyal_employee_resists_longer(self):
        a, b = id_with_goal("stability", "x"), id_with_goal("stability", "y")
        for e in (a, b):
            self.hire(e, 100_000)  # beide unbezahlbar
        self.w.reg.get(self.cid)["employees"][b]["loyalty"] = 900  # b ist deutlich loyaler
        quit_day = {}
        for d in range(1, 60):
            self.w.goto(d)
            for e in (a, b):
                if e not in self.w.reg.get(self.cid)["employees"] and e not in quit_day:
                    quit_day[e] = d
        self.assertEqual(set(quit_day), {a, b})
        self.assertLess(quit_day[a], quit_day[b])  # Hürde 10 + loyalty//100: loyale Mitarbeiter halten länger durch

    def test_catch_up_and_day_rules(self):
        self.hire("a", 30)
        self.w.goto(5)
        self.assertEqual(self.w.coins("a"), 150)  # Tage 1..5 nachgeholt
        for bad in (5, 3, 0, -1, True, 1.5):
            with self.assertRaises(WorldError):
                self.w.cs.advance_day(bad)
        with self.assertRaisesRegex(WorldError, "Zu viele"):
            self.w.cs.advance_day(5 + CR["max_catch_up_days"] + 1)
        self.w.cs.advance_day(5 + CR["max_catch_up_days"])
        self.assertEqual(self.w.reg.last_day, 35)

    def test_closed_companies_are_not_processed(self):
        self.hire("a", 30)
        self.w.cs.close_company("boss", self.cid)
        before = self.w.inv.to_json()
        self.w.goto(3)
        self.assertEqual(self.w.inv.to_json(), before)

    def test_reputation_grows_and_is_clamped(self):
        eid = id_with_goal("stability")
        self.hire(eid, 20)
        for d in range(1, 30):
            self.w.goto(d)
        c = self.w.reg.get(self.cid)
        self.assertEqual(c["reputation"], 500 + 29 * 3)  # je Tag +2 (alle bezahlt) +1 (zufrieden)
        c["reputation"] = 999
        self.w.goto(30)
        self.assertEqual(c["reputation"], 1000)


class PoachTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.a = self.w.company("boss", capital=3000)
        self.w.founder("rival")
        self.b = self.w.cs.found("rival", 3000)
        self.emp = id_with_goal("wage")
        self.w.char(self.emp)
        self.w.cs.hire("boss", self.a, self.emp, 20)  # Anspruch 20

    def test_decline_changes_nothing_but_is_logged(self):
        before = self.w.reg.employer.copy()
        res = self.w.cs.poach("rival", self.b, self.emp, 22)  # 100 Promille Vorsprung x 1,5 = 150 < Hürde
        self.assertFalse(res["accept"])
        self.assertEqual((self.w.reg.employer, self.w.career(self.emp)["company_id"]), (before, self.a))
        self.assertEqual(self.w.reg.get(self.b)["log"][-1]["kind"], "offer_declined")

    def test_accept_switches_company_with_both_cee_events(self):
        res = self.w.cs.poach("rival", self.b, self.emp, 30)  # 500 x 1,5 = 750 > Hürde (100 + 150 + 150)
        self.assertTrue(res["accept"])
        self.assertEqual((res["wage_gain"], res["barrier"]), (750, 100 + 300 // 2 + 600 // 4))
        self.assertEqual((self.w.career(self.emp)["company_id"], self.w.career(self.emp)["role"]), (self.b, "employee"))
        self.assertEqual(self.w.reg.employer, {self.emp: self.b})
        self.assertNotIn(self.emp, self.w.reg.get(self.a)["employees"])
        new = self.w.reg.get(self.b)["employees"][self.emp]
        self.assertEqual((new["wage"], new["satisfaction"], new["loyalty"], new["profit_share_permille"]), (30, 600, 300, 0))
        self.assertEqual([x["kind"] for x in self.w.reg.get(self.a)["log"]][-1], "poached_away")
        self.assertEqual(self.w.reg.get(self.b)["log"][-1]["kind"], "poached")

    def test_validations(self):
        with self.assertRaises(WorldError):
            self.w.cs.poach("boss", self.a, self.emp, 30)  # gleiche Firma
        with self.assertRaises(WorldError):
            self.w.cs.poach("boss", self.b, self.emp, 30)  # keine Berechtigung im Angebotsunternehmen
        with self.assertRaises(WorldError):
            self.w.cs.poach("rival", self.b, "nobody", 30)
        with self.assertRaises(WorldError):
            self.w.cs.poach("rival", self.b, self.emp, 3)  # Angebot unter Mindestlohn
        self.w.char("free")
        with self.assertRaises(WorldError):
            self.w.cs.poach("rival", self.b, "free", 30)  # nicht angestellt
        self.assertEqual(self.w.reg.employer, {self.emp: self.a})

    def test_capacity_of_the_offering_company(self):
        for i in range(5):
            self.w.char(f"f{i}")
            self.w.cs.hire("rival", self.b, f"f{i}", 30)
        with self.assertRaisesRegex(WorldError, "Gebäudekapazität"):
            self.w.cs.poach("rival", self.b, self.emp, 30)

    def test_better_reputation_and_level_matter_for_goals(self):
        stab = id_with_goal("stability", "s")
        self.w.char(stab)
        self.w.cs.hire("boss", self.a, stab, 20)
        self.w.reg.get(self.b)["reputation"] = 900  # deutlich besserer Ruf
        res = self.w.cs.poach("rival", self.b, stab, 24)  # 200 Promille Vorsprung
        self.assertEqual((res["conditions"], res["goal_bonus"]), ((900 - 500) // 4, 100))
        self.assertEqual(res["value"], 200 + 100 + 100)


class SharesTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.cid = self.w.company("boss", capital=3000)
        self.w.char("inv1", coins=100_000)
        self.w.char("inv2", coins=100_000)
        self.w.char("stranger", coins=100_000)
        self.c = self.w.reg.get(self.cid)
        self.w.reg.move_shares(self.c, "boss", "inv1", 200)  # Gesellschafter inv1 (200), boss (800)

    def offer(self, seller="boss", qty=300, price=10):
        return self.w.cs.offer_shares(seller, self.cid, qty, price)

    def test_offer_locks_shares(self):
        oid = self.offer(qty=300)
        self.assertEqual(self.w.reg.free_shares(self.c, "boss"), 500)
        with self.assertRaisesRegex(WorldError, "freie"):
            self.offer(qty=501)
        self.offer(qty=500)
        with self.assertRaisesRegex(WorldError, "freie"):
            self.offer(qty=1)
        self.w.cs.withdraw_offer("boss", self.cid, oid)
        self.assertEqual(self.w.reg.free_shares(self.c, "boss"), 300)

    def test_offer_validation(self):
        for qty, price in ((0, 10), (-1, 10), (10, 0), (True, 10), (10, 1.5), ("5", 10)):
            with self.assertRaises(WorldError):
                self.w.cs.offer_shares("boss", self.cid, qty, price)
        with self.assertRaises(WorldError):
            self.w.cs.offer_shares("stranger", self.cid, 1, 10)

    def test_preemption_only_for_holders_within_the_deadline(self):
        oid = self.offer(qty=300, price=10)  # Frist: Tag 1 + 7 = 8
        with self.assertRaisesRegex(WorldError, "Gesellschafter"):
            self.w.cs.preempt("stranger", self.cid, oid, 10)
        with self.assertRaisesRegex(WorldError, "Gesellschafter"):
            self.w.cs.preempt("boss", self.cid, oid, 10)  # Verkäufer selbst
        before = self.w.coins("inv1")
        self.w.cs.preempt("inv1", self.cid, oid, 100)
        self.assertEqual((self.w.coins("inv1"), self.w.coins("boss")), (before - 1000, 20000 - 3000 + 1000))
        self.assertEqual((self.c["shares"], self.c["offers"][oid]["remaining"]), ({"boss": 700, "inv1": 300}, 200))
        self.w.day[0] = 8
        with self.assertRaisesRegex(WorldError, "abgelaufen"):
            self.w.cs.preempt("inv1", self.cid, oid, 10)

    def test_preemption_validation_and_atomicity(self):
        oid = self.offer(qty=300, price=10)
        poor = CWorld()
        pid = poor.company("boss", capital=3000)
        pc = poor.reg.get(pid)
        poor.char("rich", coins=5)  # zu wenig Münzen
        poor.reg.move_shares(pc, "boss", "rich", 100)
        poid = poor.cs.offer_shares("boss", pid, 300, 10)
        before = (poor.inv.to_json(), poor.reg.to_json())
        with self.assertRaisesRegex(WorldError, "Münzen"):
            poor.cs.preempt("rich", pid, poid, 100)
        self.assertEqual((poor.inv.to_json(), poor.reg.to_json()), before)
        for qty in (0, -1, 301, True, 2.5):
            with self.assertRaises(WorldError):
                self.w.cs.preempt("inv1", self.cid, oid, qty)

    def test_purchase_needs_expired_deadline_and_current_disclosure(self):
        oid = self.offer(qty=300, price=10)
        ack = self.w.cs.disclosure(self.cid)["hash"]
        with self.assertRaisesRegex(WorldError, "läuft noch"):
            self.w.cs.purchase("stranger", self.cid, oid, 100, ack)
        self.w.day[0] = 8
        with self.assertRaisesRegex(WorldError, "Offenlegung"):
            self.w.cs.purchase("stranger", self.cid, oid, 100, "0" * 64)  # nicht bestätigt
        with self.assertRaisesRegex(WorldError, "verschieden"):
            self.w.cs.purchase("boss", self.cid, oid, 100, ack)
        self.w.cs.purchase("stranger", self.cid, oid, 100, ack)
        self.assertEqual((self.c["shares"]["stranger"], self.c["offers"][oid]["remaining"]), (100, 200))
        # Bestand hat sich geändert -> die alte Bestätigung ist ungültig
        with self.assertRaisesRegex(WorldError, "Offenlegung"):
            self.w.cs.purchase("inv2", self.cid, oid, 100, ack)
        self.w.cs.purchase("inv2", self.cid, oid, 100, self.w.cs.disclosure(self.cid)["hash"])

    def test_disclosure_content(self):
        d = self.w.cs.disclosure(self.cid)
        self.assertEqual((d["holders"], d["founder"], d["ceo"]), ({"boss": 800, "inv1": 200}, "boss", None))
        self.assertEqual(d["constitution"]["founder_veto"], True)
        self.assertEqual(d["hash"], disclosure_hash(self.c))

    def test_fully_sold_offer_is_closed_and_withdraw_rights(self):
        oid = self.offer(qty=100, price=5)
        self.w.cs.preempt("inv1", self.cid, oid, 100)
        with self.assertRaisesRegex(WorldError, "erledigt"):
            self.w.cs.preempt("inv1", self.cid, oid, 1)
        oid2 = self.offer(qty=50)
        with self.assertRaisesRegex(WorldError, "Verkäufer"):
            self.w.cs.withdraw_offer("inv1", self.cid, oid2)

    def test_share_trades_conserve_coins_and_shares(self):
        total = self.w.total_coins()
        oid = self.offer(qty=400, price=7)
        self.w.cs.preempt("inv1", self.cid, oid, 150)
        self.w.day[0] = 8
        self.w.cs.purchase("stranger", self.cid, oid, 250, self.w.cs.disclosure(self.cid)["hash"])
        self.assertEqual(self.w.total_coins(), total)
        self.assertEqual(sum(self.c["shares"].values()), 1000)

    def test_equity_grants_for_employees_with_cap(self):
        self.w.char("w1")
        self.w.cs.hire("boss", self.cid, "w1", 30)
        self.w.cs.grant_equity("boss", self.cid, "w1", 60)
        with self.assertRaisesRegex(WorldError, "begrenzt"):
            self.w.cs.grant_equity("boss", self.cid, "w1", 41)  # 60 + 41 > 100
        self.w.cs.grant_equity("boss", self.cid, "w1", 40)
        self.assertEqual(self.c["shares"]["w1"], 100)
        with self.assertRaises(WorldError):
            self.w.cs.grant_equity("boss", self.cid, "stranger", 1)  # kein Mitarbeiter
        self.offer(qty=700)  # gesperrt
        with self.assertRaisesRegex(WorldError, "freie"):
            self.w.cs.grant_equity("boss", self.cid, "w1", 1)


if __name__ == "__main__":
    unittest.main()
