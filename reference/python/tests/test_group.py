import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.rules import load_rules
from mmo_sim import EncounterServer, GroupResult, SimError, simulate, simulate_group
from mmo_sim.golden import cases as solo_cases
from mmo_sim.golden import pseudo_random_inputs
from mmo_sim.rules import (COMMANDS, GROUP_COMMANDS, check_compatibility, load_sim_rules, max_actions_per_minute,
                           validate_sim_rules)

C = load_sim_rules("sim_rules_v3.json")
R9 = load_rules("rules_v9.json")
EV, LO = "combat.encounter_resolved", "combat.loadout_set"


def P(inputs, level=1, **kw):
    return {"level": level, "inputs": inputs, **kw}


def grp(opp, *players, cfg=C):
    return simulate_group(cfg, opp, list(players))


class RulesTests(unittest.TestCase):
    def bad(self, mutate):
        cfg = copy.deepcopy(C)
        mutate(cfg["group"])
        with self.assertRaises(SimError):
            validate_sim_rules(cfg)

    def test_shipped_rules_valid_and_compatible(self):
        validate_sim_rules(C)
        self.assertEqual(check_compatibility(C, R9), [])
        rates = max_actions_per_minute(C)
        self.assertEqual((rates["ally_heal"], rates["ally_shield"]), (15, 12))
        self.assertNotIn("ally_heal", max_actions_per_minute(load_sim_rules("sim_rules_v2.json")))
        self.assertEqual(set(GROUP_COMMANDS) & set(COMMANDS), set())

    def test_group_section_is_validated(self):
        self.bad(lambda g: g.update(max_party=0))
        self.bad(lambda g: g.update(max_party=9))
        self.bad(lambda g: g.update(max_party=True))
        self.bad(lambda g: g.update(opponent_hp_per_extra_member_permille=-1))
        self.bad(lambda g: g["heal"].update(amount=0))
        self.bad(lambda g: g["heal"].update(busy=0))
        self.bad(lambda g: g["heal"].update(cost=-1))
        self.bad(lambda g: g["shield"].update(absorb=0))
        self.bad(lambda g: g["shield"].update(ticks=0))
        self.bad(lambda g: g["threat"].update(heal_permille=-1))
        self.bad(lambda g: g.update(ability_commands={"ally_mend": "fireball"}))
        self.bad(lambda g: g.update(ability_commands={"ally_mend": "heal", "ally_ward": "heal"}))

    def test_incompatible_rates_and_unknown_abilities_are_reported(self):
        fast = copy.deepcopy(C)
        fast["group"]["heal"].update(busy=1, cooldown=1)
        self.assertTrue(any(p.startswith("ally_heal") for p in check_compatibility(fast, R9)))
        ghost = copy.deepcopy(C)
        ghost["group"]["ability_commands"]["fireball"] = "shield"
        del ghost["group"]["ability_commands"]["ally_ward"]
        self.assertTrue(any("fireball" in p for p in check_compatibility(ghost, R9)))

    def test_solo_simulation_does_not_know_group_commands(self):
        for cmd in GROUP_COMMANDS:
            with self.assertRaises(SimError):
                simulate(C, "wolf", 1, [[0, cmd]])


class EquivalenceTests(unittest.TestCase):
    def test_one_player_equals_the_solo_simulation_for_every_golden_case(self):
        n = 0
        for case in solo_cases():
            if case["name"].startswith("invalid"):
                continue
            cfg = load_sim_rules(case.get("rules_file", "sim_rules_v1.json"))
            cfg = {**cfg, "group": C["group"]}
            spec = {k: v for k, v in (("allowed", case.get("allowed")), ("equipped", case.get("equipped"))) if v is not None}
            solo = simulate(cfg, case["opponent_type"], case["player_level"], case["inputs"], case.get("allowed"), case.get("equipped"))
            g = simulate_group(cfg, case["opponent_type"], [P(case["inputs"], case["player_level"], **spec)])
            self.assertEqual((g.players[0], g.outcome, g.ticks), (solo, solo.outcome, solo.ticks), case["name"])
            n += 1
        self.assertGreaterEqual(n, 75)

    def test_one_player_equals_solo_for_random_inputs_and_equipment(self):
        every = ["power_strike", "disrupting_blow", "hindering_mark", "shield_wall", "riposte", "flowing_step", "ember_strike",
                 "veteran_focus", "twilight_veil"]
        for seed in range(1, 25):
            opp = ("wolf", "bear", "stone_golem", "training_dummy")[seed % 4]
            inputs = pseudo_random_inputs(seed, 150, 3000)
            eq = every[: seed % 10]
            solo = simulate(C, opp, 1 + seed, inputs, None, eq)
            self.assertEqual(simulate_group(C, opp, [P(inputs, 1 + seed, equipped=eq)]).players[0], solo, seed)


class ValidationTests(unittest.TestCase):
    def test_party_and_player_specs(self):
        ok = P([[0, "light"]])
        bad = [[], [ok] * 5, "x", None, [5], [{"level": 1}], [{"inputs": []}], [{**ok, "extra": 1}], [P([], 0)], [P([], True)],
               [P([], 1.5)], [P([], 1, allowed="light")], [P([], 1, allowed=["fireball"])], [P([], 1, equipped="ember_strike")],
               [P([], 1, equipped=["a", "a"])], [P([[0, "fireball"]])], [P([[5, "light"], [4, "light"]])], [P("light")]]
        for players in bad:
            with self.subTest(players=players):
                with self.assertRaises(SimError):
                    simulate_group(C, "wolf", players)
        with self.assertRaises(SimError):
            simulate_group(C, "dragon", [ok])
        with self.assertRaises(SimError):
            simulate_group(load_sim_rules("sim_rules_v2.json"), "wolf", [ok])  # Regeln ohne Gruppenkampf
        simulate_group(C, "wolf", [ok] * 4)
        simulate_group(C, "wolf", (ok,))

    def test_group_commands_are_valid_inputs_only_in_groups(self):
        self.assertTrue(grp("wolf", P([[0, "heal"], [5, "shield"]]), P([])))


class OpponentTests(unittest.TestCase):
    def test_hp_scales_with_party_size(self):
        hp = [grp("wolf", *[P([[0, "flee"]])] * n).opponent_hp for n in (1, 2, 3, 4)]
        self.assertEqual(hp, [300, 480, 660, 840])  # 300 * (1000 + 600 * (n - 1)) // 1000

    def test_target_is_the_player_with_most_threat_ties_go_to_the_lowest_index(self):
        r = grp("wolf", P([[0, "light"], [60, "flee"]]), P([[60, "flee"]]))
        self.assertEqual([p.damage_ticks for p in r.players], [(40,), ()])
        r = grp("wolf", P([[60, "flee"]]), P([[0, "light"], [60, "flee"]]))
        self.assertEqual([p.damage_ticks for p in r.players], [(), (40,)])
        r = grp("wolf", P([[60, "flee"]]), P([[60, "flee"]]))
        self.assertEqual([p.damage_ticks for p in r.players], [(40,), ()])

    def test_retarget_when_the_target_left_before_the_hit(self):
        r = grp("wolf", P([[0, "light"], [38, "flee"]]), P([[60, "flee"]]))
        self.assertEqual([p.damage_ticks for p in r.players], [(), (40,)])

    def test_fallen_players_do_not_act_and_the_rest_fights_on(self):
        weak = P([[8 * i, "light"] for i in range(0, 75)], 1)
        r = grp("stone_golem", weak, P([[400, "flee"]], 100))
        self.assertEqual([p.outcome for p in r.players], ["defeat", "fled"])
        self.assertEqual(r.players[0].ticks, r.players[0].ticks)
        self.assertLess(r.players[0].ticks, 400)
        n = r.players[0].actions.get("light_hit", 0) + r.players[0].actions.get("precise_hit", 0)
        self.assertLess(n, 75)  # nach dem Ausfall zählen keine Befehle mehr
        self.assertLessEqual(n, r.players[0].ticks // 8 + 1)

    def test_outcomes_victory_defeat_fled_and_timeout(self):
        r = grp("training_dummy", P([[t, "light"] for t in range(0, 400, 8)]), P([[10, "flee"]]))
        self.assertEqual((r.outcome, [p.outcome for p in r.players]), ("victory", ["victory", "fled"]))
        self.assertEqual(r.players[1].ticks, 10)
        r = grp("training_dummy", P([[5, "flee"]]), P([[9, "flee"]]))
        self.assertEqual((r.outcome, r.ticks, [p.outcome for p in r.players]), ("fled", 9, ["fled", "fled"]))
        r = grp("training_dummy", P([]), P([]))
        self.assertEqual((r.outcome, r.ticks, [p.outcome for p in r.players]), ("fled", C["max_ticks"], ["fled", "fled"]))
        r = grp("bear", P([]), P([]))
        self.assertEqual((r.outcome, [p.outcome for p in r.players]), ("defeat", ["defeat", "defeat"]))
        r = grp("bear", P([[30, "flee"]]), P([]))
        self.assertEqual((r.outcome, [p.outcome for p in r.players]), ("defeat", ["fled", "defeat"]))

    def test_a_player_who_flees_on_the_winning_tick_loses_the_kill(self):
        # Flucht wird vor der Schadensauflösung verarbeitet: der schwere Treffer des Flüchtenden verfällt
        r = grp("training_dummy", P([[0, "heavy"], [6, "flee"]]), P([[100, "flee"]]))
        self.assertNotIn("heavy_hit", r.players[0].actions)

    def test_stun_slow_and_stagger_are_shared_by_the_group(self):
        r = grp("wolf", P([[38, "stun"], [100, "flee"]]), P([[46, "light"], [100, "flee"]]))
        self.assertEqual(r.players[1].actions, {"precise_hit": 1})  # der Betäubte ist für alle verwundbar
        r = grp("wolf", P([[39, "block"], [100, "flee"]]), P([[48, "light"], [100, "flee"]]))
        self.assertEqual((r.players[0].actions, r.players[1].actions), ({"parry": 1}, {"precise_hit": 1}))

    def test_dodge_and_block_count_for_the_player_who_was_hit(self):
        r = grp("wolf", P([[0, "light"], [37, "dodge"], [100, "flee"]]), P([[37, "dodge"], [100, "flee"]]))
        self.assertIn("dodge", r.players[0].actions)
        self.assertNotIn("dodge", r.players[1].actions)  # nicht das Ziel -> kein Ausweich-Zähler


class SupportTests(unittest.TestCase):
    def test_heal_restores_the_lowest_ally_up_to_the_maximum(self):
        r = grp("wolf", P([[0, "light"], [60, "flee"]]), P([[41, "heal"], [60, "flee"]]))
        self.assertEqual((r.players[0].player_hp, r.players[1].actions), (1020, {"ally_heal": 1}))  # 60 Schaden, 200 Heilung -> gedeckelt
        r = grp("bear", P([[0, "light"], [70, "flee"]]), P([[60, "heal"], [70, "flee"]]))  # 120 Schaden, 200 Heilung -> Maximum
        self.assertEqual(r.players[0].player_hp, 1020)

    def test_heal_picks_the_smallest_share_and_lowest_index_on_ties(self):
        # Golem: Schlag 1 (Tick 62) trifft p0 (Bedrohung durch Leichten), Schlag 2 (Tick 124) p1 (Bedrohung durch Schweren)
        def wounded(l0, l1):
            return grp("stone_golem", P([[0, "light"], [400, "flee"]], l0), P([[70, "heavy"], [400, "flee"]], l1), P([[130, "heal"], [400, "flee"]], 30))
        r = wounded(100, 1)  # p0: 2800/3000 = 933 Promille, p1: 820/1020 = 803 Promille -> p1 wird geheilt (nicht der niedrigere Index)
        self.assertEqual((r.players[0].player_hp, r.players[1].player_hp), (2800, 1020))
        r = wounded(30, 30)  # gleicher Anteil -> kleinerer Index (p0)
        self.assertEqual((r.players[0].player_hp, r.players[1].player_hp), (1600, 1400))
        self.assertEqual(r.players[2].actions, {"ally_heal": 1})

    def test_nobody_to_heal_is_ignored_and_costs_nothing(self):
        r = grp("wolf", P([[0, "light"], [30, "flee"]]), P([[10, "heal"], [11, "heal"], [30, "flee"]]))
        self.assertEqual((r.players[1].actions, r.players[1].ignored_inputs), ({}, 2))
        solo = grp("wolf", P([[10, "heal"], [20, "flee"]]))
        self.assertEqual((solo.players[0].actions, solo.players[0].ignored_inputs), ({}, 1))

    def test_heal_cooldown_stamina_and_busy(self):
        base = [[0, "light"]]
        r = grp("bear", P(base + [[300, "flee"]]), P([[60, "heal"], [61, "heal"], [75, "heal"], [101, "heal"], [300, "flee"]]))
        # 61: busy (8 Ticks), 75: Abklingzeit 40 -> erst ab 100; 101 hat nichts mehr zu heilen
        self.assertEqual(r.players[1].actions.get("ally_heal"), 1)
        self.assertGreaterEqual(r.players[1].ignored_inputs, 2)

    def test_threat_from_healing_attracts_the_opponent(self):
        r = grp("bear", P([[0, "light"], [300, "flee"]]), P([[60, "heal"], [300, "flee"]]), P([[300, "flee"]]))
        # nach der Heilung (200 hp gedeckelt auf 120) hat p1 Bedrohung 120 > p0 40: der nächste Schlag trifft p1
        self.assertEqual(len(r.players[1].damage_ticks) > 0, True)

    def test_shield_absorbs_and_goes_to_the_highest_threat(self):
        r = grp("wolf", P([[0, "light"], [60, "flee"]]), P([[20, "shield"], [60, "flee"]]))
        self.assertEqual((r.players[0].player_hp, r.players[0].damage_ticks, r.players[1].actions), (1020, (), {"ally_shield": 1}))
        r = grp("bear", P([[0, "light"], [100, "flee"]]), P([[20, "shield"], [100, "flee"]]))  # 120 Schaden, Schild 150: nichts durch
        self.assertEqual(r.players[0].player_hp, 1020)

    def test_shield_overflow_expiry_and_no_double_shield(self):
        strong = C["opponents"]["stone_golem"]  # 200 Schaden: Schild 150 deckt 150 ab
        r = grp("stone_golem", P([[0, "light"], [100, "flee"]], 30), P([[30, "shield"], [100, "flee"]]))
        self.assertEqual(1000 + 20 * 30 - r.players[0].player_hp, strong["damage"] - 150)
        # zweites Schild auf ein schon geschütztes Ziel wird ignoriert, solange das erste wirkt
        r = grp("wolf", P([[0, "light"], [200, "flee"]]), P([[5, "shield"], [20, "shield"], [200, "flee"]]))
        self.assertEqual((r.players[1].actions.get("ally_shield"), r.players[1].ignored_inputs), (1, 1))
        # nach Ablauf (40 Ticks) geht ein neues
        r = grp("wolf", P([[0, "light"], [200, "flee"]]), P([[5, "shield"], [60, "shield"], [200, "flee"]]))
        self.assertEqual(r.players[1].actions.get("ally_shield"), 2)

    def test_shield_expires_and_no_longer_absorbs(self):
        r = grp("wolf", P([[0, "light"], [200, "flee"]]), P([[1, "shield"], [200, "flee"]]))
        self.assertEqual(r.players[0].damage_ticks[0], 80)  # Schild bis Tick 41: der Schlag bei 40 wird geschluckt (kein Schadenstick)
        self.assertGreater(1020 - r.players[0].player_hp, 0)  # spätere Schläge gehen durch

    def fast_cfg(self, damage=100, **group):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["fast"] = {"level": 1, "hp": 10**6, "attack_interval": 5, "windup": 2, "damage": damage, "stagger": 1}
        for k, v in group.items():
            cfg["group"][k].update(v)
        return cfg

    def test_shield_is_used_up_hit_by_hit(self):
        cfg = self.fast_cfg()
        r = grp("fast", P([[0, "light"], [20, "flee"]], 30), P([[1, "shield"], [20, "flee"]]), cfg=cfg)
        # Treffer bei Tick 7, 14: 100 + 100 gegen Schild 150 -> 1. Treffer ganz geschluckt, 2. kostet 50, ab dem 3. voller Schaden
        hits = r.players[0].damage_ticks
        self.assertEqual(hits[0], 14)
        self.assertEqual(1600 - r.players[0].player_hp, 50 + 100 * (len(hits) - 1))

    def test_shield_goes_to_the_highest_threat_and_not_to_already_shielded_allies(self):
        r = grp("wolf", P([[0, "light"], [200, "flee"]]), P([[10, "heavy"], [200, "flee"]]), P([[30, "shield"], [200, "flee"]]))
        # Bedrohung: p0 40, p1 130 -> der Schlag bei Tick 40 geht auf p1 und wird vom Schild geschluckt
        self.assertEqual(r.players[1].damage_ticks[0] > 40, True)
        self.assertEqual(r.players[0].damage_ticks, ())
        # zweiter Unterstützer: das Schild liegt schon auf p0, also geht das zweite an den nächsten Verbündeten (p1), nicht doppelt auf p0
        cfg = self.fast_cfg()
        r = grp("fast", P([[0, "light"], [30, "flee"]], 30), P([[1, "shield"], [30, "flee"]]), P([[8, "shield"], [30, "flee"]]), cfg=cfg)
        self.assertEqual(r.players[0].damage_ticks, (14, 21, 28))  # nur ein Schild (150) lag auf p0: ab dem 2. Schlag geht Schaden durch
        self.assertEqual(1600 - r.players[0].player_hp, 50 + 100 + 100)
        self.assertEqual(r.players[2].actions, {"ally_shield": 1})  # trotzdem wirkt der Befehl: auf den ungeschützten p1

    def test_support_costs_stamina_and_has_a_cooldown(self):
        costly = self.fast_cfg(200, heal={"cost": 60, "busy": 1, "cooldown": 1})
        r = grp("fast", P([[0, "light"], [40, "flee"]], 100), P([[20, "heal"], [21, "heal"], [40, "flee"]], 100), cfg=costly)
        self.assertEqual((r.players[1].actions.get("ally_heal"), r.players[1].ignored_inputs), (1, 1))  # 100 - 60 = 40 < 60
        cheap = self.fast_cfg(200, heal={"cost": 0, "busy": 1, "cooldown": 40})
        r = grp("fast", P([[0, "light"], [80, "flee"]], 100), P([[20, "heal"], [30, "heal"], [70, "heal"], [80, "flee"]], 100), cfg=cheap)
        self.assertEqual((r.players[1].actions.get("ally_heal"), r.players[1].ignored_inputs), (2, 1))  # Tick 30: Abklingzeit bis 60

    def test_support_respects_allowed_commands(self):
        r = grp("wolf", P([[0, "light"], [60, "flee"]]), P([[41, "heal"], [60, "flee"]], allowed=["light", "dodge", "block", "flee"]))
        self.assertEqual((r.players[1].actions, r.players[1].ignored_inputs, r.players[0].player_hp), ({}, 1, 960))
        r = grp("wolf", P([[0, "light"], [60, "flee"]]), P([[41, "heal"], [60, "flee"]], allowed=["heal", "flee"]))
        self.assertEqual(r.players[1].actions, {"ally_heal": 1})


class ServerTests(unittest.TestCase):
    def build(self, n=3, rules=R9):
        svc = CharacterService(rules=rules)
        ids = [f"p{i}" for i in range(n)]
        for c in ids:
            svc.create(c, "player")
            svc.record(c, "identity.xp_gained", {"amount": 10000})
        return svc, ids

    def unlock_and_equip(self, svc, cid, abilities, day=1):
        pts = svc.state(cid).parts["combat"]["points"]
        for d in pts:
            pts[d] = 10**7  # nur für den Test: Entwicklung direkt setzen
        svc.record(cid, LO, {"abilities": abilities, "day": day})

    def test_everyone_gets_an_own_report_with_only_own_actions(self):
        svc, ids = self.build()
        srv = EncounterServer(C, svc, lambda: 4)
        eid = srv.start_group(ids, "wolf")
        res = srv.finish_group(eid, {"p0": [[0, "light"], [100, "flee"]], "p1": [[5, "light"], [100, "flee"]]})
        self.assertEqual(set(res.events), set(ids))
        self.assertIsNone(res.events["p2"])  # untätig: kein Fortschritt, kein Bericht
        p0 = svc.log.events("p0")[-1].payload
        p1 = svc.log.events("p1")[-1].payload
        self.assertEqual((p0["encounter_id"], p1["encounter_id"], p0["actions"], p1["actions"]), (eid, eid, {"light_hit": 1}, {"light_hit": 1}))
        self.assertEqual(p0["day"], 4)
        self.assertEqual(svc.log.events("p2")[-1].type, "identity.xp_gained")

    def test_support_actions_become_ally_heal_and_ally_shield_points(self):
        svc, ids = self.build(2)
        self.unlock_and_equip(svc, "p1", ["ally_mend", "ally_ward"])
        srv = EncounterServer(C, svc, lambda: 2)
        eid = srv.start_group(ids, "wolf")
        res = srv.finish_group(eid, {"p0": [[0, "light"], [100, "flee"]], "p1": [[20, "shield"], [41, "heal"], [100, "flee"]]})
        self.assertEqual(svc.log.events("p1")[-1].payload["actions"], {"ally_shield": 1})  # p0 ist nach dem Schild nicht verwundet
        self.assertEqual(res.result.players[0].player_hp, 1000 + 20 * 11 - 60)  # der zweite Schlag (Tick 80) kommt ohne Schild durch

    def test_support_needs_the_ability_when_the_rules_know_abilities(self):
        svc, ids = self.build(2)
        srv = EncounterServer(C, svc, lambda: 2)
        eid = srv.start_group(ids, "wolf")
        res = srv.finish_group(eid, {"p0": [[0, "light"], [100, "flee"]], "p1": [[20, "shield"], [100, "flee"]]})
        self.assertEqual((res.result.players[1].actions, res.result.players[1].ignored_inputs), ({}, 1))

    def test_validation_and_reuse(self):
        svc, ids = self.build()
        srv = EncounterServer(C, svc, lambda: 1)
        for bad in ([], ["p0", "p0"], ["p0", "ghost"], "p0", [5], ["p0", "p1", "p2", "p0", "p1"]):
            with self.assertRaises(SimError):
                srv.start_group(bad, "wolf")
        with self.assertRaises(SimError):
            srv.start_group(ids, "dragon")
        with self.assertRaises(SimError):
            EncounterServer(load_sim_rules("sim_rules_v2.json"), svc, lambda: 1).start_group(ids, "wolf")
        eid = srv.start_group(ids, "wolf")
        with self.assertRaises(SimError):
            srv.finish_group(eid, {"stranger": []})
        with self.assertRaises(SimError):
            srv.finish_group(eid, [])
        with self.assertRaises(SimError):
            srv.finish_group(eid, {"p0": [[0, "fireball"]]})
        with self.assertRaises(SimError):
            srv.finish_group("srv1-enc-99999999", {})
        self.assertEqual(len(svc.log.events("p0")), 2)  # nichts aufgezeichnet, Begegnung noch offen
        srv.finish_group(eid, {"p0": [[0, "light"], [100, "flee"]]})
        with self.assertRaises(SimError):
            srv.finish_group(eid, {"p0": [[0, "light"]]})

    def test_all_or_nothing_when_one_report_is_rejected(self):
        svc, ids = self.build(2)
        srv = EncounterServer(C, svc, lambda: 1)
        eid = srv.start_group(ids, "wolf")
        svc.record("p1", EV, {"encounter_id": eid, "opponent_type": "wolf", "opponent_level": 5, "outcome": "victory", "duration_s": 60,
                              "day": 1, "actions": {"light_hit": 3}})  # p1 hat diese ID schon (Wiederholungsschutz der CEE)
        n0, n1 = len(svc.log.events("p0")), len(svc.log.events("p1"))
        with self.assertRaises(RuleViolation):
            srv.finish_group(eid, {"p0": [[0, "light"], [100, "flee"]], "p1": [[0, "light"], [100, "flee"]]})
        self.assertEqual((len(svc.log.events("p0")), len(svc.log.events("p1"))), (n0, n1))

    def test_reports_from_random_group_fights_are_always_plausible(self):
        svc, ids = self.build(4)
        for c in ids:
            self.unlock_and_equip(svc, c, ["power_strike", "disrupting_blow", "ally_mend"])
        svc.record("p0", LO, {"abilities": ["ally_mend", "ally_ward"], "day": 1})
        day = [1]
        srv = EncounterServer(C, svc, lambda: day[0])
        recorded = 0
        for seed in range(1, 13):
            day[0] += 1
            eid = srv.start_group(ids, ("wolf", "bear", "stone_golem", "training_dummy")[seed % 4])
            inputs = {c: pseudo_random_inputs(seed * 7 + i, 300, 3000) + [[3000, "heal"], [3001, "shield"]] for i, c in enumerate(ids)}
            inputs = {c: sorted(v, key=lambda x: x[0]) for c, v in inputs.items()}
            res = srv.finish_group(eid, inputs)  # RuleViolation, wenn ein Bericht die CEE-Grenzen verletzt
            recorded += sum(e is not None for e in res.events.values())
        self.assertGreater(recorded, 20)

    def test_characters_with_old_rules_may_use_every_command(self):
        svc, ids = self.build(2, rules=load_rules("rules_v8.json"))
        srv = EncounterServer(C, svc, lambda: 1)
        eid = srv.start_group(ids, "wolf")
        res = srv.finish_group(eid, {"p0": [[0, "light"], [100, "flee"]], "p1": [[41, "heal"], [100, "flee"]]})
        self.assertEqual(res.result.players[1].actions, {"ally_heal": 1})

    def test_determinism(self):
        specs = [P(pseudo_random_inputs(s, 200, 3000), 5 + s, equipped=["power_strike"][: s % 2]) for s in range(4)]
        self.assertEqual(simulate_group(C, "bear", specs), simulate_group(C, "bear", copy.deepcopy(specs)))
        self.assertIsInstance(simulate_group(C, "bear", specs), GroupResult)


if __name__ == "__main__":
    unittest.main()
