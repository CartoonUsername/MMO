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


class FocusXpTests(unittest.TestCase):                              # AP 36: aktiver Zweig gibt Zusatz-Berufserfahrung (ADR-0070)
    def make(self, spec_branch):
        from tests.test_world_crafting import World as CWorld
        w = CWorld(rules=load_rules("rules_v10.json"))
        w.char("p", smithing=50)
        w.stock("p", **{"iron_ore__standard": 100})
        if spec_branch:
            w.svc.record("p", SPEC, {"profession": "smithing", "branch": spec_branch, "day": 1})
        return w

    def test_recipe_in_active_branch_gets_bonus_others_do_not(self):
        base = self.make(None).cs.craft("p", "iron_ingot", 10, "standard").profession_xp
        self.assertGreater(base, 3)
        self.assertEqual(self.make("refining").cs.craft("p", "iron_ingot", 10, "standard").profession_xp, base + base * 250 // 1000)
        self.assertEqual(self.make("shadow_alloys").cs.craft("p", "iron_ingot", 10, "standard").profession_xp, base)   # Rezept nicht im Zweig
        self.assertEqual(self.make("heavy_arms").cs.craft("p", "iron_ingot", 10, "standard").profession_xp, base)       # iron_ingot gehört nur zu refining

    def test_no_bonus_with_older_rules(self):
        from tests.test_world_crafting import World as CWorld
        w = CWorld(rules=load_rules("rules_v9.json"))
        w.char("p", smithing=50)
        w.stock("p", **{"iron_ore__standard": 100})
        self.assertEqual(w.cs.craft("p", "iron_ingot", 10, "standard").profession_xp, self.make(None).cs.craft("p", "iron_ingot", 10, "standard").profession_xp)


class MigrationAndPersistenceTests(unittest.TestCase):              # AP 38
    def test_existing_world_upgrades_from_v9_and_roundtrips_with_a_chosen_branch(self):
        import json
        from mmo_world.persistence import check_consistency, export_world, import_world, upgrade_world
        from mmo_world.world import World
        w9 = World("rules_v9.json")
        w9.svc.create("anna", "player")
        w9.svc.record("anna", "profession.work", {"profession": "smithing", "xp": 50})
        w10 = upgrade_world(w9, "rules_v10.json")                                  # alle Figuren migrieren
        self.assertEqual(w10.svc.rules.version, "10")
        r = w10.specialize("anna", "smithing", "refining")
        self.assertEqual(r["paid"], 0)
        self.assertEqual(w10.svc.state("anna").parts["profession"]["xp"], {"smithing": 50})       # alte Erfahrung bleibt
        self.assertEqual(check_consistency(w10), [])
        env, logs = export_world(w10)
        back = import_world(json.loads(json.dumps(env)), json.loads(json.dumps(logs)))
        self.assertEqual(back.svc.profession_branches("anna")["smithing"]["chosen"], "refining")
        self.assertEqual(check_consistency(back), [])
        with self.assertRaises(Exception):                                         # v9-Welt bleibt unberührt
            w9.specialize("anna", "smithing", "refining")


def World_craft_quality(w, char, grade):
    w.inv.deposit(char, f"iron_ore@{grade}", 10)
    return w.crafting.craft(char, "iron_ingot", 1, grade).quality


class MasterpieceChronicleTests(unittest.TestCase):                  # AP 46: erstes Meisterstück je Rezept in der Weltchronik (ADR-0074)
    def setUp(self):
        from mmo_world.world import World
        self.w = World("rules_v10.json")
        for c in ("anna", "ben"):
            self.w.svc.create(c, "player")
            self.w.svc.record(c, "identity.xp_gained", {"amount": 10000})
            self.w.inv.deposit(c, "iron_ore@standard", 100)

    def test_only_the_first_masterpiece_of_a_recipe_is_chronicled(self):
        w = self.w
        w.crafting.masterpiece("anna", "iron_ingot")                                  # Haken, den craft() bei Spitzengüte ruft
        w.crafting.masterpiece("ben", "iron_ingot")
        w.crafting.masterpiece("ben", "bread")
        rows = [e for e in w.chronicle.entries if e["kind"] == "masterpiece_first"]
        self.assertEqual([(e["chars"], e["data"]["recipe"]) for e in rows], [(["anna"], "iron_ingot"), (["ben"], "bread")])
        self.assertEqual([t["name"] for t in w.chronicle.titles["anna"]], ["Erstes Meisterstück: iron ingot"])
        self.assertEqual(w.chronicle.prestige("anna")["points"], 15)

    def test_craft_calls_the_hook_only_for_top_quality(self):
        calls = []
        self.w.crafting.masterpiece = lambda c, r: calls.append((c, r))
        r = self.w.crafting.craft("anna", "iron_ingot", 1, "standard")
        self.assertNotEqual(r.quality, self.w.crafting.rules["crafting"]["tiers"][-1])
        self.assertEqual(calls, [])

    def test_older_community_rules_do_not_break_crafting_hook(self):
        w = self.w
        del w.chronicle.R["kinds"]["masterpiece_first"]
        w.crafting.masterpiece("anna", "iron_ingot")                                  # keine Ausnahme, kein Eintrag
        self.assertEqual([e for e in w.chronicle.entries if e["kind"] == "masterpiece_first"], [])

    def test_real_masterwork_craft_reaches_the_chronicle(self):                       # AP 55: echter Weg, ohne Haken-Umweg
        w = self.w
        for c in ("anna", "ben"):
            w.svc.record(c, "profession.work", {"profession": "smithing", "xp": 96000})         # Meisterschaftsstufe 10
            w.inv.deposit(c, "iron_ore@select", 10)
        low = World_craft_quality(w, "anna", "standard")                                    # schlechteres Material: kein Meisterwerk
        self.assertNotEqual(low, "masterwork")
        self.assertEqual(w.crafting.craft("anna", "iron_ingot", 1, "select").quality, "masterwork")
        self.assertEqual(w.crafting.craft("ben", "iron_ingot", 1, "select").quality, "masterwork")
        rows = [e for e in w.chronicle.entries if e["kind"] == "masterpiece_first"]
        self.assertEqual([(e["chars"], e["data"]["recipe"]) for e in rows], [(["anna"], "iron_ingot")])   # nur die Erste


class FocusQualityTests(unittest.TestCase):                          # AP 53: aktiver Zweig gibt Gütepunkte (ADR-0075)
    def score(self, rules, branch, recipe="iron_ingot"):
        from mmo_cee.crafting import quality_cap, quality_score
        s = CharacterService(load_rules(rules))
        s.create("p", "player")
        s.record("p", "profession.work", {"profession": "smithing", "xp": 50})
        if branch:
            s.record("p", SPEC, {"profession": "smithing", "branch": branch, "day": 1})
        return quality_score(s.state("p"), s.rules_of("p"), recipe, None, 500), quality_cap(s.state("p"), s.rules_of("p"), recipe, None)

    def test_bonus_applies_only_to_recipes_of_the_active_branch(self):
        base, _ = self.score("rules_v10.json", None)
        self.assertEqual(self.score("rules_v10.json", "refining")[0], base + 50)
        self.assertEqual(self.score("rules_v10.json", "heavy_arms")[0], base)             # iron_ingot gehört nicht zu heavy_arms
        self.assertEqual(self.score("rules_v10.json", "heavy_arms", "iron_blade")[0], self.score("rules_v10.json", None, "iron_blade")[0] + 50)
        self.assertEqual(self.score("rules_v9.json", None)[0], base)                      # ältere Regeln unverändert

    def test_craft_report_validates_with_the_bonus(self):
        from tests.test_world_crafting import World as CWorld
        w = CWorld(rules=load_rules("rules_v10.json"))
        w.char("p", smithing=50)
        w.stock("p", **{"iron_ore__select": 100})
        w.svc.record("p", SPEC, {"profession": "smithing", "branch": "refining", "day": 1})
        r = w.cs.craft("p", "iron_ingot", 5, "select")                                   # Bericht passt zur Plausibilitätsgrenze
        self.assertIn(r.quality, w.svc.rules.data["crafting"]["tiers"])


if __name__ == "__main__":
    unittest.main()
