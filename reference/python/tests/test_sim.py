import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.rules import load_rules
from mmo_sim import EncounterServer, SimError, build_report, load_sim_rules, simulate
from mmo_sim.fight import validate_inputs
from mmo_sim.rules import COMMANDS, check_compatibility, max_actions_per_minute, validate_sim_rules

CFG = load_sim_rules()
EV = "combat.encounter_resolved"


def lights(n, step=8, start=0):
    return [[start + i * step, "light"] for i in range(n)]


class SimRulesTests(unittest.TestCase):
    def test_shipped_rules_valid_and_compatible_with_cee(self):
        validate_sim_rules(CFG)
        self.assertEqual(check_compatibility(CFG, load_rules()), [])

    def test_incompatible_rules_are_reported(self):
        bad = copy.deepcopy(CFG)
        bad["actions"]["light"]["busy"] = 1  # 600 Treffer/min > CEE-Limit 120
        self.assertTrue(any(p.startswith("light_hit") for p in check_compatibility(bad, load_rules())))
        bad = copy.deepcopy(CFG)
        bad["opponents"]["wolf"]["attack_interval"] = 5  # schnelle Angriffe -> Defensivzähler zu hoch
        self.assertTrue(any(p.startswith(("dodge", "perfect_dodge", "block", "parry")) for p in check_compatibility(bad, load_rules())))
        bad = copy.deepcopy(CFG)
        bad["max_ticks"] = 100000
        self.assertTrue(any("Dauer" in p for p in check_compatibility(bad, load_rules())))

    def test_invalid_rules_rejected(self):
        for mutate in (
            lambda c: c.update(ticks_per_second=0),
            lambda c: c["actions"].pop("slow"),
            lambda c: c["actions"]["precise"].update(busy=1),
            lambda c: c["opponents"]["wolf"].update(hp=0),
            lambda c: c["opponents"]["wolf"].update(windup=0),
        ):
            bad = copy.deepcopy(CFG)
            mutate(bad)
            with self.assertRaises(SimError):
                validate_sim_rules(bad)


class SimFightTests(unittest.TestCase):
    def test_light_attacks_kill_dummy(self):
        r = simulate(CFG, "training_dummy", 1, lights(20))
        self.assertEqual((r.outcome, r.actions), ("victory", {"light_hit": 13}))  # 13 * 40 >= 500
        self.assertEqual(r.ticks, 12 * 8 + 1)
        self.assertEqual(r.player_hp, 1020)
        self.assertEqual(r.damage_ticks, ())

    def test_inputs_while_busy_are_ignored_not_counted(self):
        spam = [[t, "light"] for t in range(200)]
        r_spam = simulate(CFG, "training_dummy", 1, spam)
        r_clean = simulate(CFG, "training_dummy", 1, lights(20))
        self.assertEqual(r_spam.actions, r_clean.actions)
        self.assertEqual(r_spam.ignored_inputs, 97 - 13)  # 97 Befehle bis zum Sieg, 13 ausgeführt

    def test_heavy_resolves_after_windup(self):
        r = simulate(CFG, "wolf", 1, [[0, "heavy"], [20, "heavy"], [40, "heavy"]])
        self.assertEqual(r.actions["heavy_hit"], 3 if r.opponent_hp <= 0 else r.actions["heavy_hit"])
        self.assertEqual(r.outcome, "victory")  # 3 * 130 = 390 >= 300 -> beim dritten Treffer (Tick 46)
        self.assertEqual(r.ticks, 47)

    def test_dodge_windows(self):
        # Wolf: Anlauf ab Tick 35, Treffer bei Tick 40, Ausweichfenster 4 Ticks
        expect = {36: None, 37: "dodge", 38: "dodge", 39: "perfect_dodge", 40: "perfect_dodge"}
        for start, action in expect.items():
            r = simulate(CFG, "wolf", 1, [[start, "dodge"], [100, "flee"]])
            if action is None:
                self.assertEqual(r.actions, {}, start)
                self.assertEqual(r.damage_ticks[:1], (40,))
            else:
                self.assertEqual(r.actions, {action: 1}, start)
                self.assertNotIn(40, r.damage_ticks)

    def test_block_and_parry(self):
        r = simulate(CFG, "wolf", 1, [[37, "block"], [100, "flee"]])
        self.assertEqual(r.actions, {"block": 1})
        self.assertEqual(r.damage_ticks[:1], (40,))
        self.assertEqual(r.player_hp, 1020 - 60 * 250 // 1000 - 60)  # Block-Treffer + späterer ungeblockter Treffer (Tick 80)
        r = simulate(CFG, "wolf", 1, [[39, "block"], [100, "flee"]])
        self.assertEqual(r.actions, {"parry": 1})
        self.assertNotIn(40, r.damage_ticks)

    def test_parry_staggers_and_enables_precise_hit(self):
        r = simulate(CFG, "wolf", 1, [[39, "block"], [48, "light"], [100, "flee"]])  # Stagger bis Tick 50
        self.assertEqual(r.actions, {"parry": 1, "precise_hit": 1})
        self.assertEqual(r.opponent_hp, 300 - 90)
        r = simulate(CFG, "wolf", 1, [[39, "block"], [60, "light"], [100, "flee"]])  # Stagger vorbei
        self.assertEqual(r.actions, {"parry": 1, "light_hit": 1})

    def test_stun_cancels_attack_and_makes_vulnerable(self):
        r = simulate(CFG, "wolf", 1, [[38, "stun"], [46, "light"], [200, "flee"]])  # Angriff läuft, Betäubung bis 53
        self.assertEqual(r.actions, {"stun_applied": 1, "precise_hit": 1})
        self.assertNotIn(40, r.damage_ticks)
        self.assertGreaterEqual(r.damage_ticks[0] if r.damage_ticks else 10**9, 53 + 35)

    def test_slow_delays_next_attack(self):
        base = simulate(CFG, "wolf", 1, [[0, "light"], [300, "flee"]])
        slow = simulate(CFG, "wolf", 1, [[10, "slow"], [300, "flee"]])  # wirkt bis Tick 50, also beim Treffer um 40
        self.assertEqual(base.damage_ticks[:2], (40, 80))  # Intervall 35 + Anlauf 5
        self.assertEqual(slow.damage_ticks[0], 40)
        self.assertEqual(slow.damage_ticks[1] - slow.damage_ticks[0], 35 * 1500 // 1000 + 5)

    def test_stamina_limits_actions(self):
        # Ausdauer 100, Heavy kostet 25, Regeneration 1/Tick (+20 je Heavy-Zyklus): netto -5 je Schlag.
        cfg = copy.deepcopy(CFG)
        cfg["opponents"]["training_dummy"]["hp"] = 10**9  # stirbt nicht, damit die Erschöpfung sichtbar wird
        r = simulate(cfg, "training_dummy", 1, [[t, "heavy"] for t in range(0, 6000, 20)])
        self.assertGreater(r.ignored_inputs, 0)
        self.assertLess(r.actions["heavy_hit"], 300)
        self.assertLess(r.actions["heavy_hit"], 6000 // 20)

    def test_flee_and_timeout(self):
        r = simulate(CFG, "training_dummy", 1, [[7, "flee"]])
        self.assertEqual((r.outcome, r.ticks, r.actions), ("fled", 7, {}))
        r = simulate(CFG, "training_dummy", 1, [])
        self.assertEqual((r.outcome, r.ticks), ("fled", CFG["max_ticks"]))

    def test_idle_player_loses_to_attacker(self):
        r = simulate(CFG, "bear", 1, [])
        self.assertEqual((r.outcome, r.actions), ("defeat", {}))
        self.assertLessEqual(r.player_hp, 0)

    def test_higher_level_has_more_hp(self):
        lo = simulate(CFG, "bear", 1, [])
        hi = simulate(CFG, "bear", 30, [])
        self.assertGreater(hi.ticks, lo.ticks)

    def test_deterministic(self):
        inputs = [[t, COMMANDS[t % 6]] for t in range(0, 800, 3)]
        results = {repr(simulate(CFG, "bear", 7, inputs)) for _ in range(5)}
        self.assertEqual(len(results), 1)

    def test_input_validation(self):
        bad_inputs = [
            "light", [[0]], [[0, "light", 1]], [[-1, "light"]], [[1.5, "light"]], [[True, "light"]],
            [["0", "light"]], [[6000, "light"]], [[5, "light"], [4, "light"]], [[0, "fireball"]], [[0, None]],
            [[0, "light"]] * 5001,
        ]
        for inputs in bad_inputs:
            with self.subTest(inputs=str(inputs)[:40]):
                with self.assertRaises(SimError):
                    simulate(CFG, "wolf", 1, inputs)
        for opp in ("dragon", None, ""):
            with self.assertRaises(SimError):
                simulate(CFG, opp, 1, [])
        for lvl in (0, -1, 1.5, "3", True):
            with self.assertRaises(SimError):
                simulate(CFG, "wolf", lvl, [])
        self.assertEqual(validate_inputs(CFG, []), [])


def pseudo_random_inputs(seed, n):
    """Deterministischer LCG: abwechslungsreiche, aggressive Eingabemuster ohne Zufall im Test."""
    x, t, out = seed, 0, []
    for _ in range(n):
        x = (1103515245 * x + 12345) % 2**31
        t += x % 4
        x = (1103515245 * x + 12345) % 2**31
        out.append([t, COMMANDS[x % 6]])  # ohne "flee"
    return [i for i in out if i[0] < CFG["max_ticks"]]


class SimNeverViolatesCeeLimitsTests(unittest.TestCase):
    """Kerneigenschaft: Kein Eingabemuster kann einen von der CEE abgelehnten Bericht erzeugen."""

    def setUp(self):
        self.svc = CharacterService()
        self.n = 0

    def accept(self, opponent, inputs, level=1):
        self.n += 1
        cid = f"c{self.n}"
        self.svc.create(cid, "player")
        if level > 1:
            self.svc.record(cid, "identity.xp_gained", {"amount": (level - 1) ** 2 * 100})
        lvl = self.svc.state(cid).parts["identity"]["level"]
        result = simulate(CFG, opponent, lvl, inputs)
        if not result.actions:
            return result
        report = build_report(CFG, f"t-{self.n}", opponent, 1, result)
        try:
            self.svc.record(cid, EV, report)
        except RuleViolation as e:  # pragma: no cover - nur im Fehlerfall
            self.fail(f"CEE lehnt Simulationsbericht ab: {e}\n{report}")
        return result

    def test_spam_every_command_every_tick(self):
        for opp in CFG["opponents"]:
            spam = [[t, c] for t in range(0, 6000, 1) for c in COMMANDS if c != "flee"]
            self.accept(opp, spam[:5000])

    def test_spam_each_single_command(self):
        for opp in CFG["opponents"]:
            for cmd in COMMANDS:
                if cmd == "flee":
                    continue
                self.accept(opp, [[t, cmd] for t in range(0, 5000)])

    def test_defensive_timing_sweeps(self):
        for opp in ("wolf", "bear", "stone_golem"):
            for cmd in ("dodge", "block"):
                for offset in range(0, 12):
                    inputs = [[t, cmd] for t in range(offset, 3000, 12)]
                    self.accept(opp, inputs)

    def test_many_pseudo_random_patterns(self):
        for seed in range(1, 121):
            opp = list(CFG["opponents"])[seed % 4]
            self.accept(opp, pseudo_random_inputs(seed, 2500), level=1 + seed % 40)


class EncounterServerTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()
        self.day = 1
        self.srv = EncounterServer(CFG, self.svc, lambda: self.day)
        self.svc.create("p", "player")

    def test_ids_are_unique_and_server_issued(self):
        self.svc.create("q", "player")
        ids = [self.srv.start(c, "wolf") for c in ("p", "q", "p", "q")]
        self.assertEqual(len(set(ids)), 4)
        self.assertTrue(all(i.startswith("srv1-enc-") for i in ids))

    def test_finish_records_cee_event_from_simulation(self):
        eid = self.srv.start("p", "training_dummy")
        out = self.srv.finish("p", eid, lights(20))
        self.assertEqual(out.event.type, EV)
        pl = out.event.payload
        self.assertEqual((pl["encounter_id"], pl["opponent_level"], pl["day"], pl["outcome"]), (eid, 1, 1, "victory"))
        self.assertEqual(pl["actions"], {"light_hit": 13})
        self.assertEqual(pl["duration_s"], 10)  # 97 Ticks = 9,7 s -> aufgerundet 10 s
        self.assertEqual(self.svc.state("p").parts["combat"]["points"]["precision"], 13 * 100)

    def test_cannot_finish_twice(self):
        eid = self.srv.start("p", "training_dummy")
        self.srv.finish("p", eid, lights(20))
        n = len(self.svc.log.events("p"))
        for _ in range(5):
            with self.assertRaisesRegex(SimError, "bereits abgeschlossen"):
                self.srv.finish("p", eid, lights(20))
        self.assertEqual(len(self.svc.log.events("p")), n)

    def test_wrong_owner_unknown_id_and_unstarted(self):
        self.svc.create("q", "player")
        eid = self.srv.start("p", "wolf")
        with self.assertRaises(SimError):
            self.srv.finish("q", eid, [[10, "flee"]])
        with self.assertRaises(SimError):
            self.srv.finish("p", "srv1-enc-99999999", [])
        with self.assertRaises(SimError):
            self.srv.finish("p", "made-up-by-client", [])
        self.srv.finish("p", eid, [[10, "flee"]])  # Besitzer darf weiterhin

    def test_invalid_inputs_keep_encounter_open(self):
        eid = self.srv.start("p", "wolf")
        with self.assertRaises(SimError):
            self.srv.finish("p", eid, [[0, "fireball"]])
        out = self.srv.finish("p", eid, [[39, "dodge"], [100, "flee"]])
        self.assertEqual(out.event.payload["actions"], {"perfect_dodge": 1})

    def test_start_validations(self):
        with self.assertRaises(SimError):
            self.srv.start("p", "dragon")
        with self.assertRaises(SimError):
            self.srv.start("ghost", "wolf")

    def test_no_actions_means_no_event_but_consumed(self):
        eid = self.srv.start("p", "training_dummy")
        out = self.srv.finish("p", eid, [[3, "flee"]])
        self.assertIsNone(out.event)
        self.assertEqual(len(self.svc.log.events("p")), 1)  # nur identity.created
        with self.assertRaises(SimError):
            self.srv.finish("p", eid, lights(3))

    def test_day_comes_from_server(self):
        eid = self.srv.start("p", "training_dummy")
        self.day = 9
        out = self.srv.finish("p", eid, lights(20))
        self.assertEqual(out.event.payload["day"], 1)  # Tag bei Beginn der Begegnung
        eid2 = self.srv.start("p", "training_dummy")
        self.assertEqual(self.srv.finish("p", eid2, lights(20)).event.payload["day"], 9)

    def test_dummy_farming_decays_to_floor_end_to_end(self):
        gains, last = [], 0
        for _ in range(60):
            eid = self.srv.start("p", "training_dummy")
            self.srv.finish("p", eid, lights(20))
            cur = self.svc.state("p").parts["combat"]["points"]["precision"]
            gains.append(cur - last)
            last = cur
        cap = load_rules()["combat"]["daily"]["hard_cap"]
        self.assertLessEqual(last, cap)
        self.assertEqual(gains[:6], [1300, 1300, 975, 650, 325, 130])  # Tabelle repeat_opponent_permille
        self.assertTrue(all(a >= b for a, b in zip(gains, gains[1:])))  # nie wieder ansteigend
        self.assertEqual(set(gains[5:]), {130})  # Untergrund 10 %
        self.assertLess(last, 15 * 1300)  # 60 Begegnungen bringen weniger als 15 volle
        self.day = 2
        eid = self.srv.start("p", "training_dummy")
        self.srv.finish("p", eid, lights(20))
        self.assertEqual(self.svc.state("p").parts["combat"]["points"]["precision"] - last, 1300)  # neuer Tag

    def test_npc_uses_same_pipeline_and_replay_is_identical(self):
        self.svc.create("n", "npc")
        for opp, inputs in (("wolf", [[39, "block"], [48, "light"], [100, "flee"]]),
                            ("training_dummy", lights(20)), ("bear", [[44, "dodge"], [150, "flee"]])):
            eid = self.srv.start("n", opp)
            self.srv.finish("n", eid, inputs)
        live = copy.deepcopy(self.svc.state("n").parts)
        self.assertEqual(live["identity"]["kind"], "npc")
        self.assertGreater(sum(live["combat"]["points"].values()), 0)
        self.assertEqual(self.svc.rebuild("n").parts, live)

    def test_same_inputs_same_reports_across_servers(self):
        outs = []
        for _ in range(2):
            svc = CharacterService()
            svc.create("p", "player")
            srv = EncounterServer(CFG, svc, lambda: 1)
            eid = srv.start("p", "bear")
            outs.append(srv.finish("p", eid, pseudo_random_inputs(7, 300)).event.hash)
        self.assertEqual(outs[0], outs[1])


if __name__ == "__main__":
    unittest.main()
