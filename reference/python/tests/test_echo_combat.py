"""AP 17: Kampfwirkung der Kampfechos (echo_rules_v2, ADR-0056)."""
import unittest

from mmo_game import GameServer
from mmo_world.echo import load_echo_rules, validate_echo_rules
from mmo_world.errors import WorldError
from mmo_world.world import World
from tests.test_game import Bot


def setup(klass="warrior"):
    w = World("rules_v9.json")
    w.svc.create("a", "player")
    w.svc.record("a", "identity.class_chosen", {"base_class": klass})
    return w


def own(w, tradition, role, level):
    eid = w.echo.mint(tradition, "a")
    w.echo.activate("a", eid)
    w.echo.equip("a", eid, role)
    w.echo.echoes[eid]["resonance"] = level
    return eid


class EchoCombat(unittest.TestCase):
    def test_rules_valid_and_invalid_profile(self):
        r = load_echo_rules()
        self.assertEqual(r["version"], 2)
        validate_echo_rules(r)
        bad = {**r, "combat": {**r["combat"], "profiles": {"wolf_tradition": {"unknown_effect": 5}}}}
        with self.assertRaises(WorldError):
            validate_echo_rules(bad)

    def test_no_echo_no_effect(self):
        w = setup()
        self.assertEqual(w.echo.sim_effects("a"), {})
        self.assertEqual(w.echo.granted_abilities("a"), [])

    def test_effect_grows_with_resonance(self):
        w = setup()
        e = own(w, "wolf_tradition", "main", 0)
        self.assertEqual(w.echo.sim_effects("a"), {})                     # Stufe 0: keine Wirkung
        w.echo.echoes[e]["resonance"] = 10
        self.assertEqual(w.echo.sim_effects("a"), {"heavy_damage_permille": 1060, "dodge_cost_delta": -1})
        w.echo.echoes[e]["resonance"] = 30
        self.assertEqual(w.echo.sim_effects("a"), {"heavy_damage_permille": 1180, "dodge_cost_delta": -3})

    def test_stone_reduces_damage_and_block(self):
        w = setup()
        own(w, "stone_tradition", "main", 30)
        self.assertEqual(w.echo.sim_effects("a"), {"damage_taken_permille": 880, "block_damage_permille": 820})

    def test_hybrid_is_weaker_and_effects_combine(self):
        w = setup()
        own(w, "wolf_tradition", "main", 20)
        own(w, "stone_tradition", "hybrid", 20)
        fx = w.echo.sim_effects("a")
        self.assertEqual(fx["heavy_damage_permille"], 1120)
        self.assertEqual(fx["damage_taken_permille"], 960)                # 1000 - 4*10 (halbe Stärke)

    def test_same_effect_from_two_traditions_multiplies(self):
        w = setup()
        own(w, "wolf_tradition", "main", 20)
        own(w, "ember_tradition", "hybrid", 20)
        self.assertEqual(w.echo.sim_effects("a")["heavy_damage_permille"], 1120 * 1030 // 1000)

    def test_mastery_strengthens(self):
        w = setup()
        own(w, "wolf_tradition", "main", 20)
        w.echo.mastery["a"] = {"wolf_tradition": 300}                     # Stufe 2
        self.assertEqual(w.echo.mastery_level("a", "wolf_tradition"), 2)
        self.assertEqual(w.echo.sim_effects("a")["heavy_damage_permille"], 1000 + 6 * (20 * 1080 // 1000))

    def test_abilities_main_always_hybrid_with_mastery(self):
        w = setup()
        own(w, "wolf_tradition", "main", 1)
        own(w, "stone_tradition", "hybrid", 1)
        self.assertEqual(w.echo.granted_abilities("a"), ["power_strike", "flowing_step"])
        w.echo.mastery["a"] = {"stone_tradition": 100}
        self.assertEqual(w.echo.granted_abilities("a"), ["power_strike", "flowing_step", "shield_wall"])

    def test_unequipping_removes_effect(self):
        w = setup()
        e = own(w, "wolf_tradition", "main", 30)
        w.echo.unequip("a", e)
        self.assertEqual(w.echo.sim_effects("a"), {})

    def test_view_exposes_combat(self):
        w = setup()
        own(w, "wolf_tradition", "main", 10)
        self.assertEqual(w.echo.view("a")["combat"]["effects"]["heavy_damage_permille"], 1060)


class EchoGame(unittest.TestCase):
    def test_spec_gear_and_kit_use_echo(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.world.svc.record("anna", "identity.class_chosen", {"base_class": "warrior"})
        eid = g.world.echo.mint("stone_tradition", "anna")
        g.world.echo.activate("anna", eid)
        g.world.echo.equip("anna", eid, "main")
        g.world.echo.echoes[eid]["resonance"] = 30
        self.assertEqual(g._sim_gear("anna")["damage_taken_permille"], 880)
        self.assertIn("shield_wall", g._kit_abilities("anna"))
        spec = g.encounters.pack_specs(["anna"], {}, {"anna": g._kit_abilities("anna")}, {"anna": g._sim_gear("anna")})[0]
        self.assertEqual(spec["gear"]["block_damage_permille"], 820)


if __name__ == "__main__":
    unittest.main()
