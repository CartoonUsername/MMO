import copy
import json
import unittest

from mmo_world import WorldError, persistence
from mmo_world.exchange import ESCROW, SINK, Exchange, load_market_rules, validate_market_rules
from mmo_world.golden import Rng
from mmo_world.world import World

COIN = "coin@gold"
FINE = "iron_blade@fine"  # Referenz 180 je Stück (120 * 1,5)


def world(chars=("a", "b", "c"), coins=10000, blades=20):
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
    def test_default_rules_valid_and_bad_ones_rejected(self):
        w = World()
        mr = load_market_rules()
        validate_market_rules(mr, w.svc.rules)
        for key, bad in (("fee_permille", 1001), ("band_permille", -1), ("ema_alpha_permille", True), ("order_days", 0),
                         ("max_open_orders", 0), ("history_days", 0), ("requires_cee_rules_min", 99)):
            with self.subTest(key):
                broken = dict(mr, **{key: bad})
                with self.assertRaises(WorldError):
                    validate_market_rules(broken, w.svc.rules)


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.x = self.w.exchange

    def test_resting_orders_are_escrowed_and_quoted(self):
        r = self.x.place("a", "sell", FINE, 5, 190)
        self.assertEqual((r.order_id, r.fills, r.remaining), ("srv1-ord-00000001", [], 5))
        self.x.place("b", "buy", FINE, 3, 170)
        self.assertEqual(self.w.inv.balance("a", FINE), 15)
        self.assertEqual(self.w.inv.holdings(ESCROW), {COIN: 510, FINE: 5})
        self.assertEqual(self.x.quote(FINE), {"best_bid": 170, "best_ask": 190, "bid_depth": 3, "ask_depth": 5, "last": None, "ema": None})
        self.assertEqual(self.x.check(), [])

    def test_full_match_at_resting_price_with_refund_and_fee(self):
        self.x.place("a", "sell", FINE, 5, 170)
        r = self.x.place("b", "buy", FINE, 5, 200)  # bietet mehr, zahlt aber den Preis der wartenden Order
        f = r.fills[0]
        self.assertEqual((f.unit_price, f.quantity, f.total, f.fee, f.seller, f.buyer), (170, 5, 850, 17, "a", "b"))
        self.assertEqual((r.order_id, r.remaining), (None, 0))
        self.assertEqual(self.w.inv.balance("b", COIN), 10000 - 850)
        self.assertEqual(self.w.inv.balance("b", FINE), 25)
        self.assertEqual(self.w.inv.balance("a", COIN), 10000 + 850 - 17)
        self.assertEqual(self.w.inv.balance(SINK, COIN), 17)
        self.assertEqual((self.x.orders, self.w.inv.holdings(ESCROW)), ({}, {}))
        # CEE: beide Seiten haben einen Handelsbericht
        for cid, role in (("a", "seller"), ("b", "buyer")):
            ev = self.w.svc.log.events(cid)[-1]
            self.assertEqual((ev.type, ev.payload["role"], ev.payload["value"], ev.payload["trade_id"]),
                             ("economy.trade_completed", role, 850, f.trade_id))

    def test_partial_fills_both_ways(self):
        self.x.place("a", "sell", FINE, 3, 180)
        r = self.x.place("b", "buy", FINE, 5, 180)
        self.assertEqual((r.remaining, [f.quantity for f in r.fills]), (2, [3]))
        self.assertEqual(self.x.orders[r.order_id]["remaining"], 2)
        self.assertEqual(self.w.inv.holdings(ESCROW), {COIN: 360})
        r2 = self.x.place("c", "sell", FINE, 7, 175)  # trifft die Rest-Kauforder (zum Preis der wartenden Order: 180)
        self.assertEqual((r2.fills[0].unit_price, r2.fills[0].quantity, r2.remaining), (180, 2, 5))
        self.assertEqual(self.x.check(), [])

    def test_price_time_priority(self):
        self.x.place("a", "sell", FINE, 2, 180)   # 1
        self.x.place("b", "sell", FINE, 2, 175)   # 2: besserer Preis
        self.x.place("c", "sell", FINE, 2, 180)   # 3: gleicher Preis, später
        self.w.svc.create("d", "player")
        self.w.inv.deposit("d", COIN, 10000)
        res = self.x.place("d", "buy", FINE, 5, 180)
        self.assertEqual([(f.seller, f.quantity, f.unit_price) for f in res.fills], [("b", 2, 175), ("a", 2, 180), ("c", 1, 180)])
        self.x.place("a", "buy", FINE, 1, 150)
        self.x.place("b", "buy", FINE, 1, 160)
        self.x.place("c", "buy", FINE, 1, 160)
        res = self.x.place("d", "sell", FINE, 3, 150)
        self.assertEqual([(f.buyer, f.unit_price) for f in res.fills], [("b", 160), ("c", 160), ("a", 150)])

    def test_no_self_match_and_book_keeps_both(self):
        self.x.place("a", "sell", FINE, 2, 170)
        r = self.x.place("a", "buy", FINE, 2, 175)
        self.assertEqual((r.fills, r.remaining), ([], 2))
        self.assertEqual(self.x.quote(FINE)["best_bid"], 175)
        r = self.x.place("b", "buy", FINE, 2, 175)  # fremde Order darf trotzdem gegen die Verkaufsorder laufen
        self.assertEqual(len(r.fills), 1)

    def test_skipping_own_order_still_reaches_better_priced_others(self):
        self.x.place("a", "sell", FINE, 1, 165)  # eigene, am besten
        self.x.place("b", "sell", FINE, 1, 170)
        r = self.x.place("a", "buy", FINE, 1, 175)
        self.assertEqual([(f.seller, f.unit_price) for f in r.fills], [("b", 170)])

    def test_ioc(self):
        self.x.place("a", "sell", FINE, 2, 180)
        r = self.x.place("b", "buy", FINE, 5, 180, ioc=True)
        self.assertEqual((r.order_id, r.remaining, len(r.fills)), (None, 3, 1))
        self.assertEqual(self.w.inv.holdings(ESCROW), {})
        self.assertEqual(self.w.inv.balance("b", COIN), 10000 - 360)
        r = self.x.place("b", "buy", FINE, 1, 150, ioc=True)  # nichts zu holen: vollständig zurück
        self.assertEqual((r.order_id, r.fills), (None, []))
        self.assertEqual(self.w.inv.balance("b", COIN), 10000 - 360)

    def test_invalid_input_changes_nothing(self):
        before = (self.w.inv.to_json(), self.x._counter, self.x.to_json())
        bad = [("a", "hold", FINE, 1, 180), ("ghost", "sell", FINE, 1, 180), ("a", "sell", "iron_blade", 1, 180),
               ("a", "sell", "ghost@fine", 1, 180), ("a", "sell", FINE, 0, 180), ("a", "sell", FINE, True, 180),
               ("a", "sell", FINE, 1.5, 180), ("a", "sell", FINE, 1, 0), ("a", "sell", FINE, 1, "180"),
               ("a", "sell", FINE, 1, True), ("a", "sell", FINE, 1001, 180), ("a", "sell", FINE, 1, 300),
               ("a", "sell", FINE, 1, 100), ("a", "sell", FINE, 21, 180), ("a", "buy", FINE, 100, 225)]
        for args in bad:
            with self.subTest(args=args):
                with self.assertRaises(WorldError):
                    self.x.place(*args)
        with self.assertRaises(WorldError):
            self.x.place("a", "sell", FINE, 1, 180, ioc="yes")
        self.assertEqual((self.w.inv.to_json(), self.x._counter, self.x.to_json()), before)

    def test_unknown_character_with_holdings_and_huge_quantities_are_rejected(self):
        self.w.inv.deposit("ghost", FINE, 5)  # hat Ware, aber keine Historie
        with self.assertRaises(WorldError):
            self.x.place("ghost", "sell", FINE, 1, 180)
        self.w.inv.deposit("a", FINE, 5000)
        for qty in (1001, 0, -1, True, 1.0, "2"):
            with self.subTest(qty=qty):
                with self.assertRaises(WorldError):
                    self.x.place("a", "sell", FINE, qty, 180)
        self.x.place("a", "sell", FINE, 1000, 180)  # Obergrenze selbst ist erlaubt

    def test_fee_is_rounded_down(self):
        self.x.place("a", "sell", FINE, 1, 171)
        f = self.x.place("b", "buy", FINE, 1, 171).fills[0]
        self.assertEqual(f.fee, 3)  # 171 * 20 / 1000 = 3,42
        self.assertEqual(self.w.inv.balance(SINK, COIN), 3)

    def test_price_band_edges(self):
        self.x.place("a", "sell", FINE, 1, 225)  # 180 * 1,25 genau
        self.x.place("a", "sell", FINE, 1, 135)  # 180 * 0,75 genau
        for p in (226, 134):
            with self.assertRaises(WorldError):
                self.x.place("a", "sell", FINE, 1, p)

    def test_max_open_orders(self):
        for i in range(10):
            self.x.place("a", "sell", FINE, 1, 200 + i)
        with self.assertRaises(WorldError):
            self.x.place("a", "sell", FINE, 1, 200)
        self.x.place("b", "buy", FINE, 1, 150)  # andere Figur unberührt
        self.x.place("a", "buy", FINE, 1, 150, ioc=True)  # IOC belegt keinen Platz


class CancelExpireTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.x = self.w.exchange

    def test_cancel_refunds_and_checks_owner(self):
        r = self.x.place("a", "sell", FINE, 4, 190)
        rb = self.x.place("b", "buy", FINE, 2, 150)
        for who, oid in (("b", r.order_id), ("a", "srv1-ord-00000099"), ("a", None)):
            with self.assertRaises(WorldError):
                self.x.cancel(who, oid)
        self.x.cancel("a", r.order_id)
        self.x.cancel("b", rb.order_id)
        self.assertEqual((self.w.inv.balance("a", FINE), self.w.inv.balance("b", COIN), self.w.inv.holdings(ESCROW)), (20, 10000, {}))
        with self.assertRaises(WorldError):
            self.x.cancel("a", r.order_id)

    def test_partially_filled_order_cancel_returns_only_rest(self):
        r = self.x.place("a", "sell", FINE, 4, 180)
        self.x.place("b", "buy", FINE, 1, 180)
        self.x.cancel("a", r.order_id)
        self.assertEqual(self.w.inv.balance("a", FINE), 19)

    def test_expiry(self):
        self.x.place("a", "sell", FINE, 1, 190)
        self.w.day[0] = 5
        self.x.place("b", "buy", FINE, 1, 150)
        self.assertEqual(self.x.expire(7), [])
        self.assertEqual(self.x.expire(8), ["srv1-ord-00000001"])  # Tag 1 + 7 Tage
        self.assertEqual(self.w.inv.balance("a", FINE), 20)
        self.assertEqual(self.x.expire(12), ["srv1-ord-00000002"])
        self.assertEqual((self.x.orders, self.w.inv.holdings(ESCROW)), ({}, {}))
        for bad in (-1, True, "3", 1.0):
            with self.assertRaises(WorldError):
                self.x.expire(bad)


class PriceIndexTests(unittest.TestCase):
    def setUp(self):
        self.w = world(blades=200)
        self.x = self.w.exchange

    def deal(self, price, qty=1):
        self.x.place("a", "sell", FINE, qty, price)
        self.x.place("b", "buy", FINE, qty, price)

    def test_last_ema_high_low_volume(self):
        self.deal(180)
        self.deal(200, 2)
        st = self.x.stats[FINE]
        self.assertEqual((st["last"], st["high"], st["low"], st["volume"], st["open"]), (200, 200, 180, 3, 180))
        # eine Aktualisierung je Ausführung: 180000 -> (180000*800 + 200000*200)//1000 = 184000
        self.assertEqual(st["ema_milli"], 184000)
        self.assertEqual(self.x.quote(FINE)["ema"], 184)

    def test_day_roll_and_history_limit(self):
        self.deal(180)
        self.w.day[0] = 2
        self.deal(190, 2)
        st = self.x.stats[FINE]
        self.assertEqual((st["closes"], st["day"], st["open"], st["volume"]), ([[1, 180, 1]], 2, 190, 2))
        for d in range(3, 40):
            self.w.day[0] = d
            self.deal(180 + d % 5)
        self.assertEqual(len(self.x.stats[FINE]["closes"]), 30)
        self.assertEqual(self.x.stats[FINE]["closes"][-1][0], 38)

    def test_prices_stay_in_band_no_matter_what(self):
        rng = Rng(5)
        for _ in range(60):
            side = "buy" if rng.below(2) else "sell"
            try:
                self.x.place(rng.pick("abc"), side, FINE, 1 + rng.below(3), 100 + rng.below(160))
            except WorldError:
                pass
        for st in self.x.stats.values():
            self.assertTrue(135 <= st["low"] <= st["high"] <= 225)


class FailureTests(unittest.TestCase):
    def test_trade_failure_rolls_back_the_incoming_order_only(self):
        w = world()
        x = w.exchange
        x.place("a", "sell", FINE, 1, 170)
        x.place("b", "sell", FINE, 1, 172)
        original = w.trading.trade
        calls = []

        def flaky(*a, **k):
            calls.append(a)
            if len(calls) == 2:
                raise WorldError("Ausfall")
            return original(*a, **k)

        w.trading.trade = flaky
        before_a = w.inv.holdings("c")
        with self.assertRaises(WorldError):
            x.place("c", "buy", FINE, 2, 180)
        w.trading.trade = original
        self.assertEqual(w.inv.balance("c", FINE), 21)  # erste Ausführung bleibt bestehen
        self.assertEqual(w.inv.balance("c", COIN), 10000 - 170)
        self.assertEqual(sorted(x.orders), ["srv1-ord-00000002"])  # wartende Order unberührt, eingehende zurückgenommen
        self.assertEqual(x.check(), [])
        self.assertEqual(w.inv.holdings(ESCROW), {FINE: 1})
        self.assertNotEqual(before_a, w.inv.holdings("c"))
        x.place("c", "buy", FINE, 1, 180)  # Markt arbeitet weiter
        self.assertEqual(x.check(), [])

    def test_escrow_release_is_reverted_if_trade_fails(self):
        w = world()
        x = w.exchange
        x.place("a", "sell", FINE, 1, 170)
        w.trading.trade = lambda *a, **k: (_ for _ in ()).throw(WorldError("Ausfall"))
        with self.assertRaises(WorldError):
            x.place("b", "buy", FINE, 1, 180)
        self.assertEqual(sorted(x.orders), ["srv1-ord-00000001"])
        self.assertEqual(w.inv.holdings(ESCROW), {FINE: 1})
        self.assertEqual(w.inv.balance("b", COIN), 10000)

    def test_check_detects_foreign_changes(self):
        w = world()
        x = w.exchange
        x.place("a", "sell", FINE, 3, 190)
        w.inv.deposit(ESCROW, COIN, 1)
        self.assertTrue(x.check())
        w.inv.apply(ESCROW, {COIN: 1}, {})
        self.assertEqual(x.check(), [])
        x.orders["srv1-ord-00000001"]["remaining"] = 0
        self.assertTrue(x.check())
        x.orders["srv1-ord-00000001"]["remaining"] = 3
        x.orders["srv1-ord-00000001"]["qty"] = 2  # Treuhand stimmt, nur die Restmenge übersteigt die Ursprungsmenge
        self.assertEqual(len(x.check()), 1)

    def test_load_rejects_inconsistent_state(self):
        w = world()
        w.exchange.place("a", "sell", FINE, 3, 190)
        text = w.exchange.to_json()
        w.inv.deposit(ESCROW, COIN, 5)
        with self.assertRaises(WorldError):
            w.exchange.load(text)
        w.inv.apply(ESCROW, {COIN: 5}, {})
        w.exchange.load(text)


class PropertyTests(unittest.TestCase):
    def test_random_markets_conserve_everything_and_never_cross(self):
        for seed in (1, 2, 3, 4):
            w = world(("a", "b", "c", "d"))
            x = w.exchange
            start = totals(w)
            rng, fee_total = Rng(seed), 0
            for step in range(200):
                kind = rng.below(10)
                who = rng.pick("abcd")
                if kind < 6:
                    side = "buy" if rng.below(2) else "sell"
                    try:
                        r = x.place(who, side, FINE, 1 + rng.below(4), 140 + rng.below(80), ioc=rng.below(5) == 0)
                    except WorldError:
                        continue
                    for f in r.fills:
                        fee_total += f.fee
                        self.assertEqual(f.total, f.unit_price * f.quantity)
                elif kind < 8 and x.orders:
                    oid = rng.pick(sorted(x.orders))
                    x.cancel(x.orders[oid]["char"], oid)
                elif kind == 8:
                    w.day[0] += 1 + rng.below(3)
                    x.expire(w.day[0])
                self.assertEqual(x.check(), [], (seed, step))
                q = x.quote(FINE)
                bids = {o["char"] for o in x._book(FINE, "buy") if o["price"] == q["best_bid"]}
                asks = {o["char"] for o in x._book(FINE, "sell") if o["price"] == q["best_ask"]}
                if q["best_bid"] is not None and q["best_ask"] is not None and q["best_bid"] >= q["best_ask"]:
                    # gekreuztes Buch ist nur erlaubt, wenn beide Seiten ausschließlich derselben Figur gehören
                    crossing = [o for o in x._book(FINE, "buy") if o["price"] >= q["best_ask"]]
                    asks_all = [o for o in x._book(FINE, "sell") if o["price"] <= q["best_bid"]]
                    chars = {o["char"] for o in crossing} | {o["char"] for o in asks_all}
                    self.assertEqual(len(chars), 1, (seed, step))
            now = totals(w)
            self.assertEqual(now[COIN], start[COIN])  # Gebühren gehen an die Senke, bleiben aber bilanziert
            self.assertEqual(now[FINE], start[FINE])
            self.assertEqual(w.inv.balance(SINK, COIN), fee_total)


class PersistenceTests(unittest.TestCase):
    def build(self):
        w = world()
        w.exchange.place("a", "sell", FINE, 5, 190)
        w.exchange.place("b", "buy", FINE, 2, 150)
        w.exchange.place("c", "buy", FINE, 3, 190)
        return w

    def roundtrip(self, w):
        e, logs = persistence.export_world(w)
        return persistence.import_world(json.loads(json.dumps(e)), json.loads(json.dumps(logs)))

    def test_market_survives_save_and_load_and_continues(self):
        w = self.build()
        loaded = self.roundtrip(w)
        self.assertEqual(loaded.snapshot(), w.snapshot())
        self.assertIn("exchange", loaded.snapshot())
        for x in (w.exchange, loaded.exchange):
            x.place("c", "sell", FINE, 2, 140)
        self.assertEqual(loaded.snapshot(), w.snapshot())
        self.assertEqual(loaded.exchange.orders.keys(), w.exchange.orders.keys())

    def test_worlds_without_market_do_not_carry_the_key(self):
        w = world()
        self.assertNotIn("exchange", w.snapshot())

    def test_escrow_tampering_with_valid_hash_is_caught(self):
        w = self.build()
        e, logs = persistence.export_world(w)
        e = copy.deepcopy(e)
        e["world"]["inventory"]["market:escrow"][COIN] += 1
        e["world_sha256"] = persistence._sha(e["world"])
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(e, logs)
        e2, logs = persistence.export_world(w)
        e2 = copy.deepcopy(e2)
        e2["world"]["exchange"]["orders"]["srv1-ord-00000002"]["remaining"] = 1
        e2["world_sha256"] = persistence._sha(e2["world"])
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(e2, logs)

    def test_store_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            s = persistence.Store(tmp)
            w = self.build()
            s.commit(w)
            self.assertEqual(s.load().snapshot(), w.snapshot())


if __name__ == "__main__":
    unittest.main()
