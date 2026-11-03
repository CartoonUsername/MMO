import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.errors import CEEError
from mmo_cee.essence import EssenceEngine, form_scores, parse_signal, signal_value, validate_essence_rules
from mmo_cee.history import EventLog
from mmo_cee.rules import Rules, load_rules

from .helpers import attune
from .test_combat import EV, train

RULES = load_rules()  # v4
VOW = "essence.decision_made"


def prepared(svc, cid="p", kind="player", xp=10000):
    svc.create(cid, kind)
    svc.record(cid, "identity.xp_gained", {"amount": xp})  # Stufe 11


def ember_ready(svc, cid="p", kind="player", smithing=3700):
    prepared(svc, cid, kind)
    attune(svc, cid, "fire")
    svc.record(cid, "profession.work", {"profession": "smithing", "xp": smithing})
    svc.record(cid, VOW, {"decision_id": "ember_vow", "choice": "accept"})


def contributions(svc, cid, form):
    return svc.essence_scores(cid)[form]["contributions"]


class EssenceRulesTests(unittest.TestCase):
    def test_default_rules_are_v4_and_valid(self):
        self.assertEqual(RULES.version, "4")
        validate_essence_rules(RULES)
        self.assertGreaterEqual(len(RULES["essence"]["forms"]), 5)

    def test_every_form_needs_two_signals_and_has_pros_and_cons(self):
        for name, f in RULES["essence"]["forms"].items():
            self.assertLess(max(f["signals"].values()), f["threshold"], name)
            self.assertTrue(f["modifiers"]["advantages"] and f["modifiers"]["disadvantages"], name)
            net = abs(sum(f["modifiers"]["advantages"].values()) - sum(f["modifiers"]["disadvantages"].values()))
            self.assertLessEqual(net, RULES["essence"]["balance"]["max_net_imbalance"], name)

    def _broken(self, mutate):
        data = copy.deepcopy(RULES.data)
        mutate(data["essence"])
        return Rules(data)

    def test_invalid_rules_are_rejected(self):
        cases = {
            "einzelnes Signal genügt": lambda e: e["forms"]["ember_kin"]["signals"].update({"element_attuned:fire": 700}),
            "Schwelle unerreichbar": lambda e: e["forms"]["ember_kin"].update(threshold=5000),
            "Gewicht null": lambda e: e["forms"]["ember_kin"]["signals"].update({"element_attuned:fire": 0}),
            "Gewicht float": lambda e: e["forms"]["ember_kin"]["signals"].update({"element_attuned:fire": 250.5}),
            "ohne Nachteile": lambda e: e["forms"]["ember_kin"]["modifiers"].update(disadvantages={}),
            "ohne Vorteile": lambda e: e["forms"]["ember_kin"]["modifiers"].update(advantages={}),
            "Ungleichgewicht": lambda e: e["forms"]["ember_kin"]["modifiers"]["advantages"].update(fire_damage_permille=900),
            "Modifikator negativ": lambda e: e["forms"]["ember_kin"]["modifiers"]["advantages"].update(fire_damage_permille=-5),
            "unbekanntes Element": lambda e: e["forms"]["ember_kin"]["signals"].update({"element_attuned:metal": 10}),
            "unbekannter Beruf": lambda e: e["forms"]["ember_kin"]["signals"].update({"profession:necromancy": 10}),
            "unbekannte Richtung": lambda e: e["forms"]["ember_kin"]["signals"].update({"combat_direction:nope": 10}),
            "unbekannte Entscheidung": lambda e: e["forms"]["ember_kin"]["signals"].update({"decision:ghost:accept": 10}),
            "unbekannte Option": lambda e: e["forms"]["ember_kin"]["signals"].update({"decision:ember_vow:maybe": 10}),
            "unbekannte Signalart": lambda e: e["forms"]["ember_kin"]["signals"].update({"luck:fire": 10}),
            "Signal ohne Wahl": lambda e: e["forms"]["ember_kin"]["signals"].update({"decision:ember_vow": 10}),
            "Entscheidung mit einer Option": lambda e: e["decisions"]["ember_vow"].update(options=["accept"]),
            "Entscheidung doppelte Option": lambda e: e["decisions"]["ember_vow"].update(options=["accept", "accept"]),
            "Cap null": lambda e: e["signal_caps"].update(element_affinity=0),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                with self.assertRaises(CEEError):
                    EssenceEngine(self._broken(mutate))

    def test_parse_signal(self):
        self.assertEqual(parse_signal("decision:a:b"), ("decision", "a", "b"))
        self.assertEqual(parse_signal("profession:mining"), ("profession", "mining", None))
        for bad in ("", "profession", "profession:", "decision:a", "x:y", "profession:a:b", ":a"):
            with self.assertRaises(CEEError):
                parse_signal(bad)

    def test_legacy_rules_state_shape_unchanged(self):
        v3 = CharacterService(rules=load_rules("rules_v3.json"))
        st = v3.create("p", "player")
        self.assertNotIn("decisions", st.parts["essence"])
        with self.assertRaises(RuleViolation):
            v3.record("p", VOW, {"decision_id": "ember_vow", "choice": "accept"})
        self.assertEqual(v3.essence_scores("p"), {})
        v4 = CharacterService()
        self.assertEqual(v4.create("p", "player").parts["essence"]["decisions"], {})


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()
        prepared(self.svc)

    def reject(self, payload):
        n = len(self.svc.log.events("p"))
        before = copy.deepcopy(self.svc.state("p").parts)
        with self.assertRaises(RuleViolation):
            self.svc.record("p", VOW, payload)
        self.assertEqual(len(self.svc.log.events("p")), n)
        self.assertEqual(self.svc.state("p").parts, before)

    def test_valid_decision_is_recorded(self):
        self.svc.record("p", VOW, {"decision_id": "ember_vow", "choice": "refuse"})
        self.assertEqual(self.svc.state("p").parts["essence"]["decisions"], {"ember_vow": "refuse"})

    def test_decision_once_and_final(self):
        self.svc.record("p", VOW, {"decision_id": "ember_vow", "choice": "accept"})
        self.reject({"decision_id": "ember_vow", "choice": "accept"})
        self.reject({"decision_id": "ember_vow", "choice": "refuse"})  # keine nachträgliche Umentscheidung

    def test_invalid_payloads(self):
        self.reject({"decision_id": "ghost", "choice": "accept"})
        self.reject({"decision_id": "ember_vow", "choice": "maybe"})
        self.reject({"decision_id": "ember_vow"})
        self.reject({"choice": "accept"})
        self.reject({"decision_id": 1, "choice": "accept"})
        self.reject({"decision_id": "ember_vow", "choice": 1})
        self.reject({"decision_id": ["ember_vow"], "choice": "accept"})
        self.reject({})

    def test_client_cannot_attach_points_or_forms(self):
        for extra in ("points", "score", "form", "weight", "xp"):
            self.reject({"decision_id": "ember_vow", "choice": "accept", extra: 1000})

    def test_minimum_level(self):
        self.svc.create("low", "player")
        with self.assertRaises(RuleViolation):
            self.svc.record("low", VOW, {"decision_id": "ember_vow", "choice": "accept"})

    def test_no_decisions_after_adoption(self):
        ember_ready(self.svc, "q")
        self.svc.record("q", "essence.trial_passed", {"form": "ember_kin"})
        self.svc.record("q", "essence.adopted", {"form": "ember_kin"})
        with self.assertRaises(RuleViolation):
            self.svc.record("q", VOW, {"decision_id": "shadow_pact", "choice": "accept"})


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()

    def test_exact_contributions(self):
        ember_ready(self.svc, smithing=700)
        c = contributions(self.svc, "p", "ember_kin")
        self.assertEqual(c["element_attuned:fire"], 250)
        self.assertEqual(c["element_affinity:fire"], 100 * (100 * 1000 // 300) // 1000)  # 33
        self.assertEqual(c["profession:smithing"], 250 * 300 // 1000)  # Meisterschaft 3 -> 300 Promille -> 75
        self.assertEqual(c["decision:ember_vow:accept"], 200)
        self.assertEqual(c["combat_direction:vanguard"], 0)
        self.assertEqual(self.svc.essence_scores("p")["ember_kin"]["score"], 33 + 250 + 75 + 200)

    def test_threshold_decides_not_a_single_requirement(self):
        ember_ready(self.svc, smithing=700)  # 558 < 600
        self.assertFalse(self.svc.essence_scores("p")["ember_kin"]["eligible"])
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 3000})  # Meisterschaft 5
        self.assertEqual(self.svc.essence_scores("p")["ember_kin"]["score"], 33 + 250 + 125 + 200)
        self.assertEqual(self.svc.eligible_essences("p"), ["ember_kin"])

    def test_threshold_boundary_is_inclusive(self):
        ember_ready(self.svc)
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 3000})
        score = self.svc.essence_scores("p")["ember_kin"]["score"]  # 608
        for threshold, expected in ((score, True), (score + 1, False), (score - 1, True)):
            data = copy.deepcopy(RULES.data)
            data["essence"]["forms"]["ember_kin"]["threshold"] = threshold
            rules = Rules(data)
            self.assertEqual(form_scores(self.svc.state("p"), rules)["ember_kin"]["eligible"], expected, threshold)

    def test_no_single_source_is_enough(self):
        prepared(self.svc, xp=1000000)  # Stufe 50
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 10**7})  # Meisterschaft 10 -> volle 250
        for el in ("fire",):
            self.svc.record("p", "element.exposure", {"element": el, "amount": 10**6})
        self.assertEqual(contributions(self.svc, "p", "ember_kin")["profession:smithing"], 250)
        self.assertEqual(contributions(self.svc, "p", "ember_kin")["element_affinity:fire"], 100)  # Cap greift
        self.assertEqual(self.svc.eligible_essences("p"), [])

    def test_repeated_exposure_beyond_cap_gives_nothing_more(self):
        prepared(self.svc)
        self.svc.record("p", "element.exposure", {"element": "fire", "amount": 300})
        a = contributions(self.svc, "p", "ember_kin")["element_affinity:fire"]
        self.svc.record("p", "element.exposure", {"element": "fire", "amount": 100000})
        self.assertEqual(contributions(self.svc, "p", "ember_kin")["element_affinity:fire"], a)

    def test_different_histories_reach_the_same_form(self):
        ember_ready(self.svc, "a")  # Beruf + Prägung + Gelübde
        prepared(self.svc, "b")  # Kampf + Prägung + Gelübde, kaum Beruf
        attune(self.svc, "b", "fire", amount=300)
        self.svc.record("b", VOW, {"decision_id": "ember_vow", "choice": "accept"})
        for day in range(1, 7):
            train(self.svc, "b", day, {"heavy_hit": 43, "block": 33}, n=6)
        self.svc.record("b", "profession.work", {"profession": "smithing", "xp": 300})
        self.assertIn("ember_kin", self.svc.eligible_essences("a"))
        self.assertIn("ember_kin", self.svc.eligible_essences("b"))
        ca, cb = contributions(self.svc, "a", "ember_kin"), contributions(self.svc, "b", "ember_kin")
        self.assertGreater(ca["profession:smithing"], cb["profession:smithing"])
        self.assertGreater(cb["combat_direction:vanguard"], ca["combat_direction:vanguard"])

    def test_decisions_steer_towards_different_forms(self):
        prepared(self.svc, "w")
        attune(self.svc, "w", "water")
        self.svc.record("w", "profession.work", {"profession": "logistics", "xp": 3000})
        self.svc.record("w", "profession.work", {"profession": "trade", "xp": 1500})
        for day in range(1, 5):
            train(self.svc, "w", day, {"ally_heal": 20}, n=6)
        before = self.svc.essence_scores("w")["tide_walker"]["score"]
        self.svc.record("w", VOW, {"decision_id": "ember_vow", "choice": "accept"})  # Gegenentscheidung hilft nicht
        self.assertEqual(self.svc.essence_scores("w")["tide_walker"]["score"], before)
        self.svc.create("w2", "player")
        self.svc.record("w2", "identity.xp_gained", {"amount": 10000})
        self.svc.record("w2", VOW, {"decision_id": "ember_vow", "choice": "refuse"})
        self.assertEqual(contributions(self.svc, "w2", "tide_walker")["decision:ember_vow:refuse"], 100)

    def test_multiple_eligible_forms_choice_is_permanent(self):
        ember_ready(self.svc)
        attune(self.svc, "p", "earth", amount=300)
        for day in range(1, 8):
            train(self.svc, "p", day, {"parry": 15, "block": 33}, n=6)
        self.svc.record("p", "profession.work", {"profession": "mining", "xp": 10**6})
        self.svc.record("p", "profession.work", {"profession": "construction", "xp": 10**6})
        self.svc.record("p", VOW, {"decision_id": "mountain_oath", "choice": "accept"})
        eligible = self.svc.eligible_essences("p")
        self.assertEqual(eligible, ["ember_kin", "stone_born"])
        self.svc.record("p", "essence.trial_passed", {"form": "stone_born"})
        self.svc.record("p", "essence.adopted", {"form": "stone_born"})
        self.assertEqual(self.svc.eligible_essences("p"), [])
        self.assertTrue(all(not s["eligible"] for s in self.svc.essence_scores("p").values()))
        for t in ("essence.trial_passed", "essence.adopted"):
            with self.assertRaises(RuleViolation):
                self.svc.record("p", t, {"form": "ember_kin"})

    def test_adoption_needs_trial_and_trial_not_twice(self):
        ember_ready(self.svc)
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 3000})
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "essence.adopted", {"form": "ember_kin"})
        self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})

    def test_level_gate(self):
        self.svc.create("p", "player")
        self.assertEqual(self.svc.essence_scores("p")["ember_kin"]["eligible"], False)
        prepared(self.svc, "q", xp=100)  # Stufe 2: Entscheidungen erst ab Stufe 5
        with self.assertRaises(RuleViolation):
            self.svc.record("q", VOW, {"decision_id": "ember_vow", "choice": "accept"})

    def test_profile_with_advantages_and_disadvantages_after_adoption(self):
        ember_ready(self.svc)
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 3000})
        self.assertEqual(self.svc.essence_profile("p"), {"form": "human", "advantages": {}, "disadvantages": {}})
        self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})
        self.svc.record("p", "essence.adopted", {"form": "ember_kin"})
        prof = self.svc.essence_profile("p")
        self.assertEqual(prof["form"], "ember_kin")
        self.assertTrue(prof["advantages"] and prof["disadvantages"])
        self.assertEqual(prof["advantages"], RULES["essence"]["forms"]["ember_kin"]["modifiers"]["advantages"])

    def test_class_identity_is_kept(self):
        ember_ready(self.svc)
        self.svc.record("p", "identity.class_chosen", {"base_class": "warrior"})
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 3000})
        self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})
        self.svc.record("p", "essence.adopted", {"form": "ember_kin"})
        self.assertEqual(self.svc.state("p").parts["identity"]["base_class"], "warrior")

    def test_npc_same_pipeline(self):
        ember_ready(self.svc, "n", kind="npc", smithing=3700)
        self.assertEqual(self.svc.eligible_essences("n"), ["ember_kin"])
        self.svc.record("n", "essence.trial_passed", {"form": "ember_kin"})
        self.svc.record("n", "essence.adopted", {"form": "ember_kin"})
        self.assertEqual(self.svc.rebuild("n").parts["essence"]["form"], "ember_kin")

    def test_replay_roundtrip_and_determinism(self):
        ember_ready(self.svc)
        self.svc.record("p", "profession.work", {"profession": "smithing", "xp": 3000})
        self.svc.record("p", "essence.trial_passed", {"form": "ember_kin"})
        live = copy.deepcopy(self.svc.state("p").parts)
        self.assertEqual(self.svc.rebuild("p").parts, live)
        svc2 = CharacterService(log=EventLog.from_json("p", self.svc.log.to_json("p")))
        self.assertEqual(svc2.state("p").parts, live)
        self.assertEqual(svc2.essence_scores("p"), self.svc.essence_scores("p"))

    def test_signal_value_is_bounded(self):
        prepared(self.svc, xp=1000000)
        st = self.svc.state("p")
        for form in RULES["essence"]["forms"].values():
            for key in form["signals"]:
                self.assertTrue(0 <= signal_value(st, RULES, key) <= 1000, key)
        self.assertEqual(sorted(form_scores(st, RULES)), sorted(RULES["essence"]["forms"]))


if __name__ == "__main__":
    unittest.main()
