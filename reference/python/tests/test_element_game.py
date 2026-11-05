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

    def test_combo_riders_are_reported(self):                     # AP 32
        self.attune("water", "nature")
        r = self.a.call("game.elements")["result"]
        self.assertEqual(set(r["combo_riders"]), set(r["combos"]))
        self.assertTrue(all(isinstance(v, dict) and v for v in r["combo_riders"].values()))
        self.assertGreater(r["ticks_per_second"], 0)

    def test_single_element_has_no_combo(self):
        self.attune("water")
        kit = {c["cmd"] for c in self.a.call("game.kit")["result"]["commands"]}
        self.assertFalse([c for c in kit if c.startswith("combo_")])

    def test_three_attunements_unlock_triple_and_pairs(self):
        self.g.world.svc.record("anna", "identity.xp_gained", {"amount": 400000})      # drittes Element: Endgame-Stufe
        self.attune("water", "nature", "earth")
        combos = self.a.call("game.elements")["result"]["combos"]
        self.assertEqual(set(combos), {"combo_earth_nature", "combo_earth_water", "combo_nature_water", "combo_earth_nature_water"})


class SpecializationGame(unittest.TestCase):                      # AP 34: Zweigwahl im Spiel aktiv (game_rules_v19, ADR-0069)
    def test_specialize_over_the_protocol(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.world.svc.record("anna", "profession.work", {"profession": "smithing", "xp": 50})
        r = a.call("profession.specialize", profession="smithing", branch="refining")
        self.assertEqual((r["ok"], r["result"]["paid"]), (True, 0))
        self.assertEqual(a.call("profession.specialize", profession="smithing", branch="heavy_arms")["ok"], False)   # Abklingzeit
        self.assertEqual(g.world.svc.profession_branches("anna")["smithing"]["chosen"], "refining")

    def test_character_query_reports_specialization_rules(self):          # AP 37
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        sp = a.call("query.character")["result"]["specialization"]
        self.assertEqual((sp["cooldown_days"], sp["cost_first"], sp["cost_change"], sp["focus_xp_permille"]), (7, 0, 500, 250))
        self.assertFalse([k for k in sp if k.startswith("_")])

    def test_specialize_abuse_is_rejected_without_side_effects(self):      # AP 39
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        a.call("game.join"), b.call("game.join")
        for c in ("anna", "ben"):
            g.world.svc.record(c, "profession.work", {"profession": "smithing", "xp": 50})
        coins = g.world.inv.balance("anna", g.world.trading.coin)
        bad = [dict(profession="smithing", branch="nope"), dict(profession="mining", branch="refining"), dict(profession="smithing", branch=7),
               dict(profession=["smithing"], branch="refining"), dict(profession="smithing", branch=None), dict(profession="__proto__", branch="refining"),
               dict(profession="smithing", branch="refining", day=99)]
        for args in bad:
            self.assertFalse(a.call("profession.specialize", **args)["ok"], args)
        # fremde Figur: das Gateway bindet "char" an die Sitzung
        r = g.handle(a.sid, {"v": 1, "id": "x1", "cmd": "profession.specialize", "args": {"char": "ben", "profession": "smithing", "branch": "refining"}})
        self.assertFalse(r["ok"])
        self.assertIsNone(g.world.svc.profession_branches("ben")["smithing"]["chosen"])
        self.assertIsNone(g.world.svc.profession_branches("anna")["smithing"]["chosen"])
        self.assertEqual(g.world.inv.balance("anna", g.world.trading.coin), coins)
        self.assertTrue(a.call("profession.specialize", profession="smithing", branch="refining")["ok"])
        self.assertEqual(g.world.svc.profession_branches("ben")["smithing"]["chosen"], None)


if __name__ == "__main__":
    unittest.main()
