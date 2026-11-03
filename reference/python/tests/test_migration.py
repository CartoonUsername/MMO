import copy
import json
import tempfile
import unittest

from mmo_cee import CharacterService, IntegrityError, RuleViolation, RulesVersionMismatch
from mmo_cee.history import EventLog
from mmo_cee.migration import (MIGRATION_TYPE, STATE_MIGRATIONS, RulesChain, check_migration, migrate_parts, next_version,
                               parts_hash)
from mmo_cee.rules import Rules, available_rules, load_rules, older_rules
from mmo_world import World, WorldError, persistence
from mmo_world.persistence import PersistenceError, upgrade_world

R = {v: load_rules(f) for v, f in available_rules().items()}
COIN, FINE = "coin@gold", "iron_blade@fine"


def legacy(version, n=1):
    """Dienst unter einer alten Regelversion mit einer gespielten Figur."""
    svc = CharacterService(rules=R[version])
    svc.create("a", "player")
    svc.record("a", "identity.xp_gained", {"amount": 600})
    svc.record("a", "profession.work", {"profession": "smithing", "xp": 700})
    return svc


def newer(log, version="8"):
    return CharacterService(rules=R[version], log=log, history_rules=older_rules(R[version]))


def rebuild(events, tamper=None):
    """Baut eine Historie neu (mit gültiger Hash-Kette) und verändert dabei einzelne Ereignisse - eine geschickte Fälschung."""
    log = EventLog()
    for e in events:
        payload = copy.deepcopy(e.payload)
        if tamper:
            payload = tamper(e, payload)
        log.append(e.character_id, e.type, payload, e.rules_version)
    return log


class RulesCatalogTests(unittest.TestCase):
    def test_available_and_older(self):
        self.assertEqual(list(available_rules()), [str(i) for i in range(1, 10)])
        self.assertEqual(list(older_rules(R["8"])), [str(i) for i in range(1, 8)])
        self.assertEqual(older_rules(R["1"]), {})

    def test_fingerprint_is_stable_and_sensitive(self):
        self.assertEqual(R["7"].sha256, load_rules("rules_v7.json").sha256)
        self.assertNotEqual(R["7"].sha256, R["8"].sha256)
        data = copy.deepcopy(R["7"].data)
        data["identity"]["max_level"] += 1
        self.assertNotEqual(Rules(data).sha256, R["7"].sha256)

    def test_next_version_is_numeric_not_lexical(self):
        self.assertEqual(next_version(["9", "10", "2"], "2"), "9")
        self.assertEqual(next_version(["9", "10"], "9"), "10")
        self.assertIsNone(next_version(["9", "10"], "10"))


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.old = legacy("7")
        self.svc = newer(self.old.log)

    def test_without_history_rules_foreign_versions_are_refused(self):
        with self.assertRaises(RulesVersionMismatch):
            CharacterService(rules=R["8"], log=self.old.log).state("a")

    def test_lagging_figure_is_readable_but_frozen(self):
        st = self.svc.state("a")
        self.assertEqual((st.rules_version, self.svc.needs_migration("a"), self.svc.rules_of("a").version), ("7", True, "7"))
        self.assertEqual(self.svc.economic_profile("a")["trades"], 0)
        self.assertTrue(self.svc.known_recipes("a"))
        self.assertTrue(self.svc.appearance("a"))
        with self.assertRaisesRegex(RuleViolation, "migrieren"):
            self.svc.record("a", "identity.xp_gained", {"amount": 1})
        with self.assertRaisesRegex(RuleViolation, "migrieren"):
            self.svc.projector.validate(st, "identity.xp_gained", {"amount": 1})

    def test_migration_records_one_event_and_keeps_everything(self):
        before = copy.deepcopy(self.svc.state("a").parts)
        n = len(self.svc.log.events("a"))
        ev = self.svc.migrate("a")
        self.assertEqual((ev.type, ev.rules_version, ev.seq, len(self.svc.log.events("a"))), (MIGRATION_TYPE, "8", n, n + 1))
        self.assertEqual(ev.payload, {"from": "7", "to": "8", "state_sha256": parts_hash(before),
                                      "from_rules_sha256": R["7"].sha256, "to_rules_sha256": R["8"].sha256})
        self.assertEqual((self.svc.state("a").rules_version, self.svc.state("a").parts, self.svc.needs_migration("a")), ("8", before, False))
        self.svc.record("a", "identity.xp_gained", {"amount": 5})  # ab jetzt unter den neuen Regeln
        self.assertEqual(self.svc.log.events("a")[-1].rules_version, "8")
        self.svc.log.verify("a")

    def test_replay_from_scratch_gives_the_same_state(self):
        self.svc.migrate("a")
        self.svc.record("a", "profession.work", {"profession": "smithing", "xp": 50})
        fresh = newer(self.svc.log)
        self.assertEqual((fresh.state("a").rules_version, fresh.state("a").parts), ("8", self.svc.state("a").parts))
        again = newer(EventLog.from_json("a", self.svc.log.to_json("a")))
        self.assertEqual(again.state("a").parts, fresh.state("a").parts)

    def test_new_rules_apply_after_migration(self):
        other = legacy("7")
        other.create("b", "player")
        s = newer(other.log)
        s.migrate("a")
        s.migrate("b")
        base = {"trade_id": "t", "role": "seller", "counterparty": "b", "item_id": "iron_blade", "grade": "fine", "quantity": 2,
                "value": 360, "day": 1}
        with self.assertRaisesRegex(RuleViolation, "fehlend"):
            s.record("a", "economy.trade_completed", base)  # v8 verlangt das Feld reference
        s.record("a", "economy.trade_completed", {**base, "reference": 360})

    def test_cannot_forge_or_repeat_a_migration(self):
        with self.assertRaisesRegex(RuleViolation, "migrate"):
            self.svc.record("a", MIGRATION_TYPE, {"from": "7", "to": "8"})
        with self.assertRaises(RuleViolation):
            self.old.record("a", MIGRATION_TYPE, {"from": "7", "to": "8"})
        self.svc.migrate("a")
        with self.assertRaisesRegex(RuleViolation, "neuesten"):
            self.svc.migrate("a")
        with self.assertRaises(RuleViolation):
            self.svc.migrate("ghost")
        self.assertFalse(self.svc.needs_migration("ghost"))

    def test_forged_histories_are_detected(self):
        self.svc.migrate("a")
        self.svc.record("a", "identity.xp_gained", {"amount": 1})
        events = self.svc.log.events("a")
        mi = next(i for i, e in enumerate(events) if e.type == MIGRATION_TYPE)
        forgeries = {
            "state_hash": lambda e, p: {**p, "state_sha256": "0" * 64} if e.type == MIGRATION_TYPE else p,
            "old_rules_hash": lambda e, p: {**p, "from_rules_sha256": "0" * 64} if e.type == MIGRATION_TYPE else p,
            "new_rules_hash": lambda e, p: {**p, "to_rules_sha256": "0" * 64} if e.type == MIGRATION_TYPE else p,
            "from": lambda e, p: {**p, "from": "6"} if e.type == MIGRATION_TYPE else p,
            "to": lambda e, p: {**p, "to": "9"} if e.type == MIGRATION_TYPE else p,
            "extra_key": lambda e, p: {**p, "bonus": 1} if e.type == MIGRATION_TYPE else p,
            "history_before": lambda e, p: {**p, "amount": 1} if e.seq == 1 else p,  # Zustand davor weicht ab
        }
        for name, fn in forgeries.items():
            with self.subTest(name):
                with self.assertRaises(IntegrityError):
                    newer(rebuild(events, fn)).state("a")
        # Migration ohne Erstellung (Seq 0) und Ereignisse nach der Migration unter der alten Version
        log = EventLog()
        log.append("a", MIGRATION_TYPE, events[mi].payload, "8")
        with self.assertRaises(IntegrityError):
            newer(log).state("a")
        log = EventLog()
        for e in events[:mi]:
            log.append("a", e.type, e.payload, e.rules_version)
        log.append("a", MIGRATION_TYPE, events[mi].payload, "8")
        log.append("a", "identity.xp_gained", {"amount": 1}, "7")
        with self.assertRaises(RulesVersionMismatch):
            newer(log).state("a")
        log = EventLog()
        for e in events[:mi]:
            log.append("a", e.type, e.payload, e.rules_version)
        log.append("a", MIGRATION_TYPE, events[mi].payload, "9")  # Ereignis-Regelversion weicht von payload.to ab
        with self.assertRaises((RulesVersionMismatch, IntegrityError)):
            newer(log).state("a")


class LegacyViewTests(unittest.TestCase):
    def test_views_of_lagging_figures_use_their_own_rules(self):
        old = CharacterService(rules=R["3"])
        old.create("a", "player")
        old.record("a", "identity.xp_gained", {"amount": 300})
        svc = newer(old.log)
        self.assertEqual(svc.state("a").rules_version, "3")
        self.assertEqual(svc.essence_scores("a"), {})  # v3 kennt keine Bewertungsformen; unter v8-Regeln wäre das ein Fehler
        self.assertEqual(svc.essence_profile("a")["form"], "human")
        self.assertEqual(svc.combat_directions("a"), {})
        while svc.needs_migration("a"):
            svc.migrate("a")
        self.assertTrue(svc.essence_scores("a"))


class ForgedStartTests(unittest.TestCase):
    def test_migration_before_creation_is_refused_even_with_a_matching_hash(self):
        from mmo_cee.migration import migration_payload
        svc = newer(EventLog())
        fresh = svc.chain.projectors["7"].new_state("a")
        log = EventLog()
        log.append("a", MIGRATION_TYPE, migration_payload(fresh, R["7"], R["8"]), "8")
        with self.assertRaisesRegex(IntegrityError, "vor der Erstellung"):
            newer(log).state("a")


class ChainTests(unittest.TestCase):
    def test_stepwise_migration_over_several_versions_adds_new_engines(self):
        old = legacy("5")
        svc = newer(old.log)
        self.assertNotIn("crafting", svc.state("a").parts)
        steps = []
        while svc.needs_migration("a"):
            steps.append((svc.migrate("a").payload["from"], svc.state("a").rules_version))
        self.assertEqual(steps, [("5", "6"), ("6", "7"), ("7", "8")])
        parts = svc.state("a").parts
        self.assertTrue({"crafting", "economy"} <= set(parts))
        self.assertEqual(parts["economy"]["points"], {"volume": 0, "network": 0})
        self.assertEqual(parts["profession"]["xp"]["smithing"], 700)  # Fortschritt bleibt
        self.assertEqual(newer(svc.log).state("a").parts, parts)
        self.assertEqual([e.rules_version for e in svc.log.events("a")][-3:], ["6", "7", "8"])

    def test_registered_state_step_is_applied_and_fingerprinted(self):
        old = legacy("7")
        svc = newer(old.log)

        def step(parts):
            parts["identity"]["note"] = "migriert"
            return parts

        STATE_MIGRATIONS[("7", "8")] = step
        self.addCleanup(STATE_MIGRATIONS.pop, ("7", "8"), None)
        svc.migrate("a")
        self.assertEqual(svc.state("a").parts["identity"]["note"], "migriert")
        self.assertEqual(newer(svc.log).state("a").parts["identity"]["note"], "migriert")

    def test_migration_may_never_drop_state(self):
        old = legacy("7")
        data = copy.deepcopy(R["8"].data)
        data["version"] = "9"
        del data["economy"]  # v9 ohne Wirtschaft würde Fortschritt entfernen
        r9 = Rules(data)
        svc = CharacterService(rules=r9, log=old.log, history_rules=older_rules(R["8"]) | {"8": R["8"]})
        # erst auf 8 (Dienst mit v8 als aktueller Version), dann der Versuch auf das verlustbehaftete v9
        mid = newer(old.log)
        mid.migrate("a")
        svc = CharacterService(rules=r9, log=old.log, history_rules=older_rules(R["8"]) | {"8": R["8"]})
        with self.assertRaisesRegex(RuleViolation, "entfernen"):
            svc.migrate("a")
        self.assertEqual(svc.state("a").rules_version, "8")
        self.assertEqual(len(old.log.events("a")), len(mid.log.events("a")))  # nichts wurde geschrieben

    def test_migrate_parts_is_a_pure_copy(self):
        svc = newer(legacy("7").log)
        st = svc.state("a")
        before = copy.deepcopy(st.parts)
        out = migrate_parts(svc.chain.projectors["7"], svc.chain.projectors["8"], st.parts, "7", "8")
        out["identity"]["kind"] = "x"
        self.assertEqual(st.parts, before)

    def test_check_migration_rejects_wrong_start_and_step(self):
        svc = newer(legacy("7").log)
        st = svc.state("a")
        from mmo_cee.migration import migration_payload
        good = migration_payload(st, R["7"], R["8"])
        check_migration(st, good, R["7"], R["8"], ["7", "8"])
        data = copy.deepcopy(R["8"].data)
        data["version"] = "9"
        r9 = Rules(data)
        with self.assertRaisesRegex(RuleViolation, "eine Stufe"):  # 8 liegt dazwischen
            check_migration(st, migration_payload(st, R["7"], r9), R["7"], r9, ["7", "8", "9"])
        with self.assertRaises(RuleViolation):
            check_migration(st, {**good, "from": "6"}, R["7"], R["8"], ["7", "8"])

    def test_empty_history_uses_current_rules(self):
        svc = newer(EventLog())
        self.assertEqual(svc.state("nobody").rules_version, "8")
        self.assertIsInstance(svc.chain, RulesChain)


class WorldMigrationTests(unittest.TestCase):
    def build(self):
        w = World()  # CEE v7
        for c in "abc":
            w.svc.create(c, "player")
            w.svc.record(c, "identity.xp_gained", {"amount": 10000})
            w.svc.record(c, "profession.work", {"profession": "trade", "xp": 700})
            w.inv.deposit(c, COIN, 10000)
            w.inv.deposit(c, FINE, 20)
        w.trading.trade("a", "b", FINE, 2, 360)
        w.company.found("a", 2000)
        w.exchange.place("c", "sell", FINE, 3, 190)
        return w

    def test_upgrade_keeps_state_and_leaves_source_untouched(self):
        w = self.build()
        snap, nlogs = w.snapshot(), {c: len(w.svc.log.events(c)) for c in "abc"}
        new = upgrade_world(w, "rules_v8.json")
        self.assertEqual(w.snapshot(), snap)
        self.assertEqual({c: len(w.svc.log.events(c)) for c in "abc"}, nlogs)
        self.assertEqual(new.svc.rules.version, "8")
        self.assertIsNotNone(new.pricing)
        for c in "abc":
            self.assertEqual((new.svc.state(c).rules_version, len(new.svc.log.events(c))), ("8", nlogs[c] + 1))
        a, b = new.snapshot(), snap
        self.assertEqual(a["inventory"], b["inventory"])
        self.assertEqual(a["companies"], b["companies"])
        self.assertEqual(a["exchange"], b["exchange"])
        self.assertEqual(a["characters"], b["characters"])  # Teilzustände unverändert
        r = new.trading.trade("b", "a", FINE, 1, 180)
        self.assertEqual(r.reference, 180)
        self.assertEqual(new.svc.log.events("b")[-1].payload["reference"], 180)

    def test_partial_upgrade_leaves_laggards_out_of_world_actions(self):
        new = upgrade_world(self.build(), "rules_v8.json", ["a", "b"])
        self.assertTrue(new.svc.needs_migration("c"))
        new.inv.deposit("c", "iron_ore@standard", 5)
        before = new.inv.to_json()
        with self.assertRaises(RuleViolation):
            new.trading.trade("a", "c", FINE, 1, 180)
        with self.assertRaises(RuleViolation):
            new.pricing.sell_to_maker("c", "iron_ore@standard", 1)
        with self.assertRaises(WorldError):
            new.company.hire("a", "srv1-co-00000001", "c", 40)
        self.assertEqual(new.inv.to_json(), before)
        new.svc.migrate("c")
        new.trading.trade("a", "c", FINE, 1, 180)

    def test_mixed_world_survives_save_and_load(self):
        new = upgrade_world(self.build(), "rules_v8.json", ["a"])
        e, logs = persistence.export_world(new)
        loaded = persistence.import_world(json.loads(json.dumps(e)), json.loads(json.dumps(logs)))
        self.assertEqual(loaded.snapshot(), new.snapshot())
        self.assertEqual([c for c in "abc" if loaded.svc.needs_migration(c)], ["b", "c"])
        with tempfile.TemporaryDirectory() as d:
            s = persistence.Store(d)
            s.commit(new)
            self.assertEqual(s.load().snapshot(), new.snapshot())
        for x in (new, loaded):
            x.svc.migrate("b")
        self.assertEqual(loaded.snapshot(), new.snapshot())

    def test_failed_upgrades_create_nothing(self):
        w = self.build()
        for target in ("rules_v7.json", "rules_v1.json", "rules_v99.json", "../data/rules_v8.json", "rules_v8", "", None, 8):
            with self.subTest(target=target):
                with self.assertRaises(PersistenceError):
                    upgrade_world(w, target)
        up = upgrade_world(w, "rules_v8.json")
        with self.assertRaises(PersistenceError):
            upgrade_world(up, "rules_v8.json")  # schon dort

    def test_forged_migration_in_a_stored_world_is_refused(self):
        new = upgrade_world(self.build(), "rules_v8.json")
        e, logs = persistence.export_world(new)
        logs = copy.deepcopy(logs)
        row = logs["a"][-1]
        self.assertEqual(row["type"], MIGRATION_TYPE)
        forged = rebuild(new.svc.log.events("a"), lambda ev, p: {**p, "state_sha256": "0" * 64} if ev.type == MIGRATION_TYPE else p)
        logs["a"] = [{**ev.body(), "hash": ev.hash} for ev in forged.events("a")]
        e = copy.deepcopy(e)
        e["log_heads"]["a"] = {"length": len(logs["a"]), "head": logs["a"][-1]["hash"]}
        with self.assertRaises(PersistenceError):
            persistence.import_world(e, logs)

    def test_old_snapshot_is_loadable_by_the_old_rules_only_until_upgraded(self):
        w = self.build()
        e, logs = persistence.export_world(w)
        self.assertEqual(persistence.import_world(e, logs).svc.rules.version, "7")


if __name__ == "__main__":
    unittest.main()
