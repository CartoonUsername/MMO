"""AP 24: Klassenwirkung der Kombinationszauber (sim_rules_v13, game_rules_v16, ADR-0063)."""
import unittest

from mmo_sim import SimError, simulate_pack
from mmo_sim.rules import load_sim_rules

V12 = load_sim_rules("sim_rules_v12.json")
V13 = load_sim_rules("sim_rules_v13.json")


def fight(cfg, cmd, cls=None, enemy="wolf", end=200, at=0):
    spec = {"level": 1, "inputs": [[at, cmd], [end, "flee"]]}
    if cls:
        spec["class"] = cls
    return simulate_pack(cfg, [enemy], [spec]).players[0]


class ComboClasses(unittest.TestCase):
    def test_v12_untouched(self):
        self.assertNotIn("combo_classes", V12)
        with self.assertRaises(SimError):
            fight(V12, "combo_electric_fire", "archer")

    def test_no_class_equals_v12(self):
        self.assertEqual(fight(V13, "combo_electric_fire").damage_ticks, fight(V12, "combo_electric_fire").damage_ticks)

    def test_archer_slows_longer(self):
        base = fight(V13, "combo_electric_fire", "warrior").damage_ticks
        arch = fight(V13, "combo_electric_fire", "archer").damage_ticks
        self.assertGreater(arch[2], base[2])

    def test_warrior_takes_less_damage_from_defense_rider(self):
        a = fight(V13, "combo_earth_fire", None, "bear", 120, 40)
        w = fight(V13, "combo_earth_fire", "warrior", "bear", 120, 40)
        self.assertGreater(w.player_hp, a.player_hp)

    def test_shaman_gets_more_stamina_back(self):
        ins = [[0, "combo_light_water"], [14, "combo_nature_water"], [28, "combo_ice_water"], [42, "combo_water_wind"], [56, "combo_earth_water"], [70, "flee"]]

        def run(cls):
            spec = {"level": 1, "inputs": ins, **({"class": cls} if cls else {})}
            return simulate_pack(V13, ["bear"], [spec]).players[0]
        plain, shaman = run(None), run("shaman_alchemist")
        self.assertEqual(shaman.ignored_inputs, 0)
        self.assertGreater(plain.ignored_inputs, 0)                       # ohne Klassenbonus reicht die Ausdauer nicht für alle fünf

    def test_unknown_class_rejected(self):
        with self.assertRaises(SimError):
            fight(V13, "combo_electric_fire", "wizard")


if __name__ == "__main__":
    unittest.main()
