import copy
import json
import tempfile
import unittest
from pathlib import Path

from mmo_cee import golden_visual as gv
from mmo_cee.rules import load_rules
from mmo_cee.visual import SECTIONS, load_visual_rules

PATH = Path(__file__).resolve().parents[2] / "golden_visual" / "appearance.json"


def has_float(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(has_float(v) for v in x.values())
    if isinstance(x, list):
        return any(has_float(v) for v in x)
    return False


class VisualGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vec = json.loads(PATH.read_text(encoding="utf-8"))
        cls.by = {c["name"]: c for c in cls.vec["cases"]}

    def test_committed_file_equals_regeneration_byte_for_byte(self):
        self.assertEqual(PATH.read_text(encoding="utf-8"), gv.render(gv.build_vector()))

    def test_stored_states_reproduce_stored_appearances(self):
        self.assertEqual(gv.verify_vector(self.vec), [])

    def test_cli(self):
        self.assertEqual(gv.main(["g", "check", str(PATH.parent)]), 0)
        self.assertEqual(gv.main(["g"]), 2)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gv.main(["g", "check", tmp]), 1)
            self.assertEqual(gv.main(["g", "write", tmp]), 0)
            self.assertEqual(gv.main(["g", "check", tmp]), 0)
            f = Path(tmp) / "appearance.json"
            f.write_text(f.read_text(encoding="utf-8").replace('"horns_ember"', '"horns_other"'), encoding="utf-8")
            self.assertEqual(gv.main(["g", "check", tmp]), 1)

    def test_tampering_is_detected(self):
        def mutated(fn):
            v = copy.deepcopy(self.vec)
            fn(v)
            return gv.verify_vector(v)

        i = next(k for k, c in enumerate(self.vec["cases"]) if c["name"] == "warrior_ember_kin_adopted")
        cases = {
            "morph": lambda v: v["cases"][i]["appearance"]["morphs"].update(muscle_mass=1),
            "hash": lambda v: v["cases"][i]["appearance"].update(appearance_sha256="0" * 64),
            "state": lambda v: v["cases"][i]["state"]["element"]["attuned"].append("ice"),
            "character_id": lambda v: v["cases"][i].update(character_id="someone-else"),
            "visual_sha": lambda v: v.update(visual_rules_sha256="0" * 64),
            "cee_sha": lambda v: v.update(cee_rules_sha256="0" * 64),
            "format": lambda v: v.update(format=9),
        }
        for label, fn in cases.items():
            with self.subTest(label):
                self.assertNotEqual(mutated(fn), [], label)

    def test_coverage(self):
        self.assertGreaterEqual(len(self.vec["cases"]), 20)
        forms = {c["appearance"]["essence_form"] for c in self.vec["cases"]}
        self.assertTrue({"human", "ember_kin", "tide_walker", "stone_born"} <= forms)
        classes = {c["appearance"]["base_class"] for c in self.vec["cases"]}
        self.assertTrue({None, "warrior", "archer", "shaman_alchemist"} <= classes)
        sizes = {len(c["appearance"]["element_signature"]) for c in self.vec["cases"]}
        self.assertEqual(sizes, {0, 1, 2, 3})
        tags = {t for c in self.vec["cases"] for t in c["appearance"]["animation_tags"]}
        self.assertTrue({"heavy_stance", "agile_stance", "channeling_pose", "wave_gait"} <= tags)
        hands = {c["appearance"]["parts"]["hands"] for c in self.vec["cases"]}
        self.assertEqual(hands, {"hands_plain", "hands_calloused", "hands_forge_scarred"})

    def test_all_vectors_share_one_schema_and_are_integer_only(self):
        vr = load_visual_rules()
        for c in self.vec["cases"]:
            a = c["appearance"]
            for s in SECTIONS:
                self.assertEqual(sorted(a[s]), sorted(vr[s]), c["name"])
            self.assertFalse(has_float(a), c["name"])
            self.assertFalse(has_float(c["state"]), c["name"])
            self.assertEqual(len(a["appearance_sha256"]), 64)

    def test_documented_properties(self):
        by = self.by
        self.assertEqual(by["fire_and_water_unequal_affinity"]["appearance"]["colors"], by["water_and_fire_reverse_order"]["appearance"]["colors"])
        self.assertEqual(by["fire_and_water_unequal_affinity"]["appearance"]["colors"]["aura"], [169, 105, 121])
        self.assertEqual(by["fire_attuned"]["appearance"]["colors"]["aura"], load_visual_rules()["palette"]["fire"])
        self.assertIsNone(by["exposed_not_attuned"]["appearance"]["colors"]["aura"])  # Affinität allein: keine Aura-Farbe
        self.assertGreater(by["exposed_not_attuned"]["appearance"]["vfx"]["aura_earth"], 0)
        self.assertEqual(by["tiny_combat_history"]["appearance"], by["fresh_human"]["appearance"])  # gleiche ID, winzige Historie: keine Wirkung
        self.assertNotEqual(by["fresh_human"]["appearance"]["identity_seed"], by["fresh_human_other_id"]["appearance"]["identity_seed"])
        self.assertEqual(by["fresh_human"]["state"], by["fresh_human_other_id"]["state"])  # gleicher Zustand ...
        self.assertNotEqual(by["fresh_human"]["appearance"]["morphs"], by["fresh_human_other_id"]["appearance"]["morphs"])  # ... andere Figur
        self.assertEqual(by["warrior_ember_kin_adopted"]["appearance"]["body_set"], "warrior_base")
        self.assertEqual(by["npc_stone_born_adopted"]["state"]["identity"]["kind"], "npc")

    def test_rules_file_hashes_match(self):
        self.assertEqual(self.vec["cee_rules_sha256"], gv._sha(gv.CEE_RULES))
        self.assertEqual(self.vec["visual_rules_sha256"], gv._sha(gv.VISUAL_RULES))
        self.assertEqual(load_rules(self.vec["cee_rules_file"]).version, "4")


if __name__ == "__main__":
    unittest.main()
