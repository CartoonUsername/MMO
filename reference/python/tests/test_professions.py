import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.professions import ProfessionEngine
from mmo_cee.rules import load_rules


class ProfessionTests(unittest.TestCase):
    def test_mastery_boundaries(self):
        eng = ProfessionEngine(load_rules())
        self.assertEqual(eng.mastery_level(0), 0)
        self.assertEqual(eng.mastery_level(99), 0)
        self.assertEqual(eng.mastery_level(100), 1)
        self.assertEqual(eng.mastery_level(299), 1)
        self.assertEqual(eng.mastery_level(300), 2)
        self.assertEqual(eng.mastery_level(10**9), 10)

    def test_accumulation_and_independence(self):
        svc = CharacterService()
        svc.create("p", "player")
        svc.record("p", "profession.work", {"profession": "smithing", "xp": 60})
        svc.record("p", "profession.work", {"profession": "smithing", "xp": 60})
        svc.record("p", "profession.work", {"profession": "alchemy", "xp": 10})
        self.assertEqual(svc.state("p").parts["profession"]["xp"], {"smithing": 120, "alchemy": 10})

    def test_unknown_profession_and_bad_xp(self):
        svc = CharacterService()
        svc.create("p", "player")
        with self.assertRaises(RuleViolation):
            svc.record("p", "profession.work", {"profession": "necromancy", "xp": 5})
        with self.assertRaises(RuleViolation):
            svc.record("p", "profession.work", {"profession": "mining", "xp": 0})

    def test_listed_professions_cover_briefing(self):
        names = set(load_rules()["professions"]["all"])
        for p in ("smithing", "alchemy", "farming", "mining", "construction", "woodworking",
                  "trade", "logistics", "research", "architecture", "engineering"):
            self.assertIn(p, names)


if __name__ == "__main__":
    unittest.main()
