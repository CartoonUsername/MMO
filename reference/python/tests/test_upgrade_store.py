"""AP 40: Spielstand auf eine höhere CEE-Regelversion heben (ADR-0071)."""
import json
import tempfile
import unittest
from pathlib import Path

from mmo_game import GameServer, load_game_rules
from mmo_game.upgrade import main, upgrade_store
from mmo_world.persistence import Store
from tests.test_game import Bot


class UpgradeStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "data"
        R = load_game_rules("game_rules_v18.json")                              # alter Stand: CEE v9
        self.g = GameServer(R)
        a = Bot(self.g, "anna")
        a.call("game.join")
        self.g.world.svc.record("anna", "profession.work", {"profession": "smithing", "xp": 50})
        self.gen = self.g.save(Store(self.path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_upgrade_keeps_old_generation_and_game_state(self):
        self.assertEqual(self.g.world.svc.rules.version, "9")
        out = upgrade_store(self.path, "rules_v10.json")
        self.assertEqual((out["from_rules"], out["to_rules"], out["generation_old"], out["generation_new"], out["game_state_kept"]), ("9", "10", self.gen, self.gen + 1, True))
        store = Store(self.path)
        self.assertEqual(store.generations(), [self.gen, self.gen + 1])
        self.assertEqual(store.load(self.gen).svc.rules.version, "9")                  # Rückweg bleibt
        self.assertTrue((self.path / f"game_state.gen-{self.gen}.json").exists())
        g2 = GameServer.load(store)                                                    # Standardregeln v19, geladene Welt v10
        self.assertEqual(g2.world.svc.rules.version, "10")
        self.assertIn("anna", g2.saved_pos)                                            # Spielzustand übernommen
        self.assertEqual(g2.world.specialize("anna", "smithing", "refining")["paid"], 0)

    def test_failures_leave_the_store_untouched_and_cli_reports_them(self):
        before = sorted(p.name for p in self.path.iterdir())
        with self.assertRaises(Exception):
            upgrade_store(self.path, "rules_v9.json")                                  # nicht höher
        with self.assertRaises(Exception):
            upgrade_store(self.path, "../rules_v10.json")
        self.assertEqual(sorted(p.name for p in self.path.iterdir()), before)
        self.assertEqual(main(["--data", str(self.path), "--to", "rules_v9.json"]), 1)
        self.assertEqual(main([]), 2)
        self.assertEqual(main(["--data", str(self.path), "--to", "rules_v10.json"]), 0)


if __name__ == "__main__":
    unittest.main()
