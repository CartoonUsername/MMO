"""AP 10: Filialen und Offline-Deckel (ADR-0049)."""
import unittest

from mmo_world import WorldError, persistence
from mmo_world.branches import load_branch_rules
from tests.test_production import PW, COIN

REGION = "crossing"


def level_up(pw, level):
    """Umsatz buchen, bis die Unternehmensstufe erreicht ist."""
    need = pw.w.company.cr["company_level_thresholds"][level - 1]
    pw.w.company.record_revenue(pw.co, max(need, 1))


class Branches(unittest.TestCase):
    def setUp(self):
        self.pw = PW(capital=20000)
        self.b = self.pw.w.branches

    def test_needs_company_level_and_cash(self):
        with self.assertRaises(WorldError):
            self.b.open_branch("boss", self.pw.co, REGION)           # Stufe 1: keine Filiale
        level_up(self.pw, 2)
        with self.assertRaises(WorldError):
            self.b.open_branch("boss", self.pw.co, "nowhere")
        with self.assertRaises(WorldError):
            self.b.open_branch("smith", self.pw.co, REGION)          # Mitarbeiter ohne Verwaltungsrecht
        before = self.pw.w.company.balance(self.pw.co)
        bid = self.b.open_branch("boss", self.pw.co, REGION)
        self.assertEqual(before - self.pw.w.company.balance(self.pw.co), load_branch_rules()["open_cost"])   # Geldsenke
        with self.assertRaises(WorldError):
            self.b.open_branch("boss", self.pw.co, "moor")           # Limit der Stufe
        self.assertEqual(self.b.view(self.pw.co)["extra_lines"], 1)
        self.b.close_branch("boss", self.pw.co, bid)
        self.assertEqual(self.b.view(self.pw.co)["branches"], [])

    def test_one_branch_per_region(self):
        level_up(self.pw, 3)
        self.b.open_branch("boss", self.pw.co, REGION)
        with self.assertRaises(WorldError):
            self.b.open_branch("boss", self.pw.co, REGION)

    def test_branch_adds_line_and_storage(self):
        level_up(self.pw, 2)
        p = self.pw.p
        c = self.pw.w.company.reg.companies[self.pw.co]
        lines0, cap0 = p.lines(c), p.capacity(c)
        self.b.open_branch("boss", self.pw.co, REGION)
        self.assertEqual((p.lines(c) - lines0, p.capacity(c) - cap0), (1, load_branch_rules()["extra_storage"]))

    def test_upkeep_and_dormancy_when_cash_is_gone(self):
        level_up(self.pw, 2)
        self.b.open_branch("boss", self.pw.co, REGION)
        t = self.pw.w.company._treasury(self.pw.w.company.reg.companies[self.pw.co])
        d0 = self.pw.w.day[0]
        bal = self.pw.w.company.balance(self.pw.co)
        self.pw.days(d0 + 1)
        self.assertLess(self.pw.w.company.balance(self.pw.co), bal)
        # Kasse leeren -> ruhend nach den konfigurierten Tagen
        self.pw.w.inv.apply(t, {COIN: self.pw.w.inv.balance(t, COIN)}, {})
        self.pw.days(d0 + 1 + load_branch_rules()["dormant_after_unpaid_days"])
        br = self.b.of(self.pw.co)[0]
        self.assertEqual(br["status"], "dormant")
        self.assertEqual(self.b.view(self.pw.co)["extra_lines"], 0)
        with self.assertRaises(WorldError):
            self.b.reopen_branch("boss", self.pw.co, br["id"])       # Kasse leer
        self.pw.w.inv.deposit(t, COIN, 5000)
        self.b.reopen_branch("boss", self.pw.co, br["id"])
        self.assertEqual(self.b.of(self.pw.co)[0]["status"], "open")

    def test_closing_the_company_removes_branches(self):
        level_up(self.pw, 2)
        self.b.open_branch("boss", self.pw.co, REGION)
        self.pw.w.company.close_company("boss", self.pw.co)
        self.assertEqual(self.b.branches, {})

    def test_roundtrip_and_old_snapshots(self):
        w0 = PW().w
        self.assertNotIn("branches", w0.snapshot())
        level_up(self.pw, 2)
        self.b.open_branch("boss", self.pw.co, REGION)
        self.b.touch("boss", 3)
        env, logs = persistence.export_world(self.pw.w)
        w2 = persistence.import_world(env, logs)
        self.assertEqual(w2.branches.to_json(), self.b.to_json())
        self.assertEqual(persistence.check_consistency(w2), [])


class OfflineCap(unittest.TestCase):
    def jobs(self, pw):
        # zwei Aufträge, zwei Arbeiter, zweites Gebäude-Level liefert zwei Linien
        pw.w.inv.deposit("boss", COIN, 100000)
        pw.w.company.upgrade_building("boss", pw.co)
        pw.p.stock_in("boss", pw.co, "iron_ore@standard", 100)
        pw.w.company.set_contract("boss", pw.co, "novice", 50)
        pw.w.svc.record("novice", "profession.work", {"profession": "smithing", "xp": 700})
        j1 = pw.p.start("boss", pw.co, "smith", "iron_ingot", 1, "standard")
        j2 = pw.p.start("boss", pw.co, "novice", "iron_ingot", 1, "standard")
        return j1, j2

    def test_without_activity_data_nothing_changes(self):
        pw = PW(capital=20000)
        j1, j2 = self.jobs(pw)
        pw.days(pw.w.day[0] + 1)
        self.assertEqual({pw.p.jobs[j]["progress"] if j in pw.p.jobs else 1 for j in (j1, j2)}, {1})

    def test_offline_leadership_runs_only_the_capped_lines(self):
        pw = PW(capital=20000)
        j1, j2 = self.jobs(pw)
        pw.w.branches.touch("boss", -10)                             # lange nichts los: Leitung gilt als offline
        pw.days(pw.w.day[0])                                         # genau ein Tagesschritt
        done = [j for j in (j1, j2) if j not in pw.p.jobs]
        self.assertEqual(len(done), 1)                               # nur eine Linie lief
        pw.w.branches.touch("boss", pw.w.day[0])
        pw.days(pw.w.day[0] + 3)
        self.assertEqual([j for j in (j1, j2) if j in pw.p.jobs], [])    # wieder aktiv: beide fertig


if __name__ == "__main__":
    unittest.main()
