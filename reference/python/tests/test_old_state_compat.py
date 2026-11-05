"""AP 72: Ein unter den alten Regeldateien gespeicherter Spielstand lädt und läuft unter den neuen Standards (Deployment-Sicherheit)."""
import json
import unittest
from unittest import mock

from mmo_world import world as W
from mmo_world.persistence import check_consistency, export_world, import_world

OLD = dict(SETTLEMENT_RULES="settlement_rules_v1.json", RESEARCH_RULES="research_rules_v1.json", EQUIPMENT_RULES="equipment_rules_v1.json",
           COMMUNITY_RULES="community_rules_v2.json")
CRC = "coin@gold"


class OldStateCompat(unittest.TestCase):
    def build_old(self):
        with mock.patch.multiple(W, **OLD):
            w = W.World("rules_v9.json")
            for c in ("anna", "ben"):
                w.svc.create(c, "player")
                w.svc.record(c, "identity.xp_gained", {"amount": 10000})
                w.inv.deposit(c, CRC, 50000)
                for k in ("timber@standard", "wooden_beam@standard", "iron_ingot@standard"):
                    w.inv.deposit(c, k, 500)
            w.settlements.found("anna", "moorufer", "Moorheim")
            w.settlements.buy_plot("anna", "moorufer", 1)
            w.settlements.contribute("anna", "moorufer", "market_square", 800, {"timber@standard": 40})
            w.settlements.buy_plot("ben", "hauptstadt", 1)
            w.inv.deposit("ben", "iron_blade@common", 1)
            w.equipment.equip("ben", "iron_blade@common")
            w.guilds.found("anna", "Nordwacht", "NW")
            self.assertEqual(str(w.equipment.R["version"]) + str(w.research.R["version"]), "11")             # wirklich alte Regeln aktiv
            self.assertNotIn("sets", w.equipment.R)
            return w

    def test_old_snapshot_loads_under_new_defaults_and_new_features_work(self):
        old = self.build_old()
        env, logs = export_world(old)
        w = import_world(json.loads(json.dumps(env)), json.loads(json.dumps(logs)))           # neue Standard-Regeldateien
        self.assertEqual((str(w.equipment.R["version"]), str(w.research.R["version"])), ("2", "2"))
        self.assertEqual(check_consistency(w), [])
        self.assertEqual(w.settlements.level("moorufer", "market_square"), 1)                  # gebaute Stufe bleibt
        self.assertEqual(w.equipment.worn["ben"]["weapon"], "iron_blade@common")
        self.assertIn("anna", w.guilds.member_of)
        # Neues Verhalten gilt ab jetzt: Rabatt der gebauten Stufe nach v2-Tabelle, Stufe 2 braucht jetzt Marktrecht
        self.assertEqual(w.settlements.fee_discount_permille("anna"), 250)
        with self.assertRaises(Exception):
            w.settlements.contribute("anna", "moorufer", "market_square", 2000, {"wooden_beam@standard": 40})
        # Neue Funktionen auf altem Stand: Chat, Verkauf, Zweigwahl-Ablehnung (CEE bleibt v9)
        self.assertEqual(w.guilds.say("anna", "Hallo")["n"], 1)
        w.settlements.sell_plot("ben", "hauptstadt", 1, "anna", 100)
        self.assertEqual(w.settlements.accept_sale("anna", "hauptstadt", 1)["fee"], 5)
        with self.assertRaises(Exception):
            w.specialize("anna", "smithing", "refining")
        self.assertEqual(check_consistency(w), [])
        env2, logs2 = export_world(w)                                                         # und wieder speichern/laden
        again = import_world(json.loads(json.dumps(env2)), json.loads(json.dumps(logs2)))
        self.assertEqual(again.snapshot(), w.snapshot())


if __name__ == "__main__":
    unittest.main()
