import copy
import unittest

from mmo_cee import RuleViolation
from mmo_world import CompanyRegistry, WorldError

from .test_company_service import CAREER, COIN, CR, CWorld, id_with_goal, make_manager


def setup_company(investor_shares=600):
    """boss gründet; Investor 'inv' hält investor_shares, boss den Rest; Manager 'mgr' (Fixture) ist ab 'ready' CEO-fähig."""
    w = CWorld()
    cid = w.company("boss", capital=5000)
    w.char("inv", coins=50_000)
    c = w.reg.get(cid)
    if investor_shares:
        w.reg.move_shares(c, "boss", "inv", investor_shares)
    ready = make_manager(w, "mgr", cid, hired_day=1)
    w.day[0] = ready
    return w, cid, c, ready


class ProposalValidationTests(unittest.TestCase):
    def setUp(self):
        self.w, self.cid, self.c, self.ready = setup_company(600)

    def test_only_shareholders_may_propose(self):
        with self.assertRaisesRegex(WorldError, "Gesellschafter"):
            self.w.cs.propose("mgr", self.cid, "appoint_ceo", "mgr")  # Angestellte ohne Anteile
        with self.assertRaisesRegex(WorldError, "Gesellschafter"):
            self.w.cs.propose("stranger", self.cid, "appoint_ceo", "mgr")

    def test_candidate_and_kind_validation(self):
        self.w.char("emp")
        self.w.cs.hire("inv", self.cid, "emp", 30)  # inv hält 600 > 500 und kontrolliert das Unternehmen
        for kind, cand in (("appoint_ceo", "emp"),  # kein Manager
                           ("appoint_ceo", "stranger"), ("appoint_ceo", None), ("dismiss_ceo", None),  # kein Geschäftsführer
                           ("fire_everyone", "mgr"), (5, "mgr")):
            with self.subTest(kind=kind, cand=cand):
                with self.assertRaises(WorldError):
                    self.w.cs.propose("boss", self.cid, kind, cand)

    def test_one_pending_proposal_per_kind(self):
        self.w.cs.propose("boss", self.cid, "appoint_ceo", "mgr")
        with self.assertRaisesRegex(WorldError, "läuft bereits"):
            self.w.cs.propose("inv", self.cid, "appoint_ceo", "mgr")


class VotingTests(unittest.TestCase):
    def test_majority_holder_with_founder_yes_appoints_the_ceo(self):
        w, cid, c, ready = setup_company(600)  # inv 600, boss 400 (Veto aktiv, >= 100 Promille)
        pid = w.cs.propose("inv", cid, "appoint_ceo", "mgr")
        self.assertEqual(w.cs.vote("inv", cid, pid, True), "pending")  # Mehrheit, aber Gründer-Veto: er muss zustimmen
        self.assertIsNone(c["ceo"])
        self.assertEqual(w.cs.vote("boss", cid, pid, True), "passed")
        self.assertEqual(c["ceo"], "mgr")
        self.assertEqual(w.career("mgr")["role"], "executive")  # CEE-Beförderung durch den Beschluss
        self.assertEqual(c["log"][-1]["kind"], "appoint_ceo")

    def test_founder_veto_blocks(self):
        w, cid, c, ready = setup_company(600)
        pid = w.cs.propose("inv", cid, "appoint_ceo", "mgr")
        w.cs.vote("inv", cid, pid, True)
        self.assertEqual(w.cs.vote("boss", cid, pid, False), "rejected")
        self.assertIsNone(c["ceo"])
        self.assertEqual(w.career("mgr")["role"], "manager")

    def test_veto_is_inactive_below_the_minimum_stake(self):
        w, cid, c, ready = setup_company(0)
        w.reg.move_shares(c, "boss", "inv", 950)  # boss behält 50 Promille < 100
        pid = w.cs.propose("inv", cid, "appoint_ceo", "mgr")
        self.assertIsNone(c["proposals"][pid]["veto_holder"])
        self.assertEqual(w.cs.vote("inv", cid, pid, True), "passed")
        self.assertEqual(c["ceo"], "mgr")

    def test_sole_founder_decides_alone(self):
        w, cid, c, ready = setup_company(0)
        pid = w.cs.propose("boss", cid, "appoint_ceo", "mgr")
        self.assertEqual(w.cs.vote("boss", cid, pid, True), "passed")

    def test_minority_cannot_pass_and_threshold_is_strict(self):
        w, cid, c, ready = setup_company(0)
        w.reg.move_shares(c, "boss", "inv", 500)  # 500 : 500 -> 500 ist nicht > 500
        pid = w.cs.propose("boss", cid, "appoint_ceo", "mgr")
        self.assertEqual(w.cs.vote("boss", cid, pid, True), "pending")
        self.assertEqual(w.cs.vote("inv", cid, pid, True), "passed")

    def test_snapshot_weights_and_voter_rights(self):
        w, cid, c, ready = setup_company(600)
        pid = w.cs.propose("inv", cid, "appoint_ceo", "mgr")
        w.char("late", coins=1)
        w.reg.move_shares(c, "inv", "late", 600)  # Anteile nach Antragstellung übertragen
        with self.assertRaisesRegex(WorldError, "Zeitpunkt des Antrags"):
            w.cs.vote("late", cid, pid, True)  # der neue Halter hat keine Stimme
        self.assertEqual(w.cs.vote("inv", cid, pid, True), "pending")  # der alte Halter votet mit dem Snapshot-Gewicht
        self.assertEqual(c["proposals"][pid]["weights"], {"boss": 400, "inv": 600})

    def test_double_vote_and_invalid_votes(self):
        w, cid, c, ready = setup_company(600)
        pid = w.cs.propose("inv", cid, "appoint_ceo", "mgr")
        w.cs.vote("inv", cid, pid, True)
        with self.assertRaises(WorldError):
            w.cs.vote("inv", cid, pid, False)
        for bad in ("yes", 1, None):
            with self.assertRaises(WorldError):
                w.cs.vote("boss", cid, pid, bad)
        with self.assertRaises(WorldError):
            w.cs.vote("boss", cid, "ghost", True)

    def test_deadline_and_expiry_by_the_day_tick(self):
        w, cid, c, ready = setup_company(600)
        pid = w.cs.propose("inv", cid, "appoint_ceo", "mgr")  # Frist: Tag + 5
        w.cs.vote("inv", cid, pid, True)
        w.day[0] = ready + 5
        with self.assertRaisesRegex(WorldError, "abgelaufen"):
            w.cs.vote("boss", cid, pid, True)
        self.assertEqual(c["proposals"][pid]["status"], "expired")
        self.assertIsNone(c["ceo"])
        pid2 = w.cs.propose("inv", cid, "appoint_ceo", "mgr")  # nach Ablauf darf neu beantragt werden
        w.reg.last_day = ready + 5
        w.cs.advance_day(ready + 5 + 6)
        self.assertEqual(c["proposals"][pid2]["status"], "expired")

    def test_execution_failure_leaves_everything_unchanged(self):
        w, cid, c, ready = setup_company(0)
        w.day[0] = ready - 20  # Dienstzeit als Manager nur 10 Tage: die CEE verweigert die Beförderung zum Geschäftsführer
        pid = w.cs.propose("boss", cid, "appoint_ceo", "mgr")
        before = len(w.svc.log.events("mgr"))
        self.assertEqual(w.cs.vote("boss", cid, pid, True), "execution_failed")
        self.assertIsNone(c["ceo"])
        self.assertIn("CEE lehnt ab", c["proposals"][pid]["result"])
        self.assertEqual((w.career("mgr")["role"], len(w.svc.log.events("mgr"))), ("manager", before))
        self.assertEqual(c["log"][-1]["kind"], "proposal_failed")


class CeoRolesTests(unittest.TestCase):
    def setUp(self):
        self.w, self.cid, self.c, self.ready = setup_company(600)
        w = self.w
        pid = w.cs.propose("inv", self.cid, "appoint_ceo", "mgr")
        w.cs.vote("inv", self.cid, pid, True)
        w.cs.vote("boss", self.cid, pid, True)
        w.char("emp")

    def test_ceo_can_manage_but_not_close_or_trade_shares(self):
        self.w.cs.hire("mgr", self.cid, "emp", 30)  # Geschäftsführer verwaltet
        self.assertIn("emp", self.c["employees"])
        with self.assertRaisesRegex(WorldError, "Eigentümer"):
            self.w.cs.close_company("mgr", self.cid)  # Schließen ist Sache des Eigentümers
        with self.assertRaises(WorldError):
            self.w.cs.offer_shares("mgr", self.cid, 1, 10)  # der Geschäftsführer besitzt keine Anteile

    def test_owner_and_founder_roles(self):
        # inv kontrolliert (600 > 500) -> Eigentümer; boss (400) ist weder Eigentümer noch Geschäftsführer
        self.w.cs.hire("inv", self.cid, "emp", 30)
        self.w.char("emp2")
        with self.assertRaisesRegex(WorldError, "Berechtigung"):
            self.w.cs.hire("boss", self.cid, "emp2", 30)

    def test_ceo_cannot_be_fired_demoted_or_poached(self):
        for call in (lambda: self.w.cs.fire("inv", self.cid, "mgr"), lambda: self.w.cs.demote("inv", self.cid, "mgr")):
            with self.assertRaisesRegex(WorldError, "Gesellschafterbeschluss"):
                call()
        self.w.founder("rival")
        other = self.w.cs.found("rival", 3000)
        with self.assertRaises(WorldError):
            self.w.cs.poach("rival", other, "mgr", 10_000)

    def test_dismissal_by_vote_demotes_to_manager(self):
        pid = self.w.cs.propose("boss", self.cid, "dismiss_ceo")
        self.w.cs.vote("inv", self.cid, pid, True)
        self.assertEqual(self.w.cs.vote("boss", self.cid, pid, True), "passed")
        self.assertEqual((self.c["ceo"], self.w.career("mgr")["role"]), (None, "manager"))
        self.assertIn("mgr", self.c["employees"])  # bleibt im Unternehmen
        with self.assertRaises(WorldError):
            self.w.cs.propose("boss", self.cid, "dismiss_ceo")  # es gibt keinen mehr

    def test_resigning_ceo_clears_the_office(self):
        self.w.cs.resign("mgr", self.cid)
        self.assertIsNone(self.c["ceo"])
        self.assertEqual(self.w.career("mgr")["role"], None)

    def test_founder_without_controlling_peer_is_owner(self):
        w, cid, c, ready = setup_company(400)  # niemand kontrolliert (> 500): der Gründer bleibt Eigentümer
        w.char("e")
        w.cs.hire("boss", cid, "e", 30)
        w.char("e2")
        with self.assertRaises(WorldError):
            w.cs.hire("inv", cid, "e2", 30)  # inv hält nur 400 und ist nicht Gründer


class CloseCompanyTests(unittest.TestCase):
    def setUp(self):
        self.w = CWorld()
        self.cid = self.w.company("boss", capital=3003)
        self.c = self.w.reg.get(self.cid)
        for e in ("e1", "e2"):
            self.w.char(e)
            self.w.cs.hire("boss", self.cid, e, 30)
        self.w.char("inv", coins=10)
        self.w.reg.move_shares(self.c, "boss", "inv", 333)

    def test_close_pays_out_pro_rata_with_remainder_to_the_founder(self):
        total = self.w.total_coins()
        payout = self.w.cs.close_company("boss", self.cid)
        # Kasse 3003: inv 333/1000 = 999, boss 667/1000 = 2001, Rest 3 -> Gründer
        self.assertEqual(payout, {"boss": 2001 + 3, "inv": 999})
        self.assertEqual(sum(payout.values()), 3003)
        self.assertEqual(self.w.cs.balance(self.cid), 0)
        self.assertEqual(self.w.total_coins(), total)

    def test_close_effects(self):
        self.w.cs.offer_shares("boss", self.cid, 100, 5)
        self.w.cs.close_company("boss", self.cid)
        self.assertEqual((self.c["open"], self.c["employees"], self.w.reg.employer), (False, {}, {}))
        for e in ("e1", "e2"):
            self.assertEqual(self.w.career(e)["role"], None)
        self.assertFalse(self.w.svc.state("boss").parts["economy"]["founded"][self.cid]["open"])
        self.assertTrue(all(o["remaining"] == 0 for o in self.c["offers"].values()))
        self.assertEqual(self.c["log"][-1]["kind"], "closed")
        for call in (lambda: self.w.cs.hire("boss", self.cid, "e1", 30), lambda: self.w.cs.record_revenue(self.cid, 5),
                     lambda: self.w.cs.close_company("boss", self.cid), lambda: self.w.cs.offer_shares("boss", self.cid, 1, 1)):
            with self.assertRaisesRegex(WorldError, "geschlossen"):
                call()

    def test_only_the_owner_can_close(self):
        with self.assertRaisesRegex(WorldError, "Eigentümer"):
            self.w.cs.close_company("inv", self.cid)
        self.assertTrue(self.c["open"])

    def test_pending_proposals_are_cancelled(self):
        ready = make_manager(self.w, "mgr", self.cid, hired_day=1)
        self.w.day[0] = ready
        pid = self.w.cs.propose("boss", self.cid, "appoint_ceo", "mgr")
        self.assertEqual(self.c["proposals"][pid]["status"], "pending")
        self.w.cs.close_company("boss", self.cid)
        self.assertEqual(self.c["proposals"][pid]["status"], "cancelled")

    def test_freed_founder_slot_allows_a_new_company(self):
        for _ in range(2):
            self.w.cs.found("boss", 1000)
        with self.assertRaises(WorldError):
            self.w.cs.found("boss", 1000)  # 3 offen (Limit)
        self.w.cs.close_company("boss", self.cid)
        self.w.cs.found("boss", 1000)  # wieder Platz


class ConsistencyPropertyTests(unittest.TestCase):
    """Zufällige (deterministische), zustandsbewusste Abläufe: Münzen bleiben bilanziert, Anteile summieren sich,
    Register und CEE stimmen überein."""

    NAMES = [f"c{i}" for i in range(8)]
    OPS = ["hire", "fire", "resign", "set_contract", "promote", "demote", "upgrade", "revenue", "advance", "poach",
           "offer_preempt", "purchase", "grant_equity", "appoint_ceo", "dismiss_ceo", "close"]

    def build(self):
        w = CWorld()
        w.day[0] = 80
        w.reg.last_day = 79  # Welt läuft schon seit Tag 79: Dienstzeiten/Fixtures liegen in der Vergangenheit
        w.founder("boss", coins=80_000)
        w.founder("rival", coins=80_000)
        for c in self.NAMES:
            xp = [0, 700, 3000][int(c[1:]) % 3]
            w.char(c, coins=3000, **({"trade": xp} if xp else {}))
        cos = [w.cs.found("boss", 6000), w.cs.found("rival", 6000)]
        make_manager(w, "mgr", cos[0], hired_day=1)  # Kandidat für die Geschäftsführung (Fixture)
        for co, holders in zip(cos, (("c0", "c1"), ("c2", "c3"))):
            for h in holders:  # bestehende Gesellschafter -> Vorkaufsrechte und Abstimmungen werden möglich
                w.reg.move_shares(w.reg.get(co), w.reg.get(co)["founder"], h, 120)
        return w, cos

    def run_ops(self, seed, n=500):
        w, cos = self.build()
        x = seed
        stats = {}

        def rnd(k):
            nonlocal x
            x = (1103515245 * x + 12345) % 2**31
            return (x // 7) % k

        def pick(items):
            items = sorted(items)
            return items[rnd(len(items))] if items else None

        for _ in range(n):
            co = cos[rnd(2)]
            c = w.reg.get(co)
            other = cos[1 - cos.index(co)]
            founder, ofounder = c["founder"], w.reg.get(other)["founder"]
            op = self.OPS[rnd(len(self.OPS))]
            if op == "close" and rnd(12):  # Schließen bleibt selten
                continue
            try:
                if op == "hire":
                    w.cs.hire(founder, co, pick(self.NAMES), 20 + rnd(60), rnd(60))
                elif op == "fire":
                    w.cs.fire(founder, co, pick(c["employees"]))
                elif op == "resign":
                    w.cs.resign(pick(c["employees"]), co)
                elif op == "set_contract":
                    w.cs.set_contract(founder, co, pick(c["employees"]), wage=5 + rnd(200))
                elif op == "promote":
                    w.cs.promote(founder, co, pick(c["employees"]))
                elif op == "demote":
                    w.cs.demote(founder, co, pick(c["employees"]))
                elif op == "upgrade":
                    w.cs.upgrade_building(founder, co)
                elif op == "revenue":
                    amount = 1 + rnd(4000)
                    w.cs.record_revenue(co, amount)
                    w.minted += amount
                elif op == "advance":
                    w.day[0] += 1 + rnd(8)
                    w.cs.advance_day(w.day[0])
                elif op == "poach":
                    w.cs.poach(ofounder, other, pick(c["employees"]), 15 + rnd(120))
                elif op == "offer_preempt":
                    oid = w.cs.offer_shares(founder, co, 1 + rnd(60), 1 + rnd(5))
                    w.cs.preempt(pick(set(c["shares"]) - {founder}), co, oid, 1 + rnd(30))
                elif op == "purchase":
                    oid = pick([o for o, v in c["offers"].items() if v["remaining"] > 0])
                    if oid is None:
                        continue  # kein offenes Angebot: nichts zu kaufen
                    w.day[0] = max(w.day[0], c["offers"][oid]["deadline"])
                    if w.day[0] > w.reg.last_day:
                        w.cs.advance_day(w.day[0])
                    w.cs.purchase(pick(self.NAMES), co, oid, 1 + rnd(20), w.cs.disclosure(co)["hash"])
                elif op == "grant_equity":
                    w.cs.grant_equity(founder, co, pick(c["employees"]), 1 + rnd(30))
                elif op == "appoint_ceo":
                    pid = w.cs.propose(founder, co, "appoint_ceo", "mgr")
                    for h in sorted(c["shares"]):
                        if w.cs.vote(h, co, pid, True) != "pending":
                            break
                elif op == "dismiss_ceo":
                    pid = w.cs.propose(founder, co, "dismiss_ceo")
                    for h in sorted(c["shares"]):
                        if w.cs.vote(h, co, pid, True) != "pending":
                            break
                elif op == "close":
                    w.cs.close_company(founder, co)
                stats[op] = stats.get(op, 0) + 1
            except (WorldError, RuleViolation):
                stats[("fail", op)] = stats.get(("fail", op), 0) + 1
            self.check_invariants(w, cos)
        return w, cos, stats

    def check_invariants(self, w, cos):
        self.assertEqual(w.total_coins(), w.minted)  # nichts entsteht, nichts verschwindet (außer Server-Einnahmen)
        for owner, stacks in w.inv._stacks.items():
            self.assertTrue(stacks and all(v > 0 for v in stacks.values()), owner)
        for cid in cos:
            c = w.reg.get(cid)
            self.assertEqual(sum(c["shares"].values()), 1000)
            self.assertTrue(all(v > 0 for v in c["shares"].values()))
            self.assertTrue(all(o["remaining"] >= 0 for o in c["offers"].values()))
            for h in c["shares"]:
                self.assertGreaterEqual(w.reg.free_shares(c, h), 0)
            self.assertTrue(0 <= c["reputation"] <= 1000)
            for e, emp in c["employees"].items():
                self.assertEqual(w.reg.employer[e], cid)
                self.assertTrue(0 <= emp["satisfaction"] <= 1000 and 0 <= emp["loyalty"] <= 1000)
                self.assertEqual(w.career(e)["company_id"], cid)  # Register und CEE stimmen überein
                self.assertIsNotNone(w.career(e)["role"])
            if c["ceo"]:
                self.assertIn(c["ceo"], c["employees"])
                self.assertEqual(w.career(c["ceo"])["role"], "executive")
            self.assertEqual(c["open"], w.svc.state(c["founder"]).parts["economy"]["founded"][cid]["open"])
        for ch in self.NAMES + ["boss", "rival", "mgr"]:
            self.assertEqual(w.reg.employer.get(ch), w.career(ch)["company_id"])  # jede Figur: Register == CEE

    def test_random_histories_keep_all_invariants_and_exercise_every_operation(self):
        total = {}
        for seed in (1, 2, 3, 4, 5):
            w, cos, stats = self.run_ops(seed)
            for k, v in stats.items():
                if not isinstance(k, tuple):
                    total[k] = total.get(k, 0) + v
        # jede Operation gelingt über alle Läufe mehrfach (sonst prüfte der Test fast nichts)
        for op, minimum in (("hire", 20), ("fire", 3), ("resign", 3), ("set_contract", 5), ("promote", 2), ("demote", 1),
                            ("upgrade", 3), ("revenue", 20), ("advance", 20), ("poach", 2), ("offer_preempt", 5),
                            ("purchase", 2), ("grant_equity", 3), ("appoint_ceo", 1), ("close", 1)):
            self.assertGreaterEqual(total.get(op, 0), minimum, f"{op}: {total.get(op, 0)} < {minimum} ({total})")

    def test_replay_and_determinism(self):
        w1, cos1, _ = self.run_ops(7, n=300)
        w2, cos2, _ = self.run_ops(7, n=300)
        self.assertEqual(w1.reg.to_json(), w2.reg.to_json())
        self.assertEqual(w1.inv.to_json(), w2.inv.to_json())
        for cid in ("boss", "rival", "c0", "c3", "mgr"):
            self.assertEqual(w1.svc.log.events(cid)[-1].hash, w2.svc.log.events(cid)[-1].hash)
            live = copy.deepcopy(w1.svc.state(cid).parts)
            self.assertEqual(w1.svc.rebuild(cid).parts, live)
        again = CompanyRegistry.from_json(CR, w1.reg.to_json())
        self.assertEqual(again.to_json(), w1.reg.to_json())


if __name__ == "__main__":
    unittest.main()
