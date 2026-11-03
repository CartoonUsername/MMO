import unittest

from mmo_cee import CharacterService, RuleViolation

from .helpers import attune


def ember_ready(svc, cid, kind="player"):
    svc.create(cid, kind)
    svc.record(cid, "identity.xp_gained", {"amount": 10000})  # Stufe 11
    attune(svc, cid, "fire")
    svc.record(cid, "profession.work", {"profession": "smithing", "xp": 700})  # Meisterschaft 3


class EssenceTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()

    def test_new_character_is_human_and_not_eligible(self):
        self.svc.create("p", "player")
        self.assertEqual(self.svc.state("p").parts["essence"]["form"], "human")
        self.assertEqual(self.svc.eligible_essences("p"), [])

    def test_eligibility_comes_from_history(self):
        ember_ready(self.svc, "p")
        self.assertEqual(self.svc.eligible_essences("p"), ["ember_kin"])

    def test_partial_history_not_eligible(self):
        self.svc.create("p", "player")
        self.svc.record("p", "identity.xp_gained", {"amount": 10000})
        attune(self.svc, "p", "fire")  # Beruf fehlt
        self.assertEqual(self.svc.eligible_essences("p"), [])
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})

    def test_adoption_requires_trial(self):
        ember_ready(self.svc, "p")
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "essence.adopted", {"form": "ember_kin"})

    def test_full_path_and_permanence(self):
        ember_ready(self.svc, "p")
        self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})
        ev = self.svc.record("p", "essence.adopted", {"form": "ember_kin"})
        part = self.svc.state("p").parts["essence"]
        self.assertEqual(part["form"], "ember_kin")
        self.assertEqual(part["adopted_at_seq"], ev.seq)
        # dauerhaft: keine weitere Prüfung/Annahme, auch nicht dieselbe Form
        for t in ("essence.trial_passed", "essence.adopted"):
            for form in ("ember_kin", "stone_born"):
                with self.assertRaises(RuleViolation):
                    self.svc.record("p", t, {"form": form})
        self.assertEqual(self.svc.eligible_essences("p"), [])

    def test_unknown_form(self):
        ember_ready(self.svc, "p")
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "essence.trial_passed", {"form": "dragon"})

    def test_npc_can_evolve(self):
        ember_ready(self.svc, "n", kind="npc")
        self.svc.record("n", "essence.trial_passed", {"form": "ember_kin"})
        self.svc.record("n", "essence.adopted", {"form": "ember_kin"})
        self.assertEqual(self.svc.rebuild("n").parts["essence"]["form"], "ember_kin")

    def test_different_histories_different_outcomes(self):
        ember_ready(self.svc, "a")
        self.svc.create("b", "player")
        self.svc.record("b", "identity.xp_gained", {"amount": 10000})
        attune(self.svc, "b", "earth")
        self.svc.record("b", "profession.work", {"profession": "mining", "xp": 700})
        self.assertEqual(self.svc.eligible_essences("a"), ["ember_kin"])
        self.assertEqual(self.svc.eligible_essences("b"), ["stone_born"])


if __name__ == "__main__":
    unittest.main()
