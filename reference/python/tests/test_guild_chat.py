"""AP 66–69: Gildenchat (ADR-0078)."""
import unittest

from mmo_game import GameServer
from mmo_world.persistence import check_consistency
from tests.test_game import Bot


class GuildChat(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()
        self.w = self.g.world
        self.a, self.b, self.c = Bot(self.g, "anna"), Bot(self.g, "ben"), Bot(self.g, "cleo")
        for bot in (self.a, self.b, self.c):
            bot.call("game.join")
            self.w.inv.deposit(bot.name, self.w.trading.coin, 20000)
        self.assertTrue(self.a.call("guild.found", name="Nordwacht", tag="NW")["ok"])
        self.assertTrue(self.a.call("guild.invite", target="ben")["ok"])
        gid = self.w.guilds.member_of["anna"]
        self.assertTrue(self.b.call("guild.accept", guild=gid)["ok"])

    def chat(self, bot):
        return bot.call("query.guild")["result"]["mine"]["chat"]

    def test_members_see_messages_outsiders_cannot_write_or_read(self):
        self.assertTrue(self.a.call("guild.say", text="Hallo zusammen")["ok"])
        self.assertTrue(self.b.call("guild.say", text="  Servus  ")["ok"])
        self.assertEqual([(m["n"], m["char"], m["text"]) for m in self.chat(self.b)], [(1, "anna", "Hallo zusammen"), (2, "ben", "Servus")])
        self.assertFalse(self.c.call("guild.say", text="reinschleichen")["ok"])                   # keine Gilde
        self.assertIsNone(self.c.call("query.guild")["result"]["mine"])                           # und kein Mitlesen
        self.b.call("guild.leave")
        self.assertFalse(self.b.call("guild.say", text="noch da?")["ok"])
        self.assertEqual(len(self.chat(self.a)), 2)                                               # Verlauf bleibt

    def test_bad_text_is_rejected_and_nothing_is_stored(self):
        for bad in ("", "   ", "x" * 65, "zeile\nzwei", "tab\there", "\x00", 5, None, ["a"], True):
            self.assertFalse(self.a.call("guild.say", text=bad)["ok"], bad)
        self.assertEqual(self.chat(self.a), [])
        self.assertTrue(self.a.call("guild.say", text="ä" * 64)["ok"])                            # genau die Obergrenze (Protokoll: 64 Zeichen)

    def test_daily_limit_and_history_cap(self):
        for i in range(30):
            self.w.guilds.say("anna", f"m{i}")                                                   # direkt: das Gateway begrenzt zusätzlich die Aufrufrate
        self.assertFalse(self.a.call("guild.say", text="zu viel")["ok"])                         # 31. am selben Tag
        self.assertTrue(self.b.call("guild.say", text="ben darf noch")["ok"])                    # Limit gilt je Figur
        self.w.day[0] += 1
        self.assertTrue(self.a.call("guild.say", text="neuer Tag")["ok"])
        g = self.w.guilds.guilds[self.w.guilds.member_of["anna"]]
        self.assertLessEqual(len(g["chat"]), 50)
        self.assertEqual(g["chat"][-1]["text"], "neuer Tag")
        self.assertEqual(len(self.chat(self.a)), 30)                                             # Sicht zeigt die letzten 30
        self.assertEqual(check_consistency(self.w), [])

    def test_unused_chat_leaves_the_guild_state_unchanged(self):
        g = self.w.guilds.guilds[self.w.guilds.member_of["anna"]]
        self.assertNotIn("chat", g)
        self.assertNotIn("chat_n", g)

    def test_roundtrip_through_persistence(self):
        from mmo_world.persistence import export_world, import_world
        import json
        self.a.call("guild.say", text="bleibt erhalten")
        env, logs = export_world(self.w)
        back = import_world(json.loads(json.dumps(env)), json.loads(json.dumps(logs)))
        self.assertEqual(back.guilds.guilds[back.guilds.member_of["anna"]]["chat"][0]["text"], "bleibt erhalten")


if __name__ == "__main__":
    unittest.main()
