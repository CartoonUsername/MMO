import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from mmo_cee.history import _canonical
from mmo_world import golden
from mmo_world.golden import COIN, OPS, strip_result

PATH = Path(__file__).resolve().parents[2] / "golden_world" / "world_scenarios.json"
NO_RESULT_OPS = {"day"}


def has_float(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(has_float(v) for v in x.values())
    if isinstance(x, list):
        return any(has_float(v) for v in x)
    return False


class WorldGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vec = json.loads(PATH.read_text(encoding="utf-8"))
        cls.by_name = {s["name"]: s for s in cls.vec["scenarios"]}
        cls.steps = [st for s in cls.vec["scenarios"] for st in s["steps"]]

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
            f = Path(tmp) / "world_scenarios.json"
            f.write_text(f.read_text(encoding="utf-8").replace('"day":8', '"day":9', 1), encoding="utf-8")
            self.assertEqual(golden.main(["g", "check", tmp]), 1)  # abweichend

    def test_tampering_is_detected(self):
        def mutated(fn):
            v = copy.deepcopy(self.vec)
            fn(v)
            return golden.verify_vector(v)

        first_trade = next(i for i, s in enumerate(self.by_name["world_trade_inventory"]["steps"]) if s["op"] == "trade" and s["expect"] == "ok")
        cases = {
            "result": lambda v: v["scenarios"][0]["steps"][first_trade]["result"].update(price=1),
            "world_hash": lambda v: v["scenarios"][0]["steps"][first_trade].update(world_sha256="0" * 64),
            "expectation": lambda v: v["scenarios"][0]["steps"][first_trade].update(expect="error", error="WorldError"),
            "op_argument": lambda v: v["scenarios"][0]["steps"][first_trade].update(qty=1),
            "final_state": lambda v: v["scenarios"][0]["final"]["counters"].update(trade=99),
            "final_hash": lambda v: v["scenarios"][0].update(final_world_sha256="f" * 64),
            "cee_rules_hash": lambda v: v.update(cee_rules_sha256="0" * 64),
            "company_rules_hash": lambda v: v.update(company_rules_sha256="0" * 64),
            "format": lambda v: v.update(format=2),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertTrue(mutated(fn), f"Manipulation {name} nicht erkannt")

    def test_every_operation_has_success_and_error_example(self):
        used_ok = {s["op"] for s in self.steps if s["expect"] == "ok"}
        used_err = {s["op"] for s in self.steps if s["expect"] == "error"}
        self.assertEqual(set(OPS) - used_ok, set())
        # Operationen ohne Fehlerfall: reine Hilfsschritte
        self.assertEqual(set(OPS) - used_err, {"cee_create", "day", "disclosure"})

    def test_errors_are_known_classes_and_carry_no_texts(self):
        classes = {s["error"] for s in self.steps if s["expect"] == "error"}
        self.assertEqual(classes, {"WorldError", "RuleViolation"})
        for s in self.steps:
            self.assertEqual(("result" in s), s["expect"] == "ok")
            self.assertEqual(("error" in s), s["expect"] == "error")

    def test_all_numbers_are_integers_only(self):
        self.assertFalse(has_float(self.vec))

    def test_world_hash_is_hash_of_canonical_snapshot_and_changes_with_state(self):
        sc = self.by_name["world_trade_inventory"]
        self.assertEqual(sc["final_world_sha256"], hashlib.sha256(_canonical(sc["final"])).hexdigest())
        hashes = [s["world_sha256"] for s in sc["steps"]]
        trade_ok = [i for i, s in enumerate(sc["steps"]) if s["op"] == "trade" and s["expect"] == "ok"]
        self.assertEqual(len(trade_ok), 2)
        for i in trade_ok:
            self.assertNotEqual(hashes[i], hashes[i - 1])
        # fehlgeschlagene Handelsschritte lassen die Welt unverändert
        for i, s in enumerate(sc["steps"]):
            if s["op"] == "trade" and s["expect"] == "error":
                self.assertEqual(hashes[i], hashes[i - 1], f"Schritt {i}")

    def test_failed_steps_leave_world_unchanged_except_documented_cases(self):
        """Abgelehnte Schritte ändern die Welt nicht - Ausnahmen (bewusst, im Vektor festgehalten):
        a) eine bereits vergebene Herstellungs-ID wird nicht wiederverwendet (nur der Zähler steigt),
        b) eine Abstimmung nach Fristende setzt den Antrag auf 'expired'."""
        for sc in self.vec["scenarios"]:
            env = golden.Env()
            for i, s in enumerate(sc["steps"]):
                before = env.snapshot()
                out = golden.execute(env, strip_result(s))
                after = env.snapshot()
                if out["expect"] != "error":
                    continue
                if s["op"] == "vote":
                    b2, a2 = copy.deepcopy(before), copy.deepcopy(after)
                    for snap in (b2, a2):
                        snap["companies"]["companies"].get(s["company"], {}).pop("proposals", None)
                    self.assertEqual(a2, b2, (sc["name"], i))
                    continue
                if s["op"] == "craft":
                    self.assertGreaterEqual(after["counters"]["craft"], before["counters"]["craft"])
                    before["counters"]["craft"] = after["counters"]["craft"] = 0
                self.assertEqual(after, before, (sc["name"], i, s["op"]))
        expired = [s for sc in self.vec["scenarios"] for s in sc["steps"] if s["op"] == "vote" and s["expect"] == "error"]
        self.assertTrue(expired)

    def test_coin_conservation_in_every_scenario(self):
        for sc in self.vec["scenarios"]:
            minted = sum(s["qty"] for s in sc["steps"] if s["op"] == "deposit" and s["key"] == COIN and s["expect"] == "ok")
            minted += sum(s["amount"] for s in sc["steps"] if s["op"] == "revenue" and s["expect"] == "ok")  # einzige Münzquelle
            held = sum(h.get(COIN, 0) for h in sc["final"]["inventory"].values())
            self.assertEqual(held, minted, sc["name"])

    def test_negative_floor_case_wage_just_below_demand(self):
        sc = self.by_name["company_lifecycle"]
        script = [strip_result(s) for s in sc["steps"]]
        cut = next(i for i, s in enumerate(script) if s["op"] == "advance_day")
        env = golden.Env()
        for op in script[:cut + 1]:
            golden.execute(env, op)
        emps = env.company_registry.get(golden.co(1))["employees"]
        w = next(e for e in emps.values() if e["wage"] == 19)
        self.assertEqual((w["goal"], w["satisfaction"] < 600), ("wage", True))
        self.assertEqual(19 * 1000 // 20, 950)  # knapp unter Bedarf

    def test_scenarios_reach_real_states(self):
        gov = self.by_name["company_governance"]["final"]["companies"]["companies"][golden.co(1)]
        self.assertIsNone(gov["ceo"])  # nach Abberufung
        kinds = [l["kind"] for l in gov["log"]]
        self.assertIn("appoint_ceo", kinds)
        self.assertIn("dismiss_ceo", kinds)
        self.assertIn("proposal_failed", kinds)  # Ausführung scheiterte an der Dienstzeit
        statuses = {p["status"] for p in gov["proposals"].values()}
        self.assertTrue({"passed", "rejected", "execution_failed", "expired"} <= statuses, statuses)
        life = self.by_name["company_lifecycle"]["final"]["companies"]["companies"][golden.co(2)]
        self.assertFalse(life["open"])
        lk = [l["kind"] for l in life["log"]]
        self.assertIn("resigned", lk)
        self.assertIn("warned", lk)
        poach = [s for s in self.by_name["company_poach_close"]["steps"] if s["op"] == "poach" and s["expect"] == "ok"]
        self.assertEqual({s["result"]["accept"] for s in poach}, {True, False})
        close = next(s for s in self.by_name["company_poach_close"]["steps"] if s["op"] == "close" and s["expect"] == "ok")
        self.assertEqual(set(close["result"]), {"boss", "inv"})
        self.assertLess(close["result"]["boss"], close["result"]["inv"])

    def test_random_scripts_are_deterministic_state_aware_and_mostly_valid(self):
        a, b = golden.random_script(4, 260), golden.random_script(4, 260)
        self.assertEqual(a, b)
        self.assertNotEqual(a, golden.random_script(5, 260))
        for name in ("random_world_4", "random_world_9"):
            steps = self.by_name[name]["steps"]
            ops = [s for s in steps if s["op"] not in ("cee_create", "cee_record", "deposit", "day")]
            share_ok = sum(s["expect"] == "ok" for s in ops) * 100 // len(ops)
            self.assertGreaterEqual(share_ok, 30, name)
            self.assertLessEqual(share_ok, 90, name)  # auch Ablehnungen kommen vor
            ok_ops = {s["op"] for s in ops if s["expect"] == "ok"}
            self.assertTrue({"found", "hire", "trade", "revenue", "advance_day", "offer_shares"} <= ok_ops, ok_ops)

    def test_rng_is_xorshift32_with_pinned_values(self):
        r = golden.Rng(1)
        self.assertEqual([r.next() for _ in range(4)], [173101455, 745838175, 1767508224, 658094749])
        self.assertEqual(r.below(10), 8)


if __name__ == "__main__":
    unittest.main()
