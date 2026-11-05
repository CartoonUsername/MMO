"""AP 21: Raid-Balancing mit den Testspielern und Etappen nach Gruppengröße (game_rules_v13, ADR-0060)."""
import unittest

from mmo_game import GameServer
from mmo_game.game import load_game_rules
from mmo_sim.balance import fight
from mmo_sim.rules import load_sim_rules
from tests.test_game_enemies import Bot  # noqa: F401
from tests.test_guild_raid import ENTRY, COIN, join, unlock

SIM = load_sim_rules("sim_rules_v10.json")
BOSS = ["stone_heart_colossus", "stone_imp"]


def wins(skill, n):
    return fight(SIM, BOSS, [25] * n, skill, "balance-spawn").outcome == "victory"


class Measured(unittest.TestCase):
    """Messwerte der Balancing-Bots (Richtwerte, keine Spielerdaten): Hält die Mindestgröße des Raids, was die Regel verspricht?"""

    def test_boss_needs_a_real_group(self):
        self.assertFalse(wins("good", 2))
        self.assertTrue(wins("good", 4))
        self.assertTrue(wins("good", 8))

    def test_min_members_matches_measurement(self):
        r = load_game_rules()["dungeons"]["steinherz_krypta"]["guild_raid"]
        self.assertEqual(r["min_members"], 4)
        self.assertTrue(wins("good", r["min_members"]))

    def test_deterministic(self):
        a = fight(SIM, BOSS, [25] * 6, "average", "balance-spawn")
        self.assertEqual(a, fight(SIM, BOSS, [25] * 6, "average", "balance-spawn"))


class StagesBySize(unittest.TestCase):
    def raid(self, n):
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

    def test_too_small_group_is_refused(self):
        g, bots = self.raid(3)
        r = bots[0].call("game.dungeon_enter", dungeon="steinherz_krypta")
        self.assertFalse(r["ok"])

    def test_four_members_get_three_stages_six_get_four(self):
        g, bots = self.raid(4)
        r = bots[0].call("game.dungeon_enter", dungeon="steinherz_krypta")
        self.assertTrue(r["ok"], r)
        self.assertEqual(g.dungeons[g.dungeon_of["p0"]]["stages_total"], 3)
        g, bots = self.raid(6)
        bots[0].call("game.dungeon_enter", dungeon="steinherz_krypta")
        run = g.dungeons[g.dungeon_of["p0"]]
        self.assertEqual((run["stages_total"], [s["name"] for s in run["stages"]][-2:]), (4, ["Splitterwache", "Das Steinherz"]))

    def test_extra_stage_is_fought_in_order(self):
        g, bots = self.raid(6)
        bots[0].call("game.dungeon_enter", dungeon="steinherz_krypta")
        seen = []
        for _ in range(3):
            run = g.dungeons[g.dungeon_of["p0"]]
            for _ in range(60):
                g.tick()
                if run.get("fight"):
                    break
            fid = g.fight_of["p0"]
            seen.append(g.fights[fid]["types"])
            run["fight"] = False                                  # Etappe als erledigt behandeln
            del g.fight_of["p0"]
            for c in run["chars"]:
                g.fight_of.pop(c, None)
            g.fights.pop(fid, None)
            run["next_at"] = 0
        self.assertEqual(seen[0], ["stone_warden", "stone_imp", "stone_imp"])
        self.assertEqual(seen[2], ["stone_warden", "stone_warden", "stone_imp"])


if __name__ == "__main__":
    unittest.main()
