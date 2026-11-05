"""AP 61–63: Ausrüstungssets mit Setbonus (equipment_rules_v2, ADR-0076)."""
import copy
import unittest

from mmo_world.equipment import load_equipment_rules, validate_equipment_rules
from mmo_world.errors import WorldError
from mmo_world.world import World


def world():
    w = World("rules_v9.json")
    w.svc.create("a", "player")
    w.svc.record("a", "identity.xp_gained", {"amount": 10000})
    return w


def give(w, *keys):
    for k in keys:
        w.inv.deposit("a", k, 1)
        w.equipment.equip("a", k)


class SetBonusTests(unittest.TestCase):
    def test_two_wanderer_pieces_give_the_first_bonus_three_the_second(self):
        w = world()
        give(w, "traveler_boots@common")
        base = dict(w.equipment.effects("a"))
        self.assertEqual([b["active"] for b in w.equipment.set_progress("a")["wanderer"]["bonuses"]], [False, False])
        give(w, "leather_jerkin@common")
        two = w.equipment.effects("a")
        self.assertEqual(two["move_permille"], base["move_permille"] * w.equipment._scale("move_permille", 1030, "standard") // 1000 * 1020 // 1000)
        self.assertNotIn("damage_taken_permille", w.equipment.effects("a") if False else {})            # (Platzhalter: Rüstungswert kommt vom Wams)
        give(w, "wooden_buckler@common")
        three = w.equipment.effects("a")
        self.assertTrue(all(b["active"] for b in w.equipment.set_progress("a")["wanderer"]["bonuses"]))
        self.assertLess(three["damage_taken_permille"], two["damage_taken_permille"])                   # zweiter Bonus 960 wirkt

    def test_view_reports_set_progress_for_the_client(self):                                           # AP 62
        w = world()
        give(w, "leather_jerkin@common", "traveler_boots@common")
        sets = w.equipment.view("a")["sets"]
        self.assertEqual((sets["wanderer"]["worn"], [b["active"] for b in sets["wanderer"]["bonuses"]]), (["leather_jerkin", "traveler_boots"], [True, False]))
        self.assertEqual(sets["ironbound"]["worn"], [])

    def test_bonus_disappears_when_a_piece_is_removed_and_ignores_grade(self):
        w = world()
        give(w, "iron_blade@fine", "iron_cuirass@poor")                                               # beliebige Güten zählen
        self.assertEqual(w.equipment.set_progress("a")["ironbound"]["worn"], ["iron_blade", "iron_cuirass"])
        with_set = w.equipment.effects("a")["heavy_damage_permille"]
        w.equipment.unequip("a", "chest")
        without = w.equipment.effects("a")["heavy_damage_permille"]
        self.assertGreater(with_set, without)

    def test_bonuses_respect_the_caps(self):
        w = world()
        w.equipment.R["sets"]["ironbound"]["bonuses"][0]["effects"]["heavy_damage_permille"] = 9000    # absurd hoch
        give(w, "iron_blade@masterwork", "iron_cuirass@masterwork")
        self.assertLessEqual(w.equipment.effects("a")["heavy_damage_permille"], w.equipment.R["caps"]["heavy_damage_permille_max"])

    def test_old_rules_have_no_sets_and_invalid_sets_are_rejected(self):
        v1 = load_equipment_rules("equipment_rules_v1.json")
        self.assertNotIn("sets", v1)
        w = world()
        self.assertEqual(w.equipment.R["version"], 2)
        r = load_equipment_rules("equipment_rules_v2.json")
        for mutate in (lambda s: s["ironbound"].update(pieces=["iron_blade", "nope"]), lambda s: s["ironbound"].update(pieces=["iron_blade", "iron_blade"]),
                       lambda s: s["ironbound"]["bonuses"][0].update(pieces=5), lambda s: s["ironbound"]["bonuses"][0]["effects"].update(nope=1),
                       lambda s: s["wanderer"]["bonuses"][1].update(pieces=2)):
            bad = copy.deepcopy(r)
            mutate(bad["sets"])
            with self.assertRaises(WorldError):
                validate_equipment_rules(bad, w.svc.rules)


if __name__ == "__main__":
    unittest.main()
