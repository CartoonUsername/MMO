import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from mmo_cee.errors import IntegrityError
from mmo_cee.history import _canonical
from mmo_world import golden, persistence
from mmo_world.persistence import (MIGRATIONS, PersistenceError, Store, check_consistency, export_world, import_world,
                                   migrate_envelope)
from mmo_world.world import World

VEC = json.loads((Path(__file__).resolve().parents[2] / "golden_world" / "world_scenarios.json").read_text(encoding="utf-8"))
SCEN = {s["name"]: s for s in VEC["scenarios"]}


def rules_of(sc):
    return sc.get("cee_rules_file", VEC["cee_rules_file"])


def play(script, upto=None, rules=None):
    env = golden.Env(rules or VEC["cee_rules_file"])
    for op in script[:upto]:
        golden.execute(env, golden.strip_result(op))
    return env


def over_json(env):
    """Export -> JSON-Text -> zurück: so wie es auf der Platte läge."""
    e, logs = export_world(env)
    return json.loads(json.dumps(e)), json.loads(json.dumps(logs))


def resume(world, saved, rules=None):
    """Setzt die Skriptausführung auf einer geladenen Welt fort (Platzhalter bleiben erhalten)."""
    env = golden.Env(rules or VEC["cee_rules_file"])
    env.__dict__.update(world.__dict__)
    env.saved = dict(saved)
    return env


def small_world():
    return play(SCEN["company_governance"]["steps"])


class RoundtripTests(unittest.TestCase):
    def test_every_scenario_roundtrips_exactly(self):
        for name, sc in SCEN.items():
            with self.subTest(name):
                env = play(sc["steps"], rules=rules_of(sc))
                loaded = import_world(*over_json(env))
                self.assertEqual(loaded.snapshot(), env.snapshot())
                self.assertEqual(loaded.snapshot(), sc["final"])
                self.assertEqual(check_consistency(env), [])

    def test_resume_at_many_cut_points_reproduces_the_golden_steps(self):
        """Speichern + Laden mitten im Ablauf ändert nichts: jeder weitere Schritt liefert Ergebnis und Welt-Hash des Vektors."""
        for name in ("world_crafting", "world_discovery", "company_lifecycle", "company_governance", "company_poach_close",
                     "company_production", "market_orderbook", "price_dynamics"):
            steps = SCEN[name]["steps"]
            for cut in range(1, len(steps), 9):
                with self.subTest(name=name, cut=cut):
                    env = play(steps, cut, rules_of(SCEN[name]))
                    world = import_world(*over_json(env))
                    cont = resume(world, env.saved, rules_of(SCEN[name]))
                    for st in steps[cut:]:
                        out = golden.execute(cont, golden.strip_result(st))
                        snap = cont.snapshot()
                        self.assertEqual({**golden.strip_result(st), **out, "world_sha256": persistence._sha(snap)}, st)

    def test_loaded_world_keeps_counters_and_ids(self):
        env = play(SCEN["world_crafting"]["steps"])
        world = import_world(*over_json(env))
        self.assertEqual(world.crafting._counter, env.crafting._counter)
        self.assertGreater(world.crafting._counter, 0)
        env2 = play(SCEN["company_governance"]["steps"])
        w2 = import_world(*over_json(env2))
        self.assertEqual(w2.company_registry._counters, env2.company_registry._counters)
        self.assertEqual(w2.trading._counter, env2.trading._counter)

    def test_envelope_is_deterministic_and_independent_of_object_identity(self):
        a, b = export_world(small_world()), export_world(small_world())
        self.assertEqual(_canonical(a[0]), _canonical(b[0]))
        self.assertEqual(a[1], b[1])


class TamperTests(unittest.TestCase):
    def setUp(self):
        self.env = small_world()
        self.e, self.logs = over_json(self.env)

    def fails(self, e=None, logs=None):
        with self.assertRaises(PersistenceError):
            import_world(self.e if e is None else e, self.logs if logs is None else logs)

    def test_untouched_loads(self):
        import_world(self.e, self.logs)

    def test_snapshot_changed_without_hash(self):
        e = copy.deepcopy(self.e)
        e["world"]["inventory"]["boss"]["coin@gold"] += 1
        self.fails(e)

    def test_character_state_hash_changed(self):
        e = copy.deepcopy(self.e)
        e["world"]["characters"]["climb"] = "0" * 64
        e["world_sha256"] = persistence._sha(e["world"])  # selbst mit passendem Hash: Historie widerspricht
        self.fails(e)

    def test_log_event_payload_changed(self):
        logs = copy.deepcopy(self.logs)
        logs["climb"][3]["payload"] = {"amount": 1}
        self.fails(logs=logs)

    def test_log_truncated_or_extended(self):
        logs = copy.deepcopy(self.logs)
        logs["climb"].pop()
        self.fails(logs=logs)
        logs = copy.deepcopy(self.logs)
        logs["climb"].append(copy.deepcopy(logs["climb"][-1]))
        self.fails(logs=logs)

    def test_logs_swapped_missing_or_extra(self):
        logs = copy.deepcopy(self.logs)
        logs["boss"], logs["climb"] = logs["climb"], logs["boss"]
        self.fails(logs=logs)
        logs = copy.deepcopy(self.logs)
        del logs["inv"]
        self.fails(logs=logs)
        logs = copy.deepcopy(self.logs)
        logs["stranger"] = logs["inv"]
        self.fails(logs=logs)

    def test_consistently_swapped_logs_and_heads_are_still_rejected(self):
        logs, e = copy.deepcopy(self.logs), copy.deepcopy(self.e)
        logs["boss"], logs["climb"] = logs["climb"], logs["boss"]
        e["log_heads"]["boss"], e["log_heads"]["climb"] = e["log_heads"]["climb"], e["log_heads"]["boss"]
        self.fails(e, logs)
        # nur die Besitzprüfung der Ereignisse: gleiche Länge/Kopf, aber fremde Figur-ID im Ereignis
        from mmo_world import persistence as p
        with self.assertRaisesRegex(PersistenceError, "fremde Ereignisse"):
            p._import(e, logs)

    def test_log_head_reference_changed(self):
        e = copy.deepcopy(self.e)
        e["log_heads"]["boss"]["head"] = "1" * 64
        self.fails(e)

    def test_rules_hashes(self):
        for key in ("cee_sha256", "company_sha256", "market_sha256", "production_sha256"):
            with self.subTest(key):
                e = copy.deepcopy(self.e)
                e["rules"][key] = "0" * 64
                self.fails(e)

    def test_unknown_rules_file(self):
        e = copy.deepcopy(self.e)
        e["rules"]["cee_file"] = "rules_v99.json"
        self.fails(e)
        for evil in ("../data/rules_v7.json", "../../etc/passwd", "../rules_v7.json", "a/b.json", "rules_v7.json\n", "", None, 7):
            e = copy.deepcopy(self.e)
            e["rules"]["cee_file"] = evil
            self.fails(e)

    def test_structurally_broken_envelope_never_leaks_other_exceptions(self):
        for mutate in (lambda e: e.pop("world"), lambda e: e.pop("log_heads"), lambda e: e.update(rules=None),
                       lambda e: e["world"].pop("counters"), lambda e: e.update(saved_day="x")):
            e = copy.deepcopy(self.e)
            mutate(e)
            self.fails(e)
        for junk in (None, 5, [], {}, {"kind": "x"}):
            with self.assertRaises(PersistenceError):
                import_world(junk, self.logs)

    def test_inventory_edit_with_valid_hash_is_the_documented_blind_spot(self):
        """Das Inventar hat kein Log: eine stimmige Änderung (Hash neu berechnet) ist am Snapshot allein nicht erkennbar –
        Schutz dafür gehört in den Speicher (Transaktion, Zugriffsrechte, Signatur), siehe ADR-0014."""
        e = copy.deepcopy(self.e)
        e["world"]["inventory"]["boss"]["coin@gold"] += 1
        e["world_sha256"] = persistence._sha(e["world"])
        import_world(e, self.logs)

    def test_cross_layer_inconsistencies_are_caught_even_with_valid_hashes(self):
        def fix(e):
            e["world_sha256"] = persistence._sha(e["world"])

        e = copy.deepcopy(self.e)
        del e["world"]["companies"]["employer"]["climb"]  # Anstellung ohne Arbeitgeberindex
        fix(e)
        self.fails(e)
        e = copy.deepcopy(self.e)
        e["world"]["companies"]["companies"]["srv1-co-00000001"]["open"] = False  # CEE des Gründers sagt: offen
        fix(e)
        self.fails(e)
        e = copy.deepcopy(self.e)
        e["world"]["discovery"]["records"]["iron_folding"]["holders"]["boss"] = {"day": 1}  # CEE kennt es nicht
        fix(e)
        self.fails(e)
        e = copy.deepcopy(self.e)
        e["world"]["companies"]["companies"]["srv1-co-00000001"]["shares"]["boss"] += 1  # Anteilssumme
        fix(e)
        self.fails(e)

    def test_adopt_rejects_broken_chain_and_leaves_log_unchanged(self):
        from mmo_cee.history import Event, EventLog
        log = EventLog()
        rows = copy.deepcopy(self.logs["inv"])
        rows[1]["payload"] = {"amount": 5}
        with self.assertRaises(IntegrityError):
            log.adopt("inv", [Event(**r) for r in rows])
        self.assertFalse(log.has("inv"))
        log.adopt("inv", [Event(**r) for r in self.logs["inv"]])
        with self.assertRaises(IntegrityError):
            log.adopt("inv", [Event(**r) for r in self.logs["inv"]])  # doppelt geladen


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.env = play(SCEN["world_trade_inventory"]["steps"])
        self.e, self.logs = over_json(self.env)
        self.saved_migrations = dict(MIGRATIONS)
        self.addCleanup(lambda: (MIGRATIONS.clear(), MIGRATIONS.update(self.saved_migrations)))

    def test_newer_and_foreign_formats_are_rejected(self):
        for mutate in (lambda e: e.update(format=persistence.SNAPSHOT_FORMAT + 1), lambda e: e.update(kind="other"),
                       lambda e: e.update(format="1")):
            e = copy.deepcopy(self.e)
            mutate(e)
            with self.assertRaises(PersistenceError):
                import_world(e, self.logs)

    def test_old_format_without_registered_step_is_rejected(self):
        e = copy.deepcopy(self.e)
        e["format"] = 0
        with self.assertRaises(PersistenceError):
            import_world(e, self.logs)

    def test_registered_step_upgrades_old_envelopes(self):
        old = copy.deepcopy(self.e)
        old["format"] = 0
        old["day_saved"] = old.pop("saved_day")  # angenommene frühere Feldbezeichnung

        def step0(e):
            e = dict(e)
            e["saved_day"] = e.pop("day_saved")
            e["format"] = 1
            return e

        MIGRATIONS[0] = step0
        self.assertEqual(migrate_envelope(old), self.e)
        self.assertEqual(import_world(old, self.logs).snapshot(), self.env.snapshot())
        self.assertEqual(old["format"], 0)  # Eingabe bleibt unverändert

    def test_step_must_advance_exactly_one_format(self):
        old = copy.deepcopy(self.e)
        old["format"] = 0
        MIGRATIONS[0] = lambda e: e
        with self.assertRaises(PersistenceError):
            migrate_envelope(old)

    def test_current_format_passes_untouched(self):
        self.assertEqual(migrate_envelope(self.e), self.e)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "world"
        self.store = Store(self.dir)
        self.steps = SCEN["company_lifecycle"]["steps"]
        self.env = play(self.steps, 40)

    def test_commit_load_and_generations(self):
        self.assertEqual((self.store.generations(), self.store.current()), ([], None))
        with self.assertRaises(PersistenceError):
            self.store.load()
        self.assertEqual(self.store.commit(self.env), 1)
        for op in self.steps[40:50]:
            golden.execute(self.env, golden.strip_result(op))
        self.assertEqual(self.store.commit(self.env), 2)
        self.assertEqual((self.store.generations(), self.store.current()), ([1, 2], 2))
        self.assertEqual(self.store.load().snapshot(), self.env.snapshot())
        self.assertEqual(self.store.load(1).snapshot(), play(self.steps, 40).snapshot())

    def test_files_are_stable_text(self):
        self.store.commit(self.env)
        first = {p.name: p.read_bytes() for p in (self.dir / "gen-000001").rglob("*") if p.is_file()}
        self.store.commit(self.env)
        second = {p.name: p.read_bytes() for p in (self.dir / "gen-000002").rglob("*") if p.is_file()}
        self.assertEqual(first, second)
        self.assertTrue(all(not b"\r" in v for v in first.values()))

    def test_crash_before_pointer_switch_keeps_last_good_generation(self):
        self.store.commit(self.env)
        (self.dir / ".tmp-gen-000002" / "logs").mkdir(parents=True)  # halb geschriebene Generation
        (self.dir / ".tmp-gen-000002" / "snapshot.json").write_text("{", encoding="utf-8")
        self.assertEqual(self.store.load().snapshot(), self.env.snapshot())
        self.assertEqual(self.store.commit(self.env), 2)  # Altlast wird überschrieben
        # Generation geschrieben, Zeiger noch alt (Absturz nach replace der Generation)
        os.replace(self.dir / "CURRENT", self.dir / "CURRENT.keep")
        ptr = {"generation": 1}
        (self.dir / "CURRENT").write_bytes(_canonical(ptr))
        self.assertEqual(self.store.current(), 1)

    def test_corrupted_current_generation_is_detected_and_fallback_works(self):
        self.store.commit(self.env)
        for op in self.steps[40:50]:
            golden.execute(self.env, golden.strip_result(op))
        self.store.commit(self.env)
        snap = self.dir / "gen-000002" / "snapshot.json"
        snap.write_bytes(snap.read_bytes().replace(b'"saved_day"', b'"saved_dey"', 1))
        with self.assertRaises(PersistenceError):
            self.store.load()
        n, world = self.store.load_latest_valid()
        self.assertEqual((n, world.snapshot()), (1, play(self.steps, 40).snapshot()))

    def test_pointer_binds_snapshot_bytes(self):
        self.store.commit(self.env)
        snap = self.dir / "gen-000001" / "snapshot.json"
        snap.write_bytes(snap.read_bytes() + b"\n")  # inhaltlich gleich, aber nicht mehr das Geschriebene
        with self.assertRaises(PersistenceError):
            self.store.load()
        self.store.load(1)  # explizit gewählte Generation wird nur inhaltlich geprüft

    def test_latest_valid_prefers_newest(self):
        self.store.commit(self.env)
        self.store.commit(self.env)
        self.assertEqual(self.store.load_latest_valid()[0], 2)

    def test_truncated_log_file_is_detected(self):
        self.store.commit(self.env)
        f = next((self.dir / "gen-000001" / "logs").glob("*.jsonl"))
        lines = f.read_text(encoding="utf-8").splitlines()
        f.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        with self.assertRaises(PersistenceError):
            self.store.load()
        with self.assertRaises(PersistenceError):
            self.store.load_latest_valid()

    def test_garbage_files(self):
        self.store.commit(self.env)
        (self.dir / "CURRENT").write_text("kaputt", encoding="utf-8")
        with self.assertRaises(PersistenceError):
            self.store.load()
        (self.dir / "CURRENT").write_bytes(_canonical({"generation": 9, "snapshot_sha256": "x"}))
        with self.assertRaises(PersistenceError):
            self.store.load()
        f = next((self.dir / "gen-000001" / "logs").glob("*.jsonl"))
        f.write_text("{nicht json", encoding="utf-8")
        with self.assertRaises(PersistenceError):
            self.store.load(1)

    def test_prune_keeps_current_and_newest(self):
        for _ in range(4):
            self.store.commit(self.env)
        self.assertEqual(self.store.prune(2), [1, 2])
        self.assertEqual(self.store.generations(), [3, 4])
        self.assertEqual(self.store.prune(0), [3])  # die aktuelle Generation bleibt immer
        self.assertEqual(self.store.generations(), [4])
        self.store.load()

    def test_unusual_character_ids_roundtrip(self):
        w = World()
        for cid in ("a/b", "..", "ä ö ü", "x.jsonl", "p:1"):
            w.svc.create(cid, "player")
        self.store.commit(w)
        self.assertEqual(self.store.load().snapshot(), w.snapshot())
        self.assertEqual(sorted(p.name for p in self.dir.glob("gen-000001/logs/*")), sorted(set(p.name for p in self.dir.glob("gen-000001/logs/*"))))
        self.assertTrue(all(p.parent == self.dir / "gen-000001" / "logs" for p in self.dir.glob("gen-000001/logs/*")))

    def test_loaded_world_is_fully_functional(self):
        self.store.commit(self.env)
        world = self.store.load()
        cont = resume(world, self.env.saved)
        for st in self.steps[40:]:
            out = golden.execute(cont, golden.strip_result(st))
            self.assertEqual(out["expect"], st["expect"])
        self.assertEqual(persistence._sha(cont.snapshot()), SCEN["company_lifecycle"]["final_world_sha256"])


class ConsistencyTests(unittest.TestCase):
    def test_clean_world_has_no_findings_and_breakage_is_reported(self):
        env = small_world()
        self.assertEqual(check_consistency(env), [])
        reg = env.company_registry
        del reg.employer["climb"]
        self.assertTrue(any("Arbeitgeberindex" in m for m in check_consistency(env)))
        reg.employer["climb"] = "srv1-co-00000099"
        self.assertTrue(any("ohne Anstellung" in m for m in check_consistency(env)))
        reg.employer["climb"] = "srv1-co-00000001"
        self.assertEqual(check_consistency(env), [])
        env.svc.record("climb", "economy.career_changed", {"company_id": None, "role": None, "day": env.day[0]})
        msgs = check_consistency(env)
        self.assertTrue(any("CEE sagt" in m for m in msgs), msgs)


if __name__ == "__main__":
    unittest.main()
