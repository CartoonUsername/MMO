"""AP 9: Regionen, Gefahrenstufen, Zugangsbedingungen, Dungeon und Weltboss (ADR-0048)."""
import unittest

from mmo_game import GameServer
from tests.test_game_enemies import Bot


def join(g, name, pos=None):
    b = Bot(g, name)
    b.call("game.join")
    if pos:
        g.players[name]["pos"] = pos
    return b


def run_ticks(g, bots, n):
    for _ in range(n):
        g.tick()
        for b in bots:
            b.pull()


class Regions(unittest.TestCase):
    def test_rules_are_consistent(self):
        g = GameServer()
        self.assertGreaterEqual(len(g.regions), 6)
        self.assertEqual({r["danger"] for r in g.regions}, {1, 2, 3, 4, 5})
        for e in g.enemies:
            self.assertIsNotNone(g._region_at(e["home"]), e["id"])
        self.assertEqual(g._region_at((500, 500))["id"], "sunmeadow")
        self.assertEqual(g._region_at((5200, 5200))["danger"], 5)

    def test_normal_regions_are_not_level_locked_and_event_is_sent(self):
        g = GameServer()
        a = join(g, "anna", (3600, 4700))
        run_ticks(g, [a], 2)
        ev = a.of("region")
        self.assertEqual((ev[-1]["region"], ev[-1]["danger"], ev[-1]["warning"]), ("stonewaste", 5, True))   # Level 1 darf trotzdem hinein
        self.assertEqual(a.call("game.state")["result"]["you"]["region"]["id"], "stonewaste")

    def test_special_region_needs_knowledge(self):
        g = GameServer()
        a = join(g, "anna", (1400, 5400))
        g.players["anna"]["dir"] = (-1, 0)
        run_ticks(g, [a], 10)
        self.assertGreater(g.players["anna"]["pos"][0], 1300)                      # nicht hinein
        self.assertEqual(a.of("region_blocked")[0]["region"], "hiddenvale")
        g.world.discovery.gather("anna", "old_shrine_map", "shrine_mural")
        g.world.discovery.gather("anna", "old_shrine_map", "hermit_story")
        g.world.discovery.complete("anna", "old_shrine_map")
        run_ticks(g, [a], 15)
        self.assertLess(g.players["anna"]["pos"][0], 1300)                          # jetzt offen

    def test_danger_raises_loot_and_xp_bonus(self):
        g = GameServer()
        self.assertEqual(g._danger_bonus([(500, 500)]), 1000)
        self.assertEqual(g._danger_bonus([(5200, 5200)]), 1500)
        self.assertEqual(g._danger_bonus([(500, 500), (3600, 3000)]), 1250)


class WorldBossAndDungeon(unittest.TestCase):
    def test_boss_defeat_is_broadcast_and_rewards_participants(self):
        g = GameServer()
        a, b = join(g, "anna"), join(g, "ben")
        res = type("R", (), {"players": [type("P", (), {"outcome": "victory", "actions": {"light": 3}})(), type("P", (), {"outcome": "victory", "actions": {}})()]})()
        g._boss_defeated(["anna", "ben"], res, ["stone_heart_colossus"])
        a.pull(); b.pull()
        self.assertEqual(g.world.inv.balance("anna", "ward_stone@standard"), 2)
        self.assertEqual(g.world.inv.balance("ben", "ward_stone@standard"), 0)       # ohne Beitrag keine Kiste
        self.assertEqual(b.of("world_boss")[0]["state"], "defeated")                  # aber alle erfahren es

    def test_bystanders_join_a_boss_fight(self):
        g = GameServer()
        a, b = join(g, "anna", (5000, 5100)), join(g, "ben", (5050, 5100))
        boss = next(e for e in g.enemies if e["type"] == "stone_heart_colossus")
        g._start_fight("anna", [boss])
        self.assertEqual(sorted(g.fights[g.fight_of["anna"]]["chars"]), ["anna", "ben"])

    def test_dungeon_flow_and_daily_limits(self):
        g = GameServer()
        a = join(g, "anna", (700, 5400))
        g.world.svc.record("anna", "identity.xp_gained", {"amount": 10000})
        self.assertFalse(join(g, "x", (100, 100)).call("game.dungeon_enter", dungeon="alte_mine")["ok"])   # nicht am Eingang
        self.assertFalse(a.call("game.dungeon_enter", dungeon="nope")["ok"])
        self.assertFalse(a.call("game.dungeon_enter", dungeon="alte_mine")["ok"])                      # Zugang fehlt (Wissen)
        g.world.discovery.gather("anna", "old_shrine_map", "shrine_mural")
        g.world.discovery.gather("anna", "old_shrine_map", "hermit_story")
        g.world.discovery.complete("anna", "old_shrine_map")
        r = a.call("game.dungeon_enter", dungeon="alte_mine")
        self.assertTrue(r["ok"], r)
        self.assertFalse(a.call("game.dungeon_enter", dungeon="alte_mine")["ok"])                      # schon drin
        run_ticks(g, [a], 12)
        self.assertEqual(a.of("dungeon")[1]["state"], "stage")
        self.assertIn("anna", g.fight_of)
        self.assertEqual(g.fights[g.fight_of["anna"]]["types"], ["stone_imp", "stone_imp"])
        # Spieler wird besiegt/flieht -> Durchlauf scheitert, Zähler bleibt verbraucht
        a.call("game.fight", input="flee")
        run_ticks(g, [a], 60)
        self.assertEqual(a.of("dungeon")[-1]["state"], "failed")
        self.assertNotIn("anna", g.dungeon_of)
        self.assertEqual(g.daily["anna|dungeon:alte_mine"], 1)

    def test_dungeon_clear_pays_chest_once_per_day(self):
        g = GameServer()
        a = join(g, "anna", (700, 5400))
        g.world.discovery.gather("anna", "old_shrine_map", "shrine_mural")
        g.world.discovery.gather("anna", "old_shrine_map", "hermit_story")
        g.world.discovery.complete("anna", "old_shrine_map")
        # Simuliere Etappen direkt über das Ergebnis, ohne zu kämpfen
        class P:  # noqa
            outcome, actions = "victory", {"light": 1}
        class Res:  # noqa
            outcome, players = "victory", [P()]
        a.call("game.dungeon_enter", dungeon="alte_mine")
        rid = g.dungeon_of["anna"]
        run = g.dungeons[rid]
        run["stage"] = run["stages_total"] - 1
        before = g.world.inv.balance("anna", "iron_cuirass@fine")
        g._dungeon_after({"dungeon": rid, "chars": ["anna"]}, Res())
        self.assertEqual(g.world.inv.balance("anna", "iron_cuirass@fine") - before, 1)
        self.assertNotIn(rid, g.dungeons)
        g.dungeon_of["anna"] = rid = "dng-x"
        g.dungeons[rid] = {"id": rid, "dungeon": "alte_mine", "name": "x", "chars": ["anna"], "stage": 2, "stages_total": 3, "next_at": 0}
        g._dungeon_after({"dungeon": rid, "chars": ["anna"]}, Res())
        self.assertEqual(g.world.inv.balance("anna", "iron_cuirass@fine") - before, 1)               # keine zweite Kiste am selben Tag

    def test_leaving_ends_participation(self):
        g = GameServer()
        a = join(g, "anna", (700, 5400))
        g.world.discovery.gather("anna", "old_shrine_map", "shrine_mural")
        g.world.discovery.gather("anna", "old_shrine_map", "hermit_story")
        g.world.discovery.complete("anna", "old_shrine_map")
        a.call("game.dungeon_enter", dungeon="alte_mine")
        g._leave("anna")
        run_ticks(g, [], 3)
        self.assertEqual(g.dungeons, {})


if __name__ == "__main__":
    unittest.main()
