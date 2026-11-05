"""Prüfung der Kampfereignisse im Spielserver: keine doppelten Ereignisse, ungültige Client-Eingaben, Gruppenkampf (ADR-0037).
Ergänzt test_game_enemies (Inhalt der Ereignisse) um Eigenschaften über ganze Kämpfe."""
import unittest

from mmo_game import GameServer
from tests.test_game_enemies import Bot, fight, start
from mmo_game import load_game_rules

BAD_INPUTS = [None, 7, 3.5, True, [], {}, ["light"], {"a": 1}, "", " ", "LIGHT", "light ", "light\n", "x" * 5000, "target_9", "target_0", "target_-1",
              "../../etc/passwd", "flee;light", "‮flee", "cast_ember" * 3]


class AuditTests(unittest.TestCase):
    def full_fight(self, pos, names=("anna",), cmds=("light", "dodge", "block", "heavy"), every=6):
        g = GameServer(load_game_rules("game_rules_v19.json"))
        bots = [Bot(g, n) for n in names]
        for b in bots:
            b.call("game.join")
            g.players[b.name]["pos"] = pos
        if len(bots) > 1:                                                        # Gruppe: nur Mitglieder kämpfen mit
            bots[0].call("party.form")
            bots[0].call("party.invite", target=bots[1].name)
            inv = bots[1].call("query.party_invites")["result"][0]["id"]
            self.assertTrue(bots[1].call("party.accept", invite=inv)["ok"])
        for _ in range(300):
            g.tick()
            for b in bots:
                b.pull()
            if bots[0].name in g.fight_of:
                break
        fight(g, bots, cmds, every)
        return g, bots

    def test_jedes_ereignis_kommt_genau_einmal(self):
        for pos in ((3000, 1000), (2200, 1800)):
            g, (a,) = self.full_fight(pos)
            with self.subTest(pos=pos):
                self.assertEqual(len(a.of("fight_start")), 1)
                self.assertEqual(len(a.of("fight_end")), 1)                              # fight_left (Niederlage/Flucht) kommt zusätzlich, aber höchstens einmal und davor
                self.assertLessEqual(len(a.of("fight_left")), 1)
                order = [e["ev"] for e in a.events if e["ev"] in ("fight_start", "fight_left", "fight_end")]
                self.assertEqual(order[0], "fight_start")
                self.assertEqual(order[-1], "fight_end")
                keys = [(e["ev"], e["fight"], e["t"], e.get("enemy"), e.get("ability"), e.get("type")) for e in a.events if e["ev"] in ("telegraph", "enemy_event")]
                self.assertEqual(len(keys), len(set(keys)))
                ticks = [e["tick"] for e in a.of("fight")]
                self.assertEqual(len(ticks), len(set(ticks)))
                self.assertEqual(ticks, sorted(ticks))

    def test_jede_ankuendigung_hat_hoechstens_ein_ergebnis(self):
        g, (a,) = self.full_fight((3000, 1000))
        res = {}
        for e in a.of("enemy_event"):
            if e["type"] in ("resolved", "interrupted"):
                k = (e["enemy"], e["ability"], e["t"] if e["type"] == "resolved" else None)
                res[k] = res.get(k, 0) + 1
        self.assertTrue(all(v == 1 for v in res.values()), res)

    def test_gruppenkampf_liefert_jedem_teilnehmer_genau_ein_ende_und_gleiche_ankuendigungen(self):
        g, (a, b) = self.full_fight((3000, 1000), names=("anna", "ben"))
        self.assertTrue(a.of("fight_start") and b.of("fight_start"))
        self.assertEqual(len(a.of("fight_start")), 1)
        self.assertEqual(len(b.of("fight_start")), 1)
        self.assertEqual(a.of("fight_start")[0]["fight"], b.of("fight_start")[0]["fight"])
        for x in (a, b):
            self.assertEqual(len(x.of("fight_end")), 1)
            self.assertLessEqual(len(x.of("fight_left")), 1)
        ta = [(e["t"], e["enemy"], e["ability"]) for e in a.of("telegraph")]
        tb = [(e["t"], e["enemy"], e["ability"]) for e in b.of("telegraph")]
        common = set(ta) & set(tb)
        self.assertTrue(common)                                                  # beide sehen dieselben Ankündigungen

    def test_ungueltige_eingaben_im_kampf_werden_abgelehnt_und_veraendern_nichts(self):
        g = GameServer(load_game_rules("game_rules_v19.json"))
        a = Bot(g, "anna")
        self.assertTrue(start(g, a, (3000, 1000)))
        live = g.fights[g.fight_of["anna"]]["live"]
        before = [list(p.inputs) for p in live._sim.ps]
        for bad in BAD_INPUTS:
            r = a.call("game.fight", input=bad)
            with self.subTest(bad=repr(bad)[:30]):
                self.assertFalse(r["ok"])
                self.assertIn(r["error"]["code"], ("rejected", "bad_request"))
        self.assertEqual([list(p.inputs) for p in live._sim.ps], before)
        r = a.call("game.fight")                                                 # input fehlt
        self.assertFalse(r["ok"])

    def test_eingaben_ausserhalb_des_kampfs_und_fremde_figuren(self):
        g = GameServer(load_game_rules("game_rules_v19.json"))
        a, b = Bot(g, "anna"), Bot(g, "ben")
        a.call("game.join")
        self.assertFalse(a.call("game.fight", input="light")["ok"])             # nicht im Kampf
        r = g.handle(a.sid, {"v": 1, "id": "x", "cmd": "game.fight", "args": {"char": "ben", "input": "light"}})
        self.assertEqual(r["error"]["code"], "forbidden")                        # fremde Figur
        for args in ({"dx": 2, "dy": 0}, {"dx": "1", "dy": 0}, {"dx": None, "dy": 0}, {"dx": 1}, {"dx": 1.0, "dy": 0}, {"dx": True, "dy": 0}):
            with self.subTest(args=args):
                self.assertFalse(a.call("game.move", **args)["ok"])
        self.assertFalse(a.call("game.gather", node=["x"])["ok"])
        self.assertFalse(a.call("game.gather", node="gibt_es_nicht")["ok"])

    def test_gesendete_befehle_werden_nur_einmal_gezaehlt(self):
        g = GameServer(load_game_rules("game_rules_v19.json"))
        a = Bot(g, "anna")
        self.assertTrue(start(g, a, (3000, 1000)))
        live = g.fights[g.fight_of["anna"]]["live"]
        n0 = len(live._sim.ps[0].inputs)
        self.assertTrue(a.call("game.fight", input="dodge")["ok"])
        self.assertEqual(len(live._sim.ps[0].inputs), n0 + 1)


if __name__ == "__main__":
    unittest.main()
