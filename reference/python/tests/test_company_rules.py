import copy
import unittest

from mmo_cee.rules import load_rules
from mmo_world import CompanyRegistry, WorldError, load_company_rules
from mmo_world.company import (building, company_level, disclosure, disclosure_hash, employee_status, evaluate_offer,
                               goal_of, next_loyalty, next_warning_days, quits, satisfaction_delta, tally,
                               validate_company_rules, wage_demand)

CEE = load_rules("rules_v7.json")
CR = load_company_rules()


def sat(**over):
    kw = dict(paid_ratio=1000, paid=True, profit_paid=False, headcount_permille=0, reputation=500, goal="stability",
              promoted_recently=False)
    kw.update(over)
    return satisfaction_delta(CR, **kw)


class CompanyRulesValidationTests(unittest.TestCase):
    def test_shipped_rules_valid(self):
        validate_company_rules(CR, CEE)

    def test_needs_new_enough_cee_rules(self):
        with self.assertRaises(WorldError):
            validate_company_rules(CR, load_rules("rules_v6.json"))

    def test_invalid_rules_rejected(self):
        cases = {
            "rolle fehlt": lambda c: c["wages"]["base_by_role"].pop("manager"),
            "rolle zu viel": lambda c: c["wages"]["base_by_role"].update(ceo=500),
            "basis < min": lambda c: c["wages"]["base_by_role"].update(employee=1),
            "min_daily 0": lambda c: c["wages"].update(min_daily=0),
            "per_mastery negativ": lambda c: c["wages"].update(per_mastery=-1),
            "profit_share > gesamt": lambda c: c["wages"].update(max_profit_share_permille=900),
            "kapital 0": lambda c: c["founding"].update(capital_min=0),
            "anteile 0": lambda c: c["founding"].update(total_shares=0),
            "gebäude lücke": lambda c: c["building_levels"][1].update(level=3),
            "stufe 1 kostet": lambda c: c["building_levels"][0].update(upgrade_cost=10),
            "gebäude nicht wachsend": lambda c: c["building_levels"][1].update(max_employees=3),
            "lager schrumpft": lambda c: c["building_levels"][1].update(storage=10),
            "schwellen ohne 0": lambda c: c.update(company_level_thresholds=[5, 10]),
            "schwellen nicht aufsteigend": lambda c: c.update(company_level_thresholds=[0, 100, 50]),
            "ziele doppelt": lambda c: c.update(goals=["wage", "wage"]),
            "ziele leer": lambda c: c.update(goals=[]),
            "warnungen reihenfolge": lambda c: c["warnings"].update(warned_days=9, intent_days=7),
            "schwelle 1000": lambda c: c["governance"].update(decision_threshold_permille=1000),
            "schwelle 0": lambda c: c["governance"].update(decision_threshold_permille=0),
            "vorkaufsfrist 0": lambda c: c["governance"].update(preemption_days=0),
            "abstimmung 0": lambda c: c["governance"].update(vote_days=0),
            "veto-min >1000": lambda c: c["governance"].update(founder_veto_min_permille=2000),
            "catch_up 0": lambda c: c.update(max_catch_up_days=0),
            "log_limit 0": lambda c: c.update(log_limit=0),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                bad = copy.deepcopy(CR)
                mutate(bad)
                with self.assertRaises(WorldError):
                    validate_company_rules(bad, CEE)


class PureRuleTests(unittest.TestCase):
    def test_wage_demand_and_levels(self):
        self.assertEqual(wage_demand(CR, "employee", 0), 20)
        self.assertEqual(wage_demand(CR, "manager", 5), 110 + 15)
        for revenue, level in ((0, 1), (9999, 1), (10000, 2), (49999, 2), (50000, 3), (199999, 3), (200000, 4), (10**9, 4)):
            self.assertEqual(company_level(CR, revenue), level, revenue)
        self.assertEqual(building(CR, 2)["max_employees"], 12)

    def test_goal_is_stable_known_and_varied(self):
        goals = {goal_of(CR, f"char-{i}") for i in range(60)}
        self.assertEqual(goals, set(CR["goals"]))
        self.assertEqual(goal_of(CR, "x"), goal_of(CR, "x"))

    def test_satisfaction_delta_exact(self):
        self.assertEqual(sat(), 0 + 2 + 3)  # Lohn = Anspruch; Ruf 500//200=2; Stabilitätsziel +3
        self.assertEqual(sat(goal="wage", paid_ratio=1200), 10 * 3 // 2 + 2)  # (+10) x 1,5
        self.assertEqual(sat(goal="wage", paid_ratio=5000), 20 * 3 // 2 + 2)  # Obergrenze +20 vor dem Ziel-Faktor
        self.assertEqual(sat(paid_ratio=0, paid=False), -40 - 30 + 2)  # Untergrenze -40, unbezahlt -30
        self.assertEqual(sat(goal="wage", paid_ratio=0, paid=False), -40 * 3 // 2 - 30 + 2)
        self.assertEqual(sat(profit_paid=True), 5 + 5)
        self.assertEqual(sat(headcount_permille=800), 5)  # Schwelle exklusiv
        self.assertEqual(sat(headcount_permille=801), 5 - 5)
        self.assertEqual(sat(goal="growth", promoted_recently=True), 2 + 3)
        self.assertEqual(sat(goal="growth", promoted_recently=False), 2 - 2)
        self.assertEqual(sat(goal="growth", paid=False, paid_ratio=0), -40 - 30 + 2 - 2)
        self.assertEqual(sat(reputation=1000), 5 + 3)
        self.assertEqual(sat(paid_ratio=999), (-1) // 20 + 2 + 3)  # Floor bei negativen Werten: -1

    def test_loyalty(self):
        self.assertEqual(next_loyalty(CR, 300, 600, 1), 302)
        self.assertEqual(next_loyalty(CR, 300, 599, 1), 300)
        self.assertEqual(next_loyalty(CR, 300, 299, 1), 297)
        self.assertEqual(next_loyalty(CR, 300, 300, 1), 300)
        self.assertEqual(next_loyalty(CR, 300, 600, 30), 303)  # Dienstzeitbonus
        self.assertEqual(next_loyalty(CR, 300, 600, 60), 303)
        self.assertEqual(next_loyalty(CR, 300, 600, 0), 302)
        self.assertEqual((next_loyalty(CR, 999, 700, 1), next_loyalty(CR, 1, 0, 1)), (1000, 0))

    def test_warnings_status_and_quitting(self):
        self.assertEqual(next_warning_days(CR, 0, 399), 1)
        self.assertEqual(next_warning_days(CR, 5, 400), 4)  # Zufriedenheit 400 ist nicht mehr unter der Schwelle
        self.assertEqual(next_warning_days(CR, 0, 900), 0)
        self.assertEqual([employee_status(CR, d) for d in (0, 2, 3, 6, 7, 20)], ["ok", "ok", "warned", "warned", "intends_to_resign", "intends_to_resign"])
        self.assertFalse(quits(CR, 12, 300))
        self.assertTrue(quits(CR, 13, 300))  # 10 + 300//100
        self.assertTrue(quits(CR, 10, 0))
        self.assertFalse(quits(CR, 19, 1000))
        self.assertTrue(quits(CR, 20, 1000))  # treue Mitarbeiter halten länger durch

    def offer(self, **over):
        kw = dict(goal="stability", demand=40, loyalty=300, satisfaction=500, current_wage=40, offer_wage=60,
                  current_reputation=500, offer_reputation=500, current_level=1, offer_level=1)
        kw.update(over)
        return evaluate_offer(CR, **kw)

    def test_evaluate_offer_breakdown_and_boundary(self):
        r = self.offer()  # +20 € = 500 Promille Lohnvorsprung
        self.assertEqual((r["wage_gain"], r["conditions"], r["goal_bonus"], r["value"]), (500, 0, 0, 500))
        self.assertEqual(r["barrier"], 100 + 300 // 2 + 500 // 4)  # 375
        self.assertTrue(r["accept"])
        # Grenze: value muss die Hürde strikt übersteigen
        tight = self.offer(offer_wage=40 + 15)  # Lohnvorsprung 375 = Hürde 375
        self.assertEqual((tight["value"], tight["barrier"], tight["accept"]), (375, 375, False))
        self.assertTrue(self.offer(offer_wage=40 + 16)["accept"])

    def test_goals_shape_the_decision(self):
        base = self.offer(offer_wage=45)  # Lohnvorsprung 125 < Hürde
        self.assertFalse(base["accept"])
        wage = self.offer(goal="wage", offer_wage=45)  # 125 x 1,5 = 187
        self.assertEqual(wage["wage_gain"], 125 * 3 // 2)
        self.assertFalse(wage["accept"])
        # Wunschziel Lohn: der Vorsprung zählt 1,5-fach. Hürde 375 -> Angebot 50 (250 x 1,5 = 375) reicht nicht, 51 schon
        self.assertEqual(self.offer(goal="wage", offer_wage=50)["value"], 375)
        self.assertFalse(self.offer(goal="wage", offer_wage=50)["accept"])
        self.assertTrue(self.offer(goal="wage", offer_wage=51)["accept"])
        self.assertFalse(self.offer(goal="stability", offer_wage=51)["accept"])  # ohne Lohnziel genügen 275 nicht
        stab = self.offer(goal="stability", offer_wage=45, offer_reputation=700)
        self.assertEqual((stab["conditions"], stab["goal_bonus"]), (200 // 4, 100))
        self.assertEqual(self.offer(goal="stability", offer_wage=45, offer_reputation=400)["goal_bonus"], 0)  # schlechterer Ruf: kein Bonus
        grow = self.offer(goal="growth", offer_wage=45, offer_level=2)
        self.assertEqual(grow["goal_bonus"], 150)
        self.assertEqual(self.offer(goal="growth", offer_wage=45, offer_level=1)["goal_bonus"], 0)

    def test_loyalty_and_satisfaction_raise_the_barrier(self):
        low = self.offer(loyalty=0, satisfaction=0, offer_wage=45)
        high = self.offer(loyalty=1000, satisfaction=1000, offer_wage=45)
        self.assertEqual((low["barrier"], high["barrier"]), (100, 100 + 500 + 250))
        self.assertTrue(low["accept"])  # 125 > 100
        self.assertFalse(high["accept"])

    def test_wage_ratio_is_capped(self):
        r = self.offer(offer_wage=10_000, current_wage=40)
        self.assertEqual(r["wage_gain"], 2000 - 1000)  # Obergrenze max_ratio = 2000

    def test_worse_offer_is_declined(self):
        r = self.offer(offer_wage=20)
        self.assertFalse(r["accept"])
        self.assertEqual(r["wage_gain"], 500 - 1000)


class TallyTests(unittest.TestCase):
    W = {"a": 600, "b": 300, "c": 100}

    def test_basic_majority(self):
        self.assertEqual(tally(self.W, {"a": True}, 500, veto_holder=None), "passed")
        self.assertEqual(tally(self.W, {"b": True, "c": True}, 500, veto_holder=None), "pending")  # 400 <= 500
        self.assertEqual(tally(self.W, {"a": False}, 500, veto_holder=None), "rejected")  # 400 übrig: nie > 500
        self.assertEqual(tally(self.W, {"b": False}, 500, veto_holder=None), "pending")  # a+c = 700 möglich

    def test_threshold_is_strict(self):
        self.assertEqual(tally({"a": 500, "b": 500}, {"a": True}, 500, veto_holder=None), "pending")  # 500 ist nicht > 500
        self.assertEqual(tally({"a": 500, "b": 500}, {"a": True, "b": True}, 500, veto_holder=None), "passed")

    def test_founder_veto(self):
        self.assertEqual(tally(self.W, {"a": True}, 500, veto_holder="b"), "pending")  # Mehrheit, aber Gründer fehlt noch
        self.assertEqual(tally(self.W, {"a": True, "b": True}, 500, veto_holder="b"), "passed")
        self.assertEqual(tally(self.W, {"a": True, "b": False}, 500, veto_holder="b"), "rejected")  # Veto

    def test_no_votes_is_pending(self):
        self.assertEqual(tally(self.W, {}, 500, veto_holder=None), "pending")


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.reg = CompanyRegistry(CR)
        self.c = self.reg.create("co1", "founder", 3)

    def test_create_state(self):
        c = self.c
        self.assertEqual((c["shares"], c["building_level"], c["open"], c["ceo"], c["reputation"]), ({"founder": 1000}, 1, True, None, 500))
        self.assertEqual(c["constitution"], {"decision_threshold_permille": 500, "founder_veto": True,
                                             "founder_veto_min_permille": 100, "preemption_days": 7, "vote_days": 5})

    def test_get_validation(self):
        for bad in ("ghost", None, 5):
            with self.assertRaises(WorldError):
                self.reg.get(bad)
        self.c["open"] = False
        with self.assertRaises(WorldError):
            self.reg.get_open("co1")

    def test_shares_move_and_invariants(self):
        self.reg.move_shares(self.c, "founder", "a", 300)
        self.assertEqual(self.c["shares"], {"founder": 700, "a": 300})
        self.reg.move_shares(self.c, "a", "founder", 300)
        self.assertEqual(self.c["shares"], {"founder": 1000})  # leerer Stapel entfernt
        for qty in (0, -1, 1001):
            with self.assertRaises(WorldError):
                self.reg.move_shares(self.c, "founder", "a", qty)
            self.assertEqual(self.c["shares"], {"founder": 1000})  # ein fehlgeschlagener Übertrag ändert nichts
        with self.assertRaises(WorldError):
            self.reg.move_shares(self.c, "nobody", "a", 1)  # Verkäufer ohne Anteile
        self.assertEqual(self.c["shares"], {"founder": 1000})
        self.c["shares"]["ghost"] = 1
        with self.assertRaises(WorldError):
            self.reg.check(self.c)

    def test_locked_and_free_shares(self):
        self.c["offers"]["o"] = {"seller": "founder", "qty": 400, "remaining": 250, "price": 1, "day": 1, "deadline": 8}
        self.assertEqual((self.reg.locked_shares(self.c, "founder"), self.reg.free_shares(self.c, "founder")), (250, 750))
        self.assertEqual(self.reg.free_shares(self.c, "nobody"), 0)

    def test_employer_map_is_exclusive(self):
        self.reg.add_employee(self.c, "w1", {"x": 1})
        c2 = self.reg.create("co2", "f2", 3)
        with self.assertRaises(WorldError):
            self.reg.add_employee(c2, "w1", {"x": 1})
        self.c["ceo"] = "w1"
        self.reg.remove_employee(self.c, "w1")
        self.assertEqual((self.reg.employer, self.c["ceo"]), ({}, None))
        self.reg.add_employee(c2, "w1", {"x": 1})  # jetzt frei

    def test_log_is_bounded(self):
        for i in range(CR["log_limit"] + 50):
            self.reg.log(self.c, i, "x", n=i)
        self.assertEqual(len(self.c["log"]), CR["log_limit"])
        self.assertEqual(self.c["log"][-1]["n"], CR["log_limit"] + 49)

    def test_company_ids_and_levels(self):
        self.assertEqual(self.reg.next_company_id("s"), "s-co-00000001")
        self.assertEqual(self.reg.next_company_id("s"), "s-co-00000002")
        self.c["revenue_total"] = 60000
        self.assertEqual(self.reg.level(self.c), 3)

    def test_json_roundtrip_and_corruption_detected(self):
        self.reg.move_shares(self.c, "founder", "a", 100)
        self.reg.add_employee(self.c, "w1", {"wage": 20})
        text = self.reg.to_json()
        again = CompanyRegistry.from_json(CR, text)
        self.assertEqual(again.to_json(), text)
        broken = text.replace('"founder":900', '"founder":901')
        with self.assertRaises(WorldError):
            CompanyRegistry.from_json(CR, broken)

    def test_disclosure_hash_tracks_rights_and_ownership(self):
        h0 = disclosure_hash(self.c)
        self.assertEqual(h0, disclosure_hash(self.c))
        self.assertEqual(disclosure(self.c)["holders"], {"founder": 1000})
        self.reg.move_shares(self.c, "founder", "a", 1)
        h1 = disclosure_hash(self.c)
        self.assertNotEqual(h0, h1)
        self.c["constitution"]["founder_veto"] = False
        self.assertNotEqual(h1, disclosure_hash(self.c))
        self.c["ceo"] = "boss"
        self.assertNotEqual(h1, disclosure_hash(self.c))


if __name__ == "__main__":
    unittest.main()
