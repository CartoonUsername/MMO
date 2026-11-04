import copy
import json
import tempfile
import unittest
from pathlib import Path

from mmo_sim import golden_pack as golden

PATH = Path(__file__).resolve().parents[2] / "golden_pack" / "sim_packs.json"


class PackGoldenTests(unittest.TestCase):
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
            f = Path(tmp) / "sim_packs.json"
            f.write_text(f.read_text(encoding="utf-8").replace('"opponent_hp":1500', '"opponent_hp":1501', 1), encoding="utf-8")
            self.assertEqual(golden.main(["g", "check", tmp]), 1)

    def test_tampering_is_detected(self):
        idx = next(i for i, c in enumerate(self.vec["cases"]) if c["name"] == "sweep_hits_all")

        def mutated(fn):
            v = copy.deepcopy(self.vec)
            fn(v)
            return golden.verify_vector(v)

        cases = {
            "opponents_hp": lambda v: v["cases"][idx]["result"].update(opponents=[1, 1, 1]),
            "player_hp": lambda v: v["cases"][idx]["result"]["players"][0].update(player_hp=1),
            "actions": lambda v: v["cases"][idx]["result"]["players"][0].update(actions={}),
            "outcome": lambda v: v["cases"][idx]["result"].update(outcome="victory"),
            "report": lambda v: v["cases"][idx]["reports"].__setitem__(0, None),
            "input": lambda v: v["cases"][idx]["players"][0].update(inputs=[]),
            "opponent_list": lambda v: v["cases"][idx].update(opponents=["wolf"]),
            "expect": lambda v: v["cases"][idx].update(expect="error"),
            "rules_hash": lambda v: v.update(rules_sha256="0" * 64),
            "format": lambda v: v.update(format=2),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertTrue(mutated(fn))

    def test_cases_cover_success_errors_and_reports(self):
        self.assertGreaterEqual(len(self.ok), 30)
        errors = [c for c in self.vec["cases"] if c["expect"] == "error"]
        self.assertGreaterEqual(len(errors), 10)
        self.assertTrue(all(c["name"].startswith("invalid_") for c in errors))
        for c in self.ok:
            self.assertEqual(len(c["reports"]), len(c["players"]))
            self.assertEqual(len(c["result"]["opponents"]), len(c["opponents"]))
            self.assertEqual(c["result"]["opponent_hp"], sum(c["result"]["opponents"]))
            for p, rep in zip(c["result"]["players"], c["reports"]):
                self.assertEqual(rep is None, not p["actions"], c["name"])
                if rep:
                    self.assertEqual((rep["actions"], rep["outcome"]), (p["actions"], p["outcome"]))
        self.assertEqual({p["outcome"] for c in self.ok for p in c["result"]["players"]}, {"victory", "defeat", "fled"})

    def test_pack_reports_name_the_strongest_opponent(self):
        c = next(c for c in self.ok if c["name"] == "focus_defaults_to_first")
        self.assertEqual(c["reports"][0]["opponent_type"], "bear")

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
