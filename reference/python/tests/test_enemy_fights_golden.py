import copy
import json
import tempfile
import unittest
from pathlib import Path

from mmo_sim import golden_enemy_fights as golden

PATH = Path(__file__).resolve().parents[2] / "golden_enemy_fights" / "sim_enemy_fights.json"


class EnemyFightGoldenTests(unittest.TestCase):
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
            f = Path(tmp) / "sim_enemy_fights.json"
            f.write_text(f.read_text(encoding="utf-8").replace('"outcome":"fled"', '"outcome":"victory"', 1), encoding="utf-8")
            self.assertEqual(golden.main(["g", "check", tmp]), 1)

    def test_tampering_is_detected(self):
        idx = next(i for i, c in enumerate(self.vec["cases"]) if c["name"] == "slam_parry")

        def mutated(fn):
            v = copy.deepcopy(self.vec)
            fn(v)
            return golden.verify_vector(v)

        cases = {
            "opponents_hp": lambda v: v["cases"][idx]["result"].update(opponents=[1]),
            "events": lambda v: v["cases"][idx]["result"]["events"].pop(),
            "event_field": lambda v: v["cases"][idx]["result"]["events"][1].update(outcome="hit"),
            "abilities": lambda v: v["cases"][idx].update(abilities=[["ground_pound"]]),
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
        self.assertGreaterEqual(len(self.ok), 45)
        errors = [c for c in self.vec["cases"] if c["expect"] == "error"]
        self.assertEqual(len(errors), 6)
        self.assertTrue(all(c["name"].startswith("invalid_") for c in errors))
        for c in self.ok:
            self.assertEqual(len(c["reports"]), len(c["players"]))
            self.assertGreaterEqual(len(c["result"]["opponents"]), len(c["opponents"]))                 # Beschworene kommen hinzu
            self.assertEqual(c["result"]["opponent_hp"], sum(c["result"]["opponents"]))
            for p, rep in zip(c["result"]["players"], c["reports"]):
                self.assertEqual(rep is None, not p["actions"], c["name"])
                if rep:
                    self.assertEqual((rep["actions"], rep["outcome"]), (p["actions"], p["outcome"]))
        self.assertEqual({p["outcome"] for c in self.ok for p in c["result"]["players"]}, {"victory", "defeat", "fled"})
        kinds = {e["type"] for c in self.ok for e in c["result"]["events"]}
        self.assertEqual(kinds, {"telegraph", "resolved", "interrupted", "shield_broken", "phase"})
        abilities = {e["ability"] for c in self.ok for e in c["result"]["events"] if e["type"] == "resolved"}
        self.assertTrue({"heavy_slam", "ground_pound", "stunning_blow", "crippling_bite", "burning_curse", "stone_skin", "mend", "howl", "call_pack", "call_imps"} <= abilities)

    def test_key_cases_show_the_intended_outcomes(self):
        by = {c["name"]: c["result"] for c in self.ok}

        def resolved(name):
            return [e for e in by[name]["events"] if e["type"] == "resolved"][0]
        self.assertEqual([resolved(n)["outcome"] for n in ("slam_hit", "slam_dodge", "slam_perfect_dodge", "slam_block", "slam_parry", "slam_evade_skill")],
                         ["hit", "dodge", "perfect_dodge", "block", "parry", "evade"])
        self.assertEqual(resolved("area_two_players_one_dodges")["outcomes"], {"0": "hit", "1": "dodge"})
        self.assertTrue(any(e["type"] == "interrupted" for e in by["burning_curse_interrupted_by_stun"]["events"]))
        self.assertTrue(any(e["type"] == "shield_broken" and e["by"] == "parry" for e in by["stone_skin_broken_by_parry"]["events"]))
        self.assertFalse(any(e["type"] == "shield_broken" for e in by["stone_skin_not_broken_by_heavy"]["events"]))
        self.assertEqual(by["call_pack_victory_needs_summons"]["outcome"], "victory")
        self.assertGreater(len(by["call_pack_summons"]["opponents"]), 1)

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
