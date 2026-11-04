"""Klassen-Kits im Kampf (Spielregeln v2, AP 1): Befehle je Grundklasse, Kampfdaten für die Skill-Leiste, Konsistenz mit der Neuberechnung."""
import unittest

from mmo_game.game import GameServer, load_game_rules
from tests.test_game import Bot, PATH_TO_WOLVES, fight_until_end, kinds, walk

BASE = {"light", "dodge", "block", "flee", "sweep"}


def cmds(bot):
    return {c["cmd"] for c in bot.call("game.kit")["result"]["commands"]}


class KitTests(unittest.TestCase):
    def test_regeln_v2_kits_sind_gueltig(self):
        R = load_game_rules()
        self.assertGreaterEqual(int(R["version"]), 2)
        g = GameServer()
        cat = g.world.svc.rules["combat"]["abilities"]
        self.assertEqual(sorted(k for k in R["class_kits"] if not k.startswith("_")), ["archer", "shaman_alchemist", "warrior"])
        for cls, abilities in ((k, v) for k, v in R["class_kits"].items() if not k.startswith("_")):
            self.assertIn(cls, g.world.svc.rules["identity"]["classes"])
            self.assertEqual(len(set(abilities)), len(abilities))
            for a in abilities:
                self.assertIn(a, cat)

    def test_kit_je_klasse(self):
        g = GameServer()
        bots = {n: Bot(g, n) for n in ("ohne", "krieger", "schuetze", "schamane")}
        for n, c in (("krieger", "warrior"), ("schuetze", "archer"), ("schamane", "shaman_alchemist")):
            g.world.svc.record(n, "identity.class_chosen", {"base_class": c})
        for b in bots.values():
            b.call("game.join")
        self.assertEqual(cmds(bots["ohne"]), BASE)
        self.assertEqual(cmds(bots["krieger"]), BASE | {"heavy", "stun"})
        self.assertEqual(cmds(bots["schuetze"]), BASE | {"heavy", "dash", "slow"})
        self.assertEqual(cmds(bots["schamane"]), BASE | {"cast_ember", "heal", "shield", "slow"})
        info = {c["cmd"]: c for c in bots["krieger"].call("game.kit")["result"]["commands"]}
        self.assertEqual((info["heavy"]["cost"], info["heavy"]["cooldown"]), (25, 20))
        self.assertEqual(info["light"]["cost"], 8)
        self.assertEqual(bots["krieger"].call("game.kit")["result"]["stamina_max"], 100)

    def _kampf(self, klasse, befehle):
        g = GameServer()
        a = Bot(g, "anna")
        if klasse:
            g.world.svc.record("anna", "identity.class_chosen", {"base_class": klasse})
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES], reach=300)
        self.assertIn("anna", g.fight_of)
        fid = g.fight_of["anna"]
        sim_player = g.fights[fid]["live"]._sim.ps[0]
        for c in befehle:                                                 # je Befehl einmal, mit Abstand (Sperr- und Abklingzeiten laufen ab)
            a.call("game.fight", input=c)
            for _ in range(70):
                g.tick()
        ignoriert = sim_player.ignored
        fight_until_end(g, [a], spam=("light", "heavy"), every=8)
        return g, a, ignoriert

    def test_kit_befehle_werden_im_kampf_angenommen_ohne_klasse_ignoriert(self):
        _, _, ohne = self._kampf(None, ["heavy", "stun"])
        _, _, krieger = self._kampf("warrior", ["heavy", "stun"])
        self.assertGreater(ohne, 0)
        self.assertEqual(krieger, 0)

    def test_fight_start_enthaelt_das_kit_und_neuberechnung_stimmt(self):
        g, a, _ = self._kampf("warrior", ["heavy"])
        start = kinds(a, "fight_start")[0]
        self.assertEqual({c["cmd"] for c in start["kit"]}, BASE | {"heavy", "stun"})
        self.assertEqual(len(start["enemy_ids"]), len(start["opponents"]))      # Zuordnung der Anzeige
        self.assertEqual(g.log, [])                                   # Live-Ergebnis == Neuberechnung aus dem Eingabeprotokoll
        self.assertEqual(kinds(a, "fight_end")[0]["outcome"], "victory")


if __name__ == "__main__":
    unittest.main()
