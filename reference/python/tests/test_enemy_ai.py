import copy
import unittest

from mmo_game import GameServer, load_game_rules
from mmo_game.navigation import Navigator
from mmo_game.terrain import Terrain

R0 = load_game_rules()
TERR = Terrain(R0["terrain"], R0["zone"], R0["speed_cm_per_tick"])
NAV = Navigator(TERR, 100)


def rules(**changes):
    r = copy.deepcopy(R0)
    r.update(changes)
    return r


class Bot:
    def __init__(self, g, name):
        self.g, self.name = g, name
        self.sid, _ = g.connect(name)
        self.n = 0

    def call(self, cmd, **args):
        self.n += 1
        return self.g.handle(self.sid, {"v": 1, "id": f"{self.name}-{self.n}", "cmd": cmd, "args": {"char": self.name, **args}})


def solo(enemies, pos, **changes):
    g = GameServer(rules(enemies=enemies, **changes))
    a = Bot(g, "anna")
    a.call("game.join")
    g.players["anna"]["pos"] = pos
    return g, a


def dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


class NavigatorTests(unittest.TestCase):
    def test_grid_and_costs(self):
        self.assertEqual((NAV.cols, NAV.rows), (60, 60))
        self.assertEqual(NAV.min_cost, 7)                                        # Straße
        self.assertIsNone(NAV.cost[10 * 60 + 18])                                # (1850, 1050) liegt im Fluss
        self.assertEqual(NAV.cost[3 * 60 + 30], 10)                              # Gras
        self.assertEqual(NAV.cost[37 * 60 + 40], 16)                             # Matsch
        self.assertEqual(NAV.cost[5 * 60 + 5], 7)                                # Straße
        self.assertEqual(NAV.center((0, 0)), (50, 50))

    def test_cell_of_and_passable(self):
        self.assertEqual(NAV.cell_of((0, 0)), (0, 0))
        self.assertEqual(NAV.cell_of((5999, 5999)), (59, 59))
        self.assertEqual(NAV.cell_of((99999, -5)), (59, 0))                      # begrenzt
        self.assertFalse(NAV.passable((-1, 0)))
        self.assertFalse(NAV.passable((0, 60)))
        self.assertTrue(NAV.passable((5, 5)))
        self.assertFalse(NAV.passable((18, 10)))

    def test_nearest_passable(self):
        self.assertEqual(NAV.nearest_passable((5, 5)), (5, 5))
        c = NAV.nearest_passable((18, 10))                                       # Fluss
        self.assertTrue(NAV.passable(c))
        self.assertEqual(c, NAV.nearest_passable((18, 10)))
        self.assertIsNone(NAV.nearest_passable((18, 10), limit=0))

    def test_paths_cross_the_river_only_on_the_bridge(self):
        path = NAV.find_path((1000, 500), (2200, 1800))
        self.assertEqual(path[-1], (2200, 1800))
        self.assertGreater(len(path), 10)
        for p in path:
            self.assertFalse(TERR.blocked(*p), p)
        crossing = [p for p in path if 1700 <= p[0] <= 1900]
        self.assertTrue(crossing and all(1700 <= p[1] <= 1900 for p in crossing), crossing)

    def test_deterministic_and_symmetric_queries(self):
        a = NAV.find_path((300, 300), (3900, 3700))
        self.assertEqual(a, NAV.find_path((300, 300), (3900, 3700)))
        self.assertTrue(a)

    def test_same_cell_and_unreachable(self):
        self.assertEqual(NAV.find_path((520, 530), (560, 580)), [(560, 580)])
        t = Terrain({**R0["terrain"], "regions": [{"kind": "water", "rect": [0, 3000, 6000, 3200]}], "obstacles": []}, R0["zone"], 35)
        n = Navigator(t, 100)
        self.assertIsNone(n.find_path((500, 500), (500, 5000)))                  # Wasserband trennt die Zone
        self.assertIsNotNone(n.find_path((500, 500), (500, 2000)))

    def test_goal_in_blocked_ground_leads_to_the_nearest_free_cell(self):
        path = NAV.find_path((1000, 500), (1800, 1000))
        self.assertEqual(path[-1], (1800, 1000))
        self.assertFalse(TERR.blocked(*path[-2]))

    def test_path_prefers_roads_over_mud(self):
        t = Terrain({**R0["terrain"], "regions": [{"kind": "mud", "rect": [1000, 1000, 3000, 1200]}, {"kind": "road", "rect": [1000, 1400, 3000, 1600]}],
                     "obstacles": []}, R0["zone"], 35)
        n = Navigator(t, 100)
        path = n.find_path((500, 1300), (3500, 1300))
        ys = [p[1] for p in path if 1500 < p[0] < 2500]
        self.assertTrue(all(y > 1300 for y in ys), ys)                           # eher über die Straße (y 1400..1600) als durch den Matsch

    def test_no_corner_cutting(self):
        t = Terrain({**R0["terrain"], "regions": [{"kind": "water", "rect": [1000, 1000, 1200, 2000]}, {"kind": "water", "rect": [1200, 2000, 1400, 2200]}],
                     "obstacles": []}, R0["zone"], 35)
        n = Navigator(t, 100)
        p = n.find_path((900, 1950), (1500, 2150))
        self.assertIsNotNone(p)
        for q in p:
            self.assertFalse(t.blocked(*q))

    def test_node_limit(self):
        n = Navigator(TERR, 100, max_nodes=5)
        self.assertIsNone(n.find_path((300, 300), (3900, 3700)))


class ChaseTests(unittest.TestCase):
    def test_enemies_stay_idle_until_a_player_comes_into_range(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (2000, 1800 + 800))
        for _ in range(30):
            g.tick()
        self.assertEqual((g.enemies[0]["state"], g.enemies[0]["pos"]), ("idle", (2000, 1800)))

    def test_a_wolf_runs_at_its_speed_and_fights_at_the_engage_radius(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}], (3000, 1600))               # 600 entfernt, Gras
        g.players["anna"]["dir"] = (0, 0)
        e = g.enemies[0]
        g.tick()
        self.assertEqual((e["state"], e["pos"]), ("chase", (3000, 1000 + 40)))          # Tempo 40 je Tick
        for _ in range(200):
            g.tick()
            if e["state"] == "fight":
                break
        self.assertEqual(e["state"], "fight")
        self.assertLessEqual(dist2(e["pos"], g.players["anna"]["pos"]), 150 ** 2)
        self.assertGreater(dist2(e["pos"], g.players["anna"]["pos"]), (150 - 2 * 40) ** 2)       # nicht früher als nötig
        self.assertEqual(g.fight_of["anna"], e["fight"])

    def test_bears_are_slower_than_wolves(self):
        g, a = solo([{"type": "bear", "at": [3000, 1000]}], (3000, 1600))
        g.tick()
        self.assertEqual(g.enemies[0]["pos"], (3000, 1000 + 28))

    def test_unknown_types_use_the_default_speed(self):
        r = rules(enemies=[{"type": "stone_golem", "at": [3000, 1000]}])
        g = GameServer(r)
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (3000, 1600)
        g.tick()
        self.assertEqual(g.enemies[0]["pos"], (3000, 1000 + 30))

    def test_terrain_slows_enemies_too(self):
        g, a = solo([{"type": "wolf", "at": [3900, 3700]}], (3900, 4250))                # Matsch 60 %
        g.tick()
        self.assertEqual(g.enemies[0]["pos"], (3900, 3700 + 24))

    def test_the_enemy_takes_the_bridge_to_reach_a_player_across_the_river(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (1650, 1500))               # Westufer
        g.players["anna"]["pos"] = (1650, 1500)
        # Anna steht nicht in der freien Sicht (Fluss) -> keine Verfolgung
        for _ in range(10):
            g.tick()
        self.assertEqual(g.enemies[0]["state"], "idle")
        g.players["anna"]["pos"] = (1650, 1750)                                        # frei über die Brücke
        seen = []
        for _ in range(200):
            g.tick()
            seen.append(g.enemies[0]["pos"])
            if g.enemies[0]["state"] == "fight":
                break
        self.assertEqual(g.enemies[0]["state"], "fight")
        for p in seen:
            self.assertFalse(g.terrain.blocked(*p), p)

    def test_chasers_never_stand_in_blocked_ground(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}, {"type": "wolf", "at": [2000, 2000]}], (1500, 1800))
        import random
        rng = random.Random(5)
        for i in range(600):
            if i % 15 == 0 and "anna" not in g.fight_of:
                a.call("game.move", dx=rng.choice([-1, 0, 1]), dy=rng.choice([-1, 0, 1]))
            if "anna" in g.fight_of:
                a.call("game.fight", input="flee")
            g.tick()
            for e in g.enemies:
                self.assertFalse(g.terrain.blocked(*e["pos"]), (i, e["id"], e["pos"]))

    def test_the_pack_follows_together_and_fights_together(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}, {"type": "wolf", "at": [2100, 1800]}, {"type": "bear", "at": [2000, 1500]}], (2000, 2300))
        g.tick()
        self.assertEqual([e["state"] for e in g.enemies], ["chase", "chase", "chase"])
        for _ in range(100):
            g.tick()
            if g.fights:
                break
        f = next(iter(g.fights.values()))
        self.assertEqual(sorted(f["types"]), ["bear", "wolf", "wolf"])

    def test_a_pack_member_outside_the_pack_radius_does_not_join(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}, {"type": "wolf", "at": [2000, 1800 - 650]}], (2000, 2300))
        for _ in range(100):
            g.tick()
            if g.fights:
                break
        f = next(iter(g.fights.values()))
        self.assertEqual(f["types"], ["wolf"])


class LeashTests(unittest.TestCase):
    def test_enemies_give_up_beyond_the_leash_radius_and_walk_home(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (2000, 2400))
        e = g.enemies[0]
        for _ in range(5):
            g.tick()
        self.assertEqual(e["state"], "chase")
        a.call("game.move", dx=0, dy=1)                                               # Spieler läuft weg (Tempo 35 < 40, Wolf holt auf)...
        g.players["anna"]["pos"] = (2000, 1800 + 2201 + 400)                          # ...und wird weit weg versetzt
        g.players["anna"]["immune_until"] = 0
        g.tick()
        self.assertEqual(e["state"], "chase") if dist2(e["pos"], e["home"]) <= 2200 ** 2 else None
        e["pos"] = (2000, 1800 + 2201)                                                # Gegner weiter als der Haltebereich von zu Hause
        g.tick()
        self.assertEqual(e["state"], "return")
        for _ in range(400):
            g.tick()
            if e["state"] == "idle":
                break
        self.assertEqual((e["state"], e["pos"]), ("idle", (2000, 1800)))

    def test_leash_boundary(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1000]}], (2000, 1600))
        e = g.enemies[0]
        g._begin_chase(e, "anna")
        e["pos"] = (2000, 1000 + 2200)                                                # genau auf dem Haltebereich: weiter verfolgen
        g.players["anna"]["pos"] = (2000, 5500)
        g._enemies_act()
        self.assertEqual(e["state"], "chase")
        e["pos"] = (2000, 1000 + 2201)
        g._enemies_act()
        self.assertEqual(e["state"], "return")

    def test_returning_enemies_ignore_players_until_home(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (2000, 2400))
        e = g.enemies[0]
        g._begin_return(e)
        e["pos"] = (2000, 2000)
        g.tick()
        self.assertEqual(e["state"], "return")                                        # Spieler direkt daneben, aber kein neues Verfolgen
        for _ in range(100):
            g.tick()
            if e["state"] != "return":
                break
        self.assertIn(e["state"], ("idle", "chase"))

    def test_home_radius_is_inclusive_and_snaps_home(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (5000, 5000))
        e = g.enemies[0]
        g._begin_return(e)
        e["pos"] = (2000, 1800 + 60)
        g._enemies_act()
        self.assertEqual((e["state"], e["pos"]), ("idle", (2000, 1800)))
        g._begin_return(e)
        e["pos"] = (2000, 1800 + 61)
        g._enemies_act()
        self.assertEqual(e["state"], "return")

    def test_a_fled_fight_sends_the_enemies_home(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (2000, 2100))
        for _ in range(60):
            g.tick()
            if "anna" in g.fight_of:
                break
        self.assertIn("anna", g.fight_of)
        a.call("game.fight", input="flee")
        g.tick()
        e = g.enemies[0]
        self.assertEqual(e["state"], "return")
        self.assertIsNone(e["fight"])
        for _ in range(400):
            g.tick()
            if e["state"] == "idle":
                break
        self.assertEqual((e["state"], e["pos"]), ("idle", e["home"]))

    def test_a_defeat_sends_the_enemies_home(self):
        g, a = solo([{"type": "bear", "at": [2000, 1800]}, {"type": "bear", "at": [2050, 1800]}, {"type": "bear", "at": [2100, 1800]}], (2000, 2000))
        for _ in range(4000):
            g.tick()
            if a.call("game.state")["result"]["you"]["fight"] is None and g.tick_no > 30:
                break
        self.assertTrue(all(e["state"] in ("return", "idle") for e in g.enemies))
        self.assertEqual(g.players["anna"]["pos"], tuple(R0["zone"]["spawn"]))

    def test_victory_removes_them_until_respawn_at_home(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (2000, 2100))
        e = g.enemies[0]
        for i in range(3000):
            if "anna" in g.fight_of and i % 8 == 0:
                a.call("game.fight", input="light")
            g.tick()
            if not e["alive"]:
                break
        self.assertFalse(e["alive"])
        g.players["anna"]["pos"] = (5000, 5000)                                       # weit weg, damit das Tier nicht sofort wieder loslegt
        for _ in range(g.R["respawn_ticks"] + 1):
            g.tick()
        self.assertEqual((e["alive"], e["state"], e["pos"]), (True, "idle", e["home"]))


class TargetLossTests(unittest.TestCase):
    def test_disconnecting_target_ends_the_chase(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}], (3000, 1600))
        for _ in range(5):
            g.tick()
        self.assertEqual(g.enemies[0]["state"], "chase")
        g.disconnect(a.sid)
        g.tick()
        self.assertEqual(g.enemies[0]["state"], "return")

    def test_a_target_that_started_another_fight_is_dropped(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}, {"type": "wolf", "at": [2000, 2800]}], (2000, 2300))
        for _ in range(60):
            g.tick()
        self.assertEqual(len(g.fights), 1)
        states = {e["state"] for e in g.enemies}
        self.assertTrue(states <= {"fight", "return", "idle"})

    def test_immune_players_are_not_chased(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}], (3000, 1900))               # 900 entfernt: erst im Alarmradius, wenn der Spieler näher kommt
        g.players["anna"]["pos"] = (3000, 1600)
        g.players["anna"]["immune_until"] = 50
        for _ in range(10):
            g.tick()
        self.assertEqual(g.enemies[0]["state"], "idle")
        g.players["anna"]["immune_until"] = 0
        g.tick()
        self.assertEqual(g.enemies[0]["state"], "chase")
        for _ in range(5):
            g.tick()
        self.assertEqual(g.enemies[0]["state"], "chase")
        g.players["anna"]["immune_until"] = g.tick_no + 20                              # während der Verfolgung geschützt: Gegner geben auf
        g.tick()
        self.assertEqual(g.enemies[0]["state"], "return")

    def test_a_runner_cannot_drag_enemies_beyond_the_leash(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}], (3000, 1500))
        a.call("game.move", dx=0, dy=1)
        far = 0
        for _ in range(250):
            g.tick()
            far = max(far, dist2(g.enemies[0]["pos"], g.enemies[0]["home"]))
            if "anna" in g.fight_of:
                break
        self.assertLessEqual(far, (g.R["enemy_ai"]["leash_radius"] + 40) ** 2)


class PackAndEngageTests(unittest.TestCase):
    def test_pack_mates_far_from_the_alerting_enemy_are_not_pulled_along(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}, {"type": "wolf", "at": [3000, 100]}], (3000, 1600))
        g._alert()
        self.assertEqual([e["state"] for e in g.enemies], ["chase", "idle"])           # zweites Tier 900 vom ersten, 1500 vom Spieler: weder Alarm- noch Rudelradius

    def test_immune_players_are_not_noticed(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}], (3000, 1300))
        g.players["anna"]["immune_until"] = 5
        g._alert()
        self.assertEqual(g.enemies[0]["state"], "idle")
        g.players["anna"]["immune_until"] = 0
        g._alert()
        self.assertEqual(g.enemies[0]["state"], "chase")

    def test_engage_radius_is_inclusive(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}], (3000, 1300))
        e = g.enemies[0]
        g._begin_chase(e, "anna")
        e["pos"] = (3000, 1300 - 151)
        g._enemies_act()
        self.assertEqual((e["state"], g.fights), ("chase", {}))
        e["pos"] = (3000, 1300 - 150)
        e["path"] = []
        g._enemies_act()
        self.assertEqual(e["state"], "fight")

    def test_no_fight_through_a_thin_barrier_even_when_very_close(self):
        r = rules(enemies=[{"type": "wolf", "at": [3000, 999]}])
        r["terrain"] = {**r["terrain"], "regions": [{"kind": "water", "rect": [2900, 1040, 3100, 1090]}], "obstacles": []}
        g = GameServer(r)
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (3000, 1131)                                        # 132 entfernt, Wasser dazwischen
        e = g.enemies[0]
        g._begin_chase(e, "anna")
        g._enemies_act()
        self.assertEqual(g.fights, {})

    def test_enemies_returning_home_are_not_pulled_into_a_fight(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}, {"type": "wolf", "at": [3000, 1100]}], (3000, 1300))
        e1, e2 = g.enemies
        g._begin_chase(e1, "anna")
        g._begin_return(e2)
        e2["pos"] = (3000, 1250)
        e1["pos"] = (3000, 1200)
        g._enemies_act()
        self.assertEqual(g.fights[g.fight_of["anna"]]["types"], ["wolf"])
        self.assertEqual(e2["state"], "return")

    def test_at_most_max_opponents_are_pulled_into_a_fight(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000 + 20 * i]} for i in range(5)], (3000, 1300))
        for _ in range(40):
            g.tick()
            if g.fights:
                break
        f = next(iter(g.fights.values()))
        self.assertEqual(len(f["types"]), 3)
        self.assertEqual(sum(1 for e in g.enemies if e["fight"] is not None), 3)


class UnreachableTests(unittest.TestCase):
    def test_no_path_to_the_player_means_going_home(self):
        r = rules(enemies=[{"type": "wolf", "at": [2000, 1000]}])
        r["terrain"] = {**r["terrain"], "regions": [{"kind": "water", "rect": [0, 1400, 6000, 1600]}], "obstacles": []}
        g = GameServer(r)
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (2000, 1300)
        g.tick()
        self.assertEqual(g.enemies[0]["state"], "chase")
        g.players["anna"]["pos"] = (2000, 1700)                                        # hinter dem Wasserband: nicht sichtbar, aber Ziel bleibt
        for _ in range(30):
            g.tick()
            if g.enemies[0]["state"] == "return":
                break
        self.assertEqual(g.enemies[0]["state"], "return")

    def test_stuck_enemies_repath_and_do_not_spin_forever(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (2000, 2400))
        e = g.enemies[0]
        g.tick()
        e["path"] = [e["pos"]]                                                         # falscher Weg: Wegpunkt auf der Stelle
        e["repath_at"] = 10 ** 9
        e["stuck"] = g.R["enemy_ai"]["stuck_limit"]
        before = e["pos"]
        g.tick()
        self.assertNotEqual(e["pos"], before)                                          # neu berechnet, läuft weiter
        self.assertEqual(e["stuck"], 0)

    def test_blocked_waypoints_raise_the_stuck_counter_until_the_path_is_recomputed(self):
        g, a = solo([{"type": "wolf", "at": [3000, 1000]}], (3000, 1600))
        e = g.enemies[0]
        g.tick()
        rock = (900, 900)                                                              # Wegpunkt im Fels: nie erreichbar
        e["path"] = [rock, rock]
        e["repath_at"] = 10 ** 9
        e["stuck"] = 0
        e["pos"] = (1000, 1000)
        counts = []
        for _ in range(g.R["enemy_ai"]["stuck_limit"] + 1):
            g.tick()
            counts.append(e["stuck"])
        self.assertEqual(counts[:3], [1, 2, 3])
        self.assertEqual(counts[-1], 0)                                                # nach stuck_limit Versuchen neu berechnet
        self.assertNotEqual(e["path"], [rock, rock])


class StateTests(unittest.TestCase):
    def test_state_events_carry_enemy_states(self):
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (2000, 2400))
        g.tick()
        g.tick()
        st = a.call("game.state")["result"]
        self.assertEqual(st["enemies"][0]["state"], "chase")

    def test_repeatable_with_identical_inputs(self):
        def run():
            g, a = solo([{"type": "wolf", "at": [2000, 1800]}, {"type": "wolf", "at": [2100, 1900]}], (1650, 1750))
            trace = []
            for i in range(200):
                if i % 20 == 0:
                    a.call("game.move", dx=(i // 20) % 3 - 1, dy=1)
                if "anna" in g.fight_of:
                    a.call("game.fight", input="flee")
                g.tick()
                trace.append((g.players["anna"]["pos"], tuple(e["pos"] for e in g.enemies), tuple(e["state"] for e in g.enemies)))
            return trace
        self.assertEqual(run(), run())

    def test_enemy_state_is_not_saved_but_positions_reset_to_home(self):
        import tempfile
        from mmo_world.persistence import Store
        g, a = solo([{"type": "wolf", "at": [2000, 1800]}], (2000, 2400))
        for _ in range(3):
            g.tick()
        self.assertEqual(g.enemies[0]["state"], "chase")
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            g.save(store)
            h = GameServer.load(store, g.R)
            self.assertEqual((h.enemies[0]["state"], h.enemies[0]["pos"]), ("idle", (2000, 1800)))


if __name__ == "__main__":
    unittest.main()
