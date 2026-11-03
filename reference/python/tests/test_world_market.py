import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.rules import load_rules
from mmo_world import CraftingService, Inventory, TradeService, WorldError

RULES = load_rules("rules_v7.json")
COIN = "coin@gold"


class World:
    def __init__(self):
        self.svc = CharacterService(rules=RULES)
        self.inv = Inventory()
        self.day = [1]
        self.ts = TradeService(self.svc, self.inv, lambda: self.day[0])
        self.cs = CraftingService(self.svc, self.inv, lambda: self.day[0])

    def char(self, cid, kind="player", xp=10000, **prof):
        self.svc.create(cid, kind)
        self.svc.record(cid, "identity.xp_gained", {"amount": xp})
        for p, x in prof.items():
            self.svc.record(cid, "profession.work", {"profession": p, "xp": x})

    def give(self, cid, item_key, qty):
        self.inv.deposit(cid, item_key, qty)


class InventoryApplyManyTests(unittest.TestCase):
    def test_atomic_across_owners(self):
        inv = Inventory()
        inv.deposit("a", "x@1", 5)
        inv.deposit("b", "c@g", 10)
        inv.apply_many([("a", {"x@1": 2}, {"c@g": 7}), ("b", {"c@g": 7}, {"x@1": 2})])
        self.assertEqual((inv.holdings("a"), inv.holdings("b")), ({"c@g": 7, "x@1": 3}, {"c@g": 3, "x@1": 2}))

    def test_nothing_changes_if_any_removal_fails(self):
        inv = Inventory()
        inv.deposit("a", "x@1", 5)
        before = inv.to_json()
        with self.assertRaises(WorldError):
            inv.apply_many([("a", {"x@1": 5}, {}), ("b", {"c@g": 1}, {"x@1": 5})])  # b hat keine Münzen
        self.assertEqual(inv.to_json(), before)

    def test_summed_removals_per_owner_are_checked(self):
        inv = Inventory()
        inv.deposit("a", "x@1", 5)
        before = inv.to_json()
        with self.assertRaises(WorldError):
            inv.apply_many([("a", {"x@1": 3}, {}), ("a", {"x@1": 3}, {})])  # zusammen 6 > 5
        self.assertEqual(inv.to_json(), before)

    def test_invalid_entries_rejected_before_any_change(self):
        inv = Inventory()
        inv.deposit("a", "x@1", 5)
        before = inv.to_json()
        with self.assertRaises(WorldError):
            inv.apply_many([("a", {"x@1": 1}, {}), ("b", {}, {"y@1": 0})])
        self.assertEqual(inv.to_json(), before)


class TradeFlowTests(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.w.char("seller")
        self.w.char("buyer")
        self.w.give("seller", "iron_blade@fine", 5)
        self.w.give("buyer", COIN, 1000)

    def test_successful_trade_moves_goods_and_coins_and_reports_both_sides(self):
        r = self.w.ts.trade("seller", "buyer", "iron_blade@fine", 2, 360)
        self.assertEqual(self.w.inv.holdings("seller"), {"coin@gold": 360, "iron_blade@fine": 3})
        self.assertEqual(self.w.inv.holdings("buyer"), {"coin@gold": 640, "iron_blade@fine": 2})
        self.assertEqual((r.reference, r.price, r.quantity), (360, 360, 2))
        s, b = r.seller_event.payload, r.buyer_event.payload
        self.assertEqual((s["role"], s["counterparty"], b["role"], b["counterparty"]), ("seller", "buyer", "buyer", "seller"))
        self.assertEqual(s["trade_id"], b["trade_id"])
        self.assertTrue(s["trade_id"].startswith("srv1-trade-"))
        for cid in ("seller", "buyer"):
            self.assertEqual(self.w.svc.state(cid).parts["economy"]["points"], {"volume": 36, "network": 200})

    def test_failures_change_nothing(self):
        before = (self.w.inv.to_json(), len(self.w.svc.log.events("seller")), len(self.w.svc.log.events("buyer")))
        bad = [("seller", "seller", "iron_blade@fine", 1, 100),  # Handel mit sich selbst
               ("seller", "buyer", "iron_blade@fine", 6, 100),  # Verkäufer besitzt zu wenig
               ("seller", "buyer", "iron_blade@fine", 1, 2000),  # Käufer besitzt zu wenig Münzen
               ("seller", "buyer", "ghost@fine", 1, 100), ("seller", "buyer", "iron_blade@legend", 1, 100),
               ("seller", "buyer", "iron_blade", 1, 100), ("seller", "buyer", "iron_blade@fine@x", 1, 100),
               ("seller", "buyer", 5, 1, 100), ("seller", "buyer", "coin@gold", 1, 100),  # Währung nicht als Ware
               ("seller", "buyer", "iron_blade@fine", 0, 100), ("seller", "buyer", "iron_blade@fine", -1, 100),
               ("seller", "buyer", "iron_blade@fine", True, 100), ("seller", "buyer", "iron_blade@fine", 1.5, 100),
               ("seller", "buyer", "iron_blade@fine", 1, 0), ("seller", "buyer", "iron_blade@fine", 1, -5),
               ("seller", "buyer", "iron_blade@fine", 1, True), ("seller", "buyer", "iron_blade@fine", 1, 10.5),
               ("seller", "buyer", "iron_blade@fine", 1001, 100), ("seller", "buyer", "iron_blade@fine", 1, 10_000_001)]
        for args in bad:
            with self.subTest(args=args):
                with self.assertRaises(WorldError):
                    self.w.ts.trade(*args)
        self.assertEqual((self.w.inv.to_json(), len(self.w.svc.log.events("seller")), len(self.w.svc.log.events("buyer"))), before)

    def test_error_messages_name_the_cause(self):
        with self.assertRaisesRegex(WorldError, "Münzen"):
            self.w.ts.trade("seller", "buyer", "iron_blade@fine", 1, 2000)
        with self.assertRaisesRegex(WorldError, "Verkäufer"):
            self.w.ts.trade("seller", "buyer", "iron_blade@fine", 6, 100)
        with self.assertRaisesRegex(WorldError, "verschiedene"):
            self.w.ts.trade("seller", "seller", "iron_blade@fine", 1, 100)

    def test_unknown_character_is_rejected_without_changes(self):
        self.w.give("ghost", "iron_blade@fine", 1)
        before = self.w.inv.to_json()
        with self.assertRaises((WorldError, RuleViolation)):
            self.w.ts.trade("ghost", "buyer", "iron_blade@fine", 1, 120)
        self.assertEqual(self.w.inv.to_json(), before)

    def test_cee_rejection_never_touches_inventory(self):
        self.w.ts.trade("seller", "buyer", "iron_blade@fine", 1, 180)
        calls = []
        original = self.w.inv.apply_many
        self.w.inv.apply_many = lambda *a, **k: (calls.append(a), original(*a, **k))[1]
        self.w.day[0] = 0  # Tag springt zurück: die CEE lehnt ab
        with self.assertRaises(RuleViolation):
            self.w.ts.trade("seller", "buyer", "iron_blade@fine", 1, 180)
        self.assertEqual(calls, [])  # Vorabprüfung beider Berichte: Inventar nie angefasst
        self.w.inv.apply_many = original

    def test_inventory_is_restored_if_recording_fails(self):
        before = self.w.inv.to_json()
        original = self.w.svc.record

        def failing(cid, type_, payload):
            if cid == "buyer":
                raise RuleViolation("simulierter Ausfall")
            return original(cid, type_, payload)

        self.w.svc.record = failing
        with self.assertRaises(RuleViolation):
            self.w.ts.trade("seller", "buyer", "iron_blade@fine", 2, 360)
        self.w.svc.record = original
        self.assertEqual(self.w.inv.to_json(), before)  # Ware und Münzen zurückgebucht

    def test_trade_ids_unique_and_server_issued(self):
        ids = {self.w.ts.trade("seller", "buyer", "iron_blade@fine", 1, 180).trade_id for _ in range(4)}
        self.assertEqual(len(ids), 4)

    def test_npc_trades_like_a_player_and_replay_matches(self):
        self.w.char("npc1", kind="npc")
        self.w.give("npc1", "iron_blade@fine", 2)
        self.w.ts.trade("npc1", "buyer", "iron_blade@fine", 1, 180)
        live = copy.deepcopy(self.w.svc.state("npc1").parts)
        self.assertEqual(self.w.svc.rebuild("npc1").parts, live)
        self.assertEqual(live["identity"]["kind"], "npc")

    def test_deterministic_across_worlds(self):
        out = []
        for _ in range(2):
            w = World()
            w.char("s")
            w.char("b")
            w.give("s", "iron_blade@fine", 5)
            w.give("b", COIN, 1000)
            for _ in range(3):
                w.ts.trade("s", "b", "iron_blade@fine", 1, 180)
            out.append((w.svc.log.events("s")[-1].hash, w.inv.to_json()))
        self.assertEqual(out[0], out[1])


class ConservationTests(unittest.TestCase):
    def test_goods_and_coins_are_conserved_over_many_trades(self):
        w = World()
        names = [f"c{i}" for i in range(6)]
        for n in names:
            w.char(n)
            w.give(n, "iron_blade@fine", 10)
            w.give(n, "bread@common", 50)
            w.give(n, COIN, 2000)
        totals = {k: w.inv.total(k) for k in ("iron_blade@fine", "bread@common", COIN)}
        x = 12345
        for i in range(300):  # deterministischer LCG, viele (teils fehlschlagende) Handel
            x = (1103515245 * x + 12345) % 2**31
            s, b = names[x % 6], names[(x // 7) % 6]
            item = ["iron_blade@fine", "bread@common"][(x // 13) % 2]
            qty, price = 1 + (x // 17) % 4, 1 + (x // 19) % 700
            w.day[0] = 1 + i // 20
            try:
                w.ts.trade(s, b, item, qty, price)
            except WorldError:
                pass
            for k, t in totals.items():
                self.assertEqual(w.inv.total(k), t, k)  # nichts entsteht, nichts verschwindet
            for n in names:
                self.assertTrue(all(v > 0 for v in w.inv.holdings(n).values()))  # nie negativ, keine leeren Stapel


class WashTradingEndToEndTests(unittest.TestCase):
    def test_alt_accounts_cannot_farm_progress(self):
        w = World()
        w.char("x")
        w.char("y")
        w.give("x", "iron_blade@common", 1)
        w.give("y", COIN, 10)
        w.give("x", COIN, 10)
        w.give("y", "iron_blade@common", 1)
        # die beiden Zweitaccounts reichen dieselbe Klinge zum Referenzpreis hin und her
        for i in range(40):
            seller, buyer = ("x", "y") if i % 2 == 0 else ("y", "x")
            w.give(buyer, COIN, 120)  # serverinterne Münzquelle, damit die Zahlung möglich bleibt
            w.ts.trade(seller, buyer, "iron_blade@common", 1, 120)
        for cid in ("x", "y"):
            part = w.svc.state(cid).parts["economy"]
            self.assertEqual(part["points"]["network"], 200)  # ein Partner -> nur ein Bonus
            self.assertLess(part["points"]["volume"], 12 * 6 + 20)  # Wiederholungsabnahme: weit unter 40 x 12

    def test_absurd_price_between_alts_earns_nothing(self):
        w = World()
        w.char("x")
        w.char("y")
        w.give("x", "bread@common", 10)
        w.give("y", COIN, 1_000_000)
        for _ in range(10):
            w.ts.trade("x", "y", "bread@common", 1, 100_000)
        for cid in ("x", "y"):
            self.assertEqual(w.svc.state(cid).parts["economy"]["points"], {"volume": 0, "network": 0})


class CraftAndSellTests(unittest.TestCase):
    def test_crafted_goods_can_be_sold_at_their_reference_value(self):
        w = World()
        w.char("smith")
        w.char("customer")
        w.give("smith", "iron_ore@standard", 40)
        w.give("customer", COIN, 500)
        made = w.cs.craft("smith", "iron_ingot", 10, "standard")
        (item_key, qty), = made.produced.items()
        self.assertEqual((item_key, qty), ("iron_ingot@common", 10))
        r = w.ts.trade("smith", "customer", item_key, qty, 200)  # 10 x 20
        self.assertEqual(r.reference, 200)
        self.assertEqual(w.inv.balance("customer", item_key), 10)
        self.assertEqual(w.inv.balance("smith", COIN), 200)


if __name__ == "__main__":
    unittest.main()
