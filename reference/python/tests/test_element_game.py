"""AP 16: Spielschicht – geprägte Elemente schalten Zauber frei, game.elements (ADR-0055)."""
import unittest

from mmo_game import GameServer
from tests.test_game import Bot


class ElementGame(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()
        self.a = Bot(self.g, "anna")
        self.a.call("game.join")

    def attune(self, *elements):
        svc = self.g.world.svc
        for e in elements:
            svc.record("anna", "element.exposure", {"element": e, "amount": 1000})
            svc.record("anna", "element.attuned", {"element": e})

    def test_no_elements_by_default(self):
        r = self.a.call("game.elements")["result"]
        self.assertEqual(r["attuned"], [])
        self.assertEqual(r["switch_ticks"], 40)

    def test_attuned_element_unlocks_cast_in_kit(self):
        before = {c["cmd"] for c in self.a.call("game.kit")["result"]["commands"]}
        self.assertNotIn("cast_water", before)
        self.attune("water")
        after = {c["cmd"] for c in self.a.call("game.kit")["result"]["commands"]}
        self.assertIn("cast_water", after)
        self.assertNotIn("cast_nature", after)

    def test_two_elements_two_casts_and_overview(self):
        self.attune("water", "nature")
        kit = {c["cmd"] for c in self.a.call("game.kit")["result"]["commands"]}
        self.assertTrue({"cast_water", "cast_nature"} <= kit)
        r = self.a.call("game.elements")["result"]
        self.assertEqual(r["casts"], {"water": "cast_water", "nature": "cast_nature"})

    def test_fire_uses_existing_ember_strike(self):
        self.attune("fire")
        kit = {c["cmd"] for c in self.a.call("game.kit")["result"]["commands"]}
        self.assertIn("cast_ember", kit)

    def test_pair_unlocks_combo_cast(self):                       # AP 22
        self.attune("water", "nature")
        kit = {c["cmd"] for c in self.a.call("game.kit")["result"]["commands"]}
        self.assertIn("combo_nature_water", kit)
        self.assertEqual(self.a.call("game.elements")["result"]["combos"], {"combo_nature_water": ["nature", "water"]})

    def test_single_element_has_no_combo(self):
        self.attune("water")
        kit = {c["cmd"] for c in self.a.call("game.kit")["result"]["commands"]}
        self.assertFalse([c for c in kit if c.startswith("combo_")])

    def test_three_attunements_unlock_triple_and_pairs(self):
        self.g.world.svc.record("anna", "identity.xp_gained", {"amount": 400000})      # drittes Element: Endgame-Stufe
        self.attune("water", "nature", "earth")
        combos = self.a.call("game.elements")["result"]["combos"]
        self.assertEqual(set(combos), {"combo_earth_nature", "combo_earth_water", "combo_nature_water", "combo_earth_nature_water"})


if __name__ == "__main__":
    unittest.main()
