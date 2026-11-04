"""Drei Schichten der Charakteridentität (ADR-0040): Lebensgeschichte nur anhängend, Profil verschiebbar, Identität dauerhaft."""
import copy
import json
import unittest

from mmo_cee import CharacterService
from mmo_cee.rules import load_rules

from .helpers import attune
from .test_essence import ember_ready


def make(rules="rules_v3.json"):
    return CharacterService(rules=load_rules(rules))


def types(svc, c="p"):
    return [m["type"] for m in svc.layers(c)["life_story"]["milestones"]]


class LayerTests(unittest.TestCase):
    def test_neue_figur_ist_mensch_ohne_geschichte_ausser_der_geburt(self):
        s = make()
        s.create("p", "player")
        L = s.layers("p")
        self.assertEqual(types(s), ["identity.created"])
        self.assertEqual(L["essence_identity"]["form"], "human")
        self.assertFalse(L["essence_identity"]["permanent"])
        self.assertEqual(L["current_profile"]["level"], 1)
        self.assertEqual(L["life_story"]["event_count"], 1)

    def test_meilensteine_in_reihenfolge_und_stufen(self):
        s = make()
        s.create("p", "player")
        s.record("p", "identity.class_chosen", {"base_class": "archer"})
        s.record("p", "identity.xp_gained", {"amount": 450})                 # Stufe 3 → zwei Stufenmeilensteine
        t = types(s)
        self.assertEqual(t, ["identity.created", "identity.class_chosen", "identity.level_reached", "identity.level_reached"])
        lv = [m["data"]["level"] for m in s.layers("p")["life_story"]["milestones"] if m["type"] == "identity.level_reached"]
        self.assertEqual(lv, [2, 3])

    def test_lebensgeschichte_ist_nur_anhaengend(self):
        s = make()
        ember_ready(s, "p")
        vorher = s.layers("p")["life_story"]["milestones"]
        s.record("p", "essence.trial_passed", {"form": "ember_kin"})
        s.record("p", "essence.adopted", {"form": "ember_kin"})
        s.record("p", "profession.work", {"profession": "alchemy", "xp": 5000})      # Schwerpunkt verschiebt sich
        nachher = s.layers("p")["life_story"]["milestones"]
        self.assertEqual(nachher[:len(vorher)], vorher)                              # Präfix bleibt unverändert
        self.assertIn("essence.adopted", [m["type"] for m in nachher])
        self.assertGreater(len(nachher), len(vorher))

    def test_profil_verschiebt_sich_geschichte_bleibt(self):
        s = make()
        s.create("p", "player")
        s.record("p", "profession.work", {"profession": "smithing", "xp": 700})
        a = s.layers("p")
        s.record("p", "profession.work", {"profession": "alchemy", "xp": 5000})
        b = s.layers("p")
        self.assertIn("smithing", b["current_profile"]["professions"])               # früherer Weg geht nicht verloren
        self.assertGreater(b["current_profile"]["professions"]["alchemy"]["xp"], b["current_profile"]["professions"]["smithing"]["xp"])
        self.assertEqual(b["life_story"]["milestones"][:len(a["life_story"]["milestones"])], a["life_story"]["milestones"])
        self.assertEqual(b["life_story"]["counts"]["work_sessions"], 2)

    def test_wesenidentitaet_ist_nach_annahme_dauerhaft(self):
        s = make()
        ember_ready(s, "p")
        s.record("p", "essence.trial_passed", {"form": "ember_kin"})
        s.record("p", "essence.adopted", {"form": "ember_kin"})
        ident = s.layers("p")["essence_identity"]
        self.assertEqual((ident["form"], ident["permanent"], ident["form_adopted"]), ("ember_kin", True, True))
        self.assertIsNotNone(ident["adopted_at_seq"])
        self.assertIn("fire", ident["attuned_elements"])
        s.record("p", "identity.xp_gained", {"amount": 99999})
        s.record("p", "profession.work", {"profession": "trade", "xp": 3000})
        self.assertEqual(s.layers("p")["essence_identity"], ident)                  # Weiterspielen ändert die Identität nicht

    def test_ableitung_ist_rein_und_deterministisch(self):
        s = make()
        ember_ready(s, "p")
        n = len(s.log.events("p"))
        a = json.dumps(s.layers("p"), sort_keys=True)
        b = json.dumps(s.layers("p"), sort_keys=True)
        self.assertEqual(a, b)
        self.assertEqual(len(s.log.events("p")), n)                                  # schreibt nichts
        s2 = make()
        s2.create("p", "player")
        for e in s.log.events("p")[1:]:                                              # gleiche Ereignisse → gleiche Schichten
            s2.record("p", e.type, copy.deepcopy(e.payload))
        self.assertEqual(json.dumps(s2.layers("p"), sort_keys=True), a)

    def test_kopfhash_und_ereigniszahl_verweisen_auf_die_hashkette(self):
        s = make()
        ember_ready(s, "p")
        ls = s.layers("p")["life_story"]
        ev = s.log.events("p")
        self.assertEqual((ls["event_count"], ls["head_hash"]), (len(ev), ev[-1].hash))

    def test_alle_regelversionen_liefern_schichten(self):
        for v in range(1, 10):
            s = make(f"rules_v{v}.json")
            s.create("p", "player")
            L = s.layers("p")
            self.assertEqual(set(L), {"life_story", "current_profile", "essence_identity"}, v)

    def test_keine_realen_personendaten_in_den_schichten(self):
        s = make()
        ember_ready(s, "p")
        text = json.dumps(s.layers("p")).lower()
        for verboten in ("password", "email", "token", "ip"):
            self.assertNotIn(f'"{verboten}"', text)


if __name__ == "__main__":
    unittest.main()
