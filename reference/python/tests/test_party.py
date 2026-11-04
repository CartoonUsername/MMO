import copy
import json
import unittest

from mmo_server import Gateway, Sessions
from mmo_world import WorldError, persistence
from mmo_world.party import load_party_rules, validate_party_rules
from mmo_world.world import World

ORE = "iron_ore@standard"


def world(chars="abcdef"):
    w = World()
    for c in chars:
        w.svc.create(c, "player")
        w.svc.record(c, "identity.xp_gained", {"amount": 10000})
    return w


def team(w, leader="a", *others):
    w.parties.create(leader)
    for o in others:
        w.parties.accept(o, w.parties.invite(leader, o))


def kinds(w, cid):
    return [(i["kind"], i["data"]) for i in w.outbox.fetch(cid)["items"]]


class RulesTests(unittest.TestCase):
    def test_validation(self):
        w = world("a")
        pr = load_party_rules()
        validate_party_rules(pr, w.svc.rules)
        for key, bad in (("max_size", 1), ("max_size", 0), ("max_size", True), ("invite_days", 0), ("max_pending_invites_per_target", 0),
                         ("max_level_gap", -1), ("loot_modes", []), ("loot_modes", ["leader", "leader"]), ("loot_modes", ["x"]),
                         ("default_loot_mode", "finder_x"), ("requires_cee_rules_min", 99)):
            with self.subTest(key=key, bad=bad), self.assertRaises(WorldError):
                validate_party_rules(dict(pr, **{key: bad}), w.svc.rules)
        validate_party_rules(dict(pr, max_level_gap=0, max_size=2), w.svc.rules)

    def test_default_world_has_no_party_state_until_used(self):
        w = world("a")
        self.assertNotIn("parties", w.snapshot())
        w.parties.create("a")
        self.assertIn("parties", w.snapshot())


class InviteTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.p = self.w.parties

    def test_create_invite_accept(self):
        pid = self.p.create("a")
        self.assertEqual(pid, "srv1-party-00000001")
        self.assertEqual(self.p.view("a"), {"id": pid, "leader": "a", "members": ["a"], "loot": "round_robin"})
        iid = self.p.invite("a", "b")
        self.assertEqual(self.p.incoming("b")[0]["expires"], 3)
        self.assertEqual(self.p.accept("b", iid), pid)
        self.assertEqual(self.p.view("b")["members"], ["a", "b"])
        self.assertEqual(self.p.incoming("b"), [])
        self.assertEqual(self.p.check(), [])

    def test_refusals(self):
        with self.assertRaises(WorldError):
            self.p.create("ghost")
        self.p.create("a")
        for fn in (lambda: self.p.create("a"), lambda: self.p.invite("b", "c"), lambda: self.p.invite("a", "ghost"),
                   lambda: self.p.invite("a", "a")):
            with self.assertRaises(WorldError):
                fn()
        iid = self.p.invite("a", "b")
        with self.assertRaises(WorldError):
            self.p.invite("a", "b")                          # doppelt
        with self.assertRaises(WorldError):
            self.p.accept("c", iid)                          # nicht die Adressatin
        with self.assertRaises(WorldError):
            self.p.decline("c", iid)
        for bad in ("nope", None, 5):
            with self.assertRaises(WorldError):
                self.p.accept("b", bad)
        self.p.accept("b", iid)
        with self.assertRaises(WorldError):
            self.p.accept("b", iid)                          # erledigt
        with self.assertRaises(WorldError):
            self.p.invite("a", "b")                          # schon in der Gruppe

    def test_decline_notifies_inviter_and_frees_the_slot(self):
        self.p.create("a")
        iid = self.p.invite("a", "b")
        self.p.decline("b", iid)
        self.assertEqual(self.p.incoming("b"), [])
        self.assertEqual(kinds(self.w, "a"), [("party.invite_declined", {"invite": iid, "by": "b"})])
        self.assertEqual(kinds(self.w, "b")[0][0], "party.invited")
        self.p.invite("a", "b")

    def test_size_limit_applies_at_invite_and_accept(self):
        self.p.create("a")
        ids = [self.p.invite("a", c) for c in "bcd"]
        with self.subTest("an Einladungen liegt keine Grenze, wohl an Mitgliedern"):
            self.p.invite("a", "e")
        for c, i in zip("bcd", ids):
            self.p.accept(c, i)
        self.assertEqual(len(self.p.view("a")["members"]), 4)
        with self.assertRaises(WorldError):
            self.p.invite("a", "f")
        e_inv = self.p.incoming("e")[0]["id"]
        with self.assertRaises(WorldError):
            self.p.accept("e", e_inv)                        # Gruppe inzwischen voll
        self.assertEqual(self.p.check(), [])

    def test_pending_invite_limit_per_target(self):
        for c in "abcde":
            self.p.create(c)
        for c in "abcde":
            self.p.invite(c, "f")
        self.assertEqual(len(self.p.incoming("f")), 5)
        self.w.svc.create("g", "player")
        self.w.svc.record("g", "identity.xp_gained", {"amount": 10000})
        self.p.create("g")
        with self.assertRaises(WorldError):
            self.p.invite("g", "f")
        self.p.decline("f", self.p.incoming("f")[0]["id"])
        self.p.invite("g", "f")

    def test_accepting_removes_other_invites_of_that_character(self):
        self.p.create("a")
        self.p.create("b")
        i1, i2 = self.p.invite("a", "c"), self.p.invite("b", "c")
        self.p.accept("c", i1)
        self.assertEqual(self.p.incoming("c"), [])
        with self.assertRaises(WorldError):
            self.p.accept("c", i2)

    def test_level_gap_is_enforced_both_ways(self):
        w = world("ab")
        w.svc.create("hi", "player")
        w.svc.record("hi", "identity.xp_gained", {"amount": 100000})
        w.svc.create("lo", "player")
        w.parties.create("a")
        gap = w.parties.level_of("hi") - w.parties.level_of("a")
        self.assertGreater(gap, w.parties.pr["max_level_gap"])
        with self.assertRaises(WorldError):
            w.parties.invite("a", "hi")
        # genau an der Grenze ist erlaubt: a (Stufe 11) und lo (Stufe 1) liegen 10 auseinander
        w.parties.accept("lo", w.parties.invite("a", "lo"))
        # Einladung vor dem Beitritt eines Dritten: der Abstand wird bei der Annahme erneut geprüft
        w2 = world("a")
        w2.svc.create("lo", "player")
        w2.svc.record("lo", "identity.xp_gained", {"amount": 30000})
        w2.parties.create("a")
        i = w2.parties.invite("a", "lo")
        w2.svc.record("a", "identity.xp_gained", {"amount": 200000})
        with self.assertRaises(WorldError):
            w2.parties.accept("lo", i)

    def test_gap_boundary_exact(self):
        w = world("a")
        w.parties.create("a")
        base = w.parties.level_of("a")
        pr = w.parties.pr
        pr["max_level_gap"] = 0
        w.svc.create("same", "player")
        w.svc.record("same", "identity.xp_gained", {"amount": 10000})
        w.parties.accept("same", w.parties.invite("a", "same"))           # Abstand 0 bei Grenze 0
        w.svc.create("low", "player")
        with self.assertRaises(WorldError):
            w.parties.invite("a", "low")
        self.assertGreater(base, 1)

    def test_expiry(self):
        self.p.create("a")
        iid = self.p.invite("a", "b")
        self.w.day[0] = 2
        self.assertEqual(self.p.expire(2), [])
        self.w.day[0] = 3
        with self.assertRaises(WorldError):
            self.p.accept("b", iid)                          # Tag 3 >= Frist 3
        self.assertEqual(self.p.expire(3), [iid])
        self.assertEqual(self.p.incoming("b"), [])
        for bad in (-1, "3", True, None, 2.0):
            with self.assertRaises(WorldError):
                self.p.expire(bad)

    def test_accept_on_last_valid_day(self):
        self.p.create("a")
        iid = self.p.invite("a", "b")
        self.w.day[0] = 2
        self.p.accept("b", iid)


class MemberTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.p = self.w.parties
        team(self.w, "a", "b", "c", "d")
        self.pid = self.p.view("a")["id"]

    def test_leader_leaves_passes_to_longest_member(self):
        self.p.leave("a")
        v = self.p.view("b")
        self.assertEqual((v["leader"], v["members"]), ("b", ["b", "c", "d"]))
        self.assertIsNone(self.p.view("a"))
        self.assertIn(("party.leader_changed", {"party": self.pid, "leader": "b"}), kinds(self.w, "c"))
        self.assertEqual([k for k, _ in kinds(self.w, "d")].count("party.left"), 1)
        self.assertEqual(self.p.check(), [])

    def test_last_two_leaving_dissolves(self):
        self.p.leave("d")
        self.p.leave("c")
        self.p.leave("b")                                    # a bleibt allein: keine Gruppe mehr
        self.assertEqual(self.p.parties, {})
        self.assertIsNone(self.p.view("a"))
        self.assertIn(("party.disbanded", {"party": self.pid, "reason": "left"}), kinds(self.w, "a"))
        self.p.create("a")                                   # a kann neu anfangen
        with self.assertRaises(WorldError):
            self.p.leave("e")

    def test_kick(self):
        for who, member in (("b", "c"), ("a", "a"), ("a", "e")):
            with self.assertRaises(WorldError):
                self.p.kick(who, member)
        self.p.kick("a", "c")
        self.assertEqual(self.p.view("a")["members"], ["a", "b", "d"])
        self.assertEqual([k for k, _ in kinds(self.w, "c") if k == "party.kicked"], ["party.kicked"])
        self.assertEqual([k for k, _ in kinds(self.w, "b") if k == "party.kicked"], ["party.kicked"])
        self.p.create("c")                                   # nach dem Rauswurf frei

    def test_kick_in_pair_dissolves_with_kick_reason(self):
        self.p.kick("a", "d")
        self.p.kick("a", "c")
        self.p.kick("a", "b")
        self.assertEqual(self.p.parties, {})
        self.assertIn(("party.disbanded", {"party": self.pid, "reason": "kicked"}), kinds(self.w, "a"))

    def test_promote(self):
        for who, member in (("b", "c"), ("a", "a"), ("a", "e")):
            with self.assertRaises(WorldError):
                self.p.promote(who, member)
        self.p.kick("a", "d")
        self.p.promote("a", "c")
        self.assertEqual(self.p.view("a")["leader"], "c")
        with self.assertRaises(WorldError):
            self.p.invite("a", "e")
        self.p.invite("c", "e")

    def test_loot_mode_and_disband(self):
        with self.assertRaises(WorldError):
            self.p.set_loot("b", "leader")
        with self.assertRaises(WorldError):
            self.p.set_loot("a", "free_for_all")
        self.p.set_loot("a", "finder")
        self.assertEqual(self.p.view("c")["loot"], "finder")
        with self.assertRaises(WorldError):
            self.p.disband("b")
        self.p.disband("a")
        self.assertEqual((self.p.parties, self.p.member_of), ({}, {}))
        self.assertEqual([k for k, _ in kinds(self.w, "b") if k == "party.disbanded"], ["party.disbanded"])
        self.assertEqual([k for k, _ in kinds(self.w, "a") if k == "party.disbanded"], [])

    def test_disband_removes_open_invites(self):
        iid = None
        self.p.kick("a", "d")
        iid = self.p.invite("a", "e")
        self.p.disband("a")
        self.assertEqual(self.p.invites, {})
        with self.assertRaises(WorldError):
            self.p.accept("e", iid)

    def test_roster_only_for_leader(self):
        self.assertEqual(self.p.roster("a"), ["a", "b", "c", "d"])
        with self.assertRaises(WorldError):
            self.p.roster("b")
        with self.assertRaises(WorldError):
            self.p.roster("e")


class LootTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.p = self.w.parties
        team(self.w, "a", "b", "c", "d")
        self.pid = self.p.view("a")["id"]

    def held(self, c):
        return self.w.inv.holdings(c).get(ORE, 0)

    def test_round_robin_cycles_and_remembers(self):
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 5, ["a", "b", "c", "d"]), {"a": 2, "b": 1, "c": 1, "d": 1})
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 2, ["a", "b", "c", "d"]), {"b": 1, "c": 1})   # weiter bei b
        self.assertEqual([self.held(c) for c in "abcd"], [2, 2, 2, 1])
        self.assertEqual(self.w.inv.total(ORE), 7)

    def test_round_robin_skips_ineligible(self):
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 3, ["b", "d"]), {"b": 2, "d": 1})
        self.assertEqual(self.held("a") + self.held("c"), 0)
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 1, ["b", "d"]), {"d": 1})

    def test_leader_and_finder_modes(self):
        self.p.set_loot("a", "leader")
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 4, ["a", "b"]), {"a": 4})
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 4, ["b", "c"]), {"b": 4})     # Anführer ohne Beitrag: erster Berechtigter
        self.p.set_loot("a", "finder")
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 3, ["b", "c"], "c"), {"c": 3})
        for finder in ("a", None, "zzz"):
            with self.assertRaises(WorldError):
                self.p.distribute_loot(self.pid, ORE, 3, ["b", "c"], finder)

    def test_leader_mode_follows_a_changed_leader(self):
        self.p.promote("a", "c")
        self.p.set_loot("c", "leader")
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 2, ["a", "c"]), {"c": 2})

    def test_validation_and_no_partial_effect(self):
        before = self.w.inv.total(ORE)
        for args in (("nope", ORE, 1, ["a"]), (self.pid, "bad", 1, ["a"]), (self.pid, ORE, 0, ["a"]), (self.pid, ORE, -1, ["a"]),
                     (self.pid, ORE, True, ["a"]), (self.pid, ORE, 1, []), (self.pid, ORE, 1, ["e"]), (self.pid, ORE, 1, ["a", "a"]),
                     (self.pid, ORE, 1, "a"), (self.pid, ORE, 1, ["a", "e"]), (None, ORE, 1, ["a"])):
            with self.subTest(args=args), self.assertRaises(WorldError):
                self.p.distribute_loot(*args)
        self.assertEqual(self.w.inv.total(ORE), before)
        self.assertEqual(self.p.parties[self.pid]["rr"], 0)

    def test_pointer_stays_on_same_character_when_members_leave(self):
        self.p.distribute_loot(self.pid, ORE, 2, ["a", "b", "c", "d"])      # nächster wäre c
        self.p.leave("a")                                                   # Mitglieder: b, c, d; Zeiger muss auf c bleiben
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 1, ["b", "c", "d"]), {"c": 1})
        self.p.leave("d")
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 1, ["b", "c"]), {"b": 1})

    def test_pointer_wraps_when_last_member_leaves(self):
        self.p.distribute_loot(self.pid, ORE, 3, ["a", "b", "c", "d"])      # nächster wäre d (Index 3)
        self.p.leave("d")
        self.assertEqual(self.p.distribute_loot(self.pid, ORE, 1, ["a", "b", "c"]), {"a": 1})
        self.assertEqual(self.p.check(), [])

    def test_loot_notifications(self):
        self.p.distribute_loot(self.pid, ORE, 3, ["a", "b"])
        self.assertIn(("party.loot", {"party": self.pid, "item_key": ORE, "qty": 2}), kinds(self.w, "a"))
        self.assertIn(("party.loot", {"party": self.pid, "item_key": ORE, "qty": 1}), kinds(self.w, "b"))
        self.assertEqual([k for k, _ in kinds(self.w, "c") if k == "party.loot"], [])


class PersistenceTests(unittest.TestCase):
    def build(self):
        w = world()
        team(w, "a", "b", "c")
        w.parties.invite("a", "d")
        w.parties.distribute_loot(w.parties.view("a")["id"], ORE, 4, ["a", "b", "c"])
        w.parties.set_loot("a", "finder")
        return w

    def test_roundtrip_and_tamper(self):
        w = self.build()
        e, logs = persistence.export_world(w)
        loaded = persistence.import_world(json.loads(json.dumps(e)), json.loads(json.dumps(logs)))
        self.assertEqual(loaded.snapshot(), w.snapshot())
        self.assertEqual(loaded.parties.to_json(), w.parties.to_json())
        self.assertEqual(loaded.parties.check(), [])
        for x in (w, loaded):                                 # Zähler laufen weiter, Einladung bleibt gültig
            x.parties.accept("d", x.parties.incoming("d")[0]["id"])
            x.parties.create("f")
        self.assertEqual(loaded.snapshot(), w.snapshot())
        self.assertEqual(loaded.parties.view("f")["id"], "srv1-party-00000002")
        pid = "srv1-party-00000001"

        def tampered(fn):
            bad = copy.deepcopy(e)
            fn(bad["world"]["parties"])
            bad["world_sha256"] = persistence._sha(bad["world"])
            with self.assertRaises(persistence.PersistenceError):
                persistence.import_world(bad, logs)

        tampered(lambda p: p["parties"][pid].update(leader="zzz"))
        tampered(lambda p: p["parties"][pid]["members"].append("a"))
        tampered(lambda p: p["parties"][pid].update(loot="xx"))
        tampered(lambda p: p["invites"][next(iter(p["invites"]))].update(to="b"))
        bad = copy.deepcopy(e)
        bad["rules"]["party_sha256"] = "0" * 64
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)

    def test_inconsistent_state_is_found(self):
        w = self.build()
        pid = w.parties.view("a")["id"]
        w.parties.parties[pid]["leader"] = "zzz"
        self.assertTrue(w.parties.check())
        w = self.build()
        w.parties.member_of["f"] = pid
        self.assertTrue(w.parties.check())
        w = self.build()
        w.parties.parties[pid]["members"].append("a")
        self.assertTrue(w.parties.check())
        w = self.build()
        w.parties.parties[pid]["rr"] = 9
        self.assertTrue(w.parties.check())
        w = self.build()
        w.parties.parties[pid]["loot"] = "xx"
        self.assertTrue(w.parties.check())
        w = self.build()
        w.parties.parties[pid]["members"] = ["a", "b", "b"]
        w.parties.member_of = {"a": pid, "b": pid}
        self.assertTrue(w.parties.check())
        w = self.build()
        w.parties.create("f")
        w.parties.parties["srv1-party-00000002"]["members"].append("a")
        self.assertTrue(any("mehreren" in e for e in w.parties.check()))
        w = self.build()
        text = w.parties.to_json()
        bad = json.loads(text)
        bad["parties"][pid]["leader"] = "zzz"
        w.parties.parties = {}
        with self.assertRaises(WorldError):
            w.parties.load(json.dumps(bad))
        w = self.build()
        for i in w.parties.invites.values():
            i["to"] = "b"
        self.assertTrue(w.parties.check())
        w = self.build()
        w.parties.parties[pid]["members"] = ["a"]
        w.parties.parties[pid]["rr"] = 0
        w.parties.member_of = {"a": pid}
        self.assertEqual(w.parties.check(), [])              # eine neu gegründete Gruppe mit einem Mitglied ist gültig
        w.parties.parties[pid]["members"] = []
        self.assertTrue(w.parties.check())

    def test_deterministic_across_two_runs(self):
        self.assertEqual(self.build().parties.to_json(), self.build().parties.to_json())


class GatewayTests(unittest.TestCase):
    def test_party_flow_and_authorization(self):
        w = world("abc")
        s = Sessions()
        sa, sb = s.open("acc-a", ["a"]), s.open("acc-b", ["b"])
        g = Gateway(w, s, lambda: 0)

        def call(sess, rid, cmd, **args):
            return g.handle(sess, {"v": 1, "id": rid, "cmd": cmd, "args": args})

        self.assertTrue(call(sa, "1", "party.form", char="a")["ok"])
        r = call(sa, "2", "party.invite", char="a", target="b")
        self.assertTrue(r["ok"], r)
        self.assertEqual(call(sb, "3", "query.party_invites", char="b")["result"][0]["id"], r["result"])
        self.assertEqual(call(sa, "4", "query.party_invites", char="b")["error"]["code"], "forbidden")    # fremde Einladungen sind privat
        self.assertEqual(call(sb, "5", "party.accept", char="a", invite=r["result"])["error"]["code"], "forbidden")
        self.assertTrue(call(sb, "6", "party.accept", char="b", invite=r["result"])["ok"])
        self.assertEqual(call(sb, "7", "party.kick", char="b", member="a")["error"]["code"], "rejected")   # nicht Anführer
        self.assertEqual(call(sa, "8", "party.set_loot", char="a", mode="leader")["ok"], True)
        self.assertEqual(call(sb, "9", "query.party", char="b")["result"]["loot"], "leader")
        self.assertEqual(call(sa, "10", "party.loot", char="a")["error"]["code"], "unknown_command")      # Beute nur serverintern
        self.assertTrue(call(sb, "11", "party.leave", char="b")["ok"])
        self.assertIsNone(call(sa, "12", "query.party", char="a")["result"])


if __name__ == "__main__":
    unittest.main()
