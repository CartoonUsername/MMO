import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.rules import Rules, load_rules
from mmo_world import DiscoveryRegistry, DiscoveryService, WorldError

from .helpers import attune
from .test_combat import EV, enc

RULES = load_rules("rules_v5.json")
DISC = RULES["discovery"]["discoveries"]


class Clock:
    def __init__(self, day=1):
        self.day = day

    def __call__(self):
        return self.day


class World:
    """Hilfsaufbau: CEE + Registry + Dienst mit steuerbarer Serverzeit."""

    def __init__(self):
        self.svc = CharacterService(rules=RULES)
        self.reg = DiscoveryRegistry(RULES)
        self.clock = Clock()
        self.ds = DiscoveryService(self.svc, self.reg, self.clock)

    def smith(self, cid, kind="player", xp=10000):
        self.svc.create(cid, kind)
        self.svc.record(cid, "identity.xp_gained", {"amount": xp})
        self.svc.record(cid, "profession.work", {"profession": "smithing", "xp": 700})

    def research(self, cid, did):
        for e in DISC[did]["evidence"]:
            self.ds.gather(cid, did, e)
        return self.ds.complete(cid, did)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.reg = DiscoveryRegistry(RULES)

    def test_first_is_pioneer_others_discoverers(self):
        self.assertEqual(self.reg.claim("a", "iron_folding", 1), "pioneer")
        self.assertEqual(self.reg.claim("b", "iron_folding", 2), "discoverer")
        self.assertEqual(self.reg.claim("c", "iron_folding", 2), "discoverer")
        self.assertEqual((self.reg.pioneer("iron_folding"), self.reg.holders("iron_folding")), ("a", ["a", "b", "c"]))

    def test_claim_validation(self):
        self.reg.claim("a", "iron_folding", 5)
        for args in (("a", "iron_folding", 6), ("b", "ghost", 6), ("b", "iron_folding", 4), ("b", "iron_folding", -1),
                     ("b", "iron_folding", 1.5), ("b", "iron_folding", True), ("b", None, 6)):
            with self.subTest(args=args):
                with self.assertRaises(WorldError):
                    self.reg.claim(*args)
        self.assertEqual(self.reg.holders("iron_folding"), ["a"])

    def test_pioneer_window_and_teaching_rights(self):
        self.reg.claim("a", "iron_folding", 10)  # Fenster 10 Tage (Regeln) -> bis Tag 20
        self.reg.claim("b", "iron_folding", 12)
        self.assertEqual(self.reg.window_end("iron_folding"), 20)
        self.assertEqual(self.reg.can_teach("a", "iron_folding", 10), (True, "ok"))
        self.assertEqual(self.reg.can_teach("a", "iron_folding", 19)[0], True)
        self.assertFalse(self.reg.can_teach("b", "iron_folding", 19)[0])  # auch unabhängiger Entdecker erst nach dem Fenster
        self.assertTrue(self.reg.can_teach("b", "iron_folding", 20)[0])  # Grenze: Tag 20 ist frei
        self.assertTrue(self.reg.can_teach("a", "iron_folding", 20)[0])

    def test_non_holders_and_non_shareable_cannot_teach(self):
        self.reg.claim("a", "iron_folding", 1)
        self.assertFalse(self.reg.can_teach("zed", "iron_folding", 99)[0])
        self.assertEqual(self.reg.can_teach("a", "iron_folding", 1), (True, "ok"))  # teilbar: Pionier darf im Fenster lehren
        self.reg.claim("a", "twilight_rite", 1)
        self.assertEqual(self.reg.can_teach("a", "twilight_rite", 9999), (False, "nicht teilbar"))  # nie lehrbar

    def test_window_lengths_come_from_rules(self):
        for did in DISC:
            self.assertEqual(self.reg.window_days(did), DISC[did].get("pioneer_window_days", RULES["discovery"]["default_pioneer_window_days"]))
        self.assertEqual((self.reg.window_days("iron_folding"), self.reg.window_days("old_shrine_map"), self.reg.window_days("windrider_glider")), (10, 7, 14))
        self.assertIsNone(self.reg.window_end("iron_folding"))  # niemand kennt sie

    def test_every_window_ends_so_nothing_is_blocked_forever(self):
        for did in DISC:
            self.reg.claim("a", did, 5)
            end = self.reg.window_end(did)
            self.assertLessEqual(end - 5, RULES["discovery"]["max_window_days"])
            self.reg.claim("b", did, 5)
            if DISC[did]["shareable"]:
                self.assertTrue(self.reg.can_teach("b", did, end)[0], did)

    def test_release_rolls_back_last_claim(self):
        self.reg.claim("a", "iron_folding", 3)
        self.reg.release("a", "iron_folding")
        self.assertEqual((self.reg.pioneer("iron_folding"), self.reg.holders("iron_folding"), self.reg.last_day), (None, [], 0))
        self.assertEqual(self.reg.claim("b", "iron_folding", 1), "pioneer")  # Pionierrolle wieder frei
        with self.assertRaises(WorldError):
            self.reg.release("a", "iron_folding")

    def test_release_only_most_recent(self):
        self.reg.claim("a", "iron_folding", 1)
        self.reg.claim("b", "iron_folding", 2)
        with self.assertRaises(WorldError):
            self.reg.release("a", "iron_folding")
        self.reg.commit()
        with self.assertRaises(WorldError):
            self.reg.release("b", "iron_folding")

    def test_persistence_roundtrip_and_determinism(self):
        for reg in (self.reg, DiscoveryRegistry(RULES)):
            reg.claim("a", "iron_folding", 1)
            reg.claim("b", "old_shrine_map", 2)
            reg.note_learned("c", "old_shrine_map", "b", 9)
        self.assertEqual(self.reg.to_json(), DiscoveryRegistry.from_json(RULES, self.reg.to_json()).to_json())
        other = DiscoveryRegistry(RULES)
        other.claim("a", "iron_folding", 1)
        other.claim("b", "old_shrine_map", 2)
        other.note_learned("c", "old_shrine_map", "b", 9)
        self.assertEqual(self.reg.to_json(), other.to_json())
        data = copy.deepcopy(RULES.data)
        data["discovery"]["discoveries"]["extra"] = copy.deepcopy(data["discovery"]["discoveries"]["iron_folding"])
        with self.assertRaises(WorldError):
            DiscoveryRegistry.from_json(Rules(data), self.reg.to_json())

    def test_note_learned_validation(self):
        self.reg.claim("a", "iron_folding", 5)
        self.reg.note_learned("b", "iron_folding", "a", 6)
        with self.assertRaises(WorldError):
            self.reg.note_learned("b", "iron_folding", "a", 7)
        with self.assertRaises(WorldError):
            self.reg.note_learned("c", "iron_folding", "a", 3)


class ServiceFlowTests(unittest.TestCase):
    def setUp(self):
        self.w = World()

    def test_pioneer_then_independent_research_is_never_blocked(self):
        w = self.w
        w.smith("a")
        w.smith("b")
        ev_a = w.research("a", "iron_folding")
        self.assertEqual(ev_a.payload["credit"], "pioneer")
        w.clock.day = 2  # mitten im Pioniervorsprung
        ev_b = w.research("b", "iron_folding")  # unabhängige Forschung bleibt möglich
        self.assertEqual(ev_b.payload["credit"], "discoverer")
        self.assertEqual(w.svc.state("b").parts["discovery"]["known"]["iron_folding"]["how"], "researched")

    def test_teaching_window_end_to_end(self):
        w = self.w
        for cid in ("a", "b", "student", "late"):
            w.smith(cid)
        w.research("a", "iron_folding")  # Tag 1 -> Pioniervorsprung bis Tag 11
        w.clock.day = 2
        w.research("b", "iron_folding")  # unabhängiger Entdecker, aber nicht Pionier
        w.clock.day = 5
        with self.assertRaisesRegex(WorldError, "Pioniervorsprung"):
            w.ds.teach("b", "student", "iron_folding")  # im Fenster darf nur der Pionier lehren
        n = len(w.svc.log.events("student"))
        w.ds.teach("a", "student", "iron_folding")
        self.assertEqual(w.svc.state("student").parts["discovery"]["known"]["iron_folding"]["credit"], "learner")
        self.assertEqual(len(w.svc.log.events("student")), n + 1)
        self.assertEqual(w.reg.holders("iron_folding"), ["a", "b", "student"])
        with self.assertRaisesRegex(WorldError, "Pioniervorsprung"):
            w.ds.teach("student", "late", "iron_folding")  # Schüler dürfen im Fenster nicht weiterlehren
        w.clock.day = 10
        with self.assertRaisesRegex(WorldError, "Pioniervorsprung"):
            w.ds.teach("b", "late", "iron_folding")  # letzter Tag des Fensters
        w.clock.day = 11
        w.ds.teach("student", "late", "iron_folding")  # Fenster vorbei: jeder Halter darf lehren
        self.assertEqual(w.svc.state("late").parts["discovery"]["known"]["iron_folding"]["from"], "student")

    def test_teaching_failures_leave_everything_unchanged(self):
        w = self.w
        w.smith("a")
        w.research("a", "iron_folding")
        w.svc.create("noskill", "player")
        snap_reg, snap_log = w.reg.to_json(), len(w.svc.log.events("noskill"))
        with self.assertRaises(WorldError):
            w.ds.teach("a", "noskill", "iron_folding")  # Schüler erfüllt Voraussetzung nicht
        with self.assertRaises(WorldError):
            w.ds.teach("a", "a", "iron_folding")
        with self.assertRaises(WorldError):
            w.ds.teach("a", "noskill", "ghost")
        self.assertEqual((w.reg.to_json(), len(w.svc.log.events("noskill"))), (snap_reg, snap_log))

    def test_inconsistent_registry_is_detected_when_teaching(self):
        w = self.w
        w.smith("ghost_teacher")
        w.smith("student")
        w.reg.claim("ghost_teacher", "iron_folding", 1)  # Registry kennt ihn als Pionier, sein Log aber nicht
        before = len(w.svc.log.events("student"))
        with self.assertRaisesRegex(WorldError, "Inkonsistenz"):
            w.ds.teach("ghost_teacher", "student", "iron_folding")
        self.assertEqual(len(w.svc.log.events("student")), before)

    def test_complete_requires_readiness_without_side_effects(self):
        w = self.w
        w.svc.create("p", "player")
        for e in DISC["iron_folding"]["evidence"]:
            w.ds.gather("p", "iron_folding", e)  # Evidenz da, Fertigkeit fehlt
        before = (w.reg.to_json(), len(w.svc.log.events("p")))
        with self.assertRaises(WorldError):
            w.ds.complete("p", "iron_folding")
        with self.assertRaises(WorldError):
            w.ds.complete("p", "ghost")
        self.assertEqual((w.reg.to_json(), len(w.svc.log.events("p"))), before)
        self.assertIsNone(w.reg.pioneer("iron_folding"))  # keine Pionierrolle durch Fehlversuch

    def test_registry_rolls_back_when_cee_rejects(self):
        w = self.w
        w.smith("p")
        for e in DISC["iron_folding"]["evidence"]:
            w.ds.gather("p", "iron_folding", e)
        original = w.svc.record

        def failing(*a, **k):
            raise RuleViolation("simulierter Fehler")

        w.svc.record = failing
        with self.assertRaises(RuleViolation):
            w.ds.complete("p", "iron_folding")
        w.svc.record = original
        self.assertEqual((w.reg.pioneer("iron_folding"), w.reg.holders("iron_folding")), (None, []))
        self.assertEqual(w.ds.complete("p", "iron_folding").payload["credit"], "pioneer")  # Pionierrolle weiter frei

    def test_cannot_complete_twice_or_gather_after(self):
        w = self.w
        w.smith("p")
        w.research("p", "iron_folding")
        with self.assertRaises(WorldError):
            w.ds.complete("p", "iron_folding")
        with self.assertRaises(RuleViolation):
            w.ds.gather("p", "iron_folding", "forge_trial")

    def test_evidence_cannot_be_farmed(self):
        w = self.w
        w.smith("p")
        w.ds.gather("p", "iron_folding", "ore_sample_a")
        for _ in range(30):
            with self.assertRaises(RuleViolation):
                w.ds.gather("p", "iron_folding", "ore_sample_a")
        self.assertFalse(w.svc.discovery_progress("p", "iron_folding")["ready"])

    def test_npc_discovers_and_teaches_like_a_player(self):
        w = self.w
        w.smith("npc1", kind="npc")
        w.smith("pl")
        w.research("npc1", "iron_folding")
        w.ds.teach("npc1", "pl", "iron_folding")
        self.assertEqual(w.svc.state("npc1").parts["identity"]["kind"], "npc")
        self.assertIn("iron_folding", w.svc.known_discoveries("pl"))

    def test_logs_and_registry_stay_consistent_and_replay(self):
        w = self.w
        w.smith("a")
        w.smith("b")
        w.research("a", "iron_folding")
        w.clock.day = 12
        w.ds.teach("a", "b", "iron_folding")
        for cid in ("a", "b"):
            live = copy.deepcopy(w.svc.state(cid).parts)
            self.assertEqual(w.svc.rebuild(cid).parts, live)
        for did in DISC:
            holders = set(w.reg.holders(did))
            cee_holders = {c for c in ("a", "b") if did in w.svc.known_discoveries(c)}
            self.assertEqual(holders, cee_holders, did)

    def test_secret_chain_and_non_teachable(self):
        w = self.w
        w.svc.create("p", "player")
        w.svc.record("p", "identity.xp_gained", {"amount": 36100})  # Stufe 20
        attune(w.svc, "p", "light")
        attune(w.svc, "p", "shadow")
        with self.assertRaises(RuleViolation):
            w.ds.gather("p", "twilight_rite", "dusk_altar")  # Vorwissen old_shrine_map fehlt
        w.research("p", "old_shrine_map")
        ev = w.research("p", "twilight_rite")
        self.assertEqual(ev.payload["credit"], "pioneer")
        w.svc.create("friend", "player")
        w.clock.day = 999
        with self.assertRaisesRegex(WorldError, "nicht teilbar"):
            w.ds.teach("p", "friend", "twilight_rite")  # persönliche Entdeckung


class EssenceIntegrationTests(unittest.TestCase):
    def secret_candidate(self, w, cid, rite):
        w.svc.create(cid, "player")
        w.svc.record(cid, "identity.xp_gained", {"amount": 36100})
        attune(w.svc, cid, "light")
        attune(w.svc, cid, "shadow")
        for day in range(1, 7):  # Duellant-Richtung (Präzision + Mobilität), gegen gleichwertige Gegner (nicht trivial)
            for i in range(6):
                w.svc.record(cid, EV, enc(f"d{day}-{i}", opponent_type=f"mob{i}", opponent_level=20, day=day,
                                          actions={"dodge": 33, "perfect_dodge": 18, "light_hit": 120}))
        if rite:
            w.research(cid, "old_shrine_map")
            w.research(cid, "twilight_rite")

    def test_secret_form_requires_discovery_even_with_enough_points(self):
        w = World()
        self.secret_candidate(w, "no_rite", rite=False)
        s = w.svc.essence_scores("no_rite")["twilight_kin"]
        self.assertGreaterEqual(s["score"], s["threshold"])  # Punkte würden genügen ...
        self.assertFalse(s["eligible"])  # ... aber ohne Entdeckung bleibt die Form verschlossen
        self.assertNotIn("twilight_kin", w.svc.eligible_essences("no_rite"))
        with self.assertRaises(RuleViolation):
            w.svc.record("no_rite", "essence.trial_passed", {"form": "twilight_kin"})

    def test_discovery_unlocks_secret_form_path(self):
        w = World()
        self.secret_candidate(w, "rite", rite=True)
        self.assertEqual(w.svc.essence_scores("rite")["twilight_kin"]["contributions"]["discovery:twilight_rite"], 200)
        self.assertIn("twilight_kin", w.svc.eligible_essences("rite"))
        w.svc.record("rite", "essence.trial_passed", {"form": "twilight_kin"})
        w.svc.record("rite", "essence.adopted", {"form": "twilight_kin"})
        self.assertEqual(w.svc.essence_profile("rite")["form"], "twilight_kin")
        self.assertTrue(w.svc.essence_profile("rite")["advantages"])

    def test_discovery_adds_to_existing_form_score(self):
        w = World()
        w.smith("a")
        before = w.svc.essence_scores("a")["ember_kin"]["contributions"]["discovery:iron_folding"]
        w.research("a", "iron_folding")
        after = w.svc.essence_scores("a")["ember_kin"]["contributions"]["discovery:iron_folding"]
        self.assertEqual((before, after), (0, 100))

    def test_essence_rules_validation_for_discovery_gates(self):
        data = copy.deepcopy(RULES.data)
        data["essence"]["forms"]["twilight_kin"]["requires_discoveries"] = ["ghost"]
        from mmo_cee.errors import CEEError
        from mmo_cee.essence import EssenceEngine

        with self.assertRaises(CEEError):
            EssenceEngine(Rules(data))
        data = copy.deepcopy(RULES.data)
        data["essence"]["forms"]["ember_kin"]["signals"]["discovery:ghost"] = 50
        with self.assertRaises(CEEError):
            EssenceEngine(Rules(data))


if __name__ == "__main__":
    unittest.main()
