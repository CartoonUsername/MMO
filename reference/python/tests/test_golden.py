import copy
import json
import tempfile
import unittest
from pathlib import Path

from mmo_cee import golden

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "golden"
ENGINE_EVENT_TYPES = [
    "identity.created", "identity.class_chosen", "identity.xp_gained",
    "element.exposure", "element.attuned",
    "profession.work",
    "essence.trial_passed", "essence.adopted", "essence.decision_made",
    "discovery.evidence_gathered", "discovery.made", "discovery.learned",
    "combat.encounter_resolved",
]


def load_all():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(GOLDEN_DIR.glob("*.json"))}


def has_float(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(has_float(v) for v in x.values())
    if isinstance(x, list):
        return any(has_float(v) for v in x)
    return False


class GoldenVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = load_all()

    def test_every_scenario_has_a_committed_file_and_no_strays(self):
        self.assertEqual(set(self.vectors), set(golden.SCENARIOS))

    def test_committed_vectors_replay_without_deviation(self):
        for name, vec in self.vectors.items():
            with self.subTest(name):
                self.assertEqual(golden.verify_vector(vec), [])

    def test_committed_files_equal_regeneration_byte_for_byte(self):
        for name in golden.SCENARIOS:
            with self.subTest(name):
                text = (GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8")
                self.assertEqual(text, golden.render(golden.build_vector(name)))

    def test_generation_is_deterministic(self):
        for name in golden.SCENARIOS:
            self.assertEqual(golden.build_vector(name), golden.build_vector(name))

    def test_cli_check_passes_and_detects_changes(self):
        self.assertEqual(golden.main(["golden", "check", str(GOLDEN_DIR)]), 0)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(golden.main(["golden", "write", tmp]), 0)
            self.assertEqual(golden.main(["golden", "check", tmp]), 0)
            f = Path(tmp) / "identity_basic.json"
            f.write_text(f.read_text(encoding="utf-8").replace('"level": 50', '"level": 49'), encoding="utf-8")
            self.assertEqual(golden.main(["golden", "check", tmp]), 1)
            f.unlink()
            self.assertEqual(golden.main(["golden", "check", tmp]), 1)  # fehlende Datei

    def test_cli_usage_error(self):
        self.assertEqual(golden.main(["golden"]), 2)

    # ---- Prüfer erkennt Abweichungen ------------------------------------------------
    def _mutated(self, mutate):
        vec = copy.deepcopy(self.vectors["combat_validation"])
        mutate(vec)
        return golden.verify_vector(vec)

    def test_verifier_detects_tampering(self):
        accepted = next(i for i, s in enumerate(self.vectors["combat_validation"]["steps"]) if s["expect"] == "accepted" and s["seq"] > 0)
        rejected = next(i for i, s in enumerate(self.vectors["combat_validation"]["steps"]) if s["expect"] == "rejected")
        cases = {
            "event_hash": lambda v: v["steps"][accepted].update(event_hash="0" * 64),
            "expect": lambda v: v["steps"][rejected].update(expect="accepted"),
            "payload": lambda v: v["steps"][accepted]["payload"]["actions"].update(heavy_hit=1),
            "state_hash": lambda v: v["steps"][accepted].update(state_sha256="f" * 64),
            "final_state": lambda v: v["final_state"]["combat"]["points"].update(strength=1),
            "final_hash": lambda v: v.update(final_state_sha256="0" * 64),
            "derived": lambda v: v["derived"].update(combat_directions={"vanguard": 3}),
            "rules_sha": lambda v: v.update(rules_sha256="0" * 64),
            "format": lambda v: v.update(format=99),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                self.assertNotEqual(self._mutated(mutate), [], f"Manipulation '{label}' nicht erkannt")

    # ---- Eigenschaften der Vektoren --------------------------------------------------
    def test_every_event_type_has_accepted_and_rejected_examples(self):
        seen = {t: set() for t in ENGINE_EVENT_TYPES}
        for vec in self.vectors.values():
            for s in vec["steps"]:
                if s["type"] in seen:
                    seen[s["type"]].add(s["expect"])
        for etype, kinds in seen.items():
            with self.subTest(etype):
                self.assertEqual(kinds, {"accepted", "rejected"})

    def test_rejected_steps_leave_state_unchanged(self):
        for name, vec in self.vectors.items():
            prev = None
            for i, s in enumerate(vec["steps"]):
                if s["expect"] == "rejected":
                    self.assertEqual(s["state_sha256"], prev, f"{name} Schritt {i}")
                else:
                    prev = s["state_sha256"]

    def test_accepted_steps_form_a_contiguous_hash_chain(self):
        for name, vec in self.vectors.items():
            seqs = [s["seq"] for s in vec["steps"] if s["expect"] == "accepted"]
            self.assertEqual(seqs, list(range(len(seqs))), name)
            hashes = [s["event_hash"] for s in vec["steps"] if s["expect"] == "accepted"]
            self.assertEqual(len(set(hashes)), len(hashes), name)

    def test_states_are_integer_only_for_portability(self):
        for name, vec in self.vectors.items():
            self.assertFalse(has_float(vec["final_state"]), name)
            self.assertFalse(has_float(vec["derived"]), name)

    def test_scenarios_demonstrate_key_behaviour(self):
        umbral = self.vectors["combat_directions_umbral"]
        self.assertEqual(umbral["final_state"]["essence"]["form"], "umbral_kin")
        self.assertIn("skirmisher", umbral["derived"]["combat_directions"])
        anti = self.vectors["combat_antifarm"]
        self.assertEqual(anti["final_state"]["combat"]["points"]["strength"], 111400)  # 11400 + 2 Tage Hardcap
        self.assertEqual(self.vectors["npc_pipeline"]["final_state"]["identity"]["kind"], "npc")
        ember = self.vectors["essence_scoring_ember"]
        self.assertEqual(ember["final_state"]["essence"]["form"], "ember_kin")
        self.assertEqual(ember["derived"]["essence_scores"]["ember_kin"]["score"], 608)
        self.assertEqual(ember["derived"]["essence_profile"]["form"], "ember_kin")
        tide = self.vectors["essence_decision_path"]
        self.assertEqual(tide["final_state"]["essence"]["form"], "tide_walker")
        self.assertEqual(tide["final_state"]["essence"]["decisions"], {"ember_vow": "refuse"})
        npc = self.vectors["essence_npc_two_candidates"]
        self.assertEqual(npc["final_state"]["identity"]["kind"], "npc")
        self.assertEqual(npc["final_state"]["essence"]["form"], "stone_born")  # zweite Form wird abgelehnt
        self.assertGreaterEqual(npc["derived"]["essence_scores"]["ember_kin"]["score"], 600)
        research = self.vectors["discovery_research"]
        self.assertEqual(research["derived"]["known_discoveries"], ["frostglass_recipe", "iron_folding", "old_shrine_map"])
        known = research["final_state"]["discovery"]["known"]
        self.assertEqual((known["iron_folding"]["credit"], known["old_shrine_map"]["credit"], known["frostglass_recipe"]["credit"]),
                         ("pioneer", "discoverer", "learner"))
        self.assertEqual(known["frostglass_recipe"]["from"], "teacher-1")
        self.assertEqual(research["final_state"]["discovery"]["evidence"]["iron_folding"], ["ore_sample_a", "ore_sample_b", "forge_trial"])
        secret = self.vectors["discovery_secret_form"]
        self.assertEqual(secret["final_state"]["essence"]["form"], "twilight_kin")
        self.assertEqual(secret["derived"]["known_discoveries"], ["old_shrine_map", "twilight_rite"])
        self.assertNotIn("discovery", self.vectors["essence_scoring_ember"]["final_state"])  # v4-Vektoren ohne Entdeckungsteil
        self.assertNotIn("known_discoveries", self.vectors["essence_scoring_ember"]["derived"])
        self.assertNotIn("decisions", self.vectors["essence_path"]["final_state"]["essence"])  # Legacy-Schema unverändert
        self.assertNotIn("essence_scores", self.vectors["essence_path"]["derived"])
        self.assertEqual(self.vectors["rules_v1_without_combat"]["rules_file"], "rules_v1.json")
        self.assertNotIn("combat", self.vectors["rules_v1_without_combat"]["final_state"])

    def test_vector_hashes_match_independent_computation(self):
        import hashlib
        vec = self.vectors["identity_basic"]
        final = vec["final_state"]
        blob = json.dumps(final, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), vec["final_state_sha256"])


if __name__ == "__main__":
    unittest.main()
