import copy
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.combat import (CombatEngine, ability_blockers, ability_catalog, allowed_commands, loadout_slots,
                            reached_directions, unlocked_abilities, validate_combat_rules)
from mmo_cee.errors import CEEError
from mmo_cee.history import EventLog
from mmo_cee.rules import Rules, load_rules, older_rules
from mmo_server import Gateway, Sessions
from mmo_sim import EncounterServer
from mmo_sim.fight import simulate
from mmo_sim.rules import load_sim_rules
from mmo_world import World, persistence

R8, R9 = load_rules("rules_v8.json"), load_rules("rules_v9.json")
EV, LO = "combat.encounter_resolved", "combat.loadout_set"
MIX = {"heavy_hit": 35, "block": 28, "stun_applied": 9, "slow_applied": 18}


def enc(eid, day, actions, opp="wolf", lvl=5):
    return {"encounter_id": eid, "opponent_type": opp, "opponent_level": lvl, "outcome": "victory", "duration_s": 60, "day": day,
            "actions": actions}


def trained(rules=R9, days=8, xp=10000, actions=MIX, cid="c", lvl=5):
    svc = CharacterService(rules=rules)
    svc.create(cid, "player")
    svc.record(cid, "identity.xp_gained", {"amount": xp})
    for day in range(1, days + 1):
        for i in range(6):
            svc.record(cid, EV, enc(f"d{day}-{i}", day, actions, opp=f"mob{i}", lvl=lvl))
    return svc


def loadout(abilities, day=9):
    return {"abilities": abilities, "day": day}


class RulesTests(unittest.TestCase):
    def bad(self, mutate):
        data = copy.deepcopy(R9.data)
        mutate(data["combat"])
        with self.assertRaises(CEEError):
            validate_combat_rules(data["combat"])

    def test_shipped_rules_are_consistent_and_older_ones_have_no_abilities(self):
        validate_combat_rules(R9["combat"])
        for v in ("2", "3", "4", "5", "6", "7", "8"):
            self.assertNotIn("abilities", load_rules(f"rules_v{v}.json")["combat"])

    def test_validation_rejects_broken_catalogs(self):
        self.bad(lambda c: c["abilities"].update(bad={"kind": "x", "requires": {"direction": "ghost", "tier": 1}, "command": None}))
        self.bad(lambda c: c["abilities"].update(bad={"kind": "x", "requires": {"direction": "vanguard", "tier": 4}, "command": None}))
        self.bad(lambda c: c["abilities"].update(bad={"kind": "x", "requires": {"direction": "vanguard", "tier": 0}, "command": None}))
        self.bad(lambda c: c["abilities"].update(bad={"kind": "x", "requires": {"tier": 1}, "command": None}))
        self.bad(lambda c: c["abilities"].update(bad={"kind": "x", "requires": {"fame": 1}, "command": None}))
        self.bad(lambda c: c["abilities"].update(bad={"kind": "x", "requires": {"min_level": 0}, "command": None}))
        self.bad(lambda c: c["abilities"].update(bad={"kind": "x", "requires": {}, "command": "heavy"}))  # Befehl schon vergeben
        self.bad(lambda c: c["abilities"].update(bad={"kind": "x", "requires": {}, "command": "light"}))  # Grundbefehl
        self.bad(lambda c: c["loadout"].update(base_commands=["light", "dodge"]))  # flee fehlt
        self.bad(lambda c: c["loadout"].update(base_commands=["light", "light", "flee"]))
        self.bad(lambda c: c["loadout"].update(slots_by_level=[[2, 2]]))
        self.bad(lambda c: c["loadout"].update(slots_by_level=[[1, 0]]))
        self.bad(lambda c: c["loadout"].update(slots_by_level=[[1, 3], [10, 2]]))
        self.bad(lambda c: c["loadout"].update(slots_by_level=[[1, 2], [1, 3]]))
        self.bad(lambda c: c.update(abilities={"_comment": "leer"}))

    def test_shipped_commands_are_the_sim_commands(self):
        from mmo_sim.rules import COMMANDS
        for a in ability_catalog(R9).values():
            self.assertTrue(a["command"] is None or a["command"] in COMMANDS)
        base = R9["combat"]["loadout"]["base_commands"]
        granted = {a["command"] for a in ability_catalog(R9).values() if a["command"]}
        self.assertEqual(set(COMMANDS), set(base) | granted)  # jeder Simulationsbefehl ist Grund- oder Fähigkeitsbefehl


class UnlockTests(unittest.TestCase):
    def test_direction_tier_unlocks(self):
        svc = trained()
        st = svc.state("c")
        self.assertEqual(reached_directions(st, R9)["vanguard"], 1)
        self.assertEqual(ability_blockers(st, R9, "power_strike"), [])
        self.assertEqual(ability_blockers(st, R9, "riposte"), ["direction:guardian>=2"])
        self.assertEqual(ability_blockers(st, R9, "ember_strike"), ["direction:vanguard>=2", "attuned:fire"])
        self.assertEqual(ability_blockers(st, R9, "veteran_focus"), ["level>=15"])
        self.assertEqual(ability_blockers(st, R9, "twilight_veil"), ["form:twilight_kin"])
        self.assertIn("power_strike", unlocked_abilities(st, R9))
        self.assertNotIn("riposte", unlocked_abilities(st, R9))

    def test_fresh_character_has_nothing_and_view_reports_missing(self):
        svc = CharacterService(rules=R9)
        svc.create("n", "player")
        self.assertEqual(svc.unlocked_abilities("n"), [])
        prog = svc.abilities("n")
        self.assertEqual(set(prog), set(ability_catalog(R9)))
        self.assertEqual(prog["power_strike"], {"kind": "attack", "command": "heavy", "missing": ["direction:vanguard>=1"], "equipped": False})
        self.assertEqual(svc.allowed_commands("n"), ["block", "dodge", "flee", "light"])
        self.assertEqual(svc.loadout_slots("n"), 2)

    def test_level_and_element_and_form_requirements(self):
        svc = trained(xp=100000)
        self.assertGreaterEqual(svc.state("c").parts["identity"]["level"], 15)
        self.assertIn("veteran_focus", svc.unlocked_abilities("c"))
        svc.record("c", "element.exposure", {"element": "fire", "amount": 100})
        svc.record("c", "element.attuned", {"element": "fire"})
        self.assertEqual(ability_blockers(svc.state("c"), R9, "ember_strike"), ["direction:vanguard>=2"])

    def test_level_requirement_is_inclusive(self):
        fake = copy.deepcopy(trained().state("c"))
        for level, missing in ((14, ["level>=15"]), (15, []), (16, [])):
            fake.parts["identity"]["level"] = level
            self.assertEqual(ability_blockers(fake, R9, "veteran_focus"), missing, level)

    def test_unlocks_are_permanent_as_progress_never_shrinks(self):
        svc = trained()
        before = svc.unlocked_abilities("c")
        for i in range(20):  # Niederlagen und Flucht nehmen nichts weg
            svc.record("c", EV, {**enc(f"x{i}", 9 + i // 6, {"light_hit": 5}, opp=f"m{i % 6}"), "outcome": "defeat"})
        self.assertTrue(set(before) <= set(svc.unlocked_abilities("c")))


class LoadoutEventTests(unittest.TestCase):
    def setUp(self):
        self.svc = trained()

    def rec(self, abilities, day=9):
        return self.svc.record("c", LO, loadout(abilities, day))

    def test_accepts_unlocked_abilities_and_resetting(self):
        self.rec(["power_strike", "disrupting_blow"])
        self.assertEqual(self.svc.state("c").parts["combat"]["loadout"], ["power_strike", "disrupting_blow"])
        self.rec(["power_strike", "disrupting_blow"])
        self.rec([], 10)
        self.assertEqual((self.svc.state("c").parts["combat"]["loadout"], self.svc.state("c").parts["combat"]["loadout_day"]), ([], 10))
        self.rec(["hindering_mark"], 10)  # gleicher Tag ist erlaubt

    def test_rejections_record_nothing(self):
        n = len(self.svc.log.events("c"))
        bad = [loadout(["power_strike", "power_strike"]), loadout(["fireball"]), loadout(["_comment"]), loadout(["riposte"]),
               loadout(["ember_strike"]), loadout(["veteran_focus"]), loadout(["twilight_veil"]),
               loadout(["hindering_mark", "power_strike", "shield_wall", "disrupting_blow"]),  # 4 > 3 Plätze
               loadout("power_strike"), loadout(["power_strike", 5]), loadout([None]), loadout(["power_strike"], -1),
               loadout(["power_strike"], True), loadout(["power_strike"], 1.5), loadout(["power_strike"], "9"),
               {"abilities": ["power_strike"]}, {"day": 9}, {**loadout(["power_strike"]), "slot": 1}, {}]
        for p in bad:
            with self.subTest(p=p):
                with self.assertRaises(RuleViolation):
                    self.svc.record("c", LO, p)
        self.rec([], 12)
        with self.assertRaisesRegex(RuleViolation, "zurückspringen"):
            self.rec(["power_strike"], 11)
        self.assertEqual(len(self.svc.log.events("c")), n + 1)

    def test_slots_follow_the_level_table(self):
        self.assertEqual([loadout_slots(self.svc.state("c"), R9)], [3])
        # exakte Grenzen über die Tabelle
        for level, want in ((1, 2), (9, 2), (10, 3), (24, 3), (25, 4), (50, 4)):
            fake = copy.deepcopy(self.svc.state("c"))
            fake.parts["identity"]["level"] = level
            self.assertEqual(loadout_slots(fake, R9), want, level)

    def test_four_slots_at_high_level(self):
        s = trained(xp=10**7, lvl=50)
        self.assertEqual(s.loadout_slots("c"), 4)
        s.record("c", LO, loadout(["power_strike", "disrupting_blow", "hindering_mark", "veteran_focus"]))

    def test_replay_gives_the_same_state_and_commands(self):
        self.rec(["power_strike", "hindering_mark"])
        again = CharacterService(rules=R9, log=EventLog.from_json("c", self.svc.log.to_json("c")))
        self.assertEqual(again.state("c").parts, self.svc.state("c").parts)
        self.assertEqual(again.allowed_commands("c"), ["block", "dodge", "flee", "heavy", "light", "slow"])

    def test_old_rules_do_not_know_the_event_and_keep_their_state_shape(self):
        old = trained(rules=R8)
        self.assertNotIn("loadout", old.state("c").parts["combat"])
        with self.assertRaisesRegex(RuleViolation, "Unbekannter Ereignistyp"):
            old.record("c", LO, loadout(["power_strike"]))
        self.assertIsNone(old.allowed_commands("c"))
        self.assertEqual((old.abilities("c"), old.unlocked_abilities("c"), old.loadout_slots("c")), ({}, [], 0))

    def test_equipped_but_never_unlocked_cannot_happen_and_unequipped_grants_nothing(self):
        self.assertEqual(allowed_commands(self.svc.state("c"), R9), ["block", "dodge", "flee", "light"])
        self.rec(["shield_wall"])  # Fähigkeit ohne Simulationsbefehl
        self.assertEqual(allowed_commands(self.svc.state("c"), R9), ["block", "dodge", "flee", "light"])
        self.rec(["power_strike"])
        self.assertIn("heavy", allowed_commands(self.svc.state("c"), R9))
        self.assertNotIn("stun", allowed_commands(self.svc.state("c"), R9))


class SimGatingTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_sim_rules()

    def test_disallowed_commands_are_ignored_but_flee_always_works(self):
        inputs = [[0, "heavy"], [20, "stun"], [40, "light"], [60, "flee"]]
        free = simulate(self.cfg, "wolf", 1, inputs)
        base = simulate(self.cfg, "wolf", 1, inputs, ["light", "dodge", "block", "flee"])
        self.assertEqual((free.ignored_inputs, base.ignored_inputs), (0, 2))
        self.assertEqual(base.actions, {"light_hit": 1})
        self.assertEqual(simulate(self.cfg, "wolf", 1, [[0, "flee"]], []).outcome, "fled")
        self.assertEqual(simulate(self.cfg, "wolf", 1, inputs, None), free)  # None = bisheriges Verhalten

    def test_allowed_is_validated(self):
        from mmo_sim.errors import SimError
        for bad in ("light", ["fireball"], [5], 7, ["light", None]):
            with self.assertRaises(SimError):
                simulate(self.cfg, "wolf", 1, [[0, "light"]], bad)

    def test_encounter_server_uses_the_equipment_of_the_figure(self):
        svc = trained(days=8)
        day = [9]
        srv = EncounterServer(self.cfg, svc, lambda: day[0])
        inputs = [[0, "heavy"], [20, "heavy"], [40, "light"], [60, "flee"]]
        e1 = srv.start("c", "training_dummy")
        r1 = srv.finish("c", e1, inputs)
        self.assertEqual(r1.result.ignored_inputs, 2)  # nichts ausgerüstet
        svc.record("c", LO, loadout(["power_strike"]))
        e2 = srv.start("c", "training_dummy")
        r2 = srv.finish("c", e2, inputs)
        self.assertEqual((r2.result.ignored_inputs, r2.result.actions.get("heavy_hit")), (0, 2))
        old = trained(rules=R8, cid="o")  # Regeln ohne Fähigkeiten: alles erlaubt (bisheriges Verhalten)
        e3 = EncounterServer(self.cfg, old, lambda: 9)
        eid = e3.start("o", "training_dummy")
        self.assertEqual(e3.finish("o", eid, inputs).result.ignored_inputs, 0)


class MigrationV9Tests(unittest.TestCase):
    def test_v8_character_migrates_with_empty_loadout_and_keeps_progress(self):
        old = trained(rules=R8)
        svc = CharacterService(rules=R9, log=old.log, history_rules=older_rules(R9))
        before = copy.deepcopy(svc.state("c").parts["combat"])
        self.assertEqual(svc.allowed_commands("c"), None)  # v8: Fähigkeiten gibt es noch nicht
        svc.migrate("c")
        after = svc.state("c").parts["combat"]
        self.assertEqual((after["loadout"], after["loadout_day"]), ([], 0))
        self.assertEqual({k: v for k, v in after.items() if k not in ("loadout", "loadout_day")}, before)
        self.assertIn("power_strike", svc.unlocked_abilities("c"))  # Fortschritt zählt sofort
        svc.record("c", LO, loadout(["power_strike"]))
        fresh = CharacterService(rules=R9, log=svc.log, history_rules=older_rules(R9))
        self.assertEqual(fresh.state("c").parts, svc.state("c").parts)

    def test_world_upgrade_from_v7_walks_through_v8_to_v9(self):
        w = World()  # v7
        w.svc.create("a", "player")
        w.svc.record("a", "identity.xp_gained", {"amount": 500})
        new = persistence.upgrade_world(w, "rules_v9.json")
        evs = [e for e in new.svc.log.events("a") if e.type == "identity.rules_migrated"]
        self.assertEqual([(e.payload["from"], e.payload["to"]) for e in evs], [("7", "8"), ("8", "9")])
        self.assertEqual(new.svc.state("a").parts["combat"]["loadout"], [])
        self.assertIsNotNone(new.pricing)
        e, logs = persistence.export_world(new)
        self.assertEqual(persistence.import_world(e, logs).snapshot(), new.snapshot())


class GatewayTests(unittest.TestCase):
    def test_set_loadout_via_gateway(self):
        src = trained()
        w = World("rules_v9.json")
        w.svc.log.adopt("c", src.log.events("c"))
        w.day[0] = 9
        s = Sessions()
        sa = s.open("acc", ["c"])
        so = s.open("other", ["z"])
        g = Gateway(w, s, lambda: 0)
        ok = g.handle(sa, {"v": 1, "id": "1", "cmd": "combat.set_loadout", "args": {"char": "c", "abilities": ["power_strike", "hindering_mark"]}})
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(w.svc.state("c").parts["combat"]["loadout_day"], 9)  # Tag setzt der Server
        self.assertEqual(g.handle(so, {"v": 1, "id": "2", "cmd": "combat.set_loadout", "args": {"char": "c", "abilities": []}})["error"]["code"], "forbidden")
        r = g.handle(sa, {"v": 1, "id": "3", "cmd": "combat.set_loadout", "args": {"char": "c", "abilities": ["riposte"]}})
        self.assertEqual(r["error"]["code"], "rejected_by_rules")
        for bad in ("power_strike", [1], ["a"] * 17, None, [""]):
            r = g.handle(sa, {"v": 1, "id": "4", "cmd": "combat.set_loadout", "args": {"char": "c", "abilities": bad}})
            self.assertEqual(r["error"]["code"], "bad_request", bad)
        r = g.handle(sa, {"v": 1, "id": "5", "cmd": "combat.set_loadout", "args": {"char": "c", "abilities": [], "day": 1}})
        self.assertEqual(r["error"]["code"], "bad_request")  # Zeit kommt nie vom Client
        q = g.handle(sa, {"v": 1, "id": "6", "cmd": "query.abilities", "args": {"char": "c"}})
        self.assertTrue(q["result"]["power_strike"]["equipped"])


if __name__ == "__main__":
    unittest.main()
