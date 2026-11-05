"""AP 95 (ADR-0081): Hauptstadt als Ort im Spiel (game_rules_v20): Layout, Prüfung, Abfrage, Schutzzone, Ereignisse."""
import copy
import math
import unittest

from mmo_game import GameServer, load_game_rules
from mmo_game.terrain import TerrainError

R20 = load_game_rules("game_rules_v20.json")
R19 = load_game_rules("game_rules_v19.json")
CENTER = tuple(R20["capital"]["center"])           # Marktplatz
OUTSIDE_NEAR = (3100, 1900)                         # knapp außerhalb (Abstand ~632 > 550)
WOLF_FAR = {"type": "wolf", "at": [3300, 2000]}     # außerhalb, aber im Alarmradius (700) von OUTSIDE_NEAR und vom Zentrum aus sichtbar


def rules(base=R20, **changes):
    r = copy.deepcopy(base)
    r.update(changes)
    return r


def cap(**changes):
    r = copy.deepcopy(R20)
    r["capital"].update(changes)
    return r


class Bot:
    def __init__(self, g, name):
        self.g, self.name = g, name
        self.sid, _ = g.connect(name)
        self.n = 0

    def call(self, cmd, **args):
        self.n += 1
        return self.g.handle(self.sid, {"v": 1, "id": f"{self.name}-{self.n}", "cmd": cmd, "args": {"char": self.name, **args}})

    def events(self):
        return self.g.drain(self.sid)


def solo(r, pos):
    g = GameServer(r)
    a = Bot(g, "anna")
    assert a.call("game.join")["ok"]
    g.players["anna"]["pos"] = tuple(pos)
    g.players["anna"]["immune_until"] = 0
    return g, a


class Layout(unittest.TestCase):
    def test_default_rules_are_v20_with_capital(self):
        self.assertEqual(load_game_rules()["version"], 20)
        self.assertEqual(R20["capital"]["site"], "hauptstadt")
        self.assertNotIn("capital", R19)

    def test_geometry(self):
        c = R20["capital"]
        d = lambda p: math.hypot(p[0] - CENTER[0], p[1] - CENTER[1])
        for o in c["gates"] + c["npcs"]:
            self.assertLessEqual(d(o["at"]), c["radius"], o["id"])
        for v in c["districts"]:
            x0, y0, x1, y1 = v["rect"]
            self.assertTrue(all(d(q) <= c["radius"] for q in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))), v["id"])
        self.assertEqual(len({v["id"] for v in c["districts"]}), len(c["districts"]))
        regions = {r["id"] for r in R20["regions"]["list"]}
        self.assertTrue({g["leads_to"] for g in c["gates"]} <= regions)
        # Alle bisherigen Regeln bleiben bis auf Version und Hauptstadtblock gleich
        a = {k: v for k, v in R20.items() if k not in ("version", "capital", "_capital_comment")}
        b = {k: v for k, v in R19.items() if k != "version"}
        self.assertEqual(a, b)

    def test_server_builds_and_services_name_known_windows(self):
        GameServer(R20)
        known = {"Figur", "Ausrüstung", "Echos", "Markt", "Herstellen", "Gruppe", "Handel", "Firma", "Siedlung", "Forschung", "Gilde", "Chronik"}
        for v in R20["capital"]["districts"]:
            self.assertTrue(set(v["services"]) <= known, v["id"])

    def test_broken_layouts_are_rejected(self):
        def bad(r, why):
            with self.assertRaises(TerrainError, msg=why):
                GameServer(r)
        c = R20["capital"]
        bad(cap(site="moorufer"), "kein Hauptstadt-Ort")
        bad(cap(site="gibtsnicht"), "unbekannter Ort")
        bad(cap(region="sunmeadow"), "Region passt nicht zum Ort")
        bad(cap(radius=0), "Radius")
        bad(cap(radius=3000), "Kreis größer als Region")
        bad(cap(center=[1800, 1300]), "Mittelpunkt im Fluss/außerhalb der Region")
        bad(cap(districts=c["districts"] + [{"id": "weit", "name": "x", "rect": [0, 0, 100, 100], "services": []}]), "Viertel außerhalb")
        bad(cap(districts=c["districts"] + [c["districts"][0]]), "doppeltes Viertel")
        bad(cap(gates=[{"id": "t", "name": "T", "at": [2900, 1800], "leads_to": "nirgends"}]), "Tor ohne Ziel")
        bad(cap(gates=[{"id": "t", "name": "T", "at": [2900, 1800], "leads_to": "crossing"}]), "Tor zurück in die eigene Region")
        bad(cap(gates=[{"id": "t", "name": "T", "at": [5000, 5000], "leads_to": "moor"}]), "Tor außerhalb")
        bad(cap(npcs=[{"id": "n", "name": "N", "role": "x", "at": [2900, 1300], "district": "gibtsnicht"}]), "NPC in unbekanntem Viertel")
        bad(cap(npcs=c["npcs"] + [c["npcs"][0]]), "doppelte NPC-ID")
        bad(rules(enemies=R20["enemies"] + [{"type": "wolf", "at": [2900, 1100]}]), "Gegner in der Stadt")


class Query(unittest.TestCase):
    def test_query_inside_district(self):
        g, a = solo(R20, CENTER)
        r = a.call("game.capital")
        self.assertTrue(r["ok"])
        res = r["result"]
        self.assertEqual(res["here"], {"district": "marktplatz"})
        self.assertTrue(res["safe_here"])
        self.assertEqual({v["id"] for v in res["districts"]}, {v["id"] for v in R20["capital"]["districts"]})
        self.assertEqual(len(res["gates"]), 3)

    def test_query_between_districts_and_outside(self):
        g, a = solo(R20, (2900, 1700))                                       # im Kreis, in keinem Viertel
        res = a.call("game.capital")["result"]
        self.assertEqual(res["here"], {"district": None})
        self.assertTrue(res["safe_here"])
        g.players["anna"]["pos"] = OUTSIDE_NEAR
        res = a.call("game.capital")["result"]
        self.assertIsNone(res["here"])
        self.assertFalse(res["safe_here"])

    def test_older_rules_have_no_capital(self):
        g, a = solo(R19, (500, 500))
        r = a.call("game.capital")
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"]["code"], "not_available")
        self.assertNotIn("capital", g.handle(a.sid, {"v": 1, "id": "s", "cmd": "game.state", "args": {"char": "anna"}})["result"]["you"])

    def test_requires_own_character_and_join(self):
        g = GameServer(R20)
        a = Bot(g, "anna")
        r = a.call("game.capital")                                          # nicht beigetreten: Layout trotzdem lesbar, ohne Ort
        self.assertTrue(r["ok"])
        self.assertIsNone(r["result"]["here"])
        b = Bot(g, "bert")
        self.assertEqual(g.handle(a.sid, {"v": 1, "id": "x", "cmd": "game.capital", "args": {"char": "bert"}})["error"]["code"], "forbidden")

    def test_snapshot_reports_district(self):
        g, a = solo(R20, CENTER)
        you = a.call("game.state")["result"]["you"]
        self.assertEqual(you["capital"], {"district": "marktplatz", "safe": True})
        g.players["anna"]["pos"] = OUTSIDE_NEAR
        self.assertIsNone(a.call("game.state")["result"]["you"]["capital"])


class SafeZone(unittest.TestCase):
    def test_enemy_notices_player_outside_but_not_inside(self):
        # Gegenprobe: ohne Schutzzone (v19) beginnt der Wolf die Verfolgung, wenn der Spieler im Alarmradius steht
        g, a = solo(rules(R19, enemies=[WOLF_FAR]), OUTSIDE_NEAR)
        g.tick()
        self.assertEqual(g.enemies[0]["state"], "chase")
        # v20, Spieler außerhalb der Stadt: dasselbe
        g, a = solo(rules(enemies=[WOLF_FAR]), OUTSIDE_NEAR)
        g.tick()
        self.assertEqual(g.enemies[0]["state"], "chase")
        # v20, Spieler im Stadtkreis und ebenfalls im Alarmradius des Wolfs: bleibt ruhig
        g, a = solo(rules(enemies=[{"type": "wolf", "at": [3300, 1750]}]), (3150, 1600))
        self.assertLess(math.hypot(3300 - 3150, 1750 - 1600), R20["aggro_radius"])
        self.assertTrue(g._safe_at((3150, 1600)))
        for _ in range(30):
            g.tick()
        self.assertEqual(g.enemies[0]["state"], "idle")
        self.assertIsNone(g.players["anna"]["fight"] if "fight" in g.players["anna"] else None)
        self.assertNotIn("anna", g.fight_of)

    def test_chaser_gives_up_when_target_enters_city(self):
        g, a = solo(rules(enemies=[{"type": "wolf", "at": [3500, 2100]}]), OUTSIDE_NEAR)     # weiter weg, damit der Kampf nicht sofort beginnt
        for _ in range(3):                                                   # ein Stück verfolgen, weg von zu Hause
            g.tick()
        e = g.enemies[0]
        self.assertEqual(e["state"], "chase")
        self.assertNotEqual(e["pos"], e["home"])
        g.players["anna"]["pos"] = CENTER
        g.tick()
        self.assertEqual(e["state"], "return")
        for _ in range(200):
            g.tick()
        self.assertEqual(e["state"], "idle")                                 # wieder zu Hause
        self.assertEqual(e["pos"], e["home"])
        self.assertNotIn("anna", g.fight_of)

    def test_not_safe_when_flag_is_off(self):
        r = cap(safe=False)
        r["enemies"] = [{"type": "wolf", "at": [3300, 1750]}]
        g, a = solo(r, (3150, 1600))
        g.tick()
        self.assertEqual(g.enemies[0]["state"], "chase")
        res = a.call("game.capital")["result"]
        self.assertFalse(res["safe_here"])


class Events(unittest.TestCase):
    def test_enter_and_leave_events(self):
        g, a = solo(R20, OUTSIDE_NEAR)
        g.tick()
        a.events()                                                           # Region-Ereignisse verwerfen
        g.players["anna"]["pos"] = CENTER
        g.tick()
        ev = [e for e in a.events() if e.get("ev") == "capital"]
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["state"], ev[0]["name"], ev[0]["safe"]), ("enter", "Hauptstadt", True))
        g.tick()
        self.assertEqual([e for e in a.events() if e.get("ev") == "capital"], [])        # nicht doppelt
        g.players["anna"]["pos"] = OUTSIDE_NEAR
        g.tick()
        ev = [e for e in a.events() if e.get("ev") == "capital"]
        self.assertEqual([(e["state"], e["safe"]) for e in ev], [("leave", False)])

    def test_rejoin_inside_announces_again(self):
        g, a = solo(R20, CENTER)
        g.tick()
        self.assertEqual([e["state"] for e in a.events() if e.get("ev") == "capital"], ["enter"])
        g.disconnect(a.sid)
        self.assertNotIn("anna", g._in_capital)


if __name__ == "__main__":
    unittest.main()
