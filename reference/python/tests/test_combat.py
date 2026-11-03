import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.combat import CombatEngine, reached_directions, style_profile, validate_combat_rules
from mmo_cee.errors import CEEError
from mmo_cee.history import EventLog
from mmo_cee.rules import Rules, load_rules

EV = "combat.encounter_resolved"


def enc(eid="e1", **over):
    p = {
        "encounter_id": eid,
        "opponent_type": "wolf",
        "opponent_level": 5,
        "outcome": "victory",
        "duration_s": 60,
        "day": 1,
        "actions": {"heavy_hit": 10},
    }
    p.update(over)
    return p


def train(svc, cid, day, actions, n=6, tag=""):
    """n Begegnungen mit verschiedenen Gegnertypen (keine Wiederholungsabnahme)."""
    for i in range(n):
        svc.record(cid, EV, enc(f"{tag}d{day}-{i}", opponent_type=f"mob{i}", day=day, actions=actions))


class CombatBasicTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()
        self.svc.create("p", "player")

    def part(self, cid="p"):
        return self.svc.state(cid).parts["combat"]

    def test_initial_state_has_six_dimensions_at_zero(self):
        part = self.part()
        self.assertEqual(sorted(part["points"]), sorted(load_rules()["combat"]["dimensions"]))
        self.assertEqual(len(part["points"]), 6)
        self.assertTrue(all(v == 0 for v in part["points"].values()))

    def test_exact_gain(self):
        # 10 heavy_hit * Gewicht 3 = 30 Roh; * Skala 100; Sieg/relevant/erste Begegnung = x1
        self.svc.record("p", EV, enc())
        self.assertEqual(self.part()["points"]["strength"], 3000)
        self.assertEqual(self.part()["points"]["precision"], 0)
        self.assertEqual(self.part()["stats"]["victory"], 1)
        self.assertEqual(self.part()["encounters"], {"e1": 1})

    def test_actions_feed_several_dimensions(self):
        self.svc.record("p", EV, enc(actions={"parry": 4, "perfect_dodge": 2}))
        pts = self.part()["points"]
        self.assertEqual(pts["defense"], 1200)
        self.assertEqual(pts["precision"], 4 * 100 + 2 * 100)
        self.assertEqual(pts["mobility"], 600)

    def test_outcome_factors(self):
        for i, (outcome, expected) in enumerate([("victory", 3000), ("defeat", 1500), ("fled", 750)]):
            cid = f"o{i}"
            self.svc.create(cid, "player")
            self.svc.record(cid, EV, enc(outcome=outcome))
            self.assertEqual(self.part(cid)["points"]["strength"], expected)

    def test_trivial_opponent_is_discounted(self):
        self.svc.create("v", "player")
        self.svc.record("v", "identity.xp_gained", {"amount": 36100})  # Stufe 20
        self.assertEqual(self.svc.state("v").parts["identity"]["level"], 20)
        self.svc.record("v", EV, enc(opponent_level=5))  # 5 + 10 < 20 -> trivial (100 Promille)
        self.assertEqual(self.part("v")["points"]["strength"], 300)
        self.svc.record("v", EV, enc("e2", opponent_level=10, opponent_type="bear"))  # 10 + 10 < 20 ist falsch
        self.assertEqual(self.part("v")["points"]["strength"], 300 + 3000)


class CombatValidationTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()
        self.svc.create("p", "player")

    def reject(self, payload, cid="p"):
        n = len(self.svc.log.events(cid))
        before = copy.deepcopy(self.svc.state(cid).parts)
        with self.assertRaises(RuleViolation):
            self.svc.record(cid, EV, payload)
        self.assertEqual(len(self.svc.log.events(cid)), n)  # nichts aufgezeichnet
        self.assertEqual(self.svc.state(cid).parts, before)  # Zustand unverändert

    def test_duplicate_encounter_rejected(self):
        self.svc.record("p", EV, enc("same"))
        self.reject(enc("same"))
        self.reject(enc("same", actions={"dodge": 1}, opponent_type="other"))  # auch mit anderem Inhalt
        self.assertEqual(self.svc.state("p").parts["combat"]["points"]["strength"], 3000)

    def test_replay_spam_cannot_farm(self):
        self.svc.record("p", EV, enc("one"))
        for _ in range(50):
            with self.assertRaises(RuleViolation):
                self.svc.record("p", EV, enc("one"))
        self.assertEqual(self.svc.state("p").parts["combat"]["points"]["strength"], 3000)

    def test_same_encounter_id_for_other_character_is_independent(self):
        self.svc.create("q", "player")
        self.svc.record("p", EV, enc("shared"))
        self.svc.record("q", EV, enc("shared"))  # Gruppenkampf: jeder Teilnehmer wird einmal gewertet
        self.assertEqual(self.svc.state("q").parts["combat"]["points"]["strength"], 3000)

    def test_client_chosen_points_rejected(self):
        for forbidden in ("points", "strength", "xp", "gain", "dimension_points"):
            self.reject(enc(**{forbidden: 999999}))

    def test_missing_fields_rejected(self):
        for key in enc():
            p = enc()
            del p[key]
            self.reject(p)

    def test_bad_ids_and_strings(self):
        for bad in ("", "x" * 65, 5, None):
            self.reject(enc(encounter_id=bad))
            self.reject(enc("ok", opponent_type=bad))

    def test_bad_numbers(self):
        for field, values in {
            "opponent_level": (0, -1, 101, 1.5, "5", True),
            "duration_s": (0, 4, 3601, 60.0, "60", True),
            "day": (-1, 1.5, "1", True),
        }.items():
            for v in values:
                self.reject(enc(**{field: v}))

    def test_unknown_outcome(self):
        self.reject(enc(outcome="draw"))

    def test_bad_actions(self):
        self.reject(enc(actions={}))
        self.reject(enc(actions=[("heavy_hit", 1)]))
        self.reject(enc(actions={"fireball": 3}))
        for bad in (0, -3, 2.5, "3", True):
            self.reject(enc(actions={"heavy_hit": bad}))

    def test_implausible_action_rate_rejected_boundary(self):
        # heavy_hit: 40/min * 60 s // 60 + Burst 3 = 43
        self.reject(enc(actions={"heavy_hit": 44}))
        self.svc.record("p", EV, enc("ok", actions={"heavy_hit": 43}))
        # kurze Begegnung: 5 s -> 40*5//60 = 3, +3 = 6
        self.reject(enc("short", duration_s=5, actions={"heavy_hit": 7}))
        self.svc.record("p", EV, enc("short2", duration_s=5, actions={"heavy_hit": 6}))

    def test_day_cannot_go_backwards(self):
        self.svc.record("p", EV, enc("a", day=5))
        self.reject(enc("b", day=4))
        self.svc.record("p", EV, enc("c", day=5, opponent_type="x"))  # gleicher Tag ok

    def test_event_requires_created_character(self):
        with self.assertRaises(RuleViolation):
            self.svc.record("ghost", EV, enc())

    def test_unknown_combat_event_type(self):
        with self.assertRaises(RuleViolation):
            self.svc.record("p", "combat.grant_points", {"strength": 100})


class CombatAntiFarmingTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()
        self.svc.create("p", "player")

    def strength(self):
        return self.svc.state("p").parts["combat"]["points"]["strength"]

    def test_repeat_opponent_decay(self):
        gains, last = [], 0
        for i in range(8):
            self.svc.record("p", EV, enc(f"w{i}", actions={"heavy_hit": 10}))
            gains.append(self.strength() - last)
            last = self.strength()
        self.assertEqual(gains, [3000, 3000, 2250, 1500, 750, 300, 300, 300])  # Tabelle aus Regeln

    def test_different_opponents_not_decayed(self):
        for i in range(6):
            self.svc.record("p", EV, enc(f"w{i}", opponent_type=f"t{i}"))
        self.assertEqual(self.strength(), 6 * 3000)

    def test_decay_resets_next_day(self):
        for i in range(6):
            self.svc.record("p", EV, enc(f"a{i}", day=1))
        before = self.strength()
        self.svc.record("p", EV, enc("b0", day=2))
        self.assertEqual(self.strength() - before, 3000)

    def test_daily_hard_cap_and_next_day_resume(self):
        cfg = load_rules()["combat"]["daily"]
        train(self.svc, "p", 1, {"heavy_hit": 43}, n=30)
        self.assertEqual(self.strength(), cfg["hard_cap"])
        self.svc.record("p", EV, enc("extra", opponent_type="fresh", day=1, actions={"heavy_hit": 43}))
        self.assertEqual(self.strength(), cfg["hard_cap"])  # kein weiterer Fortschritt
        self.assertEqual(self.svc.state("p").parts["combat"]["encounters"]["extra"], 31)  # aber gewertet/nachvollziehbar
        train(self.svc, "p", 2, {"heavy_hit": 43}, n=30)
        self.assertEqual(self.strength(), 2 * cfg["hard_cap"])

    def test_reduced_rate_between_full_and_hard_cap(self):
        # 12900 pro Begegnung: nach 2 Begegnungen 25800; 3. -> 4200 voll + (8700*250/1000=2175)
        train(self.svc, "p", 1, {"heavy_hit": 43}, n=3)
        self.assertEqual(self.strength(), 12900 + 12900 + 4200 + 2175)

    def test_dimensions_capped_independently(self):
        train(self.svc, "p", 1, {"heavy_hit": 43, "block": 33}, n=30)
        pts = self.svc.state("p").parts["combat"]["points"]
        self.assertEqual(pts["strength"], 50000)
        self.assertEqual(pts["defense"], 50000)


class CombatDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()
        self.rules = self.svc.rules

    def test_multiple_directions_at_once_and_no_exclusivity(self):
        self.svc.create("p", "player")
        self.assertEqual(self.svc.combat_directions("p"), {})
        for day in range(1, 5):
            train(self.svc, "p", day, {"heavy_hit": 43, "block": 33}, n=30)
        first = self.svc.combat_directions("p")
        self.assertIn("vanguard", first)
        # Weitere, völlig andere Richtung dazu – nichts wird abgewählt
        for day in range(5, 9):
            train(self.svc, "p", day, {"perfect_dodge": 15, "precise_hit": 40}, n=30, tag="x")
        later = self.svc.combat_directions("p")
        self.assertIn("vanguard", later)
        self.assertIn("duelist", later)
        self.assertGreaterEqual(len(later), 2)
        for name, tier in first.items():
            self.assertGreaterEqual(later[name], tier)  # nie zurückgestuft

    def test_points_never_decrease(self):
        self.svc.create("p", "player")
        last = 0
        for i in range(10):
            self.svc.record("p", EV, enc(f"n{i}", outcome="fled" if i % 2 else "victory", day=i))
            cur = sum(self.svc.state("p").parts["combat"]["points"].values())
            self.assertGreaterEqual(cur, last)
            last = cur

    def test_base_class_does_not_restrict_styles(self):
        for cid, klass in (("w", "warrior"), ("a", "archer"), ("s", "shaman_alchemist")):
            self.svc.create(cid, "player")
            self.svc.record(cid, "identity.class_chosen", {"base_class": klass})
            self.svc.record(cid, EV, enc(actions={"ally_heal": 10, "stun_applied": 5}))
            pts = self.svc.state(cid).parts["combat"]["points"]
            self.assertGreater(pts["support"], 0)
            self.assertGreater(pts["control"], 0)

    def test_different_histories_different_profiles(self):
        self.svc.create("a", "player")
        self.svc.create("b", "player")
        self.svc.record("a", EV, enc(actions={"heavy_hit": 20}))
        self.svc.record("b", EV, enc(actions={"ally_heal": 15}))
        pa = style_profile(self.svc.state("a"), self.rules)
        pb = style_profile(self.svc.state("b"), self.rules)
        self.assertEqual(pa["strength"], 1000)
        self.assertEqual(pb["support"], 1000)
        self.assertNotEqual(pa, pb)

    def test_style_profile_sums_to_at_most_1000(self):
        self.svc.create("p", "player")
        self.assertTrue(all(v == 0 for v in style_profile(self.svc.state("p"), self.rules).values()))
        self.svc.record("p", EV, enc(actions={"light_hit": 7, "parry": 3, "ally_shield": 2}))
        total = sum(style_profile(self.svc.state("p"), self.rules).values())
        self.assertTrue(990 <= total <= 1000)

    def test_npc_same_pipeline(self):
        self.svc.create("n", "npc")
        self.svc.record("n", EV, enc("npc-1", actions={"stun_applied": 8, "slow_applied": 10}))
        pts = self.svc.state("n").parts["combat"]["points"]
        self.assertEqual(pts["control"], (8 * 3 + 10 * 2) * 100)
        for day in range(1, 5):
            train(self.svc, "n", day, {"stun_applied": 10, "slow_applied": 23}, n=30)
        self.assertIn("controller", self.svc.combat_directions("n"))
        self.assertEqual(self.svc.state("n").parts["identity"]["kind"], "npc")


class CombatReplayTests(unittest.TestCase):
    def build(self):
        svc = CharacterService()
        svc.create("p", "player")
        svc.record("p", "identity.xp_gained", {"amount": 400})
        train(svc, "p", 1, {"heavy_hit": 43, "parry": 12}, n=8)
        svc.record("p", EV, enc("w", day=2, outcome="defeat", actions={"light_hit": 50}))
        svc.record("p", EV, enc("w2", day=2, outcome="fled", actions={"dodge": 9}))
        return svc

    def test_replay_equals_live_state(self):
        svc = self.build()
        live = copy.deepcopy(svc.state("p").parts)
        self.assertEqual(svc.rebuild("p").parts, live)

    def test_deterministic_across_instances(self):
        a, b = self.build(), self.build()
        self.assertEqual(a.state("p").parts, b.state("p").parts)
        self.assertEqual(a.log.events("p")[-1].hash, b.log.events("p")[-1].hash)

    def test_json_roundtrip_restores_state(self):
        svc = self.build()
        log2 = EventLog.from_json("p", svc.log.to_json("p"))
        svc2 = CharacterService(log=log2)
        self.assertEqual(svc2.state("p").parts, svc.state("p").parts)

    def test_tampered_combat_event_detected(self):
        import dataclasses

        from mmo_cee import IntegrityError

        svc = self.build()
        evs = svc.log._events["p"]
        i = next(k for k, e in enumerate(evs) if e.type == EV)
        pl = dict(evs[i].payload)
        pl["actions"] = {"heavy_hit": 43, "parry": 9999}
        evs[i] = dataclasses.replace(evs[i], payload=pl)
        with self.assertRaises(IntegrityError):
            svc.rebuild("p")

    def test_payload_decoupled_from_caller(self):
        svc = CharacterService()
        svc.create("p", "player")
        payload = enc()
        ev = svc.record("p", EV, payload)
        payload["actions"]["heavy_hit"] = 43
        self.assertEqual(ev.payload["actions"]["heavy_hit"], 10)
        svc.log.verify("p")
        self.assertEqual(svc.rebuild("p").parts["combat"]["points"]["strength"], 3000)

    def test_direction_view_is_pure_function_of_state(self):
        svc = self.build()
        self.assertEqual(reached_directions(svc.state("p"), svc.rules), svc.combat_directions("p"))


class CombatRulesTests(unittest.TestCase):
    def test_shipped_rules_are_consistent(self):
        validate_combat_rules(load_rules()["combat"])

    def test_v1_rules_still_load_without_combat(self):
        rules = load_rules("rules_v1.json")
        self.assertNotIn("combat", rules)
        svc = CharacterService(rules=rules)
        svc.create("p", "player")
        with self.assertRaises(RuleViolation):
            svc.record("p", EV, enc())
        self.assertEqual(svc.log.events("p")[0].rules_version, "1")

    def _broken(self, mutate):
        data = copy.deepcopy(load_rules().data)
        mutate(data["combat"])
        return Rules(data)

    def test_bad_rules_are_rejected_at_startup(self):
        cases = [
            lambda c: c["actions"]["dodge"]["weights"].update({"ghost": 1}),
            lambda c: c["actions"]["dodge"].update({"max_per_minute": 0}),
            lambda c: c["directions"]["duelist"].update({"tier_thresholds": [100, 50]}),
            lambda c: c["directions"]["duelist"]["weights"].update({"nope": 1}),
            lambda c: c["daily"].update({"hard_cap": 1}),
            lambda c: c.update({"repeat_opponent_permille": []}),
        ]
        for mutate in cases:
            with self.assertRaises(CEEError):
                CombatEngine(self._broken(mutate))

    def test_thresholds_come_from_rules_not_code(self):
        data = copy.deepcopy(load_rules().data)
        data["combat"]["point_scale"] = 200
        svc = CharacterService(rules=Rules(data))
        svc.create("p", "player")
        svc.record("p", EV, enc())
        self.assertEqual(svc.state("p").parts["combat"]["points"]["strength"], 6000)


if __name__ == "__main__":
    unittest.main()
