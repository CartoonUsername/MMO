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


    def test_moderation_mute_and_unmute(self):                                                    # AP 82–84
        gid = self.w.guilds.member_of["anna"]
        self.assertTrue(self.a.call("guild.say", text="hallo")["ok"])
        self.assertFalse(self.b.call("guild.mute", target="cleo")["ok"])                          # Ben ist nur Mitglied
        self.assertFalse(self.a.call("guild.mute", target="anna")["ok"])                          # nicht sich selbst
        self.assertFalse(self.a.call("guild.mute", target="cleo")["ok"])                          # Cleo ist nicht in der Gilde
        r = self.a.call("guild.mute", target="ben")
        self.assertTrue(r["ok"] and r["result"]["muted"])
        self.assertFalse(self.b.call("guild.say", text="hört mich jemand?")["ok"])
        self.assertEqual(self.a.call("query.guild")["result"]["mine"]["muted"], ["ben"])
        self.assertTrue(self.a.call("guild.mute", target="ben", on=False)["ok"])
        self.assertTrue(self.b.call("guild.say", text="wieder da")["ok"])
        self.assertNotIn("muted", self.w.guilds.guilds[gid])                                       # leeres Feld wird nicht gespeichert
        self.assertEqual(check_consistency(self.w), [])

    def test_officers_cannot_mute_officers_or_the_leader_and_leaving_clears_the_mute(self):
        gid = self.w.guilds.member_of["anna"]
        self.assertTrue(self.a.call("guild.role", target="ben", role="officer")["ok"])
        self.a.call("guild.invite", target="cleo")
        self.c.call("guild.accept", guild=gid)
        self.assertFalse(self.b.call("guild.mute", target="anna")["ok"])                          # Leiter nie
        self.assertTrue(self.a.call("guild.mute", target="ben")["ok"])                            # Leiter darf Offizier stummschalten
        self.a.call("guild.mute", target="ben", on=False)
        self.assertTrue(self.b.call("guild.mute", target="cleo")["ok"])                           # Offizier darf Mitglied
        self.c.call("guild.leave")
        self.assertNotIn("muted", self.w.guilds.guilds[gid])                                       # Austritt hebt die Sperre auf
        self.assertEqual(check_consistency(self.w), [])
        self.a.call("guild.invite", target="cleo")
        self.c.call("guild.accept", guild=gid)
        self.assertTrue(self.c.call("guild.say", text="neu dabei")["ok"])                         # nach Wiedereintritt nicht mehr stumm


    def test_live_push_reaches_online_members_except_the_sender(self):                          # AP 85–87
        self.b.pull(), self.a.pull(), self.c.pull()
        self.b.events.clear(), self.a.events.clear(), self.c.events.clear()
        self.assertTrue(self.a.call("guild.say", text="Hallo Gilde")["ok"])
        for bot in (self.a, self.b, self.c):
            bot.pull()
        got = lambda bot: [e for e in bot.events if e.get("ev") == "guild_chat"]
        self.assertEqual([(e["char"], e["text"], e["tag"], e["n"]) for e in got(self.b)], [("anna", "Hallo Gilde", "NW", 1)])
        self.assertEqual(got(self.a), [])                                                       # Absender bekommt keine Kopie
        self.assertEqual(got(self.c), [])                                                       # Nicht-Mitglied hört nichts
        self.a.call("guild.mute", target="ben")
        self.b.call("guild.say", text="stumm")
        self.a.pull()
        self.assertEqual([e for e in self.a.events if e.get("ev") == "guild_chat" and e["text"] == "stumm"], [])   # abgelehnte Nachricht wird nicht verteilt

    def test_offline_members_are_skipped_without_error(self):
        self.g.disconnect(self.b.sid)                                                           # Ben geht offline
        self.assertNotIn("ben", self.g.sess_of)
        self.assertTrue(self.a.call("guild.say", text="ist jemand da?")["ok"])                  # kein Fehler, Verlauf bleibt für später
        self.assertEqual(self.w.guilds.guilds[self.w.guilds.member_of["anna"]]["chat"][-1]["text"], "ist jemand da?")

    def test_roundtrip_through_persistence(self):
        from mmo_world.persistence import export_world, import_world
        import json
        self.a.call("guild.say", text="bleibt erhalten")
        env, logs = export_world(self.w)
        back = import_world(json.loads(json.dumps(env)), json.loads(json.dumps(logs)))
        self.assertEqual(back.guilds.guilds[back.guilds.member_of["anna"]]["chat"][0]["text"], "bleibt erhalten")


if __name__ == "__main__":
    unittest.main()
