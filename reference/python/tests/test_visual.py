import copy
import json
import unittest

from mmo_cee import CharacterService
from mmo_cee.errors import CEEError
from mmo_cee.history import EventLog
from mmo_cee.interfaces import VisualEvolution as VisualEvolutionProtocol
from mmo_cee.rules import load_rules
from mmo_cee.visual import SECTIONS, VisualEvolution, appearance_diff, load_visual_rules, validate_visual_rules

from .helpers import attune
from .test_combat import EV, enc, train
from .test_essence_scoring import ember_ready, prepared

RULES = load_rules()
VR = load_visual_rules()
ELEMENTS = RULES["elements"]["all"]


def has_float(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(has_float(v) for v in x.values())
    if isinstance(x, (list, tuple)):
        return any(has_float(v) for v in x)
    return False


def valid_output(testcase, a):
    q = VR["quantize_permille"]
    for section in SECTIONS:
        testcase.assertEqual(sorted(a[section]), sorted(VR[section]))
        for k, v in a[section].items():
            p = VR[section][k]
            testcase.assertTrue(p.get("min", 0) <= v <= p.get("max", 1000), (k, v))
            testcase.assertEqual(v % q, 0, (k, v))
    for c in (a["colors"]["aura"] or []) + a["colors"]["skin_tint"]:
        testcase.assertTrue(0 <= c <= 255)
    testcase.assertFalse(has_float(a))


class VisualRulesTests(unittest.TestCase):
    def test_shipped_rules_valid(self):
        validate_visual_rules(RULES, VR)

    def test_protocol_shape(self):
        ve = VisualEvolution(RULES)
        self.assertTrue(callable(getattr(ve, "appearance")))
        self.assertTrue(hasattr(VisualEvolutionProtocol, "appearance"))

    def test_requires_new_enough_cee_rules(self):
        with self.assertRaises(CEEError):
            VisualEvolution(load_rules("rules_v3.json"))

    def _bad(self, mutate):
        vr = copy.deepcopy(VR)
        mutate(vr)
        return vr

    def test_invalid_visual_rules_rejected(self):
        cases = {
            "quantize 7": lambda v: v.update(quantize_permille=7),
            "quantize 0": lambda v: v.update(quantize_permille=0),
            "cap 0": lambda v: v["caps"].update(style_total=0),
            "quelle unbekannt": lambda v: v["morphs"]["muscle_mass"]["from"].update({"style:magic": 10}),
            "quelle art": lambda v: v["morphs"]["muscle_mass"]["from"].update({"luck:fire": 10}),
            "quelle form": lambda v: v["morphs"]["muscle_mass"]["from"].update({"essence:dragon": 10}),
            "decision option": lambda v: v["morphs"]["muscle_mass"]["from"].update({"decision:ember_vow:maybe": 10}),
            "gewicht negativ": lambda v: v["morphs"]["muscle_mass"]["from"].update({"style:strength": -5}),
            "gewicht float": lambda v: v["morphs"]["muscle_mass"]["from"].update({"style:strength": 5.5}),
            "base außerhalb": lambda v: v["morphs"]["muscle_mass"].update(base=2000),
            "min>max": lambda v: v["morphs"]["muscle_mass"].update(min=900, max=100),
            "jitter groß": lambda v: v["morphs"]["face_width"].update(jitter=900),
            "palette unvollständig": lambda v: v["palette"].pop("ice"),
            "farbe 300": lambda v: v["palette"].update(fire=[300, 0, 0]),
            "farbe 2 kanäle": lambda v: v["palette"].update(fire=[1, 2]),
            "teile ohne 0": lambda v: v["parts"]["hands"]["variants"].pop(0),
            "teile absteigend": lambda v: v["parts"]["hands"]["variants"].reverse(),
            "tag min 0": lambda v: v["animation_tags"][0].update(min=0),
            "layer form": lambda v: v["essence_layers"].update({"dragon": v["essence_layers"]["ember_kin"]}),
            "layer parameter": lambda v: v["essence_layers"]["ember_kin"]["morphs"].update({"ghost": 5}),
            "layer delta float": lambda v: v["essence_layers"]["ember_kin"]["morphs"].update({"muscle_mass": 1.5}),
            "layer tint": lambda v: v["essence_layers"]["ember_kin"].update(skin_tint_delta=[1, 2]),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                with self.assertRaises(CEEError):
                    validate_visual_rules(RULES, self._bad(mutate))


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()

    def test_fresh_character_is_a_neutral_human(self):
        self.svc.create("p", "player")
        a = self.svc.appearance("p")
        valid_output(self, a)
        self.assertEqual((a["essence_form"], a["base_class"], a["body_set"]), ("human", None, "unassigned_base"))
        self.assertIsNone(a["colors"]["aura"])
        self.assertEqual(a["element_signature"], [])
        self.assertEqual(sum(a["vfx"].values()), 0)
        self.assertEqual(a["animation_tags"], [])
        self.assertEqual(a["parts"], {"hands": "hands_plain", "shoulders": "shoulders_plain"})

    def test_deterministic_and_replay_identical(self):
        ember_ready(self.svc)
        live = copy.deepcopy(self.svc.appearance("p"))
        self.assertEqual(self.svc.appearance("p"), live)
        self.assertEqual(self.svc.appearance("p")["appearance_sha256"], live["appearance_sha256"])
        self.svc.rebuild("p")
        self.assertEqual(self.svc.appearance("p"), live)
        svc2 = CharacterService(log=EventLog.from_json("p", self.svc.log.to_json("p")))
        self.assertEqual(svc2.appearance("p"), live)

    def test_individual_variation_is_stable_per_character(self):
        for cid in ("a", "b", "c", "d"):
            self.svc.create(cid, "player")
        faces = {cid: self.svc.appearance(cid)["morphs"]["face_width"] for cid in ("a", "b", "c", "d")}
        seeds = {self.svc.appearance(c)["identity_seed"] for c in ("a", "b", "c", "d")}
        self.assertEqual(len(seeds), 4)
        self.assertGreater(len(set(faces.values())), 1)  # gleiche Historie, trotzdem erkennbar verschieden
        for cid in faces:
            self.assertEqual(self.svc.appearance(cid)["morphs"]["face_width"], faces[cid])
        for v in faces.values():
            self.assertTrue(500 - 120 - 5 <= v <= 500 + 120 + 5)

    def test_element_attunement_creates_aura_and_color(self):
        prepared(self.svc)
        before = self.svc.appearance("p")
        attune(self.svc, "p", "fire")
        a = self.svc.appearance("p")
        self.assertGreater(a["vfx"]["aura_fire"], before["vfx"]["aura_fire"])
        self.assertEqual(a["element_signature"], ["fire"])
        self.assertEqual(a["colors"]["aura"], VR["palette"]["fire"])
        for other in ELEMENTS:
            if other != "fire":
                self.assertEqual(a["vfx"][f"aura_{other}"], before["vfx"][f"aura_{other}"])

    def test_every_free_element_pair_gets_a_valid_distinct_blend(self):
        import itertools
        seen = {}
        for i, (e1, e2) in enumerate(itertools.combinations(ELEMENTS, 2)):
            cid = f"c{i}"
            prepared(self.svc, cid, xp=1000)
            attune(self.svc, cid, e1)
            attune(self.svc, cid, e2)
            a = self.svc.appearance(cid)
            valid_output(self, a)
            self.assertEqual(a["element_signature"], sorted([e1, e2]))
            lo = [min(VR["palette"][e1][c], VR["palette"][e2][c]) for c in range(3)]
            hi = [max(VR["palette"][e1][c], VR["palette"][e2][c]) for c in range(3)]
            self.assertTrue(all(lo[c] <= a["colors"]["aura"][c] <= hi[c] for c in range(3)))
            seen[(e1, e2)] = (tuple(a["element_signature"]), tuple(a["colors"]["aura"]))
        self.assertEqual(len(seen), 36)  # 36 Zweierkombinationen, alle ohne feste Paarliste darstellbar
        self.assertEqual(len({sig for sig, _ in seen.values()}), 36)  # jede Kombination hat eine eigene Signatur
        self.assertGreater(len({color for _, color in seen.values()}), 30)  # und (fast) immer eine eigene Mischfarbe

    def test_three_elements_endgame_blend_and_order_independence(self):
        prepared(self.svc, "x", xp=400000)
        prepared(self.svc, "y", xp=400000)
        for e in ("fire", "wind", "light"):
            attune(self.svc, "x", e)
        for e in ("light", "fire", "wind"):
            attune(self.svc, "y", e)
        ax, ay = self.svc.appearance("x"), self.svc.appearance("y")
        self.assertEqual(ax["element_signature"], ["fire", "light", "wind"])
        self.assertEqual(ax["colors"], ay["colors"])  # Reihenfolge der Prägung ändert nichts
        self.assertEqual(ax["vfx"], ay["vfx"])

    def test_combat_style_changes_body_and_tags(self):
        for cid, acts in (("heavy", {"heavy_hit": 43, "block": 33}), ("agile", {"dodge": 33, "perfect_dodge": 18, "light_hit": 120})):
            self.svc.create(cid, "player")
            for day in range(1, 5):
                train(self.svc, cid, day, acts, n=6)
        h, g = self.svc.appearance("heavy"), self.svc.appearance("agile")
        self.assertGreater(h["morphs"]["muscle_mass"], g["morphs"]["muscle_mass"])
        self.assertGreater(g["morphs"]["leanness"], h["morphs"]["leanness"])
        self.assertIn("heavy_stance", h["animation_tags"])
        self.assertIn("agile_stance", g["animation_tags"])
        self.assertNotIn("agile_stance", h["animation_tags"])
        self.assertEqual((h["parts"]["shoulders"], g["parts"]["shoulders"]), ("shoulders_guarded", "shoulders_plain"))
        self.assertEqual((h["morphs"]["muscle_mass"], g["morphs"]["leanness"]), (660, 660))
        self.assertNotEqual(h["appearance_sha256"], g["appearance_sha256"])

    def test_tiny_history_cannot_create_extreme_look(self):
        self.svc.create("p", "player")
        before = self.svc.appearance("p")
        self.svc.record("p", EV, enc("e1", actions={"heavy_hit": 1}))  # 100 % Kraft, aber winzige Datenbasis (100 Punkte)
        after = self.svc.appearance("p")
        self.assertEqual(after["morphs"]["muscle_mass"], before["morphs"]["muscle_mass"])
        self.assertEqual(after["animation_tags"], [])

    def test_more_training_same_style_never_reduces_the_look(self):
        self.svc.create("p", "player")
        last = self.svc.appearance("p")["morphs"]["muscle_mass"]
        for day in range(1, 8):
            train(self.svc, "p", day, {"heavy_hit": 43}, n=6)
            cur = self.svc.appearance("p")["morphs"]["muscle_mass"]
            self.assertGreaterEqual(cur, last)
            last = cur
        self.assertGreater(last, 250)

    def test_professions_leave_visible_traces(self):
        self.svc.create("p", "player")
        base = self.svc.appearance("p")
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 3700})
        mid = self.svc.appearance("p")
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 10**6})
        top = self.svc.appearance("p")
        self.assertGreater(mid["materials"]["soot_amount"], base["materials"]["soot_amount"])
        self.assertGreater(top["materials"]["soot_amount"], mid["materials"]["soot_amount"])
        self.assertEqual((base["parts"]["hands"], mid["parts"]["hands"], top["parts"]["hands"]),
                         ("hands_plain", "hands_calloused", "hands_forge_scarred"))

    def test_essence_form_layer_and_class_identity(self):
        ember_ready(self.svc)
        self.svc.record("p", "identity.class_chosen", {"base_class": "warrior"})
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 3000})
        human = self.svc.appearance("p")
        self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})
        self.svc.record("p", "essence.adopted", {"form": "ember_kin"})
        a = self.svc.appearance("p")
        valid_output(self, a)
        self.assertEqual((a["essence_form"], a["body_set"], a["base_class"]), ("ember_kin", "warrior_base", "warrior"))
        self.assertEqual(human["body_set"], a["body_set"])  # Grundklasse bleibt Identität
        self.assertEqual(a["parts"]["head_ornament"], "horns_ember")
        self.assertNotIn("head_ornament", human["parts"])
        self.assertIn("ember_gait", a["animation_tags"])
        self.assertGreater(a["materials"]["skin_ember_cracks"], human["materials"]["skin_ember_cracks"])
        self.assertEqual(a["vfx"]["essence_presence"], 1000)
        self.assertNotEqual(a["colors"]["skin_tint"], human["colors"]["skin_tint"])
        self.assertEqual(sorted(a["parts"]), sorted(set(a["parts"])))

    def test_each_form_has_its_own_look(self):
        shas = {}
        for i, form in enumerate(VR["essence_layers"]):
            cid = f"f{i}"
            prepared(self.svc, cid)
            # Wesensform per Regeldaten-Eignung nicht nötig: direkt über Zustand setzen (reine Ableitung testen)
            st = self.svc.state(cid)
            st.parts["essence"]["form"] = form
            shas[form] = VisualEvolution(RULES).appearance(st)
        self.assertEqual(len({a["parts"]["head_ornament"] for a in shas.values()}), len(shas))
        self.assertEqual(len({a["appearance_sha256"] for a in shas.values()}), len(shas))

    def _as_form(self, cid, form):
        st = copy.deepcopy(self.svc.state(cid))
        st.parts["essence"]["form"] = form
        return VisualEvolution(RULES).appearance(st)

    def test_essence_layer_deltas_are_applied_exactly(self):
        prepared(self.svc)
        human = self._as_form("p", "human")
        ember = self._as_form("p", "ember_kin")
        stone = self._as_form("p", "stone_born")
        layers = VR["essence_layers"]
        # Delta-Vielfache der Quantisierung -> exakte Differenz (solange nichts geklemmt wird)
        self.assertEqual(ember["morphs"]["muscle_mass"] - human["morphs"]["muscle_mass"], layers["ember_kin"]["morphs"]["muscle_mass"])
        self.assertEqual(ember["materials"]["skin_roughness"] - human["materials"]["skin_roughness"], layers["ember_kin"]["materials"]["skin_roughness"])
        self.assertEqual(stone["morphs"]["muscle_mass"] - human["morphs"]["muscle_mass"], layers["stone_born"]["morphs"]["muscle_mass"])
        self.assertEqual(stone["morphs"]["leanness"] - human["morphs"]["leanness"], layers["stone_born"]["morphs"]["leanness"])  # negativ
        self.assertEqual([ember["colors"]["skin_tint"][c] - human["colors"]["skin_tint"][c] for c in range(3)], layers["ember_kin"]["skin_tint_delta"])

    def test_values_are_clamped_to_parameter_bounds(self):
        vr = copy.deepcopy(VR)
        vr["morphs"]["muscle_mass"]["from"] = {"element_attuned:fire": 5000}  # würde 5250 ergeben
        vr["morphs"]["leanness"].update(base=50, min=0, max=400)
        vr["morphs"]["shoulder_width"].update(base=500, min=300, max=900)
        vr["essence_layers"]["stone_born"]["morphs"] = {"leanness": -900, "shoulder_width": -900}
        validate_visual_rules(RULES, vr)
        prepared(self.svc)
        attune(self.svc, "p", "fire")
        a = VisualEvolution(RULES, vr).appearance(self.svc.state("p"))
        self.assertEqual(a["morphs"]["muscle_mass"], 1000)  # oben geklemmt
        st = copy.deepcopy(self.svc.state("p"))
        st.parts["essence"]["form"] = "stone_born"
        b = VisualEvolution(RULES, vr).appearance(st)
        self.assertEqual(b["morphs"]["leanness"], 0)  # unten geklemmt
        self.assertEqual(b["morphs"]["shoulder_width"], 300)  # eigenes Minimum
        vr["morphs"]["leanness"]["from"] = {"element_attuned:fire": 5000}
        self.assertEqual(VisualEvolution(RULES, vr).appearance(self.svc.state("p"))["morphs"]["leanness"], 400)  # eigenes Maximum

    def test_aura_color_is_affinity_weighted_integer_blend(self):
        prepared(self.svc)
        attune(self.svc, "p", "fire", amount=300)  # Gewicht 500 + 1000//2 = 1000
        attune(self.svc, "p", "water", amount=100)  # Affinität 333 -> Gewicht 500 + 166 = 666
        a = self.svc.appearance("p")
        fire, water = VR["palette"]["fire"], VR["palette"]["water"]
        expected = [(fire[c] * 1000 + water[c] * 666) // 1666 for c in range(3)]
        self.assertEqual(a["colors"]["aura"], expected)
        self.assertNotEqual(expected, [(fire[c] + water[c]) // 2 for c in range(3)])  # nicht einfach der Mittelwert

    def test_tag_and_part_thresholds_are_inclusive(self):
        self.svc.create("p", "player")
        for day in range(1, 4):
            train(self.svc, "p", day, {"heavy_hit": 43, "block": 33}, n=6)  # gemischter Stil: Kraft-Anteil unter 1000
        st = self.svc.state("p")
        v = VisualEvolution(RULES)._sources(st)("style:strength")
        self.assertTrue(0 < v < 1000)
        for minimum, expected in ((v, True), (v + 1, False)):
            vr = copy.deepcopy(VR)
            vr["animation_tags"][0].update(min=minimum)  # heavy_stance
            vr["parts"]["shoulders"] = {"source": "style:strength", "variants": [{"min": 0, "id": "a"}, {"min": minimum, "id": "b"}]}
            a = VisualEvolution(RULES, vr).appearance(st)
            self.assertEqual("heavy_stance" in a["animation_tags"], expected, minimum)
            self.assertEqual(a["parts"]["shoulders"], "b" if expected else "a", minimum)

    def test_npc_same_pipeline(self):
        ember_ready(self.svc, "n", kind="npc")
        self.svc.record("n", "profession.work", {"profession": "smithing", "xp": 3000})
        self.svc.record("n", "essence.trial_passed", {"form": "ember_kin"})
        self.svc.record("n", "essence.adopted", {"form": "ember_kin"})
        a = self.svc.appearance("n")
        valid_output(self, a)
        self.assertEqual(a["essence_form"], "ember_kin")

    def test_unrelated_events_do_not_change_appearance(self):
        self.svc.create("p", "player")
        a = self.svc.appearance("p")
        self.svc.record("p", "identity.xp_gained", {"amount": 500})  # Stufe ist keine Quelle
        self.assertEqual(self.svc.appearance("p"), a)
        self.svc.record("p", "element.exposure", {"element": "fire", "amount": 30})  # Affinität wirkt dagegen
        self.assertNotEqual(self.svc.appearance("p")["appearance_sha256"], a["appearance_sha256"])

    def test_hash_tracks_content_and_diff_is_minimal(self):
        prepared(self.svc)
        a = self.svc.appearance("p")
        attune(self.svc, "p", "ice")
        b = self.svc.appearance("p")
        self.assertNotEqual(a["appearance_sha256"], b["appearance_sha256"])
        diff = appearance_diff(a, b)
        self.assertEqual(set(diff), {"vfx", "materials", "colors", "element_signature"})
        self.assertEqual(set(diff["vfx"]), {"aura_ice"})
        self.assertEqual(set(diff["materials"]), {"skin_frost"})
        self.assertEqual(set(diff["colors"]), {"aura"})
        self.assertEqual(diff["element_signature"], ["ice"])
        self.assertNotIn("morphs", diff)
        self.assertNotIn("parts", diff)
        self.assertEqual(appearance_diff(a, a), {})

    def test_output_is_compact_and_json_serializable(self):
        ember_ready(self.svc)
        raw = json.dumps(self.svc.appearance("p"), sort_keys=True, separators=(",", ":"))
        self.assertLess(len(raw), 2048)
        json.loads(raw)

    def test_sweep_many_histories_always_valid(self):
        import random
        # deterministische Pseudo-Historien (fester Seed im Test, kein Zufall im Produktivcode)
        rng = random.Random(4711)
        schema = None
        for n in range(60):
            cid = f"s{n}"
            prepared(self.svc, cid, xp=rng.choice([100, 1000, 10000, 400000]))
            for e in rng.sample(ELEMENTS, rng.choice([0, 1, 2])):
                self.svc.record(cid, "element.exposure", {"element": e, "amount": rng.choice([10, 100, 1000])})
                if rng.random() < 0.7:
                    try:
                        self.svc.record(cid, "element.attuned", {"element": e})
                    except Exception:
                        pass
            for p in rng.sample(RULES["professions"]["all"], rng.choice([0, 1, 3])):
                self.svc.record(cid, "profession.work", {"profession": p, "xp": rng.choice([50, 700, 5000, 10**6])})
            for day in range(1, rng.choice([1, 3, 6])):
                acts = rng.choice([{"heavy_hit": 43}, {"dodge": 33}, {"ally_heal": 20}, {"stun_applied": 10}, {"parry": 15}])
                train(self.svc, cid, day, acts, n=rng.choice([1, 6]))
            a = self.svc.appearance(cid)
            valid_output(self, a)
            keys = (sorted(a), sorted(a["morphs"]), sorted(a["vfx"]), sorted(a["materials"]))
            schema = schema or keys
            self.assertEqual(keys, schema)  # Schema für alle Figuren gleich (Replikation/Client-Erwartung)


if __name__ == "__main__":
    unittest.main()
