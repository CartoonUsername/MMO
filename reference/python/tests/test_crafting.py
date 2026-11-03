import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.crafting import (CraftingEngine, craft_blockers, craft_direction_scores, craft_directions, craft_gains,
                              craft_profile, known_recipes, known_techniques, quality_cap, quality_score,
                              quality_tier, validate_crafting_rules)
from mmo_cee.errors import CEEError
from mmo_cee.history import EventLog
from mmo_cee.rules import Rules, load_rules

from .helpers import attune

RULES = load_rules("rules_v6.json")
CFG = RULES["crafting"]
CRAFT = "crafting.crafted"


def pl(craft_id="c1", recipe="iron_ingot", quality="common", quantity=10, technique=None, element=None, day=1):
    return {"craft_id": craft_id, "recipe_id": recipe, "technique_id": technique, "element": element,
            "quantity": quantity, "quality": quality, "day": day}


def make(svc, cid="p", kind="player", xp=10000, **professions):
    svc.create(cid, kind)
    svc.record(cid, "identity.xp_gained", {"amount": xp})
    for p, x in professions.items():
        svc.record(cid, "profession.work", {"profession": p, "xp": x})


def know(svc, cid, discovery, day=1):
    """Entdeckung über den legitimen Weg (alle Beweise + Voraussetzungen) -> 'made'."""
    for e in RULES["discovery"]["discoveries"][discovery]["evidence"]:
        svc.record(cid, "discovery.evidence_gathered", {"discovery_id": discovery, "evidence_id": e})
    svc.record(cid, "discovery.made", {"discovery_id": discovery, "day": day, "credit": "pioneer"})


class CraftingRulesTests(unittest.TestCase):
    def _bad(self, mutate):
        data = copy.deepcopy(RULES.data)
        mutate(data)
        return Rules(data)

    def test_shipped_rules_valid(self):
        validate_crafting_rules(RULES)
        self.assertGreaterEqual(len(CFG["recipes"]), 7)

    def test_invalid_rules_rejected(self):
        c = lambda f: (lambda d: f(d["crafting"]))
        cases = {
            "tiers doppelt": c(lambda x: x.update(tiers=["a", "a"])),
            "schwellen nicht aufsteigend": c(lambda x: x["quality_thresholds"].update(fine=100)),
            "schwellen ohne 0": c(lambda x: x["quality_thresholds"].update(poor=5)),
            "quality_permille fehlt": c(lambda x: x["quality_permille"].pop("fine")),
            "quality_permille >1000": c(lambda x: x["quality_permille"].update(fine=2000)),
            "per_mastery float": c(lambda x: x["quality"].update(per_mastery=1.5)),
            "grade >1000": c(lambda x: x["material_grades"].update(rough=5000)),
            "dimensions leer": c(lambda x: x.update(dimensions=[])),
            "daily inkonsistent": c(lambda x: x["daily"].update(hard_cap=1)),
            "repeat leer": c(lambda x: x.update(repeat_recipe_permille=[])),
            "repeat 0": c(lambda x: x.update(repeat_recipe_permille=[0])),
            "bonus negativ": c(lambda x: x.update(first_craft_bonus_points=-1)),
            "unbekannter Beruf": c(lambda x: x["recipes"]["iron_ingot"].update(profession="necromancy")),
            "mastery 11": c(lambda x: x["recipes"]["iron_ingot"].update(min_mastery=11)),
            "tier 0": c(lambda x: x["recipes"]["iron_ingot"].update(tier=0)),
            "unbekannte Familie": c(lambda x: x["recipes"]["iron_ingot"].update(family="plasma")),
            "inputs leer": c(lambda x: x["recipes"]["iron_ingot"].update(inputs={})),
            "input 0": c(lambda x: x["recipes"]["iron_ingot"].update(inputs={"iron_ore": 0})),
            "output 0": c(lambda x: x["recipes"]["iron_ingot"]["output"].update(qty=0)),
            "max_batch 0": c(lambda x: x["recipes"]["iron_ingot"].update(max_batch=0)),
            "max_batch 101": c(lambda x: x["recipes"]["iron_ingot"].update(max_batch=101)),
            "infusible kein bool": c(lambda x: x["recipes"]["iron_ingot"].update(infusible=1)),
            "Entdeckung unbekannt": c(lambda x: x["recipes"]["frostglass"].update(requires_discovery="ghost")),
            "Entdeckung schaltet nicht frei": c(lambda x: x["recipes"]["frostglass"].update(requires_discovery="iron_folding")),
            "Technik: Entdeckung schaltet nicht frei": c(lambda x: x["techniques"]["folded_iron"].update(requires_discovery="old_shrine_map")),
            "Technik: unbekanntes Rezept": c(lambda x: x["techniques"]["folded_iron"].update(recipes=["ghost"])),
            "Technik: input_permille 0": c(lambda x: x["techniques"]["folded_iron"].update(input_permille=0)),
            "Technik: input_permille >1000": c(lambda x: x["techniques"]["folded_iron"].update(input_permille=1500)),
            "Richtung: Quelle": c(lambda x: x["directions"]["inventor"]["weights"].update({"dim:magic": 5})),
            "Richtung: Schwellen": c(lambda x: x["directions"]["inventor"].update(tier_thresholds=[10, 5])),
            "Richtung: Gewicht 0": c(lambda x: x["directions"]["inventor"]["weights"].update({"dim:innovation": 0})),
            "Entdeckung schaltet unbekanntes Rezept frei": lambda d: d["discovery"]["discoveries"]["iron_folding"]["grants"].update(recipes=["ghost"]),
            "Entdeckung schaltet unbekannte Technik frei": lambda d: d["discovery"]["discoveries"]["iron_folding"]["grants"].update(techniques=["ghost"]),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                with self.assertRaises(CEEError):
                    validate_crafting_rules(self._bad(mutate))

    def test_engine_validates_on_construction(self):
        with self.assertRaises(CEEError):
            CraftingEngine(self._bad(lambda d: d["crafting"].update(dimensions=[])))

    def test_older_rules_have_no_crafting_part(self):
        for name in ("rules_v1.json", "rules_v3.json", "rules_v4.json", "rules_v5.json"):
            svc = CharacterService(rules=load_rules(name))
            st = svc.create("p", "player")
            self.assertNotIn("crafting", st.parts, name)
            with self.assertRaises(RuleViolation):
                svc.record("p", CRAFT, pl())

    def test_initial_state(self):
        st = CharacterService(rules=RULES).create("p", "player")
        part = st.parts["crafting"]
        self.assertEqual(sorted(part["points"]), sorted(CFG["dimensions"]))
        self.assertEqual(sorted(part["families"]), sorted(CFG["families"]))
        self.assertEqual(len(part["elements"]), 9)
        self.assertEqual((part["recipes"], part["techniques"], part["crafts"]), ({}, {}, {}))


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)

    def test_base_recipes_for_fresh_character(self):
        self.svc.create("p", "player")
        self.assertEqual(self.svc.known_recipes("p"), ["bread", "healing_salve", "iron_ingot", "wooden_beam"])
        self.assertEqual(self.svc.known_techniques("p"), [])

    def test_mastery_unlocks_recipes(self):
        make(self.svc)
        self.assertNotIn("iron_blade", self.svc.known_recipes("p"))
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 300})  # Meisterschaft 2
        self.assertIn("iron_blade", self.svc.known_recipes("p"))

    def test_discoveries_unlock_recipes_and_techniques(self):
        make(self.svc, alchemy=300, smithing=700)
        attune(self.svc, "p", "ice")
        self.assertNotIn("frostglass", self.svc.known_recipes("p"))
        self.svc.record("p", "discovery.learned", {"discovery_id": "frostglass_recipe", "day": 1, "from_character": "teacher"})
        self.assertIn("frostglass", self.svc.known_recipes("p"))
        self.assertEqual(self.svc.known_techniques("p"), [])
        know(self.svc, "p", "iron_folding", day=2)
        self.assertEqual(self.svc.known_techniques("p"), ["folded_iron"])

    def test_recipe_needs_both_mastery_and_discovery(self):
        make(self.svc)  # alchemy 0
        self.svc.record("p", "discovery.learned", {"discovery_id": "old_shrine_map", "day": 1, "from_character": "t"})
        self.assertEqual(craft_blockers(self.svc.state("p"), RULES, "frostglass", None, None, 1),
                         ["fehlt: profession:alchemy>=2", "fehlt: discovery:frostglass_recipe"])

    def test_blockers_cover_all_cases(self):
        make(self.svc, smithing=700)  # Meisterschaft 3 (nötig für iron_folding)
        st = self.svc.state("p")
        b = lambda *a: craft_blockers(st, RULES, *a)
        self.assertEqual(b("iron_blade", None, None, 1), [])
        self.assertEqual(b("ghost", None, None, 1), ["unbekanntes Rezept"])
        for q in (0, -1, 21, 1.5, True, "5"):
            self.assertTrue(any("quantity" in x for x in b("iron_blade", None, None, q)), q)
        self.assertIn("unbekannte Technik", b("iron_blade", "ghost", None, 1))
        self.assertIn("Technik unbekannt: folded_iron", b("iron_blade", "folded_iron", None, 1))
        self.assertIn("unbekanntes Element", b("iron_blade", None, "metal", 1))
        self.assertIn("Element nicht geprägt", b("iron_blade", None, "fire", 1))
        self.assertIn("Rezept nicht infusionsfähig", b("iron_ingot", None, "fire", 1))
        attune(self.svc, "p", "fire")
        self.assertEqual(craft_blockers(self.svc.state("p"), RULES, "iron_blade", None, "fire", 1), [])
        know(self.svc, "p", "iron_folding")
        st = self.svc.state("p")
        self.assertIn("Technik passt nicht zum Rezept", craft_blockers(st, RULES, "healing_salve", "folded_iron", None, 1))


class QualityTests(unittest.TestCase):
    def test_score_and_tier_boundaries(self):
        svc = CharacterService(rules=RULES)
        make(svc, smithing=700)  # Meisterschaft 3
        st = svc.state("p")
        self.assertEqual(quality_score(st, RULES, "iron_ingot", None, 600), 250 + 3 * 40 + 600 * 300 // 1000)  # 550
        self.assertEqual(quality_score(st, RULES, "iron_ingot", "folded_iron", 0), 250 + 120 + 100)
        for score, tier in ((0, "poor"), (399, "poor"), (400, "common"), (649, "common"), (650, "fine"), (849, "fine"), (850, "masterwork"), (5000, "masterwork")):
            self.assertEqual(quality_tier(RULES, score), tier, score)

    def test_cap_uses_best_material_and_grows_with_mastery(self):
        svc = CharacterService(rules=RULES)
        caps = {}
        for m, xp in ((0, 0), (3, 700), (4, 1500), (9, 48000)):
            cid = f"m{m}"
            make(svc, cid, smithing=xp) if xp else make(svc, cid)
            caps[m] = quality_cap(svc.state(cid), RULES, "iron_ingot", None)
        self.assertEqual(caps, {0: "common", 3: "common", 4: "fine", 9: "masterwork"})  # 250+40m+270: 520/640/680/880


class CraftEventTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)
        make(self.svc)

    def reject(self, payload, cid="p"):
        n = len(self.svc.log.events(cid))
        before = copy.deepcopy(self.svc.state(cid).parts)
        with self.assertRaises(RuleViolation):
            self.svc.record(cid, CRAFT, payload)
        self.assertEqual(len(self.svc.log.events(cid)), n)
        self.assertEqual(self.svc.state(cid).parts, before)

    def test_valid_report_records_and_counts(self):
        ev = self.svc.record("p", CRAFT, pl())
        part = self.svc.state("p").parts["crafting"]
        self.assertEqual(part["crafts"], {"c1": ev.seq})
        self.assertEqual(part["recipes"], {"iron_ingot": {"count": 1, "best": 1}})
        self.assertEqual(part["families"]["metal"], 1000)

    def test_duplicate_craft_id_rejected(self):
        self.svc.record("p", CRAFT, pl("same"))
        for _ in range(20):
            self.reject(pl("same", recipe="bread", quantity=1))
        self.assertEqual(self.svc.state("p").parts["crafting"]["points"]["volume"], 1000)
        self.svc.create("q", "player")
        self.svc.record("q", CRAFT, pl("same"))  # je Figur eindeutig

    def test_client_cannot_attach_points_or_items(self):
        for extra in ("points", "volume", "xp", "items", "output", "inputs", "material_grade"):
            self.reject({**pl(), extra: 999})

    def test_missing_fields(self):
        for k in pl():
            p = pl()
            del p[k]
            self.reject(p)

    def test_bad_types_and_ranges(self):
        for field, values in {
            "craft_id": ("", "x" * 65, 5, None),
            "recipe_id": ("ghost", 5, None, ["bread"]),
            "quantity": (0, -1, 21, 1.5, "10", True, None),
            "quality": ("legendary", "", 1, None, ["common"]),
            "day": (-1, 1.5, "1", True, None),
            "technique_id": (5, ["folded_iron"], "ghost", "folded_iron"),
            "element": (5, "metal", ["fire"], "fire"),
        }.items():
            for v in values:
                with self.subTest(field=field, value=v):
                    self.reject({**pl(), field: v})

    def test_quantity_limit_per_recipe(self):
        self.svc.record("p", CRAFT, pl("a", quantity=20))
        self.reject(pl("b", quantity=21))

    def test_quality_plausibility_boundary(self):
        # Meisterschaft 0: Obergrenze "common" (250 + 270 = 520)
        self.reject(pl("q1", quality="fine"))
        self.reject(pl("q2", quality="masterwork"))
        self.svc.record("p", CRAFT, pl("q3", quality="common"))
        self.svc.record("p", CRAFT, pl("q4", quality="poor", recipe="bread"))  # schlechter ist immer plausibel
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 1500})  # Meisterschaft 4 -> fine
        self.svc.record("p", CRAFT, pl("q5", quality="fine"))
        self.reject(pl("q6", quality="masterwork"))

    def test_recipe_and_technique_availability_enforced(self):
        self.reject(pl("a", recipe="iron_blade"))  # Meisterschaft fehlt
        self.reject(pl("b", recipe="frostglass"))
        self.reject(pl("c", technique="folded_iron"))  # Technik unbekannt
        self.reject(pl("d", element="fire"))  # nicht geprägt / nicht infusionsfähig
        attune(self.svc, "p", "fire")
        self.reject(pl("e", element="fire"))  # iron_ingot nicht infusionsfähig
        self.svc.record("p", CRAFT, pl("f", recipe="healing_salve", element="fire", quantity=2))

    def test_day_monotonic(self):
        self.svc.record("p", CRAFT, pl("a", day=5))
        self.reject(pl("b", day=4))
        self.svc.record("p", CRAFT, pl("c", day=5))

    def test_event_before_creation_and_unknown_type(self):
        with self.assertRaises(RuleViolation):
            self.svc.record("ghost", CRAFT, pl())
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "crafting.grant_points", {"volume": 100})


class GainTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)
        make(self.svc)

    def pts(self):
        return dict(self.svc.state("p").parts["crafting"]["points"])

    def test_exact_gains_first_craft(self):
        self.svc.record("p", CRAFT, pl())
        # unit = 10 * Stufe 1 * 100 = 1000; common = 250 Promille; Erstherstellungsbonus 500 auf Innovation
        self.assertEqual(self.pts(), {"volume": 1000, "finesse": 250, "innovation": 500, "infusion": 0})

    def test_repeat_decay_per_recipe_and_day(self):
        gains, last = [], 0
        for i in range(8):
            self.svc.record("p", CRAFT, pl(f"c{i}"))
            gains.append(self.pts()["volume"] - last)
            last = self.pts()["volume"]
        self.assertEqual(gains, [1000, 1000, 750, 500, 250, 100, 100, 100])
        self.svc.record("p", CRAFT, pl("next", day=2))  # neuer Tag setzt die Abnahme zurück
        self.assertEqual(self.pts()["volume"] - last, 1000)

    def test_first_craft_bonus_only_once_per_recipe(self):
        self.svc.record("p", CRAFT, pl("a"))
        self.svc.record("p", CRAFT, pl("b"))
        self.assertEqual(self.pts()["innovation"], 500)
        self.svc.record("p", CRAFT, pl("c", recipe="bread", quantity=1))  # anderes Rezept: neuer Bonus
        self.assertEqual(self.pts()["innovation"], 1000)
        self.svc.record("p", CRAFT, pl("d", day=3))  # neuer Tag: kein neuer Bonus
        self.assertEqual(self.pts()["innovation"], 1000)

    def test_quality_scales_finesse(self):
        make(self.svc, "m", woodworking=48000)
        for i, q in enumerate(("poor", "common", "fine", "masterwork")):
            self.svc.record("m", CRAFT, pl(f"c{i}", recipe="wooden_beam", quality=q, quantity=10, day=1 + i))
        finesse = [self.svc.state("m").parts["crafting"]["points"]["finesse"]]
        self.assertEqual(finesse[0], 0 + 250 + 600 + 1000)  # Stufe-1-Rezept, 10 Stück, je Tag eine Herstellung

    def test_technique_and_element_dimensions(self):
        make(self.svc, "t", smithing=700)
        attune(self.svc, "t", "fire")
        know(self.svc, "t", "iron_folding")
        self.svc.record("t", CRAFT, pl("a", recipe="iron_blade", technique="folded_iron", element="fire", quantity=5, quality="common"))
        pts = self.svc.state("t").parts["crafting"]["points"]
        unit = 5 * 2 * 100
        self.assertEqual(pts["volume"], unit)
        self.assertEqual(pts["infusion"], unit)
        self.assertEqual(pts["innovation"], unit * 500 // 1000 + 500)  # Technik + Erstherstellung
        part = self.svc.state("t").parts["crafting"]
        self.assertEqual((part["families"]["metal"], part["elements"]["fire"], part["techniques"]), (unit, unit, {"folded_iron": 1}))

    def test_repeat_decay_is_stronger_than_the_default_daily_cap(self):
        # Mit den Standardwerten greift die Wiederholungsabnahme lange vor dem Tageslimit (Balancing-Hinweis).
        recipes = [r for r, d in CFG["recipes"].items() if not d.get("requires_discovery") and d["min_mastery"] == 0]
        make(self.svc, "c", smithing=10**6, alchemy=10**6)
        n = 0
        for _ in range(12):
            for r in recipes:
                n += 1
                self.svc.record("c", CRAFT, pl(f"x{n}", recipe=r, quality="poor", quantity=20))
        self.assertLess(self.svc.state("c").parts["crafting"]["points"]["volume"], CFG["daily"]["hard_cap"])

    def test_daily_caps_exact_with_lowered_limits(self):
        data = copy.deepcopy(RULES.data)
        data["crafting"]["daily"] = {"full_cap": 3000, "reduced_permille": 250, "hard_cap": 5000}
        svc = CharacterService(rules=Rules(data))
        make(svc, "cap", smithing=10**6, alchemy=10**6, woodworking=10**6, farming=10**6)
        recipes = ["iron_ingot", "healing_salve", "wooden_beam", "bread"]  # alle Stufe 1: 20 Stück = 2000 Rohpunkte
        volume = lambda: svc.state("cap").parts["crafting"]["points"]["volume"]
        got, last = [], 0
        for i, r in enumerate(recipes):
            svc.record("cap", CRAFT, pl(f"d{i}", recipe=r, quality="poor", quantity=20))
            got.append(volume() - last)
            last = volume()
        # 1: voll (2000) | 2: 1000 voll + 1000 * 25 % = 1250 | 3 und 4: nur noch reduziert: 2000 * 25 % = 500
        self.assertEqual(got, [2000, 1250, 500, 500])
        for i in range(30):  # weiter bis zum harten Limit: nie darüber
            svc.record("cap", CRAFT, pl(f"e{i}", recipe=recipes[i % 4], quality="poor", quantity=20))
            self.assertLessEqual(volume(), 5000)
        self.assertEqual(volume(), 5000)
        svc.record("cap", CRAFT, pl("over", recipe="bread", quality="poor", quantity=20))
        self.assertEqual(volume(), 5000)  # Limit hält
        self.assertIn("over", svc.state("cap").parts["crafting"]["crafts"])  # trotzdem nachvollziehbar gewertet
        svc.record("cap", CRAFT, pl("tomorrow", recipe="bread", quality="poor", quantity=20, day=2))
        self.assertGreater(volume(), 5000)  # nächster Tag geht weiter

    def test_gain_function_is_pure(self):
        before = copy.deepcopy(self.svc.state("p").parts)
        g1 = craft_gains(self.svc.state("p"), RULES, pl())
        g2 = craft_gains(self.svc.state("p"), RULES, pl())
        self.assertEqual((g1, self.svc.state("p").parts), (g2, before))

    def test_points_never_decrease(self):
        last = 0
        for i in range(12):
            self.svc.record("p", CRAFT, pl(f"n{i}", quality=["poor", "common"][i % 2], day=1 + i // 3))
            cur = sum(self.pts().values())
            self.assertGreaterEqual(cur, last)
            last = cur


class DirectionTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)

    def grind(self, cid, recipe, days, qty=20, quality="poor", element=None, technique=None, start=1):
        for day in range(start, start + days):
            self.svc.record(cid, CRAFT, pl(f"{recipe}-{day}", recipe=recipe, quantity=qty, quality=quality, day=day,
                                           element=element, technique=technique))

    def test_multiple_directions_non_exclusive_and_monotone(self):
        make(self.svc, smithing=10**6, alchemy=10**6)
        attune(self.svc, "p", "fire")
        self.assertEqual(self.svc.craft_directions("p"), {})
        self.grind("p", "iron_blade", 30, element="fire")  # Metall + Infusion
        first = self.svc.craft_directions("p")
        self.assertIn("elemental_smith", first)
        self.grind("p", "healing_salve", 40, element="fire", start=31)  # ganz andere Richtung dazu (Tage laufen weiter)
        later = self.svc.craft_directions("p")
        self.assertIn("elemental_smith", later)
        self.assertGreaterEqual(len(later), 2)
        for k, v in first.items():
            self.assertGreaterEqual(later[k], v)

    def test_different_histories_different_profiles(self):
        make(self.svc, "a", smithing=10**6)
        make(self.svc, "b", smithing=10**6, alchemy=10**6)
        self.grind("a", "iron_ingot", 10, quality="common")
        self.grind("b", "healing_salve", 10, quality="common")
        pa, pb = self.svc.state("a").parts["crafting"], self.svc.state("b").parts["crafting"]
        self.assertGreater(pa["families"]["metal"], 0)
        self.assertEqual(pb["families"]["metal"], 0)
        self.assertGreater(pb["families"]["herb"], 0)
        sa, sb = craft_direction_scores(self.svc.state("a"), RULES), craft_direction_scores(self.svc.state("b"), RULES)
        self.assertEqual(sa["glass_alchemist"], 0)
        self.assertGreater(sb["glass_alchemist"], 0)
        self.assertGreater(sa["elemental_smith"], sb["elemental_smith"])

    def test_profile_shares(self):
        self.svc.create("p", "player")
        self.assertTrue(all(v == 0 for v in self.svc.craft_profile("p").values()))
        self.svc.record("p", CRAFT, pl())
        prof = self.svc.craft_profile("p")
        self.assertTrue(990 <= sum(prof.values()) <= 1000)

    def test_scores_are_weighted_sums(self):
        make(self.svc, smithing=10**6)
        self.svc.record("p", CRAFT, pl(quality="poor"))
        st = self.svc.state("p")
        scores = craft_direction_scores(st, RULES)
        self.assertEqual(scores["mass_producer"], st.parts["crafting"]["points"]["volume"])
        self.assertEqual(scores["inventor"], st.parts["crafting"]["points"]["innovation"])
        self.assertEqual(scores["elemental_smith"], st.parts["crafting"]["families"]["metal"] * 400 // 1000)

    def test_npc_same_pipeline_replay_and_roundtrip(self):
        make(self.svc, "n", kind="npc", smithing=300)
        self.svc.record("n", CRAFT, pl("a", recipe="iron_blade", quantity=3))
        live = copy.deepcopy(self.svc.state("n").parts)
        self.assertEqual(self.svc.rebuild("n").parts, live)
        svc2 = CharacterService(rules=RULES, log=EventLog.from_json("n", self.svc.log.to_json("n")))
        self.assertEqual(svc2.state("n").parts, live)
        self.assertEqual(live["identity"]["kind"], "npc")

    def test_unrelated_events_do_not_change_crafting_state(self):
        make(self.svc)
        before = copy.deepcopy(self.svc.state("p").parts["crafting"])
        self.svc.record("p", "identity.xp_gained", {"amount": 500})
        self.svc.record("p", "profession.work", {"profession": "mining", "xp": 50})
        self.assertEqual(self.svc.state("p").parts["crafting"], before)


if __name__ == "__main__":
    unittest.main()
