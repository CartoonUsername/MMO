"""AP 5: Berufszweige und Meisterstücke (abgeleitet, ADR-0044)."""
import unittest

from mmo_cee import CharacterService
from mmo_cee.branches import load_profession_rules
from mmo_cee.rules import load_rules

R9 = load_rules("rules_v9.json")


def craft(svc, i, recipe, q="common", tech=None, qty=1, day=1):
    svc.record("a", "crafting.crafted", {"craft_id": f"c{i}", "recipe_id": recipe, "technique_id": tech, "element": None,
                                        "quantity": qty, "quality": q, "day": day})


class Branches(unittest.TestCase):
    def setUp(self):
        self.s = CharacterService(rules=R9)
        self.s.create("a", "player")
        self.s.record("a", "profession.work", {"profession": "smithing", "xp": 3000})

    def test_rules_reference_known_things(self):
        pr = load_profession_rules()
        c = R9["crafting"]
        for pid, p in pr["professions"].items():
            self.assertIn(pid, R9["professions"]["all"])
            for b in p["branches"].values():
                for r in b["recipes"]:
                    self.assertIn(r, c["recipes"])
                for t in b["techniques"]:
                    self.assertIn(t, c["techniques"])
                for e in b["elements"]:
                    self.assertIn(e, R9["elements"]["all"])

    def test_fresh_character_has_no_branch_points(self):
        v = self.s.profession_branches("a")["smithing"]
        self.assertTrue(all(b["points"] == 0 and b["level"] == 0 for b in v["branches"].values()))
        self.assertEqual(v["masterpieces"], [])

    def test_crafting_feeds_matching_branch_only(self):
        self.s.record("a", "profession.work", {"profession": "smithing", "xp": 3000})
        craft(self.s, 1, "iron_blade", qty=5)
        v = self.s.profession_branches("a")["smithing"]["branches"]
        self.assertEqual(v["heavy_arms"]["points"], 1 * 2 * 100)   # zählt Einsätze, nicht Stückzahl
        self.assertEqual(v["refining"]["points"], 0)

    def test_levels_and_masterpiece(self):
        for i in range(12):
            craft(self.s, i, "iron_blade", q="common", qty=1, day=1 + i)
        v = self.s.profession_branches("a")["smithing"]
        self.assertEqual(v["branches"]["heavy_arms"]["level"], 1)
        self.assertEqual(v["masterpieces"], [])
        self.assertIn("iron_blade", v["masterpiece_goals"])

    def test_masterwork_makes_a_masterpiece(self):
        self.s.record("a", "profession.work", {"profession": "smithing", "xp": 100000})
        craft(self.s, 1, "iron_ingot", q="masterwork")
        v = self.s.profession_branches("a")["smithing"]
        self.assertEqual(v["masterpieces"], ["iron_ingot"])
        self.assertNotIn("iron_ingot", v["masterpiece_goals"])

    def test_view_does_not_change_state(self):
        before = self.s.state("a")
        self.s.profession_branches("a")
        self.assertEqual(before.parts, self.s.state("a").parts)


if __name__ == "__main__":
    unittest.main()
