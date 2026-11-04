import copy
import tempfile
import unittest
from types import SimpleNamespace

from mmo_cee.rules import load_rules
from mmo_game import GameServer, load_game_rules
from mmo_sim.balance import FAMILIES, matrix
from mmo_sim.rules import load_sim_rules
from mmo_world.persistence import Store

R = load_game_rules()
C = load_sim_rules(R["sim_rules"])
ECON = load_rules(R["cee_rules"])["economy"]
BASE = {k: v["base_value"] for k, v in ECON["items"].items()}
GRADES = ECON["grade_permille"]
VICTORY = SimpleNamespace(players=[SimpleNamespace(outcome="victory", actions={"light_hit": 1}), SimpleNamespace(outcome="victory", actions={"light_hit": 1})])


def value(key, qty):
    if key == "coin@gold":
        return qty
    item, grade = key.split("@")
    return BASE[item] * GRADES[grade] // 1000 * qty


def table_value(types):
    return sum(value(k, q) for t in types for k, q in R["drops"].get(t, {}).items())


class Bot:
    def __init__(self, g, name):
        self.g, self.name = g, name
        self.sid, _ = g.connect(name)


class DropTableTests(unittest.TestCase):
    def test_tables_use_known_enemies_and_tradable_items(self):
        g = GameServer()
        for t, items in R["drops"].items():
            self.assertIn(t, C["opponents"], t)
            for key, q in items.items():
                self.assertIsInstance(q, int)
                self.assertGreater(q, 0)
                if key != "coin@gold":
                    g.world.trading.parse(key)
        self.assertNotIn("wolf_pup", R["drops"])                                      # Beschworene bringen nichts
        self.assertNotIn("stone_imp", R["drops"])

    def test_every_world_enemy_type_has_loot_except_summons(self):
        for e in R["enemies"]:
            self.assertIn(e["type"], R["drops"], e["type"])

    def test_rarer_enemies_pay_more(self):
        self.assertGreater(table_value(["alpha_wolf"]), 3 * table_value(["wolf"]))
        self.assertGreater(table_value(["stone_heart_colossus"]), 5 * table_value(["alpha_wolf"]))
        self.assertIn("iron_blade@fine", R["drops"]["stone_heart_colossus"])

    def test_respawn_times_are_longer_for_rare_enemies(self):
        by = R["respawn_ticks_by_type"]
        self.assertGreater(by["alpha_wolf"], R["respawn_ticks"])
        self.assertGreater(by["stone_heart_colossus"], by["alpha_wolf"])
        g = GameServer()
        boss = next(e for e in g.enemies if e["type"] == "stone_heart_colossus")
        self.assertTrue(boss["alive"])


class RespawnTests(unittest.TestCase):
    def test_respawn_time_follows_the_enemy_type(self):
        for by_type, expect in (({"wolf": 900}, 900), ({}, R["respawn_ticks"])):
            r = copy.deepcopy(R)
            r["enemies"] = [{"type": "wolf", "at": [2000, 1800]}]
            r["respawn_ticks_by_type"] = by_type
            g = GameServer(r)
            a = Bot(g, "anna")
            g.world.svc.record("anna", "identity.xp_gained", {"amount": 100000})
            g.handle(a.sid, {"v": 1, "id": "j", "cmd": "game.join", "args": {"char": "anna"}})
            g.players["anna"]["pos"] = (2000, 2100)
            e = g.enemies[0]
            for i in range(4000):
                if "anna" in g.fight_of and i % 8 == 0:
                    g.handle(a.sid, {"v": 1, "id": f"f{i}", "cmd": "game.fight", "args": {"char": "anna", "input": "light"}})
                g.tick()
                if not e["alive"]:
                    break
            self.assertFalse(e["alive"])
            self.assertEqual(e["respawn_at"] - g.tick_no, expect)


class ValueTests(unittest.TestCase):
    """Beutewert je Spieler und Sekunde (Kampfdauer + 15 s Weg/Wartezeit, mal Risikoaufschlag) im Vergleich zum Sammeln (ca. 1,6 Münzen/s je Sammelpunkt)."""

    SPEC = {"Wolf": (1, "average"), "Wolfsrudel (2)": (1, "average"), "Höhlenbär": (1, "average"), "Irrlicht + Wolf": (1, "average"),
            "Moorhexe": (1, "average"), "Moorhexe + Irrlicht": (1, "average"), "Schattenjäger": (1, "average"), "Steinwächter": (1, "average"),
            "Totem-Beschwörer": (1, "average"), "Alpha + 2 Wölfe": (2, "average"), "Steinherz-Koloss (Boss)": (4, "good")}

    def rate(self, name):
        n, skill = self.SPEC[name]
        opp, lvl = FAMILIES[name]
        m = matrix(C, opp, [lvl] * n, skill, spawns=1 if "Boss" in name else 6)
        return table_value(opp) * 1000 // (n * (m["seconds"] + 15) * (1000 + m["hp_lost"]) // 1000) / 1000

    def test_combat_pays_roughly_like_gathering_adjusted_for_risk(self):
        for name in self.SPEC:
            if "Boss" in name:
                continue
            r = self.rate(name)
            self.assertTrue(1.4 <= r <= 3.0, (name, r))

    def test_the_boss_pays_more_but_not_absurdly(self):
        r = self.rate("Steinherz-Koloss (Boss)")
        self.assertTrue(2.0 <= r <= 4.0, r)

    def test_gathering_reference(self):
        node = R["nodes"][0]
        per_second = value(node["item"], node["qty"]) * 10 / R["node_cooldown_ticks"]
        self.assertAlmostEqual(per_second, 1.6, places=1)                           # Bezugsgröße der Bänder


class DecayTests(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()
        self.a = Bot(self.g, "anna")
        self.drops = R["drops"]["wolf"]

    def kill(self, *chars, types=("wolf",)):
        res = SimpleNamespace(players=[SimpleNamespace(outcome="victory", actions={"light_hit": 1}) for _ in chars])
        return self.g._loot(list(chars), res, list(types))

    def test_the_table_is_applied_kill_by_kill(self):
        table = R["loot_decay_permille"]
        seen = []
        for i in range(len(table) + 2):
            loot, f = self.kill("anna")
            seen.append((f["wolf"], loot["anna"].get("coin@gold", 0)))
        for i, (f, coin) in enumerate(seen):
            want = table[min(i, len(table) - 1)]
            self.assertEqual((f, coin), (want, self.drops["coin@gold"] * want // 1000), i)
        self.assertEqual(self.g.kills["anna|wolf"], len(table) + 2)

    def test_items_round_down_and_vanish_at_zero(self):
        for _ in range(3):
            self.kill("anna")
        loot, f = self.kill("anna")                                                   # vierter Kill: 750 ‰
        self.assertEqual(f["wolf"], 750)
        self.assertEqual(loot["anna"]["healing_herb@standard"], self.drops["healing_herb@standard"] * 750 // 1000)
        g = GameServer(copy.deepcopy({**R, "drops": {"wolf": {"coin@gold": 5, "healing_herb@standard": 1}}, "loot_decay_permille": [1000, 400]}))
        g.world.svc.create("zed", "player")
        res = SimpleNamespace(players=[SimpleNamespace(outcome="victory", actions={"light_hit": 1})])
        g._loot(["zed"], res, ["wolf"])
        loot, _ = g._loot(["zed"], res, ["wolf"])
        self.assertEqual(loot["zed"], {"coin@gold": 2})                               # 1 * 400 // 1000 = 0: Gegenstand entfällt

    def test_counts_are_per_character_and_per_enemy_type(self):
        for _ in range(4):
            self.kill("anna")
        self.assertEqual(self.kill("anna", types=("bear",))[1]["bear"], 1000)         # andere Art: frisch
        Bot(self.g, "ben")
        self.assertEqual(self.kill("ben")[1]["wolf"], 1000)                           # andere Figur: frisch

    def test_group_loot_uses_the_average_factor_and_counts_for_everyone(self):
        Bot(self.g, "ben")
        for _ in range(4):
            self.kill("anna")                                                         # anna: 4 Kills (Faktor jetzt 500), ben: 0 (1000)
        loot, f = self.kill("anna", "ben")
        self.assertEqual(f["wolf"], (500 + 1000) // 2)
        self.assertEqual(sum(l.get("coin@gold", 0) for l in loot.values()), self.drops["coin@gold"] * 750 // 1000)
        self.assertEqual((self.g.kills["anna|wolf"], self.g.kills["ben|wolf"]), (5, 1))

    def test_only_contributors_count_and_defeats_give_nothing(self):
        res = SimpleNamespace(players=[SimpleNamespace(outcome="victory", actions={}), SimpleNamespace(outcome="victory", actions={"light_hit": 1})])
        Bot(self.g, "ben")
        loot, f = self.g._loot(["anna", "ben"], res, ["wolf"])
        self.assertEqual(list(loot), ["ben"])
        self.assertNotIn("anna|wolf", self.g.kills)
        res = SimpleNamespace(players=[SimpleNamespace(outcome="defeat", actions={"light_hit": 1})])
        self.assertEqual(self.g._loot(["anna"], res, ["wolf"]), ({}, {}))
        self.assertEqual(self.g.kills.get("anna|wolf", 0), 0)

    def test_a_new_day_resets_the_counts(self):
        for _ in range(5):
            self.kill("anna")
        self.assertEqual(self.g.kills["anna|wolf"], 5)
        for _ in range(R["ticks_per_day"]):
            self.g.tick()
        self.assertEqual(self.g.kills, {})
        self.assertEqual(self.kill("anna")[1]["wolf"], 1000)

    def test_counts_survive_a_save_on_the_same_day_only(self):
        for _ in range(5):
            self.kill("anna")
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            self.g.save(store)
            h = GameServer.load(store)
            self.assertEqual(h.kills, {"anna|wolf": 5})
            # Spielstand eines anderen Tages (z. B. nach längerer Pause): Zähler werden nicht übernommen
            import json
            f = store.path / "game_state.json"
            data = json.loads(f.read_text())
            data["kills_day"] = 999
            f.write_text(json.dumps(data))
            self.assertEqual(GameServer.load(store).kills, {})

    def test_the_fight_end_event_reports_the_factor(self):
        g = GameServer()
        a = Bot(g, "anna")
        g.handle(a.sid, {"v": 1, "id": "j", "cmd": "game.join", "args": {"char": "anna"}})
        g.kills["anna|wolf"] = 3
        g.players["anna"]["pos"] = (2000, 2100)
        g.enemies[:] = [e for e in g.enemies if e["type"] == "wolf"][:1]
        g.enemies[0].update(pos=(2000, 1800), home=(2000, 1800))
        for i in range(4000):
            if "anna" in g.fight_of and i % 8 == 0:
                g.handle(a.sid, {"v": 1, "id": f"f{i}", "cmd": "game.fight", "args": {"char": "anna", "input": "light"}})
            g.tick()
            if g.kills.get("anna|wolf", 0) > 3:
                break
        end = [e for e in g.drain(a.sid) if e["ev"] == "fight_end"][0]
        self.assertEqual(end["loot_factor"], {"wolf": 750})
        self.assertEqual(end["loot"]["coin@gold"], self.drops["coin@gold"] * 750 // 1000)


if __name__ == "__main__":
    unittest.main()
