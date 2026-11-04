import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.rules import load_rules
from mmo_sim import EncounterServer, PackFinish, PackResult, SimError, simulate_group, simulate_pack
from mmo_sim.golden import pseudo_random_inputs
from mmo_sim.pack import strongest
from mmo_sim.rules import (COMMANDS, GROUP_COMMANDS, MULTI_COMMANDS, SKILL_KINDS, check_compatibility, load_sim_rules, max_actions_per_minute,
                           skill_commands, validate_sim_rules)

C = load_sim_rules("sim_rules_v4.json")
C3 = load_sim_rules("sim_rules_v3.json")
C5 = load_sim_rules("sim_rules_v5.json")
R9 = load_rules("rules_v9.json")
EV = "combat.encounter_resolved"


def P(inputs, level=1, **kw):
    return {"level": level, "inputs": inputs, **kw}


def pack(opps, *players, cfg=C):
    return simulate_pack(cfg, opps, list(players))


class RulesTests(unittest.TestCase):
    def bad(self, mutate):
        cfg = copy.deepcopy(C)
        mutate(cfg["multi"])
        with self.assertRaises(SimError):
            validate_sim_rules(cfg)

    def test_shipped_rules_valid_and_compatible(self):
        validate_sim_rules(C)
        self.assertEqual(check_compatibility(C, R9), [])
        self.assertEqual(set(MULTI_COMMANDS) & set(COMMANDS + GROUP_COMMANDS), set())
        self.assertEqual(C["multi"]["max_opponents"], 3)

    def test_multi_section_is_validated(self):
        self.bad(lambda m: m.update(max_opponents=0))
        self.bad(lambda m: m.update(max_opponents=4))
        self.bad(lambda m: m.update(max_opponents=True))
        for key, val in (("cost", -1), ("busy", 0), ("cooldown", -1), ("damage", 0)):
            self.bad(lambda m, key=key, val=val: m["sweep"].update({key: val}))
        cfg = copy.deepcopy(C)
        del cfg["group"]
        with self.assertRaises(SimError):
            validate_sim_rules(cfg)

    def test_rules_without_multi_refuse_packs(self):
        with self.assertRaises(SimError):
            simulate_pack(C3, ["wolf"], [P([])])

    def test_old_simulations_do_not_know_the_new_commands(self):
        for cmd in MULTI_COMMANDS:
            with self.assertRaises(SimError):
                simulate_group(C, "wolf", [P([[0, cmd]])])


class EquivalenceTests(unittest.TestCase):
    def test_one_opponent_equals_the_group_fight_for_random_inputs_and_equipment(self):
        every = ["power_strike", "disrupting_blow", "hindering_mark", "shield_wall", "riposte", "flowing_step", "ember_strike",
                 "veteran_focus", "twilight_veil"]
        for seed in range(1, 31):
            opp = ("wolf", "bear", "stone_golem", "training_dummy")[seed % 4]
            specs = []
            for i in range(1 + seed % 4):
                ins = sorted(pseudo_random_inputs(seed * 10 + i, 150, 3000) + [[5 + i, "heal"], [40 + i, "shield"]], key=lambda x: x[0])
                specs.append(P(ins, 1 + seed + i, equipped=every[: (seed + i) % 10]))
            g = simulate_group(C, opp, specs)
            k = simulate_pack(C, [opp], specs)
            self.assertEqual((k.players, k.outcome, k.ticks, k.opponent_hp, k.opponents), (g.players, g.outcome, g.ticks, g.opponent_hp, (g.opponent_hp,)), seed)

    def test_golden_group_cases_replay_identically_as_packs(self):
        from mmo_sim.golden_group import cases
        n = 0
        for case in cases():
            if case["name"].startswith("invalid"):
                continue
            g = simulate_group(C, case["opponent_type"], case["players"])
            k = simulate_pack(C, [case["opponent_type"]], case["players"])
            self.assertEqual((k.players, k.outcome, k.ticks, k.opponent_hp), (g.players, g.outcome, g.ticks, g.opponent_hp), case["name"])
            n += 1
        self.assertGreaterEqual(n, 40)


class ValidationTests(unittest.TestCase):
    def test_opponents_and_players(self):
        ok = P([[0, "light"]])
        bad = [([], [ok]), (["wolf"] * 4, [ok]), ("wolf", [ok]), (None, [ok]), (["wolf", "dragon"], [ok]), ([5], [ok]), ([["wolf"]], [ok]),
               (["wolf"], []), (["wolf"], [ok] * 5), (["wolf"], [P([[0, "target_4"]])]), (["wolf"], [P([[0, "target_0"]])]),
               (["wolf"], [P([], 1, allowed=["target_9"])]), (["wolf"], [P([[5, "sweep"], [4, "light"]])]), (["wolf"], [P("light")])]
        for opps, players in bad:
            with self.subTest(opps=opps, players=players), self.assertRaises(SimError):
                simulate_pack(C, opps, players)
        simulate_pack(C, ["wolf", "bear", "stone_golem"], [ok])
        simulate_pack(C, ["wolf"], [P([[0, "sweep"], [1, "target_3"]], 1, allowed=["sweep", "target_3"])])

    def test_determinism_and_types(self):
        specs = [P(pseudo_random_inputs(s, 200, 3000), 5 + s) for s in range(3)]
        a = simulate_pack(C, ["wolf", "bear"], specs)
        self.assertEqual(a, simulate_pack(C, ["wolf", "bear"], copy.deepcopy(specs)))
        self.assertIsInstance(a, PackResult)
        self.assertEqual(len(a.opponents), 2)
        self.assertEqual(a.opponent_hp, sum(a.opponents))


class MechanicsTests(unittest.TestCase):
    def fast(self, hp=10**6, **extra):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["fast"] = {"level": 1, "hp": hp, "attack_interval": 5, "windup": 2, "damage": 10, "stagger": 1}
        cfg["opponents"]["frail"] = {"level": 1, "hp": 50, "attack_interval": 0, "windup": 0, "damage": 0, "stagger": 0}
        cfg["multi"]["sweep"].update(extra)
        return cfg

    def test_hp_scales_per_opponent_with_party_size(self):
        r = pack(["wolf", "bear"], P([[0, "flee"]]), P([[0, "flee"]]), P([[0, "flee"]]))
        self.assertEqual(r.opponents, (660, 1980))      # 1000 + 600 * 2 Promille
        self.assertEqual(r.opponent_hp, 2640)

    def test_focus_defaults_to_the_first_and_can_be_switched(self):
        self.assertEqual(pack(["wolf", "bear"], P([[0, "light"], [100, "flee"]])).opponents, (260, 900))
        self.assertEqual(pack(["wolf", "bear"], P([[0, "target_2"], [1, "light"], [100, "flee"]])).opponents, (300, 860))

    def test_target_commands_cost_nothing_and_ignore_invalid_choices(self):
        r = pack(["wolf"], P([[0, "target_3"], [1, "target_2"], [2, "light"], [100, "flee"]]))
        self.assertEqual((r.opponents, r.players[0].ignored_inputs, r.players[0].actions), ((260,), 2, {"light_hit": 1}))
        r = pack(["wolf", "wolf"], P([[0, "target_2"], [0, "light"], [100, "flee"]]))       # kein Verbrauch an Ausdauer/Sperrzeit
        self.assertEqual((r.opponents, r.players[0].ignored_inputs), ((300, 260), 0))

    def test_dead_opponent_cannot_be_targeted_and_focus_falls_back(self):
        cfg = self.fast()
        r = pack(["frail", "wolf"], P([[0, "light"], [8, "light"], [30, "target_1"], [31, "light"], [100, "flee"]]), cfg=cfg)
        # frail (50 Leben) fällt nach dem zweiten Schlag; target_1 wird danach ignoriert, der nächste Schlag trifft den Wolf
        self.assertEqual((r.opponents[0] <= 0, r.opponents[1], r.players[0].ignored_inputs), (True, 300 - 40, 1))

    def test_blows_in_the_tick_the_last_opponent_falls_still_count(self):
        cfg = self.fast()
        r = pack(["frail"], P([[0, "light"], [8, "light"]]), P([[8, "light"]]), cfg=cfg)
        self.assertEqual((r.outcome, r.players[1].actions, r.opponents), ("victory", {"light_hit": 1}, (-40,)))

    def test_victory_needs_every_opponent_down(self):
        cfg = self.fast()
        lights = [[i * 8, "light"] for i in range(2)]
        r = pack(["frail", "frail"], P(lights + [[100, "flee"]]), cfg=cfg)
        self.assertEqual((r.outcome, r.opponents[0] <= 0, r.opponents[1] > 0), ("fled", True, True))
        r = pack(["frail", "frail"], P(lights + [[30, "target_2"], [31, "light"], [39, "light"], [100, "flee"]]), cfg=cfg)
        self.assertEqual((r.outcome, r.ticks, r.players[0].outcome), ("victory", 40, "victory"))

    def test_sweep_hits_every_living_opponent_once_per_use(self):
        r = pack(["wolf", "wolf", "wolf"], P([[0, "sweep"], [100, "flee"]]))
        self.assertEqual((r.opponents, r.players[0].actions), ((250, 250, 250), {"light_hit": 1}))

    def test_sweep_uses_cost_busy_and_cooldown(self):
        r = pack(["wolf", "wolf"], P([[0, "sweep"], [13, "sweep"], [14, "sweep"], [49, "sweep"], [50, "sweep"], [100, "flee"]]))
        self.assertEqual((r.opponents, r.players[0].ignored_inputs), ((200, 200), 3))   # 13 beschäftigt, 14 und 49 in der Abklingzeit
        cfg = self.fast(cost=60, cooldown=0, busy=1)
        r = pack(["wolf"], P([[0, "sweep"], [1, "sweep"], [100, "flee"]]), cfg=cfg)
        self.assertEqual((r.opponents, r.players[0].ignored_inputs), ((250,), 1))        # 100 - 60 = 40 < 60
        cfg = self.fast(cost=0, cooldown=0, busy=1)
        r = pack(["wolf"], P([[0, "sweep"], [1, "sweep"], [100, "flee"]]), cfg=cfg)
        self.assertEqual((r.opponents, r.players[0].ignored_inputs), ((200,), 0))

    def test_sweep_skips_the_fallen_and_adds_threat(self):
        cfg = self.fast()
        r = pack(["frail", "wolf"], P([[0, "sweep"], [50, "sweep"], [100, "flee"]]), cfg=cfg)
        self.assertEqual((r.opponents[0] <= 0, r.opponents[1]), (True, 200))
        # Bedrohung: der Spieler, der gefegt hat, zieht den Gegner (Gleichstand würde dem kleinsten Index gehören)
        r = pack(["wolf"], P([[100, "flee"]]), P([[0, "sweep"], [100, "flee"]]))
        self.assertEqual((r.players[0].damage_ticks, len(r.players[1].damage_ticks) > 0), ((), True))

    def test_sweep_obeys_allowed_commands(self):
        r = pack(["wolf", "wolf"], P([[0, "sweep"], [100, "flee"]], allowed=["light", "flee"]),
                 P([[0, "sweep"], [100, "flee"]], allowed=["sweep", "flee"]))
        self.assertEqual((r.players[0].ignored_inputs, r.players[1].actions, r.opponents), (1, {"light_hit": 1}, (430, 430)))

    def test_stun_and_slow_affect_only_the_focused_opponent(self):
        r = pack(["wolf", "wolf"], P([[0, "target_2"], [1, "stun"], [150, "flee"]]))
        self.assertEqual(r.players[0].damage_ticks, (40, 56, 80, 96, 120, 136))     # Wolf 2 beginnt erst nach der Betäubung
        r = pack(["wolf", "wolf"], P([[20, "slow"], [150, "flee"]]))
        self.assertEqual(r.players[0].damage_ticks, (40, 40, 80, 97, 120, 137))    # Wolf 1 schlägt langsamer: 40 + 52 + 5
        r = pack(["wolf", "wolf"], P([[0, "stun"], [10, "light"], [30, "target_2"], [31, "light"], [100, "flee"]]))
        self.assertEqual(r.players[0].actions, {"light_hit": 1, "precise_hit": 1, "stun_applied": 1})   # nur der betäubte Wolf ist verwundbar

    def test_each_opponent_has_its_own_clock(self):
        r = pack(["wolf", "bear"], P([[150, "flee"]]))
        self.assertEqual(r.players[0].damage_ticks, (40, 53, 80, 106, 120))        # Wolf: 35+5, Bär: 45+8

    def test_two_attackers_pick_the_target_with_most_threat(self):
        r = pack(["wolf", "wolf"], P([[150, "flee"]]), P([[0, "light"], [150, "flee"]]))
        self.assertEqual((r.players[0].damage_ticks, len(r.players[1].damage_ticks)), ((), 6))

    def test_parry_staggers_only_the_parried_opponent(self):
        # Wolf trifft bei 40 (pariert, Taumeln bis 50); der Bär trifft erst bei 53
        r = pack(["wolf", "bear"], P([[39, "block"], [150, "flee"]]), P([[45, "light"], [61, "light"], [150, "flee"]]))
        self.assertEqual(r.players[1].actions, {"light_hit": 1, "precise_hit": 1})
        r = pack(["wolf", "bear"], P([[39, "block"], [150, "flee"]]), P([[0, "target_2"], [45, "light"], [150, "flee"]]))
        self.assertEqual(r.players[1].actions, {"light_hit": 1})                      # Bär wankt nicht

    def test_parry_uses_the_stagger_of_the_parried_opponent(self):
        # Bär (Taumeln 8) steht vorn, der Wolf (Taumeln 10) trifft bei 40 und wird pariert: Taumeln bis 50, nicht bis 48
        r = pack(["bear", "wolf"], P([[39, "block"], [150, "flee"]]), P([[0, "target_2"], [49, "light"], [150, "flee"]]))
        self.assertEqual(r.players[1].actions, {"precise_hit": 1})

    def test_heavy_hits_the_target_chosen_when_it_started(self):
        r = pack(["wolf", "bear"], P([[0, "target_2"], [1, "heavy"], [3, "target_1"], [100, "flee"]]))
        self.assertEqual(r.opponents, (300, 770))

    def test_heavy_moves_to_a_living_opponent_if_its_target_fell(self):
        cfg = self.fast()
        r = pack(["frail", "wolf"], P([[0, "heavy"], [1, "target_2"]]), P([[0, "light"], [8, "light"], [100, "flee"]]), cfg=cfg)
        self.assertEqual(r.opponents[0] <= 0, True)
        cfg["opponents"]["frail"]["hp"] = 400
        r = pack(["frail", "wolf"], P([[0, "heavy"], [100, "flee"]]), P([[2, "sweep"], [100, "flee"]]), cfg=cfg)
        self.assertTrue(r.opponents[0] < 400 * 1600 // 1000)

    def test_heal_and_shield_work_in_packs(self):
        r = pack(["wolf", "wolf"], P([[0, "light"], [60, "flee"]]), P([[41, "heal"], [60, "flee"]]))
        self.assertEqual((r.players[1].actions, r.players[0].player_hp), ({"ally_heal": 1}, 1020 - 120 + 120))

    def test_fallen_opponents_stop_attacking(self):
        cfg = self.fast(hp=100)
        r = pack(["fast", "frail"], P([[0, "light"], [8, "light"], [16, "light"], [100, "flee"]], 100), cfg=cfg)
        hits_after = [t for t in r.players[0].damage_ticks if t > 25]
        self.assertEqual(hits_after, [])

    def test_outcomes(self):
        r = pack(["bear", "bear", "bear"], P([]), P([]))
        self.assertEqual((r.outcome, r.players[0].outcome), ("defeat", "defeat"))
        r = pack(["training_dummy"] * 3, P([]))
        self.assertEqual((r.outcome, r.ticks, r.players[0].outcome), ("fled", 6000, "fled"))
        r = pack(["wolf", "wolf"], P([[5, "flee"]]), P([[9, "flee"]]))
        self.assertEqual(r.outcome, "fled")


class ServerTests(unittest.TestCase):
    def build(self, n=2, rules=R9):
        svc = CharacterService(rules=rules)
        ids = [f"p{i}" for i in range(n)]
        for c in ids:
            svc.create(c, "player")
            svc.record(c, "identity.xp_gained", {"amount": 10000})
        return svc, ids

    def test_strongest_opponent_names_the_report(self):
        self.assertEqual(strongest(C, ["wolf", "bear", "stone_golem"]), "stone_golem")
        self.assertEqual(strongest(C, ["wolf", "wolf"]), "wolf")
        self.assertEqual(strongest(C, ["training_dummy", "wolf"]), "wolf")
        cfg = copy.deepcopy(C)
        cfg["opponents"]["wolf2"] = dict(cfg["opponents"]["wolf"])
        self.assertEqual(strongest(cfg, ["wolf2", "wolf"]), "wolf2")                  # Gleichstand: der erste

    def test_reports_use_the_strongest_opponent_and_each_player_gets_an_own_one(self):
        svc, ids = self.build()
        srv = EncounterServer(C, svc, lambda: 3)
        eid = srv.start_pack(ids, ["wolf", "bear"])
        res = srv.finish_pack(eid, {"p0": [[0, "sweep"], [100, "flee"]], "p1": [[0, "target_2"], [1, "light"], [100, "flee"]]})
        self.assertIsInstance(res, PackFinish)
        p0, p1 = (svc.log.events(c)[-1].payload for c in ids)
        self.assertEqual((p0["opponent_type"], p0["opponent_level"], p0["actions"], p1["actions"], p0["day"]), ("bear", 12, {"light_hit": 1}, {"light_hit": 1}, 3))
        self.assertEqual(p0["encounter_id"], eid)

    def test_idle_player_gets_no_report(self):
        svc, ids = self.build()
        srv = EncounterServer(C, svc, lambda: 3)
        eid = srv.start_pack(ids, ["wolf", "wolf"])
        res = srv.finish_pack(eid, {"p0": [[0, "light"], [100, "flee"]]})
        self.assertIsNone(res.events["p1"])
        self.assertEqual(svc.log.events("p1")[-1].type, "identity.xp_gained")

    def test_validation_and_reuse(self):
        svc, ids = self.build()
        srv = EncounterServer(C, svc, lambda: 1)
        for opps in ([], ["wolf"] * 4, "wolf", None, ["dragon"], [5]):
            with self.assertRaises(SimError):
                srv.start_pack(ids, opps)
        for party in ([], ["p0", "p0"], ["p0", "ghost"], "p0", [5], ["p0", "p1", "p0", "p1", "p0"]):
            with self.assertRaises(SimError):
                srv.start_pack(party, ["wolf"])
        with self.assertRaises(SimError):
            EncounterServer(C3, svc, lambda: 1).start_pack(ids, ["wolf"])
        eid = srv.start_pack(ids, ["wolf"])
        for bad in ({"stranger": []}, [], {"p0": [[0, "fireball"]]}):
            with self.assertRaises(SimError):
                srv.finish_pack(eid, bad)
        with self.assertRaises(SimError):
            srv.finish_pack("srv1-enc-99999999", {})
        self.assertEqual(len(svc.log.events("p0")), 2)
        srv.finish_pack(eid, {"p0": [[0, "light"], [100, "flee"]]})
        with self.assertRaises(SimError):
            srv.finish_pack(eid, {"p0": [[0, "light"]]})
        with self.assertRaises(SimError):
            srv.finish_group(eid, {})

    def test_all_or_nothing(self):
        svc, ids = self.build()
        srv = EncounterServer(C, svc, lambda: 1)
        eid = srv.start_pack(ids, ["wolf"])
        svc.record("p1", EV, {"encounter_id": eid, "opponent_type": "wolf", "opponent_level": 5, "outcome": "victory", "duration_s": 60,
                              "day": 1, "actions": {"light_hit": 3}})
        n0, n1 = len(svc.log.events("p0")), len(svc.log.events("p1"))
        with self.assertRaises(RuleViolation):
            srv.finish_pack(eid, {"p0": [[0, "light"], [100, "flee"]], "p1": [[0, "light"], [100, "flee"]]})
        self.assertEqual((len(svc.log.events("p0")), len(svc.log.events("p1"))), (n0, n1))

    def test_multi_commands_are_allowed_for_characters_with_abilities(self):
        svc, ids = self.build(1)
        pts = svc.state("p0").parts["combat"]["points"]
        for d in pts:
            pts[d] = 10**7
        svc.record("p0", "combat.loadout_set", {"abilities": ["power_strike"], "day": 1})
        self.assertIsNotNone(svc.allowed_commands("p0"))
        srv = EncounterServer(C, svc, lambda: 2)
        eid = srv.start_pack(ids, ["wolf", "wolf"])
        res = srv.finish_pack(eid, {"p0": [[0, "target_2"], [1, "sweep"], [100, "flee"]]})
        self.assertEqual(res.result.players[0].actions, {"light_hit": 1})
        self.assertEqual(res.result.players[0].ignored_inputs, 0)

    def test_reports_from_random_pack_fights_are_always_plausible(self):
        svc, ids = self.build(4)
        day = [1]
        srv = EncounterServer(C, svc, lambda: day[0])
        recorded = 0
        for seed in range(1, 13):
            day[0] += 1
            opps = [("wolf", "bear", "stone_golem", "training_dummy")[(seed + k) % 4] for k in range(1 + seed % 3)]
            eid = srv.start_pack(ids, opps)
            inputs = {c: sorted(pseudo_random_inputs(seed * 7 + i, 300, 3000) + [[10, "sweep"], [20, "target_2"], [3000, "heal"]], key=lambda x: x[0])
                      for i, c in enumerate(ids)}
            res = srv.finish_pack(eid, inputs)  # RuleViolation, wenn ein Bericht die CEE-Grenzen verletzt
            recorded += sum(e is not None for e in res.events.values())
        self.assertGreater(recorded, 20)


class SkillRulesTests(unittest.TestCase):
    def bad(self, mutate):
        cfg = copy.deepcopy(C5)
        mutate(cfg["skills"])
        with self.assertRaises(SimError):
            validate_sim_rules(cfg)

    def test_shipped_rules_valid_and_compatible(self):
        validate_sim_rules(C5)
        self.assertEqual(check_compatibility(C5, R9), [])
        self.assertEqual(skill_commands(C5), ("cast_ember", "dash", "focus_surge", "veil"))
        self.assertEqual(set(SKILL_KINDS), {"burst_dot", "evade", "mitigate", "restore_stamina"})
        self.assertEqual(max_actions_per_minute(C5)["heavy_hit"], max_actions_per_minute(C)["heavy_hit"] + 7)   # Einsätze von cast_ember zählen mit
        self.assertEqual(skill_commands(C), ())

    def test_skill_section_is_validated(self):
        self.bad(lambda k: k["dash"].update(kind="teleport"))
        self.bad(lambda k: k["dash"].update(cost=-1))
        self.bad(lambda k: k["dash"].update(busy=0))
        self.bad(lambda k: k["dash"].update(cooldown=-1))
        self.bad(lambda k: k["dash"].update(ticks=0))
        self.bad(lambda k: k["dash"].update(counts_as="light_hit"))
        self.bad(lambda k: k["dash"].update(ability=""))
        self.bad(lambda k: k["dash"].update(ability="ember_strike"))      # schon vergeben
        self.bad(lambda k: k["cast_ember"].update(damage=0))
        self.bad(lambda k: k["cast_ember"].update(dot={"interval": 0, "damage": 1, "ticks": 1}))
        self.bad(lambda k: k["cast_ember"].update(dot={"interval": 1, "damage": 0, "ticks": 1}))
        self.bad(lambda k: k["cast_ember"].update(dot=None))
        self.bad(lambda k: k["veil"].update(damage_permille=1001))
        self.bad(lambda k: k["veil"].update(ticks=0))
        self.bad(lambda k: k["focus_surge"].update(amount=0))
        self.bad(lambda k: k.update(light=dict(k["dash"])))                # Name schon als Befehl vergeben
        self.bad(lambda k: k.update(**{"not valid": dict(k["dash"], ability="x")}))
        cfg = copy.deepcopy(C5)
        del cfg["multi"]
        with self.assertRaises(SimError):
            validate_sim_rules(cfg)

    def test_unknown_abilities_are_reported(self):
        cfg = copy.deepcopy(C5)
        cfg["skills"]["dash"]["ability"] = "ghost_step"
        self.assertTrue(any("ghost_step" in p for p in check_compatibility(cfg, R9)))

    def test_skill_rate_beyond_the_cee_limit_is_reported(self):
        cfg = copy.deepcopy(C5)
        cfg["skills"]["cast_ember"].update(busy=1, cooldown=1)
        self.assertTrue(any(p.startswith("heavy_hit") for p in check_compatibility(cfg, R9)))

    def test_rules_without_skills_do_not_know_the_commands(self):
        with self.assertRaises(SimError):
            simulate_pack(C, ["wolf"], [P([[0, "dash"]])])


class SkillTests(unittest.TestCase):
    def sk(self, opps, *players, cfg=C5):
        return simulate_pack(cfg, opps, list(players))

    def test_old_rules_files_behave_identically_with_v5(self):
        for seed in range(1, 15):
            specs = [P(sorted(pseudo_random_inputs(seed * 10 + i, 120, 2500) + [[5, "sweep"], [30, "target_2"]], key=lambda x: x[0]), 3 + seed + i)
                     for i in range(1 + seed % 3)]
            opps = [("wolf", "bear", "stone_golem")[(seed + k) % 3] for k in range(1 + seed % 3)]
            self.assertEqual(simulate_pack(C, opps, specs), simulate_pack(C5, opps, specs), seed)

    def test_ember_hits_burns_and_counts_as_one_heavy_hit(self):
        r = self.sk(["bear"], P([[0, "cast_ember"], [100, "flee"]], 20))
        self.assertEqual((r.opponents, r.players[0].actions), ((900 - 180 - 4 * 20,), {"heavy_hit": 1}))

    def test_burn_ticks_every_interval_and_ends(self):
        r = self.sk(["bear"], P([[0, "cast_ember"], [19, "flee"]], 20))
        self.assertEqual(r.opponents, (900 - 180 - 20,))                        # nur der Tick bei 10; Flucht bei 19 beendet den Spieler, nicht den Brand
        r = self.sk(["bear"], P([[0, "cast_ember"], [9, "flee"]], 20))
        self.assertEqual(r.opponents, (900 - 180,))
        r = self.sk(["bear"], P([[0, "cast_ember"], [200, "flee"]], 20))
        self.assertEqual(r.opponents, (900 - 180 - 80,))                         # genau 4 Ticks

    def test_burn_can_finish_the_kill_and_ends_with_the_target(self):
        r = self.sk(["wolf"], P([[0, "cast_ember"], [12, "light"], [60, "flee"]]))
        self.assertEqual((r.outcome, r.ticks, r.opponents), ("victory", 41, (0,)))
        r = self.sk(["wolf", "wolf"], P([[0, "cast_ember"], [12, "sweep"], [40, "sweep"], [90, "flee"]], 20))
        self.assertEqual(r.opponents[0] <= 0, True)

    def test_a_second_cast_replaces_the_burn(self):
        r = self.sk(["bear"], P([[0, "cast_ember"], [80, "cast_ember"], [140, "flee"]], 20))
        self.assertEqual(r.opponents, (900 - 180 - 80 - 180 - 80,))

    def test_burn_goes_to_the_focus_and_adds_threat_for_the_caster(self):
        r = self.sk(["wolf", "bear"], P([[0, "target_2"], [1, "cast_ember"], [100, "flee"]], 20))
        self.assertEqual(r.opponents, (300, 900 - 180 - 80))
        r = self.sk(["wolf"], P([[100, "flee"]]), P([[0, "cast_ember"], [100, "flee"]]))
        self.assertEqual((r.players[0].damage_ticks, len(r.players[1].damage_ticks) > 0), ((), True))

    def test_burn_threat_is_credited_when_the_caster_is_still_in_the_fight(self):
        # Tick-Schaden zählt zur Bedrohung: p1 wirkt, p0 schlägt einmal leicht (40 < 180 + 80)
        r = self.sk(["wolf"], P([[0, "light"], [100, "flee"]]), P([[0, "cast_ember"], [100, "flee"]]))
        self.assertEqual((len(r.players[0].damage_ticks), len(r.players[1].damage_ticks) > 0), (0, True))

    def test_instant_damage_and_burn_ticks_both_add_threat(self):
        # Bedrohung bei Tick 35 (Wolf wählt sein Ziel): p0 = schwerer Schlag 130; p1 = 180 (Einsatz) + Brandtick 10/20/30
        r = self.sk(["wolf"], P([[0, "heavy"], [100, "flee"]], 20), P([[0, "cast_ember"], [100, "flee"]], 20))
        self.assertEqual((r.players[0].damage_ticks, len(r.players[1].damage_ticks) > 0), ((), True))
        # p0 = 130 + 40 + 40 = 210; p1 = 180 + 60 = 240 (ohne Brandticks nur 180)
        r = self.sk(["wolf"], P([[0, "heavy"], [20, "light"], [28, "light"], [100, "flee"]], 20), P([[0, "cast_ember"], [100, "flee"]], 20))
        self.assertEqual((r.players[0].damage_ticks, len(r.players[1].damage_ticks) > 0), ((), True))

    def test_cost_busy_and_cooldown(self):
        r = self.sk(["wolf", "wolf", "wolf"], P([[0, "cast_ember"], [5, "cast_ember"], [12, "cast_ember"], [79, "cast_ember"], [80, "cast_ember"], [100, "flee"]]))
        self.assertEqual((r.players[0].actions, r.players[0].ignored_inputs), ({"heavy_hit": 2}, 3))
        cfg = copy.deepcopy(C5)
        cfg["skills"]["cast_ember"].update(cost=60, cooldown=0, busy=1)
        r = self.sk(["wolf"], P([[0, "cast_ember"], [1, "cast_ember"], [100, "flee"]]), cfg=cfg)
        self.assertEqual((r.players[0].actions, r.players[0].ignored_inputs), ({"heavy_hit": 1}, 1))     # 100 - 60 < 60

    def test_dash_avoids_hits_only_in_its_window(self):
        r = self.sk(["wolf"], P([[36, "dash"], [100, "flee"]]))
        self.assertEqual((r.players[0].damage_ticks, r.players[0].actions), ((80,), {}))
        r = self.sk(["wolf"], P([[34, "dash"], [100, "flee"]]))             # Fenster 34..39: Treffer bei 40 nicht mehr
        self.assertEqual(r.players[0].damage_ticks, (40, 80))
        r = self.sk(["wolf"], P([[35, "dash"], [100, "flee"]]))
        self.assertEqual(r.players[0].damage_ticks, (80,))
        r = self.sk(["wolf"], P([[36, "dash"], [40, "dash"], [100, "dash"], [150, "flee"]]))
        self.assertEqual((r.players[0].damage_ticks, r.players[0].ignored_inputs), ((80, 120), 1))

    def test_dash_does_not_save_allies(self):
        r = self.sk(["wolf"], P([[36, "dash"], [100, "flee"]]), P([[0, "light"], [100, "flee"]]))
        self.assertEqual((r.players[0].damage_ticks, len(r.players[1].damage_ticks) > 0), ((), True))

    def test_veil_scales_damage_for_its_duration(self):
        # Schleier ab Tick 30 für 30 Ticks: der Treffer bei 40 wird halbiert, der bei 80 nicht mehr
        self.assertEqual(self.sk(["wolf"], P([[30, "veil"], [100, "flee"]])).players[0].player_hp, 1020 - 30 - 60)
        self.assertEqual(self.sk(["wolf"], P([[1, "veil"], [100, "flee"]])).players[0].player_hp, 1020 - 60 - 60)    # Fenster 1..31: Treffer erst bei 40
        self.assertEqual(self.sk(["wolf"], P([[10, "veil"], [100, "flee"]])).players[0].player_hp, 1020 - 60 - 60)   # Fenster endet vor Tick 40
        self.assertEqual(self.sk(["wolf"], P([[11, "veil"], [100, "flee"]])).players[0].player_hp, 1020 - 30 - 60)

    def test_veil_stacks_multiplicatively_with_block(self):
        r = self.sk(["wolf"], P([[30, "veil"], [38, "block"], [100, "flee"]]))
        self.assertEqual((r.players[0].actions, r.players[0].player_hp), ({"block": 1}, 1020 - 7 - 60))   # 60 * 250 / 1000 = 15, halbiert: 7

    def test_focus_surge_restores_stamina_up_to_the_maximum(self):
        cfg = copy.deepcopy(C5)
        cfg["player"].update(stamina_max=60, stamina_regen_per_tick=0)
        cfg["skills"]["focus_surge"].update(amount=30)
        spec = [[0, "heavy"], [20, "heavy"], [50, "heavy"], [80, "heavy"], [100, "flee"]]       # 25 je Schlag, Start 60, keine Regeneration
        r = self.sk(["stone_golem"], P(spec), cfg=cfg)
        self.assertEqual((r.players[0].actions, r.players[0].ignored_inputs), ({"heavy_hit": 2}, 2))
        r = self.sk(["stone_golem"], P(sorted(spec + [[40, "focus_surge"]])), cfg=cfg)
        self.assertEqual((r.players[0].actions, r.players[0].ignored_inputs), ({"heavy_hit": 3}, 1))     # 10 + 30 = 40 -> dritter Schlag, danach 15 < 25
        r = self.sk(["stone_golem"], P([[0, "focus_surge"], [100, "flee"]]), cfg=cfg)
        self.assertEqual(r.players[0].ignored_inputs, 0)
        r = self.sk(["stone_golem"], P([[0, "focus_surge"], [10, "heavy"], [30, "heavy"], [50, "heavy"], [70, "heavy"], [100, "flee"]]), cfg=cfg)
        self.assertEqual((r.players[0].actions, r.players[0].ignored_inputs), ({"heavy_hit": 2}, 2))     # Obergrenze 60, nicht 90

    def test_skills_respect_allowed(self):
        r = self.sk(["wolf"], P([[0, "cast_ember"], [12, "dash"], [100, "flee"]], allowed=["light", "dash", "flee"]))
        self.assertEqual((r.players[0].actions, r.players[0].ignored_inputs), ({}, 1))
        self.assertEqual(r.players[0].damage_ticks, (40, 80))                  # dash um 12 greift 6 Ticks, der Treffer kommt bei 40

    def test_unknown_skill_inputs_and_allowed_are_rejected(self):
        for bad in (P([[0, "cast_nova"]]), P([], 1, allowed=["cast_nova"])):
            with self.assertRaises(SimError):
                simulate_pack(C5, ["wolf"], [bad])


class SkillServerTests(unittest.TestCase):
    def build(self, abilities):
        svc = CharacterService(rules=R9)
        svc.create("p0", "player")
        svc.record("p0", "identity.xp_gained", {"amount": 100000})
        svc.record("p0", "element.exposure", {"element": "fire", "amount": 100})
        svc.record("p0", "element.attuned", {"element": "fire"})
        pts = svc.state("p0").parts["combat"]["points"]
        for d in pts:
            pts[d] = 10**7
        svc.record("p0", "combat.loadout_set", {"abilities": abilities, "day": 1})
        return svc

    def test_only_equipped_abilities_unlock_their_commands(self):
        svc = self.build(["ember_strike"])
        srv = EncounterServer(C5, svc, lambda: 2)
        eid = srv.start_pack(["p0"], ["wolf"])
        res = srv.finish_pack(eid, {"p0": [[0, "cast_ember"], [13, "dash"], [100, "flee"]]})
        self.assertEqual((res.result.players[0].actions, res.result.players[0].ignored_inputs), ({"heavy_hit": 1}, 1))   # dash: Fähigkeit nicht ausgerüstet
        self.assertEqual(svc.log.events("p0")[-1].payload["actions"], {"heavy_hit": 1})

    def test_empty_loadout_unlocks_no_skill(self):
        svc = self.build([])
        srv = EncounterServer(C5, svc, lambda: 2)
        res = srv.finish_pack(srv.start_pack(["p0"], ["wolf"]), {"p0": [[0, "cast_ember"], [20, "dash"], [100, "flee"]]})
        self.assertEqual((res.result.players[0].actions, res.result.players[0].ignored_inputs), ({}, 2))

    def test_unequipped_character_cannot_cast(self):
        svc = self.build(["power_strike"])
        srv = EncounterServer(C5, svc, lambda: 2)
        eid = srv.start_pack(["p0"], ["wolf"])
        res = srv.finish_pack(eid, {"p0": [[0, "cast_ember"], [100, "flee"]]})
        self.assertEqual(res.result.players[0].ignored_inputs, 1)
        self.assertIsNone(res.events["p0"])

    def test_characters_with_old_rules_may_use_every_skill(self):
        svc = CharacterService(rules=load_rules("rules_v8.json"))
        svc.create("p0", "player")
        svc.record("p0", "identity.xp_gained", {"amount": 10000})
        res = EncounterServer(C5, svc, lambda: 1)
        eid = res.start_pack(["p0"], ["wolf"])
        out = res.finish_pack(eid, {"p0": [[0, "cast_ember"], [100, "flee"]]})
        self.assertEqual(out.result.players[0].actions, {"heavy_hit": 1})

    def test_reports_from_random_skill_fights_are_always_plausible(self):
        svc = CharacterService(rules=R9)
        ids = ["p0", "p1"]
        for c in ids:
            svc.create(c, "player")
            svc.record(c, "identity.xp_gained", {"amount": 10000})
        day = [1]
        srv = EncounterServer(C5, svc, lambda: day[0])
        recorded = 0
        for seed in range(1, 11):
            day[0] += 1
            eid = srv.start_pack(ids, [("wolf", "bear")[seed % 2]])
            inputs = {c: sorted(pseudo_random_inputs(seed * 7 + i, 300, 3000) + [[10, "cast_ember"], [200, "cast_ember"], [400, "cast_ember"], [60, "dash"], [90, "veil"]],
                                key=lambda x: x[0]) for i, c in enumerate(ids)}
            res = srv.finish_pack(eid, inputs)
            recorded += sum(e is not None for e in res.events.values())
        self.assertGreater(recorded, 8)


if __name__ == "__main__":
    unittest.main()
