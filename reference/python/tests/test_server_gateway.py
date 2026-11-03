import copy
import json
import unittest
from pathlib import Path

from mmo_server import COMMANDS, INTERNAL_ONLY, Gateway, Sessions, load_protocol_rules
from mmo_server.gateway import CODES
from mmo_world import WorldError
from mmo_world.world import World

COIN, FINE = "coin@gold", "iron_blade@fine"
DOC = Path(__file__).resolve().parents[3] / "docs" / "PROTOCOL.md"


def req(rid, cmd, **args):
    return {"v": 1, "id": rid, "cmd": cmd, "args": args}


class Env:
    def __init__(self, rules="rules_v8.json"):
        self.w = World(rules)
        for c in ("a", "b", "c"):
            self.w.svc.create(c, "player")
            self.w.svc.record(c, "identity.xp_gained", {"amount": 10000})
            self.w.svc.record(c, "profession.work", {"profession": "trade", "xp": 700})
            self.w.inv.deposit(c, COIN, 20000)
            self.w.inv.deposit(c, FINE, 30)
            self.w.inv.deposit(c, "iron_ore@standard", 100)
        self.tick = [0]
        self.s = Sessions()
        self.sa = self.s.open("acc-a", ["a"])
        self.sb = self.s.open("acc-b", ["b", "c"])
        self.g = Gateway(self.w, self.s, lambda: self.tick[0])

    def snap(self):
        return json.dumps(self.w.snapshot(), sort_keys=True)


def dummy(cmd):
    return {k: {"s": "x", "i": 1, "b": True}[t.rstrip("?")] for k, t in cmd.args.items() if not t.endswith("?")}


class CatalogTests(unittest.TestCase):
    def test_schema_is_well_formed(self):
        for name, c in COMMANDS.items():
            with self.subTest(name):
                self.assertEqual(c.name, name)
                self.assertTrue(all(t.rstrip("?") in ("s", "i", "b") for t in c.args.values()))
                if c.actor is not None:
                    self.assertEqual(c.args.get(c.actor), "s")
                self.assertIn(c.rate_group, load_protocol_rules()["rate"] | {"query": 0})
        self.assertTrue(all(not c.mutating for n, c in COMMANDS.items() if n.startswith("query.")))
        self.assertTrue(all(c.mutating for n, c in COMMANDS.items() if not n.startswith("query.")))

    def test_clients_cannot_reach_server_internal_operations(self):
        forbidden = ("gather", "advance_day", "deposit", "revenue", "shock", "expire", "upgrade_rules", "migrate", "record", "trade",
                     "price_advance", "create")
        for name in COMMANDS:
            self.assertFalse(any(f == name.split(".")[-1] for f in forbidden), name)
        self.assertTrue(INTERNAL_ONLY)

    def test_no_command_accepts_client_supplied_time_progress_or_reference(self):
        banned = {"day", "tick", "time", "xp", "points", "reference", "quality", "value", "progress", "result", "rules_version"}
        for name, c in COMMANDS.items():
            self.assertFalse(banned & set(c.args), name)

    def test_protocol_document_lists_every_command(self):
        text = DOC.read_text(encoding="utf-8")
        for name in COMMANDS:
            self.assertIn(f"`{name}`", text, f"{name} fehlt in docs/PROTOCOL.md")


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.g, self.sa = self.e.g, self.e.sa

    def code(self, msg, session="own"):
        r = self.g.handle(self.sa if session == "own" else session, msg)
        return r["error"]["code"] if not r["ok"] else "ok"

    def test_malformed_messages(self):
        base = req("r1", "query.quote", item_key=FINE)
        self.assertEqual(self.code(base), "ok")
        bad = [None, 5, [], "x", {}, {"v": 1}, {**base, "extra": 1}, {k: v for k, v in base.items() if k != "id"},
               {k: v for k, v in base.items() if k != "cmd"}, {**base, "id": ""}, {**base, "id": "a b"}, {**base, "id": "a" * 65},
               {**base, "id": 5}, {**base, "id": "ä"}, {**base, "cmd": 5}, {**base, "args": []}, {**base, "args": None}]
        for m in bad:
            with self.subTest(m=m):
                self.assertEqual(self.code(m if isinstance(m, dict) or m is None else m), "bad_request")

    def test_size_limit_is_exact(self):
        limit = load_protocol_rules()["max_message_bytes"]
        base = json.dumps(req("r1", "query.quote", item_key=FINE))
        self.assertEqual(self.code(base + " " * (limit - len(base))), "ok")
        self.assertEqual(self.code(base + " " * (limit - len(base) + 1)), "bad_request")

    def test_session_opening_validates(self):
        s = Sessions()
        for acct, chars in (("", ["a"]), ("a b", ["a"]), (5, ["a"]), ("acc", [])):
            with self.assertRaises(ValueError):
                s.open(acct, chars)
        self.assertEqual(s.open("acc", ["a"]), "sess-00000001")

    def test_query_ids_may_be_reused_freely(self):
        self.assertTrue(self.g.handle(self.sa, req("q1", "query.quote", item_key=FINE))["ok"])
        r = self.g.handle(self.sa, req("q1", "query.quote", item_key="iron_ore@standard"))
        self.assertTrue(r["ok"] and "replayed" not in r)

    def test_raw_text_json_size_and_encoding(self):
        ok = json.dumps(req("r1", "query.quote", item_key=FINE))
        self.assertEqual(self.code(ok), "ok")
        self.assertEqual(self.code(ok.encode()), "ok")
        self.assertEqual(self.code("{kaputt"), "bad_request")
        self.assertEqual(self.code(b"\xff\xfe"), "bad_request")
        self.assertEqual(self.code(" " * 5000 + ok), "bad_request")
        self.assertEqual(self.code("[1,2]"), "bad_request")

    def test_version_session_and_command(self):
        self.assertEqual(self.code({**req("r1", "query.quote", item_key=FINE), "v": 2}), "unsupported_version")
        r = self.g.handle(self.sa, {**req("r1", "query.quote", item_key=FINE), "v": "1"})
        self.assertEqual(r["error"]["code"], "unsupported_version")
        self.assertEqual(r["supported"], [1])
        self.assertEqual(self.code(req("r1", "query.quote", item_key=FINE), "sess-99999999"), "unknown_session")
        self.assertEqual(self.code(req("r1", "query.quote", item_key=FINE), None), "unknown_session")
        self.e.s.close(self.sa)
        self.assertEqual(self.code(req("r1", "query.quote", item_key=FINE)), "unknown_session")
        self.assertEqual(self.code(req("r1", "company.advance_day", day=3), self.e.sb), "unknown_command")
        for evil in ("price_advance", "cee_record", "deposit", "__class__", "", "market.place ", "MARKET.PLACE"):
            self.assertEqual(self.code(req("r2", evil), self.e.sb), "unknown_command")

    def test_args_are_exact_and_typed(self):
        ok = dict(char="a", side="sell", item_key=FINE, qty=1, price=190)
        self.assertEqual(self.code(req("r1", "market.place", **ok)), "ok")
        cases = [{**ok, "day": 5}, {**ok, "reference": 100}, {**ok, "xp": 5}, {k: v for k, v in ok.items() if k != "price"},
                 {**ok, "qty": True}, {**ok, "qty": 1.0}, {**ok, "qty": "1"}, {**ok, "qty": 10**13}, {**ok, "price": None},
                 {**ok, "char": ""}, {**ok, "char": "a" * 65}, {**ok, "char": 5}, {**ok, "ioc": 1}, {**ok, "ioc": "yes"},
                 {**ok, "side": ["sell"]}, {**ok, "item_key": {"x": 1}}]
        for i, a in enumerate(cases):
            with self.subTest(a=a):
                self.assertEqual(self.code(req(f"c{i}", "market.place", **a)), "bad_request")
        self.assertEqual(self.code(req("o1", "market.place", **ok, ioc=True)), "ok")
        self.assertEqual(self.code({"v": 1, "id": "q1", "cmd": "query.quote"}), "bad_request")  # args fehlt, aber Pflichtfeld nötig


class AuthorizationTests(unittest.TestCase):
    def test_every_actor_command_refuses_foreign_characters_without_touching_the_world(self):
        e = Env()
        before = e.snap()
        for i, (name, c) in enumerate(COMMANDS.items()):
            if c.actor is None:
                continue
            args = dummy(c) | {c.actor: "b"}  # Figur b gehört nicht zur Sitzung von acc-a
            r = e.g.handle(e.sa, req(f"f{i}", name, **args))
            self.assertEqual((name, r["error"]["code"]), (name, "forbidden"))
        self.assertEqual(e.snap(), before)

    def test_own_characters_pass_authorization_and_targets_stay_free(self):
        e = Env()
        for i, (name, c) in enumerate(COMMANDS.items()):
            if c.actor is None:
                continue
            e.tick[0] += 100  # Ratenlimit soll hier nicht stören
            args = dummy(c) | {c.actor: "a"}
            r = e.g.handle(e.sa, req(f"o{i}", name, **args))
            self.assertNotEqual(r.get("error", {}).get("code"), "forbidden", name)
        # Ziel-Figur darf eine fremde sein (anwerben, lehren, Mitarbeiter einstellen)
        cid = e.g.handle(e.sa, req("f1", "company.found", char="a", capital=3000))["result"]
        r = e.g.handle(e.sa, req("h1", "company.hire", actor="a", company=cid, char="b", wage=40))
        self.assertTrue(r["ok"], r)

    def test_account_with_several_characters(self):
        e = Env()
        for rid, ch in (("m1", "b"), ("m2", "c")):
            self.assertTrue(e.g.handle(e.sb, req(rid, "market.place", char=ch, side="sell", item_key=FINE, qty=1, price=200))["ok"])
        self.assertFalse(e.g.handle(e.sb, req("m3", "market.place", char="a", side="sell", item_key=FINE, qty=1, price=200))["ok"])

    def test_queries(self):
        e = Env()
        self.assertEqual(e.g.handle(e.sa, req("q1", "query.inventory", char="b"))["error"]["code"], "forbidden")  # fremdes Inventar
        self.assertTrue(e.g.handle(e.sa, req("q2", "query.inventory", char="a"))["ok"])
        self.assertTrue(e.g.handle(e.sa, req("q3", "query.appearance", char="b"))["ok"])  # öffentlich
        self.assertTrue(e.g.handle(e.sa, req("q4", "query.quote", item_key=FINE))["ok"])


class IdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.g, self.sa = self.e.g, self.e.sa
        self.msg = req("p1", "market.place", char="a", side="sell", item_key=FINE, qty=2, price=190)

    def test_replay_returns_the_same_answer_without_executing_again(self):
        first = self.g.handle(self.sa, self.msg)
        snap = self.e.snap()
        again = self.g.handle(self.sa, copy.deepcopy(self.msg))
        self.assertEqual(again, {**first, "replayed": True})
        self.assertEqual(self.e.snap(), snap)
        self.assertEqual(len(self.e.w.exchange.orders), 1)

    def test_id_reuse_with_other_content_is_a_conflict(self):
        self.g.handle(self.sa, self.msg)
        other = copy.deepcopy(self.msg)
        other["args"]["qty"] = 3
        self.assertEqual(self.g.handle(self.sa, other)["error"]["code"], "duplicate_conflict")
        other = copy.deepcopy(self.msg)
        other["cmd"] = "market.cancel"
        other["args"] = {"char": "a", "order": "srv1-ord-00000001"}
        self.assertEqual(self.g.handle(self.sa, other)["error"]["code"], "duplicate_conflict")
        self.assertEqual(len(self.e.w.exchange.orders), 1)

    def test_rejections_are_remembered_too(self):
        bad = req("p2", "market.cancel", char="a", order="srv1-ord-00000099")
        r1 = self.g.handle(self.sa, bad)
        self.assertEqual(r1["error"]["code"], "rejected")
        self.assertEqual(self.g.handle(self.sa, bad), {**r1, "replayed": True})

    def test_malformed_or_forbidden_requests_do_not_burn_the_id(self):
        wrong = req("p3", "market.place", char="b", side="sell", item_key=FINE, qty=1, price=190)
        self.assertEqual(self.g.handle(self.sa, wrong)["error"]["code"], "forbidden")
        fixed = req("p3", "market.place", char="a", side="sell", item_key=FINE, qty=1, price=190)
        self.assertTrue(self.g.handle(self.sa, fixed)["ok"])

    def test_ids_are_per_account_and_window_is_bounded(self):
        self.g.handle(self.sa, self.msg)
        other = req("p1", "market.place", char="b", side="sell", item_key=FINE, qty=1, price=190)
        self.assertTrue(self.g.handle(self.e.sb, other)["ok"])  # gleiche ID, anderes Konto
        for i in range(300):
            self.e.tick[0] += 100
            self.g.handle(self.sa, req(f"w{i}", "market.cancel", char="a", order="srv1-ord-00000099"))
        again = self.g.handle(self.sa, self.msg)  # p1 ist aus dem Fenster gefallen: wird neu ausgeführt
        self.assertNotIn("replayed", again)

    def test_queries_are_not_stored(self):
        self.g.handle(self.sa, self.msg)
        q = req("q1", "query.quote", item_key=FINE)
        self.g.handle(self.sa, q)
        self.e.w.exchange.place("b", "sell", FINE, 1, 200)
        again = self.g.handle(self.sa, q)
        self.assertNotIn("replayed", again)
        self.assertEqual(again["result"]["best_ask"], 190)


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.g, self.sa = self.e.g, self.e.sa

    def place(self, i, char="a", sess=None):
        # IOC ohne Gegenseite: belegt kein Orderbuch-Limit, kostet aber Rate
        return self.g.handle(sess or self.sa, req(f"r{i}-{char}", "market.place", char=char, side="sell", item_key=FINE, qty=1,
                                                  price=200 + i % 20, ioc=True))

    def test_bucket_capacity_and_refill(self):
        cap = load_protocol_rules()["rate"]["market.place"]["capacity"]
        first = [self.place(i) for i in range(cap)]
        self.assertTrue(all(r["ok"] for r in first))  # Kapazität = erlaubte Stöße
        over = [self.place(cap + i) for i in range(2)]
        self.assertEqual([r["error"]["code"] for r in over], ["rate_limited", "rate_limited"])
        self.e.tick[0] += 3  # drei Ticks = drei Marken
        later = [self.place(100 + i) for i in range(4)]
        self.assertEqual([r["ok"] for r in later], [True, True, True, False])
        self.e.tick[0] += 1000  # nie über die Kapazität hinaus
        burst = [self.place(200 + i) for i in range(cap + 1)]
        self.assertEqual([r["ok"] for r in burst].count(True), cap)

    def test_separate_buckets_per_character_and_group(self):
        for i in range(10):
            self.place(i)
        self.assertEqual(self.place(50)["error"]["code"], "rate_limited")
        self.assertTrue(self.g.handle(self.sa, req("q1", "query.quote", item_key=FINE))["ok"])  # andere Gruppe
        self.assertNotEqual(self.g.handle(self.sa, req("c1", "market.cancel", char="a", order="srv1-ord-00000001"))["error"]["code"],
                            "rate_limited")  # andere Gruppe (default): Eimer voll
        self.assertTrue(self.place(1, "b", self.e.sb)["ok"])  # andere Figur, anderes Konto
        for i in range(9):
            self.place(10 + i, "b", self.e.sb)  # Eimer von b leeren
        self.assertEqual(self.place(40, "b", self.e.sb)["error"]["code"], "rate_limited")
        self.assertTrue(self.place(1, "c", self.e.sb)["ok"])  # zweite Figur desselben Kontos hat einen eigenen Eimer

    def test_replays_and_invalid_requests_cost_nothing(self):
        msg = req("p1", "market.place", char="a", side="sell", item_key=FINE, qty=1, price=200)
        self.g.handle(self.sa, msg)
        for _ in range(50):
            self.assertTrue(self.g.handle(self.sa, msg)["replayed"])
            self.g.handle(self.sa, {**msg, "id": "zzz", "args": {"char": "a"}})  # bad_request
        self.assertTrue(self.g.handle(self.sa, req("p2", "market.place", char="a", side="sell", item_key=FINE, qty=1, price=201))["ok"])

    def test_rate_limited_requests_can_be_retried_with_the_same_id(self):
        for i in range(10):
            self.place(i)
        retry = req("late", "market.place", char="a", side="sell", item_key=FINE, qty=1, price=210)
        self.assertEqual(self.g.handle(self.sa, retry)["error"]["code"], "rate_limited")
        self.e.tick[0] += 2
        r = self.g.handle(self.sa, retry)
        self.assertTrue(r["ok"] and "replayed" not in r)

    def test_queries_without_actor_are_limited_per_account(self):
        cap = load_protocol_rules()["rate"]["query"]["capacity"]
        res = [self.g.handle(self.sa, req(f"q{i}", "query.quote", item_key=FINE)) for i in range(cap + 2)]
        self.assertEqual([r["ok"] for r in res].count(False), 2)
        self.assertTrue(self.g.handle(self.e.sb, req("q1", "query.quote", item_key=FINE))["ok"])


class ExecutionTests(unittest.TestCase):
    def test_error_mapping(self):
        e = Env()
        g, sa = e.g, e.sa
        self.assertEqual(g.handle(sa, req("e1", "market.cancel", char="a", order="nope"))["error"]["code"], "rejected")
        old = World()  # v7-Welt: Preishändler gibt es nicht
        old.svc.create("a", "player")
        s = Sessions()
        sid = s.open("acc", ["a"])
        g7 = Gateway(old, s, lambda: 0)
        self.assertEqual(g7.handle(sid, req("e2", "maker.sell", char="a", item_key="iron_ore@standard", qty=1))["error"]["code"], "rejected")
        # Figur mit älterer Regelversion: CEE lehnt ab
        up = World("rules_v7.json")
        up.svc.create("a", "player")
        from mmo_world.persistence import upgrade_world
        mixed = upgrade_world(up, "rules_v8.json", [])
        mixed.inv.deposit("a", "iron_ore@standard", 5)
        s2 = Sessions()
        sid2 = s2.open("acc", ["a"])
        gm = Gateway(mixed, s2, lambda: 0)
        r = gm.handle(sid2, req("e3", "craft", char="a", recipe="iron_ingot", qty=1, grade="standard"))
        self.assertEqual(r["error"]["code"], "rejected_by_rules")
        self.assertIn(r["error"]["code"], CODES)

    def test_unexpected_exceptions_do_not_leak_details(self):
        e = Env()
        e.w.exchange.cancel = lambda *a, **k: (_ for _ in ()).throw(KeyError("geheim: interner Pfad"))
        r = e.g.handle(e.sa, req("x1", "market.cancel", char="a", order="o"))
        self.assertEqual((r["error"]["code"], r["error"]["message"]), ("server_error", "Interner Fehler"))
        self.assertNotIn("geheim", json.dumps(r))

    def test_results_are_plain_json(self):
        e = Env()
        g, sa = e.g, e.sa
        cid = g.handle(sa, req("1", "company.found", char="a", capital=3000))["result"]
        out = [g.handle(sa, req("2", "market.place", char="a", side="sell", item_key=FINE, qty=1, price=190)),
               g.handle(e.sb, req("3", "market.place", char="b", side="buy", item_key=FINE, qty=1, price=190)),
               g.handle(sa, req("4", "craft", char="a", recipe="iron_ingot", qty=1, grade="standard")),
               g.handle(sa, req("5", "query.disclosure", company=cid)),
               g.handle(sa, req("6", "query.inventory", char="a")),
               g.handle(sa, req("7", "query.economic_profile", char="a"))]
        for r in out:
            self.assertTrue(r["ok"], r)
            json.dumps(r)  # serialisierbar
        fills = out[1]["result"]["fills"]
        self.assertEqual((fills[0]["quantity"], fills[0]["unit_price"]), (1, 190))
        self.assertNotIn("event", json.dumps(out[2]["result"]).replace("event_hash", ""))

    def test_end_to_end_company_production_flow(self):
        e = Env()
        g, sa, sb, w = e.g, e.sa, e.sb, e.w
        w.svc.record("c", "profession.work", {"profession": "smithing", "xp": 700})
        cid = g.handle(sa, req("1", "company.found", char="a", capital=5000))["result"]
        self.assertTrue(g.handle(sa, req("2", "company.hire", actor="a", company=cid, char="c", wage=50))["ok"])
        w.inv.deposit("a", "iron_ore@standard", 100)
        self.assertTrue(g.handle(sa, req("3", "production.stock_in", actor="a", company=cid, item_key="iron_ore@standard", qty=100))["ok"])
        # b gehört zu einem anderen Konto: darf die Firma von a weder verwalten noch beliefern
        r = g.handle(sb, req("4", "production.start", actor="b", company=cid, worker="c", recipe="iron_ingot", batches=1, grade="standard"))
        self.assertEqual(r["error"]["code"], "rejected")
        r = g.handle(sa, req("5", "production.start", actor="a", company=cid, worker="c", recipe="iron_ingot", batches=2, grade="standard"))
        self.assertTrue(r["ok"], r)
        w.day[0] = 3  # Tagesschritt macht der Server, nicht der Client
        w.company.advance_day(3)
        sold = g.handle(sa, req("6", "production.sell", actor="a", company=cid, item_key="iron_ingot@common", qty=10))
        self.assertTrue(sold["ok"], sold)
        self.assertEqual(sold["result"], w.production.npc_price("iron_ingot@common", 10))
        self.assertEqual(g.handle(sa, req("7", "query.inventory", char="a"))["result"], w.inv.holdings("a"))


class AuditTests(unittest.TestCase):
    def test_chain_and_tampering_and_limit(self):
        e = Env()
        for i in range(6):
            e.g.handle(e.sa, req(f"a{i}", "query.quote", item_key=FINE))
        e.g.handle(e.sa, "{kaputt")
        e.g.handle("sess-0", req("z", "query.quote", item_key=FINE))
        self.assertTrue(e.g.audit_ok())
        self.assertEqual([x["code"] for x in e.g.audit[-2:]], ["bad_request", "unknown_session"])
        self.assertTrue(all("args" not in x for x in e.g.audit))  # keine Inhalte im Audit
        e.g.audit[2]["code"] = "forbidden"
        self.assertFalse(e.g.audit_ok())

    def test_audit_is_bounded(self):
        e = Env()
        e.g.rules = {**e.g.rules, "audit_limit": 5}
        for i in range(12):
            e.g.handle(e.sa, req(f"a{i}", "query.quote", item_key=FINE))
        self.assertEqual(len(e.g.audit), 5)
        self.assertTrue(e.g.audit_ok())


class DeterminismTests(unittest.TestCase):
    def script(self):
        out = []
        for i in range(15):
            out.append(("sa", req(f"s{i}", "market.place", char="a", side="sell", item_key=FINE, qty=1 + i % 3, price=180 + i)))
            out.append(("sb", req(f"t{i}", "market.place", char="b", side="buy", item_key=FINE, qty=1 + i % 2, price=185 + i)))
            if i % 4 == 0:
                out.append(("sa", req(f"c{i}", "market.cancel", char="a", order=f"srv1-ord-{i + 1:08d}")))
        return out

    def run_once(self):
        e = Env()
        resp = []
        for who, m in self.script():
            e.tick[0] += 1
            resp.append(e.g.handle(e.sa if who == "sa" else e.sb, m))
        return resp, e.snap(), e.g.audit

    def test_same_messages_same_everything(self):
        a, b = self.run_once(), self.run_once()
        self.assertEqual(a, b)
        self.assertGreater(sum(1 for r in a[0] if r["ok"]), 10)
        self.assertTrue(any(not r["ok"] for r in a[0]))


if __name__ == "__main__":
    unittest.main()
