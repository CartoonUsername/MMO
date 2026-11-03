import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.rules import load_rules

from .helpers import attune
from .test_combat import EV, train

DODGER = {"dodge": 33, "perfect_dodge": 18, "light_hit": 120}


def make_skirmisher(svc, cid, kind="player"):
    svc.create(cid, kind)
    svc.record(cid, "identity.xp_gained", {"amount": 10000})  # Stufe 11
    for day in range(1, 16):
        if "skirmisher" in svc.combat_directions(cid):
            return day
        train(svc, cid, day, DODGER, n=6)
    raise AssertionError("Richtung nicht erreicht")


class EssenceCombatTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()

    def test_direction_alone_is_not_enough(self):
        make_skirmisher(self.svc, "p")
        self.assertIn("skirmisher", self.svc.combat_directions("p"))
        self.assertEqual(self.svc.eligible_essences("p"), [])

    def test_element_alone_is_not_enough(self):
        self.svc.create("p", "player")
        self.svc.record("p", "identity.xp_gained", {"amount": 10000})
        attune(self.svc, "p", "shadow")
        self.assertEqual(self.svc.eligible_essences("p"), [])
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "essence.trial_passed", {"form": "umbral_kin"})

    def test_wrong_direction_does_not_qualify(self):
        self.svc.create("p", "player")
        self.svc.record("p", "identity.xp_gained", {"amount": 10000})
        attune(self.svc, "p", "shadow")
        for day in range(1, 6):
            train(self.svc, "p", day, {"heavy_hit": 43, "block": 33}, n=6)
        self.assertIn("vanguard", self.svc.combat_directions("p"))
        self.assertNotIn("umbral_kin", self.svc.eligible_essences("p"))

    def test_history_combination_unlocks_and_is_permanent(self):
        make_skirmisher(self.svc, "p")
        attune(self.svc, "p", "shadow")
        self.assertEqual(self.svc.eligible_essences("p"), ["umbral_kin"])
        self.svc.record("p", "essence.trial_passed", {"form": "umbral_kin"})
        self.svc.record("p", "essence.adopted", {"form": "umbral_kin"})
        self.assertEqual(self.svc.rebuild("p").parts["essence"]["form"], "umbral_kin")
        # Grundklasse bleibt unabhängig von der Wesensform erhalten
        self.svc.record("p", "identity.class_chosen", {"base_class": "warrior"})
        self.assertEqual(self.svc.state("p").parts["identity"]["base_class"], "warrior")
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "essence.adopted", {"form": "umbral_kin"})

    def test_npc_same_path(self):
        make_skirmisher(self.svc, "n", kind="npc")
        attune(self.svc, "n", "shadow")
        self.assertEqual(self.svc.eligible_essences("n"), ["umbral_kin"])

    def test_rules_v2_unchanged_and_without_new_form(self):
        v2 = load_rules("rules_v2.json")
        self.assertEqual(v2.version, "2")
        self.assertNotIn("umbral_kin", v2["essence"]["forms"])
        self.assertIn("umbral_kin", load_rules()["essence"]["forms"])

    def test_old_rules_without_combat_still_work(self):
        svc = CharacterService(rules=load_rules("rules_v1.json"))
        svc.create("p", "player")
        self.assertEqual(svc.eligible_essences("p"), [])


if __name__ == "__main__":
    unittest.main()
