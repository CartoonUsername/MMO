import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.economy import (EconomyEngine, credited_value, economic_direction_scores, economic_directions,
                             economic_profile, reference_value, trade_gains, validate_economy_rules)
from mmo_cee.errors import CEEError
from mmo_cee.history import EventLog
from mmo_cee.rules import Rules, load_rules

RULES = load_rules("rules_v7.json")
ECO = RULES["economy"]
TRADE, CAREER, FOUNDED, CLOSED = ("economy.trade_completed", "economy.career_changed",
                                  "economy.company_founded", "economy.company_closed")


def tr(tid="t1", role="seller", cp="b", item="iron_blade", grade="fine", qty=2, value=360, day=1):
    return {"trade_id": tid, "role": role, "counterparty": cp, "item_id": item, "grade": grade,
            "quantity": qty, "value": value, "day": day}


def car(company="acme", role="employee", day=1):
    return {"company_id": company, "role": role, "day": day}


def make(svc, cid="a", kind="player", xp=10000, **prof):
    svc.create(cid, kind)
    svc.record(cid, "identity.xp_gained", {"amount": xp})
    for p, x in prof.items():
        svc.record(cid, "profession.work", {"profession": p, "xp": x})


def eco(svc, cid="a"):
    return svc.state(cid).parts["economy"]


class EconomyRulesTests(unittest.TestCase):
    def _bad(self, mutate):
        data = copy.deepcopy(RULES.data)
        mutate(data["economy"], data)
        return Rules(data)

    def test_shipped_rules_valid(self):
        validate_economy_rules(RULES)

    def test_invalid_rules_rejected(self):
        cases = {
            "währung leer": lambda e, d: e["currency"].update(item=""),
            "währung handelbar": lambda e, d: e["items"].update(coin={"class": "food", "base_value": 1}),
            "klassen leer": lambda e, d: e.update(item_classes=[]),
            "gegenstand mit @": lambda e, d: e["items"].update({"a@b": {"class": "food", "base_value": 1}}),
            "unbekannte klasse": lambda e, d: e["items"]["bread"].update({"class": "magic"}),
            "basiswert 0": lambda e, d: e["items"]["bread"].update(base_value=0),
            "stufenfaktor 0": lambda e, d: e["grade_permille"].update(common=0),
            "rezept ohne wert": lambda e, d: e["items"].pop("bread"),
            "qualität ohne faktor": lambda e, d: e["grade_permille"].pop("masterwork"),
            "güte ohne faktor": lambda e, d: e["grade_permille"].pop("rough"),
            "max_quantity 0": lambda e, d: e["trade"].update(max_quantity=0),
            "value_per_point 0": lambda e, d: e["trade"].update(value_per_point=0),
            "abweichung >1000": lambda e, d: e["trade"].update(max_deviation_permille=1500),
            "netzwerkbonus negativ": lambda e, d: e["trade"].update(network_bonus_points=-1),
            "netzwerk-mindestwert 0": lambda e, d: e["trade"].update(network_min_credited_value=0),
            "repeat leer": lambda e, d: e["trade"].update(counterparty_repeat_permille=[]),
            "repeat 0": lambda e, d: e["trade"].update(counterparty_repeat_permille=[0]),
            "dimensionen falsch": lambda e, d: e.update(dimensions=["volume"]),
            "daily inkonsistent": lambda e, d: e["daily"].update(hard_cap=1),
            "rollen doppelt": lambda e, d: e["career"].update(roles=["employee", "employee"]),
            "gate fehlt": lambda e, d: e["career"]["gates"].pop("manager"),
            "gate mastery 11": lambda e, d: e["career"]["gates"]["manager"].update(min_best_mastery=11),
            "gate negativ": lambda e, d: e["career"]["gates"]["manager"].update(min_tenure_days=-1),
            "gate unbekannte dim": lambda e, d: e["career"]["gates"]["manager"].update(min_points={"fame": 5}),
            "gründung negativ": lambda e, d: e["founding"].update(min_level=-1),
            "gründung max 0": lambda e, d: e["founding"].update(max_open_companies=0),
            "richtung quelle": lambda e, d: e["directions"]["merchant"]["weights"].update({"dim:fame": 5}),
            "richtung klasse": lambda e, d: e["directions"]["merchant"]["weights"].update({"class:magic": 5}),
            "richtung schwellen": lambda e, d: e["directions"]["merchant"].update(tier_thresholds=[10, 5]),
            "richtung gewicht 0": lambda e, d: e["directions"]["merchant"]["weights"].update({"dim:volume": 0}),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                with self.assertRaises(CEEError):
                    validate_economy_rules(self._bad(mutate))

    def test_engine_validates_on_construction(self):
        with self.assertRaises(CEEError):
            EconomyEngine(self._bad(lambda e, d: e.update(item_classes=[])))

    def test_older_rules_have_no_economy_part(self):
        for name in ("rules_v1.json", "rules_v3.json", "rules_v5.json", "rules_v6.json"):
            svc = CharacterService(rules=load_rules(name))
            st = svc.create("a", "player")
            self.assertNotIn("economy", st.parts, name)
            with self.assertRaises(RuleViolation):
                svc.record("a", TRADE, tr())

    def test_initial_state(self):
        part = CharacterService(rules=RULES).create("a", "player").parts["economy"]
        self.assertEqual(part["points"], {"volume": 0, "network": 0})
        self.assertEqual(sorted(part["classes"]), sorted(ECO["item_classes"]))
        self.assertEqual((part["counterparties"], part["trades"], part["founded"]), ({}, {}, {}))
        self.assertEqual(part["career"], {"company_id": None, "role": None, "since_day": 0, "best_rung": -1, "changes": 0})

    def test_every_craftable_item_has_a_value(self):
        for r in RULES["crafting"]["recipes"].values():
            for it in [*r["inputs"], r["output"]["item"]]:
                self.assertIn(it, ECO["items"])


class ValueTests(unittest.TestCase):
    def test_reference_value_exact(self):
        self.assertEqual(reference_value(RULES, "iron_blade", "fine", 2), 360)  # 120 * 1,5 * 2
        self.assertEqual(reference_value(RULES, "bread", "common", 5), 25)
        self.assertEqual(reference_value(RULES, "iron_ore", "rough", 3), 16)  # 8 * 0,7 * 3 = 16,8 -> abgerundet
        self.assertEqual(reference_value(RULES, "frostglass", "masterwork", 1), 500)

    def test_credited_value_boundaries_inclusive(self):
        ref = 1000  # Abweichung 250 Promille
        for value, expected in ((1000, 1000), (750, 750), (1250, 1000), (749, 0), (1251, 0), (1, 0), (10**6, 0)):
            self.assertEqual(credited_value(RULES, value, ref), expected, value)


class TradeEventTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)
        make(self.svc)

    def reject(self, payload, cid="a"):
        n = len(self.svc.log.events(cid))
        before = copy.deepcopy(self.svc.state(cid).parts)
        with self.assertRaises(RuleViolation):
            self.svc.record(cid, TRADE, payload)
        self.assertEqual(len(self.svc.log.events(cid)), n)
        self.assertEqual(self.svc.state(cid).parts, before)

    def test_valid_trade_is_recorded(self):
        ev = self.svc.record("a", TRADE, tr())
        part = eco(self.svc)
        self.assertEqual(part["trades"], {"t1": ev.seq})
        self.assertEqual(part["counterparties"], {"b": 1})
        self.assertEqual(part["classes"]["weapons"], 36)

    def test_self_trade_is_rejected(self):
        self.reject(tr(cp="a"))

    def test_duplicate_trade_id_rejected_per_character(self):
        self.svc.record("a", TRADE, tr("same"))
        for _ in range(10):
            self.reject(tr("same", cp="c"))
        make(self.svc, "z")
        self.svc.record("z", TRADE, tr("same"))  # je Figur eindeutig

    def test_client_cannot_attach_points(self):
        for extra in ("points", "volume", "reference_value", "credited", "xp", "network"):
            self.reject({**tr(), extra: 99999})

    def test_missing_fields(self):
        for k in tr():
            p = tr()
            del p[k]
            self.reject(p)

    def test_bad_types_and_ranges(self):
        for field, values in {
            "trade_id": ("", "x" * 65, 5, None),
            "role": ("broker", "", 1, None, ["buyer"]),
            "counterparty": ("", "x" * 65, 5, None),
            "item_id": ("ghost", "coin", 5, None, "iron_blade@fine"),
            "grade": ("legendary", "", 1, None),
            "quantity": (0, -1, 1001, 1.5, "2", True, None),
            "value": (0, -1, 10_000_001, 1.5, "360", True, None),
            "day": (-1, 1.5, "1", True, None),
        }.items():
            for v in values:
                with self.subTest(field=field, value=v):
                    self.reject({**tr(), field: v})

    def test_day_monotonic(self):
        self.svc.record("a", TRADE, tr("a1", day=5))
        self.reject(tr("a2", day=4))
        self.svc.record("a", TRADE, tr("a3", cp="c", day=5))

    def test_event_before_creation_and_unknown_type(self):
        with self.assertRaises(RuleViolation):
            self.svc.record("ghost", TRADE, tr())
        with self.assertRaises(RuleViolation):
            self.svc.record("a", "economy.grant_points", {"volume": 100})


class TradeGainTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)
        make(self.svc)

    def pts(self):
        return dict(eco(self.svc)["points"])

    def test_exact_first_trade(self):
        self.svc.record("a", TRADE, tr())
        self.assertEqual(self.pts(), {"volume": 36, "network": 200})

    def test_repeat_with_same_partner_decays_per_day(self):
        gains, last = [], 0
        for i in range(8):
            self.svc.record("a", TRADE, tr(f"t{i}"))
            gains.append(self.pts()["volume"] - last)
            last = self.pts()["volume"]
        self.assertEqual(gains, [36, 36, 27, 18, 9, 3, 3, 3])  # 36 x [1000,1000,750,500,250,100,...] / 1000
        self.assertEqual(self.pts()["network"], 200)  # Netzwerkbonus nur einmal je Partner
        self.svc.record("a", TRADE, tr("next", day=2))
        self.assertEqual(self.pts()["volume"] - last, 36)  # neuer Tag: Abnahme zurückgesetzt

    def test_new_partners_give_network_bonus(self):
        for i, cp in enumerate(("b", "c", "d", "b")):
            self.svc.record("a", TRADE, tr(f"t{i}", cp=cp))
        self.assertEqual(self.pts()["network"], 600)
        self.assertEqual(eco(self.svc)["counterparties"], {"b": 2, "c": 1, "d": 1})
        self.assertEqual(economic_profile(self.svc.state("a"), RULES)["network_size"], 3)

    def test_price_far_from_reference_earns_nothing_but_is_recorded(self):
        for i, value in enumerate((10_000, 5, 451, 1000)):  # Referenz 360: erlaubt 270..450
            self.svc.record("a", TRADE, tr(f"x{i}", cp=f"p{i}", value=value))
        self.assertEqual(self.pts(), {"volume": 0, "network": 0})  # auch kein Netzwerkbonus
        self.assertEqual(len(eco(self.svc)["trades"]), 4)  # aber nachvollziehbar gewertet

    def test_price_tolerance_band_and_credit_is_min_of_value_and_reference(self):
        self.svc.record("a", TRADE, tr("lo", cp="p1", value=270))  # untere Grenze: 270 -> 27
        self.svc.record("a", TRADE, tr("hi", cp="p2", value=450))  # obere Grenze: gutgeschrieben wird nur die Referenz (360) -> 36
        self.assertEqual(self.pts()["volume"], 27 + 36)
        self.svc.record("a", TRADE, tr("out", cp="p3", value=269))
        self.assertEqual(self.pts()["volume"], 27 + 36)

    def test_network_bonus_needs_a_minimum_real_value(self):
        self.svc.record("a", TRADE, tr("tiny", cp="p1", item="bread", grade="common", qty=1, value=5))  # Wert 5 < 100
        self.assertEqual(self.pts()["network"], 0)
        self.svc.record("a", TRADE, tr("ok", cp="p1", item="iron_blade", grade="common", qty=1, value=120))  # 120 >= 100
        self.assertEqual(self.pts()["network"], 200)  # p1 war noch nie "neu" gewertet
        self.assertEqual(eco(self.svc)["counterparties"], {"p1": 1})  # nur der qualifizierte Handel zählt zum Netzwerk

    def test_item_classes_are_counted(self):
        self.svc.record("a", TRADE, tr("w", item="iron_blade", grade="fine", qty=2, value=360))
        self.svc.record("a", TRADE, tr("f", cp="c", item="bread", grade="common", qty=100, value=500))
        cls = eco(self.svc)["classes"]
        self.assertEqual((cls["weapons"], cls["food"], cls["luxury"]), (36, 50, 0))

    def test_gain_function_is_pure(self):
        before = copy.deepcopy(self.svc.state("a").parts)
        a = trade_gains(self.svc.state("a"), RULES, tr())
        b = trade_gains(self.svc.state("a"), RULES, tr())
        self.assertEqual((a, self.svc.state("a").parts), (b, before))

    def test_daily_caps_exact_with_lowered_limits(self):
        data = copy.deepcopy(RULES.data)
        data["economy"]["daily"] = {"full_cap": 100, "reduced_permille": 250, "hard_cap": 150}
        svc = CharacterService(rules=Rules(data))
        make(svc)
        vol = lambda: svc.state("a").parts["economy"]["points"]["volume"]
        got, last = [], 0
        for i in range(4):  # je 80 Punkte (800 Wert), jeweils neuer Partner -> keine Abnahme
            svc.record("a", TRADE, tr(f"d{i}", cp=f"p{i}", item="iron_blade", grade="common", qty=1, value=120))
            got.append(vol() - last)
            last = vol()
        # Wert 120 -> 12 Punkte; mit lowered caps nicht erreichbar -> größere Mengen
        svc2 = CharacterService(rules=Rules(data))
        make(svc2)
        vol2 = lambda: svc2.state("a").parts["economy"]["points"]["volume"]
        got2, last = [], 0
        for i in range(4):  # 8 Stück: Referenz 960 -> 96 Punkte
            svc2.record("a", TRADE, tr(f"e{i}", cp=f"p{i}", item="iron_blade", grade="common", qty=8, value=960))
            got2.append(vol2() - last)
            last = vol2()
        # 1: voll 96 | 2: 4 voll + 92 * 25 % = 27 | 3: nur reduziert 96 * 25 % = 24 | 4: Rest bis hartes Limit 150
        self.assertEqual(got2, [96, 4 + 23, 24, 150 - 96 - 27 - 24])
        self.assertEqual(vol2(), 150)
        svc2.record("a", TRADE, tr("over", cp="pz", item="iron_blade", grade="common", qty=8, value=960))
        self.assertEqual(vol2(), 150)
        svc2.record("a", TRADE, tr("tomorrow", cp="py", item="iron_blade", grade="common", qty=8, value=960, day=2))
        self.assertGreater(vol2(), 150)

    def test_points_never_decrease(self):
        last = 0
        for i in range(15):
            self.svc.record("a", TRADE, tr(f"n{i}", cp=f"p{i % 4}", value=[360, 5, 400][i % 3], day=1 + i // 5))
            cur = sum(self.pts().values())
            self.assertGreaterEqual(cur, last)
            last = cur


class WashTradingTests(unittest.TestCase):
    def test_two_accounts_trading_back_and_forth_gain_little(self):
        svc = CharacterService(rules=RULES)
        make(svc, "x")
        make(svc, "y")
        for i in range(60):  # beide Seiten verbuchen jeden Handel (wie der Handelsdienst es täte)
            svc.record("x", TRADE, tr(f"t{i}", role="seller", cp="y", value=360))
            svc.record("y", TRADE, tr(f"t{i}", role="buyer", cp="x", value=360))
        x = eco(svc, "x")["points"]
        self.assertEqual(x["network"], 200)  # ein Partner -> ein Bonus
        self.assertLessEqual(x["volume"], 36 + 36 + 27 + 18 + 9 + 3 * 55)  # Abnahme auf 10 %
        honest = CharacterService(rules=RULES)
        make(honest, "h")
        for i in range(60):
            honest.record("h", TRADE, tr(f"t{i}", cp=f"partner{i}", value=360))
        h = eco(honest, "h")["points"]
        self.assertGreater(h["volume"], 4 * x["volume"])  # viele echte Partner zahlen sich aus
        self.assertGreater(h["network"], 20 * x["network"])

    def test_price_laundering_with_absurd_prices_earns_nothing(self):
        svc = CharacterService(rules=RULES)
        make(svc, "x")
        for i in range(30):
            svc.record("x", TRADE, tr(f"t{i}", cp=f"alt{i}", item="bread", grade="common", qty=1, value=10_000_000))
        self.assertEqual(eco(svc, "x")["points"], {"volume": 0, "network": 0})


class DirectionTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)
        make(self.svc)

    def grind(self, item, grade, qty, value, days, start=1, prefix="g"):
        for d in range(start, start + days):
            for i in range(6):
                self.svc.record("a", TRADE, tr(f"{prefix}{d}-{i}", cp=f"{prefix}p{i}", item=item, grade=grade, qty=qty, value=value, day=d))

    def test_multiple_directions_non_exclusive_and_monotone(self):
        self.assertEqual(economic_directions(self.svc.state("a"), RULES), {})
        self.grind("iron_blade", "common", 50, 6000, 4)  # Waffen: 600 Punkte je Handel, 6 Partner/Tag
        first = self.svc.economic_directions("a")
        self.assertIn("arms_dealer", first)
        self.assertIn("merchant", first)
        self.grind("bread", "common", 400, 2000, 6, start=5, prefix="h")
        later = self.svc.economic_directions("a")
        self.assertIn("grocer", later)
        self.assertGreaterEqual(len(later), 3)
        for k, v in first.items():
            self.assertGreaterEqual(later[k], v)

    def test_scores_are_weighted_sums(self):
        self.svc.record("a", TRADE, tr())
        st = self.svc.state("a")
        part = st.parts["economy"]
        sc = economic_direction_scores(st, RULES)
        self.assertEqual(sc["merchant"], part["points"]["volume"] * 700 // 1000 + part["points"]["network"] * 300 // 1000)
        self.assertEqual(sc["arms_dealer"], part["classes"]["weapons"])
        self.assertEqual(sc["grocer"], 0)

    def test_npc_replay_roundtrip_and_unrelated_events(self):
        make(self.svc, "n", kind="npc")
        self.svc.record("n", TRADE, tr("n1", cp="p"))
        live = copy.deepcopy(self.svc.state("n").parts)
        self.assertEqual(self.svc.rebuild("n").parts, live)
        svc2 = CharacterService(rules=RULES, log=EventLog.from_json("n", self.svc.log.to_json("n")))
        self.assertEqual(svc2.state("n").parts, live)
        self.assertEqual(live["identity"]["kind"], "npc")
        before = copy.deepcopy(self.svc.state("n").parts["economy"])
        self.svc.record("n", "identity.xp_gained", {"amount": 500})
        self.svc.record("n", "profession.work", {"profession": "trade", "xp": 50})
        self.assertEqual(self.svc.state("n").parts["economy"], before)


class CareerTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)
        make(self.svc, trade=48000)  # beste Meisterschaft 9

    def reject(self, payload, type_=CAREER, cid="a"):
        n = len(self.svc.log.events(cid))
        before = copy.deepcopy(self.svc.state(cid).parts)
        with self.assertRaises(RuleViolation):
            self.svc.record(cid, type_, payload)
        self.assertEqual(len(self.svc.log.events(cid)), n)
        self.assertEqual(self.svc.state(cid).parts, before)

    def career(self):
        return dict(eco(self.svc)["career"])

    def test_hire_only_as_entry_role(self):
        for role in ("specialist", "department_head", "manager", "executive"):
            self.reject(car(role=role))
        self.svc.record("a", CAREER, car())
        c = self.career()
        self.assertEqual((c["company_id"], c["role"], c["since_day"], c["best_rung"]), ("acme", "employee", 1, 0))

    def test_invalid_payloads(self):
        for p in ({"company_id": "acme", "role": None, "day": 1}, {"company_id": None, "role": "employee", "day": 1},
                  car(company=""), car(company="x" * 65), car(company=5), car(role="ceo"), car(role=5), car(role=["employee"]),
                  {"company_id": "acme", "role": "employee"}, {**car(), "salary": 99}, car(day=-1), car(day=1.5), car(day=True)):
            with self.subTest(p=p):
                self.reject(p)

    def test_promotion_one_step_with_gates(self):
        self.svc.record("a", CAREER, car(day=1))
        self.reject(car(role="manager", day=40))  # Stufen überspringen
        self.reject(car(role="specialist", day=7))  # Dienstzeit 6 < 7
        self.svc.record("a", CAREER, car(role="specialist", day=8))  # 7 Tage: Grenze inklusiv
        self.reject(car(role="department_head", day=21))  # 13 < 14
        self.svc.record("a", CAREER, car(role="department_head", day=22))
        self.reject(car(role="manager", day=43))  # Dienstzeit ok (21), aber Handelspunkte fehlen
        self.svc.record("a", TRADE, tr("big", item="iron_blade", grade="masterwork", qty=100, value=30000, day=22))  # 3000 Punkte
        self.assertGreaterEqual(eco(self.svc)["points"]["volume"], 2000)
        self.reject(car(role="manager", day=42))  # 20 < 21
        self.svc.record("a", CAREER, car(role="manager", day=43))
        self.assertEqual(self.career()["best_rung"], 3)

    def test_skipping_a_rung_is_rejected_even_when_all_gates_are_met(self):
        self.svc.record("a", CAREER, car(day=1))
        # Meisterschaft 9, Dienstzeit 21: die Voraussetzungen von department_head wären erfüllt - nur der Sprung ist unzulässig
        self.reject(car(role="department_head", day=22))
        self.svc.record("a", CAREER, car(role="specialist", day=22))
        self.svc.record("a", CAREER, car(role="department_head", day=36))

    def test_company_switch_without_leaving_is_rejected_even_when_promotion_gates_are_met(self):
        self.svc.record("a", CAREER, car(day=1))
        self.svc.record("a", CAREER, car(role="specialist", day=8))
        self.reject(car(company="other", role="department_head", day=22))  # Gates erfüllt, aber fremde Firma
        self.svc.record("a", CAREER, car(role="department_head", day=22))  # in der eigenen Firma geht es

    def test_executive_needs_points_and_network(self):
        self.svc.record("a", CAREER, car(day=1))
        for role, day in (("specialist", 8), ("department_head", 22), ("manager", 43)):
            if role == "manager":
                self.svc.record("a", TRADE, tr("m", item="iron_blade", grade="masterwork", qty=100, value=30000, day=30))
            self.svc.record("a", CAREER, car(role=role, day=day))
        self.reject(car(role="executive", day=73))  # Handelspunkte (10000) und Netzwerk (1000) fehlen
        for i in range(5):  # 5 neue Partner -> Netzwerk 1000 (nur bei echtem Handel)
            self.svc.record("a", TRADE, tr(f"n{i}", cp=f"net{i}", item="iron_blade", grade="masterwork", qty=100, value=30000, day=50 + i))
        for d in (60, 61, 62, 63):  # Volumen: 6 + ... ; mehrere Tage wegen Tageslimit
            self.svc.record("a", TRADE, tr(f"v{d}", cp=f"vol{d}", item="iron_blade", grade="masterwork", qty=100, value=30000, day=d))
        pts = eco(self.svc)["points"]
        self.assertGreaterEqual(pts["volume"], 10000)
        self.assertGreaterEqual(pts["network"], 1000)
        self.reject(car(role="executive", day=72))  # Dienstzeit 29 < 30
        self.svc.record("a", CAREER, car(role="executive", day=73))
        self.assertEqual(economic_profile(self.svc.state("a"), RULES)["rung"], 4)

    def test_mastery_gate(self):
        make(self.svc, "weak", trade=100)  # Meisterschaft 1
        self.svc.record("weak", CAREER, car(day=1))
        self.reject(car(role="specialist", day=30), cid="weak")

    def test_demotion_leave_and_company_switch(self):
        self.svc.record("a", CAREER, car(day=1))
        self.svc.record("a", CAREER, car(role="specialist", day=8))
        self.reject(car(company="other", role="specialist", day=9))  # Firmenwechsel nur nach Austritt
        self.reject(car(role="specialist", day=9))  # Rolle unverändert
        self.svc.record("a", CAREER, car(role="employee", day=9))  # Zurückstufung zulässig
        self.assertEqual((self.career()["role"], self.career()["best_rung"]), ("employee", 1))  # bester Rang bleibt erhalten
        self.svc.record("a", CAREER, {"company_id": None, "role": None, "day": 10})
        self.assertEqual((self.career()["company_id"], self.career()["role"]), (None, None))
        self.reject({"company_id": None, "role": None, "day": 11})  # nicht angestellt
        self.svc.record("a", CAREER, car(company="other", day=12))
        self.assertEqual(self.career()["company_id"], "other")
        self.assertEqual(self.career()["changes"], 5)

    def test_tenure_restarts_after_each_change(self):
        self.svc.record("a", CAREER, car(day=1))
        self.svc.record("a", CAREER, {"company_id": None, "role": None, "day": 20})
        self.svc.record("a", CAREER, car(day=21))
        self.reject(car(role="specialist", day=27))  # neue Anstellung: 6 < 7
        self.svc.record("a", CAREER, car(role="specialist", day=28))

    def test_day_monotonic_across_all_economy_events(self):
        self.svc.record("a", TRADE, tr(day=10))
        self.reject(car(day=9))
        self.reject({"company_id": "c1", "day": 9}, type_=FOUNDED)
        self.svc.record("a", CAREER, car(day=10))


class FoundingTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)
        make(self.svc, trade=700)  # Stufe 11, Meisterschaft 3

    def reject(self, type_, payload, cid="a"):
        n = len(self.svc.log.events(cid))
        before = copy.deepcopy(self.svc.state(cid).parts)
        with self.assertRaises(RuleViolation):
            self.svc.record(cid, type_, payload)
        self.assertEqual(len(self.svc.log.events(cid)), n)
        self.assertEqual(self.svc.state(cid).parts, before)

    def test_found_and_close(self):
        ev = self.svc.record("a", FOUNDED, {"company_id": "c1", "day": 2})
        self.assertEqual(eco(self.svc)["founded"], {"c1": {"day": 2, "open": True, "seq": ev.seq}})
        self.svc.record("a", CLOSED, {"company_id": "c1", "day": 3})
        self.assertFalse(eco(self.svc)["founded"]["c1"]["open"])
        prof = economic_profile(self.svc.state("a"), RULES)
        self.assertEqual((prof["companies_open"], prof["companies_founded_total"]), (0, 1))

    def test_gates(self):
        make(self.svc, "low", xp=100, trade=700)
        self.reject(FOUNDED, {"company_id": "c", "day": 1}, cid="low")  # Stufe zu niedrig
        make(self.svc, "unskilled")
        self.reject(FOUNDED, {"company_id": "c", "day": 1}, cid="unskilled")  # Meisterschaft fehlt

    def test_max_open_companies_and_reopening(self):
        for i in range(3):
            self.svc.record("a", FOUNDED, {"company_id": f"c{i}", "day": 1})
        self.reject(FOUNDED, {"company_id": "c3", "day": 1})
        self.svc.record("a", CLOSED, {"company_id": "c0", "day": 2})
        self.svc.record("a", FOUNDED, {"company_id": "c3", "day": 2})  # Platz frei geworden
        self.reject(FOUNDED, {"company_id": "c0", "day": 3})  # geschlossene ID nie wiederverwendbar

    def test_duplicates_and_closing_rules(self):
        self.svc.record("a", FOUNDED, {"company_id": "c1", "day": 1})
        self.reject(FOUNDED, {"company_id": "c1", "day": 1})
        self.reject(CLOSED, {"company_id": "ghost", "day": 1})
        self.svc.record("a", CLOSED, {"company_id": "c1", "day": 1})
        self.reject(CLOSED, {"company_id": "c1", "day": 1})

    def test_invalid_payloads(self):
        for p in ({"company_id": "", "day": 1}, {"company_id": 5, "day": 1}, {"company_id": "c", "day": -1},
                  {"company_id": "c"}, {"day": 1}, {"company_id": "c", "day": 1, "capital": 10**9}):
            with self.subTest(p=p):
                self.reject(FOUNDED, p)

    def test_owner_and_career_are_independent(self):
        self.svc.record("a", FOUNDED, {"company_id": "own", "day": 1})
        self.svc.record("a", CAREER, car(company="other", day=1))  # Eigentümer einer Firma, Angestellter einer anderen
        prof = economic_profile(self.svc.state("a"), RULES)
        self.assertEqual((prof["companies_open"], prof["company_id"], prof["role"]), (1, "other", "employee"))


if __name__ == "__main__":
    unittest.main()
