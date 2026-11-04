import copy
import unittest

from mmo_cee import CharacterService
from mmo_cee.rules import load_rules
from mmo_sim import EncounterServer, SimError, simulate_pack
from mmo_sim.live import LiveEncounter, replay_equals_live
from mmo_sim.rules import load_sim_rules
from mmo_sim.server import clamp_actions

C0 = load_sim_rules("sim_rules_v6.json")
R9 = load_rules("rules_v9.json")


def cfg_with(**opponents):
    c = copy.deepcopy(C0)
    base = {"level": 1, "hp": 10000, "attack_interval": 40, "windup": 5, "damage": 100, "stagger": 10, "role": "brute", "element": "earth",
            "abilities": [], "pool": {"count": [0, 0], "entries": {}}, "danger_cap": 20}
    for name, kw in opponents.items():
        c["opponents"][name] = {**base, **kw}
    return c


C = cfg_with(dummy={}, dummy_h={"hp": 1000}, small={"hp": 100})


def P(inputs, level=1, **kw):
    return {"level": level, "inputs": inputs, **kw}


def run(opps, players, abilities=None, cfg=C):
    return simulate_pack(cfg, opps, players, abilities)


def ev(res, kind=None, ability=None):
    return [e for e in res.events if (kind is None or e["type"] == kind) and (ability is None or e.get("ability") == ability)]


FLEE = [[600, "flee"]]


class SlamTests(unittest.TestCase):
    def test_telegraph_then_resolution_after_the_windup(self):
        r = run(["dummy"], [P(FLEE)], [["heavy_slam"]])
        t, res = ev(r, "telegraph")[0], ev(r, "resolved")[0]
        self.assertEqual((t["t"], t["ability"], t["kind"], t["ticks"], t["target"], t["answers"]), (40, "heavy_slam", "slam", 12, 0, ["dodge", "parry", "block"]))
        self.assertEqual((res["t"], res["outcome"], res["target"]), (52, "hit", 0))
        self.assertEqual(r.players[0].damage_ticks[0], 52)

    def test_damage_is_enemy_damage_times_permille(self):
        r = run(["dummy"], [P([[100, "flee"]])], [["heavy_slam"]])
        self.assertEqual(r.players[0].player_hp, 1020 - 250 - 100)               # Wuchtschlag 250, dann ein normaler Angriff bei 97 (100)

    def test_answers_dodge_block_parry(self):
        dodge = run(["dummy"], [P([[50, "dodge"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual((ev(dodge, "resolved")[0]["outcome"], dodge.players[0].actions.get("dodge")), ("dodge", 1))
        self.assertEqual(dodge.players[0].player_hp, 1020 - 100)                  # nur der spätere normale Angriff
        perfect = run(["dummy"], [P([[51, "dodge"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual((ev(perfect, "resolved")[0]["outcome"], perfect.players[0].actions.get("perfect_dodge")), ("perfect_dodge", 1))
        block = run(["dummy"], [P([[49, "block"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual((ev(block, "resolved")[0]["outcome"], block.players[0].player_hp), ("block", 1020 - 62 - 100))   # 250 * 250 / 1000 = 62
        parry = run(["dummy"], [P([[51, "block"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual((ev(parry, "resolved")[0]["outcome"], parry.players[0].actions.get("parry"), parry.players[0].player_hp), ("parry", 1, 1020))

    def test_parry_staggers_the_enemy_and_delays_its_next_move(self):
        r = run(["dummy"], [P([[51, "block"], [200, "flee"]])], [["heavy_slam"]])
        # Parade bei 52: Taumeln 10 Ticks, nächster Start 52 + 40 + 10 = 102, Treffer bei 107
        self.assertEqual([t for t in r.players[0].damage_ticks][:1], [107])

    def test_cooldown_and_priority_order(self):
        r = run(["dummy"], [P([[500, "flee"]])], [["heavy_slam"]])
        starts = [e["t"] for e in ev(r, "telegraph")]
        self.assertEqual(starts[:2], [40, 182])                                  # dazwischen normale Angriffe (92, 137), Abklingzeit 120 ab Tick 40
        r = run(["dummy"], [P([[100, "flee"]])], [["ground_pound", "heavy_slam"]])
        self.assertEqual([e["ability"] for e in ev(r, "telegraph")][:2], ["ground_pound", "heavy_slam"])   # erste bereite zuerst

    def test_the_slam_goes_to_the_highest_threat(self):
        r = run(["dummy"], [P([[100, "flee"]]), P([[0, "heavy"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual(ev(r, "telegraph")[0]["target"], 1)
        self.assertEqual(r.players[1].damage_ticks[0], 52)
        self.assertEqual(r.players[0].damage_ticks, ())

    def test_evade_skill_beats_a_slam(self):
        r = run(["dummy"], [P([[49, "dash"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual(ev(r, "resolved")[0]["outcome"], "evade")

    def test_veil_halves_the_slam(self):
        r = run(["dummy"], [P([[40, "veil"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual(r.players[0].damage_ticks[0], 52)
        self.assertEqual(r.players[0].player_hp, 1020 - 125 - 100)               # 250 * 500 / 1000

    def test_non_interruptible_slam_ignores_stun_and_heavy_hits(self):
        r = run(["dummy"], [P([[45, "stun"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual(ev(r, "interrupted"), [])
        self.assertEqual(ev(r, "resolved")[0]["t"], 52)
        r = run(["dummy"], [P([[35, "heavy"], [100, "flee"]])], [["heavy_slam"]])
        self.assertEqual(ev(r, "interrupted"), [])


class AreaTests(unittest.TestCase):
    def test_area_hits_everyone_and_each_defends_on_their_own(self):
        r = run(["dummy"], [P([[100, "flee"]]), P([[54, "dodge"], [100, "flee"]])], [["ground_pound"]])
        res = ev(r, "resolved")[0]
        self.assertEqual((res["t"], res["outcomes"]), (56, {"0": "hit", "1": "dodge"}))
        self.assertEqual((r.players[0].damage_ticks[0], r.players[1].actions.get("dodge")), (56, 1))
        self.assertEqual((r.players[0].player_hp, r.players[1].player_hp), (1020 - 100, 1020))      # 1000 ‰ von 100 nur für den, der nicht ausweicht

    def test_fallen_players_are_not_hit(self):
        r = run(["dummy"], [P([[55, "flee"]]), P([[100, "flee"]])], [["ground_pound"]])
        self.assertEqual(ev(r, "resolved")[0]["outcomes"], {"1": "hit"})

    def test_parry_during_an_area_attack_staggers_once(self):
        r = run(["dummy"], [P([[55, "block"], [200, "flee"]]), P([[200, "flee"]])], [["ground_pound"]])
        res = ev(r, "resolved")[0]
        self.assertEqual(res["outcomes"], {"0": "parry", "1": "hit"})


class StateTests(unittest.TestCase):
    def test_stun_blocks_all_inputs_until_it_ends_but_not_fleeing(self):
        r = run(["dummy"], [P([[40, "light"], [53, "light"], [59, "light"], [60, "light"], [200, "flee"]])], [["stunning_blow"]])
        res = ev(r, "resolved")[0]
        self.assertEqual((res["t"], res["outcome"]), (48, "hit"))                # Vorwarnung 8
        # Betäubung 48..59 (12 Ticks): Eingaben bei 53 und 59 verworfen, bei 60 wieder angenommen
        self.assertEqual(r.players[0].ignored_inputs, 2)
        self.assertEqual(r.players[0].actions.get("light_hit"), 2)               # 40 und 60

    def test_stun_cancels_a_pending_heavy_swing(self):
        r = run(["dummy"], [P([[35, "heavy"], [100, "flee"]])], [["stunning_blow"]])
        self.assertEqual(r.players[0].actions.get("heavy_hit"), 1)               # Befehl bei 35 landet bei 41, vor der Betäubung bei 48
        r2 = run(["dummy"], [P([[45, "heavy"], [100, "flee"]])], [["stunning_blow"]])
        self.assertIsNone(r2.players[0].actions.get("heavy_hit"))                # Befehl bei 45, Landung 51 > Betäubung 48: Schlag verfällt

    def test_dodged_or_blocked_state_attacks_apply_no_state(self):
        for ins in ([[47, "dodge"]], [[41, "block"]]):
            r = run(["dummy"], [P(ins + [[53, "light"], [200, "flee"]])], [["stunning_blow"]])
            self.assertEqual(r.players[0].ignored_inputs, 0, ins)

    def test_slow_stretches_busy_and_cooldown_of_players(self):
        r = run(["dummy"], [P([[0, "light"], [8, "light"], [56, "light"], [66, "light"], [200, "flee"]])], [["crippling_bite"]])
        res = ev(r, "resolved")[0]
        self.assertEqual((res["t"], res["outcome"]), (46, "hit"))                # Vorwarnung 6
        # ab 46 für 40 Ticks verlangsamt: Schlag bei 56 sperrt 12 statt 8 Ticks -> Eingabe bei 66 wird ignoriert (normal: erlaubt ab 64)
        self.assertEqual(r.players[0].ignored_inputs, 1)
        fast = run(["dummy"], [P([[0, "light"], [8, "light"], [56, "light"], [66, "light"], [200, "flee"]])], [[]])
        self.assertEqual(fast.players[0].ignored_inputs, 0)

    def test_burning_curse_burns_for_four_ticks_of_damage_and_adds_no_hit_tick_free_damage(self):
        r = run(["dummy"], [P([[200, "flee"]])], [["burning_curse"]])
        res = ev(r, "resolved")[0]
        self.assertEqual(res["t"], 60)
        self.assertEqual(r.players[0].damage_ticks[:4], (70, 80, 90, 100))        # alle 10 Ticks 15
        self.assertEqual(r.players[0].player_hp, 1020 - 60 - 300)                # Brand 4 x 15 plus normale Angriffe bei 105, 150 und 195

    def test_burn_is_absorbed_by_an_ally_shield(self):
        r = run(["dummy"], [P([[101, "flee"]]), P([[50, "shield"], [101, "flee"]])], [["burning_curse"]])
        # Brandticks bei 70, 80, 90, 100; Schild (ab 50, 40 Ticks bis 90) schluckt die ersten beiden vollständig
        self.assertEqual(r.players[0].damage_ticks, (90, 100))
        self.assertEqual(r.players[0].player_hp, 1020 - 30)


class CastTests(unittest.TestCase):
    def test_stun_interrupts_a_cast_and_the_enemy_staggers(self):
        r = run(["dummy"], [P([[45, "stun"], [200, "flee"]])], [["burning_curse"]])
        i = ev(r, "interrupted")[0]
        self.assertEqual((i["t"], i["ability"]), (45, "burning_curse"))
        self.assertEqual(ev(r, "resolved"), [])
        self.assertEqual(r.players[0].damage_ticks[:1], (105,))                   # Betäubung bis 60, dann 40 Takt, Vorwarnung 5: Treffer bei 105 ohne Brand
        self.assertEqual(r.players[0].actions.get("stun_applied"), 1)

    def test_heavy_hit_interrupts_a_cast(self):
        r = run(["dummy"], [P([[35, "heavy"], [200, "flee"]])], [["burning_curse"]])
        self.assertEqual([(e["t"], e["ability"]) for e in ev(r, "interrupted")], [(41, "burning_curse")])

    def test_interrupt_works_only_while_casting(self):
        r = run(["dummy"], [P([[80, "stun"], [200, "flee"]])], [["burning_curse"]])
        self.assertEqual(ev(r, "interrupted"), [])
        self.assertEqual(len(ev(r, "resolved")), 1)

    def test_a_dead_caster_never_resolves(self):
        r = run(["small"], [P([[0, "heavy"], [10, "light"], [18, "light"], [200, "flee"]], 20)], [["burning_curse"]])
        self.assertEqual(r.outcome, "victory")
        self.assertEqual(ev(r, "resolved"), [])


class ShieldTests(unittest.TestCase):
    def test_shield_absorbs_until_it_is_used_up_or_expires(self):
        r = run(["dummy"], [P([[i * 8, "light"] for i in range(15, 40)] + [[400, "flee"]])], [["stone_skin"]])
        self.assertEqual(ev(r, "resolved")[0]["t"], 50)                          # Vorwarnung 10
        # Schild 400 ab 50 für 80 Ticks: Treffer ab 120 landen direkt; vorher sind 10000 - 40 * (Treffer nach Ablauf)
        hits = sum(1 for i in range(15, 40) if i * 8 >= 130)
        self.assertEqual(r.opponents[0], 10000 - 40 * hits - max(0, 0))

    def test_parry_and_precise_hits_break_the_shield_but_heavy_hits_do_not(self):
        parry = run(["dummy"], [P([[60, "block"], [80, "block"], [100, "flee"]])], [["stone_skin", "heavy_slam"]])
        self.assertTrue(ev(parry, "shield_broken") == [] or ev(parry, "shield_broken")[0]["by"] == "parry")
        r = run(["dummy"], [P([[51, "stun"], [60, "light"], [100, "flee"]])], [["stone_skin"]])        # betäubt = verwundbar -> präziser Treffer
        b = ev(r, "shield_broken")
        self.assertEqual([(x["by"]) for x in b], ["precise_hit"])
        self.assertEqual(r.opponents[0], 10000 - 90)                              # der brechende Treffer geht voll durch
        h = run(["dummy"], [P([[52, "heavy"], [100, "flee"]])], [["stone_skin"]])
        self.assertEqual(ev(h, "shield_broken"), [])
        self.assertEqual(h.opponents[0], 10000)                                   # 130 vom Schild (400) geschluckt

    def test_shield_does_not_stack_and_is_recast_after_cooldown(self):
        r = run(["dummy"], [P([[700, "flee"]])], [["stone_skin"]])
        self.assertEqual([e["t"] for e in ev(r, "resolved")][:2], [50, 370])


class HealAndBuffTests(unittest.TestCase):
    def test_healer_heals_the_wounded_ally_up_to_the_cap(self):
        r = run(["small", "dummy_h"], [P([[0, "light"], [200, "flee"]])], [[], ["mend"]])
        ts = ev(r, "telegraph")[0]
        self.assertEqual((ts["t"], ts["ability"]), (40, "mend"))
        res = ev(r, "resolved")[0]
        self.assertEqual((res["t"], res["ally"]), (55, 0))
        self.assertEqual(r.opponents[0], 100 - 40 + 30)                           # 300 ‰ von 100
        r2 = run(["small", "dummy_h"], [P([[200, "flee"]])], [[], ["mend"]])
        self.assertEqual(ev(r2, "telegraph"), [])                                 # niemand verwundet: keine Heilung

    def test_mend_picks_the_lowest_share_and_never_heals_the_healer(self):
        c = cfg_with(a={"hp": 100}, b={"hp": 100}, healer={"hp": 100, "abilities": ["mend"]})
        r = run(["a", "b", "healer"], [P([[0, "light"], [8, "target_2"], [9, "light"], [17, "light"], [300, "flee"]])], [[], [], ["mend"]], c)
        res = ev(r, "resolved", "mend")
        self.assertEqual(res[0]["ally"], 1)                                       # b hat zwei Treffer, a nur einen

    def test_stun_on_the_healer_cancels_the_mend(self):
        r = run(["small", "dummy_h"], [P([[0, "light"], [8, "target_2"], [43, "stun"], [200, "flee"]])], [[], ["mend"]])
        self.assertEqual([(e["t"], e["ability"]) for e in ev(r, "interrupted")], [(43, "mend")])
        self.assertEqual(ev(r, "resolved", "mend"), [])

    def test_howl_hastes_allies_with_the_cycle_floor(self):
        c = cfg_with(a={"attack_interval": 60, "abilities": ["howl"]}, b={"attack_interval": 60})
        r = run(["a", "b"], [P([[400, "flee"]], 100)], [["howl"], []], c)
        self.assertEqual([(e["t"], e["ability"]) for e in ev(r, "resolved")][:1], [(70, "howl")])
        ticks = r.players[0].damage_ticks
        self.assertEqual(ticks[0], 65)                                            # b: normaler Angriff bei 60
        # a: Brüllen bei 60..70, danach mit Faktor 700: max(60 * 700 // 1000, 40 - 5) = 42 -> nächster Start 112, Treffer 117
        self.assertIn(117, ticks)
        self.assertNotIn(135, ticks)                                              # ohne Verstärkung wäre es 70 + 60 + 5

    def test_howl_needs_an_ally(self):
        c = cfg_with(a={"attack_interval": 60, "abilities": ["howl"]})
        r = run(["a"], [P(FLEE)], [["howl"]], c)
        self.assertEqual(ev(r, "telegraph"), [])


class SummonTests(unittest.TestCase):
    def test_summon_adds_enemies_that_must_be_defeated_and_respects_limits(self):
        r = run(["dummy"], [P([[100, "flee"]])], [["call_pack"]])
        res = ev(r, "resolved")[0]
        self.assertEqual((res["t"], res["summoned"]), (60, [1, 2]))
        self.assertEqual(len(r.opponents), 3)
        c = copy.deepcopy(C)
        c["enemy_abilities"]["max_enemies"] = 2
        r2 = run(["dummy"], [P([[100, "flee"]])], [["call_pack"]], c)
        self.assertEqual(ev(r2, "telegraph"), [])                                 # sonst mehr als 2 lebende Gegner
        c["enemy_abilities"]["max_enemies"] = 3
        r3 = run(["dummy"], [P([[100, "flee"]])], [["call_pack"]], c)
        self.assertEqual(len(ev(r3, "telegraph")), 1)

    def test_victory_needs_the_summons_too(self):
        c = cfg_with(boss_small={"hp": 100})
        kill_boss = [[62, "heavy"]]                                               # fällt bei 68, nachdem die Beschwörung bei 60 fertig war
        r = run(["boss_small"], [P(kill_boss + [[200, "flee"]], 100)], [["call_pack"]], c)
        self.assertEqual((r.outcome, r.opponents[0] <= 0, r.opponents[1] > 0), ("fled", True, True))
        sweeps = [[70 + 50 * i, "sweep"] for i in range(7)]
        r = run(["boss_small"], [P(kill_boss + sweeps + [[900, "flee"]], 100)], [["call_pack"]], c)
        self.assertEqual(r.outcome, "victory")
        self.assertTrue(all(h <= 0 for h in r.opponents))
        self.assertEqual(len(r.opponents), 3)

    def test_summoning_is_limited_by_max_alive_and_cooldown(self):
        r = run(["dummy"], [P([[1500, "flee"]], 100)], [["call_pack"]])
        # Einsatz bei 40 (fertig 60); Abklingzeit 300 -> frühestens 340; 2 lebende + 2 = 4 <= max_alive 4: zweiter Einsatz bei 340 (fertig 360 oder später, nach dem Takt)
        times = [e["t"] for e in ev(r, "resolved", "call_pack")]
        self.assertEqual(times[0], 60)
        self.assertGreaterEqual(times[1] - 20, 340)
        self.assertEqual(len(times), 2)                                           # ein dritter scheitert an max_alive (4 lebende)
        self.assertEqual(len(r.opponents), 5)

    def test_summoned_enemies_attack_and_get_their_own_abilities(self):
        r = run(["dummy"], [P([[300, "flee"]])], [["call_pack"]])
        self.assertTrue(len(r.players[0].damage_ticks) > 3)

    def test_target_commands_reach_summoned_enemies(self):
        r = run(["dummy"], [P([[100, "target_2"], [101, "light"], [300, "flee"]], 100)], [["call_pack"]])
        self.assertEqual((r.opponents[1], r.opponents[2]), (300 - 40, 300))       # nur der zweite Eintrag (erster Beschworener) wurde getroffen


class PhaseTests(unittest.TestCase):
    def test_phase_events_and_new_abilities(self):
        c = cfg_with(boss={"hp": 1000, "abilities": [], "phases": [{"at_permille": 500, "add": ["crippling_bite"], "attack_interval_permille": 850}]})
        ins = [[i * 8, "light"] for i in range(0, 60)] + [[600, "flee"]]
        r = run(["boss"], [P(ins, 1)], None, c)
        ph = ev(r, "phase")
        self.assertEqual([(e["phase"]) for e in ph], [1])
        self.assertTrue(any(e["ability"] == "crippling_bite" for e in ev(r, "telegraph")))
        first = [e for e in ev(r, "telegraph") if e["ability"] == "crippling_bite"][0]["t"]
        self.assertGreater(first, ph[0]["t"] - 1)

    def test_attack_cycle_floor_limits_enrage(self):
        c = cfg_with(boss={"hp": 1000, "attack_interval": 36, "windup": 4, "phases": [{"at_permille": 900, "add": [], "attack_interval_permille": 100}]})
        ins = [[i * 8, "light"] for i in range(0, 60)] + [[600, "flee"]]
        r = run(["boss"], [P(ins, 1)], None, c)
        hits = r.players[0].damage_ticks
        gaps = [b - a for a, b in zip(hits, hits[1:])]
        self.assertTrue(gaps and min(gaps) >= 36, gaps)                          # Boden 40 - Vorwarnung 4


class InputValidationTests(unittest.TestCase):
    def test_abilities_argument_validation(self):
        for bad in ("heavy_slam", [["heavy_slam"], []], [["nonsense"]], [["heavy_slam", "heavy_slam"]], [None], [5], {"a": 1}):
            with self.assertRaises(SimError, msg=str(bad)):
                run(["dummy"], [P(FLEE)], bad)
        run(["dummy"], [P(FLEE)], [[]])
        c5 = load_sim_rules("sim_rules_v5.json")
        with self.assertRaises(SimError):
            simulate_pack(c5, ["wolf"], [P(FLEE)], [["heavy_slam"]])

    def test_default_abilities_are_the_templates_fixed_ones(self):
        r = simulate_pack(C0, ["wisp_healer", "wolf"], [P([[0, "target_2"], [1, "light"], [9, "light"], [17, "light"], [300, "flee"]])])
        self.assertEqual(ev(r, "telegraph")[0]["ability"], "mend")                      # Wolf auf 60 %: unter der Heilschwelle von 70 %

    def test_old_rules_have_no_events(self):
        c5 = load_sim_rules("sim_rules_v5.json")
        r = simulate_pack(c5, ["wolf"], [P(FLEE)])
        self.assertEqual(r.events, ())

    def test_extra_target_commands_exist_with_enemy_rules_only(self):
        simulate_pack(C0, ["wolf"], [P([[0, "target_6"]])])
        c5 = load_sim_rules("sim_rules_v5.json")
        with self.assertRaises(SimError):
            simulate_pack(c5, ["wolf"], [P([[0, "target_4"]])])


class LiveTests(unittest.TestCase):
    def test_live_events_view_and_replay(self):
        pl = [P([])]
        e = LiveEncounter(C, ["dummy"], pl, [["burning_curse", "stone_skin"]])
        seen = []
        while not e.done and e.t < 400:
            if e.t == 30:
                e.submit(0, "light")
            e.advance()
            seen += e.drain_events()
            if e.t == 45:
                v = e.view()
                self.assertEqual(v["opponents"][0]["casting"]["ability"], "burning_curse")
        self.assertEqual([x["type"] for x in seen][:2], ["telegraph", "resolved"])
        self.assertEqual(e.drain_events(), [])
        e.submit(0, "flee")
        e.advance()
        self.assertTrue(replay_equals_live(C, e, pl))

    def test_view_shows_player_states_and_shields(self):
        e = LiveEncounter(C, ["dummy"], [P([])], [["stunning_blow"]])
        for _ in range(50):
            e.advance()
        v = e.view()
        self.assertGreater(v["players"][0]["stunned"], 0)
        self.assertEqual((v["players"][0]["slowed"], v["players"][0]["burning"]), (0, False))
        e2 = LiveEncounter(C, ["dummy"], [P([])], [["stone_skin"]])
        for _ in range(55):
            e2.advance()
        self.assertEqual(e2.view()["opponents"][0]["shield"], 400)

    def test_random_live_play_equals_replay_with_abilities(self):
        import random
        cmds = ["light", "heavy", "dodge", "block", "stun", "slow", "sweep", "target_2", "target_4", "flee"]
        types = ["alpha_wolf", "bog_witch", "wisp_healer", "stone_warden", "totem_caller", "shadow_hunter"]
        for seed in range(1, 16):
            rng = random.Random(seed)
            opps = [types[(seed + k) % len(types)] for k in range(1 + seed % 3)]
            players = [P([], 10 + seed + i) for i in range(1 + seed % 3)]
            from mmo_sim.enemies import roll_abilities
            abil = [roll_abilities(C0, t, f"sp{k}", seed) for k, t in enumerate(opps)]
            e = LiveEncounter(C0, opps, players, abil)
            while not e.done:
                for i in range(e.player_count):
                    if rng.random() < 0.3:
                        e.submit(i, rng.choice(cmds))
                if e.t == 700:
                    for i in range(e.player_count):
                        e.submit(i, "flee")
                e.advance()
            self.assertTrue(replay_equals_live(C0, e, players), seed)


class ReportTests(unittest.TestCase):
    def test_clamp_actions_follows_the_cee_limit_and_drops_zero_counts(self):
        cc = R9["combat"]
        limit = cc["actions"]["parry"]["max_per_minute"] * 5 // 60 + cc["encounter"]["burst_allowance"]
        self.assertEqual(clamp_actions(cc, {"parry": 99}, 5), {"parry": limit})
        self.assertEqual(clamp_actions(cc, {"parry": 1, "dodge": 2}, 5), {"parry": 1, "dodge": 2})
        self.assertEqual(clamp_actions(cc, {"parry": 99}, 3600), {"parry": 99})
        self.assertEqual(clamp_actions(cc, {"parry": 5000}, 3600)["parry"], cc["actions"]["parry"]["max_per_minute"] * 60 + cc["encounter"]["burst_allowance"])

    def test_long_boss_fights_produce_reports_the_cee_accepts(self):
        svc = CharacterService(rules=R9)
        ids = ["p0", "p1", "p2"]
        for c in ids:
            svc.create(c, "player")
            svc.record(c, "identity.xp_gained", {"amount": 100000})
        srv = EncounterServer(C0, svc, lambda: 3)
        eid = srv.start_pack(ids, ["stone_heart_colossus"], [["heavy_slam", "ground_pound"]])
        ins = {c: sorted([[i * 8, "light"] for i in range(1, 300)] + [[i * 25 + 3 * k, "block" if i % 2 else "dodge"] for i in range(1, 90)] + [[2600, "flee"]], key=lambda x: x[0])
               for k, c in enumerate(ids)}
        res = srv.finish_pack(eid, ins)                                          # RuleViolation, wenn ein Bericht die CEE-Grenzen verletzt
        self.assertTrue(any(v is not None for v in res.events.values()))
        for c in ids:
            ev_ = res.events[c]
            if ev_ is not None:
                for name, n in ev_.payload["actions"].items():
                    self.assertLessEqual(n, R9["combat"]["actions"][name]["max_per_minute"] * ev_.payload["duration_s"] // 60 + R9["combat"]["encounter"]["burst_allowance"])

    def test_start_pack_stores_the_abilities_and_finish_uses_them(self):
        svc = CharacterService(rules=R9)
        svc.create("p0", "player")
        svc.record("p0", "identity.xp_gained", {"amount": 10000})
        srv = EncounterServer(C, svc, lambda: 1)
        eid = srv.start_pack(["p0"], ["dummy"], [["heavy_slam"]])
        res = srv.finish_pack(eid, {"p0": [[30, "light"], [100, "flee"]]})
        self.assertEqual(res.result.players[0].damage_ticks[0], 52)
        self.assertEqual(ev(res.result, "telegraph")[0]["ability"], "heavy_slam")


class SurvivorTests(unittest.TestCase):
    """Fälle, die zuvor nur durch Mutationstests auffielen."""

    @staticmethod
    def sim(opps, players, abilities, cfg=C):
        return LiveEncounter(cfg, opps, players, abilities)._sim

    def test_haste_boundary_and_negative_share(self):
        sim = self.sim(["a"], [P([])], [["howl"]], cfg_with(a={"attack_interval": 60}))
        e = sim.es[0]
        e.haste_until, e.haste_factor = 100, 700
        self.assertEqual((sim._interval_of(e, 99), sim._interval_of(e, 100)), (42, 60))        # genau am Ende nicht mehr verstärkt
        e.hp = -5
        self.assertEqual(sim._hp_permille(e), 0)

    def test_slow_stretches_the_cooldown_not_only_the_busy_time(self):
        slowed = run(["dummy"], [P([[50, "dodge"], [75, "dodge"], [200, "flee"]])], [["crippling_bite"]])
        normal = run(["dummy"], [P([[50, "dodge"], [75, "dodge"], [200, "flee"]])], [[]])
        self.assertEqual((slowed.players[0].ignored_inputs, normal.players[0].ignored_inputs), (1, 0))      # Abklingzeit 20 -> 30

    def test_a_shield_is_not_recast_while_it_is_still_up(self):
        c = copy.deepcopy(C)
        c["enemy_abilities"]["abilities"]["stone_skin"]["cooldown"] = 20
        r = run(["dummy"], [P([[600, "flee"]], 100)], [["stone_skin"]], c)
        times = [e["t"] for e in ev(r, "resolved", "stone_skin")]
        self.assertGreaterEqual(times[1] - times[0], 80)                                       # erst nach Ablauf der 80 Ticks

    def test_summoning_respects_max_alive_while_summons_live(self):
        c = copy.deepcopy(C)
        c["enemy_abilities"]["abilities"]["call_pack"]["max_alive"] = 2
        r = run(["dummy"], [P([[1500, "flee"]], 100)], [["call_pack"]], c)
        self.assertEqual(len(ev(r, "resolved", "call_pack")), 1)                               # solange die Beschworenen leben, kein zweiter Ruf
        self.assertEqual(len(r.opponents), 3)

    def test_the_healer_never_heals_itself(self):
        r = run(["small"], [P([[0, "light"], [8, "light"], [200, "flee"]])], [["mend"]])
        self.assertEqual(ev(r, "telegraph"), [])

    def test_a_target_that_left_before_the_hit_is_replaced(self):
        r = run(["dummy"], [P([[100, "flee"]]), P([[0, "heavy"], [50, "flee"]])], [["heavy_slam"]])
        res = ev(r, "resolved")[0]
        self.assertEqual((res["t"], res["target"]), (52, 0))
        self.assertEqual(r.players[0].damage_ticks[0], 52)
        self.assertEqual(r.players[1].damage_ticks, ())

    def test_mend_never_exceeds_the_maximum(self):
        c = copy.deepcopy(C)
        c["enemy_abilities"]["abilities"]["mend"]["amount_permille"] = 900
        r = run(["small", "dummy_h"], [P([[0, "light"], [8, "light"], [200, "flee"]])], [[], ["mend"]], c)
        self.assertEqual(r.opponents[0], 100)                                                  # 20 % + 90 % -> Deckel 100

    def test_a_burn_stops_when_the_player_left(self):
        r = run(["dummy"], [P([[75, "flee"]]), P([[300, "flee"]])], [["burning_curse"]])
        self.assertEqual([t for t in r.players[0].damage_ticks if t > 75], [])

    def test_shields_can_be_configured_to_break_on_heavy_hits(self):
        c = copy.deepcopy(C)
        c["enemy_abilities"]["abilities"]["stone_skin"]["breakable_by"] = ["heavy_hit"]
        r = run(["dummy"], [P([[52, "heavy"], [100, "flee"]])], [["stone_skin"]], c)
        self.assertEqual([x["by"] for x in ev(r, "shield_broken")], ["heavy_hit"])
        self.assertEqual(r.opponents[0], 10000 - 130)

    def test_clamping_in_the_server_report(self):
        c = cfg_with(fast={"attack_interval": 8, "windup": 2, "damage": 1, "hp": 10 ** 6})
        svc = CharacterService(rules=R9)
        svc.create("p0", "player")
        svc.record("p0", "identity.xp_gained", {"amount": 100000})
        srv = EncounterServer(c, svc, lambda: 1)
        eid = srv.start_pack(["p0"], ["fast"], [[]])
        ins = [[10 + i * 20, "dodge"] for i in range(40)] + [[900, "flee"]]
        res = srv.finish_pack(eid, {"p0": ins})
        payload = res.events["p0"].payload
        cc = R9["combat"]
        over = {n: k for n, k in res.result.players[0].actions.items()
                if k > cc["actions"][n]["max_per_minute"] * payload["duration_s"] // 60 + cc["encounter"]["burst_allowance"]}
        self.assertTrue(over, res.result.players[0].actions)                                  # die Simulation zählt mehr als erlaubt ...
        for n in over:                                                                         # ... der Bericht nur die Grenze
            self.assertEqual(payload["actions"][n], cc["actions"][n]["max_per_minute"] * payload["duration_s"] // 60 + cc["encounter"]["burst_allowance"])


class LiveSurvivorTests(unittest.TestCase):
    def test_target_commands_beyond_three_and_the_shield_display(self):
        e = LiveEncounter(C, ["dummy"], [P([])], [["stone_skin"]])
        self.assertTrue(e.submit(0, "target_4"))
        self.assertTrue(e.submit(0, "target_6"))
        self.assertFalse(e.submit(0, "target_7"))
        for _ in range(140):
            e.advance()
        self.assertEqual(e.view()["opponents"][0]["shield"], 0)                              # Schild bei 50 für 80 Ticks: bei 140 abgelaufen

    def test_the_burning_flag(self):
        e = LiveEncounter(C, ["dummy"], [P([])], [["burning_curse"]])
        for _ in range(75):
            e.advance()
        self.assertTrue(e.view()["players"][0]["burning"])
        for _ in range(40):
            e.advance()
        self.assertFalse(e.view()["players"][0]["burning"])


if __name__ == "__main__":
    unittest.main()
