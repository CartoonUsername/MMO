import copy
import json
import tempfile
import unittest
from pathlib import Path

from mmo_cee import CharacterService
from mmo_cee.rules import load_rules
from mmo_sim import golden
from mmo_sim.rules import load_sim_rules

PATH = Path(__file__).resolve().parents[2] / "golden_sim" / "sim_fights.json"
CEE_ACTIONS = ["light_hit", "precise_hit", "heavy_hit", "dodge", "perfect_dodge", "block", "parry",
               "stun_applied", "slow_applied"]


def has_float(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(has_float(v) for v in x.values())
    if isinstance(x, list):
        return any(has_float(v) for v in x)
    return False


class SimGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vec = json.loads(PATH.read_text(encoding="utf-8"))
        cls.ok = [c for c in cls.vec["cases"] if c["expect"] == "ok"]
        cls.err = [c for c in cls.vec["cases"] if c["expect"] == "error"]

    def test_committed_file_equals_regeneration_byte_for_byte(self):
        self.assertEqual(PATH.read_text(encoding="utf-8"), golden.render(golden.build_vector()))

    def test_replay_without_deviation(self):
        self.assertEqual(golden.verify_vector(self.vec), [])

    def test_cli(self):
        self.assertEqual(golden.main(["g", "check", str(PATH.parent)]), 0)
        self.assertEqual(golden.main(["g"]), 2)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(golden.main(["g", "check", tmp]), 1)  # fehlt
            self.assertEqual(golden.main(["g", "write", tmp]), 0)
            self.assertEqual(golden.main(["g", "check", tmp]), 0)
            f = Path(tmp) / "sim_fights.json"
            f.write_text(f.read_text(encoding="utf-8").replace('"ticks":47', '"ticks":48'), encoding="utf-8")
            self.assertEqual(golden.main(["g", "check", tmp]), 1)  # abweichend

    def test_tampering_is_detected(self):
        def mutated(fn):
            v = copy.deepcopy(self.vec)
            fn(v)
            return golden.verify_vector(v)

        first_ok = next(i for i, c in enumerate(self.vec["cases"]) if c["expect"] == "ok" and c["result"]["actions"])
        cases = {
            "outcome": lambda v: v["cases"][first_ok]["result"].update(outcome="defeat"),
            "ticks": lambda v: v["cases"][first_ok]["result"].update(ticks=1),
            "actions": lambda v: v["cases"][first_ok]["result"]["actions"].update(light_hit=99),
            "report": lambda v: v["cases"][first_ok]["report"].update(duration_s=999),
            "expect": lambda v: v["cases"][-1].update(expect="ok"),
            "input": lambda v: v["cases"][first_ok].update(inputs=[]),  # Eingaben passen nicht mehr zum gespeicherten Ergebnis
            "rules_sha": lambda v: v.update(rules_sha256="0" * 64),
            "format": lambda v: v.update(format=2),
        }
        for label, fn in cases.items():
            with self.subTest(label):
                self.assertNotEqual(mutated(fn), [], label)

    def test_coverage_outcomes_opponents_and_actions(self):
        self.assertEqual({c["result"]["outcome"] for c in self.ok}, {"victory", "defeat", "fled"})
        cfg = load_sim_rules()
        self.assertEqual({c["opponent_type"] for c in self.ok}, set(cfg["opponents"]))
        seen = {a for c in self.ok for a in c["result"]["actions"]}
        self.assertEqual(seen, set(CEE_ACTIONS))
        self.assertGreaterEqual(len(self.err), 10)
        self.assertTrue(any(c["result"]["ignored_inputs"] > 0 for c in self.ok))

    def test_every_report_is_accepted_by_the_cee(self):
        svc = CharacterService()
        n = 0
        for c in self.ok:
            if c["report"] is None:
                self.assertEqual(c["result"]["actions"], {}, c["name"])
                continue
            n += 1
            svc.create(f"c{n}", "player")
            svc.record(f"c{n}", "combat.encounter_resolved", c["report"])  # wirft bei Ablehnung
        self.assertGreater(n, 25)

    def test_report_fields_derive_from_rules_not_from_inputs(self):
        rules = load_sim_rules()
        for c in self.ok:
            if c["report"]:
                self.assertEqual(c["report"]["opponent_level"], rules["opponents"][c["opponent_type"]]["level"])
                self.assertEqual(c["report"]["day"], 1)
                self.assertGreaterEqual(c["report"]["duration_s"], 5)
                self.assertEqual(c["report"]["actions"], c["result"]["actions"])

    def test_integer_only_results(self):
        for c in self.ok:
            self.assertFalse(has_float(c["result"]), c["name"])
            self.assertFalse(has_float(c["report"]), c["name"])

    def test_documented_behaviours(self):
        by = {c["name"]: c["result"] for c in self.ok}
        self.assertEqual(by["lights_kill_dummy"]["actions"], {"light_hit": 13})
        self.assertEqual(by["dodge_at_37"]["actions"], {"dodge": 1})
        self.assertEqual(by["dodge_at_39"]["actions"], {"perfect_dodge": 1})
        self.assertEqual(by["dodge_at_36"]["actions"], {})
        self.assertEqual(by["block_at_39"]["actions"], {"parry": 1})
        self.assertEqual(by["parry_then_precise"]["actions"], {"parry": 1, "precise_hit": 1})
        self.assertEqual(by["slow_delays_attack"]["damage_ticks"][:2], [40, 97])
        self.assertEqual(by["no_slow_baseline"]["damage_ticks"][:2], [40, 80])
        self.assertGreater(by["level_scales_hp_high"]["ticks"], by["level_scales_hp_low"]["ticks"])
        self.assertEqual(by["timeout_vs_dummy"]["ticks"], load_sim_rules()["max_ticks"])
        self.assertEqual(by["dodge_every_cycle_bear"]["actions"], {"dodge": 11})
        self.assertEqual(by["stamina_pressure_golem"]["ignored_inputs"], 58)  # Ohne Ausdauerprüfung wären es 40

    def test_rules_file_hash_matches(self):
        self.assertEqual(self.vec["rules_sha256"], golden.rules_sha256())

    def test_error_cases_cover_each_validation_class(self):
        names = {c["name"] for c in self.err}
        for needed in ("invalid_not_a_list", "invalid_item_shape", "invalid_negative_tick", "invalid_float_tick",
                       "invalid_bool_tick", "invalid_string_tick", "invalid_tick_too_large", "invalid_unsorted",
                       "invalid_command", "invalid_too_many_inputs", "invalid_opponent", "invalid_level_zero",
                       "invalid_level_float"):
            self.assertIn(needed, names)

    def test_pseudo_random_generator_is_stable(self):
        self.assertEqual(golden.pseudo_random_inputs(1, 5, 6000), golden.pseudo_random_inputs(1, 5, 6000))
        self.assertEqual(load_rules()["combat"]["dimensions"][0], "strength")  # CEE unverändert verfügbar


if __name__ == "__main__":
    unittest.main()
