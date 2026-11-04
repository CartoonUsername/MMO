"""Progression aus dem Spielgeschehen (AP 3, ADR-0041): Quellen, Grenzen, Wiederholbarkeit, Erkundung, Prägung."""
import unittest

from mmo_game import progression
from mmo_game.game import GameServer, load_game_rules
from tests.test_game import Bot, PATH_TO_WOLVES, fight_until_end, kinds, walk

P = load_game_rules()["progression"]


def near_node(g, bot, node_id):
    n = next(x for x in g.nodes if x["id"] == node_id)
    g.players[bot.name]["pos"] = tuple(n["pos"])


class PureTests(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()

    def test_kampferfahrung_nach_stufe_und_faktor(self):
        sim = self.g.sim
        voll = progression.fight_xp(P, sim, ["wolf", "wolf"], {"wolf": 1000})
        self.assertEqual(voll, 2 * sim["opponents"]["wolf"]["level"] * P["fight_xp_per_level"])
        self.assertEqual(progression.fight_xp(P, sim, ["wolf", "wolf"], {"wolf": 250}), 2 * (sim["opponents"]["wolf"]["level"] * P["fight_xp_per_level"] * 250 // 1000))
        self.assertEqual(progression.fight_xp(P, sim, ["wolf"], {"wolf": 0}), 0)

    def test_elementexposition_nur_mit_element_und_faktor(self):
        sim = self.g.sim
        self.assertEqual(progression.element_exposure(P, sim, ["wolf"], {"wolf": 1000}), {"nature": P["fight_element_exposure"]})
        self.assertEqual(progression.element_exposure(P, sim, ["wolf", "bear"], {"wolf": 500, "bear": 1000}),
                         {"nature": P["fight_element_exposure"] // 2, "earth": P["fight_element_exposure"]})

    def test_faehigkeitsexposition_hat_kampf_und_tagesgrenze(self):
        cmds = ["cast_ember"] * 30 + ["light"] * 5
        self.assertEqual(progression.skill_exposure(P, cmds, 0), {"fire": 6 * P["skill_exposure_max_per_fight"]})
        self.assertEqual(progression.skill_exposure(P, cmds, P["skill_exposure_daily_cap"] - 3), {"fire": 6 * 3})
        self.assertEqual(progression.skill_exposure(P, cmds, P["skill_exposure_daily_cap"]), {})
        self.assertEqual(progression.skill_exposure(P, ["light", "dodge"], 0), {})

    def test_sammeln_hat_tageslimit(self):
        voll = progression.gather_gain(P, "iron_ore@standard", 0)
        self.assertEqual(voll, ("mining", 10))
        self.assertEqual(progression.gather_gain(P, "iron_ore@standard", P["gather_daily_full"] - 1), voll)
        self.assertEqual(progression.gather_gain(P, "iron_ore@standard", P["gather_daily_full"]), ("mining", 10 * P["gather_reduced_permille"] // 1000))
        self.assertIsNone(progression.gather_gain(P, "unbekannt@standard", 0))

    def test_regeln_referenzen_sind_gueltig(self):
        g = self.g
        cee = g.world.svc.rules
        for item, (prof, xp) in P["gather"].items():
            self.assertIn(prof, cee["professions"]["all"])
            self.assertGreater(xp, 0)
        for cmd, (el, n) in P["skill_exposure"].items():
            self.assertIn(el, cee["elements"]["all"])
            self.assertIn(cmd, g.sim["skills"])
        for poi in P["pois"]:
            self.assertIn(poi["evidence"], cee["discovery"]["discoveries"][poi["discovery"]]["evidence"])
            self.assertEqual(g.terrain.nearest_walkable(tuple(poi["at"])), tuple(poi["at"]))        # Ort ist begehbar
            for e in g.R["enemies"]:                                                                  # und liegt außerhalb jeder Gegnerreichweite
                self.assertGreater((poi["at"][0] - e["at"][0]) ** 2 + (poi["at"][1] - e["at"][1]) ** 2, g.R["aggro_radius"] ** 2)
        for t in g.sim["opponents"]:
            self.assertIn(g.sim["opponents"][t].get("element"), [None] + cee["elements"]["all"])


class GameTests(unittest.TestCase):
    def test_sammeln_gibt_berufserfahrung_mit_tageslimit(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        near_node(g, a, "ore1")
        r = a.call("game.gather", node="ore1")["result"]
        self.assertEqual(r["gains"], {"profession": "mining", "xp": 10})
        self.assertEqual(g.world.svc.state("anna").parts["profession"]["xp"]["mining"], 10)
        for i in range(P["gather_daily_full"] + 3):                          # Tageslimit überschreiten (Sammelpunkt erholt sich per Tick)
            g.tick_no += g.R["node_cooldown_ticks"] + 1
            a.call("game.gather", node="ore1")
        xp = g.world.svc.state("anna").parts["profession"]["xp"]["mining"]
        voll = 10 * (P["gather_daily_full"])
        self.assertLess(xp, voll + 10 * 4)                                  # die letzten zählen nur noch ein Viertel
        self.assertGreater(xp, voll)

    def test_sieg_gibt_erfahrung_element_und_stufe(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES], reach=300)
        fight_until_end(g, [a])
        end = kinds(a, "fight_end")[0]
        self.assertEqual(end["outcome"], "victory")
        xp = 2 * g.sim["opponents"]["wolf"]["level"] * P["fight_xp_per_level"]
        self.assertEqual(end["gains"]["xp"], xp)
        self.assertEqual(end["gains"]["elements"], {"nature": 2 * P["fight_element_exposure"]})
        st = g.world.svc.state("anna").parts
        self.assertEqual(st["identity"]["xp"], xp)
        self.assertEqual(st["element"]["affinity"]["nature"], 2 * P["fight_element_exposure"])
        self.assertEqual(g.log, [])                                          # nichts abgelehnt, Live == Neuberechnung

    def test_niederlage_und_flucht_geben_nichts(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES], reach=300)
        a.call("game.fight", input="flee")
        for _ in range(20):
            g.tick()
        self.assertEqual(g.world.svc.state("anna").parts["identity"]["xp"], 0)

    def test_wiederholung_am_selben_tag_bringt_weniger(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.kills["anna|wolf"] = 5                                            # fünf Wölfe heute schon besiegt → Faktor 250 ‰ (loot_decay_permille)
        walk(g, [a], [PATH_TO_WOLVES], reach=300)
        fight_until_end(g, [a])
        gains = kinds(a, "fight_end")[0]["gains"]
        lvl = g.sim["opponents"]["wolf"]["level"]
        self.assertEqual(gains["xp"], 2 * (lvl * P["fight_xp_per_level"] * 250 // 1000))
        self.assertLess(gains["xp"], 2 * lvl * P["fight_xp_per_level"] // 3)
        self.assertEqual(gains["elements"], {"nature": 2 * (P["fight_element_exposure"] * 250 // 1000)})

    def test_erkundungsort_gibt_hinweis_einmalig(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        poi = P["pois"][0]
        g.players["anna"]["pos"] = tuple(poi["at"])
        for _ in range(12):
            g.tick()
        a.pull()
        evs = [e for e in a.events if e["ev"] == "poi"]
        self.assertEqual([e["poi"] for e in evs], [poi["id"]])
        self.assertEqual(g.world.svc.state("anna").parts["discovery"]["evidence"]["old_shrine_map"], [poi["evidence"]])
        for _ in range(20):
            g.tick()
        a.pull()
        self.assertEqual(len([e for e in a.events if e["ev"] == "poi"]), 1)             # nicht erneut

    def test_beide_hinweise_machen_die_entdeckung_abschlussreif(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        for poi in P["pois"]:
            g.players["anna"]["pos"] = tuple(poi["at"])
            for _ in range(6):
                g.tick()
        self.assertTrue(g.world.svc.discovery_progress("anna", "old_shrine_map")["ready"])
        self.assertTrue(a.call("discovery.complete", discovery="old_shrine_map")["ok"])
        self.assertIn("old_shrine_map", g.world.svc.known_discoveries("anna"))

    def test_praegung_erst_ab_schwelle_und_nur_einmal(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        self.assertEqual(a.call("game.attune", element="nature")["error"]["code"], "rejected")   # Affinität zu gering
        g.world.svc.record("anna", "element.exposure", {"element": "nature", "amount": 100})
        self.assertTrue(a.call("game.attune", element="nature")["ok"])
        self.assertEqual(a.call("game.attune", element="nature")["error"]["code"], "rejected")   # schon geprägt
        self.assertEqual(a.call("game.attune", element="drache")["error"]["code"], "rejected")

    def test_tageszaehler_beginnen_neu_und_werden_gespeichert(self):
        g = GameServer()
        g.daily["anna|gather"] = 7
        g._new_day(g.world.day[0] + 1)
        self.assertEqual(g.daily, {})


if __name__ == "__main__":
    unittest.main()
