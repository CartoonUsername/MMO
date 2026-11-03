import unittest

from mmo_cee import CharacterService, RuleViolation


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()

    def test_starts_human_and_level_one(self):
        st = self.svc.create("p", "player")
        self.assertEqual(st.parts["essence"]["form"], "human")
        self.assertEqual(st.parts["identity"]["level"], 1)

    def test_npc_uses_same_pipeline(self):
        st = self.svc.create("n", "npc")
        self.assertEqual(st.parts["identity"]["kind"], "npc")
        self.svc.record("n", "profession.work", {"profession": "farming", "xp": 120})
        self.assertEqual(self.svc.state("n").parts["profession"]["xp"], {"farming": 120})

    def test_invalid_kind(self):
        with self.assertRaises(RuleViolation):
            self.svc.create("x", "monster")
        self.assertFalse(self.svc.log.has("x") and self.svc.log.events("x"))

    def test_event_before_creation_rejected(self):
        with self.assertRaises(RuleViolation):
            self.svc.record("ghost", "identity.xp_gained", {"amount": 5})

    def test_double_creation_rejected(self):
        self.svc.create("p", "player")
        with self.assertRaises(RuleViolation):
            self.svc.create("p", "player")

    def test_class_once_and_known(self):
        self.svc.create("p", "player")
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "identity.class_chosen", {"base_class": "mage"})
        self.svc.record("p", "identity.class_chosen", {"base_class": "archer"})
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "identity.class_chosen", {"base_class": "warrior"})

    def test_level_curve_and_cap(self):
        self.svc.create("p", "player")
        self.svc.record("p", "identity.xp_gained", {"amount": 99})
        self.assertEqual(self.svc.state("p").parts["identity"]["level"], 1)
        self.svc.record("p", "identity.xp_gained", {"amount": 1})
        self.assertEqual(self.svc.state("p").parts["identity"]["level"], 2)
        self.svc.record("p", "identity.xp_gained", {"amount": 10**9})
        self.assertEqual(self.svc.state("p").parts["identity"]["level"], 50)

    def test_bad_xp_values(self):
        self.svc.create("p", "player")
        for bad in (0, -5, 1.5, "10", True):
            with self.assertRaises(RuleViolation):
                self.svc.record("p", "identity.xp_gained", {"amount": bad})

    def test_unknown_event_type(self):
        self.svc.create("p", "player")
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "bogus.thing", {})

    def test_rejected_event_not_logged(self):
        self.svc.create("p", "player")
        n = len(self.svc.log.events("p"))
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "identity.xp_gained", {"amount": -1})
        self.assertEqual(len(self.svc.log.events("p")), n)


if __name__ == "__main__":
    unittest.main()
