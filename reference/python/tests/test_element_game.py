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


if __name__ == "__main__":
    unittest.main()
