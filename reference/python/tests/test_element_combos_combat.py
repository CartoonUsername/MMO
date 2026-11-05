"""AP 22: Kombinationszauber (Paare und Dreier) im Kampf (sim_rules_v11, game_rules_v14, ADR-0061)."""
import unittest
from itertools import combinations

from mmo_sim import SimError, simulate_pack
from mmo_sim.rules import load_sim_rules, validate_element_rules, validate_sim_rules
from mmo_game.game import load_game_rules

V10 = load_sim_rules("sim_rules_v10.json")
V11 = load_sim_rules("sim_rules_v11.json")
EL = ["fire", "water", "earth", "nature", "electric", "ice", "wind", "light", "shadow"]
CAST = {"fire": "cast_ember", **{e: "cast_" + e for e in EL[1:]}}


def dealt(cfg, cmd, enemy):
    r = simulate_pack(cfg, [enemy], [{"level": 1, "inputs": [[0, cmd], [2, "flee"]]}])
    return cfg["opponents"][enemy]["hp"] - r.opponent_hp


class ComboCombat(unittest.TestCase):
    def test_rules_valid_and_v10_untouched(self):
        validate_sim_rules(V11)
        self.assertFalse(any("elements" in s for s in V10["skills"].values() if isinstance(s, dict)))

    def test_every_pair_and_triple_exists(self):
        names = {n for n, s in V11["skills"].items() if isinstance(s, dict) and "elements" in s}
        self.assertEqual(len([n for n in names if len(V11["skills"][n]["elements"]) == 2]), 36)
        self.assertEqual(len([n for n in names if len(V11["skills"][n]["elements"]) == 3]), 84)
        self.assertEqual(len({V11["skills"][n]["ability"] for n in names}), 120)

    def test_pair_beats_single_and_triple_beats_pair(self):
        single = dealt(V11, CAST["light"], "bear")
        pair = dealt(V11, "combo_light_water", "bear")
        triple = dealt(V11, "combo_earth_light_water", "bear")
        self.assertLess(single, pair)
        self.assertLess(pair, triple)

    def test_best_element_factor_applies(self):
        # Bär = Erde: Wasser ist stark (1250), Licht neutral (1000) -> Mischung nimmt das Beste
        self.assertEqual(dealt(V11, "combo_light_water", "bear"), 260 * 1250 // 1000)
        # Wolf = Natur: Feuer stark, Wasser neutral
        self.assertEqual(dealt(V11, "combo_fire_water", "wolf"), 260 * 1250 // 1000)

    def test_same_element_enemy_not_worse_than_single(self):
        self.assertGreater(dealt(V11, "combo_earth_nature", "bear"), dealt(V11, CAST["earth"], "bear"))

    def test_combo_needs_no_switch_wait(self):
        r = simulate_pack(V11, ["bear"], [{"level": 1, "inputs": [[0, "cast_water"], [20, "combo_light_nature"], [100, "flee"]]}])
        one = simulate_pack(V11, ["bear"], [{"level": 1, "inputs": [[0, "cast_water"], [100, "flee"]]}])
        self.assertLess(r.opponent_hp, one.opponent_hp)

    def test_invalid_elements_rejected(self):
        for bad in (["water", "fire"], ["fire"], ["fire", "fire"], ["fire", "nothing"], ["fire", "ice", "wind", "light"]):
            cfg = {**V11, "skills": {**V11["skills"], "combo_fire_water": {**V11["skills"]["combo_fire_water"], "elements": bad}}}
            with self.assertRaises(SimError, msg=str(bad)):
                validate_element_rules(cfg)
        both = {**V11, "skills": {**V11["skills"], "combo_fire_water": {**V11["skills"]["combo_fire_water"], "element": "fire"}}}
        with self.assertRaises(SimError):
            validate_element_rules(both)

    def test_game_rules_use_v12(self):
        g = load_game_rules()
        self.assertEqual(g["sim_rules"], "sim_rules_v12.json")
        self.assertTrue(g["combo_abilities"])
        self.assertEqual(len(list(combinations(EL, 2))), 36)


if __name__ == "__main__":
    unittest.main()
