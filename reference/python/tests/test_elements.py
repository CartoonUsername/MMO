import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.elements import combination_key

from .helpers import attune, make_veteran


class ElementTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()

    def test_nine_elements(self):
        st = self.svc.create("p", "player")
        self.assertEqual(len(st.parts["element"]["affinity"]), 9)

    def test_unknown_element(self):
        self.svc.create("p", "player")
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "element.exposure", {"element": "metal", "amount": 5})

    def test_attune_needs_affinity(self):
        self.svc.create("p", "player")
        self.svc.record("p", "element.exposure", {"element": "fire", "amount": 99})
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "element.attuned", {"element": "fire"})
        self.svc.record("p", "element.exposure", {"element": "fire", "amount": 1})
        self.svc.record("p", "element.attuned", {"element": "fire"})
        self.assertEqual(self.svc.state("p").parts["element"]["attuned"], ["fire"])

    def test_no_double_attune(self):
        make_veteran(self.svc, "p")
        attune(self.svc, "p", "ice")
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "element.attuned", {"element": "ice"})

    def test_two_elements_free_combination_any_pair(self):
        make_veteran(self.svc, "p")
        attune(self.svc, "p", "shadow")
        attune(self.svc, "p", "electric")  # kein fest vorgegebenes Paar nötig
        self.assertEqual(combination_key(self.svc.state("p").parts["element"]["attuned"]), ("electric", "shadow"))

    def test_combination_key_order_independent(self):
        self.assertEqual(combination_key(["wind", "fire"]), combination_key(["fire", "wind"]))

    def test_third_element_gated_by_endgame_level(self):
        make_veteran(self.svc, "p")  # Stufe 4
        attune(self.svc, "p", "fire")
        attune(self.svc, "p", "wind")
        self.svc.record("p", "element.exposure", {"element": "light", "amount": 500})
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "element.attuned", {"element": "light"})
        self.svc.record("p", "identity.xp_gained", {"amount": 160000})  # Stufe >= 40
        self.assertGreaterEqual(self.svc.state("p").parts["identity"]["level"], 40)
        self.svc.record("p", "element.attuned", {"element": "light"})
        self.assertEqual(len(self.svc.state("p").parts["element"]["attuned"]), 3)

    def test_never_more_than_three(self):
        make_veteran(self.svc, "p", level_xp=400000)
        for e in ("fire", "wind", "light"):
            attune(self.svc, "p", e)
        self.svc.record("p", "element.exposure", {"element": "earth", "amount": 500})
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "element.attuned", {"element": "earth"})


if __name__ == "__main__":
    unittest.main()
