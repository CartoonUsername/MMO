"""AP 73–75: Anzeigetitel aus der Weltchronik wählen (ADR-0080)."""
import json
import unittest

from mmo_game import GameServer
from mmo_world.persistence import check_consistency, export_world, import_world
from tests.test_game import Bot


class TitleChoice(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()
        self.w = self.g.world
        self.a, self.b = Bot(self.g, "anna"), Bot(self.g, "ben")
        for bot in (self.a, self.b):
            bot.call("game.join")
        self.w.chronicle.record("settlement_founded", ["anna"], key="settlement:moorufer", name="Moorheim")
        self.w.chronicle.record("dungeon_cleared", ["anna", "ben"], key="dungeon:x", name="Gruft")

    def prestige(self, bot):
        return bot.call("query.prestige")["result"]

    def test_choose_show_and_clear(self):
        titles = {t["id"]: t["name"] for t in self.prestige(self.a)["titles"]}
        self.assertEqual(len(titles), 2)
        self.assertEqual((self.prestige(self.a)["chosen"], self.prestige(self.a)["display"]), (None, None))
        tid = next(i for i, n in titles.items() if n == "Gründer von Moorheim")
        r = self.a.call("title.choose", title=tid)
        self.assertTrue(r["ok"])
        self.assertEqual((self.prestige(self.a)["chosen"], self.prestige(self.a)["display"]), (tid, "Gründer von Moorheim"))
        self.assertTrue(self.a.call("title.choose")["ok"])                                           # ohne Titel = entfernen
        self.assertEqual(self.prestige(self.a)["display"], None)
        self.assertEqual(self.w.chronicle.chosen, {})

    def test_cannot_choose_titles_one_does_not_have(self):
        foreign = next(t["id"] for t in self.prestige(self.a)["titles"] if t["name"].startswith("Gründer"))
        for bad in (foreign, "nope", "", 7, ["x"], True):
            self.assertFalse(self.b.call("title.choose", title=bad)["ok"], bad)
        self.assertEqual(self.w.chronicle.chosen, {})
        self.assertFalse(self.b.call("title.choose", title=foreign)["ok"])                           # Ben hat nur den Dungeon-Titel

    def test_unused_choice_keeps_state_and_roundtrips_when_used(self):
        self.assertNotIn("chosen", json.loads(self.w.chronicle.to_json()))
        tid = self.prestige(self.b)["titles"][0]["id"]
        self.assertTrue(self.b.call("title.choose", title=tid)["ok"])
        env, logs = export_world(self.w)
        back = import_world(json.loads(json.dumps(env)), json.loads(json.dumps(logs)))
        self.assertEqual(back.chronicle.prestige("ben")["chosen"], tid)
        self.assertEqual(check_consistency(back), [])


if __name__ == "__main__":
    unittest.main()
