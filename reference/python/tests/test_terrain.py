import copy
import json
import unittest

from mmo_game import GameServer, load_game_rules
from mmo_game.terrain import Terrain, TerrainError

R = load_game_rules()


def cfg(**changes):
    c = copy.deepcopy(R["terrain"])
    c.update(changes)
    return c


def terr(**changes):
    return Terrain(cfg(**changes), R["zone"], R["speed_cm_per_tick"])


T = terr()


class Bot:
    def __init__(self, g, name):
        self.g, self.name = g, name
        self.sid, _ = g.connect(name)
        self.n = 0

    def call(self, cmd, **args):
        self.n += 1
        return self.g.handle(self.sid, {"v": 1, "id": f"{self.name}-{self.n}", "cmd": cmd, "args": {"char": self.name, **args}})


class RulesTests(unittest.TestCase):
    def bad(self, **changes):
        with self.assertRaises(TerrainError):
            terr(**changes)

    def test_shipped_map_is_valid(self):
        self.assertEqual(T.kind_at(500, 500), "road")
        self.assertEqual(T.kind_at(3000, 1000), "grass")

    def test_validation(self):
        k = R["terrain"]["kinds"]
        self.bad(player_radius=0)
        self.bad(player_radius=True)
        self.bad(kinds={})
        self.bad(default="lava")
        self.bad(default="water")                                                       # Grundart muss begehbar sein
        self.bad(kinds={**k, "road": 3001})
        self.bad(kinds={**k, "road": -1})
        self.bad(regions=[{"kind": "lava", "rect": [0, 0, 100, 100]}])
        self.bad(regions=[{"kind": "road", "rect": [100, 0, 100, 100]}])                # leer
        self.bad(regions=[{"kind": "road", "rect": [0, 0, 100, 99999]}])                # über den Rand
        self.bad(regions=[{"kind": "road", "rect": [0, 0, 100.5, 100]}])
        self.bad(regions=[{"kind": "water", "rect": [100, 100, 130, 900]}])             # dünner als ein Schritt (45)
        self.bad(regions=[{"kind": "water", "rect": [100, 100, 145, 900]}])             # genau ein Schritt: noch zu dünn
        terr(regions=[{"kind": "water", "rect": [100, 100, 146, 900]}])                 # einen mehr: erlaubt
        self.bad(obstacles=[{"at": [100, 100], "r": 20, "kind": "rock"}])               # Durchmesser 40 <= 45
        self.bad(obstacles=[{"at": [100, 100], "r": 90, "kind": "grass"}])              # Hindernis muss blockieren
        self.bad(obstacles=[{"at": [100, 100], "r": 90}])
        self.bad(obstacles=[{"at": [-1, 100], "r": 90, "kind": "rock"}])
        self.bad(obstacles=[{"at": [100.5, 100], "r": 90, "kind": "rock"}])


class BoundaryTests(unittest.TestCase):
    def test_obstacle_thickness_limit_depends_on_the_fastest_step(self):
        k = {**R["terrain"]["kinds"], "road": 1200}                                     # längster Schritt 42
        terr(kinds=k, obstacles=[{"at": [100, 100], "r": 22, "kind": "rock"}])
        with self.assertRaises(TerrainError):
            terr(kinds=k, obstacles=[{"at": [100, 100], "r": 21, "kind": "rock"}])

    def test_later_regions_override_earlier_ones_regardless_of_kind(self):
        t = terr(regions=[{"kind": "mud", "rect": [1000, 1000, 2000, 2000]}, {"kind": "water", "rect": [1500, 1000, 2000, 2000]},
                          {"kind": "road", "rect": [1700, 1000, 2000, 2000]}], obstacles=[])
        self.assertEqual([t.kind_at(x, 1500) for x in (1100, 1600, 1800)], ["mud", "water", "road"])

    def test_corners_are_detected_through_the_diagonal_sample_points(self):
        t = terr(regions=[{"kind": "water", "rect": [1000, 1000, 1500, 1500]}], obstacles=[])
        self.assertTrue(t.blocked(972, 972))                                            # nur die Ecke berührt den Kreis
        self.assertFalse(t.blocked(971, 971))
        self.assertTrue(t.blocked(1528, 1528))
        self.assertTrue(t.blocked(972, 1528))
        self.assertTrue(t.blocked(1528, 972))

    def test_sliding_along_x_when_y_is_blocked(self):
        self.assertEqual(T.step((2900, 2250), 1, 1), (2924, 2250))                      # See im Süden: nach Osten gleiten (Diagonalschritt 24)
        self.assertEqual(T.step((2900, 2250), 0, 1), (2900, 2250))

    def test_nearest_walkable_prefers_the_closest_point_and_breaks_ties_by_coordinates(self):
        self.assertEqual(T.nearest_walkable((1800, 1000)), (1650, 1000))                # links und rechts gleich weit: kleineres x
        self.assertEqual(T.nearest_walkable((2500, 1000)), (2500, 1000))


class QueryTests(unittest.TestCase):
    def test_later_regions_cover_earlier_ones(self):
        self.assertEqual(T.kind_at(1800, 1000), "water")                                # Fluss
        self.assertEqual(T.kind_at(1800, 1800), "road")                                 # Brücke über dem Fluss
        self.assertEqual(T.kind_at(1800, 1900), "road")                                 # Rand inklusive
        self.assertEqual(T.kind_at(1800, 1901), "water")

    def test_speed_factors(self):
        self.assertEqual([T.speed_permille(*p) for p in ((500, 500), (3000, 1000), (3900, 3700), (1800, 1000))], [1300, 1000, 600, 0])

    def test_blocked_by_water_rocks_borders_and_the_figure_radius(self):
        self.assertTrue(T.blocked(1800, 1000))
        self.assertTrue(T.blocked(1660, 1000))                                          # 40 vor dem Wasser: Figur berührt es
        self.assertFalse(T.blocked(1659, 1000))
        self.assertTrue(T.blocked(1940, 1000))
        self.assertFalse(T.blocked(1941, 1000))
        self.assertTrue(T.blocked(900, 900))                                            # Fels
        self.assertTrue(T.blocked(900 + 129, 900))                                      # r 90 + 40 = 130
        self.assertFalse(T.blocked(900 + 130, 900))
        self.assertTrue(T.blocked(39, 500))
        self.assertFalse(T.blocked(40, 500))
        self.assertTrue(T.blocked(R["zone"]["width"] - 39, 500))
        self.assertFalse(T.blocked(R["zone"]["width"] - 40, 500))
        self.assertTrue(T.blocked(500, R["zone"]["height"] - 39))

    def test_the_bridge_is_walkable_but_its_neighbours_are_not(self):
        self.assertFalse(T.blocked(1800, 1800))
        self.assertFalse(T.blocked(1800, 1760))
        self.assertTrue(T.blocked(1800, 1600))
        self.assertFalse(T.blocked(1800, 1860))                                         # Mittelpunkt auf der Brücke, Kreisrand noch auf der Brücke
        self.assertTrue(T.blocked(1800, 1900 + 50))                                     # Mittelpunkt im Wasser

    def test_clear_line(self):
        self.assertTrue(T.clear_line((500, 500), (1400, 500)))
        self.assertFalse(T.clear_line((1500, 1000), (2000, 1000)))                      # durch den Fluss
        self.assertTrue(T.clear_line((1500, 1800), (2100, 1800)))                       # über die Brücke
        self.assertFalse(T.clear_line((700, 700), (1100, 1100)))                        # durch den Fels bei (900, 900)
        self.assertTrue(T.clear_line((10, 10), (10, 10)))
        self.assertTrue(T.clear_line((500, 500), (520, 500)))                           # kürzer als ein Prüfschritt


class MovementTests(unittest.TestCase):
    def test_step_uses_the_speed_of_the_ground_under_the_figure(self):
        self.assertEqual(T.step((500, 500), 1, 0), (545, 500))                          # Straße 1300
        self.assertEqual(T.step((3000, 1000), 1, 0), (3035, 1000))                      # Gras
        self.assertEqual(T.step((3900, 3700), 1, 0), (3921, 3700))                      # Matsch 600 -> 21
        self.assertEqual(T.step((3000, 1000), 1, 1), (3000 + 24, 1000 + 24))            # Diagonale 35 * 0,707 = 24
        self.assertEqual(T.step((500, 500), 0, 0), (500, 500))

    def test_water_and_rocks_block_with_sliding_along_one_axis(self):
        self.assertEqual(T.step((1650, 1000), 1, 0), (1650, 1000))                      # direkt gegen das Wasser: stehen bleiben
        x, y = T.step((1650, 1000), 1, 1)                                               # schräg: entlang des Ufers gleiten
        self.assertEqual((x, y > 1000), (1650, True))
        self.assertEqual(T.step((1650, 1000), 1, -1)[1] < 1000, True)
        self.assertEqual(T.step((900, 760), 0, 1), (900, 760))                          # Fels unter der Figur (900, 900): 760 + 130 = 890 < 900 -> berührt nicht
        px, py = 900, 770
        self.assertEqual(T.step((px, py), 0, 1), (px, py))                              # Berührungsabstand 130: nicht weiter
        self.assertEqual(T.step((px, py), 1, 1)[1], py)                                 # gleitet seitlich

    def test_no_tunnelling_through_thin_barriers(self):
        pos = (1500, 1000)
        for _ in range(200):
            pos = T.step(pos, 1, 0)
            self.assertFalse(T.blocked(*pos))
        self.assertLess(pos[0], 1700)                                                   # nie im Fluss oder dahinter
        pos = (1500, 1000)
        for _ in range(400):                                                            # schräg am Ufer entlang bis zur Brücke gleiten
            pos = T.step(pos, 1, 1)
            self.assertFalse(T.blocked(*pos))
            if 1660 < pos[0] < 1940:                                                    # im Bereich des Flusses nur auf Höhe der Brücke
                self.assertTrue(1700 <= pos[1] <= 1900, pos)

    def test_walking_the_whole_map_never_enters_blocked_places(self):
        import random
        rng = random.Random(7)
        pos = (500, 500)
        for i in range(6000):
            if i % 40 == 0:
                d = (rng.choice([-1, 0, 1]), rng.choice([-1, 0, 1]))
            pos = T.step(pos, *d)
            self.assertFalse(T.blocked(*pos), (i, pos))
            self.assertTrue(0 <= pos[0] <= R["zone"]["width"] and 0 <= pos[1] <= R["zone"]["height"])

    def test_the_bridge_can_be_crossed(self):
        pos = (1500, 1800)
        for _ in range(60):
            pos = T.step(pos, 1, 0)
        self.assertGreater(pos[0], 2100)

    def test_nearest_walkable(self):
        self.assertEqual(T.nearest_walkable((500, 500)), (500, 500))
        p = T.nearest_walkable((1800, 1000))                                            # mitten im Fluss
        self.assertFalse(T.blocked(*p))
        self.assertEqual(p, T.nearest_walkable((1800, 1000)))                           # deterministisch
        self.assertTrue(abs(p[0] - 1800) <= 200)
        with self.assertRaises(TerrainError):
            terr(regions=[{"kind": "water", "rect": [0, 0, 6000, 6000]}], default="grass").nearest_walkable((3000, 3000), limit=200)

    def test_export_is_a_complete_static_map(self):
        e = T.export()
        self.assertEqual((e["w"], e["h"], e["default"], e["player_radius"]), (6000, 6000, "grass", 40))
        self.assertEqual(len(e["regions"]), len(R["terrain"]["regions"]))
        self.assertEqual(e["obstacles"][0], {"at": [900, 900], "r": 90})
        json.dumps(e)


class GameTests(unittest.TestCase):
    def test_rules_must_place_everything_on_walkable_ground(self):
        for key, bad in (("enemies", [{"type": "wolf", "at": [1800, 1000]}]),
                         ("nodes", [{"id": "x", "item": "iron_ore@standard", "at": [900, 900], "qty": 1}]),
                         ("zone", {**R["zone"], "spawn": [1800, 1000]})):
            r = copy.deepcopy(R)
            r[key] = bad
            with self.assertRaises(TerrainError):
                GameServer(r)

    def test_map_command_and_ground_in_the_state(self):
        g = GameServer()
        a = Bot(g, "anna")
        j = a.call("game.join")["result"]
        self.assertEqual(j["you"]["ground"], "road")
        m = a.call("game.map")
        self.assertTrue(m["ok"])
        self.assertEqual(m["result"], g.terrain.export())

    def test_players_cannot_walk_into_the_river(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (1500, 1000)
        a.call("game.move", dx=1, dy=0)
        for _ in range(100):
            g.tick()
        self.assertLess(g.players["anna"]["pos"][0], 1700)

    def test_no_aggro_across_the_river_but_aggro_on_the_bridge(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (1650, 1500)                                         # Westufer: Wolf (2200, 1800) ist ~630 entfernt, Fluss dazwischen
        for _ in range(5):
            g.tick()
        self.assertNotIn("anna", g.fight_of)
        g.players["anna"]["pos"] = (1800, 1800)                                         # auf der Brücke: freie Strecke
        g.tick()
        self.assertIn("anna", g.fight_of)

    def test_slower_ground_slows_the_player_and_roads_speed_up(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (3900, 3700)                                         # Matsch (Gegner weit genug entfernt: nach Kampf egal)
        g.enemies[:] = [e for e in g.enemies if e["pos"][0] < 3000]
        a.call("game.move", dx=0, dy=-1)
        g.tick()
        self.assertEqual(g.players["anna"]["pos"], (3900, 3700 - 21))
        g.players["anna"]["pos"] = (3000, 1000)
        a.call("game.move", dx=0, dy=1)
        g.tick()
        self.assertEqual(g.players["anna"]["pos"], (3000, 1035))

    def test_fleeing_never_lands_in_blocked_ground(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (2300, 1800)
        g.tick()
        self.assertIn("anna", g.fight_of)
        a.call("game.fight", input="flee")
        g.tick()
        self.assertNotIn("anna", g.fight_of)
        self.assertFalse(g.terrain.blocked(*g.players["anna"]["pos"]))

    def test_flee_point_inside_the_river_is_moved_to_walkable_ground(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (2500, 1800)                                         # 700 zurück liegt der Fluss
        g.tick()
        self.assertIn("anna", g.fight_of)
        a.call("game.fight", input="flee")
        g.tick()
        pos = g.players["anna"]["pos"]
        self.assertNotEqual(pos, (1800, 1100))
        self.assertFalse(g.terrain.blocked(*pos))

    def test_a_saved_position_inside_a_blocked_area_is_moved_out(self):
        g = GameServer()
        g.saved_pos["anna"] = (1800, 1000)                                              # z. B. Karte wurde geändert
        a = Bot(g, "anna")
        pos = tuple(a.call("game.join")["result"]["you"]["pos"])
        self.assertFalse(g.terrain.blocked(*pos))
        self.assertTrue(abs(pos[0] - 1800) <= 300)

    def test_nobody_ever_stands_in_blocked_ground_while_walking_randomly(self):
        import random
        g = GameServer()
        bots = [Bot(g, f"p{i}") for i in range(3)]
        for b in bots:
            b.call("game.join")
        rng = random.Random(3)
        for i in range(1500):
            if i % 25 == 0:
                for b in bots:
                    if b.name not in g.fight_of:
                        b.call("game.move", dx=rng.choice([-1, 0, 1]), dy=rng.choice([-1, 0, 1]))
            g.tick()
            for b in bots:
                if b.name in g.fight_of:
                    b.call("game.fight", input="flee")
                self.assertFalse(g.terrain.blocked(*g.players[b.name]["pos"]), (i, b.name))


if __name__ == "__main__":
    unittest.main()
