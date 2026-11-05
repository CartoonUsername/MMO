"""AP 18: Gildenforschung und Gilden-Raids (community_rules_v2, game_rules_v11, ADR-0057)."""
import unittest

from mmo_game import GameServer
from mmo_world.community import load_community_rules, validate_community_rules
from mmo_world.errors import WorldError
from tests.test_game_enemies import Bot

COIN = "coin@gold"
ENTRY = (1100, 5400)


def join(g, name, pos=None):
    b = Bot(g, name)
    b.call("game.join")
    if pos:
        g.players[name]["pos"] = pos
    return b


def unlock(g, c):
    g.world.discovery.gather(c, "old_shrine_map", "shrine_mural")
    g.world.discovery.gather(c, "old_shrine_map", "hermit_story")
    g.world.discovery.complete(c, "old_shrine_map")


def guild_of(g, leader, *others):
    g.world.inv.deposit(leader, COIN, 5000)
    gid = g.world.guilds.found(leader, "Nordwacht", "NW")
    for o in others:
        g.world.guilds.invite(leader, o)
        g.world.guilds.accept(o, gid)
    return gid


class Research(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()
        self.a = join(self.g, "anna")
        self.b = join(self.g, "ben")
        self.gid = guild_of(self.g, "anna", "ben")
        self.gs = self.g.world.guilds
        self.gs.set_role("anna", "ben", "member")
        t = self.gs.treasury(self.gid)
        self.g.world.inv.deposit(t, COIN, 20000)
        self.g.world.inv.deposit(t, "timber@standard", 200)
        self.g.world.inv.deposit(t, "iron_ingot@standard", 100)

    def day(self, n):
        self.g.world.day[0] += n

    def test_rules_valid(self):
        r = load_community_rules()
        self.assertEqual(r["version"], "2")
        validate_community_rules(r)
        r["guild"]["research"]["techs"]["banners"]["requires"] = "gibtsnicht"
        with self.assertRaises(WorldError):
            validate_community_rules(r)

    def test_only_leader_or_officer_and_cost_from_treasury(self):
        with self.assertRaises(WorldError):
            self.gs.research_start("ben", "banners")
        before = self.g.world.inv.balance(self.gs.treasury(self.gid), COIN)
        self.gs.research_start("anna", "banners")
        self.assertEqual(before - self.g.world.inv.balance(self.gs.treasury(self.gid), COIN), 1500)

    def test_takes_days_and_raises_capacity(self):
        g = self.gs.guilds[self.gid]
        self.assertEqual(self.gs.capacity(g), 20)
        self.gs.research_start("anna", "banners")
        self.assertEqual(self.gs.capacity(g), 20)                       # noch nicht fertig
        self.day(1)
        self.assertEqual(self.gs.capacity(g), 20)
        self.day(1)
        self.assertEqual(self.gs.capacity(g), 25)
        self.assertEqual(self.gs.view("anna")["mine"]["research"]["techs"][1]["status"], "done")

    def test_one_at_a_time_prerequisite_and_no_repeat(self):
        with self.assertRaises(WorldError):
            self.gs.research_start("anna", "strongbox")                 # braucht Spähtrupps
        self.gs.research_start("anna", "scouting")
        with self.assertRaises(WorldError):
            self.gs.research_start("anna", "banners")                   # läuft schon eine
        self.day(2)
        self.gs.research_start("anna", "strongbox")
        self.day(3)
        self.assertEqual(self.gs.bonus(self.gs.guilds[self.gid], "raid_treasury_permille"), 250)
        with self.assertRaises(WorldError):
            self.gs.research_start("anna", "scouting")

    def test_not_enough_in_treasury_changes_nothing(self):
        self.g.world.inv.apply(self.gs.treasury(self.gid), {COIN: 20000}, {})
        with self.assertRaises(Exception):
            self.gs.research_start("anna", "banners")
        self.assertIsNone(self.gs._res(self.gs.guilds[self.gid])["active"])

    def test_survives_snapshot_roundtrip(self):
        self.gs.research_start("anna", "banners")
        text = self.gs.to_json()
        self.gs.guilds.clear()
        self.gs.load(text)
        self.day(2)
        self.assertEqual(self.gs.capacity(self.gs.guilds[self.gid]), 25)


class Raid(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()
        self.a = join(self.g, "anna", ENTRY)
        self.b = join(self.g, "ben", ENTRY)
        self.c = join(self.g, "cora", ENTRY)
        for n in ("anna", "ben", "cora"):
            unlock(self.g, n)
        self.gid = guild_of(self.g, "anna", "ben")

    def test_raid_is_in_rules_and_marked(self):
        self.assertTrue(self.g.dungeon_rules["steinherz_krypta"]["guild_raid"])
        self.assertTrue(self.g._cmd_world("", "anna", {})["dungeons"]["steinherz_krypta"]["raid"])
        self.assertFalse(self.g._cmd_world("", "anna", {})["dungeons"]["alte_mine"]["raid"])

    def test_needs_guild_and_enough_members(self):
        self.assertFalse(self.c.call("game.dungeon_enter", dungeon="steinherz_krypta")["ok"])        # keine Gilde
        self.g.players["ben"]["pos"] = (100, 100)
        self.assertFalse(self.a.call("game.dungeon_enter", dungeon="steinherz_krypta")["ok"])        # zu wenige am Eingang

    def test_only_guild_members_join_and_party_is_ignored(self):
        pid = self.g.world.parties.create("anna")
        inv = self.g.world.parties.invite("anna", "cora")
        self.g.world.parties.accept("cora", inv if isinstance(inv, str) else pid)
        self.assertIsNotNone(self.g.world.parties.view("cora"))                                 # cora ist in anna's Gruppe, aber nicht in der Gilde
        r = self.a.call("game.dungeon_enter", dungeon="steinherz_krypta")
        self.assertTrue(r["ok"], r)
        self.assertEqual(sorted(r["result"]["party"]), ["anna", "ben"])
        self.assertNotIn("cora", self.g.dungeon_of)

    def test_one_entry_per_guild_per_day_then_scouting_adds_one(self):
        self.assertTrue(self.a.call("game.dungeon_enter", dungeon="steinherz_krypta")["ok"])
        for c in ("anna", "ben"):
            self.g.dungeon_of.pop(c, None)
        self.g.dungeons.clear()
        self.assertFalse(self.a.call("game.dungeon_enter", dungeon="steinherz_krypta")["ok"])
        self.g.daily = {k: v for k, v in self.g.daily.items() if not k.endswith("dungeon:steinherz_krypta")}   # persönliche Zutritte zurücksetzen
        gs = self.g.world.guilds
        gs.guilds[self.gid].setdefault("research", {"done": [], "active": None})["done"].append("scouting")
        self.assertTrue(self.a.call("game.dungeon_enter", dungeon="steinherz_krypta")["ok"])

    def test_clear_pays_guild_treasury_with_strongbox_and_chronicle(self):
        gs = self.g.world.guilds
        gs.guilds[self.gid].setdefault("research", {"done": [], "active": None})["done"] += ["scouting", "strongbox"]
        r = self.a.call("game.dungeon_enter", dungeon="steinherz_krypta")
        self.assertTrue(r["ok"], r)
        rid = self.g.dungeon_of["anna"]
        self.g.dungeons[rid]["stage"] = self.g.dungeons[rid]["stages_total"] - 1

        class P:
            outcome, actions = "victory", {"light": 1}

        class Res:
            outcome, players = "victory", [P(), P()]
        before = gs.guilds[self.gid]["points"]
        self.g._dungeon_after({"dungeon": rid, "chars": ["anna", "ben"]}, Res())
        t = gs.treasury(self.gid)
        self.assertEqual(self.g.world.inv.balance(t, COIN), 1200 * 1250 // 1000)
        self.assertEqual(self.g.world.inv.balance(t, "resonance_dust@standard"), 40 * 1250 // 1000)
        self.assertEqual(gs.guilds[self.gid]["points"] - before, 2 * 8)                    # 8 Punkte je Beteiligtem
        self.assertEqual(self.g.world.chronicle.entries[-1]["kind"], "raid_cleared")
        self.assertEqual(self.g.world.inv.balance("anna", "ward_stone@standard"), 1)       # persönliche Truhe wie im Dungeon

    def test_failed_raid_pays_nothing(self):
        self.a.call("game.dungeon_enter", dungeon="steinherz_krypta")
        rid = self.g.dungeon_of["anna"]

        class Res:
            outcome, players = "defeat", []
        self.g._dungeon_after({"dungeon": rid, "chars": ["anna", "ben"]}, Res())
        self.assertEqual(self.g.world.inv.balance(self.g.world.guilds.treasury(self.gid), COIN), 0)


if __name__ == "__main__":
    unittest.main()
