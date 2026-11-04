"""AP 8: Ausrüstung mit Wirkung und Transmog (ADR-0047)."""
import unittest

from mmo_sim import simulate_pack, SimError
from mmo_sim.rules import load_sim_rules
from mmo_world import persistence
from mmo_world.equipment import load_equipment_rules, validate_equipment_rules
from mmo_world.errors import WorldError
from mmo_world.world import World

C8 = load_sim_rules("sim_rules_v8.json")


def world(cls="warrior", level_xp=0):
    w = World("rules_v9.json")
    w.svc.create("a", "player")
    if cls:
        w.svc.record("a", "identity.class_chosen", {"base_class": cls})
    if level_xp:
        w.svc.record("a", "identity.xp_gained", {"amount": level_xp})
    return w


class Sim(unittest.TestCase):
    def test_gear_changes_damage_and_is_validated(self):
        inp = [[0, "heavy"], [40, "flee"]]
        base = simulate_pack(C8, ["wolf"], [{"level": 1, "inputs": inp}]).opponent_hp
        gear = simulate_pack(C8, ["wolf"], [{"level": 1, "inputs": inp, "gear": {"heavy_damage_permille": 1500}}]).opponent_hp
        self.assertLess(gear, base)
        for bad in ({"nope": 1}, {"heavy_damage_permille": 0}, {"heavy_damage_permille": True}, [1]):
            with self.assertRaises(SimError):
                simulate_pack(C8, ["wolf"], [{"level": 1, "inputs": inp, "gear": bad}])

    def test_armor_reduces_damage_taken(self):
        inp = [[0, "light"], [200, "flee"]]
        a = simulate_pack(C8, ["bear"], [{"level": 1, "inputs": inp}]).players[0]
        b = simulate_pack(C8, ["bear"], [{"level": 1, "inputs": inp, "gear": {"damage_taken_permille": 500}}]).players[0]
        self.assertLess(a.player_hp, simulate_pack(C8, ["bear"], [{"level": 1, "inputs": [[0, "flee"]]}]).players[0].player_hp)  # ohne Rüstung wird Schaden genommen
        self.assertGreater(b.player_hp, a.player_hp)                                                                    # Rüstung mindert ihn


class Rules(unittest.TestCase):
    def test_valid(self):
        validate_equipment_rules(load_equipment_rules(), World("rules_v9.json").svc.rules)


class Wear(unittest.TestCase):
    def test_equip_moves_item_not_duplicates(self):
        w = world()
        w.inv.deposit("a", "iron_blade@common", 1)
        w.equipment.equip("a", "iron_blade@common")
        self.assertEqual((w.inv.balance("a", "iron_blade@common"), w.inv.balance("worn:a", "iron_blade@common"), w.inv.total("iron_blade@common")), (0, 1, 1))
        with self.assertRaises(WorldError):
            w.equipment.equip("a", "iron_blade@common")                  # keiner mehr im Inventar
        w.equipment.unequip("a", "weapon")
        self.assertEqual(w.inv.balance("a", "iron_blade@common"), 1)

    def test_swap_returns_old_item(self):
        w = world()
        w.inv.deposit("a", "iron_blade@common", 1)
        w.inv.deposit("a", "iron_blade@fine", 1)
        w.equipment.equip("a", "iron_blade@common")
        w.equipment.equip("a", "iron_blade@fine")
        self.assertEqual((w.inv.balance("a", "iron_blade@common"), w.equipment.worn["a"]["weapon"]), (1, "iron_blade@fine"))
        self.assertEqual(w.equipment.check(), [])

    def test_requirements(self):
        w = world(cls=None)
        w.inv.deposit("a", "hunter_bow@common", 1)
        w.inv.deposit("a", "iron_cuirass@common", 1)
        with self.assertRaises(WorldError):
            w.equipment.equip("a", "hunter_bow@common")                  # keine Klasse
        w.svc.record("a", "identity.class_chosen", {"base_class": "warrior"})
        with self.assertRaises(WorldError):
            w.equipment.equip("a", "hunter_bow@common")                  # falsche Klasse
        with self.assertRaises(WorldError):
            w.equipment.equip("a", "iron_cuirass@common")                # Stufe 5 nötig
        with self.assertRaises(WorldError):
            w.equipment.equip("a", "coin@gold")                          # keine Ausrüstung
        self.assertEqual(w.equipment.worn, {})

    def test_light_vs_heavy_tradeoff_and_grade(self):
        w = world(level_xp=10000)
        for k in ("leather_jerkin@common", "iron_cuirass@common", "iron_cuirass@fine"):
            w.inv.deposit("a", k, 1)
        w.equipment.equip("a", "leather_jerkin@common")
        light = w.equipment.effects("a")
        w.equipment.equip("a", "iron_cuirass@common")
        heavy = w.equipment.effects("a")
        self.assertLess(heavy["damage_taken_permille"], light["damage_taken_permille"])     # mehr Schutz
        self.assertLess(heavy["move_permille"], light["move_permille"])                    # aber langsamer
        self.assertEqual(heavy["dodge_cost_delta"], 6)
        w.equipment.equip("a", "iron_cuirass@fine")
        self.assertLess(w.equipment.effects("a")["damage_taken_permille"], heavy["damage_taken_permille"])  # bessere Güte stärker
        self.assertGreaterEqual(w.equipment.effects("a")["damage_taken_permille"], w.equipment.R["caps"]["damage_taken_permille_min"])

    def test_sim_gear_excludes_movement(self):
        w = world()
        w.inv.deposit("a", "traveler_boots@common", 1)
        w.equipment.equip("a", "traveler_boots@common")
        self.assertEqual(w.equipment.sim_gear("a"), {})
        self.assertEqual(w.equipment.move_permille("a"), 1040)


class Transmog(unittest.TestCase):
    def test_look_needs_wardrobe_and_is_separate_from_stats(self):
        w = world(level_xp=10000)
        w.inv.deposit("a", "iron_cuirass@common", 1)
        w.inv.deposit("a", "leather_jerkin@common", 1)
        w.equipment.equip("a", "iron_cuirass@common")
        stats = w.equipment.effects("a")
        with self.assertRaises(WorldError):
            w.equipment.set_look("a", "chest", "leather_jerkin")           # nie getragen
        w.equipment.equip("a", "leather_jerkin@common")
        w.equipment.equip("a", "iron_cuirass@common")
        w.equipment.set_look("a", "chest", "leather_jerkin")
        self.assertEqual(w.equipment.effects("a"), stats)                  # Werte unverändert
        ap = w.equipment.appearance("a")["chest"]
        self.assertEqual((ap["look"], ap["transmog"]), ("gear/leather_jerkin", True))
        with self.assertRaises(WorldError):
            w.equipment.set_look("a", "weapon", "leather_jerkin")          # falscher Slot
        w.equipment.set_look("a", "chest", None)
        self.assertEqual(w.equipment.appearance("a")["chest"]["look"], "gear/iron_cuirass")


class Persistence(unittest.TestCase):
    def test_roundtrip_and_unchanged_snapshots(self):
        w = world()
        self.assertNotIn("equipment", w.snapshot())
        w.inv.deposit("a", "iron_blade@common", 1)
        w.equipment.equip("a", "iron_blade@common")
        env, logs = persistence.export_world(w)
        w2 = persistence.import_world(env, logs)
        self.assertEqual(w2.equipment.to_json(), w.equipment.to_json())
        self.assertEqual(persistence.check_consistency(w2), [])


class Game(unittest.TestCase):
    def test_gear_drops_deterministic_and_speed(self):
        from mmo_game.game import GameServer
        g = GameServer()
        g.world.svc.create("anna", "player")
        r1 = g._gear_gains("anna", ["wolf"] * 40)
        g2 = GameServer()
        g2.world.svc.create("anna", "player")
        self.assertEqual(r1, g2._gear_gains("anna", ["wolf"] * 40))
        self.assertTrue(set(r1) <= {"leather_jerkin@common"})


if __name__ == "__main__":
    unittest.main()
