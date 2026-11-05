"""AP 16: aktives Elementmanagement im Kampf (sim_rules_v9, game_rules_v10, ADR-0055)."""
import unittest

from mmo_sim import SimError, simulate_pack
from mmo_sim.rules import load_sim_rules, validate_element_rules, validate_sim_rules
from mmo_game.game import load_game_rules

V8 = load_sim_rules("sim_rules_v8.json")
V9 = load_sim_rules("sim_rules_v9.json")
CAST = {"fire": "cast_ember", **{e: "cast_" + e for e in ["water", "earth", "nature", "electric", "ice", "wind", "light", "shadow"]}}
ELEMENTS = ["fire", "water", "earth", "nature", "electric", "ice", "wind", "light", "shadow"]


def run(cfg, inputs, enemy="wolf"):
    return simulate_pack(cfg, [enemy], [{"level": 1, "inputs": inputs}])


class ElementManagement(unittest.TestCase):
    def test_rules_valid_and_v8_untouched(self):
        validate_sim_rules(V9)
        self.assertNotIn("switch_ticks", V8["elements"])
        self.assertNotIn("cast_water", V8["skills"])

    def test_every_element_has_a_cast(self):
        got = {s["element"] for n, s in V9["skills"].items() if not n.startswith("_") and "element" in s}
        self.assertEqual(got, set(ELEMENTS))
        self.assertEqual(len({s["ability"] for n, s in V9["skills"].items() if not n.startswith("_") and "element" in s}), 9)

    def test_game_rules_cover_all_elements(self):
        g = load_game_rules()
        sim = load_sim_rules(g["sim_rules"])                              # Standardregeln (ab AP 19 sim_rules_v10) behalten die Elementzauber
        self.assertEqual(sim["elements"]["switch_ticks"], 40)
        self.assertEqual(set(g["element_abilities"]), set(ELEMENTS))
        for el, ab in g["element_abilities"].items():
            self.assertTrue(any(s.get("ability") == ab for s in sim["skills"].values() if isinstance(s, dict)), el)

    def test_same_element_repeats_without_switch_delay(self):
        # Abklingzeit 80 Ticks gilt weiter; Wechselzeit (40) spielt bei gleichem Element keine Rolle
        base = V9["opponents"]["bear"]["hp"]
        one = run(V9, [[0, "cast_water"], [100, "flee"]], "bear")
        two = run(V9, [[0, "cast_water"], [80, "cast_water"], [100, "flee"]], "bear")
        self.assertLess(two.opponent_hp, one.opponent_hp)

    def test_switch_too_early_is_ignored(self):
        early = run(V9, [[0, "cast_water"], [20, "cast_nature"], [100, "flee"]], "bear")
        late = run(V9, [[0, "cast_water"], [60, "cast_nature"], [100, "flee"]], "bear")
        base = V9["opponents"]["bear"]["hp"]
        one = run(V9, [[0, "cast_water"], [100, "flee"]], "bear")
        self.assertEqual(base - early.opponent_hp, base - one.opponent_hp)      # zweiter Zauber ignoriert
        self.assertLess(late.opponent_hp, one.opponent_hp)                      # nach der Wechselzeit wirkt er

    def test_v8_has_no_switch_limit(self):
        a = run(V8, [[0, "cast_ember"], [20, "cast_ember"], [100, "flee"]], "bear")
        self.assertIsNotNone(a)

    def test_invalid_switch_ticks(self):
        bad = {**V9, "elements": {**V9["elements"], "switch_ticks": -1}}
        with self.assertRaises(SimError):
            validate_element_rules(bad)

    def test_element_matchup_still_applies(self):
        def dealt(el, enemy):
            r = run(V9, [[0, CAST[el]], [2, "flee"]], enemy)
            return V9["opponents"][enemy]["hp"] - r.opponent_hp
        self.assertEqual(dealt("fire", "wolf"), 225)       # Natur-Gegner: Feuer stark
        self.assertEqual(dealt("water", "bear"), 225)      # Erde-Gegner: Wasser stark
        self.assertEqual(dealt("light", "bear"), 180)      # neutral


if __name__ == "__main__":
    unittest.main()
