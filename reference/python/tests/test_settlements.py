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
        self.assertEqual(s.view("anna")["orders_per_reach"], 3)
        for _ in range(3):
            w.exchange.place("anna", "sell", item, 1, 25)
        with self.assertRaises(WorldError):
            w.exchange.place("anna", "sell", item, 1, 25)           # 10 + 3
        with self.assertRaises(WorldError):                          # Ben ohne Hafen bleibt bei 10
            for _ in range(11):
                w.exchange.place("ben", "sell", item, 1, 25)

    def test_plot_sale(self):                                        # AP 43
        s, w = self.s, self.w
        s.buy_plot("anna", "hauptstadt", 1)
        s.build("anna", "hauptstadt", 1, "house")
        for bad in (("ben", -1), ("ben", 10**9), ("anna", 100), ("nobody", 100), ("ben", True)):
            with self.assertRaises(WorldError):
                s.sell_plot("anna", "hauptstadt", 1, *bad)
        with self.assertRaises(WorldError):
            s.sell_plot("ben", "hauptstadt", 1, "anna", 100)                       # fremdes Grundstück
        s.stash_in("anna", "hauptstadt", 1, "timber@standard", 5)
        with self.assertRaises(WorldError):
            s.sell_plot("anna", "hauptstadt", 1, "ben", 1000)                      # Lager nicht leer
        s.stash_out("anna", "hauptstadt", 1, "timber@standard", 5)
        offer = s.sell_plot("anna", "hauptstadt", 1, "ben", 1000)
        self.assertEqual((s.view("anna")["sale_days"], s.view("anna")["sale_fee_permille"]), (7, 50))
        self.assertEqual((offer["price"], s.view("ben")["sales_in"][0]["plot"], len(s.view("anna")["sales_out"])), (1000, "hauptstadt:1", 1))
        with self.assertRaises(WorldError):
            s.accept_sale("anna", "hauptstadt", 1)                                 # nur der Käufer
        a0, b0 = w.inv.balance("anna", CRC), w.inv.balance("ben", CRC)
        r = s.accept_sale("ben", "hauptstadt", 1)
        self.assertEqual((r["price"], r["fee"]), (1000, 50))
        self.assertEqual((w.inv.balance("anna", CRC) - a0, b0 - w.inv.balance("ben", CRC)), (950, 1000))   # Gebühr 5 % verschwindet
        p = s.plots["hauptstadt:1"]
        self.assertEqual((p["owner"], p["building"], p["level"]), ("ben", "house", 1))                    # Gebäude geht mit
        self.assertEqual(s.sales, {})
        self.assertEqual(check_consistency(w), [])

    def test_plot_sale_notifications(self):                          # AP 51
        s, w = self.s, self.w
        kinds = lambda who: [i["kind"] for i in w.outbox.fetch(who)["items"] if i["kind"].startswith("plot.")]
        s.buy_plot("anna", "hauptstadt", 1)
        s.sell_plot("anna", "hauptstadt", 1, "ben", 100)
        self.assertEqual((kinds("ben"), kinds("anna")), (["plot.sale_offered"], []))
        s.cancel_sale("anna", "hauptstadt", 1)
        s.sell_plot("anna", "hauptstadt", 1, "ben", 100)
        s.accept_sale("ben", "hauptstadt", 1)
        self.assertEqual(kinds("anna"), ["plot.sold"])
        self.assertEqual(kinds("ben"), ["plot.sale_offered", "plot.sale_cancelled", "plot.sale_offered"])
        s.sell_plot("ben", "hauptstadt", 1, "anna", 100)
        s.advance(9)
        self.assertEqual(kinds("anna")[-1], "plot.sale_expired")
        self.assertEqual(kinds("ben")[-1], "plot.sale_expired")

    def test_plot_sale_cancel_expiry_and_invalid_offers(self):       # AP 43
        s, w = self.s, self.w
        s.buy_plot("anna", "hauptstadt", 1)
        s.sell_plot("anna", "hauptstadt", 1, "ben", 100)
        s.cancel_sale("anna", "hauptstadt", 1)
        with self.assertRaises(WorldError):
            s.accept_sale("ben", "hauptstadt", 1)
        s.sell_plot("anna", "hauptstadt", 1, "ben", 100)
        s.advance(8)
        self.assertEqual(len(s.sales), 1)                                          # Tag 8 = letzter gültiger Tag
        s.advance(9)                                                               # danach verfallen (7 Tage Frist)
        self.assertEqual(s.sales, {})
        s.sell_plot("anna", "hauptstadt", 1, "ben", 100)
        s.abandon("anna", "hauptstadt", 1)                                         # Aufgeben löscht das Angebot
        self.assertEqual(s.sales, {})
        s.buy_plot("anna", "hauptstadt", 2)
        s.sell_plot("anna", "hauptstadt", 2, "ben", 10**6)
        with self.assertRaises(WorldError):
            s.accept_sale("ben", "hauptstadt", 2)                                  # zu wenig Münzen (20000)
        self.assertEqual(s.plots["hauptstadt:2"]["owner"], "anna")
        snap = w.snapshot()
        self.assertEqual(json.loads(s.to_json()), snap["settlements"])
        s2 = World("rules_v9.json").settlements
        s2.load(s.to_json())
        self.assertEqual(s2.sales, s.sales)

    def test_wall_lowers_plot_tax(self):                              # AP 64
        s, w = self.s, self.w
        s.buy_plot("anna", "hauptstadt", 1)
        medium = next(n for n in range(1, 13) if s.size_of(n) == "medium")
        s.buy_plot("anna", "hauptstadt", medium)
        mp = s.plots[f"hauptstadt:{medium}"]
        self.assertEqual((s.tax_of(s.plots["hauptstadt:1"]), s.tax_of(mp)), (5, 12))
        s.projects["hauptstadt:wall"] = {"level": 1, "have": {}}                    # Mauer Stufe 1: 150 ‰
        self.assertEqual(s.tax_of(mp), 12 - 12 * 150 // 1000)
        s.projects["hauptstadt:wall"] = {"level": 2, "have": {}}                    # Stufe 2: 350 ‰
        self.assertEqual((s.tax_of(mp), s.plot_view(mp)["tax"]), (8, 8))
        before = w.inv.balance("anna", CRC)
        s.advance(1)
        self.assertEqual(before - w.inv.balance("anna", CRC), s.tax_of(s.plots["hauptstadt:1"]) + 8)   # wirklich abgebucht
        s.R["wall_tax_relief"] = False                                              # ältere Regeln: keine Wirkung
        self.assertEqual(s.tax_of(mp), 12)

    def test_new_techs_gate_higher_project_levels(self):             # AP 70
        s, w = self.s, self.w
        s.found("anna", "moorufer", "Moorheim")
        s.buy_plot("anna", "moorufer", 1)
        s.contribute("anna", "moorufer", "market_square", 800, {"timber@standard": 40})            # Stufe 1 frei
        with self.assertRaises(WorldError) as cm:
            s.contribute("anna", "moorufer", "market_square", 2000, {"wooden_beam@standard": 40})   # Stufe 2 braucht Marktrecht
        self.assertIn("marktrecht", str(cm.exception))
        ms = next(x for x in s.view("anna")["sites"] if x["id"] == "moorufer")["projects"]["market_square"]
        self.assertEqual((ms["requires_tech"], ms["tech_known"]), ("marktrecht", False))             # AP 71: Client erfährt den Grund
        self.assertTrue(next(x for x in s.view("anna")["sites"] if x["id"] == "moorufer")["projects"]["road"]["tech_known"])
        self.assertEqual(w.research.R["version"], 2)
        for tech in ("marktrecht", "lagerwesen", "stadtrecht", "dampfkraft"):
            self.assertIn(tech, w.research.R["techs"])
        w.research.known.setdefault("moorufer", {})["marktrecht"] = {"day": 1, "via": "test"}
        self.assertTrue(next(x for x in s.view("anna")["sites"] if x["id"] == "moorufer")["projects"]["market_square"]["tech_known"])
        self.assertTrue(s.contribute("anna", "moorufer", "market_square", 2000, {"wooden_beam@standard": 40})["completed"])
        self.assertEqual(s.fee_discount_permille("anna"), 500)                                      # v2-Rabatt Stufe 2

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
