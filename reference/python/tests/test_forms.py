"""AP 6: Wesensformen mit Vorschau und bestätigter, dauerhafter Annahme (ADR-0045)."""
import unittest

from mmo_cee import CharacterService, RuleViolation
from mmo_cee.forms import load_definitions
from mmo_cee.rules import load_rules
from mmo_world.errors import WorldError
from mmo_server.protocol import COMMANDS
from mmo_world.world import World

R9 = load_rules("rules_v9.json")


class Defs(unittest.TestCase):
    def test_definitions_cover_rules(self):
        d = load_definitions()
        for f in R9["essence"]["forms"]:
            self.assertIn(f, d["forms"])
        for k in R9["essence"]["decisions"]:
            self.assertIn(k, d["decisions"])
        for f in R9["essence"]["forms"].values():
            for k in list(f["modifiers"]["advantages"]) + list(f["modifiers"]["disadvantages"]):
                self.assertIn(k, d["modifiers"])
        for a in R9["combat"]["abilities"]:
            if not a.startswith("_"):
                self.assertIn(a, d["abilities"])


class Preview(unittest.TestCase):
    def setUp(self):
        self.s = CharacterService(rules=R9)
        self.s.create("a", "player")

    def test_fresh_character(self):
        p = self.s.essence_preview("a")
        self.assertEqual(p["form"], "human")
        st = {f["id"]: f["status"] for f in p["forms"]}
        self.assertEqual(st["twilight_kin"], "secret")
        self.assertTrue(all(f["permanent"] and f["tradeoff"] for f in p["forms"]))
        self.assertTrue(all(not d["available"] for d in p["decisions"]))
        self.assertIn("dauerhaft", p["warning"])

    def test_decision_trial_adopt_flow(self):
        w = World()
        s = w.svc
        s.create("a", "player")
        s.record("a", "identity.xp_gained", {"amount": 10000})
        s.record("a", "element.exposure", {"element": "fire", "amount": 100})
        s.record("a", "element.attuned", {"element": "fire"})
        s.record("a", "profession.work", {"profession": "smithing", "xp": 3700})
        call = lambda n, **a: COMMANDS[n].call(w, {"char": "a", **a})
        call("essence.decide", decision="ember_vow", choice="accept")
        f = {x["id"]: x for x in s.essence_preview("a")["forms"]}["ember_kin"]
        self.assertEqual(f["status"], "eligible")
        self.assertGreaterEqual(f["score"], f["threshold"])
        call("essence.trial", form="ember_kin")
        self.assertEqual({x["id"]: x["status"] for x in s.essence_preview("a")["forms"]}["ember_kin"], "trial_passed")
        call("essence.adopt", form="ember_kin", ack="adopt:ember_kin")
        p = s.essence_preview("a")
        self.assertEqual(p["form"], "ember_kin")
        self.assertEqual({x["id"]: x["status"] for x in p["forms"]}["umbral_kin"], "locked_in")
        with self.assertRaises(RuleViolation):                        # nicht umkehrbar
            call("essence.adopt", form="stone_born", ack="adopt:stone_born")


class Gateway(unittest.TestCase):
    def test_adopt_needs_explicit_ack_and_trial(self):
        w = World()
        w.svc.create("a", "player")
        adopt = COMMANDS["essence.adopt"].call
        with self.assertRaises(WorldError):
            adopt(w, {"char": "a", "form": "ember_kin", "ack": "yes"})
        with self.assertRaises(RuleViolation):
            adopt(w, {"char": "a", "form": "ember_kin", "ack": "adopt:ember_kin"})   # keine Prüfung bestanden
        with self.assertRaises(RuleViolation):
            COMMANDS["essence.trial"].call(w, {"char": "a", "form": "ember_kin"})    # Voraussetzungen fehlen
        self.assertEqual(w.svc.state("a").parts["essence"]["form"], "human")


if __name__ == "__main__":
    unittest.main()
