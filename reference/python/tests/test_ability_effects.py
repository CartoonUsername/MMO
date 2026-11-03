import copy
import unittest

from mmo_cee import CharacterService
from mmo_cee.rules import load_rules
from mmo_sim import EncounterServer
from mmo_sim.errors import SimError
from mmo_sim.fight import simulate
from mmo_sim.golden import pseudo_random_inputs
from mmo_sim.rules import (COMMANDS, EFFECT_KEYS, ability_effects, check_compatibility, combine_effects, load_sim_rules,
                           max_actions_per_minute, validate_sim_rules)

V1, V2 = load_sim_rules(), load_sim_rules("sim_rules_v2.json")
R9 = load_rules("rules_v9.json")
LO = "combat.loadout_set"
ALL = sorted(ability_effects(V2))
LIGHTS = [[0, "light"], [10, "light"], [20, "light"], [30, "light"], [200, "flee"]]


def run(opp, level, inputs, equipped=None, cfg=V2, allowed=None):
    return simulate(cfg, opp, level, inputs, allowed, equipped)


class RulesTests(unittest.TestCase):
    def bad(self, mutate):
        cfg = copy.deepcopy(V2)
        mutate(cfg["ability_effects"])
        with self.assertRaises(SimError):
            validate_sim_rules(cfg)

    def test_shipped_rules_valid_and_v1_has_no_effects(self):
        validate_sim_rules(V2)
        self.assertEqual(ability_effects(V1), {})
        self.assertEqual({k: v for k, v in V2.items() if k not in ("version", "_comment", "ability_effects")},
                         {k: v for k, v in V1.items() if k not in ("version", "_comment")})  # sonst identisch zu v1

    def test_validation(self):
        self.bad(lambda e: e.update(x={"unknown_effect": 1}))
        self.bad(lambda e: e.update(x={}))
        self.bad(lambda e: e.update(x=5))
        self.bad(lambda e: e.update(x={"heavy_damage_permille": 0}))
        self.bad(lambda e: e.update(x={"heavy_damage_permille": 10001}))
        self.bad(lambda e: e.update(x={"block_damage_permille": 1001}))
        self.bad(lambda e: e.update(x={"block_damage_permille": -1}))
        self.bad(lambda e: e.update(x={"stun_ticks_bonus": 101}))
        self.bad(lambda e: e.update(x={"stamina_regen_bonus": -1}))
        self.bad(lambda e: e.update(x={"dodge_cost_delta": 1.5}))
        self.bad(lambda e: e.update(x={"dodge_cost_delta": True}))
        self.assertTrue(set(EFFECT_KEYS) >= {k for e in ability_effects(V2).values() for k in e})

    def test_every_effect_key_is_used_by_the_shipped_catalog(self):
        used = {k for e in ability_effects(V2).values() for k in e}
        self.assertEqual(used, set(EFFECT_KEYS))

    def test_compatible_with_cee_rules_and_names_are_checked(self):
        self.assertEqual(check_compatibility(V2, R9), [])
        bad = copy.deepcopy(V2)
        bad["ability_effects"]["fireball"] = {"stun_ticks_bonus": 1}
        self.assertEqual(len(check_compatibility(bad, R9)), 1)
        self.assertTrue(any("fireball" in p for p in check_compatibility(bad, R9)))
        self.assertTrue(any("existiert" in p for p in check_compatibility(V2, load_rules("rules_v8.json"))))

    def test_rate_bound_uses_the_best_case_of_all_abilities(self):
        fast = copy.deepcopy(V2)
        fast["ability_effects"]["flowing_step"]["dodge_cooldown_delta"] = -20  # Abklingzeit 0: nur noch Gegnertakt begrenzt
        self.assertEqual(max_actions_per_minute(fast)["dodge"], max_actions_per_minute(V2)["dodge"])
        slow_opp = copy.deepcopy(fast)
        slow_opp["opponents"] = {k: v for k, v in slow_opp["opponents"].items() if k == "training_dummy"}
        slow_opp["ability_effects"].pop("flowing_step")
        slow_opp["ability_effects"]["x"] = {"dodge_cooldown_delta": -20}
        self.assertEqual(max_actions_per_minute(slow_opp)["dodge"], 0)  # ohne angreifende Gegner kann nichts ausgewichen werden


class RateBoundTests(unittest.TestCase):
    def test_best_case_cooldown_raises_the_dodge_bound_when_attacks_are_fast(self):
        cfg = copy.deepcopy(V2)
        cfg["opponents"] = {"fast": {"level": 1, "hp": 100, "attack_interval": 3, "windup": 2, "damage": 1, "stagger": 1}}
        with_fx = max_actions_per_minute(cfg)["dodge"]
        no_fx = copy.deepcopy(cfg)
        no_fx["ability_effects"] = {"_comment": "leer"}
        self.assertEqual((max_actions_per_minute(no_fx)["dodge"], with_fx), (60 * 10 // 20, 60 * 10 // 12))


class CombineTests(unittest.TestCase):
    def test_semantics(self):
        cfg = {"ability_effects": {"a": {"light_damage_permille": 1500, "stun_ticks_bonus": 3, "block_damage_permille": 200},
                                   "b": {"light_damage_permille": 1333, "stun_ticks_bonus": 4, "block_damage_permille": 100},
                                   "c": {"light_damage_permille": 1001}}}
        self.assertEqual(combine_effects(cfg, None), {})
        self.assertEqual(combine_effects(cfg, []), {})
        self.assertEqual(combine_effects(cfg, ["zzz"]), {})  # unbekannter Name: keine Wirkung
        out = combine_effects(cfg, ["b", "a"])
        self.assertEqual(out, {"light_damage_permille": 1500 * 1333 // 1000, "stun_ticks_bonus": 7, "block_damage_permille": 100})
        self.assertEqual(combine_effects(cfg, ["c", "a", "b"]), combine_effects(cfg, ["b", "c", "a"]))  # Reihenfolge der Eingabe egal
        self.assertEqual(combine_effects(cfg, ["a", "b", "c"])["light_damage_permille"], (1500 * 1333 // 1000) * 1001 // 1000)

    def test_invalid_input(self):
        for bad in ("a", ["a", "a"], [1], ("a", 2), {"a"}, 5):
            with self.assertRaises(SimError):
                combine_effects(V2, bad)
        combine_effects(V2, ("power_strike",))  # Tupel sind erlaubt


class EffectTests(unittest.TestCase):
    def test_light_damage(self):
        base, ember = run("training_dummy", 1, LIGHTS), run("training_dummy", 1, LIGHTS, ["ember_strike"])
        self.assertEqual((500 - base.opponent_hp, 500 - ember.opponent_hp), (4 * 40, 4 * 56))

    def test_heavy_damage(self):
        r = run("training_dummy", 1, [[0, "heavy"], [40, "heavy"], [100, "flee"]], ["power_strike"])
        self.assertEqual(500 - r.opponent_hp, 2 * 162)  # 130 * 1250 // 1000
        self.assertEqual(500 - run("training_dummy", 1, [[0, "heavy"], [100, "flee"]]).opponent_hp, 130)

    def test_block_damage(self):
        inputs = [[34, "block"], [50, "flee"]]  # nur der erste Gegnerschlag (Tick 40) wird geblockt
        plain, wall = run("wolf", 1, inputs), run("wolf", 1, inputs, ["shield_wall"])
        self.assertEqual((1020 - plain.player_hp, 1020 - wall.player_hp), (60 * 250 // 1000, 60 * 150 // 1000))

    def test_block_effect_never_worsens_blocking(self):
        weak = copy.deepcopy(V2)
        weak["ability_effects"]["shield_wall"]["block_damage_permille"] = 900
        inputs = [[34, "block"], [50, "flee"]]
        self.assertEqual(run("wolf", 1, inputs, ["shield_wall"], weak).player_hp, run("wolf", 1, inputs, []).player_hp)

    def test_parry_stagger_extends_the_punish_window(self):
        inputs = [[39, "block"], [52, "light"], [100, "flee"]]
        self.assertEqual(run("wolf", 1, inputs).actions, {"light_hit": 1, "parry": 1})
        self.assertEqual(run("wolf", 1, inputs, ["riposte"]).actions, {"parry": 1, "precise_hit": 1})

    def test_dodge_cost_and_cooldown(self):
        chain = [[t, "dodge"] for t in range(50, 400, 14)] + [[500, "flee"]]
        plain, flow = run("bear", 12, chain), run("bear", 12, chain, ["flowing_step"])
        self.assertLess(flow.ignored_inputs, plain.ignored_inputs)
        self.assertGreater(flow.actions["dodge"] + flow.actions["perfect_dodge"], plain.actions["dodge"] + plain.actions["perfect_dodge"])

    def test_stun_and_slow_durations(self):
        stun = run("wolf", 1, [[38, "stun"], [95, "flee"]], ["disrupting_blow"])
        none = run("wolf", 1, [[38, "stun"], [95, "flee"]])
        self.assertEqual((none.player_hp, stun.player_hp), (960, 1020))  # 5 Ticks länger betäubt: der nächste Schlag kommt erst nach 95
        inputs = [[0, "slow"], [87, "flee"]]  # Schlag bei Tick 40 fällt noch in die Verlangsamung; +10 Ticks verschieben den nächsten
        self.assertEqual((run("wolf", 1, inputs).player_hp, run("wolf", 1, inputs, ["hindering_mark"]).player_hp), (900, 960))

    def test_stamina_regen(self):
        rotation = [[7 * (3 * k + j), cmd] for k in range(40) for j, cmd in enumerate(("dodge", "block", "heavy"))]
        plain, focus = run("stone_golem", 100, rotation), run("stone_golem", 100, rotation, ["veteran_focus"])
        self.assertLess(focus.ignored_inputs, plain.ignored_inputs)

    def test_damage_taken(self):
        self.assertEqual((1020 - run("bear", 1, [[300, "flee"]]).player_hp, 1020 - run("bear", 1, [[300, "flee"]], ["twilight_veil"]).player_hp),
                         (600, 540))

    def test_damage_taken_also_applies_to_blocked_hits(self):
        inputs = [[34, "block"], [50, "flee"]]
        plain, veil = run("wolf", 1, inputs), run("wolf", 1, inputs, ["twilight_veil"])
        self.assertEqual((1020 - plain.player_hp, 1020 - veil.player_hp), (15, 60 * 250 // 1000 * 900 // 1000))
        both = run("wolf", 1, inputs, ["twilight_veil", "shield_wall"])
        self.assertEqual(1020 - both.player_hp, (60 * 150 // 1000) * 900 // 1000)

    def test_dodge_deltas_do_not_leak_into_other_commands(self):
        spam = [[t, "light"] for t in range(0, 200)]
        self.assertEqual(run("training_dummy", 1, spam, ["flowing_step"]), run("training_dummy", 1, spam))
        cfg = copy.deepcopy(V2)
        cfg["opponents"]["training_dummy"]["hp"] = 10**7  # damit der Kampf nicht endet
        heavies = [[21 * k, "heavy"] for k in range(120)]  # Ausdauer (25 > 21 Regeneration je Zyklus) wird irgendwann knapp
        a, b = simulate(cfg, "training_dummy", 1, heavies, None, ["flowing_step"]), simulate(cfg, "training_dummy", 1, heavies)
        self.assertGreater(b.ignored_inputs, 10)
        self.assertEqual(a, b)  # Ausweichen-Werte wirken nur auf Ausweichen
        stuns = [[55 * k, "stun"] for k in range(30)]  # Abklingzeit 60: jeder zweite Befehl ist zu früh
        x, y = simulate(cfg, "training_dummy", 1, stuns, None, ["flowing_step"]), simulate(cfg, "training_dummy", 1, stuns)
        self.assertGreater(y.ignored_inputs, 10)
        self.assertEqual(x, y)

    def test_abilities_without_entries_and_v1_rules_change_nothing(self):
        self.assertEqual(run("wolf", 1, LIGHTS, ["ally_mend", "ally_ward"]), run("wolf", 1, LIGHTS))
        self.assertEqual(run("training_dummy", 1, LIGHTS, ["ember_strike"], V1), run("training_dummy", 1, LIGHTS, None, V1))

    def test_stacking_matches_the_single_effects(self):
        self.assertEqual(combine_effects(V2, ALL)["light_damage_permille"], 1400)
        self.assertEqual(combine_effects(V2, ALL)["heavy_damage_permille"], 1250)

    def test_without_equipment_nothing_changes_even_with_the_v2_table(self):
        for opp in ("wolf", "bear", "stone_golem"):
            inputs = pseudo_random_inputs(3, 100, 2000)
            self.assertEqual(run(opp, 5, inputs), run(opp, 5, inputs, None, V1))


class ReportPlausibilityTests(unittest.TestCase):
    def test_reports_with_every_ability_are_always_accepted_by_the_cee(self):
        """Wirkungen dürfen die Plausibilitätsgrenzen der CEE nie überschreiten (sonst würde der Bericht abgelehnt)."""
        svc = CharacterService(rules=R9)
        svc.create("c", "player")
        svc.record("c", "identity.xp_gained", {"amount": 10**7})
        # alle Fähigkeiten freischalten, indem die Entwicklung direkt in den Zustand geschrieben wird (nur für diesen Test)
        pts = svc.state("c").parts["combat"]["points"]
        for d in pts:
            pts[d] = 10**8
        svc.state("c").parts["element"]["attuned"] = ["fire"]
        day = [1]
        srv = EncounterServer(V2, svc, lambda: day[0])
        svc.record("c", LO, {"abilities": ["power_strike", "disrupting_blow", "hindering_mark", "flowing_step"], "day": 1})
        loadouts = [["power_strike", "disrupting_blow", "hindering_mark", "flowing_step"], ["shield_wall", "riposte", "ember_strike", "veteran_focus"],
                    ["twilight_veil"]]
        accepted = 0
        for n, loadout in enumerate(loadouts):
            try:
                svc.record("c", LO, {"abilities": loadout, "day": 1})
            except Exception:
                continue  # nicht jede Kombination ist für die Testfigur ausrüstbar
            for seed in range(1, 9):
                day[0] += 1
                eid = srv.start("c", ("wolf", "bear", "stone_golem", "training_dummy")[seed % 4])
                inputs = [[t, cmd] for t, cmd in pseudo_random_inputs(seed, 400, 3000)]
                res = srv.finish("c", eid, inputs)  # wirft RuleViolation, wenn der Bericht unplausibel wäre
                accepted += res.event is not None
        self.assertGreaterEqual(accepted, 8)


class ServerIntegrationTests(unittest.TestCase):
    def build(self, rules="rules_v9.json"):
        svc = CharacterService(rules=load_rules(rules))
        svc.create("c", "player")
        svc.record("c", "identity.xp_gained", {"amount": 10000})
        if "abilities" in svc.rules["combat"]:
            for day in range(1, 9):
                for i in range(6):
                    svc.record("c", "combat.encounter_resolved", {"encounter_id": f"d{day}-{i}", "opponent_type": f"mob{i}", "opponent_level": 5,
                                                                   "outcome": "victory", "duration_s": 60, "day": day,
                                                                   "actions": {"heavy_hit": 35, "block": 28, "stun_applied": 9, "slow_applied": 18}})
        return svc

    def test_equipment_changes_the_outcome_through_the_server(self):
        svc = self.build()
        srv = EncounterServer(V2, svc, lambda: 9)
        inputs = [[0, "heavy"], [40, "heavy"], [100, "flee"]]
        plain = srv.finish("c", srv.start("c", "training_dummy"), inputs)
        svc.record("c", LO, {"abilities": ["power_strike"], "day": 9})
        armed = srv.finish("c", srv.start("c", "training_dummy"), inputs)
        self.assertEqual((plain.result.actions, plain.result.ignored_inputs), ({}, 2))
        self.assertEqual(500 - armed.result.opponent_hp, 2 * 162)
        self.assertEqual(armed.event.payload["actions"], {"heavy_hit": 2})

    def test_characters_without_abilities_in_their_rules_are_unaffected(self):
        svc = self.build("rules_v8.json")
        srv = EncounterServer(V2, svc, lambda: 9)
        res = srv.finish("c", srv.start("c", "training_dummy"), LIGHTS)
        self.assertEqual((res.result.ignored_inputs, 500 - res.result.opponent_hp), (0, 160))


if __name__ == "__main__":
    unittest.main()
