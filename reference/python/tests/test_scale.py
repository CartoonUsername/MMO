"""AP 14: Interessenverwaltung, Lastmessung, einstellbare Verbindungsgrenze (ADR-0053)."""
import unittest

from mmo_game import GameServer, loadtest
from mmo_game.net import NetServer
from tests.test_game_enemies import Bot


class Scale(unittest.TestCase):
    def test_crowd_snapshot_is_capped_to_nearest_players(self):
        g = GameServer()
        cap = g.R["interest"]["max_visible_players"]
        bots = [Bot(g, f"p{i:03d}") for i in range(cap + 30)]
        for i, b in enumerate(bots):
            b.call("game.join")
            g.players[b.name]["pos"] = (3000 + i * 10, 1000)
        snap = g._snapshot_for("p000")
        self.assertEqual(len(snap["players"]), cap)
        far = {b.name for b in bots[cap + 1:]}
        self.assertFalse(far & {p["char"] for p in snap["players"]})          # die Nächsten gewinnen
        self.assertEqual([p["char"] for p in snap["players"]], sorted(p["char"] for p in snap["players"]))

    def test_looks_are_computed_once_per_tick(self):
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        for x in (a, b):
            x.call("game.join")
        n = [0]
        orig = g.world.equipment.appearance
        g.world.equipment.appearance = lambda c: (n.__setitem__(0, n[0] + 1), orig(c))[1]
        g.tick()
        for _ in range(5):
            g._snapshot_for("anna"); g._snapshot_for("ben")
        self.assertLessEqual(n[0], 2)

    def test_loadtest_runs_and_stays_in_tick_budget(self):
        r = loadtest.run(40, 60)
        self.assertEqual(r["bots"], 40)
        self.assertLess(r["max_ms"], 100)                                    # Tickbudget bei 10 Ticks/s (großzügig, kein Leistungstest)

    def test_connection_limit_is_configurable_and_validated(self):
        self.assertEqual(NetServer(max_connections=50).max_connections, 50)
        with self.assertRaises(ValueError):
            NetServer(max_connections=0)
        self.assertEqual(NetServer().max_connections, 16)
