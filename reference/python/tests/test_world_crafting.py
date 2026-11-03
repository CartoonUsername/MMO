import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.rules import load_rules
from mmo_world import (CraftingService, DiscoveryRegistry, DiscoveryService, Inventory, WorldError, key,
                       required_inputs)

from .helpers import attune

RULES = load_rules("rules_v6.json")
CFG = RULES["crafting"]
DISC = RULES["discovery"]["discoveries"]


class World:
    def __init__(self, day=1, rules=RULES):
        self.svc = CharacterService(rules=rules)
        self.inv = Inventory()
        self.day = [day]
        self.cs = CraftingService(self.svc, self.inv, lambda: self.day[0])
        self.reg = DiscoveryRegistry(RULES)
        self.ds = DiscoveryService(self.svc, self.reg, lambda: self.day[0])

    def char(self, cid="p", kind="player", xp=10000, **prof):
        self.svc.create(cid, kind)
        self.svc.record(cid, "identity.xp_gained", {"amount": xp})
        for p, x in prof.items():
            self.svc.record(cid, "profession.work", {"profession": p, "xp": x})

    def stock(self, cid, **items):
        for k, n in items.items():
            self.inv.deposit(cid, k.replace("__", "@"), n)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()

    def test_deposit_apply_balance(self):
        self.inv.deposit("a", "iron_ore@standard", 10)
        self.inv.apply("a", {"iron_ore@standard": 4}, {"iron_ingot@fine": 2})
        self.assertEqual((self.inv.balance("a", "iron_ore@standard"), self.inv.balance("a", "iron_ingot@fine")), (6, 2))
        self.assertEqual(self.inv.holdings("a"), {"iron_ingot@fine": 2, "iron_ore@standard": 6})
        self.assertEqual(self.inv.total("iron_ore@standard"), 6)

    def test_atomic_all_or_nothing(self):
        self.inv.deposit("a", "x@1", 5)
        self.inv.deposit("a", "y@1", 1)
        before = self.inv.to_json()
        with self.assertRaises(WorldError):
            self.inv.apply("a", {"x@1": 3, "y@1": 2}, {"z@1": 9})  # y reicht nicht -> nichts ändert sich
        self.assertEqual(self.inv.to_json(), before)

    def test_stack_removed_when_zero_and_never_negative(self):
        self.inv.deposit("a", "x@1", 2)
        self.inv.apply("a", {"x@1": 2}, {})
        self.assertEqual(self.inv.holdings("a"), {})
        with self.assertRaises(WorldError):
            self.inv.apply("a", {"x@1": 1}, {})
        self.assertEqual(self.inv.balance("a", "x@1"), 0)

    def test_invalid_entries_rejected(self):
        for bad in ({"x@1": 0}, {"x@1": -1}, {"x@1": 1.5}, {"x@1": True}, {"x@1": "3"}, {"x": 1}, {5: 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(WorldError):
                    self.inv.apply("a", {}, bad)
                with self.assertRaises(WorldError):
                    self.inv.apply("a", bad, {})
        self.assertEqual(self.inv.holdings("a"), {})

    def test_owners_are_separate_and_roundtrip(self):
        self.inv.deposit("a", "x@1", 3)
        self.inv.deposit("b", "x@1", 4)
        self.assertEqual((self.inv.balance("a", "x@1"), self.inv.balance("b", "x@1"), self.inv.total("x@1")), (3, 4, 7))
        again = Inventory.from_json(self.inv.to_json())
        self.assertEqual(again.to_json(), self.inv.to_json())
        with self.assertRaises(WorldError):
            Inventory.from_json('{"a":{"x@1":-3}}')

    def test_key_helper(self):
        self.assertEqual(key("iron_ore", "standard"), "iron_ore@standard")


class CraftingFlowTests(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.w.char("p")
        self.w.stock("p", **{"iron_ore__standard": 100, "iron_ore__select": 100, "iron_ore__rough": 100})

    def test_exact_consumption_production_and_cee_report(self):
        r = self.w.cs.craft("p", "iron_ingot", 10, "standard")
        self.assertEqual((r.quality, r.consumed, r.produced), ("common", {"iron_ore@standard": 20}, {"iron_ingot@common": 10}))
        self.assertEqual(self.w.inv.balance("p", "iron_ore@standard"), 80)
        self.assertEqual(self.w.inv.balance("p", "iron_ingot@common"), 10)
        pl = r.event.payload
        self.assertEqual((pl["recipe_id"], pl["quantity"], pl["quality"], pl["day"]), ("iron_ingot", 10, "common", 1))
        self.assertTrue(pl["craft_id"].startswith("srv1-craft-"))
        self.assertEqual(self.w.svc.state("p").parts["crafting"]["recipes"]["iron_ingot"]["count"], 1)

    def test_recipe_output_quantity(self):
        self.w.stock("p", **{"healing_herb__standard": 10, "clean_water__standard": 10})
        r = self.w.cs.craft("p", "healing_salve", 5, "standard")
        self.assertEqual((r.consumed, r.produced), ({"healing_herb@standard": 10, "clean_water@standard": 5}, {"healing_salve@common": 10}))

    def test_material_grade_drives_quality(self):
        q = {g: self.w.cs.craft("p", "iron_ingot", 1, g).quality for g in ("rough", "standard", "select")}
        self.assertEqual(q, {"rough": "poor", "standard": "common", "select": "common"})  # 250+90 / 250+180 / 250+270
        self.w.char("m4", smithing=1500)  # Meisterschaft 4: 250 + 160 + Material
        self.w.stock("m4", **{"iron_ore__select": 10, "iron_ore__standard": 10})
        self.assertEqual(self.w.cs.craft("m4", "iron_ingot", 1, "select").quality, "fine")  # 680
        self.assertEqual(self.w.cs.craft("m4", "iron_ingot", 1, "standard").quality, "common")  # 590

    def test_unknown_grade_and_recipe_and_blockers_change_nothing(self):
        before = (self.w.inv.to_json(), len(self.w.svc.log.events("p")))
        for args in (("iron_ingot", 1, "legendary"), ("iron_ingot", 1, None), ("ghost", 1, "standard"),
                     ("iron_ingot", 0, "standard"), ("iron_ingot", 21, "standard"), ("iron_blade", 1, "standard"),
                     ("frostglass", 1, "standard")):
            with self.subTest(args=args):
                with self.assertRaises(WorldError):
                    self.w.cs.craft("p", *args)
        self.assertEqual((self.w.inv.to_json(), len(self.w.svc.log.events("p"))), before)

    def test_insufficient_material_changes_nothing(self):
        self.w.char("poor")
        self.w.stock("poor", **{"iron_ore__standard": 5})
        before = (self.w.inv.to_json(), len(self.w.svc.log.events("poor")))
        with self.assertRaises(WorldError):
            self.w.cs.craft("poor", "iron_ingot", 10, "standard")  # braucht 20
        with self.assertRaises(WorldError):
            self.w.cs.craft("poor", "iron_ingot", 1, "select")  # falsche Güteklasse vorhanden
        self.assertEqual((self.w.inv.to_json(), len(self.w.svc.log.events("poor"))), before)

    def test_craft_ids_are_server_issued_and_unique(self):
        ids = {self.w.cs.craft("p", "iron_ingot", 1, "standard").event.payload["craft_id"] for _ in range(10)}
        self.assertEqual(len(ids), 10)

    def test_rollback_when_cee_rejects(self):
        before = self.w.inv.to_json()
        original = self.w.svc.record
        calls = []

        def failing(cid, type_, payload):
            calls.append(type_)
            if type_ == "crafting.crafted":
                raise RuleViolation("simulierter Fehler")
            return original(cid, type_, payload)

        self.w.svc.record = failing
        with self.assertRaises(RuleViolation):
            self.w.cs.craft("p", "iron_ingot", 10, "standard")
        self.w.svc.record = original
        self.assertEqual(self.w.inv.to_json(), before)  # Eingaben zurückgegeben, keine Ausgaben
        self.assertNotIn("iron_ingot@common", self.w.inv.holdings("p"))
        self.assertEqual(self.w.svc.state("p").parts["crafting"]["crafts"], {})

    def test_cee_validation_happens_before_any_inventory_change(self):
        # Tag springt zurück: die CEE würde ablehnen -> Inventar darf nie angefasst werden
        self.w.cs.craft("p", "iron_ingot", 1, "standard")
        self.w.day[0] = 0
        before = (self.w.inv.to_json(), len(self.w.svc.log.events("p")))
        with self.assertRaises(RuleViolation):
            self.w.cs.craft("p", "iron_ingot", 1, "standard")
        self.assertEqual((self.w.inv.to_json(), len(self.w.svc.log.events("p"))), before)

    def test_rejected_craft_never_touches_the_inventory(self):
        calls = []
        original = self.w.inv.apply
        self.w.inv.apply = lambda *args, **kw: (calls.append(args), original(*args, **kw))[1]
        self.w.cs.craft("p", "iron_ingot", 1, "standard")
        n_ok = len(calls)
        self.w.day[0] = 0  # Tag springt zurück -> die CEE lehnt ab
        with self.assertRaises(RuleViolation):
            self.w.cs.craft("p", "iron_ingot", 1, "standard")
        self.assertEqual(len(calls), n_ok)  # kein Entnehmen und kein Zurückgeben: Inventar nie angefasst
        self.w.inv.apply = original

    def test_daily_cap_reached_means_no_xp_event_but_craft_still_succeeds(self):
        import copy as _copy

        from mmo_cee.rules import Rules

        data = _copy.deepcopy(RULES.data)
        data["crafting"]["daily"] = {"full_cap": 200, "reduced_permille": 250, "hard_cap": 300}
        w = World(rules=Rules(data))
        w.char("p")
        w.stock("p", **{"iron_ore__standard": 200})
        results = [w.cs.craft("p", "iron_ingot", 10, "standard") for _ in range(8)]
        self.assertEqual(w.svc.state("p").parts["crafting"]["points"]["volume"], 300)  # hartes Limit
        self.assertEqual(results[-1].profession_xp, 0)  # nichts mehr gutgeschrieben ...
        self.assertEqual(results[-1].produced, {"iron_ingot@common": 10})  # ... aber die Herstellung gelingt
        xp_events = [e for e in w.svc.log.events("p") if e.type == "profession.work"]
        self.assertTrue(all(e.payload["xp"] > 0 for e in xp_events))  # nie ein Ereignis mit 0 Erfahrung
        self.assertLess(len(xp_events), 8)

    def test_profession_xp_comes_from_capped_points(self):
        r = self.w.cs.craft("p", "iron_ingot", 10, "standard")
        self.assertEqual(r.profession_xp, 1000 // 10)
        self.assertEqual(self.w.svc.state("p").parts["profession"]["xp"]["smithing"], 100)

    def test_repeated_crafting_decays_xp_and_cannot_farm_forever(self):
        self.w.stock("p", **{"iron_ore__standard": 100})  # genug Material für 8 Herstellungen (160 Erz)
        xps = []
        for _ in range(8):
            xps.append(self.w.cs.craft("p", "iron_ingot", 10, "standard").profession_xp)
        self.assertEqual(xps, [100, 100, 75, 50, 25, 10, 10, 10])  # gleiche Wiederholungsabnahme wie die Punkte

    def test_no_production_without_inputs_and_bounded_by_inputs(self):
        self.w.char("q")
        self.w.stock("q", **{"iron_ore__standard": 7})
        made = 0
        for _ in range(50):
            try:
                made += self.w.cs.craft("q", "iron_ingot", 1, "standard").produced["iron_ingot@common"]
            except WorldError:
                pass
        self.assertEqual(made, 3)  # 7 Erz / 2 pro Barren -> höchstens 3; nie mehr als das Material hergibt
        self.assertEqual(self.w.inv.balance("q", "iron_ore@standard"), 1)

    def test_progression_unlocks_recipes_through_crafting_itself(self):
        self.w.stock("p", **{"charcoal__standard": 10})
        with self.assertRaises(WorldError):
            self.w.cs.craft("p", "iron_blade", 1, "standard")  # Meisterschaft 2 fehlt
        self.w.day[0] = 1
        for day in (1, 2):
            self.w.day[0] = day
            self.w.cs.craft("p", "iron_ingot", 20, "standard")  # je Tag 2000 Punkte / 10 = 200 Erfahrung -> 400 >= 300
        self.assertIn("iron_blade", self.w.svc.known_recipes("p"))
        self.w.stock("p", **{"iron_ingot__standard": 10})
        r = self.w.cs.craft("p", "iron_blade", 1, "standard")
        self.assertEqual(r.produced, {"iron_blade@common": 1})

    def test_element_infusion_needs_attunement(self):
        self.w.stock("p", **{"healing_herb__standard": 10, "clean_water__standard": 10})
        with self.assertRaises(WorldError):
            self.w.cs.craft("p", "healing_salve", 1, "standard", element="fire")
        attune(self.w.svc, "p", "fire")
        r = self.w.cs.craft("p", "healing_salve", 1, "standard", element="fire")
        self.assertEqual(r.event.payload["element"], "fire")
        self.assertEqual(self.w.svc.state("p").parts["crafting"]["elements"]["fire"], 100)  # 1 Stück Stufe 1 = 100 Punkte

    def test_npc_crafts_like_a_player_and_replay_matches(self):
        self.w.char("npc1", kind="npc")
        self.w.stock("npc1", **{"iron_ore__standard": 6})
        self.w.cs.craft("npc1", "iron_ingot", 3, "standard")
        live = copy.deepcopy(self.w.svc.state("npc1").parts)
        self.assertEqual(self.w.svc.rebuild("npc1").parts, live)
        self.assertEqual(live["identity"]["kind"], "npc")

    def test_deterministic_across_worlds(self):
        hashes = []
        for _ in range(2):
            w = World()
            w.char("p")
            w.stock("p", **{"iron_ore__standard": 50})
            for _ in range(3):
                w.cs.craft("p", "iron_ingot", 5, "standard")
            hashes.append((w.svc.log.events("p")[-1].hash, w.inv.to_json()))
        self.assertEqual(hashes[0], hashes[1])


class TechniqueAndDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.w = World()

    def discover(self, cid, did):
        for e in DISC[did]["evidence"]:
            self.w.ds.gather(cid, did, e)
        return self.w.ds.complete(cid, did)

    def test_technique_reduces_inputs_raises_quality_and_needs_discovery(self):
        self.w.char("p", smithing=700)
        self.w.stock("p", **{"iron_ore__standard": 100})
        with self.assertRaises(WorldError):
            self.w.cs.craft("p", "iron_ingot", 10, "standard", technique_id="folded_iron")  # nicht entdeckt
        base = self.w.cs.craft("p", "iron_ingot", 10, "standard")
        self.discover("p", "iron_folding")
        self.w.day[0] = 2
        tech = self.w.cs.craft("p", "iron_ingot", 10, "standard", technique_id="folded_iron")
        self.assertEqual(base.consumed, {"iron_ore@standard": 20})
        self.assertEqual(tech.consumed, {"iron_ore@standard": 18})  # 900 Promille, aufgerundet
        self.assertEqual((base.quality, tech.quality), ("common", "fine"))  # 250+120+180=550 -> +100 = 650
        self.assertEqual(self.w.svc.state("p").parts["crafting"]["techniques"], {"folded_iron": 1})

    def test_required_inputs_rounding_and_minimum(self):
        self.assertEqual(required_inputs(RULES, "iron_ingot", 1, "folded_iron"), {"iron_ore": 2})  # 1.8 -> 2
        self.assertEqual(required_inputs(RULES, "iron_ingot", 10, "folded_iron"), {"iron_ore": 18})
        self.assertEqual(required_inputs(RULES, "iron_ingot", 10, None), {"iron_ore": 20})
        self.assertEqual(required_inputs(RULES, "healing_salve", 1, None), {"healing_herb": 2, "clean_water": 1})

    def test_technique_not_applicable_to_other_recipe(self):
        self.w.char("p", smithing=700)
        self.discover("p", "iron_folding")
        self.w.stock("p", **{"flour__standard": 10})
        with self.assertRaises(WorldError):
            self.w.cs.craft("p", "bread", 1, "standard", technique_id="folded_iron")

    def test_discovered_recipe_flow_end_to_end(self):
        self.w.char("teacher", alchemy=300)
        attune(self.w.svc, "teacher", "ice")
        self.w.char("student", alchemy=300)
        # Lehrer entdeckt das Rezept eigenständig (Voraussetzung: Alchemie 2 + Eis), Schüler lernt später
        self.discover("teacher", "frostglass_recipe")
        self.w.stock("student", **{"glass_sand__standard": 6, "frost_lily__standard": 2})
        with self.assertRaises(WorldError):
            self.w.cs.craft("student", "frostglass", 1, "standard")  # Rezept noch unbekannt
        self.w.day[0] = 8  # Fenster (7 Tage ab Tag 1) vorbei
        attune(self.w.svc, "student", "ice")
        self.w.ds.teach("teacher", "student", "frostglass_recipe")
        r = self.w.cs.craft("student", "frostglass", 2, "standard")
        self.assertEqual((r.consumed, r.produced), ({"glass_sand@standard": 6, "frost_lily@standard": 2}, {"frostglass@common": 2}))

    def test_secret_recipe_needs_personal_discovery_chain(self):
        self.w.char("p", xp=36100, alchemy=700)
        attune(self.w.svc, "p", "light")
        attune(self.w.svc, "p", "shadow")
        self.w.stock("p", **{"shade_essence__standard": 5, "glass_sand__standard": 10})
        with self.assertRaises(WorldError):
            self.w.cs.craft("p", "shadow_lantern", 1, "standard")
        self.discover("p", "old_shrine_map")
        self.discover("p", "twilight_rite")
        r = self.w.cs.craft("p", "shadow_lantern", 1, "standard", technique_id="twilight_binding")
        self.assertEqual(r.produced, {"shadow_lantern@fine": 1})  # 300 + 120 + 180 + 150 = 750
        self.assertEqual(self.w.svc.known_techniques("p"), ["twilight_binding"])


if __name__ == "__main__":
    unittest.main()
