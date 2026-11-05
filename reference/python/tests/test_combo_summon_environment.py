"""AP 26: Beschwörung und Umgebung der Kombinationszauber (sim_rules_v15, game_rules_v18, ADR-0065)."""
import unittest

from mmo_sim import SimError, simulate_pack
from mmo_sim.rules import load_sim_rules, validate_sim_rules

V14 = load_sim_rules("sim_rules_v14.json")
V15 = load_sim_rules("sim_rules_v15.json")


def run(cfg, inputs, enemy="bear"):
    return simulate_pack(cfg, [enemy], [{"level": 1, "inputs": inputs}])


class SummonEnvironment(unittest.TestCase):
    def test_rules_valid_and_v14_untouched(self):
        validate_sim_rules(V15)
        self.assertFalse(any({"dot_permille", "stagger_ticks"} & set(s.get("riders", {})) for s in V14["skills"].values() if isinstance(s, dict)))

    def test_riders_follow_domains(self):
        sk = V15["skills"]
        self.assertEqual(sk["combo_fire_nature"]["riders"]["dot_permille"], 1500)       # Natur: Beschwörung
        self.assertEqual(sk["combo_earth_fire"]["riders"]["stagger_ticks"], 20)         # Erde: Umgebung
        self.assertNotIn("stagger_ticks", sk["combo_fire_water"].get("riders", {}))

    def test_summon_boosts_damage_over_time(self):
        a = run(V14, [[0, "combo_fire_nature"], [300, "flee"]])
        b = run(V15, [[0, "combo_fire_nature"], [300, "flee"]])
        self.assertLess(b.opponent_hp, a.opponent_hp)
        self.assertEqual(a.opponent_hp - b.opponent_hp, 72)                            

    def test_environment_makes_the_enemy_vulnerable(self):
        ins = [[0, "combo_earth_fire"], [15, "light"], [300, "flee"]]
        a, b = run(V14, ins), run(V15, ins)
        self.assertLess(b.opponent_hp, a.opponent_hp)                                   # präziser Treffer (90 statt 40)

    def test_invalid_riders_rejected(self):
        base = V15["skills"]["combo_earth_fire"]
        for bad in ({"stagger_ticks": 0}, {"dot_permille": -5}, {"dot_permille": True}):
            cfg = {**V15, "skills": {**V15["skills"], "combo_earth_fire": {**base, "riders": bad}}}
            with self.assertRaises(SimError, msg=str(bad)):
                validate_sim_rules(cfg)


if __name__ == "__main__":
    unittest.main()
