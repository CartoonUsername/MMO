"""Eigenschaftstests für Kämpfe mit Gegnerfähigkeiten (sim_rules_v7): zufällige Eingaben von bis zu drei Spielern gegen alle Gegnerarten
und gemischte Rudel, in jedem Tick werden Invarianten geprüft (ADR-0037). Ergänzt test_enemy_sim um Kämpfe über viele Ticks und Wechselwirkungen
(Schilde, Zustände, Unterbrechen, Beschwörungen, Phasen), ohne Regeln zu ändern."""
import random
import unittest

from mmo_sim.enemies import roll_abilities
from mmo_sim.live import LiveEncounter, replay_equals_live
from mmo_sim.rules import load_sim_rules

C = load_sim_rules("sim_rules_v7.json")
CMDS = ["light", "heavy", "dodge", "block", "stun", "slow", "sweep", "heal", "shield", "target_1", "target_2", "target_3", "target_4", "target_5",
        "cast_ember", "dash", "veil", "focus_surge"]
TYPES = ["wolf", "wolf_pup", "bear", "alpha_wolf", "wisp_healer", "bog_witch", "stone_warden", "shadow_hunter", "totem_caller", "stone_imp", "stone_heart_colossus"]


def play(opps, n_players, seed, level, flee_at=900):
    rng = random.Random(seed)
    players = [{"level": level + i, "inputs": []} for i in range(n_players)]
    abil = [roll_abilities(C, t, f"sp{k}", seed) for k, t in enumerate(opps)]
    e = LiveEncounter(C, opps, players, abil)
    events, views = [], []
    while not e.done:
        for i in range(e.player_count):
            if rng.random() < 0.35:
                e.submit(i, rng.choice(CMDS))
        if e.t == flee_at:
            for i in range(e.player_count):
                e.submit(i, "flee")
        e.advance()
        events += e.drain_events()
        if e.t % 5 == 0 or e.done:
            views.append(e.view())
    return e, players, events, views


class InvariantTests(unittest.TestCase):
    CASES = [([t], 1 + i % 3, 100 + i, 6 + i % 12) for i, t in enumerate(TYPES)] + \
            [(["wolf", "wolf", "alpha_wolf"], 2, 7, 12), (["wisp_healer", "bog_witch", "stone_warden"], 3, 8, 14), (["stone_heart_colossus", "totem_caller"], 3, 9, 20),
             (["bear", "shadow_hunter", "stone_imp"], 2, 10, 15)]

    def test_zustandsgroessen_bleiben_im_gueltigen_bereich(self):
        for opps, n, seed, level in self.CASES:
            e, players, events, views = play(opps, n, seed, level)
            with self.subTest(opps=opps, seed=seed):
                cap = C["enemy_abilities"]["max_enemies"]
                for v in views:
                    self.assertLessEqual(len(v["opponents"]), max(cap, len(opps)))
                    for p in v["players"]:
                        self.assertTrue(0 <= p["hp"] <= p["max_hp"], p)
                        self.assertGreaterEqual(p["stamina"], 0)
                        self.assertTrue(p["stunned"] >= 0 and p["slowed"] >= 0 and p["busy"] >= 0)
                        if p["hp"] == 0:
                            self.assertEqual(p["state"], "down")
                    for o in v["opponents"]:
                        self.assertGreaterEqual(o["hp"], 0)
                        self.assertGreaterEqual(o["shield"], 0)
                        if not o["alive"]:
                            self.assertIsNone(o["casting"])

    def test_ankuendigungen_haben_hoechstens_ein_ergebnis_und_wirken_zur_rechten_zeit(self):
        for opps, n, seed, level in self.CASES:
            e, players, events, views = play(opps, n, seed, level)
            with self.subTest(opps=opps, seed=seed):
                self.assertEqual([x["t"] for x in events], sorted(x["t"] for x in events))        # Ereignisse in Zeitordnung
                open_casts: dict[tuple[int, str], dict] = {}
                for x in events:
                    if x.get("kind") == "basic" or x.get("ability") == "basic_attack":     # normale Angriffe werden nur angezeigt, ohne Ergebnisereignis
                        continue
                    key = (x["enemy"], x["ability"]) if "ability" in x else None
                    if x["type"] == "telegraph":
                        self.assertNotIn(key, open_casts, "zweite Ankündigung derselben Fähigkeit vor dem Ergebnis")
                        open_casts[key] = x
                    elif x["type"] == "resolved":
                        tele = open_casts.pop(key, None)
                        self.assertIsNotNone(tele, f"Ergebnis ohne Ankündigung: {x}")
                        self.assertEqual(x["t"], tele["t"] + tele["ticks"])
                    elif x["type"] == "interrupted":
                        tele = open_casts.pop(key, None)
                        self.assertIsNotNone(tele, f"Unterbrechung ohne Ankündigung: {x}")
                        self.assertLess(x["t"], tele["t"] + tele["ticks"])

    def test_live_und_wiederholung_stimmen_ueberein_und_sind_reproduzierbar(self):
        for opps, n, seed, level in self.CASES:
            e, players, events, _ = play(opps, n, seed, level)
            with self.subTest(opps=opps, seed=seed):
                self.assertTrue(replay_equals_live(C, e, players))
                e2, _, events2, _ = play(opps, n, seed, level)                                   # gleicher Ausgangszustand, gleiche Eingaben
                self.assertEqual(e.result, e2.result)
                self.assertEqual(events, events2)

    def test_ergebnis_ist_in_sich_stimmig(self):
        for opps, n, seed, level in self.CASES:
            e, players, events, _ = play(opps, n, seed, level)
            r = e.result
            with self.subTest(opps=opps, seed=seed):
                self.assertIn(r.outcome, ("victory", "defeat", "fled", "timeout"))
                self.assertEqual(len(r.players), n)
                if r.outcome == "victory":
                    last = e.view()
                    self.assertTrue(all(not o["alive"] for o in last["opponents"]))             # Sieg nur mit allen (auch beschworenen) Gegnern erledigt

    def test_die_faelle_sind_nicht_leer_sondern_decken_die_mechaniken_ab(self):
        from collections import Counter
        kinds, outcomes, longest = Counter(), Counter(), 0
        for opps, n, seed, level in self.CASES:
            e, _, events, _ = play(opps, n, seed, level)
            kinds.update(x["type"] for x in events)
            outcomes[e.result.outcome] += 1
            longest = max(longest, e.t)
        for k in ("telegraph", "resolved", "interrupted", "phase", "shield_broken"):
            self.assertGreater(kinds[k], 0, k)
        self.assertGreater(kinds["telegraph"], 100)
        self.assertGreaterEqual(len(outcomes), 2)
        self.assertGreater(longest, 600)


if __name__ == "__main__":
    unittest.main()
