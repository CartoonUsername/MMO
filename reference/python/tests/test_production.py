import json
import tempfile
import unittest

from mmo_world import WorldError, persistence
from mmo_world.golden import Rng
from mmo_world.production import job_owner, load_production_rules, validate_production_rules
from mmo_world.world import World

COIN = "coin@gold"
ORE = "iron_ore@standard"
INGOT = "iron_ingot@common"


class PW:
    """Hilfsaufbau: Gründer, Schmied (Meisterschaft 3), Lehrling, Firma mit Erz im Lager."""

    def __init__(self, ore=200, capital=5000, wage=50):
        self.w = World()
        self.minted = 0
        self.char("boss", trade=700)
        self.char("smith", smithing=700)
        self.char("novice")
        self.give("boss", capital + 20000)
        self.give("boss", 0)
        self.w.inv.deposit("boss", ORE, 1000)
        self.w.inv.deposit("boss", "charcoal@standard", 100)
        self.co = self.w.company.found("boss", capital)
        self.w.company.hire("boss", self.co, "smith", wage)
        self.w.company.hire("boss", self.co, "novice", wage)
        self.p = self.w.production
        if ore:
            self.p.stock_in("boss", self.co, ORE, ore)

    def char(self, cid, **prof):
        self.w.svc.create(cid, "player")
        self.w.svc.record(cid, "identity.xp_gained", {"amount": 10000})
        for k, v in prof.items():
            self.w.svc.record(cid, "profession.work", {"profession": k, "xp": v})

    def give(self, cid, n):
        if n:
            self.w.inv.deposit(cid, COIN, n)
            self.minted += n

    def days(self, to):
        self.w.day[0] = to
        return self.w.company.advance_day(to)

    def coins_total(self):
        return self.w.inv.total(COIN)


class RulesTests(unittest.TestCase):
    def test_default_valid_and_broken_rejected(self):
        w = World()
        pr = load_production_rules()
        validate_production_rules(pr, w.svc.rules, w.company_rules)
        for key, bad in (("lines_by_building_level", [1, 2]), ("lines_by_building_level", [3, 2, 1]), ("batch_size", 0),
                         ("batch_size", 21), ("output_permille", 0), ("output_permille", 1001), ("max_quality", "legend"),
                         ("days_per_batch_by_tier", {"1": 1}), ("upkeep_per_batch_by_tier", {"1": 0, "2": 1, "3": 1, "4": 1}),
                         ("npc_buyer", {"permille": 0, "daily_cap": 5}), ("npc_buyer", {"permille": 500, "daily_cap": 0}),
                         ("max_batches_per_job", True), ("requires_cee_rules_min", 99)):
            with self.subTest(key=key, bad=bad):
                with self.assertRaises(WorldError):
                    validate_production_rules(dict(pr, **{key: bad}), w.svc.rules, w.company_rules)


class StockTests(unittest.TestCase):
    def setUp(self):
        self.t = PW(ore=0)
        self.p, self.co = self.t.p, self.t.co

    def test_in_out_and_capacity(self):
        self.p.stock_in("boss", self.co, ORE, 150)
        self.assertEqual((self.p.stock(self.co), self.p.used_capacity(self.co)), ({ORE: 150}, 150))
        self.p.stock_in("boss", self.co, ORE, 50)  # Stufe 1: Lager 200
        with self.assertRaises(WorldError):
            self.p.stock_in("boss", self.co, ORE, 1)
        self.p.stock_out("boss", self.co, ORE, 60)
        self.assertEqual((self.t.w.inv.balance("boss", ORE), self.p.stock(self.co)), (860, {ORE: 140}))

    def test_rejections_change_nothing(self):
        self.t.w.inv.deposit("smith", ORE, 5)
        self.p.stock_in("boss", self.co, ORE, 10)
        before = self.t.w.inv.to_json()
        for fn in (lambda: self.p.stock_in("smith", self.co, ORE, 1),            # keine Berechtigung trotz Ware
                   lambda: self.p.stock_in("boss", self.co, COIN, 1),           # Münzen sind keine Ware
                   lambda: self.p.stock_in("boss", self.co, "iron_ore", 1),
                   lambda: self.p.stock_in("boss", self.co, "ghost@fine", 1),
                   lambda: self.p.stock_in("boss", self.co, ORE, 0),
                   lambda: self.p.stock_in("boss", self.co, ORE, True),
                   lambda: self.p.stock_in("boss", self.co, ORE, 5000),
                   lambda: self.p.stock_in("boss", "srv1-co-00000099", ORE, 1),
                   lambda: self.p.stock_out("boss", self.co, ORE, 11),          # mehr als im Lager
                   lambda: self.p.stock_out("smith", self.co, ORE, 1)):        # keine Berechtigung trotz Bestand
            with self.assertRaises(WorldError):
                fn()
        self.assertEqual(self.t.w.inv.to_json(), before)


class StartTests(unittest.TestCase):
    def setUp(self):
        self.t = PW()
        self.p, self.co = self.t.p, self.t.co

    def test_start_moves_inputs_into_job_account(self):
        jid = self.p.start("boss", self.co, "smith", "iron_ingot", 3, "standard")
        self.assertEqual(jid, "srv1-job-00000001")
        self.assertEqual(self.t.w.inv.holdings(job_owner(jid)), {ORE: 60})  # 3 Chargen * 10 * 2 Erz
        self.assertEqual(self.p.stock(self.co), {ORE: 140})
        j = self.p.jobs[jid]
        self.assertEqual((j["quality"], j["tier"], j["done"], j["progress"]), ("common", 1, 0, 0))
        self.assertEqual(self.p.check(), [])

    def test_rejections_change_nothing(self):
        t = self.t
        before = (t.w.inv.to_json(), self.p._counter, self.p.to_json())
        calls = [("boss", self.co, "smith", "ghost", 1, "standard"), ("boss", self.co, "smith", "iron_ingot", 1, "legendary"),
                 ("boss", self.co, "smith", "iron_ingot", 0, "standard"), ("boss", self.co, "smith", "iron_ingot", 11, "standard"),
                 ("boss", self.co, "smith", "iron_ingot", True, "standard"), ("boss", self.co, "boss", "iron_ingot", 1, "standard"),
                 ("boss", self.co, "ghost", "iron_ingot", 1, "standard"), ("smith", self.co, "smith", "iron_ingot", 1, "standard"),
                 ("boss", self.co, "novice", "iron_blade", 1, "standard"),      # Meisterschaft fehlt
                 ("boss", self.co, "smith", "frostglass", 1, "standard"),       # Entdeckung fehlt
                 ("boss", self.co, "smith", "iron_ingot", 10, "standard"),      # 200 Erz nötig, 200 da -> ok? siehe unten
                 ]
        for args in calls[:-1]:
            with self.subTest(args=args):
                with self.assertRaises(WorldError):
                    self.p.start(*args)
        self.assertEqual((t.w.inv.to_json(), self.p._counter, self.p.to_json()), before)
        t.w.inv.apply(self.p.store_of(self.co), {ORE: 100}, {})  # nur noch 100 Erz: 6 Chargen brauchen 120
        before = (t.w.inv.to_json(), self.p._counter)
        with self.assertRaises(WorldError):
            self.p.start("boss", self.co, "smith", "iron_ingot", 6, "standard")
        self.assertEqual((t.w.inv.to_json(), self.p._counter), before)
        with self.assertRaises(WorldError):
            self.p.start("boss", self.co, "smith", "iron_ingot", 5, "select")  # falsche Güteklasse im Lager

    def test_line_and_worker_limits_and_upgrade(self):
        self.p.start("boss", self.co, "smith", "iron_ingot", 5, "standard")
        for who in ("smith", "novice"):
            with self.assertRaises(WorldError):  # Arbeiter belegt / keine freie Linie (Stufe 1 hat 1)
                self.p.start("boss", self.co, who, "iron_ingot", 1, "standard")
        self.t.w.company.record_revenue(self.co, 10000)
        self.t.w.company.upgrade_building("boss", self.co)  # Stufe 2: 2 Linien, Lager 600
        self.p.start("boss", self.co, "novice", "iron_ingot", 1, "standard")
        self.t.char("third", smithing=100)
        self.t.w.company.hire("boss", self.co, "third", 50)
        with self.assertRaises(WorldError):  # beide Linien belegt
            self.p.start("boss", self.co, "third", "iron_ingot", 1, "standard")

    def test_one_worker_cannot_run_two_lines_and_recipe_knowledge_is_required(self):
        self.t.w.company.record_revenue(self.co, 10000)
        self.t.w.company.upgrade_building("boss", self.co)  # zwei Linien
        self.p.start("boss", self.co, "smith", "iron_ingot", 5, "standard")
        with self.assertRaisesRegex(WorldError, "bereits einem Auftrag"):
            self.p.start("boss", self.co, "smith", "iron_ingot", 1, "standard")
        store = self.p.store_of(self.co)
        self.t.w.inv.deposit(store, "iron_ingot@standard", 20)
        self.t.w.inv.deposit(store, "charcoal@standard", 5)
        with self.assertRaisesRegex(WorldError, "beherrscht das Rezept nicht"):
            self.p.start("boss", self.co, "novice", "iron_blade", 1, "standard")  # Material da, Meisterschaft fehlt
        self.t.w.inv.deposit(store, "glass_sand@standard", 30)
        self.t.w.inv.deposit(store, "frost_lily@standard", 10)
        self.t.char("alch", alchemy=700)
        self.t.w.company.hire("boss", self.co, "alch", 50)
        with self.assertRaisesRegex(WorldError, "beherrscht das Rezept nicht"):
            self.p.start("boss", self.co, "alch", "frostglass", 1, "standard")  # Meisterschaft ok, Entdeckung fehlt

    def test_quality_is_capped_below_masterwork(self):
        self.t.char("master", smithing=48000)  # Meisterschaft 9: 250 + 360 + 270 = 880 -> von Hand Meisterstück
        self.t.w.company.hire("boss", self.co, "master", 50)
        self.t.w.inv.deposit(self.p.store_of(self.co), "iron_ore@select", 20)
        jid = self.p.start("boss", self.co, "master", "iron_ingot", 1, "select")
        self.assertEqual(self.p.jobs[jid]["quality"], "fine")


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.t = PW()
        self.p, self.co = self.t.p, self.t.co

    def test_batches_complete_with_yield_upkeep_and_log(self):
        jid = self.p.start("boss", self.co, "smith", "iron_ingot", 2, "standard")
        treasury = self.t.w.company.balance(self.co)
        ev = self.t.days(1)  # Tag 1: Tier 1 = 1 Tag je Charge
        self.assertEqual((self.p.jobs[jid]["done"], self.p.stock(self.co)), (1, {ORE: 160, INGOT: 8}))  # 10 * 1 * 800/1000
        self.assertEqual(self.t.w.inv.holdings(job_owner(jid)), {ORE: 20})
        self.t.days(2)
        self.assertNotIn(jid, self.p.jobs)
        self.assertEqual(self.p.stock(self.co)[INGOT], 16)
        self.assertEqual(self.t.w.inv.balance("world:sink", COIN), 4)  # 2 Chargen * 2 Münzen
        self.assertEqual(self.t.w.inv.holdings(job_owner(jid)), {})
        kinds = [l["kind"] for l in self.t.w.company_registry.get(self.co)["log"]]
        self.assertIn("production_started", kinds)
        self.assertIn("production_done", kinds)
        self.assertEqual(self.p.check(), [])
        self.assertLess(self.t.w.company.balance(self.co), treasury)

    def test_higher_tier_takes_longer_and_costs_more(self):
        self.p.stock_out("boss", self.co, ORE, 100)
        self.t.w.inv.deposit(self.p.store_of(self.co), "iron_ingot@standard", 20)
        self.t.w.inv.deposit(self.p.store_of(self.co), "charcoal@standard", 10)
        jid = self.p.start("boss", self.co, "smith", "iron_blade", 1, "standard")  # Stufe 2: 2 Tage, 5 Münzen
        self.t.days(1)
        self.assertEqual((self.p.jobs[jid]["progress"], self.p.jobs[jid]["done"]), (1, 0))
        self.t.days(2)
        self.assertNotIn(jid, self.p.jobs)
        self.assertEqual(self.p.stock(self.co)["iron_blade@common"], 8)
        self.assertEqual(self.t.w.inv.balance("world:sink", COIN), 5)

    def test_progress_restarts_after_each_batch(self):
        self.p.stock_out("boss", self.co, ORE, 100)
        self.t.w.inv.deposit(self.p.store_of(self.co), "iron_ingot@standard", 40)
        self.t.w.inv.deposit(self.p.store_of(self.co), "charcoal@standard", 20)
        jid = self.p.start("boss", self.co, "smith", "iron_blade", 2, "standard")
        seen = []
        for d in range(1, 5):
            self.t.days(d)
            seen.append(self.p.jobs[jid]["done"] if jid in self.p.jobs else 2)
        self.assertEqual(seen, [0, 1, 1, 2])  # je Charge 2 Tage

    def test_output_quantity_of_multi_output_recipe(self):
        self.t.char("alch", alchemy=100)
        self.t.w.company.hire("boss", self.co, "alch", 50)
        self.p.stock_out("boss", self.co, ORE, 150)
        for k, n in (("healing_herb@standard", 20), ("clean_water@standard", 10)):
            self.t.w.inv.deposit(self.p.store_of(self.co), k, n)
        self.p.start("boss", self.co, "alch", "healing_salve", 1, "standard")
        self.t.days(1)
        self.assertEqual(self.p.stock(self.co)["healing_salve@common"], 16)  # 2 * 10 * 0,8

    def test_no_cee_reports_and_no_profession_progress(self):
        before = (len(self.t.w.svc.log.events("smith")), self.t.w.svc.state("smith").parts["profession"]["xp"])
        self.p.start("boss", self.co, "smith", "iron_ingot", 3, "standard")
        self.t.days(5)
        after = (len(self.t.w.svc.log.events("smith")), self.t.w.svc.state("smith").parts["profession"]["xp"])
        self.assertEqual(before, after)

    def test_worker_gone_or_unpaid_stalls_the_line(self):
        jid = self.p.start("boss", self.co, "smith", "iron_ingot", 2, "standard")
        self.t.w.company.fire("boss", self.co, "smith")
        self.t.days(3)
        j = self.p.jobs[jid]
        self.assertEqual((j["done"], j["stalled"]), (0, 3))
        # unbezahlt: zwei Löhne à 400 bei 1000 in der Kasse -> ab Tag 2 reicht es nicht mehr
        t2 = PW(wage=400, capital=1000, ore=100)
        j2 = t2.p.start("boss", t2.co, "smith", "iron_ingot", 5, "standard")
        t2.days(1)
        self.assertEqual((t2.p.jobs[j2]["done"], t2.p.jobs[j2]["stalled"]), (1, 0))  # Tag 1 bezahlt
        t2.days(4)
        job = t2.p.jobs[j2]
        self.assertGreater(job["stalled"], 0)
        self.assertLess(job["done"], 5)

    def test_storage_full_blocks_completion_until_space_exists(self):
        jid = self.p.start("boss", self.co, "smith", "iron_ingot", 1, "standard")
        self.p.stock_in("boss", self.co, ORE, 20)  # Lager: 180 + 20 = 200 von 200: voll, die Ausgabe (8) passt nicht
        self.t.days(1)
        self.assertEqual((self.p.jobs[jid]["done"], self.p.jobs[jid]["stalled"], self.p.jobs[jid]["progress"]), (0, 1, 1))
        self.t.days(2)  # weiter blockiert: der Fortschritt läuft nicht über die Dauer hinaus
        self.assertEqual((self.p.jobs[jid]["done"], self.p.jobs[jid]["stalled"], self.p.jobs[jid]["progress"]), (0, 2, 1))
        self.p.stock_out("boss", self.co, ORE, 10)
        self.t.days(3)
        self.assertNotIn(jid, self.p.jobs)
        self.assertEqual(self.p.stock(self.co)[INGOT], 8)

    def test_upkeep_missing_blocks_completion(self):
        t = PW(capital=1000, wage=5)
        jid = t.p.start("boss", t.co, "smith", "iron_ingot", 1, "standard")
        store = t.p.store_of(t.co)
        t.w.inv.apply(store, {COIN: t.w.company.balance(t.co) - 10}, {})  # genau die zwei Löhne (2 x 5), nichts für den Betrieb
        t.days(1)
        self.assertEqual((t.p.jobs[jid]["done"], t.p.jobs[jid]["stalled"], t.w.inv.balance(store, COIN)), (0, 1, 0))
        t.w.inv.deposit(store, COIN, 12)  # Löhne + Betriebskosten
        t.days(2)
        self.assertEqual(t.p.jobs.get(jid), None)

    def test_two_jobs_run_in_parallel_with_two_lines(self):
        self.t.w.day[0] = 1
        self.t.w.company.record_revenue(self.co, 10000)
        self.t.w.day[0] = 8
        self.t.days(8)
        self.t.w.company.upgrade_building("boss", self.co)
        a = self.p.start("boss", self.co, "smith", "iron_ingot", 1, "standard")
        b = self.p.start("boss", self.co, "novice", "iron_ingot", 1, "standard")
        self.t.days(9)
        self.assertEqual((a in self.p.jobs, b in self.p.jobs), (False, False))


class CancelSellCloseTests(unittest.TestCase):
    def setUp(self):
        self.t = PW()
        self.p, self.co = self.t.p, self.t.co

    def test_cancel_refunds_unstarted_batches_only(self):
        jid = self.p.start("boss", self.co, "smith", "iron_ingot", 4, "standard")
        self.t.days(1)  # 1 Charge fertig (progress wieder 0)
        self.p.jobs[jid]["progress"] = 1  # eine angefangene Charge
        for who, oid in (("smith", jid), ("boss", "srv1-job-00000099"), ("boss", None)):
            with self.assertRaises(WorldError):
                self.p.cancel(who, self.co, oid)
        refund = self.p.cancel("boss", self.co, jid)
        self.assertEqual(refund, {ORE: 40})  # 3 Restchargen, die angefangene ist verloren: 2 * 20
        self.assertEqual(self.t.w.inv.holdings(job_owner(jid)), {})
        self.assertEqual(self.p.stock(self.co)[ORE], 200 - 80 + 40)
        with self.assertRaises(WorldError):
            self.p.cancel("boss", self.co, jid)
        self.assertEqual(self.p.check(), [])

    def test_other_companys_manager_cannot_cancel_or_use_foreign_jobs(self):
        jid = self.p.start("boss", self.co, "smith", "iron_ingot", 2, "standard")
        self.t.char("rival", trade=700)
        self.t.give("rival", 5000)
        other = self.t.w.company.found("rival", 2000)
        with self.assertRaises(WorldError):
            self.p.cancel("rival", other, jid)
        self.assertIn(jid, self.p.jobs)

    def test_cancel_refund_never_exceeds_storage(self):
        jid = self.p.start("boss", self.co, "smith", "iron_ingot", 4, "standard")  # 80 Erz im Auftrag, Lager: 120
        self.p.stock_in("boss", self.co, ORE, 80)  # Lager voll (200)
        refund = self.p.cancel("boss", self.co, jid)
        self.assertEqual((refund, self.p.used_capacity(self.co)), ({ORE: 80}, 200))
        self.assertEqual(self.t.w.inv.balance("boss", ORE), 1000 - 200 - 80 + 80)  # Rückgabe an den Verwalter, nicht ins volle Lager
        self.assertEqual(self.p.check(), [])

    def test_sell_to_npc_price_cap_and_revenue(self):
        self.t.w.inv.deposit(self.p.store_of(self.co), "iron_blade@fine", 30)  # Referenz 180 -> 60 % = 108
        before_rev = self.t.w.company_registry.get(self.co)["revenue_total"]
        self.assertEqual(self.p.sell_to_npc("boss", self.co, "iron_blade@fine", 10), 1080)
        self.assertEqual(self.t.w.company_registry.get(self.co)["revenue_total"] - before_rev, 1080)
        with self.assertRaises(WorldError):  # Tageslimit 2000: 1080 + 1080 > 2000
            self.p.sell_to_npc("boss", self.co, "iron_blade@fine", 10)
        self.assertEqual(self.p.sell_to_npc("boss", self.co, "iron_blade@fine", 8), 864)  # genau unter dem Limit
        self.t.w.day[0] = 2
        self.assertEqual(self.p.sell_to_npc("boss", self.co, "iron_blade@fine", 10), 1080)  # neuer Tag
        for fn in (lambda: self.p.sell_to_npc("smith", self.co, "iron_blade@fine", 1), lambda: self.p.sell_to_npc("boss", self.co, "iron_blade@fine", 0),
                   lambda: self.p.sell_to_npc("boss", self.co, "iron_blade@fine", 99), lambda: self.p.sell_to_npc("boss", self.co, COIN, 1),
                   lambda: self.p.sell_to_npc("boss", self.co, ORE, 1000)):
            with self.assertRaises(WorldError):
                fn()

    def test_npc_daily_cap_is_inclusive(self):
        store = self.p.store_of(self.co)
        for k, n in (("iron_blade@fine", 18), ("iron_ingot@common", 4), ("iron_ingot@rough", 1), ("bread@rough", 5)):
            self.t.w.inv.deposit(store, k, n)
        got = [self.p.sell_to_npc("boss", self.co, k, n) for k, n in (("iron_blade@fine", 18), ("iron_ingot@common", 4), ("iron_ingot@rough", 1))]
        self.assertEqual((got, sum(got)), ([1944, 48, 8], 2000))  # genau das Tageslimit ist erlaubt
        with self.assertRaises(WorldError):
            self.p.sell_to_npc("boss", self.co, "bread@rough", 5)  # 5 Münzen mehr: nein

    def test_close_returns_goods_and_job_accounts_to_the_founder(self):
        jid = self.p.start("boss", self.co, "smith", "iron_ingot", 3, "standard")
        self.t.days(1)
        before_goods = self.t.w.inv.total(ORE) + self.t.w.inv.total(INGOT)
        self.t.w.company.close_company("boss", self.co)
        self.assertEqual((self.p.jobs, self.p.stock(self.co), self.t.w.inv.holdings(job_owner(jid))), ({}, {}, {}))
        self.assertEqual(self.t.w.inv.balance("boss", INGOT), 8)
        self.assertEqual(self.t.w.inv.total(ORE) + self.t.w.inv.total(INGOT), before_goods)  # nichts geht verloren
        self.assertEqual(self.p.check(), [])

    def test_hooks_do_nothing_for_companies_without_production(self):
        w = PW(ore=0)
        w.days(3)
        self.assertFalse(w.p.active)
        self.assertNotIn("production", w.w.snapshot())


class InvariantTests(unittest.TestCase):
    def setUp(self):
        self.t = PW()
        self.p, self.co = self.t.p, self.t.co
        self.jid = self.p.start("boss", self.co, "smith", "iron_ingot", 3, "standard")

    def test_check_detects_each_kind_of_damage(self):
        self.assertEqual(self.p.check(), [])
        j = self.p.jobs[self.jid]
        j["done"] = 3
        self.assertTrue(any("Fortschritt" in m for m in self.p.check()))
        j["done"] = 0
        j["progress"] = -1
        self.assertTrue(any("Fortschritt" in m for m in self.p.check()))
        j["progress"] = 0
        self.t.w.inv.deposit(job_owner(self.jid), ORE, 1)
        self.assertTrue(any("deckt" in m for m in self.p.check()))
        self.t.w.inv.apply(job_owner(self.jid), {ORE: 1}, {})
        self.t.w.inv.deposit("production:srv1-job-00000042", ORE, 1)
        self.assertEqual(len(self.p.check()), 1)
        self.assertIn("ohne Auftrag", self.p.check()[0])
        self.t.w.inv.apply("production:srv1-job-00000042", {ORE: 1}, {})
        self.t.w.company_registry.get(self.co)["open"] = False
        self.assertTrue(any("geschlossen" in m for m in self.p.check()))

    def test_load_rejects_damaged_state_and_accepts_good(self):
        text = self.p.to_json()
        self.t.w.inv.deposit(job_owner(self.jid), ORE, 1)
        with self.assertRaises(WorldError):
            self.p.load(text)
        self.t.w.inv.apply(job_owner(self.jid), {ORE: 1}, {})
        self.p.load(text)


class PropertyTests(unittest.TestCase):
    def test_random_operations_keep_invariants(self):
        for seed in (1, 2, 3):
            t = PW()
            p, co, rng = t.p, t.co, Rng(seed)
            day = 1
            for step in range(120):
                k = rng.below(9)
                try:
                    if k == 0:
                        p.start("boss", co, rng.pick(["smith", "novice"]), "iron_ingot", 1 + rng.below(4), "standard")
                    elif k == 1 and p.jobs:
                        p.cancel("boss", co, rng.pick(sorted(p.jobs)))
                    elif k == 2:
                        p.stock_in("boss", co, ORE, 1 + rng.below(80))
                    elif k == 3:
                        p.stock_out("boss", co, rng.pick([ORE, INGOT]), 1 + rng.below(40))
                    elif k == 4:
                        p.sell_to_npc("boss", co, INGOT, 1 + rng.below(20))
                    elif k == 5:
                        t.w.company.record_revenue(co, 100)
                    else:
                        day += 1 + rng.below(2)
                        t.days(day)
                except WorldError:
                    pass
                self.assertEqual(p.check(), [], (seed, step))
                self.assertLessEqual(p.used_capacity(co), p.capacity(t.w.company_registry.get(co)))
            revenue = t.w.company_registry.get(co)["revenue_total"]
            self.assertEqual(t.coins_total(), t.minted + revenue)


class PersistenceTests(unittest.TestCase):
    def test_roundtrip_continue_and_tampering(self):
        t = PW()
        t.p.start("boss", t.co, "smith", "iron_ingot", 3, "standard")
        t.days(2)
        e, logs = persistence.export_world(t.w)
        loaded = persistence.import_world(json.loads(json.dumps(e)), json.loads(json.dumps(logs)))
        self.assertEqual(loaded.snapshot(), t.w.snapshot())
        self.assertIn("production", loaded.snapshot())
        for w in (t.w, loaded):
            w.day[0] = 3
            w.company.advance_day(3)
        self.assertEqual(loaded.snapshot(), t.w.snapshot())
        # stimmiger Hash, aber Auftragskonto manipuliert
        import copy
        bad = copy.deepcopy(e)
        jid = next(iter(bad["world"]["production"]["jobs"]))
        bad["world"]["inventory"][f"production:{jid}"]["iron_ore@standard"] += 1
        bad["world_sha256"] = persistence._sha(bad["world"])
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)
        bad = copy.deepcopy(e)
        bad["world"]["production"]["jobs"][jid]["done"] = 3
        bad["world_sha256"] = persistence._sha(bad["world"])
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)

    def test_store(self):
        t = PW()
        t.p.start("boss", t.co, "smith", "iron_ingot", 2, "standard")
        with tempfile.TemporaryDirectory() as d:
            s = persistence.Store(d)
            s.commit(t.w)
            self.assertEqual(s.load().snapshot(), t.w.snapshot())


if __name__ == "__main__":
    unittest.main()
