"""AP 19: größere Kampfgruppen für Raids und Weltbosse (sim_rules_v10, game_rules_v12, ADR-0058)."""
import unittest

from mmo_game import GameServer
from mmo_sim import SimError, simulate_pack
from mmo_sim.rules import load_sim_rules, validate_sim_rules
from tests.test_game_enemies import Bot
from tests.test_guild_raid import COIN, ENTRY, join, unlock

V9 = load_sim_rules("sim_rules_v9.json")
V10 = load_sim_rules("sim_rules_v10.json")
PLAN = [[0, "light"], [12, "light"], [30, "heavy"], [60, "light"], [100, "stun"], [150, "light"]]


def fight(cfg, n, enemies=("wolf", "bear")):
    return simulate_pack(cfg, list(enemies), [{"level": 5, "inputs": PLAN} for _ in range(n)])


class SimGroups(unittest.TestCase):
    def test_v9_unchanged_and_v10_differs_only_in_group_size(self):
        self.assertEqual(V9["group"]["max_party"], 4)
        a = {k: v for k, v in V9.items() if k not in ("version", "group")}
        b = {k: v for k, v in V10.items() if k not in ("version", "group")}
        self.assertEqual(a, b)
        self.assertEqual({k: v for k, v in V9["group"].items() if k != "max_party"}, {k: v for k, v in V10["group"].items() if k not in ("max_party", "_comment_ap19")})
        validate_sim_rules(V10)

    def test_limits(self):
        with self.assertRaises(SimError):
            fight(V9, 5)
        self.assertEqual(len(fight(V10, 8).players), 8)
        with self.assertRaises(SimError):
            fight(V10, 9)

    def test_eight_player_fight_is_deterministic(self):
        self.assertEqual(fight(V10, 8), fight(V10, 8))

    def test_opponents_scale_with_group_size(self):
        base = V10["opponents"]["wolf"]["hp"]
        one = fight(V10, 1, ("wolf",))
        self.assertEqual(one.opponents[0] + 0, one.opponents[0])
        # Gegner-Lebenspunkte wachsen um 600 Promille je zusätzlichem Mitglied
        r8 = simulate_pack(V10, ["wolf"], [{"level": 5, "inputs": [[0, "flee"]]} for _ in range(8)])
        self.assertEqual(r8.opponents[0], base * (1000 + 600 * 7) // 1000)


class GameLargeGroups(unittest.TestCase):
    def raid_setup(self, n):
        g = GameServer()
        names = [f"p{i}" for i in range(n)]
        bots = [join(g, c, ENTRY) for c in names]
        for c in names:
            unlock(g, c)
        g.world.inv.deposit(names[0], COIN, 5000)
        gid = g.world.guilds.found(names[0], "Nordwacht", "NW")
        for c in names[1:]:
            g.world.guilds.invite(names[0], c)
            g.world.guilds.accept(c, gid)
        return g, bots

    def test_default_rules_use_v10(self):
        g = GameServer()
        self.assertEqual(g.sim["group"]["max_party"], 8)
        self.assertEqual(g.world.parties.pr["max_size"], 4)               # normale Gruppen bleiben bei 4

    def test_raid_takes_up_to_eight_guild_members(self):
        g, bots = self.raid_setup(10)
        r = bots[0].call("game.dungeon_enter", dungeon="steinherz_krypta")
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["result"]["party"]), 8)
        self.assertEqual(r["result"]["party"][0], "p0")

    def test_raid_stage_fight_has_all_members(self):
        g, bots = self.raid_setup(8)
        bots[0].call("game.dungeon_enter", dungeon="steinherz_krypta")
        for _ in range(12):
            g.tick()
        fid = g.fight_of["p0"]
        self.assertEqual(len(g.fights[fid]["chars"]), 8)
        self.assertEqual(len(g.fights[fid]["specs"]), 8)

    def test_raid_max_members_rule_is_honoured(self):
        g, bots = self.raid_setup(8)
        g.dungeon_rules["steinherz_krypta"]["guild_raid"]["max_members"] = 3
        r = bots[0].call("game.dungeon_enter", dungeon="steinherz_krypta")
        self.assertEqual(len(r["result"]["party"]), 3)

    def test_normal_dungeon_stays_at_four(self):
        g = GameServer()
        names = ["a", "b", "c", "d", "e"]
        bots = [join(g, c, (700, 5400)) for c in names]
        for c in names:
            unlock(g, c)
        g.world.parties.create("a")
        for c in names[1:4]:
            iid = g.world.parties.invite("a", c)
            g.world.parties.accept(c, iid)
        with self.assertRaises(Exception):
            iid = g.world.parties.invite("a", "e")
            g.world.parties.accept("e", iid)
        r = bots[0].call("game.dungeon_enter", dungeon="alte_mine")
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["result"]["party"]), 4)

    def test_world_boss_gathers_up_to_eight(self):
        g = GameServer()
        names = [f"w{i}" for i in range(10)]
        for c in names:
            join(g, c, (5000, 5100))
        boss = next(e for e in g.enemies if e["type"] == "stone_heart_colossus")
        g._start_fight("w0", [boss])
        self.assertEqual(len(g.fights[g.fight_of["w0"]]["chars"]), 8)


if __name__ == "__main__":
    unittest.main()
