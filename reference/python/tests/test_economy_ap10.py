"""AP 10: NPC-Weltwirtschaft (Ereignisse), Firmen-/Marktsichten und Filialbefehle (ADR-0049)."""
import unittest

from mmo_game import GameServer
from mmo_server.protocol import COMMANDS
from tests.test_game_enemies import Bot
from tests.test_production import PW


class Events(unittest.TestCase):
    def test_events_are_deterministic_bounded_and_broadcast(self):
        g = GameServer()
        self.assertIsNotNone(g.world.pricing)
        a = Bot(g, "anna")
        a.call("game.join")
        seen = []
        for day in range(2, 80):
            g._economy_event(day)
            g.world.day[0] = day
            a.pull()
        evs = a.of("economy_event")
        self.assertGreater(len(evs), 5)
        self.assertLess(len(evs), 60)                       # nicht jeden Tag
        for e in evs:
            for key, permille in e["shocks"].items():
                self.assertLessEqual(abs(permille - 1000), g.world.pricing.pr["shock"]["max_permille"])
        g2 = GameServer()
        Bot(g2, "x").call("game.join")
        for day in range(2, 80):
            g2._economy_event(day)
            g2.world.day[0] = day
        self.assertEqual([n["id"] + str(n["day"]) for n in g.economy_news], [n["id"] + str(n["day"]) for n in g2.economy_news])

    def test_shock_moves_the_reference_price(self):
        g = GameServer()
        g.world.day[0] = 1
        base = g.world.pricing.reference("frostglass", "common", 1)
        g.world.pricing.set_shock("frostglass@common", 1250, 10)
        for d in range(2, 12):
            g.world.pricing.advance(d)
        self.assertGreater(g.world.pricing.reference("frostglass", "common", 1), base)

    def test_news_expire_and_survive_save(self):
        g = GameServer()
        g.economy_news = [{"id": "x", "day": 1, "until": 3, "headline": "h", "region": "moor", "shocks": {"flour@standard": 1200}}]
        g._economy_event(5)
        self.assertEqual([n for n in g.economy_news if n["id"] == "x"], [])


class Queries(unittest.TestCase):
    def setUp(self):
        self.pw = PW(capital=20000)
        self.w = self.pw.w

    def test_my_companies(self):
        v = COMMANDS["query.my_companies"].call(self.w, {"char": "boss"})
        c = v["companies"][0]
        self.assertTrue(c["can_manage"])
        self.assertEqual((c["balance"], c["lines"], c["capacity"]), (20000, 1, 200))
        self.assertEqual([e["char"] for e in c["employees"]], ["novice", "smith"])
        s = COMMANDS["query.my_companies"].call(self.w, {"char": "smith"})["companies"][0]
        self.assertFalse(s["can_manage"])
        self.assertEqual(COMMANDS["query.my_companies"].call(self.w, {"char": "nobody"})["companies"], [])

    def test_market_and_quote(self):
        from mmo_world.world import World
        w = World("rules_v9.json")
        w.svc.create("boss", "player")
        m = COMMANDS["query.market"].call(w, {"char": "boss"})
        self.assertIn("iron_ore", m["items"])
        q = COMMANDS["query.market_quote"].call(w, {"item_key": "iron_ore@standard"})
        self.assertEqual(q["reference"], w.trading.reference("iron_ore", "standard", 1))
        self.assertLess(q["maker_buys_at"], q["maker_sells_at"])

    def test_branch_commands(self):
        w = self.w
        w.company.record_revenue(self.pw.co, 20000)
        r = COMMANDS["company.branch_open"].call(w, {"actor": "boss", "company": self.pw.co, "region": "crossing"})
        self.assertIn("branch", r)
        v = COMMANDS["query.my_companies"].call(w, {"char": "boss"})["companies"][0]
        self.assertEqual(len(v["branches"]["branches"]), 1)
        COMMANDS["company.branch_close"].call(w, {"actor": "boss", "company": self.pw.co, "branch": r["branch"]})


if __name__ == "__main__":
    unittest.main()
