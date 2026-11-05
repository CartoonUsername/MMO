"""AP 33: Zweigwahl und Respezialisierung der Berufe (rules_v10, ADR-0068)."""
import unittest

from mmo_cee import CharacterService
from mmo_cee.errors import RuleViolation
from mmo_cee.rules import load_rules

SPEC = "profession.specialize"


def svc(rules="rules_v10.json"):
    s = CharacterService(load_rules(rules))
    s.create("anna", "player")
    return s


class SpecializationTests(unittest.TestCase):
    def test_choose_needs_experience_and_valid_branch(self):
        s = svc()
        with self.assertRaises(RuleViolation):                                     # noch keine Erfahrung
            s.record("anna", SPEC, {"profession": "smithing", "branch": "refining", "day": 1})
        s.record("anna", "profession.work", {"profession": "smithing", "xp": 50})
        for bad in ({"profession": "smithing", "branch": "nope", "day": 1}, {"profession": "alchemy", "branch": "refining", "day": 1},
                    {"profession": "smithing", "branch": "refining", "day": -1}, {"profession": "smithing", "branch": "refining"},
                    {"profession": "smithing", "branch": "refining", "day": True}, {"profession": "smithing", "branch": "refining", "day": 1, "x": 1}):
            with self.assertRaises(RuleViolation):
                s.record("anna", SPEC, bad)
        s.record("anna", SPEC, {"profession": "smithing", "branch": "refining", "day": 1})
        self.assertEqual(s.profession_branches("anna")["smithing"]["chosen"], "refining")
        self.assertIsNone(s.profession_branches("anna")["alchemy"]["chosen"])

    def test_change_needs_cooldown_and_a_different_branch(self):
        s = svc()
        s.record("anna", "profession.work", {"profession": "smithing", "xp": 50})
        s.record("anna", SPEC, {"profession": "smithing", "branch": "refining", "day": 3})
        for bad in ({"branch": "refining", "day": 20}, {"branch": "heavy_arms", "day": 9}, {"branch": "heavy_arms", "day": 2}):
            with self.assertRaises(RuleViolation):
                s.record("anna", SPEC, dict(bad, profession="smithing"))
        s.record("anna", SPEC, {"profession": "smithing", "branch": "heavy_arms", "day": 10})
        v = s.profession_branches("anna")["smithing"]
        self.assertEqual((v["chosen"], v["chosen_day"]), ("heavy_arms", 10))

    def test_history_is_kept_and_state_replays(self):
        s = svc()
        s.record("anna", "profession.work", {"profession": "smithing", "xp": 50})
        s.record("anna", SPEC, {"profession": "smithing", "branch": "refining", "day": 1})
        s.record("anna", SPEC, {"profession": "smithing", "branch": "heavy_arms", "day": 8})
        before = s.state("anna").parts["profession"]
        s._states.clear()
        self.assertEqual(s.state("anna").parts["profession"], before)             # Wiedergabe aus dem Ereignislog
        self.assertEqual(len(s.log.events("anna")), 4)                            # beide Wahlen bleiben im Log

    def test_older_rules_do_not_know_the_event_and_state_is_unchanged(self):
        s = svc("rules_v9.json")
        s.record("anna", "profession.work", {"profession": "smithing", "xp": 50})
        with self.assertRaises(RuleViolation):
            s.record("anna", SPEC, {"profession": "smithing", "branch": "refining", "day": 1})
        self.assertNotIn("spec", s.state("anna").parts["profession"])
        self.assertNotIn("spec", svc().state("anna").parts["profession"])         # auch v10 legt das Feld erst bei Gebrauch an



class WorldSpecializationTests(unittest.TestCase):
    def setUp(self):
        from mmo_world.world import World
        self.w = World("rules_v10.json")
        self.w.svc.create("anna", "player")
        self.w.svc.record("anna", "profession.work", {"profession": "smithing", "xp": 50})
        self.w.inv.deposit("anna", self.w.trading.coin, 600)

    def test_first_choice_is_free_and_change_costs_coins_after_cooldown(self):
        from mmo_world.errors import WorldError
        w, coin = self.w, self.w.trading.coin
        r = w.specialize("anna", "smithing", "refining")
        self.assertEqual((r["paid"], w.inv.balance("anna", coin)), (0, 600))
        with self.assertRaises(RuleViolation):                                     # Abklingzeit
            w.specialize("anna", "smithing", "heavy_arms")
        self.assertEqual(w.inv.balance("anna", coin), 600)                         # nichts bezahlt
        w.day[0] += 7
        r = w.specialize("anna", "smithing", "heavy_arms")
        self.assertEqual((r["paid"], w.inv.balance("anna", coin)), (500, 100))
        w.day[0] += 7
        with self.assertRaises(WorldError):                                        # zu wenig Münzen, Zustand unverändert
            w.specialize("anna", "smithing", "shadow_alloys")
        self.assertEqual(w.svc.profession_branches("anna")["smithing"]["chosen"], "heavy_arms")

    def test_old_rules_have_no_specialization(self):
        from mmo_world.errors import WorldError
        from mmo_world.world import World
        w = World("rules_v9.json")
        w.svc.create("anna", "player")
        with self.assertRaises(WorldError):
            w.specialize("anna", "smithing", "refining")


if __name__ == "__main__":
    unittest.main()
