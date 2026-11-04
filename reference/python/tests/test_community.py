import json
import unittest

from mmo_world.errors import WorldError
from mmo_world.persistence import check_consistency
from mmo_world.world import World

COIN = "coin@gold"


class GuildChronicle(unittest.TestCase):
    def setUp(self):
        self.w = World("rules_v9.json")
        self.g, self.c = self.w.guilds, self.w.chronicle
        for n in ("anna", "ben", "cora"):
            self.w.svc.create(n, "player")
            self.w.inv.deposit(n, COIN, 20000)
            self.w.inv.deposit(n, "timber@standard", 100)

    def test_lifecycle_roles_treasury(self):
        g = self.g
        gid = g.found("anna", "Nordwacht", "nw")
        with self.assertRaises(WorldError):
            g.found("ben", "nordwacht", "XY")                     # Name vergeben
        with self.assertRaises(WorldError):
            g.accept("ben", gid)                                  # keine Einladung
        g.invite("anna", "ben"); g.accept("ben", gid)
        with self.assertRaises(WorldError):
            g.invite("ben", "cora")                               # Mitglied darf nicht einladen
        g.deposit("ben", COIN, 500)
        with self.assertRaises(WorldError):
            g.withdraw("ben", COIN, 1)                            # nur Offiziere/Leitung
        g.set_role("anna", "ben", "officer"); g.withdraw("ben", COIN, 200)
        self.assertEqual(self.w.inv.balance("ben", COIN), 20000 - 500 + 200)
        with self.assertRaises(WorldError):
            g.leave("anna")                                       # Leitung erst übergeben
        g.set_role("anna", "ben", "leader")
        g.leave("anna")
        self.assertEqual(g.view("ben")["mine"]["role"], "leader")
        g.disband("ben")
        self.assertEqual(self.w.inv.balance("ben", COIN), 20000 - 500 + 200 + 300)   # Kasse zurück
        self.assertEqual((g.guilds, g.member_of), ({}, {}))

    def test_house_raises_capacity(self):
        g = self.g
        gid = g.found("anna", "Nordwacht", "NW")
        self.assertEqual(g.capacity(g.guilds[gid]), 20)
        g.contribute("anna", 1500, {"timber@standard": 40})
        self.assertEqual(g.capacity(g.guilds[gid]), 30)
        self.assertGreater(g.guilds[gid]["points"], 0)

    def test_chronicle_firsts_titles_prestige(self):
        w, c = self.w, self.c
        w.settlements.found("anna", "moorufer", "Moorheim")
        e = c.record("boss_defeated", ["anna", "ben"], key="boss:x", name="Golem")
        self.assertTrue(e["first"])
        self.assertIsNone(c.record("boss_defeated", ["cora"], key="boss:x", name="Golem"))    # nur der erste Sieg zählt
        self.assertIn("Bezwinger von Golem", [t["name"] for t in c.titles["ben"]])
        self.assertNotIn("cora", c.titles)
        p = c.prestige("anna")
        self.assertEqual(p["points"], 20 + 40)
        page = c.page(0, 1)
        self.assertEqual((page["total"], page["entries"][0]["kind"]), (2, "boss_defeated"))   # neueste zuerst
        snap = w.snapshot()
        self.assertEqual(json.loads(c.to_json()), snap["chronicle"])
        self.assertEqual(check_consistency(w), [])
        with self.assertRaises(WorldError):
            c.page(0, 500)


class GameHooks(unittest.TestCase):
    def test_commands_and_boss_hook(self):
        from mmo_game import GameServer
        from mmo_server.protocol import COMMANDS
        from tests.test_game_enemies import Bot
        for k in ("guild.found", "query.guild", "query.chronicle", "query.prestige"):
            self.assertIn(k, COMMANDS)
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.world.inv.deposit("anna", COIN, 5000)
        self.assertTrue(a.call("guild.found", name="Nordwacht", tag="NW")["ok"])
        class R:  # minimaler Kampfausgang
            class P:
                outcome, actions = "victory", [1]
            players = [P()]
        t = next(iter(g.boss_rules))
        g._boss_defeated(["anna"], R(), [t])
        a.pull()
        self.assertTrue(a.of("chronicle"))
        self.assertEqual(g.handle(a.sid, {"v": 1, "id": "q", "cmd": "query.chronicle", "args": {}})["result"]["total"], 2)       # Gildengründung + Weltboss
        self.assertGreater(a.call("query.guild")["result"]["mine"]["points"], 0)
        self.assertEqual(a.call("query.prestige")["result"]["points"], 50)
