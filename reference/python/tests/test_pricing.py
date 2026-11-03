import copy
import json
import unittest

from mmo_world import WorldError, persistence
from mmo_world.golden import Rng
from mmo_world.pricing import load_pricing_rules, validate_pricing_rules
from mmo_world.world import World

COIN = "coin@gold"
FINE = "iron_blade@fine"  # Tabellenwert je Stück 180
ORE = "iron_ore@standard"


def world(chars="abc", coins=50000):
    w = World("rules_v8.json")
    for c in chars:
        w.svc.create(c, "player")
        w.svc.record(c, "identity.xp_gained", {"amount": 10000})
        w.inv.deposit(c, COIN, coins)
        w.inv.deposit(c, FINE, 100)
        w.inv.deposit(c, ORE, 200)
    return w


def wash(w, price, days, start=1, qty=5):
    """Scheinhandel zweier Figuren zu einem Preis, täglich mit anschließendem Preisschritt."""
    for d in range(start, start + days):
        w.day[0] = d
        w.exchange.place("a", "sell", FINE, qty, price)
        w.exchange.place("b", "buy", FINE, qty, price)
        w.pricing.advance(d)


class RulesTests(unittest.TestCase):
    def test_valid_and_broken(self):
        w = World("rules_v8.json")
        pr = load_pricing_rules()
        validate_pricing_rules(pr, w.svc.rules)
        broken = [("alpha_permille", 1001), ("max_step_permille", -1), ("max_shift_permille", 401), ("stale_days", 0),
                  ("max_catch_up_days", True), ("shock", {"max_permille": 901, "max_days": 3}), ("shock", {"max_permille": 100, "max_days": 0}),
                  ("maker", dict(pr["maker"], items=[])), ("maker", dict(pr["maker"], items=["ghost"])),
                  ("maker", dict(pr["maker"], items=["iron_ore", "iron_ore"])), ("maker", dict(pr["maker"], spread_permille=901)),
                  ("maker", dict(pr["maker"], daily_qty_per_side=0)), ("maker", dict(pr["maker"], character_id="")),
                  ("requires_cee_rules_min", 99)]
        for key, bad in broken:
            with self.subTest(key=key):
                with self.assertRaises(WorldError):
                    validate_pricing_rules(dict(pr, **{key: bad}), w.svc.rules)

    def test_not_available_with_v7_rules(self):
        w = World()
        self.assertIsNone(w.pricing)
        with self.assertRaises(WorldError):
            validate_pricing_rules(load_pricing_rules(), w.svc.rules)
        w.svc.create("a", "player")
        w.svc.create("b", "player")
        w.inv.deposit("a", FINE, 1)
        w.inv.deposit("b", COIN, 500)
        r = w.trading.trade("a", "b", FINE, 1, 180)
        self.assertNotIn("reference", w.svc.log.events("a")[-1].payload)
        self.assertEqual(r.reference, 180)


class ReferenceTests(unittest.TestCase):
    def test_trade_reports_the_current_reference(self):
        w = world()
        w.inv.deposit("a", FINE, 5)
        r = w.trading.trade("a", "b", FINE, 2, 360)
        self.assertEqual((r.reference, w.svc.log.events("a")[-1].payload["reference"]), (360, 360))
        w.pricing.factors[FINE] = 1250
        r = w.trading.trade("a", "b", FINE, 2, 360)
        self.assertEqual((r.reference, w.svc.log.events("b")[-1].payload["reference"]), (450, 450))
        self.assertEqual(w.pricing.reference("iron_blade", "fine", 3), 675)  # 540 * 1250 // 1000

    def test_exchange_band_and_npc_price_follow_the_reference(self):
        w = world()
        with self.assertRaises(WorldError):
            w.exchange.place("a", "sell", FINE, 1, 226)
        w.pricing.factors[FINE] = 1200  # Referenz 216 -> Band 162..270
        w.exchange.place("a", "sell", FINE, 1, 270)
        with self.assertRaises(WorldError):
            w.exchange.place("a", "sell", FINE, 1, 271)
        self.assertEqual(w.production.npc_price(FINE, 10), 1296)  # 2160 * 0,6

    def test_cee_accepts_only_references_inside_its_span(self):
        w = world()
        w.pricing.factors[FINE] = 1400  # außerhalb der Pricing-Spanne, innerhalb der CEE-Spanne
        w.inv.deposit("a", FINE, 1)
        w.trading.trade("a", "b", FINE, 1, 180)
        w.pricing.factors[FINE] = 1500  # nur durch Manipulation möglich: die CEE lehnt ab (270 > 252)
        before = w.inv.to_json()
        with self.assertRaises(Exception) as cm:
            w.trading.trade("a", "b", FINE, 1, 180)
        self.assertIn("reference", str(cm.exception))
        self.assertEqual(w.inv.to_json(), before)


class AdvanceTests(unittest.TestCase):
    def test_moves_toward_market_with_cap_and_limit(self):
        w = world()
        w.inv.deposit("a", FINE, 1000)
        w.inv.deposit("b", COIN, 500000)
        wash(w, 216, 1)  # Marktsignal 1200
        self.assertEqual(w.pricing.factors[FINE], 1020)  # (1200-1000)*100//1000 = 20 (Schritt <= 50)
        seen = [1020]
        for d in range(2, 120):
            w.day[0] = d
            top = int(w.pricing.reference("iron_blade", "fine", 1) * 1.2)
            w.exchange.place("a", "sell", FINE, 1, top)
            w.exchange.place("b", "buy", FINE, 1, top)
            w.pricing.advance(d)
            seen.append(w.pricing.factors[FINE])
        self.assertTrue(all(b - a <= 50 for a, b in zip(seen, seen[1:])))
        self.assertEqual(max(seen), 1300)  # Spanne der Preisdynamik, nie mehr

    def test_step_cap(self):
        w = world()
        w.day[0] = 1
        w.pricing.set_shock(ORE, 1300, 30)
        w.pricing.advance(1)
        self.assertEqual(w.pricing.factors[ORE], 1030)  # (1300-1000)*100//1000 = 30 <= 50
        pr = w.pricing
        pr.pr = dict(pr.pr, alpha_permille=1000)
        pr.advance(2)
        self.assertEqual(pr.factors[ORE], 1080)  # volle Annäherung, aber höchstens +50

    def test_stale_market_returns_to_table_value_and_factor_disappears(self):
        w = world()
        wash(w, 216, 3)
        self.assertIn(FINE, w.pricing.factors)
        for d in range(4, 60):
            w.pricing.advance(d)
        self.assertNotIn(FINE, w.pricing.factors)

    def test_steps_are_symmetric_and_at_least_one_permille(self):
        w = world()
        pr = w.pricing

        def one(cur, ema):
            pr.factors = {FINE: cur} if cur != 1000 else {}
            w.exchange.stats[FINE] = {"last": 0, "ema_milli": ema, "day": pr.last_day + 1, "open": 0, "high": 0, "low": 0, "volume": 1, "closes": []}
            w.day[0] = pr.last_day + 1
            pr.advance(pr.last_day + 1)
            return pr.factors.get(FINE, 1000)

        self.assertEqual(one(1033, 150000), 1013)   # Ziel 833: Abstand -200 * 100 / 1000 = -20
        self.assertEqual(one(1033, 180000), 1030)   # Ziel 1000: Abstand -33 -> -3 (Richtung 0 abgeschnitten, nicht -4)
        self.assertEqual(one(967, 180000), 970)     # spiegelbildlich: +3
        self.assertEqual(one(1005, 180000), 1004)   # Abstand -5 -> 0 -> mindestens -1
        self.assertEqual(one(995, 180000), 996)
        self.assertEqual(one(1001, 180000), 1000)   # erreicht das Ziel exakt, Faktor verschwindet
        self.assertNotIn(FINE, pr.factors)

    def test_market_signal_is_fresh_for_exactly_stale_days(self):
        w = world()
        pr = w.pricing
        w.exchange.stats[FINE] = {"last": 216, "ema_milli": 216000, "day": 1, "open": 216, "high": 216, "low": 216, "volume": 1, "closes": []}
        pr.last_day = 7
        w.day[0] = 8
        pr.advance(8)  # 8 - 1 = 7 Tage alt: noch frisch
        self.assertEqual(pr.factors[FINE], 1020)
        pr.advance(9)  # 8 Tage alt: veraltet, Rückkehr zu 1000 (Abstand 20 -> mindestens 2 Promille)
        self.assertEqual(pr.factors[FINE], 1020 - 2)

    def test_rejections_and_catch_up(self):
        w = world()
        w.pricing.advance(3)
        for bad in (3, 2, 0, True, "5", 3.5):
            with self.assertRaises(WorldError):
                w.pricing.advance(bad)
        with self.assertRaises(WorldError):
            w.pricing.advance(34)  # mehr als 30 Tage
        w.pricing.advance(33)
        self.assertEqual(w.pricing.last_day, 33)


class ShockTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.p = self.w.pricing

    def test_limits(self):
        before = self.p.to_json()
        for args in ((ORE, 1000, 3), (ORE, 1301, 3), (ORE, 699, 3), (ORE, True, 3), (ORE, 1100, 0), (ORE, 1100, 31),
                     (ORE, 1100, True), ("ghost@fine", 1100, 3), ("iron_ore", 1100, 3), (None, 1100, 3)):
            with self.subTest(args=args):
                with self.assertRaises(WorldError):
                    self.p.set_shock(*args)
        self.assertEqual(self.p.to_json(), before)
        self.p.set_shock(ORE, 1300, 3)
        self.p.set_shock(ORE, 700, 30)  # ersetzt den vorigen
        self.assertEqual(self.p.shocks[ORE], {"permille": 700, "until": 31})

    def test_shock_lifetime_and_effect(self):
        self.p.set_shock(ORE, 700, 3)  # Tag 1 + 3 = bis einschließlich Tag 4
        for d in range(1, 5):
            self.w.day[0] = d
            self.p.advance(d)
            self.assertIn(ORE, self.p.shocks)
        self.assertLess(self.p.factors[ORE], 1000)
        self.w.day[0] = 5
        self.p.advance(5)
        self.assertNotIn(ORE, self.p.shocks)
        low = self.p.factors[ORE]
        for d in range(6, 80):
            self.p.advance(d)
        self.assertNotIn(ORE, self.p.factors)  # zurück beim Tabellenwert
        self.assertLess(low, 1000)

    def test_shock_moves_the_exchange_band(self):
        self.p.set_shock(FINE, 1300, 30)
        for d in range(1, 30):
            self.w.day[0] = d
            self.p.advance(d)
        self.assertGreater(self.p.factors[FINE], 1200)
        self.w.exchange.place("a", "sell", FINE, 1, 280)  # alt: maximal 225


class MakerTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.p = self.w.pricing

    def test_prices_with_spread_and_rounding(self):
        ref = self.p.reference("iron_ore", "standard", 10)
        self.assertEqual(self.p.quote(ORE, 10, "sell"), ref * 850 // 1000)
        self.assertEqual(self.p.quote(ORE, 10, "buy"), -(-ref * 1150 // 1000))
        self.assertLess(self.p.quote(ORE, 7, "sell"), self.p.quote(ORE, 7, "buy"))
        for q in range(1, 41):  # Verkäuferpreis abgerundet, Käuferpreis aufgerundet (nie zum Nachteil der Welt)
            ref = self.p.reference("iron_ore", "standard", q)
            self.assertEqual(self.p.quote(ORE, q, "sell"), ref * 850 // 1000)
            self.assertEqual(self.p.quote(ORE, q, "buy"), (ref * 1150 + 999) // 1000)

    def test_sell_to_maker_creates_coins_and_removes_goods(self):
        coins, ore = self.w.inv.total(COIN), self.w.inv.total(ORE)
        r = self.p.sell_to_maker("a", ORE, 10)
        self.assertEqual(r.price, self.p.quote(ORE, 10, "sell"))
        self.assertEqual((self.w.inv.total(COIN), self.w.inv.total(ORE)), (coins + r.price, ore - 10))
        self.assertEqual(self.w.inv.holdings("npc:maker"), {})
        ev = self.w.svc.log.events("a")[-1]
        self.assertEqual((ev.payload["counterparty"], ev.payload["role"], ev.payload["reference"]), ("npc:maker", "seller", r.reference))
        self.assertEqual(self.w.svc.state("npc:maker").parts["identity"]["kind"], "npc")

    def test_buy_from_maker_creates_goods_and_sinks_coins(self):
        coins, ore = self.w.inv.total(COIN), self.w.inv.total(ORE)
        r = self.p.buy_from_maker("a", ORE, 10)
        self.assertEqual(r.price, self.p.quote(ORE, 10, "buy"))
        self.assertEqual((self.w.inv.total(COIN), self.w.inv.total(ORE)), (coins, ore + 10))  # Münzen bilanziert (Senke)
        self.assertEqual(self.w.inv.balance("world:sink", COIN), r.price)
        self.assertEqual(self.w.inv.holdings("npc:maker"), {})

    def test_daily_quantity_is_per_item_and_side_and_resets(self):
        self.p.sell_to_maker("a", ORE, 40)
        with self.assertRaises(WorldError):
            self.p.sell_to_maker("b", ORE, 1)  # Tagesmenge je Seite gilt für alle zusammen
        self.p.buy_from_maker("b", ORE, 40)  # andere Seite hat ihre eigene Menge
        self.w.inv.deposit("c", "iron_ore@select", 5)
        self.p.sell_to_maker("c", "iron_ore@select", 5)  # andere Güte: eigene Menge
        self.w.day[0] = 2
        self.p.sell_to_maker("b", ORE, 40)

    def test_rejections_change_nothing(self):
        self.w.inv.deposit("c", "clean_water@rough", 1)
        before = (self.w.inv.to_json(), self.p.to_json(), self.w.snapshot())
        for fn in (lambda: self.p.sell_to_maker("a", FINE, 1),              # nicht im Sortiment
                   lambda: self.p.sell_to_maker("a", ORE, 0), lambda: self.p.sell_to_maker("a", ORE, True),
                   lambda: self.p.sell_to_maker("ghost", ORE, 1), lambda: self.p.sell_to_maker("npc:maker", ORE, 1),
                   lambda: self.p.sell_to_maker("a", ORE, 41),                # Tagesmenge
                   lambda: self.p.sell_to_maker("a", "iron_ore", 1), lambda: self.p.sell_to_maker("a", "iron_ore@legend", 1),
                   lambda: self.p.sell_to_maker("c", "clean_water@rough", 1),  # Preis wäre 0 (Referenz 1, Händler zahlt 85 %)
                   lambda: self.p.buy_from_maker("a", ORE, 41)):
            with self.assertRaises(WorldError):
                fn()
        poor = World("rules_v8.json")
        poor.svc.create("p", "player")
        poor.inv.deposit("p", COIN, 1)
        with self.assertRaises(WorldError):
            poor.pricing.buy_from_maker("p", ORE, 5)  # nicht genug Münzen
        with self.assertRaises(WorldError):
            poor.pricing.sell_to_maker("p", ORE, 5)  # nicht genug Ware
        self.assertEqual((self.w.inv.to_json(), self.p.to_json(), self.w.snapshot()), before)
        self.assertFalse(poor.svc.log.has("npc:maker"))

    def test_unknown_characters_and_the_maker_itself_are_refused_even_with_holdings(self):
        self.w.inv.deposit("ghost", ORE, 5)
        self.w.inv.deposit("ghost", COIN, 500)
        with self.assertRaises(WorldError):
            self.p.sell_to_maker("ghost", ORE, 1)
        with self.assertRaises(WorldError):
            self.p.buy_from_maker("ghost", ORE, 1)
        self.p.sell_to_maker("a", ORE, 1)  # legt den Händler an
        self.w.inv.deposit("npc:maker", ORE, 5)
        self.w.inv.deposit("npc:maker", COIN, 500)
        for fn in (self.p.sell_to_maker, self.p.buy_from_maker):
            with self.assertRaises(WorldError):
                fn("npc:maker", ORE, 1)

    def test_load_rejects_damaged_state(self):
        good = self.p.to_json()
        bad = json.loads(good)
        bad["factors"] = {FINE: 1301}
        with self.assertRaises(WorldError):
            self.p.load(json.dumps(bad))
        self.p.load(good)

    def test_trade_failure_rolls_back_minted_value(self):
        before = self.w.inv.to_json()
        original = self.w.trading.trade
        self.w.trading.trade = lambda *a, **k: (_ for _ in ()).throw(WorldError("Ausfall"))
        with self.assertRaises(WorldError):
            self.p.sell_to_maker("a", ORE, 5)
        with self.assertRaises(WorldError):
            self.p.buy_from_maker("a", ORE, 5)
        self.w.trading.trade = original
        self.assertEqual(self.w.inv.to_json(), before)
        self.assertEqual(self.p.maker_used, {})

    def test_repeat_decay_makes_farming_the_maker_worthless(self):
        self.w.inv.deposit("a", ORE, 500)
        gains, last = [], 0
        for _ in range(8):
            self.w.pricing.maker_used.clear()  # Tagesmenge des Händlers hier nicht der Engpass
            self.p.sell_to_maker("a", ORE, 40)
            now = self.w.svc.state("a").parts["economy"]["points"]["volume"]
            gains.append(now - last)
            last = now
        self.assertGreater(gains[0], 0)
        self.assertEqual(gains[0], gains[1])            # die ersten beiden Handel voll
        self.assertLess(gains[2], gains[1])             # dann Abnahme (75 %, 50 %, 25 %, 10 %)
        self.assertLessEqual(gains[5], gains[0] * 100 // 1000 + 1)
        self.assertEqual(gains[5], gains[7])


class ExploitBoundTests(unittest.TestCase):
    def test_pumping_the_price_is_bounded_by_shift_and_the_maker_by_daily_quantity(self):
        w = world(coins=500000)
        w.inv.deposit("a", FINE, 500)
        p = w.pricing
        for d in range(1, 120):  # zwei Figuren treiben den Marktpreis (Ziel +20 %), danach Schock auf Erz (+30 %)
            w.day[0] = d
            top = int(p.reference("iron_blade", "fine", 1) * 1.2)
            w.exchange.place("a", "sell", FINE, 1, top)
            w.exchange.place("b", "buy", FINE, 1, top)
            p.advance(d)
        self.assertLessEqual(p.factor(FINE), 1300)
        with self.assertRaises(WorldError):
            p.sell_to_maker("a", FINE, 1)  # Schwerter kauft der Händler nicht: kein Gewinn aus dem Scheinhandel
        p.set_shock(ORE, 1300, 30)
        for d in range(120, 150):
            w.day[0] = d
            p.advance(d)
        self.assertLessEqual(p.factor(ORE), 1300)
        day_cap = p.pr["maker"]["daily_qty_per_side"]
        first = p.sell_to_maker("a", ORE, day_cap).price
        with self.assertRaises(WorldError):
            p.sell_to_maker("b", ORE, 1)  # mehr als die Tagesmenge gibt es nicht
        table = 8 * day_cap  # Tabellenwert des Erzes je Stück: 8
        self.assertLessEqual(first, table * 1300 // 1000 * 850 // 1000 + 1)  # höchstens Referenz +30 % abzüglich Spanne


class InvariantTests(unittest.TestCase):
    def test_random_operations(self):
        for seed in (1, 2, 3):
            w = world("abcd", 40000)
            p, rng = w.pricing, Rng(seed)
            day = 1
            minted = w.inv.total(COIN)
            made = 0
            for step in range(150):
                k, who = rng.below(8), rng.pick(list("abcd"))
                item = rng.pick([ORE, FINE])
                try:
                    if k == 0:
                        made += p.sell_to_maker(who, ORE, 1 + rng.below(15)).price
                    elif k == 1:
                        p.buy_from_maker(who, ORE, 1 + rng.below(15))
                    elif k == 2:
                        p.set_shock(item, 1000 + rng.below(500) - 250, 1 + rng.below(10))
                    elif k in (3, 4):
                        w.exchange.place(who, rng.pick(["buy", "sell"]), item, 1 + rng.below(5),
                                         max(1, p.reference(*item.split("@")[0:1], item.split("@")[1], 1) * (70 + rng.below(60)) // 100))
                    else:
                        day += 1 + rng.below(3)
                        w.day[0] = day
                        p.advance(day)
                except WorldError:
                    pass
                self.assertEqual(p.check(), [], (seed, step))
                self.assertEqual(w.exchange.check(), [], (seed, step))
                for f in p.factors.values():
                    self.assertTrue(700 <= f <= 1300)
            self.assertEqual(w.inv.total(COIN), minted + made)


class PersistenceTests(unittest.TestCase):
    def build(self):
        w = world()
        wash(w, 216, 4)
        w.pricing.set_shock(ORE, 1200, 10)
        w.pricing.sell_to_maker("a", ORE, 5)
        w.pricing.advance(5)
        return w

    def roundtrip(self, w):
        e, logs = persistence.export_world(w)
        return persistence.import_world(json.loads(json.dumps(e)), json.loads(json.dumps(logs))), e, logs

    def test_roundtrip_and_continuation(self):
        w = self.build()
        loaded, e, _ = self.roundtrip(w)
        self.assertEqual(loaded.snapshot(), w.snapshot())
        self.assertEqual(e["rules"]["cee_file"], "rules_v8.json")
        for x in (w, loaded):
            x.day[0] = 6
            x.pricing.sell_to_maker("b", ORE, 3)
            x.pricing.advance(6)
        self.assertEqual(loaded.snapshot(), w.snapshot())

    def test_v7_world_has_no_pricing_and_roundtrips(self):
        w = World()
        w.svc.create("a", "player")
        loaded, e, _ = self.roundtrip(w)
        self.assertIsNone(loaded.pricing)
        self.assertEqual((e["rules"]["pricing_file"], e["rules"]["pricing_sha256"]), (None, None))

    def test_tampering(self):
        w = self.build()
        _, e, logs = self.roundtrip(w)

        def fix(x):
            x["world_sha256"] = persistence._sha(x["world"])
            return x

        cases = {
            "factor_out_of_range": lambda x: x["world"]["pricing"]["factors"].update({FINE: 1301}),
            "factor_1000": lambda x: x["world"]["pricing"]["factors"].update({FINE: 1000}),
            "shock_out_of_range": lambda x: x["world"]["pricing"]["shocks"].update({ORE: {"permille": 2000, "until": 9}}),
            "maker_holds_goods": lambda x: x["world"]["inventory"].update({"npc:maker": {ORE: 3}}),
            "pricing_rules_hash": lambda x: x["rules"].update(pricing_sha256="0" * 64),
            "pricing_file_removed": lambda x: x["rules"].update(pricing_file=None, pricing_sha256=None),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                bad = copy.deepcopy(e)
                fn(bad)
                with self.assertRaises(persistence.PersistenceError):
                    persistence.import_world(fix(bad), logs)
        v7 = World()
        v7.svc.create("a", "player")
        e7, l7 = persistence.export_world(v7)
        e7 = copy.deepcopy(e7)
        e7["world"]["pricing"] = {"factors": {}, "shocks": {}, "maker_used": {}, "last_day": 1}
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(fix(e7), l7)


if __name__ == "__main__":
    unittest.main()
