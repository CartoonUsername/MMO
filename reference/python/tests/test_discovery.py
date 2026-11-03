import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.discovery import (DiscoveryEngine, discovery_progress, known_discoveries, requirements_missing,
                               validate_discovery_rules)
from mmo_cee.errors import CEEError
from mmo_cee.history import EventLog
from mmo_cee.rules import Rules, load_rules

from .helpers import attune

RULES = load_rules("rules_v5.json")
DISC = RULES["discovery"]["discoveries"]
EVID, MADE, LEARNED = "discovery.evidence_gathered", "discovery.made", "discovery.learned"


def make(svc, cid="p", kind="player", xp=10000):
    svc.create(cid, kind)
    svc.record(cid, "identity.xp_gained", {"amount": xp})


def gather_all(svc, cid, did):
    for e in DISC[did]["evidence"]:
        svc.record(cid, EVID, {"discovery_id": did, "evidence_id": e})


def ready_iron(svc, cid="p", kind="player"):
    make(svc, cid, kind)
    svc.record(cid, "profession.work", {"profession": "smithing", "xp": 700})  # Meisterschaft 3
    gather_all(svc, cid, "iron_folding")


class DiscoveryRulesTests(unittest.TestCase):
    def _bad(self, mutate):
        data = copy.deepcopy(RULES.data)
        mutate(data["discovery"])
        return Rules(data)

    def test_shipped_rules_valid_and_finite_windows(self):
        validate_discovery_rules(RULES)
        cfg = RULES["discovery"]
        for did, d in DISC.items():
            w = d.get("pioneer_window_days", cfg["default_pioneer_window_days"])
            self.assertTrue(0 < w <= cfg["max_window_days"], did)  # kein dauerhaftes Monopol

    def test_invalid_rules_rejected(self):
        cases = {
            "fenster zu groß": lambda c: c["discoveries"]["iron_folding"].update(pioneer_window_days=999),
            "fenster 0": lambda c: c["discoveries"]["iron_folding"].update(pioneer_window_days=0),
            "default fenster zu groß": lambda c: c.update(default_pioneer_window_days=999),
            "max 0": lambda c: c.update(max_window_days=0),
            "unbekannte Art": lambda c: c["discoveries"]["iron_folding"].update(kind="magic"),
            "evidence leer": lambda c: c["discoveries"]["iron_folding"].update(evidence=[]),
            "evidence doppelt": lambda c: c["discoveries"]["iron_folding"].update(evidence=["a", "a"]),
            "evidence kein string": lambda c: c["discoveries"]["iron_folding"].update(evidence=[1]),
            "shareable kein bool": lambda c: c["discoveries"]["iron_folding"].update(shareable=1),
            "unbekannter Beruf": lambda c: c["discoveries"]["iron_folding"]["requires"].update(professions={"necromancy": 1}),
            "Meisterschaft 0": lambda c: c["discoveries"]["iron_folding"]["requires"].update(professions={"smithing": 0}),
            "unbekanntes Element": lambda c: c["discoveries"]["iron_folding"]["requires"].update(elements_attuned=["metal"]),
            "unbekannte Voraussetzung": lambda c: c["discoveries"]["iron_folding"]["requires"].update(discoveries=["ghost"]),
            "selbstbezug": lambda c: c["discoveries"]["iron_folding"]["requires"].update(discoveries=["iron_folding"]),
            "zyklus": lambda c: c["discoveries"]["old_shrine_map"]["requires"].update(discoveries=["twilight_rite"]),
            "min_level 0": lambda c: c["discoveries"]["iron_folding"]["requires"].update(min_level=0),
            "grants kein string": lambda c: c["discoveries"]["iron_folding"].update(grants={"recipes": [1]}),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                with self.assertRaises(CEEError):
                    validate_discovery_rules(self._bad(mutate))

    def test_old_rules_have_no_discovery_part(self):
        for name in ("rules_v1.json", "rules_v3.json", "rules_v4.json"):
            svc = CharacterService(rules=load_rules(name))
            st = svc.create("p", "player")
            self.assertNotIn("discovery", st.parts, name)
            with self.assertRaises(RuleViolation):
                svc.record("p", EVID, {"discovery_id": "iron_folding", "evidence_id": "forge_trial"})

    def test_state_shape(self):
        st = CharacterService(rules=RULES).create("p", "player")
        self.assertEqual(st.parts["discovery"], {"evidence": {}, "known": {}, "last_day": 0})


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)
        make(self.svc)

    def reject(self, type_, payload, cid="p"):
        n = len(self.svc.log.events(cid))
        before = copy.deepcopy(self.svc.state(cid).parts)
        with self.assertRaises(RuleViolation):
            self.svc.record(cid, type_, payload)
        self.assertEqual(len(self.svc.log.events(cid)), n)
        self.assertEqual(self.svc.state(cid).parts, before)

    def test_evidence_is_recorded_once_each(self):
        self.svc.record("p", EVID, {"discovery_id": "iron_folding", "evidence_id": "ore_sample_a"})
        self.assertEqual(self.svc.state("p").parts["discovery"]["evidence"], {"iron_folding": ["ore_sample_a"]})
        for _ in range(20):  # Wiederholen derselben Handlung bringt nichts
            self.reject(EVID, {"discovery_id": "iron_folding", "evidence_id": "ore_sample_a"})
        self.assertEqual(len(self.svc.state("p").parts["discovery"]["evidence"]["iron_folding"]), 1)

    def test_invalid_payloads(self):
        self.reject(EVID, {"discovery_id": "ghost", "evidence_id": "x"})
        self.reject(EVID, {"discovery_id": "iron_folding", "evidence_id": "frost_lily"})  # Beweis einer anderen Entdeckung
        self.reject(EVID, {"discovery_id": "iron_folding"})
        self.reject(EVID, {"evidence_id": "ore_sample_a"})
        self.reject(EVID, {"discovery_id": 1, "evidence_id": "ore_sample_a"})
        self.reject(EVID, {"discovery_id": "iron_folding", "evidence_id": 1})
        self.reject(EVID, {"discovery_id": ["iron_folding"], "evidence_id": "ore_sample_a"})
        self.reject(EVID, {"discovery_id": "iron_folding", "evidence_id": ["ore_sample_a"]})
        for extra in ("points", "known", "credit", "day"):
            self.reject(EVID, {"discovery_id": "iron_folding", "evidence_id": "ore_sample_a", extra: 1})

    def test_prerequisite_knowledge_gates_gathering(self):
        self.reject(EVID, {"discovery_id": "twilight_rite", "evidence_id": "dusk_altar"})  # old_shrine_map fehlt
        gather_all(self.svc, "p", "old_shrine_map")
        self.svc.record("p", MADE, {"discovery_id": "old_shrine_map", "day": 1, "credit": "pioneer"})
        self.svc.record("p", EVID, {"discovery_id": "twilight_rite", "evidence_id": "dusk_altar"})

    def test_no_evidence_for_known_discovery(self):
        ready_iron(self.svc, "q")
        self.svc.record("q", MADE, {"discovery_id": "iron_folding", "day": 1, "credit": "pioneer"})
        self.reject(EVID, {"discovery_id": "iron_folding", "evidence_id": "ore_sample_a"}, cid="q")

    def test_event_before_creation(self):
        with self.assertRaises(RuleViolation):
            self.svc.record("ghost", EVID, {"discovery_id": "iron_folding", "evidence_id": "ore_sample_a"})


class MadeLearnedTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService(rules=RULES)

    def reject(self, type_, payload, cid="p"):
        n = len(self.svc.log.events(cid))
        before = copy.deepcopy(self.svc.state(cid).parts)
        with self.assertRaises(RuleViolation):
            self.svc.record(cid, type_, payload)
        self.assertEqual(len(self.svc.log.events(cid)), n)
        self.assertEqual(self.svc.state(cid).parts, before)

    def test_made_needs_all_evidence(self):
        make(self.svc)
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 700})
        for e in DISC["iron_folding"]["evidence"][:-1]:
            self.svc.record("p", EVID, {"discovery_id": "iron_folding", "evidence_id": e})
        self.reject(MADE, {"discovery_id": "iron_folding", "day": 1, "credit": "pioneer"})

    def test_made_needs_requirements(self):
        make(self.svc)  # Schmieden-Meisterschaft fehlt
        gather_all(self.svc, "p", "iron_folding")
        self.reject(MADE, {"discovery_id": "iron_folding", "day": 1, "credit": "pioneer"})
        self.assertEqual(requirements_missing(self.svc.state("p"), RULES, DISC["iron_folding"]["requires"]), ["profession:smithing>=3"])
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 700})
        self.svc.record("p", MADE, {"discovery_id": "iron_folding", "day": 1, "credit": "pioneer"})

    def test_made_records_credit_and_day(self):
        ready_iron(self.svc)
        ev = self.svc.record("p", MADE, {"discovery_id": "iron_folding", "day": 3, "credit": "pioneer"})
        self.assertEqual(self.svc.state("p").parts["discovery"]["known"]["iron_folding"],
                         {"how": "researched", "credit": "pioneer", "day": 3, "seq": ev.seq})
        self.assertEqual(self.svc.state("p").parts["discovery"]["last_day"], 3)
        self.assertEqual(known_discoveries(self.svc.state("p")), ["iron_folding"])

    def test_made_invalid_payloads(self):
        ready_iron(self.svc)
        for pl in ({"discovery_id": "iron_folding", "day": 1, "credit": "learner"},
                   {"discovery_id": "iron_folding", "day": 1, "credit": "king"},
                   {"discovery_id": "iron_folding", "day": 1},
                   {"discovery_id": "iron_folding", "day": -1, "credit": "pioneer"},
                   {"discovery_id": "iron_folding", "day": 1.5, "credit": "pioneer"},
                   {"discovery_id": "iron_folding", "day": True, "credit": "pioneer"},
                   {"discovery_id": "ghost", "day": 1, "credit": "pioneer"},
                   {"discovery_id": "iron_folding", "day": 1, "credit": "pioneer", "points": 5}):
            with self.subTest(pl=pl):
                self.reject(MADE, pl)

    def test_cannot_make_twice_and_day_monotonic(self):
        ready_iron(self.svc)
        self.svc.record("p", MADE, {"discovery_id": "iron_folding", "day": 5, "credit": "pioneer"})
        self.reject(MADE, {"discovery_id": "iron_folding", "day": 5, "credit": "pioneer"})
        gather_all(self.svc, "p", "old_shrine_map")
        self.reject(MADE, {"discovery_id": "old_shrine_map", "day": 4, "credit": "discoverer"})  # Tag zurück
        self.svc.record("p", MADE, {"discovery_id": "old_shrine_map", "day": 5, "credit": "discoverer"})

    def test_learned_rules(self):
        make(self.svc)
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 700})
        self.svc.record("p", LEARNED, {"discovery_id": "iron_folding", "day": 2, "from_character": "teacher"})
        k = self.svc.state("p").parts["discovery"]["known"]["iron_folding"]
        self.assertEqual((k["how"], k["credit"], k["from"], k["day"]), ("learned", "learner", "teacher", 2))
        self.reject(LEARNED, {"discovery_id": "iron_folding", "day": 2, "from_character": "teacher"})  # schon bekannt

    def test_learned_needs_shareable_requirements_and_other_teacher(self):
        make(self.svc)
        self.reject(LEARNED, {"discovery_id": "iron_folding", "day": 1, "from_character": "t"})  # Beruf fehlt
        self.reject(LEARNED, {"discovery_id": "twilight_rite", "day": 1, "from_character": "t"})  # nicht teilbar
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 700})
        self.reject(LEARNED, {"discovery_id": "iron_folding", "day": 1, "from_character": "p"})  # sich selbst
        for bad in ("", 5, None):
            self.reject(LEARNED, {"discovery_id": "iron_folding", "day": 1, "from_character": bad})
        for extra in ("credit", "points"):
            self.reject(LEARNED, {"discovery_id": "iron_folding", "day": 1, "from_character": "t", extra: 1})

    def test_non_shareable_is_rejected_independent_of_requirements(self):
        data = copy.deepcopy(RULES.data)
        data["discovery"]["discoveries"]["old_shrine_map"]["shareable"] = False  # sonst voraussetzungsfrei
        svc = CharacterService(rules=Rules(data))
        make(svc)
        with self.assertRaises(RuleViolation):
            svc.record("p", LEARNED, {"discovery_id": "old_shrine_map", "day": 1, "from_character": "t"})
        data["discovery"]["discoveries"]["old_shrine_map"]["shareable"] = True
        svc2 = CharacterService(rules=Rules(data))
        make(svc2)
        svc2.record("p", LEARNED, {"discovery_id": "old_shrine_map", "day": 1, "from_character": "t"})  # gleiche Lage, teilbar: ok

    def test_learned_does_not_need_evidence(self):
        make(self.svc)
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 700})
        self.assertEqual(discovery_progress(self.svc.state("p"), RULES, "iron_folding")["evidence"], [])
        self.svc.record("p", LEARNED, {"discovery_id": "iron_folding", "day": 1, "from_character": "t"})

    def test_progress_view(self):
        make(self.svc)
        p0 = self.svc.discovery_progress("p", "iron_folding")
        self.assertEqual((p0["ready"], p0["evidence_needed"], len(p0["evidence_missing"])), (False, 3, 3))
        gather_all(self.svc, "p", "iron_folding")
        p1 = self.svc.discovery_progress("p", "iron_folding")
        self.assertEqual((p1["ready"], p1["missing_requirements"]), (False, ["profession:smithing>=3"]))
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 700})
        self.assertTrue(self.svc.discovery_progress("p", "iron_folding")["ready"])
        self.svc.record("p", MADE, {"discovery_id": "iron_folding", "day": 1, "credit": "pioneer"})
        self.assertFalse(self.svc.discovery_progress("p", "iron_folding")["ready"])  # schon bekannt

    def test_all_requirement_kinds(self):
        make(self.svc, xp=36100)
        st = self.svc.state("p")
        self.assertEqual(requirements_missing(st, RULES, DISC["twilight_rite"]["requires"]),
                         ["attuned:light", "attuned:shadow", "discovery:old_shrine_map"])
        self.assertEqual(requirements_missing(st, RULES, DISC["windrider_glider"]["requires"]),
                         ["profession:engineering>=2", "profession:research>=3"])
        make(self.svc, "low", xp=100)
        self.assertEqual(requirements_missing(self.svc.state("low"), RULES, DISC["windrider_glider"]["requires"])[0], "level>=15")

    def test_npc_replay_and_roundtrip(self):
        ready_iron(self.svc, "n", kind="npc")
        self.svc.record("n", MADE, {"discovery_id": "iron_folding", "day": 2, "credit": "pioneer"})
        live = copy.deepcopy(self.svc.state("n").parts)
        self.assertEqual(self.svc.rebuild("n").parts, live)
        svc2 = CharacterService(rules=RULES, log=EventLog.from_json("n", self.svc.log.to_json("n")))
        self.assertEqual(svc2.state("n").parts, live)
        self.assertEqual(live["identity"]["kind"], "npc")

    def test_unknown_event_type(self):
        make(self.svc)
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "discovery.grant_all", {})


class EngineConstructionTests(unittest.TestCase):
    def test_engine_validates_rules_on_construction(self):
        data = copy.deepcopy(RULES.data)
        data["discovery"]["discoveries"]["iron_folding"]["evidence"] = []
        with self.assertRaises(CEEError):
            DiscoveryEngine(Rules(data))


if __name__ == "__main__":
    unittest.main()
