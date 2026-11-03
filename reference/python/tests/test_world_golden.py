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
            "market_rules_hash": lambda v: v.update(market_rules_sha256="0" * 64),
            "trade_rules_hash": lambda v: v.update(trade_rules_sha256="0" * 64),
            "production_rules_hash": lambda v: v.update(production_rules_sha256="0" * 64),
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
        self.assertEqual(set(OPS) - used_err, {"cee_create", "day"})

    def test_errors_are_known_classes_and_carry_no_texts(self):
        classes = {s["error"] for s in self.steps if s["expect"] == "error"}
        self.assertEqual(classes, {"WorldError", "RuleViolation", "PersistenceError"})
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
        a) eine bereits vergebene ID (Herstellung, Handel, Order) wird nicht wiederverwendet (nur der Zähler steigt),
        b) eine Abstimmung nach Fristende setzt den Antrag auf 'expired'."""
        for sc in self.vec["scenarios"]:
            env = golden.Env(sc.get("cee_rules_file", self.vec["cee_rules_file"]))
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
                for key in ("trade", "craft"):  # vergebene IDs werden nie wiederverwendet: Zähler steigen, sinken nie
                    self.assertGreaterEqual(after["counters"][key], before["counters"][key])
                    before["counters"][key] = after["counters"][key] = 0
                if "exchange" in before or "exchange" in after:
                    self.assertGreaterEqual(after["exchange"]["counter"], before["exchange"]["counter"])
                    for snap in (before, after):
                        snap["exchange"] = {**snap["exchange"], "counter": 0}
                self.assertEqual(after, before, (sc["name"], i, s["op"]))
        expired = [s for sc in self.vec["scenarios"] for s in sc["steps"] if s["op"] == "vote" and s["expect"] == "error"]
        self.assertTrue(expired)

    def test_coin_conservation_in_every_scenario(self):
        for sc in self.vec["scenarios"]:
            minted = sum(s["qty"] for s in sc["steps"] if s["op"] == "deposit" and s["key"] == COIN and s["expect"] == "ok")
            minted += sum(s["amount"] for s in sc["steps"] if s["op"] == "revenue" and s["expect"] == "ok")  # Münzquelle: Umsatz
            minted += sum(s["result"] for s in sc["steps"] if s["op"] == "prod_sell" and s["expect"] == "ok")  # Münzquelle 3: NPC-Abnehmer
            minted += sum(s["result"]["price"] for s in sc["steps"] if s["op"] == "maker_sell" and s["expect"] == "ok")  # Münzquelle 4: NPC-Händler
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

    def test_market_scenarios_cover_the_exchange(self):
        steps = self.by_name["market_orderbook"]["steps"]
        places = [s for s in steps if s["op"] == "market_place" and s["expect"] == "ok"]
        fills = [f for s in places for f in s["result"]["fills"]]
        self.assertTrue(any(s["result"]["order_id"] is None and s["result"]["remaining"] > 0 for s in places))  # IOC-Rest
        self.assertTrue(any(s["result"]["order_id"] and s["result"]["fills"] for s in places))  # Teilausführung mit Rest im Buch
        self.assertGreaterEqual(len({f["unit_price"] for f in fills}), 4)
        self.assertTrue(all(f["total"] == f["unit_price"] * f["quantity"] and f["fee"] == f["total"] * 20 // 1000 for f in fills))
        fin = self.by_name["market_orderbook"]["final"]
        self.assertEqual(set(fin["exchange"]["stats"]), {"iron_blade@fine", "iron_blade@common"})
        self.assertEqual(fin["inventory"]["world:sink"][COIN], sum(f["fee"] for f in fills))
        rnd = self.by_name["random_market_3"]["steps"]
        self.assertGreaterEqual(sum(1 for s in rnd if s["op"] == "market_place" and s["expect"] == "ok" and s["result"]["fills"]), 15)
        self.assertTrue(any(s["op"] == "market_cancel" and s["expect"] == "ok" for s in rnd))
        self.assertTrue(any(s["op"] == "market_expire" and s["result"] for s in rnd if s["expect"] == "ok"))

    def test_production_scenario_covers_lines_stalls_sales_and_closing(self):
        sc = self.by_name["company_production"]
        steps = sc["steps"]
        started = [s for s in steps if s["op"] == "prod_start" and s["expect"] == "ok"]
        self.assertEqual([s["result"] for s in started], [f"srv1-job-{i:08d}" for i in range(1, 6)])
        done = [e for s in steps if s["op"] == "advance_day" and s["expect"] == "ok" for e in s["result"] if e["kind"] == "production_done"]
        self.assertGreaterEqual(len(done), 2)
        sales = [s["result"] for s in steps if s["op"] == "prod_sell" and s["expect"] == "ok"]
        self.assertEqual(sales, [240, 1728, 216])
        cancel = next(s for s in steps if s["op"] == "prod_cancel" and s["expect"] == "ok")
        self.assertEqual(cancel["result"], {"charcoal@standard": 10, "iron_ingot@standard": 20})
        fin = sc["final"]
        self.assertEqual(fin["production"]["jobs"], {})  # Schließung beendet alle Aufträge
        self.assertEqual([k for k in fin["inventory"] if k.startswith("production:")], [])
        self.assertTrue(fin["inventory"]["boss"]["iron_ore@standard"] > 0)  # Ware zurück an den Gründer
        log = [l["kind"] for l in fin["companies"]["companies"][golden.co(2)]["log"]]
        self.assertIn("production_started", log)

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
