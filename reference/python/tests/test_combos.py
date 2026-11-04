"""Elementkombinationen (AP 4a, ADR-0042): 36 Paare, 84 Dreier, ungeordnet, klassenabhängig, begrenzt."""
import json
import unittest
from itertools import permutations

from mmo_cee import CharacterService, combos
from mmo_cee.rules import load_rules

from .helpers import attune

R = load_rules("rules_v9.json")
EL = combos.load_element_rules()
CLASSES = R["identity"]["classes"]


class CatalogTests(unittest.TestCase):
    def test_anzahlen_36_und_84(self):
        self.assertEqual(len(combos.all_combinations(R, 2)), 36)
        self.assertEqual(len(combos.all_combinations(R, 3)), 84)
        c = combos.catalog(R)
        self.assertEqual((len(c["pairs"]), len(c["triples"])), (36, 84))
        self.assertEqual(len({p["key"] for p in c["pairs"]}), 36)

    def test_ungeordnet_und_ohne_wiederholung(self):
        keys = {combos.combo_key(list(p)) for p in permutations(["fire", "wind"])}
        self.assertEqual(keys, {"fire+wind"})
        self.assertEqual(len({combos.combo_key(list(p)) for p in permutations(["fire", "wind", "ice"])}), 1)
        for bad in (["fire"], ["fire", "fire"], ["fire", "wind", "ice", "earth"], []):
            with self.assertRaises(ValueError):
                combos.combo_key(bad)

    def test_daten_stimmen_mit_den_cee_regeln_ueberein(self):
        self.assertEqual(sorted(EL["elements"]), sorted(R["elements"]["all"]))
        self.assertEqual(sorted(EL["delivery"]), sorted(CLASSES))
        for e, v in EL["elements"].items():
            self.assertTrue(v["domains"] and set(v["domains"]) <= set(EL["domains"]), e)
        for c in CLASSES:
            self.assertEqual(set(EL["delivery"][c]), set(EL["domains"]), c)
        self.assertEqual(EL["limits"]["triple_requires_attuned"], R["elements"]["max_total"])

    def test_jede_kombination_hat_fuer_jede_klasse_eine_umsetzung(self):
        for p in combos.catalog(R)["pairs"] + combos.catalog(R)["triples"]:
            self.assertEqual(set(p["variants"]), set(CLASSES), p["key"])
            for c in CLASSES:
                self.assertEqual(len(p["variants"][c]), len(p["domains"]))
                self.assertTrue(all(isinstance(t, str) and t for t in p["variants"][c]))

    def test_gleiche_kombination_wirkt_je_klasse_anders(self):
        for p in combos.catalog(R)["pairs"]:
            texte = [tuple(p["variants"][c]) for c in CLASSES]
            self.assertEqual(len(set(texte)), len(CLASSES), p["key"])                 # keine Klasse bekommt dieselbe Umsetzung

    def test_stapelgrenze_und_gegenspiel(self):
        cap = EL["limits"]["max_same_domain_per_combination"]
        for p in combos.catalog(R)["triples"]:
            self.assertTrue(all(1 <= d["weight"] <= cap for d in p["domains"]), p["key"])
            self.assertTrue(all(d["counterplay"] for d in p["domains"]))

    def test_katalog_ist_deterministisch_und_serialisierbar(self):
        a = json.dumps(combos.catalog(R), sort_keys=True, ensure_ascii=False)
        self.assertEqual(a, json.dumps(combos.catalog(R), sort_keys=True, ensure_ascii=False))


class UnlockTests(unittest.TestCase):
    def setUp(self):
        self.s = CharacterService(rules=R)
        self.s.create("p", "player")
        self.s.record("p", "identity.xp_gained", {"amount": 200000})                    # hohe Stufe für das dritte Element

    def test_ohne_und_mit_einem_element_keine_kombination(self):
        self.assertEqual(self.s.element_combinations("p"), [])
        attune(self.s, "p", "fire")
        self.assertEqual(self.s.element_combinations("p"), [])

    def test_zwei_elemente_ein_paar_frei_wahlbar(self):
        attune(self.s, "p", "wind")
        attune(self.s, "p", "shadow")                                                    # Reihenfolge der Prägung egal
        c = self.s.element_combinations("p")
        self.assertEqual([x["key"] for x in c], ["shadow+wind"])
        self.assertEqual(set(c[0]["variants"]), set(CLASSES))                          # ohne Klasse: Vorschau aller drei Umsetzungen

    def test_klasse_bestimmt_die_umsetzung(self):
        out = {}
        for cls in CLASSES:
            s = CharacterService(rules=R)
            s.create("p", "player")
            s.record("p", "identity.class_chosen", {"base_class": cls})
            attune(s, "p", "shadow")
            attune(s, "p", "wind")
            out[cls] = s.element_combinations("p")[0]["variants"]
            self.assertEqual(list(out[cls]), [cls])
        self.assertEqual(len({json.dumps(v) for v in out.values()}), 3)

    def test_drei_elemente_geben_drei_paare_und_einen_dreier(self):
        for e in ("fire", "wind", "ice"):
            attune(self.s, "p", e)
        keys = [x["key"] for x in self.s.element_combinations("p")]
        self.assertEqual(sorted(keys), sorted(["fire+ice", "fire+wind", "ice+wind", "fire+ice+wind"]))


if __name__ == "__main__":
    unittest.main()
