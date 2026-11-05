import asyncio
import copy
import json
import unittest

from mmo_game import GameServer, load_game_rules
from mmo_game.client import Client
from mmo_game.net import NetServer

WOLVES = (2200, 1800)


class Bot:
    """Synchroner Testspieler am GameServer (kein Netzwerk)."""

    def __init__(self, g, name):
        self.g, self.name = g, name
        self.sid, _ = g.connect(name)
        self.n = 0
        self.events = []

    def call(self, cmd, **args):
        self.n += 1
        return self.g.handle(self.sid, {"v": 1, "id": f"{self.name}-{self.n}", "cmd": cmd, "args": {"char": self.name, **args}})

    def pull(self):
        self.events += self.g.drain(self.sid)

    def pos(self):
        return self.g.players[self.name]["pos"]


PATH_TO_WOLVES = [(1500, 500), (1500, 1800), (2300, 1800)]       # Straße, dann über die Brücke


def walk(g, bots, targets, reach=300, max_ticks=3000):
    """Alle Bots gehen zu ihren Zielen (ein Punkt oder eine Liste von Wegpunkten); stoppt, sobald jemand im Kampf ist oder alle da sind."""
    paths = [list(t) if isinstance(t, list) else [t] for t in targets]
    idx = [0] * len(bots)
    for _ in range(max_ticks):
        done = True
        for k, (b, path) in enumerate(zip(bots, paths)):
            if b.name in g.fight_of:
                continue
            t = path[idx[k]]
            last = idx[k] == len(path) - 1
            x, y = b.pos()
            if (x - t[0]) ** 2 + (y - t[1]) ** 2 <= (reach if last else 60) ** 2:
                if last:
                    b.call("game.move", dx=0, dy=0)
                    continue
                idx[k] += 1
            done = False
            t = path[idx[k]]
            dx = (t[0] > x) - (t[0] < x) if abs(t[0] - x) > 40 else 0
            dy = (t[1] > y) - (t[1] < y) if abs(t[1] - y) > 40 else 0
            b.call("game.move", dx=dx, dy=dy)
        g.tick()
        for b in bots:
            b.pull()
        if done or any(b.name in g.fight_of for b in bots):
            return


def fight_until_end(g, bots, spam=("light",), every=8, max_ticks=3000):
    for i in range(max_ticks):
        for b in bots:
            if b.name in g.fight_of and i % every == 0:
                for cmd in spam:
                    b.call("game.fight", input=cmd)
        g.tick()
        for b in bots:
            b.pull()
        if all(b.name not in g.fight_of for b in bots):
            return


def kinds(bot, ev):
    return [e for e in bot.events if e["ev"] == ev]


class RulesTests(unittest.TestCase):
    def test_game_rules_load_and_match_the_oracle_files(self):
        R = load_game_rules()
        g = GameServer()
        self.assertEqual(g.world.svc.rules.version, "9")
        self.assertEqual(g.sim["version"], "12")
        self.assertTrue(R["speed_cm_per_tick"] > 0 and R["aggro_radius"] > 0)
        # Beute nur aus bekannten Gegnern und handelbaren Gegenständen
        for t, items in R["drops"].items():
            self.assertIn(t, g.sim["opponents"])
            for key in items:
                if key != "coin@gold":
                    g.world.trading.parse(key)
        for n in R["nodes"]:
            g.world.trading.parse(n["item"])
        for e in R["enemies"]:
            self.assertIn(e["type"], g.sim["opponents"])


class SessionTests(unittest.TestCase):
    def test_connect_creates_a_human_character_with_starting_coins(self):
        g = GameServer()
        b = Bot(g, "anna")
        self.assertEqual(g.world.svc.state("anna").parts["identity"]["kind"], "player")
        self.assertEqual(b.call("query.inventory")["result"], {"coin@gold": 200})
        with self.assertRaises(ValueError):
            g.connect("anna")                                  # schon verbunden
        for bad in ("", "a b", None, 5, "x" * 65):
            with self.assertRaises(ValueError):
                g.connect(bad)
        g.disconnect(b.sid)
        Bot(g, "anna")                                         # nach dem Trennen wieder möglich; die Figur bleibt bestehen
        self.assertEqual(g.world.inv.balance("anna", "coin@gold"), 200)

    def test_commands_need_join_and_own_character(self):
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        self.assertEqual(a.call("game.move", dx=1, dy=0)["error"]["code"], "rejected")
        a.call("game.join")
        b.call("game.join")
        r = g.handle(a.sid, {"v": 1, "id": "x1", "cmd": "game.move", "args": {"char": "ben", "dx": 1, "dy": 0}})
        self.assertEqual(r["error"]["code"], "forbidden")
        self.assertEqual(g.handle("sess-99999999", {"cmd": "game.join"})["error"]["code"], "unknown_session")
        for raw in ("not json", "[]", '{"cmd": 5}', json.dumps({"cmd": "game.join", "args": []})):
            self.assertFalse(g.handle(a.sid, raw)["ok"])
        self.assertEqual(g.handle(a.sid, "x" * 5000)["error"]["code"], "bad_request")
        self.assertEqual(a.call("game.nonsense")["error"]["code"], "unknown_command")
        self.assertEqual(a.call("game.__class__")["error"]["code"], "unknown_command")

    def test_world_commands_still_go_through_the_gateway_with_authorization(self):
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        r = g.handle(a.sid, {"v": 1, "id": "q1", "cmd": "query.inventory", "args": {"char": "ben"}})
        self.assertEqual(r["error"]["code"], "forbidden")
        self.assertTrue(a.call("query.inventory")["ok"])


class MovementTests(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()
        self.a = Bot(self.g, "anna")
        self.a.call("game.join")

    def test_speed_is_limited_by_the_server(self):
        start = self.a.pos()
        self.assertEqual(start, (500, 500))                                              # Straße: Faktor 1,3 -> 45 je Tick
        self.assertEqual(self.a.call("game.move", dx=1, dy=0)["result"], {"dir": [1, 0]})
        for _ in range(10):
            self.g.tick()
        self.assertEqual(self.a.pos(), (start[0] + 10 * 45, start[1]))
        for bad in ({"dx": 2, "dy": 0}, {"dx": 1.5, "dy": 0}, {"dx": "1", "dy": 0}, {"dx": True, "dy": 0}, {"dx": 1}, {}):
            self.assertEqual(self.a.call("game.move", **bad)["error"]["code"], "bad_request", bad)
        self.assertEqual(self.a.pos(), (start[0] + 450, start[1]))

    def test_diagonal_is_not_faster_and_zone_borders_hold(self):
        self.a.call("game.move", dx=1, dy=1)
        x0, y0 = self.a.pos()
        self.g.tick()
        x1, y1 = self.a.pos()
        self.assertTrue((x1 - x0) ** 2 + (y1 - y0) ** 2 <= 45 ** 2)
        self.a.call("game.move", dx=-1, dy=-1)
        for _ in range(400):
            self.g.tick()
            self.a.call("game.move", dx=-1, dy=-1)
        x, y = self.a.pos()
        r = self.g.terrain.radius
        self.assertTrue(x >= r and y >= r)                                               # Rand mit Figurenradius
        self.assertEqual((x < r + 45, y < r + 45), (True, True))

    def test_state_events_show_nearby_players_only(self):
        b = Bot(self.g, "ben")
        b.call("game.join")
        self.g.tick()
        self.g.tick()
        self.a.pull()
        st = [e for e in self.a.events if e["ev"] == "state"][-1]
        self.assertEqual([p["char"] for p in st["players"]], ["ben"])
        self.g.players["ben"]["pos"] = (5900, 5900)
        self.g.tick()
        self.g.tick()
        self.a.pull()
        self.assertEqual([e for e in self.a.events if e["ev"] == "state"][-1]["players"], [])

    def test_rate_limit_on_game_commands(self):
        codes = {self.a.call("game.move", dx=0, dy=0).get("error", {}).get("code") for _ in range(60)}
        self.assertIn("rate_limited", codes)
        for _ in range(60):
            self.g.tick()
        self.assertTrue(self.a.call("game.move", dx=0, dy=0)["ok"])


class GatheringTests(unittest.TestCase):
    def test_gather_needs_reach_and_respects_cooldown(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        self.assertEqual(a.call("game.gather", node="ore1")["error"]["code"], "rejected")        # zu weit
        self.assertEqual(a.call("game.gather", node="nope")["error"]["code"], "rejected")
        walk(g, [a], [(1100, 700)], reach=200)
        r = a.call("game.gather", node="ore1")
        self.assertEqual(r["result"], {"item": "iron_ore@standard", "qty": 3, "gains": {"profession": "mining", "xp": 10}})
        self.assertEqual(a.call("game.gather", node="ore1")["error"]["code"], "rejected")        # erschöpft
        for _ in range(150):
            g.tick()
        self.assertTrue(a.call("game.gather", node="ore1")["ok"])
        self.assertEqual(g.world.inv.balance("anna", "iron_ore@standard"), 6)

    def test_ore_becomes_ingots_and_can_be_sold(self):
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        a.call("game.join")
        b.call("game.join")
        walk(g, [a], [(1100, 700)], reach=200)
        a.call("game.gather", node="ore1")
        walk(g, [a], [(1300, 1000)], reach=200)
        a.call("game.gather", node="ore2")
        c = a.call("craft", recipe="iron_ingot", qty=3, grade="standard")
        self.assertTrue(c["ok"], c)
        inv = a.call("query.inventory")["result"]
        ingot = next(k for k in inv if k.startswith("iron_ingot@"))
        self.assertEqual(inv[ingot], 3)
        self.assertEqual(inv.get("iron_ore@standard", 0), 0)                   # 6 Erz -> 3 Barren
        o = a.call("trade.offer", to="ben", side="sell", item_key=ingot, qty=3, price=60)
        self.assertTrue(o["ok"], o)
        done = b.call("trade.accept", offer=o["result"])
        self.assertTrue(done["ok"], done)
        self.assertEqual(g.world.inv.balance("ben", ingot), 3)
        self.assertEqual(g.world.inv.balance("anna", "coin@gold"), 200 + 60 - done["result"]["fee"] * 0 - done["result"]["fee"])
        self.assertTrue(any(e["ev"] == "notify" for e in (a.pull() or a.events)))


class CombatTests(unittest.TestCase):
    def test_solo_fight_end_to_end_with_report_loot_and_respawn(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES], reach=300)
        self.assertIn("anna", g.fight_of)
        fight_until_end(g, [a])
        start, end = kinds(a, "fight_start")[0], kinds(a, "fight_end")[0]
        self.assertEqual((start["opponents"], start["party"], start["you"]), (["wolf", "wolf"], ["anna"], 0))
        self.assertEqual(end["outcome"], "victory")
        self.assertEqual(end["report"]["opponent_type"], "wolf")
        drops = g.R["drops"]["wolf"]
        self.assertEqual(end["loot"], {"coin@gold": 2 * drops["coin@gold"], "healing_herb@standard": 2 * drops["healing_herb@standard"]})         # zwei Wölfe, erster Kill des Tages
        self.assertEqual(end["loot_factor"], {"wolf": 1000})
        self.assertEqual(g.world.inv.balance("anna", "coin@gold"), 200 + 2 * drops["coin@gold"])
        self.assertEqual(g.log, [])                                            # Live-Ergebnis == Neuberechnung
        st = g.world.svc.state("anna")
        self.assertGreater(sum(st.parts["combat"]["points"].values()), 0)      # Entwicklung entsteht aus dem Bericht
        self.assertEqual(st.parts["combat"]["stats"]["victory"], 1)
        killed = [e for e in g.enemies if e["type"] == "wolf" and not e["alive"]]
        self.assertEqual(len(killed), 2)
        for _ in range(400):
            g.tick()
        self.assertTrue(all(e["alive"] for e in g.enemies))                     # Wiedererscheinen

    def test_fight_inputs_are_validated_and_assigned_server_ticks(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        self.assertEqual(a.call("game.fight", input="light")["error"]["code"], "rejected")     # nicht im Kampf
        walk(g, [a], [PATH_TO_WOLVES])
        for bad in ("fireball", 5, None, "cast_ember"):                         # unbekannt / Fähigkeit nicht ausgerüstet wird ignoriert
            r = a.call("game.fight", input=bad)
            if bad in ("fireball", 5, None):
                self.assertEqual(r["error"]["code"], "rejected", bad)
        r = a.call("game.fight", input="light")
        self.assertEqual(r["result"]["tick"], g.fights[g.fight_of["anna"]]["live"].t)       # Tick bestimmt der Server

    def test_movement_is_blocked_during_a_fight(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES])
        p = a.pos()
        a.call("game.move", dx=1, dy=0)
        for _ in range(5):
            g.tick()
        self.assertEqual(a.pos(), p)
        self.assertEqual(a.call("game.gather", node="ore1")["error"]["code"], "rejected")

    def test_fleeing_leaves_the_fight_and_gives_a_pause_from_aggro(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES])
        a.call("game.fight", input="flee")
        g.tick()
        a.pull()
        self.assertNotIn("anna", g.fight_of)
        self.assertEqual(kinds(a, "fight_left")[0]["reason"], "fled")
        self.assertTrue(all(e["fight"] is None for e in g.enemies))
        for _ in range(10):
            g.tick()
        self.assertNotIn("anna", g.fight_of)                                    # kurze Schonfrist

    def test_defeat_sends_the_player_home(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (3875, 3700)                                  # Bär + 2 Wölfe
        g.tick()
        self.assertIn("anna", g.fight_of)
        for _ in range(3000):
            g.tick()
            if "anna" not in g.fight_of:
                break
        a.pull()
        self.assertEqual(kinds(a, "fight_left")[0]["reason"], "defeat")
        self.assertEqual(a.pos(), tuple(g.R["zone"]["spawn"]))
        self.assertTrue(all(e["alive"] and e["fight"] is None for e in g.enemies))

    def test_disconnect_in_a_fight_counts_as_fleeing(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES])
        fid = g.fight_of["anna"]
        g.disconnect(a.sid)
        for _ in range(3):
            g.tick()
        self.assertNotIn(fid, g.fights)
        self.assertNotIn("anna", g.players)
        self.assertTrue(all(e["fight"] is None for e in g.enemies))

    def test_two_players_in_a_party_fight_together_and_share_loot(self):
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        a.call("game.join")
        b.call("game.join")
        a.call("party.form")
        iid = a.call("party.invite", target="ben")["result"]
        self.assertTrue(b.call("party.accept", invite=iid)["ok"])
        walk(g, [a, b], [PATH_TO_WOLVES, PATH_TO_WOLVES])
        for _ in range(20):
            g.tick()
        self.assertEqual(g.fight_of.get("anna"), g.fight_of.get("ben"))
        fight_until_end(g, [a, b])
        ea, eb = kinds(a, "fight_end")[0], kinds(b, "fight_end")[0]
        self.assertEqual((ea["outcome"], eb["outcome"]), ("victory", "victory"))
        drops = g.R["drops"]["wolf"]
        self.assertEqual(sum(l.get("coin@gold", 0) for l in (ea["loot"], eb["loot"])), 2 * drops["coin@gold"])
        self.assertEqual(sum(l.get("healing_herb@standard", 0) for l in (ea["loot"], eb["loot"])), 2 * drops["healing_herb@standard"])
        self.assertIsNotNone(ea["report"])
        self.assertIsNotNone(eb["report"])
        self.assertEqual(g.log, [])

    def test_idle_party_member_gets_no_loot_and_no_report(self):
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        a.call("game.join")
        b.call("game.join")
        a.call("party.form")
        b.call("party.accept", invite=a.call("party.invite", target="ben")["result"])
        g.world.svc.record("anna", "identity.xp_gained", {"amount": 200000})            # starke Kämpferin (die Wölfe sind seit dem Balancing zäher)
        walk(g, [a, b], [PATH_TO_WOLVES, PATH_TO_WOLVES])
        for i in range(3000):
            if "anna" in g.fight_of and i % 8 == 0:
                a.call("game.fight", input="light")                              # nur anna kämpft
            g.tick()
            if "anna" not in g.fight_of:
                break
        a.pull()
        b.pull()
        eb = kinds(b, "fight_end")[0]
        self.assertEqual((eb["loot"], eb["report"]), ({}, None))
        self.assertEqual(kinds(a, "fight_end")[0]["loot"]["coin@gold"], 2 * g.R["drops"]["wolf"]["coin@gold"])

    def test_a_third_player_cannot_join_a_running_fight(self):
        g = GameServer()
        a, c = Bot(g, "anna"), Bot(g, "cara")
        a.call("game.join")
        c.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES])
        g.players["cara"]["pos"] = (WOLVES[0] + 50, WOLVES[1])
        for _ in range(5):
            g.tick()
        self.assertNotIn("cara", g.fight_of)

    def test_same_inputs_same_world(self):
        def run():
            g = GameServer()
            a = Bot(g, "anna")
            a.call("game.join")
            walk(g, [a], [PATH_TO_WOLVES])
            fight_until_end(g, [a], spam=("light", "dodge"))
            return json.dumps(g.world.snapshot(), sort_keys=True), json.dumps(a.events, sort_keys=True)
        self.assertEqual(run(), run())


class DayTests(unittest.TestCase):
    def test_days_advance_and_expire_services(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        a.call("party.form")
        b = Bot(g, "ben")
        iid = a.call("party.invite", target="ben")["result"]
        for _ in range(g.R["ticks_per_day"] * 2):
            g.tick()
        self.assertEqual(g.world.day[0], 3)
        self.assertEqual(b.call("party.accept", invite=iid)["error"]["code"], "rejected")      # Frist (2 Tage) abgelaufen


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.srv = NetServer(port=0, tick_seconds=0.002)
        self.port = await self.srv.start()

    async def asyncTearDown(self):
        await self.srv.stop()

    async def test_two_clients_play_a_party_fight_over_tcp(self):
        a, b = Client("127.0.0.1", self.port, "anna"), Client("127.0.0.1", self.port, "ben")
        self.assertEqual((await a.connect())["ev"], "welcome")
        await b.connect()
        for c in (a, b):
            self.assertTrue((await c.call("game.join", char=c.account))["ok"])
        await a.call("party.form", char="anna")
        iid = (await a.call("party.invite", char="anna", target="ben"))["result"]
        self.assertTrue((await b.call("party.accept", char="ben", invite=iid))["ok"])
        g = self.srv.game
        for c in (a, b):                                                     # Test setzt die Spieler an die Wölfe (Laufen ist oben getestet)
            g.players[c.account]["pos"] = (WOLVES[0] + (0 if c is a else 80), WOLVES[1])
        for _ in range(400):
            await asyncio.sleep(0.01)
            if "anna" in g.fight_of:
                break
        self.assertIn("anna", g.fight_of)
        for _ in range(600):
            for c in (a, b):
                if c.account in g.fight_of:
                    await c.call("game.fight", char=c.account, input="light")
            await asyncio.sleep(0.02)
            if a.seen("fight_end") and b.seen("fight_end"):
                break
        self.assertEqual(a.seen("fight_end")[0]["outcome"], "victory")
        self.assertEqual(b.seen("fight_end")[0]["outcome"], "victory")
        self.assertTrue(a.seen("fight"))                                      # Live-Zustand während des Kampfes
        self.assertEqual(a.state["tick"] > 0, True)
        inv = (await a.call("query.inventory", char="anna"))["result"]
        self.assertGreaterEqual(inv["coin@gold"], 200)
        await a.close()
        await b.close()

    async def test_bad_hello_and_oversized_lines(self):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write(b'{"cmd":"hello","account":"bad name"}\n')
        await w.drain()
        self.assertEqual(json.loads(await r.readline())["code"], "bad_hello")
        w.close()
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write(b"nonsense\n")
        await w.drain()
        self.assertEqual(json.loads(await r.readline())["ev"], "error")
        w.close()
        c = Client("127.0.0.1", self.port, "anna")
        await c.connect()
        c.writer.write(b"x" * 6000 + b"\n")
        await c.writer.drain()
        await asyncio.sleep(0.1)
        self.assertTrue(any(e["ev"] == "error" for e in c.events))
        d = Client("127.0.0.1", self.port, "anna")
        w2 = await asyncio.open_connection("127.0.0.1", self.port)
        w2[1].write(b'{"cmd":"hello","account":"anna"}\n')
        await w2[1].drain()
        await asyncio.sleep(0.05)
        w2[1].close()
        await c.close()
        del d

    async def test_disconnect_frees_the_account(self):
        c = Client("127.0.0.1", self.port, "anna")
        await c.connect()
        await c.call("game.join", char="anna")
        await c.close()
        await asyncio.sleep(0.1)
        self.assertNotIn("anna", self.srv.game.players)
        c2 = Client("127.0.0.1", self.port, "anna")
        self.assertEqual((await c2.connect())["ev"], "welcome")
        await c2.close()


def rules_with(**changes):
    R = copy.deepcopy(load_game_rules())
    R.update(changes)
    return R


class SurvivorTests(unittest.TestCase):
    """Fälle, die zuvor nur durch Mutationstests auffielen."""

    def test_drain_empties_the_queue(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.tick()
        g.tick()
        first = g.drain(a.sid)
        self.assertTrue(first)
        self.assertEqual(g.drain(a.sid), [])

    def test_oversized_but_valid_json_is_refused(self):
        g = GameServer()
        a = Bot(g, "anna")
        big = json.dumps({"cmd": "game.join", "args": {"char": "anna", "pad": "x" * 5000}})
        r = g.handle(a.sid, big)
        self.assertEqual((r["ok"], r["error"]["message"]), (False, "Nachricht zu groß"))
        self.assertNotIn("anna", g.players)

    def test_joining_twice_keeps_the_position(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        a.call("game.move", dx=1, dy=0)
        for _ in range(5):
            g.tick()
        pos = a.pos()
        r = a.call("game.join")
        self.assertEqual((a.pos(), r["result"]["you"]["pos"]), (pos, list(pos)))

    def test_gather_is_refused_in_a_fight_even_next_to_a_node(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES])
        g.players["anna"]["pos"] = (1100, 700)                                  # neben ore1, aber im Kampf
        r = a.call("game.gather", node="ore1")
        self.assertEqual((r["error"]["code"], r["error"]["message"]), ("rejected", "Im Kampf nicht möglich"))

    def test_gather_reach_is_inclusive(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        reach = g.R["gather_reach"]
        g.players["anna"]["pos"] = (1100 + reach, 700)
        self.assertTrue(a.call("game.gather", node="ore1")["ok"])
        g.players["anna"]["pos"] = (1300 + reach + 1, 1000)
        self.assertFalse(a.call("game.gather", node="ore2")["ok"])

    def test_new_day_expires_invites_and_offers(self):
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        g.world.inv.deposit("anna", "iron_blade@fine", 2)
        a.call("party.form")
        a.call("party.invite", target="ben")
        o = a.call("trade.offer", to="ben", side="sell", item_key="iron_blade@fine", qty=2, price=300)["result"]
        self.assertEqual(g.world.inv.balance("anna", "iron_blade@fine"), 0)       # hinterlegt
        for _ in range(g.R["ticks_per_day"] * 4):
            g.tick()
        self.assertEqual(g.world.parties.invites, {})
        self.assertEqual(g.world.inv.balance("anna", "iron_blade@fine"), 2)       # Hinterlegung zurück
        self.assertEqual(b.call("trade.accept", offer=o)["error"]["code"], "rejected")

    def test_stop_after_a_fight_and_no_walking_on_with_the_old_direction(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        a.call("game.move", dx=1, dy=1)
        g.players["anna"]["pos"] = (WOLVES[0] - 200, WOLVES[1] - 200)
        for _ in range(3):
            g.tick()
        self.assertIn("anna", g.fight_of)
        fight_until_end(g, [a])
        pos = a.pos()
        for _ in range(10):
            g.tick()
        self.assertEqual(a.pos(), pos)

    def test_fleeing_moves_away_and_the_pause_lasts_exactly_as_long_as_configured(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES])
        before = a.pos()
        a.call("game.fight", input="flee")
        g.tick()
        r = g.R["aggro_radius"]
        self.assertEqual(a.pos(), (before[0] - r, before[1] - r))
        left_at = g.tick_no
        a.call("game.move", dx=1, dy=1)
        entered = None
        for _ in range(200):
            g.tick()
            if "anna" in g.fight_of:
                entered = g.tick_no
                break
        self.assertIsNotNone(entered)
        self.assertGreaterEqual(entered - left_at, g.R["aggro_immunity_ticks"] - 1)    # frühestens nach der Schonfrist
        self.assertLessEqual(entered - left_at, g.R["aggro_immunity_ticks"] + 200)     # danach müssen Gegner heimkehren und neu aufmerksam werden

    def test_no_second_fight_while_fighting(self):
        R = rules_with(enemies=[{"type": "wolf", "at": [2000, 1800]}, {"type": "wolf", "at": [2000, 1850]}, {"type": "wolf", "at": [2000, 2800]}])
        g = GameServer(R)
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (2000, 2150)                                  # alle drei bemerken sie; das dritte Tier (650 entfernt) ist nicht im Rudelradius
        for _ in range(120):
            g.tick()
        self.assertEqual(len(g.fights), 1)
        self.assertEqual(g.fights[g.fight_of["anna"]]["types"], ["wolf", "wolf"])
        self.assertIsNone(g.enemies[2]["fight"])
        self.assertIn(g.enemies[2]["state"], ("return", "idle"))                 # sein Ziel kämpft schon: es gibt auf und geht heim

    def test_party_members_far_away_or_busy_do_not_join(self):
        R = rules_with(join_radius=1000, enemies=[{"type": "wolf", "at": [2000, 1800]}])
        g = GameServer(R)
        a, b = Bot(g, "anna"), Bot(g, "ben")
        for x in (a, b):
            x.call("game.join")
        a.call("party.form")
        b.call("party.accept", invite=a.call("party.invite", target="ben")["result"])
        g.players["ben"]["pos"] = (2000 + 1001, 1800)                           # knapp außerhalb des Beitrittsradius
        g.players["anna"]["pos"] = (2000, 1800)
        for _ in range(40):
            g.tick()
        self.assertEqual(g.fights[g.fight_of["anna"]]["chars"], ["anna"])
        self.assertNotIn("ben", g.fight_of)

    def test_party_member_inside_the_radius_joins_exactly_at_the_border(self):
        R = rules_with(join_radius=1000, enemies=[{"type": "wolf", "at": [2000, 1800]}])
        g = GameServer(R)
        a, b = Bot(g, "anna"), Bot(g, "ben")
        for x in (a, b):
            x.call("game.join")
        a.call("party.form")
        b.call("party.accept", invite=a.call("party.invite", target="ben")["result"])
        g.players["ben"]["pos"] = (2000 + 1000, 1800)
        g.players["anna"]["pos"] = (2000, 1800)
        g.tick()
        self.assertEqual(g.fights[g.fight_of["anna"]]["chars"], ["anna", "ben"])

    def test_a_member_in_another_fight_is_not_pulled_in(self):
        R = rules_with(join_radius=4000, enemies=[{"type": "wolf", "at": [500, 5000]}, {"type": "wolf", "at": [3000, 5000]}])
        g = GameServer(R)
        a, b = Bot(g, "anna"), Bot(g, "ben")
        for x in (a, b):
            x.call("game.join")
        a.call("party.form")
        b.call("party.accept", invite=a.call("party.invite", target="ben")["result"])
        g.players["anna"]["pos"] = (5900, 5900)
        g.players["ben"]["pos"] = (500, 5000)
        g.tick()
        self.assertIn("ben", g.fight_of)
        g.players["anna"]["pos"] = (3000, 5000)
        g.tick()
        self.assertEqual(g.fights[g.fight_of["anna"]]["chars"], ["anna"])
        self.assertNotEqual(g.fight_of["anna"], g.fight_of["ben"])

    def test_loot_is_shared_round_robin_and_coins_split_with_remainder(self):
        R = rules_with(enemies=[{"type": "wolf", "at": [2000, 1800]}], drops={"wolf": {"coin@gold": 7, "healing_herb@standard": 2}})
        g = GameServer(R)
        a, b = Bot(g, "anna"), Bot(g, "ben")
        for x in (a, b):
            x.call("game.join")
        a.call("party.form")
        b.call("party.accept", invite=a.call("party.invite", target="ben")["result"])
        g.players["anna"]["pos"] = (2000, 1800)
        g.players["ben"]["pos"] = (2100, 1800)
        g.tick()
        fight_until_end(g, [a, b])
        ea, eb = kinds(a, "fight_end")[0], kinds(b, "fight_end")[0]
        self.assertEqual((ea["loot"]["coin@gold"], eb["loot"]["coin@gold"]), (4, 3))
        self.assertEqual((ea["loot"]["healing_herb@standard"], eb["loot"]["healing_herb@standard"]), (1, 1))
        self.assertEqual(g.world.inv.balance("anna", "coin@gold"), 204)

    def test_a_participant_who_fled_gets_no_loot_but_keeps_the_report(self):
        R = rules_with(enemies=[{"type": "wolf", "at": [2000, 1800]}])
        g = GameServer(R)
        a, b = Bot(g, "anna"), Bot(g, "ben")
        for x in (a, b):
            x.call("game.join")
        a.call("party.form")
        b.call("party.accept", invite=a.call("party.invite", target="ben")["result"])
        g.players["anna"]["pos"] = (2000, 1800)
        g.players["ben"]["pos"] = (2100, 1800)
        g.tick()
        b.call("game.fight", input="light")
        for _ in range(9):
            g.tick()
        b.call("game.fight", input="flee")
        fight_until_end(g, [a])
        b.pull()
        self.assertEqual(kinds(b, "fight_left")[0]["reason"], "fled")
        self.assertEqual(kinds(a, "fight_end")[0]["loot"]["coin@gold"], g.R["drops"]["wolf"]["coin@gold"])         # alles an anna
        eb = kinds(b, "fight_end")[0]
        self.assertEqual((eb["outcome"], eb["loot"], eb["report"] is not None), ("fled", {}, True))      # Bericht ja, Beute nein

    def test_a_mismatch_between_live_and_replay_is_logged(self):
        import dataclasses
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [PATH_TO_WOLVES])
        real = g.encounters.finish_pack

        def tampered(eid, inputs):
            fin = real(eid, inputs)
            return dataclasses.replace(fin, result=dataclasses.replace(fin.result, ticks=fin.result.ticks + 1))
        g.encounters.finish_pack = tampered
        fight_until_end(g, [a])
        self.assertTrue(any("weicht" in m for m in g.log))


class NetSurvivorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.srv = NetServer(port=0, tick_seconds=0.002, max_per_ip=100)
        self.port = await self.srv.start()

    async def asyncTearDown(self):
        await self.srv.stop()

    async def hello(self, line):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write(line + b"\n")
        await w.drain()
        out = json.loads(await asyncio.wait_for(r.readline(), 2))
        w.close()
        return out

    async def test_hello_must_be_an_object_with_cmd_hello(self):
        for line in (b"[]", b'{"cmd":"join","account":"anna"}', b'{"account":"anna"}', b"5"):
            out = await self.hello(line)
            self.assertEqual((out["ev"], out["code"]), ("error", "bad_hello"), line)
        self.assertEqual((await self.hello(b'{"cmd":"hello","account":"anna"}'))["ev"], "welcome")

    async def test_server_full(self):
        clients = []
        for i in range(16):
            c = Client("127.0.0.1", self.port, f"p{i}")
            await c.connect()
            clients.append(c)
        out = await self.hello(b'{"cmd":"hello","account":"extra"}')
        self.assertEqual(out["code"], "server_full")
        for c in clients:
            await c.close()


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from mmo_world.persistence import Store
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def played(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        walk(g, [a], [(1100, 700)], reach=200)
        a.call("game.gather", node="ore1")
        walk(g, [a], [PATH_TO_WOLVES])
        fight_until_end(g, [a])
        return g, a

    def test_save_and_load_restore_world_and_game_state(self):
        from mmo_game import GameServer as GS
        g, a = self.played()
        pos = a.pos()
        gen = g.save(self.store)
        h = GS.load(self.store)
        self.assertEqual(h.world.snapshot(), g.world.snapshot())
        self.assertEqual(h.world.svc.log.events("anna")[-1].hash, g.world.svc.log.events("anna")[-1].hash)
        self.assertEqual(h.tick_no, g.tick_no)
        self.assertEqual([(e["alive"], e["respawn_at"]) for e in h.enemies], [(e["alive"], e["respawn_at"]) for e in g.enemies])
        self.assertEqual([n["ready_at"] for n in h.nodes], [n["ready_at"] for n in g.nodes])
        self.assertEqual(h.world.inv.balance("anna", "coin@gold"), g.world.inv.balance("anna", "coin@gold"))
        self.assertEqual(gen, 1)
        b = Bot(h, "anna")                                      # nach dem Neustart wieder verbinden: alte Position
        self.assertEqual(b.call("game.join")["result"]["you"]["pos"], list(pos))

    def test_encounter_ids_do_not_repeat_after_a_restart(self):
        from mmo_game import GameServer as GS
        g, a = self.played()
        g.save(self.store)
        h = GS.load(self.store)
        self.assertEqual(h.encounters._counter, 1)
        b = Bot(h, "anna")
        b.call("game.join")
        for _ in range(h.R["respawn_ticks"] + 5):
            h.tick()
        walk(h, [b], [PATH_TO_WOLVES])
        fight_until_end(h, [b])
        self.assertEqual(h.log, [])                              # CEE hat den Bericht mit neuer ID angenommen
        self.assertEqual(kinds(b, "fight_end")[0]["outcome"], "victory")
        self.assertEqual(h.world.svc.state("anna").parts["combat"]["stats"]["victory"], 2)

    def test_the_encounter_counter_is_the_maximum_over_all_characters(self):
        from mmo_game import GameServer as GS
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")                    # anna ist vor ben angelegt, kämpft aber später (höhere ID)
        for x in (a, b):
            x.call("game.join")
        walk(g, [b], [PATH_TO_WOLVES])
        fight_until_end(g, [b])
        g.players["ben"]["pos"] = (3000, 5700)
        for _ in range(g.R["respawn_ticks"] + 5):
            g.tick()
        walk(g, [a], [PATH_TO_WOLVES])
        fight_until_end(g, [a])
        g.save(self.store)
        self.assertEqual(GS.load(self.store).encounters._counter, 2)

    def test_offline_positions_survive_a_save(self):
        from mmo_game import GameServer as GS
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        a.call("game.move", dx=1, dy=0)
        for _ in range(9):
            g.tick()
        pos = a.pos()
        g.disconnect(a.sid)
        g.save(self.store)
        h = GS.load(self.store)
        self.assertEqual(Bot(h, "anna").call("game.join")["result"]["you"]["pos"], list(pos))

    def test_state_from_another_generation_is_ignored_but_the_world_stays(self):
        from mmo_game import GameServer as GS
        g, a = self.played()
        g.save(self.store)
        g.save(self.store)
        f = self.store.path / "game_state.json"
        data = json.loads(f.read_text())
        data["generation"] = 1                                    # gehört nicht zur aktuellen Generation
        f.write_text(json.dumps(data))
        h = GS.load(self.store)
        self.assertEqual(h.tick_no, 0)
        self.assertTrue(all(e["alive"] for e in h.enemies))
        self.assertEqual(h.world.inv.balance("anna", "coin@gold"), g.world.inv.balance("anna", "coin@gold"))
        f.write_text("kaputt")
        self.assertEqual(GS.load(self.store).tick_no, 0)

    def test_a_damaged_latest_generation_falls_back_to_the_previous_one(self):
        from mmo_game import GameServer as GS
        g, a = self.played()
        g.save(self.store)
        coins = g.world.inv.balance("anna", "coin@gold")
        g.world.inv.deposit("anna", "coin@gold", 5)
        g.save(self.store)
        (self.store.path / "gen-000002" / "snapshot.json").write_text("{}")
        h = GS.load(self.store)
        self.assertEqual(h.world.inv.balance("anna", "coin@gold"), coins)

    def test_load_without_a_save_fails_clearly(self):
        from mmo_game import GameServer as GS
        from mmo_world.persistence import PersistenceError
        with self.assertRaises(PersistenceError):
            GS.load(self.store)

    def test_disconnect_remembers_the_position(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        a.call("game.move", dx=1, dy=1)
        for _ in range(7):
            g.tick()
        pos = a.pos()
        g.disconnect(a.sid)
        b = Bot(g, "anna")
        self.assertEqual(b.call("game.join")["result"]["you"]["pos"], list(pos))
        g.disconnect(b.sid)
        c = Bot(g, "anna")
        self.assertEqual(c.call("game.join")["result"]["you"]["pos"], list(pos))     # auch nach nochmaligem Trennen


class NetPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_autosave_and_save_on_stop(self):
        import tempfile
        from mmo_world.persistence import Store
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            srv = NetServer(port=0, tick_seconds=0.001, store=store, autosave_ticks=20)
            port = await srv.start()
            c = Client("127.0.0.1", port, "anna")
            await c.connect()
            await c.call("game.join", char="anna")
            for _ in range(200):
                await asyncio.sleep(0.01)
                if store.generations():
                    break
            self.assertTrue(store.generations())
            await c.close()
            await srv.stop()
            n = len(store.generations())
            self.assertGreaterEqual(n, 1)
            self.assertTrue((store.path / "game_state.json").exists())
            from mmo_game import GameServer as GS
            self.assertEqual(GS.load(store).world.inv.balance("anna", "coin@gold"), 200)

    async def test_stopping_saves_even_without_autosave(self):
        import tempfile
        from mmo_world.persistence import Store
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            srv = NetServer(port=0, tick_seconds=0.001, store=store, autosave_ticks=0)
            await srv.start()
            await asyncio.sleep(0.05)
            self.assertEqual(store.generations(), [])
            await srv.stop()
            self.assertEqual(store.generations(), [1])

    async def test_no_store_means_no_files_and_no_error(self):
        srv = NetServer(port=0, tick_seconds=0.001)
        await srv.start()
        await asyncio.sleep(0.05)
        await srv.stop()


if __name__ == "__main__":
    unittest.main()
