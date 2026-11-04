import random
import unittest

from mmo_sim import SimError
from mmo_sim.live import LiveEncounter, replay_equals_live
from mmo_sim.rules import load_sim_rules

C = load_sim_rules("sim_rules_v5.json")
CMDS = ["light", "heavy", "dodge", "block", "stun", "slow", "heal", "shield", "sweep", "target_1", "target_2", "cast_ember", "dash", "veil", "focus_surge", "flee"]


def play(opps, players, seed, p=0.25, flee_at=None):
    rng = random.Random(seed)
    e = LiveEncounter(C, opps, players)
    while not e.done:
        for i in range(e.player_count):
            if rng.random() < p:
                e.submit(i, rng.choice(CMDS))
        if flee_at is not None and e.t == flee_at:
            for i in range(e.player_count):
                e.submit(i, "flee")
        e.advance()
    return e


class LiveTests(unittest.TestCase):
    def test_live_play_equals_replay_of_the_input_log(self):
        for seed in range(1, 25):
            opps = [("wolf", "bear", "stone_golem", "training_dummy")[(seed + k) % 4] for k in range(1 + seed % 3)]
            players = [{"level": 5 + seed + i, "equipped": ["ember_strike"][: i % 2]} for i in range(1 + seed % 4)]
            e = play(opps, players, seed, flee_at=400)
            self.assertTrue(replay_equals_live(C, e, players), seed)

    def test_inputs_get_the_current_server_tick(self):
        e = LiveEncounter(C, ["wolf"], [{"level": 1}])
        for _ in range(7):
            e.advance()
        self.assertTrue(e.submit(0, "light"))
        e.advance()
        self.assertTrue(e.submit(0, "block"))
        self.assertEqual(e.inputs_of(0), [[7, "light"], [8, "block"]])

    def test_submit_validation(self):
        e = LiveEncounter(C, ["wolf"], [{"level": 1, "allowed": ["light", "flee"]}])
        for bad in ("fireball", "", None, 5, "target_4"):
            self.assertFalse(e.submit(0, bad))
        for player in (1, -1, True, "0", None):
            self.assertFalse(e.submit(player, "light"))
        self.assertTrue(e.submit(0, "block"))                   # angenommen, aber vom Freigabefilter ignoriert
        e.advance()
        self.assertEqual(e._sim.ps[0].ignored, 1)
        self.assertTrue(e.submit(0, "flee"))
        e.advance()
        self.assertFalse(e.submit(0, "light"))                  # ausgeschieden
        self.assertTrue(e.done)
        self.assertFalse(e.submit(0, "flee"))

    def test_input_limit(self):
        cfg = dict(C, max_inputs=3)
        e = LiveEncounter(cfg, ["training_dummy"], [{"level": 1}])
        self.assertEqual([e.submit(0, "light") for _ in range(5)], [True, True, True, False, False])

    def test_timeout_and_idempotent_advance(self):
        e = LiveEncounter(C, ["training_dummy"], [{"level": 1}])
        while not e.done:
            e.advance()
        self.assertEqual((e.result.outcome, e.t), ("fled", C["max_ticks"]))
        r = e.result
        self.assertIs(e.advance(), r)
        self.assertEqual(e.t, C["max_ticks"])

    def test_invalid_setup_is_rejected(self):
        for opps, players in (([], [{"level": 1}]), (["wolf"] * 4, [{"level": 1}]), (["dragon"], [{"level": 1}]), (["wolf"], []),
                              (["wolf"], [{"level": 0}]), (["wolf"], [{"level": 1, "equipped": "x"}]), (["wolf"], "x")):
            with self.assertRaises(SimError):
                LiveEncounter(C, opps, players)

    def test_view_shows_only_public_state(self):
        e = LiveEncounter(C, ["wolf", "bear"], [{"level": 1}, {"level": 30}])
        e.submit(0, "heavy")
        for _ in range(3):
            e.advance()
        v = e.view()
        self.assertEqual(v["tick"], 3)
        self.assertEqual([o["type"] for o in v["opponents"]], ["wolf", "bear"])
        self.assertEqual(v["players"][0]["cooldowns"], {"heavy": 17})
        self.assertEqual(v["players"][0]["busy"], 17)
        self.assertEqual(v["players"][1]["max_hp"], 1000 + 20 * 30)
        self.assertNotIn("threat", str(v))
        self.assertEqual(v["stagger"], [False, False])

    def test_dead_opponents_show_zero_hp(self):
        e = play(["training_dummy"], [{"level": 1}], 3, p=0.6)
        self.assertEqual(e.view()["opponents"][0]["hp"] == 0, e.result.outcome == "victory")


if __name__ == "__main__":
    unittest.main()
