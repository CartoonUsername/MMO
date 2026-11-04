import copy
import json
import tempfile
import unittest
from pathlib import Path

from mmo_sim import golden_enemies as golden

PATH = Path(__file__).resolve().parents[2] / "golden_enemies" / "enemy_rolls.json"


class EnemyGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vec = json.loads(PATH.read_text(encoding="utf-8"))
        cls.ok = [c for c in cls.vec["cases"] if c["expect"] == "ok"]

    def test_committed_file_equals_regeneration_byte_for_byte(self):
        self.assertEqual(PATH.read_text(encoding="utf-8"), golden.render(golden.build_vector()))

    def test_replay_without_deviation(self):
        self.assertEqual(golden.verify_vector(self.vec), [])

    def test_cli(self):
        self.assertEqual(golden.main(["g", "check", str(PATH.parent)]), 0)
        self.assertEqual(golden.main(["g"]), 2)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(golden.main(["g", "check", tmp]), 1)
            self.assertEqual(golden.main(["g", "write", tmp]), 0)
            self.assertEqual(golden.main(["g", "check", tmp]), 0)
            f = Path(tmp) / "enemy_rolls.json"
            f.write_text(f.read_text(encoding="utf-8").replace('"crippling_bite"', '"howl"', 1), encoding="utf-8")
            self.assertEqual(golden.main(["g", "check", tmp]), 1)

    def test_tampering_is_detected(self):
        idx = next(i for i, c in enumerate(self.vec["cases"]) if c["name"] == "roll_bog_witch_sp1_1")
        pidx = next(i for i, c in enumerate(self.vec["cases"]) if c["name"] == "phase_alpha_wolf_599")

        def mutated(fn):
            v = copy.deepcopy(self.vec)
            fn(v)
            return golden.verify_vector(v)

        cases = {
            "roll_result": lambda v: v["cases"][idx]["result"].update(abilities=["burning_curse"]),
            "roll_day": lambda v: v["cases"][idx].update(day=2),
            "roll_spawn": lambda v: v["cases"][idx].update(spawn="sp2"),
            "phase_factor": lambda v: v["cases"][pidx]["result"].update(attack_interval_permille=1000),
            "phase_abilities": lambda v: v["cases"][pidx]["result"].update(abilities=["howl"]),
            "expect": lambda v: v["cases"][idx].update(expect="error"),
            "rules_hash": lambda v: v.update(rules_sha256="0" * 64),
            "format": lambda v: v.update(format=2),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertTrue(mutated(fn))

    def test_cases_cover_every_template_spawn_day_and_phase_threshold(self):
        types = {c["type"] for c in self.ok if c["kind"] == "roll"}
        self.assertTrue({"wolf", "bear", "alpha_wolf", "wisp_healer", "bog_witch", "stone_heart_colossus"} <= types)
        self.assertGreaterEqual(len([c for c in self.ok if c["kind"] == "roll"]), 9 * 5 * 6)
        phases = [c for c in self.ok if c["kind"] == "phase"]
        self.assertEqual({c["type"] for c in phases}, {"alpha_wolf", "stone_heart_colossus"})
        errors = [c for c in self.vec["cases"] if c["expect"] == "error"]
        self.assertEqual(len(errors), 6)
        self.assertTrue(all(c["name"].startswith("invalid_") and "result" not in c for c in errors))

    def test_rolls_actually_differ_across_spawns_and_days(self):
        res = {(c["spawn"], c["day"]): tuple(c["result"]["abilities"]) for c in self.ok if c["kind"] == "roll" and c["type"] == "bog_witch"}
        self.assertGreater(len(set(res.values())), 4)

    def test_no_floats(self):
        def has_float(x):
            if isinstance(x, float):
                return True
            if isinstance(x, dict):
                return any(has_float(v) for v in x.values())
            if isinstance(x, list):
                return any(has_float(v) for v in x)
            return False
        self.assertFalse(has_float(self.vec))


if __name__ == "__main__":
    unittest.main()
