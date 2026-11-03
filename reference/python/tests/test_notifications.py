import copy
import json
import unittest

from mmo_server import Gateway, Sessions
from mmo_world import WorldError, persistence
from mmo_world.notifications import FETCH_MAX, KINDS, Outbox
from mmo_world.world import World

from .test_company_service import make_manager

COIN, FINE = "coin@gold", "iron_blade@fine"


def world(chars="abc", coins=20000):
    w = World()
    for c in chars:
        w.svc.create(c, "player")
        w.svc.record(c, "identity.xp_gained", {"amount": 10000})
        w.svc.record(c, "profession.work", {"profession": "trade", "xp": 700})
        w.inv.deposit(c, COIN, coins)
        w.inv.deposit(c, FINE, 30)
    return w


def kinds(w, cid):
    return [(i["kind"], i["data"]) for i in w.outbox.fetch(cid)["items"]]


def only(w, cid, kind):
    got = [d for k, d in kinds(w, cid) if k == kind]
    return got


class Adapter:
    """Lässt die Hilfen aus test_company_service auf einer World laufen."""

    def __init__(self, w):
        self.w, self.svc, self.reg, self.cs = w, w.svc, w.company_registry, w.company

    def char(self, cid, kind="player", xp=10000, **prof):
        self.svc.create(cid, kind)
        self.svc.record(cid, "identity.xp_gained", {"amount": xp})
        for p, x in prof.items():
            self.svc.record(cid, "profession.work", {"profession": p, "xp": x})


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.day = [1]
        self.o = Outbox(lambda: self.day[0], mailbox_limit=5)

    def test_sequence_fetch_and_latest(self):
        self.assertEqual(self.o.fetch("a"), {"items": [], "latest": 0, "gap": False})
        for i in range(3):
            self.o.emit("a", "market.fill", {"n": i})
        self.o.emit("b", "market.expired", {})
        r = self.o.fetch("a")
        self.assertEqual(([i["seq"] for i in r["items"]], r["latest"], r["gap"]), ([1, 2, 3], 3, False))
        self.assertEqual([i["seq"] for i in self.o.fetch("a", 1, 1)["items"]], [2])
        self.assertEqual([i["seq"] for i in self.o.fetch("b")["items"]], [1])  # je Figur eigene Folge
        self.assertEqual(self.o.fetch("a")["items"][0], {"seq": 1, "day": 1, "kind": "market.fill", "data": {"n": 0}})

    def test_fetch_returns_copies_and_validates(self):
        self.o.emit("a", "market.fill", {"n": 1})
        self.o.fetch("a")["items"][0]["kind"] = "x"
        self.assertEqual(self.o.fetch("a")["items"][0]["kind"], "market.fill")
        for after, limit in ((-1, 5), (True, 5), ("0", 5), (0, 0), (0, FETCH_MAX + 1), (0, True), (0, 1.5)):
            with self.assertRaises(WorldError):
                self.o.fetch("a", after, limit)

    def test_overflow_drops_oldest_and_reports_a_gap(self):
        for i in range(8):
            self.o.emit("a", "market.fill", {"n": i})
        r = self.o.fetch("a")
        self.assertEqual(([i["seq"] for i in r["items"]], r["gap"]), ([4, 5, 6, 7, 8], True))
        self.assertTrue(self.o.fetch("a", 2)["gap"])
        self.assertFalse(self.o.fetch("a", 3)["gap"])  # ab Folgenummer 3 fehlt nichts mehr
        self.assertEqual(self.o.check(), [])

    def test_ack_removes_and_validates(self):
        for _ in range(4):
            self.o.emit("a", "market.fill", {})
        self.assertEqual(self.o.ack("a", 2), 2)
        self.assertEqual([i["seq"] for i in self.o.fetch("a")["items"]], [3, 4])
        self.assertEqual(self.o.ack("a", 2), 2)  # wiederholt: ohne Wirkung
        self.assertFalse(self.o.fetch("a", 2)["gap"])
        for bad in (5, -1, True, "1", 1.5):
            with self.assertRaises(WorldError):
                self.o.ack("a", bad)
        self.assertEqual(self.o.ack("nobody", 0), 0)
        with self.assertRaises(WorldError):
            self.o.ack("nobody", 1)
        self.assertEqual(self.o.check(), [])

    def test_mute_unmute(self):
        self.o.mute("a", ["market.fill"])
        self.o.emit("a", "market.fill", {})
        self.o.emit("a", "market.expired", {})
        self.assertEqual([i["kind"] for i in self.o.fetch("a")["items"]], ["market.expired"])
        self.assertEqual(self.o.mute("a", ["market.expired"]), ["market.expired", "market.fill"])  # ergänzt, ersetzt nicht
        self.assertEqual(self.o.unmute("a", ["market.fill"]), ["market.expired"])
        self.o.emit("a", "market.fill", {})
        self.assertEqual(self.o.fetch("a")["latest"], 2)
        for bad in ([], "market.fill", ["nope"], [1], None, ["market.fill", "nope"]):
            with self.assertRaises(WorldError):
                self.o.mute("a", bad)
            with self.assertRaises(WorldError):
                self.o.unmute("a", bad)
        self.assertEqual(self.o.unmute("nobody", ["market.fill"]), [])

    def test_unknown_kind_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            self.o.emit("a", "made.up", {})

    def test_listeners_see_every_stored_item_but_not_muted_ones(self):
        seen = []
        self.o.listeners.append(lambda who, item: seen.append((who, item["seq"], item["kind"])))
        self.o.mute("a", ["market.expired"])
        self.o.emit("a", "market.fill", {})
        self.o.emit("a", "market.expired", {})
        self.assertEqual(seen, [("a", 1, "market.fill")])

    def test_roundtrip_and_load_validation(self):
        for i in range(7):
            self.o.emit("a", "market.fill", {"n": i})
        self.o.mute("b", ["market.fill"])
        text = self.o.to_json()
        other = Outbox(lambda: 1, mailbox_limit=5)
        other.load(text)
        self.assertEqual(other.to_json(), text)
        bad = json.loads(text)
        bad["a"]["items"][0]["seq"] = 99
        with self.assertRaises(WorldError):
            Outbox(lambda: 1, mailbox_limit=5).load(json.dumps(bad))
        bad = json.loads(text)
        bad["a"]["items"][0]["kind"] = "made.up"
        with self.assertRaises(WorldError):
            Outbox(lambda: 1, mailbox_limit=5).load(json.dumps(bad))
        bad = json.loads(text)
        bad["a"]["dropped_through"] = 99
        with self.assertRaises(WorldError):
            Outbox(lambda: 1, mailbox_limit=5).load(json.dumps(bad))
        bad = json.loads(text)
        bad["a"]["items"] = bad["a"]["items"] * 2
        with self.assertRaises(WorldError):
            Outbox(lambda: 1, mailbox_limit=5).load(json.dumps(bad))
        fresh = Outbox(lambda: 1)
        with self.assertRaises(WorldError):
            fresh.load(json.dumps({"a": {"next": 1, "dropped_through": 0, "muted": ["x"], "items": []}}))
        self.assertEqual(fresh.boxes, {})


class MarketAndTradeEventTests(unittest.TestCase):
    def setUp(self):
        self.w = world()

    def test_resting_order_owner_is_told_about_fills_and_expiry(self):
        x = self.w.exchange
        x.place("a", "sell", FINE, 2, 190)
        x.place("b", "buy", FINE, 2, 190)
        self.assertEqual(only(self.w, "a", "market.fill"), [{"order": "srv1-ord-00000001", "item_key": FINE, "qty": 2, "unit_price": 190,
                                                             "trade_id": "srv1-trade-00000001", "role": "seller"}])
        self.assertEqual(only(self.w, "b", "market.fill"), [])  # der Einsteller sieht es in der Antwort
        x.place("c", "buy", FINE, 1, 150)
        self.w.day[0] = 9
        x.expire(9)
        self.assertEqual(only(self.w, "c", "market.expired"), [{"order": "srv1-ord-00000003"}])
        x.place("c", "sell", FINE, 1, 200)
        x.place("a", "buy", FINE, 1, 200)
        self.assertEqual(only(self.w, "c", "market.fill")[0]["role"], "seller")
        x.place("b", "buy", FINE, 1, 150)
        x.place("a", "sell", FINE, 1, 150)
        self.assertEqual(only(self.w, "b", "market.fill")[0]["role"], "buyer")

    def test_partial_fills_notify_once_per_fill(self):
        x = self.w.exchange
        x.place("a", "sell", FINE, 5, 190)
        x.place("b", "buy", FINE, 2, 190)
        x.place("c", "buy", FINE, 3, 190)
        self.assertEqual([d["qty"] for d in only(self.w, "a", "market.fill")], [2, 3])

    def test_direct_trade_events(self):
        o = self.w.offers
        o1 = o.make("a", "b", "sell", FINE, 1, 180)
        self.assertEqual(only(self.w, "b", "trade.offer_received"), [{"offer": o1, "from": "a", "side": "sell", "item_key": FINE, "qty": 1,
                                                                      "price": 180, "expires": 4}])
        o.accept("b", o1)
        self.assertEqual(only(self.w, "a", "trade.offer_accepted"), [{"offer": o1, "by": "b", "trade_id": "srv1-trade-00000001"}])
        o2 = o.make("a", "b", "sell", FINE, 1, 180)
        o.decline("b", o2)
        self.assertEqual(only(self.w, "a", "trade.offer_declined"), [{"offer": o2, "by": "b"}])
        o3 = o.make("a", "b", "sell", FINE, 1, 180)
        o.cancel("a", o3)
        self.assertEqual(only(self.w, "b", "trade.offer_cancelled"), [{"offer": o3, "by": "a"}])
        o4 = o.make("a", "b", "buy", FINE, 1, 180)
        self.w.day[0] = 4
        o.expire(4)
        self.assertEqual((only(self.w, "a", "trade.offer_expired"), only(self.w, "b", "trade.offer_expired")), ([{"offer": o4}], [{"offer": o4}]))

    def test_rejected_actions_emit_nothing(self):
        before = self.w.outbox.to_json()
        for fn in (lambda: self.w.offers.make("a", "a", "sell", FINE, 1, 100), lambda: self.w.offers.accept("b", "nope"),
                   lambda: self.w.exchange.place("a", "sell", FINE, 1, 99999), lambda: self.w.offers.make("a", "ghost", "sell", FINE, 1, 100)):
            with self.assertRaises(WorldError):
                fn()
        self.assertEqual(self.w.outbox.to_json(), before)

    def test_discovery_teaching(self):
        w = world("mn")
        for c in "mn":
            w.svc.record(c, "profession.work", {"profession": "smithing", "xp": 700})
        for e in ("ore_sample_a", "ore_sample_b", "forge_trial"):
            w.discovery.gather("m", "iron_folding", e)
        w.discovery.complete("m", "iron_folding")
        w.day[0] = 12
        w.discovery.teach("m", "n", "iron_folding")
        self.assertEqual(only(w, "n", "discovery.taught"), [{"discovery": "iron_folding", "teacher": "m"}])
        self.assertEqual(only(w, "m", "discovery.taught"), [])


class CompanyEventTests(unittest.TestCase):
    def setUp(self):
        self.w = world("boss emp inv x".split())
        self.cid = self.w.company.found("boss", 5000)

    def test_hire_left_fired_resigned(self):
        c = self.w.company
        c.hire("boss", self.cid, "emp", 40)
        c.hire("boss", self.cid, "inv", 40)
        self.assertEqual(only(self.w, "emp", "company.hired"), [{"company": self.cid, "wage": 40}])
        c.fire("boss", self.cid, "emp")
        self.assertEqual(only(self.w, "emp", "company.left"), [{"company": self.cid, "reason": "fired"}])
        self.assertEqual(only(self.w, "boss", "company.employee_left"), [])  # Entlassung: der Verwalter weiß es
        c.resign("inv", self.cid)
        self.assertEqual(only(self.w, "inv", "company.left"), [{"company": self.cid, "reason": "resigned"}])
        self.assertEqual(only(self.w, "boss", "company.employee_left"), [{"company": self.cid, "character": "inv", "reason": "resigned"}])

    def test_promote_demote(self):
        c = self.w.company
        self.w.svc.record("emp", "profession.work", {"profession": "trade", "xp": 700})
        c.hire("boss", self.cid, "emp", 40)
        self.w.day[0] = 8
        c.promote("boss", self.cid, "emp")
        self.assertEqual(only(self.w, "emp", "company.promoted"), [{"company": self.cid, "role": "specialist"}])
        c.demote("boss", self.cid, "emp")
        self.assertEqual(only(self.w, "emp", "company.demoted"), [{"company": self.cid, "role": "employee"}])

    def test_poaching_tells_the_owners_of_the_old_company(self):
        other = self.w.company.found("x", 5000)
        self.w.company.hire("boss", self.cid, "emp", 20)
        res = self.w.company.poach("x", other, "emp", 400)
        self.assertTrue(res["accept"])
        self.assertEqual(only(self.w, "emp", "company.left"), [{"company": self.cid, "reason": "poached_away"}])
        self.assertEqual(only(self.w, "boss", "company.employee_left"), [{"company": self.cid, "character": "emp", "reason": "poached_away"}])
        self.assertEqual(only(self.w, "emp", "company.hired"), [{"company": self.cid, "wage": 20}, {"company": other, "wage": 400}])

    def test_warnings_and_automatic_resignation_come_from_the_daily_step(self):
        poor = self.w.company.found("x", 1000)
        self.w.company.hire("x", poor, "emp", 400)
        self.w.company.hire("x", poor, "inv", 400)
        for d in range(1, 41):
            self.w.day[0] = d
            self.w.company.advance_day(d)
        got = [d["status"] for d in only(self.w, "emp", "company.warning")]
        self.assertIn("warned", got)
        self.assertEqual(only(self.w, "emp", "company.left")[0]["reason"], "resigned")
        self.assertTrue(only(self.w, "x", "company.employee_left"))

    def test_share_offers_proposals_and_closing(self):
        c = self.w.company
        c.hire("boss", self.cid, "emp", 40)
        o1 = c.offer_shares("boss", self.cid, 300, 5)
        self.assertEqual(only(self.w, "inv", "company.shares_offered"), [])  # noch kein anderer Gesellschafter
        self.w.day[0] = 9
        c.purchase("inv", self.cid, o1, 300, c.disclosure(self.cid)["hash"])
        o2 = c.offer_shares("boss", self.cid, 100, 6)
        self.assertEqual(only(self.w, "inv", "company.shares_offered"),
                         [{"company": self.cid, "offer": o2, "seller": "boss", "qty": 100, "price": 6, "deadline": 16}])
        self.assertEqual(only(self.w, "boss", "company.shares_offered"), [])
        c.close_company("boss", self.cid)
        self.assertEqual(only(self.w, "emp", "company.closed"), [{"company": self.cid}])
        self.assertEqual(only(self.w, "inv", "company.closed"), [{"company": self.cid}])
        self.assertEqual(only(self.w, "boss", "company.closed"), [])  # wer schließt, weiß es

    def test_proposals_open_and_resolve(self):
        a = Adapter(self.w)
        make_manager(a, "mgr", self.cid)
        self.w.company_registry.get(self.cid)["shares"] = {"boss": 600, "inv": 400}
        day = 100
        self.w.day[0] = day
        pid = self.w.company.propose("inv", self.cid, "appoint_ceo", "mgr")
        self.assertEqual(only(self.w, "boss", "company.proposal_opened"),
                         [{"company": self.cid, "proposal": pid, "kind": "appoint_ceo", "candidate": "mgr", "deadline": day + 5}])
        self.assertEqual(only(self.w, "inv", "company.proposal_opened"), [])
        self.w.company.vote("boss", self.cid, pid, True)
        res = [(k, d["status"]) for k, d in kinds(self.w, "boss") + kinds(self.w, "inv") if k == "company.proposal_resolved"]
        self.assertEqual(len(res), 2)  # beide gewichtsberechtigten Gesellschafter erfahren das Ergebnis
        self.assertEqual({s for _, s in res}, {"passed"} if self.w.company_registry.get(self.cid)["ceo"] else {"execution_failed"})

    def test_production_job_done_goes_to_founder_and_ceo(self):
        w = self.w
        w.svc.record("emp", "profession.work", {"profession": "smithing", "xp": 700})
        w.company.hire("boss", self.cid, "emp", 40)
        w.inv.deposit("boss", "iron_ore@standard", 100)
        w.production.stock_in("boss", self.cid, "iron_ore@standard", 100)
        jid = w.production.start("boss", self.cid, "emp", "iron_ingot", 1, "standard")
        w.day[0] = 1
        w.company.advance_day(1)
        self.assertEqual(only(w, "boss", "production.job_done"), [{"company": self.cid, "job": jid, "recipe": "iron_ingot"}])
        self.assertEqual(only(w, "emp", "production.job_done"), [])


class PrivacyAndStateTests(unittest.TestCase):
    def test_notifications_carry_only_ids_and_terms(self):
        w = world()
        w.exchange.place("a", "sell", FINE, 1, 190)
        w.exchange.place("b", "buy", FINE, 1, 190)
        w.offers.make("a", "c", "buy", FINE, 1, 180)
        banned = {"inventory", "balance", "coins", "holdings", "wealth", "xp", "points", "hp"}
        for cid in "abc":
            for k, data in kinds(w, cid):
                self.assertIn(k, KINDS)
                self.assertFalse(banned & set(data), (k, data))
                self.assertTrue(all(isinstance(v, (str, int)) or v is None for v in data.values()))

    def test_notifications_are_not_part_of_the_world_state(self):
        w = world()
        w.offers.make("a", "b", "sell", FINE, 1, 180)
        self.assertTrue(w.outbox.active)
        self.assertNotIn("outbox", w.snapshot())
        quiet = world()
        quiet.offers.make("a", "b", "sell", FINE, 1, 180)
        quiet.outbox.boxes.clear()
        self.assertEqual(quiet.snapshot(), w.snapshot())  # gleicher Weltzustand, egal was im Postfach liegt


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.s = Sessions()
        self.sa, self.sb = self.s.open("acc-a", ["a"]), self.s.open("acc-b", ["b"])
        self.tick = [0]
        self.g = Gateway(self.w, self.s, lambda: self.tick[0])

    def call(self, sess, rid, cmd, **args):
        return self.g.handle(sess, {"v": 1, "id": rid, "cmd": cmd, "args": args})

    def test_fetch_ack_mute(self):
        oid = self.call(self.sa, "1", "trade.offer", char="a", to="b", side="sell", item_key=FINE, qty=1, price=180)["result"]
        r = self.call(self.sb, "2", "notify.fetch", char="b")
        self.assertEqual([i["kind"] for i in r["result"]["items"]], ["trade.offer_received"])
        self.assertEqual(r["result"]["items"][0]["data"]["offer"], oid)
        self.assertEqual(self.call(self.sa, "3", "notify.fetch", char="b")["error"]["code"], "forbidden")
        self.assertEqual(self.call(self.sb, "4", "notify.fetch", char="b", after=1)["result"]["items"], [])
        self.assertTrue(self.call(self.sb, "5", "notify.ack", char="b", upto=1)["ok"])
        self.assertEqual(self.call(self.sb, "6", "notify.fetch", char="b")["result"]["items"], [])
        self.assertEqual(self.call(self.sb, "7", "notify.ack", char="b", upto=5)["error"]["code"], "rejected")
        self.assertEqual(self.call(self.sb, "8", "notify.mute", char="b", kinds=["trade.offer_received"])["result"], ["trade.offer_received"])
        self.call(self.sa, "9", "trade.offer", char="a", to="b", side="sell", item_key=FINE, qty=1, price=181)
        self.assertEqual(self.call(self.sb, "10", "notify.fetch", char="b")["result"]["latest"], 1)  # stumm: nichts Neues
        self.assertEqual(self.call(self.sb, "11", "notify.unmute", char="b", kinds=["trade.offer_received"])["result"], [])
        for bad in ({"kinds": []}, {"kinds": ["x"]}, {"kinds": "market.fill"}):
            self.assertFalse(self.call(self.sb, "b" + str(len(str(bad))), "notify.mute", char="b", **bad)["ok"])
        self.assertEqual(self.call(self.sb, "12", "notify.fetch", char="b", limit=0)["error"]["code"], "rejected")

    def test_fetch_is_a_query_and_not_stored_while_ack_is_idempotent(self):
        self.call(self.sa, "1", "trade.offer", char="a", to="b", side="sell", item_key=FINE, qty=1, price=180)
        f = {"v": 1, "id": "q", "cmd": "notify.fetch", "args": {"char": "b"}}
        self.assertNotIn("replayed", self.g.handle(self.sb, f))
        self.assertNotIn("replayed", self.g.handle(self.sb, f))
        ack = {"v": 1, "id": "k", "cmd": "notify.ack", "args": {"char": "b", "upto": 1}}
        first = self.g.handle(self.sb, ack)
        self.assertEqual(self.g.handle(self.sb, ack), {**first, "replayed": True})

    def test_live_push_reaches_only_the_owner_session(self):
        got_a, got_b = [], []
        self.g.on_push(self.sa, lambda who, item: got_a.append((who, item["kind"])))
        self.g.on_push(self.sb, lambda who, item: got_b.append((who, item["kind"])))
        self.call(self.sa, "1", "trade.offer", char="a", to="b", side="sell", item_key=FINE, qty=1, price=180)
        self.assertEqual((got_a, got_b), ([], [("b", "trade.offer_received")]))
        self.s.close(self.sb)
        self.call(self.sa, "2", "trade.offer", char="a", to="b", side="sell", item_key=FINE, qty=1, price=181)
        self.assertEqual(got_b, [("b", "trade.offer_received")])  # Sitzung beendet: kein Push mehr, Abruf bleibt möglich
        self.assertEqual(self.w.outbox.fetch("b")["latest"], 2)
        self.assertNotIn(self.sb, self.g._push)  # Rückrufe beendeter Sitzungen werden aufgeräumt
        with self.assertRaises(ValueError):
            self.g.on_push("sess-99999999", lambda *a: None)


class PersistenceTests(unittest.TestCase):
    def build(self):
        w = world()
        w.offers.make("a", "b", "sell", FINE, 1, 180)
        w.exchange.place("a", "sell", FINE, 1, 190)
        w.exchange.place("c", "buy", FINE, 1, 190)
        w.outbox.mute("c", ["market.expired"])
        w.outbox.ack("a", 1)
        return w

    def roundtrip(self, w):
        e, logs = persistence.export_world(w)
        return persistence.import_world(json.loads(json.dumps(e)), json.loads(json.dumps(logs))), e, logs

    def test_mailboxes_survive_and_numbering_continues(self):
        w = self.build()
        loaded, e, _ = self.roundtrip(w)
        self.assertEqual(loaded.outbox.to_json(), w.outbox.to_json())
        for x in (w, loaded):
            x.offers.make("a", "b", "sell", FINE, 1, 181)
        self.assertEqual(loaded.outbox.fetch("b"), w.outbox.fetch("b"))
        self.assertEqual(loaded.outbox.fetch("b")["items"][-1]["seq"], 2)

    def test_tampering_and_older_envelopes(self):
        w = self.build()
        _, e, logs = self.roundtrip(w)
        bad = copy.deepcopy(e)
        bad["outbox"]["b"]["items"][0]["data"]["price"] = 1  # ohne neuen Hash
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)
        bad = copy.deepcopy(e)
        bad["outbox"]["b"]["items"][0]["seq"] = 7  # mit neuem Hash, aber unstimmig
        bad["outbox_sha256"] = persistence._sha(bad["outbox"])
        with self.assertRaises(persistence.PersistenceError):
            persistence.import_world(bad, logs)
        old = copy.deepcopy(e)
        del old["outbox"], old["outbox_sha256"]
        loaded = persistence.import_world(old, logs)
        self.assertFalse(loaded.outbox.active)
        self.assertEqual(loaded.snapshot(), w.snapshot())

    def test_fresh_worlds_do_not_carry_an_outbox_key(self):
        e, _ = persistence.export_world(World())
        self.assertNotIn("outbox", e)

    def test_world_upgrade_keeps_mailboxes(self):
        w = self.build()
        new = persistence.upgrade_world(w, "rules_v8.json")
        self.assertEqual(new.outbox.to_json(), w.outbox.to_json())


if __name__ == "__main__":
    unittest.main()
