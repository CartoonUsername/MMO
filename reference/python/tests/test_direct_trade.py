import copy
import json
import unittest

from mmo_cee import RuleViolation
from mmo_server import Gateway, Sessions
from mmo_world import WorldError, persistence
from mmo_world.direct_trade import ESCROW, SINK, load_trade_rules, validate_trade_rules
from mmo_world.golden import Rng
from mmo_world.world import World

COIN, FINE = "coin@gold", "iron_blade@fine"  # Referenz 180 je Stück


def world(chars="abc", coins=5000, blades=30):
    w = World()
    for c in chars:
        w.svc.create(c, "player")
        w.inv.deposit(c, COIN, coins)
        w.inv.deposit(c, FINE, blades)
    return w


def totals(w):
    keys = {k for st in w.inv._stacks.values() for k in st}
    return {k: w.inv.total(k) for k in keys}


class RulesTests(unittest.TestCase):
    def test_validation(self):
        w = World()
        tr = load_trade_rules()
        validate_trade_rules(tr, w.svc.rules)
        for key, bad in (("fee_permille", 1001), ("fee_permille", -1), ("offer_days", 0), ("max_open_offers", 0),
                         ("max_incoming_offers", True), ("requires_cee_rules_min", 99)):
            with self.subTest(key):
                with self.assertRaises(WorldError):
                    validate_trade_rules(dict(tr, **{key: bad}), w.svc.rules)


class MakeTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.o = self.w.offers

    def test_sell_offer_escrows_goods_buy_offer_escrows_coins(self):
        a = self.o.make("a", "b", "sell", FINE, 3, 540)
        b = self.o.make("b", "a", "buy", FINE, 2, 400)
        self.assertEqual((a, b), ("srv1-off-00000001", "srv1-off-00000002"))
        self.assertEqual(self.w.inv.holdings(ESCROW), {FINE: 3, COIN: 400})
        self.assertEqual((self.w.inv.balance("a", FINE), self.w.inv.balance("b", COIN)), (27, 4600))
        self.assertEqual(self.o.open_offers("a"), {"outgoing": [a], "incoming": [b]})
        self.assertEqual(self.o.check(), [])

    def test_rejections_change_nothing(self):
        before = (self.w.inv.to_json(), self.o._counter, self.o.to_json())
        bad = [("a", "a", "sell", FINE, 1, 100), ("a", "ghost", "sell", FINE, 1, 100), ("ghost", "a", "sell", FINE, 1, 100),
               ("a", "b", "swap", FINE, 1, 100), ("a", "b", "sell", FINE, 0, 100), ("a", "b", "sell", FINE, True, 100),
               ("a", "b", "sell", FINE, 1001, 100), ("a", "b", "sell", FINE, 1, 0), ("a", "b", "sell", FINE, 1, True),
               ("a", "b", "sell", FINE, 1, 10**8), ("a", "b", "sell", "iron_blade", 1, 100), ("a", "b", "sell", "ghost@fine", 1, 100),
               ("a", "b", "sell", FINE, 31, 100), ("a", "b", "buy", FINE, 1, 5001), ("a", 5, "sell", FINE, 1, 100), ("a", None, "sell", FINE, 1, 100)]
        for args in bad:
            with self.subTest(args=args):
                with self.assertRaises(WorldError):
                    self.o.make(*args)
        self.assertEqual((self.w.inv.to_json(), self.o._counter, self.o.to_json()), before)

    def test_limits(self):
        for _ in range(5):
            self.o.make("a", "b", "sell", FINE, 1, 180)
        with self.assertRaisesRegex(WorldError, "Zu viele"):
            self.o.make("a", "c", "sell", FINE, 1, 180)
        for _ in range(5):
            self.o.make("c", "b", "sell", FINE, 1, 180)
        self.w.svc.create("d", "player")
        self.w.inv.deposit("d", FINE, 5)
        with self.assertRaisesRegex(WorldError, "gegenseite|Gegenseite"):
            self.o.make("d", "b", "sell", FINE, 1, 180)  # b hat 10 eingehende
        self.o.make("d", "a", "sell", FINE, 1, 180)  # andere Gegenseite ist frei

    def test_free_price_is_allowed(self):
        self.o.make("a", "b", "sell", FINE, 1, 1)
        self.o.make("a", "b", "sell", FINE, 1, 10**6)


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.o = self.w.offers

    def test_accept_trades_with_reports_and_fee(self):
        oid = self.o.make("a", "b", "sell", FINE, 2, 360)
        s = self.o.accept("b", oid)
        self.assertEqual((s.fee, s.trade.price, s.trade.reference, s.trade.quantity), (7, 360, 360, 2))  # 360 * 20 // 1000
        self.assertEqual((self.w.inv.balance("a", COIN), self.w.inv.balance("b", COIN)), (5000 + 360 - 7, 5000 - 360))
        self.assertEqual((self.w.inv.balance("a", FINE), self.w.inv.balance("b", FINE)), (28, 32))
        self.assertEqual(self.w.inv.balance(SINK, COIN), 7)
        self.assertEqual(self.w.inv.holdings(ESCROW), {})
        for cid, role in (("a", "seller"), ("b", "buyer")):
            ev = self.w.svc.log.events(cid)[-1]
            self.assertEqual((ev.type, ev.payload["role"], ev.payload["value"], ev.payload["counterparty"]),
                             ("economy.trade_completed", role, 360, "b" if cid == "a" else "a"))
        self.assertEqual(self.o.offers, {})

    def test_buy_offer_roles_and_fee_payer(self):
        oid = self.o.make("b", "a", "buy", FINE, 3, 500)
        s = self.o.accept("a", oid)
        self.assertEqual(s.fee, 10)
        self.assertEqual((self.w.inv.balance("a", COIN), self.w.inv.balance("b", COIN), self.w.inv.balance("b", FINE)), (5000 + 500 - 10, 4500, 33))
        self.assertEqual(self.w.svc.log.events("a")[-1].payload["role"], "seller")  # der Annehmende verkauft und trägt die Gebühr

    def test_only_the_addressee_may_accept_or_decline_and_only_the_sender_may_cancel(self):
        oid = self.o.make("a", "b", "sell", FINE, 1, 180)
        before = (self.w.inv.to_json(), self.o.to_json())
        for fn in (lambda: self.o.accept("c", oid), lambda: self.o.accept("a", oid), lambda: self.o.decline("c", oid),
                   lambda: self.o.decline("a", oid), lambda: self.o.cancel("b", oid), lambda: self.o.cancel("c", oid),
                   lambda: self.o.accept("b", "nope"), lambda: self.o.accept("b", None), lambda: self.o.cancel("a", 5)):
            with self.assertRaises(WorldError):
                fn()
        self.assertEqual((self.w.inv.to_json(), self.o.to_json()), before)

    def test_decline_and_cancel_refund(self):
        o1 = self.o.make("a", "b", "sell", FINE, 2, 360)
        o2 = self.o.make("b", "a", "buy", FINE, 2, 360)
        self.o.decline("b", o1)
        self.o.cancel("b", o2)
        self.assertEqual((self.w.inv.balance("a", FINE), self.w.inv.balance("b", COIN), self.w.inv.holdings(ESCROW)), (30, 5000, {}))
        with self.assertRaises(WorldError):
            self.o.cancel("b", o2)

    def test_failed_accept_keeps_the_offer_and_the_escrow(self):
        oid = self.o.make("a", "c", "sell", FINE, 3, 4000)
        self.w.inv.apply("c", {COIN: 4500}, {})  # c hat nur noch 500 Münzen
        before = (self.w.inv.to_json(), self.o.to_json())
        with self.assertRaises(WorldError):
            self.o.accept("c", oid)
        self.assertEqual(self.w.inv.holdings(ESCROW), {FINE: 3})
        self.assertEqual((self.w.inv.to_json(), self.o.offers.keys()), (before[0], json.loads(before[1])["offers"].keys()))
        self.w.inv.deposit("c", COIN, 4000)
        self.o.accept("c", oid)

    def test_cee_rejection_keeps_the_offer(self):
        from mmo_world.persistence import upgrade_world
        mixed = upgrade_world(world("ab"), "rules_v8.json", ["a"])  # b bleibt auf v7 zurück
        oid = mixed.offers.make("a", "b", "sell", FINE, 1, 180)
        with self.assertRaises(RuleViolation):
            mixed.offers.accept("b", oid)
        self.assertEqual((list(mixed.offers.offers), mixed.inv.holdings(ESCROW)), ([oid], {FINE: 1}))
        mixed.svc.migrate("b")
        mixed.offers.accept("b", oid)

    def test_expiry_boundaries(self):
        oid = self.o.make("a", "b", "sell", FINE, 1, 180)  # Tag 1 + 3 Tage -> gilt bis Tag 3, ab Tag 4 abgelaufen
        self.w.day[0] = 3
        self.assertEqual(self.o.expire(3), [])
        self.w.day[0] = 4
        with self.assertRaisesRegex(WorldError, "abgelaufen"):
            self.o.accept("b", oid)
        self.assertEqual(self.o.expire(4), [oid])
        self.assertEqual((self.w.inv.balance("a", FINE), self.w.inv.holdings(ESCROW)), (30, {}))
        for bad in (-1, True, "3", 1.0):
            with self.assertRaises(WorldError):
                self.o.expire(bad)

    def test_accept_on_the_last_valid_day(self):
        oid = self.o.make("a", "b", "sell", FINE, 1, 180)
        self.w.day[0] = 3
        self.o.accept("b", oid)

    def test_wash_trading_between_alts_earns_nothing_at_absurd_prices(self):
        oid = self.o.make("a", "b", "sell", FINE, 1, 1)
        self.o.accept("b", oid)
        self.assertEqual(self.w.svc.state("a").parts["economy"]["points"]["volume"], 0)

    def test_fee_rounds_down_and_can_be_zero(self):
        oid = self.o.make("a", "b", "sell", FINE, 1, 49)
        self.assertEqual(self.o.accept("b", oid).fee, 0)  # 49 * 20 // 1000


class InvariantTests(unittest.TestCase):
    def test_check_detects_damage_and_load_rejects_it(self):
        w = world()
        w.offers.make("a", "b", "sell", FINE, 3, 540)
        text = w.offers.to_json()
        w.inv.deposit(ESCROW, COIN, 1)
        self.assertTrue(w.offers.check())
        with self.assertRaises(WorldError):
            w.offers.load(text)
        w.inv.apply(ESCROW, {COIN: 1}, {})
        w.offers.load(text)
        w.offers.offers["srv1-off-00000001"]["to"] = "a"
        self.assertTrue(any("sich selbst" in m for m in w.offers.check()))

    def test_random_operations_conserve_everything(self):
        for seed in (1, 2, 3):
            w = world("abcd")
            o, rng = w.offers, Rng(seed)
            start, fees = totals(w), 0
            day = 1
            for step in range(150):
                who, other = rng.pick(list("abcd")), rng.pick(list("abcd"))
                k = rng.below(8)
                try:
                    if k < 3:
                        o.make(who, other, rng.pick(["sell", "buy"]), FINE, 1 + rng.below(4), 1 + rng.below(800))
                    elif k < 5 and o.offers:
                        oid = rng.pick(sorted(o.offers))
                        fees += o.accept(o.offers[oid]["to"] if rng.below(5) else who, oid).fee
                    elif k == 5 and o.offers:
                        oid = rng.pick(sorted(o.offers))
                        (o.decline if rng.below(2) else o.cancel)(o.offers[oid]["to" if rng.below(2) else "from"], oid)
                    elif k == 6:
                        day += 1 + rng.below(2)
                        w.day[0] = day
                        o.expire(day)
                except WorldError:
                    pass
                self.assertEqual(o.check(), [], (seed, step))
            self.assertEqual(totals(w), start)
            self.assertEqual(w.inv.balance(SINK, COIN), fees)


class PersistenceTests(unittest.TestCase):
    def test_roundtrip_continue_and_tamper(self):
        w = world()
        w.offers.make("a", "b", "sell", FINE, 3, 540)
        w.offers.make("b", "c", "buy", FINE, 1, 200)
        e, logs = persistence.export_world(w)
        loaded = persistence.import_world(json.loads(json.dumps(e)), json.loads(json.dumps(logs)))
        self.assertEqual(loaded.snapshot(), w.snapshot())
        self.assertIn("trade_offers", loaded.snapshot())
        for x in (w, loaded):
            x.offers.accept("b", "srv1-off-00000001")
        self.assertEqual(loaded.snapshot(), w.snapshot())
        bad = copy.deepcopy(e)
        bad["world"]["inventory"][ESCROW][COIN] += 1
        bad["world_sha256"] = persistence._sha(bad["world"])
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)
        bad = copy.deepcopy(e)
        bad["world"]["trade_offers"]["offers"]["srv1-off-00000002"]["price"] = 999  # Kaufangebot: Hinterlegung = Preis
        bad["world_sha256"] = persistence._sha(bad["world"])
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)
        bad = copy.deepcopy(e)
        bad["world"]["trade_offers"]["offers"]["srv1-off-00000001"]["qty"] = 9  # Verkaufsangebot: Hinterlegung = Menge
        bad["world_sha256"] = persistence._sha(bad["world"])
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)
        bad = copy.deepcopy(e)
        bad["rules"]["trade_sha256"] = "0" * 64
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)
        self.assertNotIn("trade_offers", world().snapshot())


class GatewayTests(unittest.TestCase):
    def test_offer_accept_decline_cancel_and_query(self):
        w = world()
        s = Sessions()
        sa, sb = s.open("acc-a", ["a"]), s.open("acc-b", ["b"])
        g = Gateway(w, s, lambda: 0)

        def call(sess, rid, cmd, **args):
            return g.handle(sess, {"v": 1, "id": rid, "cmd": cmd, "args": args})

        r = call(sa, "1", "trade.offer", char="a", to="b", side="sell", item_key=FINE, qty=2, price=360)
        self.assertTrue(r["ok"], r)
        oid = r["result"]
        q = call(sb, "2", "query.offers", char="b")
        self.assertEqual([o["id"] for o in q["result"]["incoming"]], [oid])
        self.assertEqual(call(sa, "3", "query.offers", char="b")["error"]["code"], "forbidden")  # fremde Angebote sind privat
        self.assertEqual(call(sa, "4", "trade.accept", char="a", offer=oid)["error"]["code"], "rejected")  # nicht die Adressatin
        self.assertEqual(call(sb, "5", "trade.accept", char="a", offer=oid)["error"]["code"], "forbidden")  # fremde Figur
        done = call(sb, "6", "trade.accept", char="b", offer=oid)
        self.assertTrue(done["ok"] and done["result"]["fee"] == 7, done)
        self.assertEqual(call(sb, "6", "trade.accept", char="b", offer=oid), {**done, "replayed": True})  # Wiederholung ohne Wirkung
        o2 = call(sb, "7", "trade.offer", char="b", to="a", side="buy", item_key=FINE, qty=1, price=180)["result"]
        self.assertTrue(call(sa, "8", "trade.decline", char="a", offer=o2)["ok"])
        o3 = call(sa, "9", "trade.offer", char="a", to="b", side="sell", item_key=FINE, qty=1, price=180)["result"]
        self.assertTrue(call(sa, "10", "trade.cancel", char="a", offer=o3)["ok"])
        for bad in ({"side": "swap"}, {"qty": 0}, {"to": "a"}, {"price": "1"}):
            args = dict(char="a", to="b", side="sell", item_key=FINE, qty=1, price=100) | bad
            self.assertFalse(call(sa, "x" + str(len(str(bad))) + next(iter(bad)), "trade.offer", **args)["ok"])
        self.assertEqual(w.offers.check(), [])


if __name__ == "__main__":
    unittest.main()
