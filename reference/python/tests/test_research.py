import json
import unittest

from mmo_world.errors import WorldError
from mmo_world.persistence import check_consistency
from mmo_world.world import World

COIN = "coin@gold"


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.w = World("rules_v9.json")
        self.s, self.r = self.w.settlements, self.w.research
        for c in ("anna", "ben", "cora"):
            self.w.svc.create(c, "player")
            for k, n in ((COIN, 50000), ("timber@standard", 500), ("wooden_beam@standard", 500), ("iron_ingot@standard", 200)):
                self.w.inv.deposit(c, k, n)
        self.s.buy_plot("anna", "hauptstadt", 1)
        self.s.found("ben", "sonnenwiese_ost", "Sonnental")
        self.s.buy_plot("ben", "sonnenwiese_ost", 1)
        self.s.buy_plot("cora", "hauptstadt", 2)
        self.w.day[0] = 0

    def adv(self, d):
        self.w.day[0] = d
        return self.r.advance(d)

    def fund(self, char, site, tech):
        need = self.r.view(char)["running"]
        pr = next(p for p in need if p["site"] == site and p["tech"] == tech)
        for k, x in pr["need"].items():
            rest = x["need"] - x["have"]
            if rest:
                self.r.contribute(char, site, tech, rest if k == COIN else 0, None if k == COIN else {k: rest})

    def test_gate_research_and_pioneer(self):
        r, s = self.r, self.s
        with self.assertRaises(WorldError):
            s.contribute("anna", "hauptstadt", "wall", 1000, {"timber@standard": 50, "iron_ingot@standard": 10})   # Technik fehlt
        r.start("anna", "hauptstadt", "mauerbau")
        with self.assertRaises(WorldError):
            r.start("ben", "hauptstadt", "mauerbau")              # kein Bewohner
        self.fund("anna", "hauptstadt", "mauerbau")
        self.assertFalse(r.knows("hauptstadt", "mauerbau"))
        for d in range(1, 5):
            self.assertEqual(self.adv(d), [])
        ev = self.adv(5)
        self.assertEqual((ev[0]["tech"], ev[0]["first"], ev[0]["pioneer"]), ("mauerbau", True, "anna"))
        self.assertIn("Erfinder: Mauerbau", r.view("anna")["titles"])
        s.contribute("anna", "hauptstadt", "wall", 1000, {"timber@standard": 50, "iron_ingot@standard": 10})
        self.assertEqual(s.level("hauptstadt", "wall"), 1)

    def test_license_and_lead_window(self):
        r, w = self.r, self.w
        r.start("anna", "hauptstadt", "pflasterstrasse"); self.fund("anna", "hauptstadt", "pflasterstrasse"); self.adv(4)
        self.assertTrue(r.lead_active("pflasterstrasse"))
        w.day[0] = 5
        pm = r.start("ben", "sonnenwiese_ost", "pflasterstrasse")["permille"]
        self.assertEqual(pm, 1000)                                # Vorsprung: unabhängige Forschung kostet voll
        before = w.inv.balance("anna", COIN)
        r.contribute("ben", "sonnenwiese_ost", "pflasterstrasse", 600)
        r.license("ben", "sonnenwiese_ost", "pflasterstrasse")
        self.assertEqual(w.inv.balance("anna", COIN) - before, 500)
        self.assertEqual(w.inv.balance("ben", COIN), 50000 - 5000 - 300 - 600 - 500 + 120)       # Überschuss (600 - 480) zurück
        with self.assertRaises(WorldError):
            r.license("ben", "sonnenwiese_ost", "pflasterstrasse")

    def test_adopt_after_lead_never_blocked(self):
        r, w = self.r, self.w
        r.start("anna", "hauptstadt", "seefahrt"); self.fund("anna", "hauptstadt", "seefahrt"); self.adv(7)
        w.day[0] = 7 + 14
        self.assertEqual(r.start("ben", "sonnenwiese_ost", "seefahrt")["permille"], 400)

    def test_epoch_lock_prereq_and_roundtrip(self):
        r = self.r
        with self.assertRaises(WorldError):
            r.start("anna", "hauptstadt", "dampfkraft")
        r.set_epoch(1)
        with self.assertRaises(WorldError):
            r.start("anna", "hauptstadt", "dampfkraft")           # Voraussetzung Mauerbau
        with self.assertRaises(WorldError):
            r.set_epoch(0)
        r.start("anna", "hauptstadt", "mauerbau")
        snap = self.w.snapshot()
        self.assertEqual(json.loads(r.to_json()), snap["research"])
        self.assertEqual(check_consistency(self.w), [])
