import json
import unittest

from mmo_world.persistence import check_consistency, export_world, import_world
from mmo_world.world import World
from mmo_world.errors import WorldError

CRC = "coin@gold"


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.w = World("rules_v9.json")
        self.s = self.w.settlements
        for c in ("anna", "ben"):
            self.w.svc.create(c, "player")
            self.w.inv.deposit(c, CRC, 20000)
            self.w.inv.deposit(c, "timber@standard", 500)
            self.w.inv.deposit(c, "wooden_beam@standard", 500)
            self.w.inv.deposit(c, "iron_ingot@standard", 100)

    def test_plot_building_stash_and_tax(self):
        s, w = self.s, self.w
        s.buy_plot("anna", "hauptstadt", 1)
        with self.assertRaises(WorldError):
            s.buy_plot("ben", "hauptstadt", 1)
        self.assertEqual(s.build("anna", "hauptstadt", 1, "house"), 1)
        s.stash_in("anna", "hauptstadt", 1, "timber@standard", 50)
        with self.assertRaises(WorldError):
            s.stash_in("anna", "hauptstadt", 1, "timber@standard", 500)
        with self.assertRaises(WorldError):
            s.stash_out("ben", "hauptstadt", 1, "timber@standard", 1)
        before = w.inv.balance("anna", CRC)
        s.advance(1)
        self.assertEqual(before - w.inv.balance("anna", CRC), 5)
        s.stash_out("anna", "hauptstadt", 1, "timber@standard", 50)

    def test_forfeit_returns_stash(self):
        s, w = self.s, self.w
        s.buy_plot("anna", "hauptstadt", 1)
        s.build("anna", "hauptstadt", 1, "house")
        s.stash_in("anna", "hauptstadt", 1, "iron_ingot@standard", 10)
        w.inv.apply("anna", {CRC: w.inv.balance("anna", CRC)}, {})
        gone = []
        for d in range(1, 9):
            gone += s.advance(d)
        self.assertEqual(len(gone), 1)
        self.assertEqual(w.inv.balance("anna", "iron_ingot@standard"), 100)
        self.assertEqual(s.plots, {})

    def test_found_and_projects(self):
        s, w = self.s, self.w
        with self.assertRaises(WorldError):
            s.buy_plot("anna", "moorufer", 1)
        s.found("anna", "moorufer", "Moorheim")
        with self.assertRaises(WorldError):
            s.found("ben", "moorufer", "Anderes")
        s.buy_plot("anna", "moorufer", 1)
        with self.assertRaises(WorldError):
            s.contribute("ben", "moorufer", "road", 100)          # kein Bewohner
        with self.assertRaises(WorldError):
            s.contribute("anna", "moorufer", "harbor", 100)       # keine Küste
        r = s.contribute("anna", "moorufer", "road", 600, {"timber@standard": 30})
        self.assertTrue(r["completed"])
        self.assertEqual(s.effects("moorufer")["move_permille"], 40)
        self.assertEqual(s.road_permille("moor"), 40)
        self.assertEqual(s.road_permille("sunmeadow"), 0)
        with self.assertRaises(WorldError):
            s.contribute("anna", "moorufer", "road", 2000)        # mehr als gebraucht
        self.assertEqual(s.view("anna")["contributed"]["moorufer"], 630)

    def test_market_square_discounts_exchange_fee(self):
        s, w = self.s, self.w
        item = "iron_ingot@standard"

        def sell_fee() -> int:
            w.exchange.place("anna", "sell", item, 10, 20)
            return w.exchange.place("ben", "buy", item, 10, 20).fills[0].fee

        base = sell_fee()                                        # ohne Marktplatz: volle Gebühr
        self.assertGreater(base, 0)
        s.found("anna", "moorufer", "Moorheim")
        s.buy_plot("anna", "moorufer", 1)
        self.assertEqual(s.fee_discount_permille("anna"), 0)
        s.contribute("anna", "moorufer", "market_square", 800, {"timber@standard": 40})   # Stufe 1: 250 Promille Rabatt
        self.assertEqual(s.fee_discount_permille("anna"), 250)
        self.assertEqual(s.fee_discount_permille("ben"), 0)      # ohne Grundstück kein Rabatt
        self.assertEqual((s.view("anna")["fee_discount_permille"], s.view("ben")["fee_discount_permille"]), (250, 0))
        self.assertEqual(sell_fee(), base - base * 250 // 1000)
        w.exchange.place("ben", "sell", item, 10, 20)           # Rabatt gilt nur für den Verkäufer
        self.assertEqual(w.exchange.place("anna", "buy", item, 10, 20).fills[0].fee, base)

    def test_harbor_raises_open_order_limit(self):                  # AP 41
        s, w = self.s, self.w
        item = "iron_ingot@standard"
        for _ in range(10):
            w.exchange.place("anna", "sell", item, 1, 25)
        with self.assertRaises(WorldError):
            w.exchange.place("anna", "sell", item, 1, 25)           # Standardgrenze 10
        s.tech_known = lambda site, tech: True
        s.buy_plot("anna", "hauptstadt", 1)
        self.assertEqual(s.order_bonus("anna"), 0)
        s.contribute("anna", "hauptstadt", "harbor", 2500, {"wooden_beam@standard": 40, "iron_ingot@standard": 10})
        self.assertEqual((s.order_bonus("anna"), s.order_bonus("ben"), s.view("anna")["order_bonus"]), (3, 0, 3))
        for _ in range(3):
            w.exchange.place("anna", "sell", item, 1, 25)
        with self.assertRaises(WorldError):
            w.exchange.place("anna", "sell", item, 1, 25)           # 10 + 3
        with self.assertRaises(WorldError):                          # Ben ohne Hafen bleibt bei 10
            for _ in range(11):
                w.exchange.place("ben", "sell", item, 1, 25)

    def test_plot_limit_and_roundtrip(self):
        s, w = self.s, self.w
        for n in (1, 2, 4):
            s.buy_plot("anna", "hauptstadt", n)
        with self.assertRaises(WorldError):
            s.buy_plot("anna", "hauptstadt", 5)
        s.build("anna", "hauptstadt", 1, "shop")
        snap = w.snapshot()
        self.assertIn("settlements", snap)
        self.assertEqual(check_consistency(w), [])
        self.assertEqual(json.loads(s.to_json()), snap["settlements"])


if __name__ == "__main__":
    unittest.main()


class GatewayAndGame(unittest.TestCase):
    def test_commands_and_road_speed(self):
        from mmo_game import GameServer
        from mmo_server.protocol import COMMANDS
        from tests.test_game_enemies import Bot
        for c in ("query.settlements", "settlement.found", "plot.buy", "plot.build", "plot.stash_in", "project.contribute"):
            self.assertIn(c, COMMANDS)
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.world.inv.deposit("anna", CRC, 20000)
        self.assertTrue(a.call("settlement.found", site="sonnenwiese_ost", name="Sonnental")["ok"])
        self.assertTrue(a.call("plot.buy", site="sonnenwiese_ost", n=1)["ok"])
        self.assertFalse(a.call("plot.buy", site="sonnenwiese_ost", n=1)["ok"])
        v = a.call("query.settlements")["result"]
        self.assertEqual([p["n"] for p in v["mine"]], [1])
        self.assertEqual(next(s for s in v["sites"] if s["id"] == "sonnenwiese_ost")["name"], "Sonnental")
        g.world.inv.deposit("anna", "timber@standard", 30)
        self.assertTrue(a.call("project.contribute", site="sonnenwiese_ost", project="road", coins=600)["ok"])
        self.assertTrue(a.call("project.contribute", site="sonnenwiese_ost", project="road", item_key="timber@standard", qty=30)["ok"])
        self.assertEqual(g.world.settlements.road_permille("sunmeadow"), 40)
