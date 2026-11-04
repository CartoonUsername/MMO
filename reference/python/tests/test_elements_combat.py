"""AP 4b: Elementwirkung im Kampf (sim_rules_v8, ADR-0043)."""
import unittest

from mmo_sim.rules import element_permille, load_sim_rules
from mmo_sim import SimError, simulate_pack
from mmo_sim.rules import validate_element_rules

V7 = load_sim_rules("sim_rules_v7.json")
V8 = load_sim_rules("sim_rules_v8.json")


class ElementCombat(unittest.TestCase):
    def test_v7_unchanged(self):
        self.assertNotIn("elements", V7)
        self.assertEqual(element_permille(V7, "fire", "nature"), 1000)

    def test_factors(self):
        self.assertEqual(element_permille(V8, "fire", "nature"), 1250)   # stark
        self.assertEqual(element_permille(V8, "nature", "fire"), 800)    # schwach (Gegenseite ist stark)
        self.assertEqual(element_permille(V8, "fire", "fire"), 750)      # gleich
        self.assertEqual(element_permille(V8, "fire", "light"), 1000)    # neutral
        self.assertEqual(element_permille(V8, None, "nature"), 1000)

    def test_v8_keeps_v7_otherwise(self):
        a = {k: v for k, v in V7.items() if k not in ("version", "skills")}
        b = {k: v for k, v in V8.items() if k not in ("version", "skills", "elements")}
        self.assertEqual(a, b)

    def test_invalid_rules(self):
        bad = {**V8, "elements": {**V8["elements"], "weak_permille": 1200}}
        with self.assertRaises(SimError):
            validate_element_rules(bad)

    def test_fire_hits_nature_harder(self):
        def dealt(cfg, enemy, until=2):
            r = simulate_pack(cfg, [enemy], [{"level": 1, "inputs": [[0, "cast_ember"], [until, "flee"]]}])
            return cfg["opponents"][enemy]["hp"] - r.opponent_hp
        self.assertEqual(dealt(V7, "wolf"), 180)
        self.assertEqual(dealt(V8, "wolf"), 225)     # Natur: stark (+25 %)
        self.assertEqual(dealt(V8, "bear"), 180)     # Erde: neutral
        # Schaden über Zeit wird mitskaliert: 40 Ticks, alle 10 Ticks 20 (v7) bzw. 25 (v8)
        self.assertEqual(dealt(V7, "bear", 45) - 180, 80)
        self.assertEqual(dealt(V8, "wolf", 45) - 225, 100)


if __name__ == "__main__":
    unittest.main()
