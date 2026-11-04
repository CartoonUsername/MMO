import unittest

from mmo_game import GameServer
from mmo_sim.enemies import roll_abilities


class Bot:
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

    def of(self, ev):
        return [e for e in self.events if e["ev"] == ev]


def start(g, bot, pos, ticks=200):
    bot.call("game.join")
    g.players[bot.name]["pos"] = pos
    for _ in range(ticks):
        g.tick()
        bot.pull()
        if bot.name in g.fight_of:
            return True
    return False


def fight(g, bots, cmds=("light",), every=8, max_ticks=4000):
    for i in range(max_ticks):
        for b in bots:
            if b.name in g.fight_of and i % every == 0:
                for c in cmds:
                    b.call("game.fight", input=c)
        g.tick()
        for b in bots:
            b.pull()
        if all(b.name not in g.fight_of for b in bots):
            return


class AbilityRollTests(unittest.TestCase):
    def test_fight_start_announces_the_abilities_rolled_for_spawn_and_day(self):
        g = GameServer()
        a = Bot(g, "anna")
        self.assertTrue(start(g, a, (3000, 1000)))
        st = a.of("fight_start")[0]
        fid = g.fight_of["anna"]
        ids = g.fights[fid]["enemies"]
        types = st["opponents"]
        self.assertEqual(sorted(types), ["bog_witch", "wisp_healer"])
        for t, i, ab in zip(types, ids, st["abilities"]):
            self.assertEqual(ab, roll_abilities(g.sim, t, i, g.world.day[0]))
        self.assertIn("mend", dict(zip(types, st["abilities"]))["wisp_healer"])
        self.assertIn("burning_curse", dict(zip(types, st["abilities"]))["bog_witch"])

    def test_same_spawn_same_day_same_abilities_but_a_new_day_may_differ(self):
        seen = {}
        for day in range(1, 8):
            g = GameServer()
            g.world.day[0] = day
            a = Bot(g, "anna")
            self.assertTrue(start(g, a, (3000, 1000)))
            seen[day] = tuple(map(tuple, a.of("fight_start")[0]["abilities"]))
            g2 = GameServer()
            g2.world.day[0] = day
            b = Bot(g2, "ben")
            start(g2, b, (3000, 1000))
            self.assertEqual(tuple(map(tuple, b.of("fight_start")[0]["abilities"])), seen[day])          # reproduzierbar
        self.assertGreater(len(set(seen.values())), 1)

    def test_old_sim_rules_send_no_abilities(self):
        import copy
        from mmo_game import load_game_rules
        r = copy.deepcopy(load_game_rules())
        r["sim_rules"] = "sim_rules_v5.json"
        r["enemies"] = [{"type": "wolf", "at": [2000, 1800]}]
        g = GameServer(r)
        a = Bot(g, "anna")
        self.assertTrue(start(g, a, (2000, 2100)))
        self.assertIsNone(a.of("fight_start")[0]["abilities"])


class TelegraphTests(unittest.TestCase):
    def test_telegraphs_and_results_reach_the_participants_in_order(self):
        g = GameServer()
        a = Bot(g, "anna")
        self.assertTrue(start(g, a, (3000, 1000)))
        res = []
        for _ in range(400):
            g.tick()
            a.pull()
            tel = a.of("telegraph")
            if tel:
                first = tel[0]
                res = [e for e in a.of("enemy_event") if e["type"] == "resolved" and e["ability"] == first["ability"] and e["enemy"] == first["enemy"]]
                if res:
                    break
        self.assertEqual(first["fight"], g.fight_of["anna"])
        self.assertTrue(first["answers"] and first["ticks"] >= 1 and first["ability"] and first["kind"])
        self.assertTrue(res and res[0]["t"] == first["t"] + first["ticks"])       # Ergebnis genau nach der Vorwarnzeit

    def test_view_events_include_casting_and_player_states(self):
        g = GameServer()
        a = Bot(g, "anna")
        start(g, a, (3000, 1000))
        saw_cast = False
        for _ in range(300):
            g.tick()
            a.pull()
            for f in a.of("fight"):
                if any(o.get("casting") for o in f["opponents"]):
                    saw_cast = True
            if saw_cast or a.name not in g.fight_of:
                break
        self.assertTrue(saw_cast)
        self.assertIn("stunned", a.of("fight")[-1]["players"][0])

    def test_non_participants_get_no_telegraphs(self):
        g = GameServer()
        a, b = Bot(g, "anna"), Bot(g, "ben")
        b.call("game.join")
        g.players["ben"]["pos"] = (400, 400)
        start(g, a, (3000, 1000))
        for _ in range(100):
            g.tick()
            b.pull()
        self.assertEqual((b.of("telegraph"), b.of("enemy_event")), ([], []))


class EndToEndTests(unittest.TestCase):
    def test_healer_and_witch_fight_ends_with_an_accepted_report_and_matching_replay(self):
        g = GameServer()
        a = Bot(g, "anna")
        g.world.svc.record("anna", "identity.xp_gained", {"amount": 100000})
        start(g, a, (3000, 1000))
        fight(g, [a], cmds=("light", "stun", "dodge"), every=8)
        end = a.of("fight_end")
        left = a.of("fight_left")
        self.assertTrue(end or left)
        self.assertEqual(g.log, [])                                               # Live-Ergebnis == Neuberechnung mit denselben Fähigkeiten
        if end:
            self.assertIn(end[0]["outcome"], ("victory", "defeat", "fled"))
            self.assertIsNotNone(end[0]["report"])

    def test_the_boss_fight_runs_and_never_breaks_the_report_rules(self):
        g = GameServer()
        bots = [Bot(g, n) for n in ("anna", "ben", "cara")]
        for b in bots:
            b.call("game.join")
        bots[0].call("party.form")
        for b in bots[1:]:
            b.call("party.accept", invite=bots[0].call("party.invite", target=b.name)["result"])
        for b in bots:
            g.world.svc.record(b.name, "identity.xp_gained", {"amount": 100000})
        for i, b in enumerate(bots):
            g.players[b.name]["pos"] = (5200 + 80 * i, 5000)
        for _ in range(200):
            g.tick()
            if bots[0].name in g.fight_of:
                break
        self.assertIn("anna", g.fight_of)
        self.assertEqual(g.fights[g.fight_of["anna"]]["types"], ["stone_heart_colossus"])
        for i in range(2500):
            for b in bots:
                if b.name in g.fight_of:
                    if i % 8 == 0:
                        b.call("game.fight", input="light")
                    if i % 25 == 3:
                        b.call("game.fight", input="dodge")
                    if i == 1800:
                        b.call("game.fight", input="flee")
            g.tick()
            if all(b.name not in g.fight_of for b in bots):
                break
        self.assertEqual(g.log, [])
        for b in bots:
            b.pull()
            self.assertTrue(b.of("fight_end") or b.of("fight_left"))
        tel = [e["ability"] for e in bots[0].of("telegraph")]
        self.assertIn("colossus_slam", tel)
        self.assertIn("colossus_quake", tel)
        self.assertIn("basic_attack", tel)                                        # auch normale Angriffe werden angekündigt (sim_rules_v7)

    def test_summons_vanish_after_the_fight_and_do_not_drop_loot(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.world.svc.record("anna", "identity.xp_gained", {"amount": 100000})
        g.players["anna"]["pos"] = (800, 3000)
        for _ in range(200):
            g.tick()
            if "anna" in g.fight_of:
                break
        self.assertEqual(g.fights[g.fight_of["anna"]]["types"], ["totem_caller"])
        fight(g, [a], cmds=("light", "sweep"), every=8, max_ticks=2500)
        a.pull()
        self.assertEqual(g.log, [])
        self.assertTrue(all(e["fight"] is None for e in g.enemies))
        self.assertEqual(len(g.enemies), len(g.R["enemies"]))                                     # Beschworene sind keine Welt-Gegner

    def test_a_loadout_change_during_a_fight_does_not_change_the_replayed_result(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.world.svc.record("anna", "identity.xp_gained", {"amount": 50000})
        start(g, a, (3000, 1000))
        g.world.svc.record("anna", "identity.xp_gained", {"amount": 200000})        # Stufe ändert sich mitten im Kampf (z. B. durch Verwaltungsvorgang)
        fight(g, [a], cmds=("light", "dodge"), every=8)
        self.assertEqual(g.log, [])

    def test_the_world_snapshot_shows_new_enemy_types_with_states(self):
        g = GameServer()
        a = Bot(g, "anna")
        a.call("game.join")
        g.players["anna"]["pos"] = (5000, 4900)
        st = a.call("game.state")["result"]
        types = {e["type"]: e["state"] for e in st["enemies"]}
        self.assertEqual(types.get("stone_heart_colossus"), "idle")


if __name__ == "__main__":
    unittest.main()
