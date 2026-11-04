import unittest
from pathlib import Path

from mmo_cee.rules import load_rules
from mmo_sim.balance import FAMILIES, MISS_EVERY, REACTION, RULES_FILE, Bot, fight, matrix, report
from mmo_sim.rules import check_compatibility, load_sim_rules

C = load_sim_rules(RULES_FILE)
DOC = Path(__file__).resolve().parents[3] / "docs" / "BALANCE_REPORT.md"


def cell(name, party, skill, spawns=6):
    opp, lvl = FAMILIES[name]
    return matrix(C, opp, [lvl] * party, skill, spawns=1 if "Boss" in name else spawns)


class RulesTests(unittest.TestCase):
    def test_v7_is_valid_compatible_and_keeps_v6_untouched(self):
        self.assertEqual(C["version"], "7")
        self.assertEqual(check_compatibility(C, load_rules("rules_v9.json")), [])
        v6 = load_sim_rules("sim_rules_v6.json")
        self.assertEqual(v6["opponents"]["wolf"]["hp"], 300)                      # v6 bleibt unverändert (Vektoren)
        self.assertEqual(C["opponents"]["wolf"]["hp"], 850)
        self.assertTrue(C["enemy_abilities"]["telegraph_basic"])
        self.assertNotIn("telegraph_basic", v6["enemy_abilities"])

    def test_summoned_pups_are_weaker_than_wolves(self):
        self.assertLess(C["opponents"]["wolf_pup"]["hp"], C["opponents"]["wolf"]["hp"])
        self.assertEqual(C["enemy_abilities"]["abilities"]["call_pack"]["summon"], "wolf_pup")


class BotTests(unittest.TestCase):
    def ev(self, kind, ticks, target=0, t=100, enemy=0):
        return {"t": t, "type": "telegraph", "kind": kind, "ticks": ticks, "target": target, "enemy": enemy, "ability": "x", "answers": []}

    def test_novice_never_reacts(self):
        b = Bot(0, "novice", "attacker", 1)
        b.plan(self.ev("slam", 20), [], [])
        self.assertEqual(b.queue, [])

    def test_reaction_time_limits_what_can_be_answered(self):
        a = Bot(0, "average", "attacker", 1)
        a.plan(self.ev("slam", REACTION["average"] + 1), [], [])
        self.assertEqual(a.queue, [])                                               # zu kurz für „average"
        a.plan(self.ev("slam", REACTION["average"] + 2), [], [])
        self.assertEqual(len(a.queue), 1)
        g = Bot(0, "good", "attacker", 1)
        g.plan(self.ev("slam", REACTION["good"] + 2), [], [])
        self.assertEqual(len(g.queue), 1)

    def test_only_attacks_on_me_are_answered_but_areas_always(self):
        b = Bot(1, "good", "attacker", 2)
        b.plan(self.ev("slam", 12, target=0), [], [])
        b.plan(self.ev("basic", 12, target=0), [], [])
        b.plan(self.ev("state", 12, target=0), [], [])
        self.assertEqual(b.queue, [])
        b.plan(self.ev("area", 12, target=None), [], [])
        self.assertEqual(len(b.queue), 1)

    def test_answers_match_the_skill(self):
        g = Bot(0, "good", "attacker", 1)
        g.plan(self.ev("slam", 12, t=100), [], [])
        g.plan(self.ev("area", 12, t=200), [], [])
        self.assertEqual(g.queue, [(111, "block"), (211, "dodge")])                   # Parade bzw. perfektes Ausweichen
        a = Bot(0, "average", "attacker", 1)
        a.plan(self.ev("slam", 12, t=100), [], [])
        self.assertEqual(a.queue, [(110, "dodge")])

    def test_miss_pattern(self):
        a = Bot(0, "average", "attacker", 1)
        for _ in range(6):
            a.plan(self.ev("slam", 12), [], [])
        self.assertEqual(len(a.queue), 6 - 6 // MISS_EVERY["average"])
        g = Bot(0, "good", "attacker", 1)
        for _ in range(10):
            g.plan(self.ev("slam", 12), [], [])
        self.assertEqual(len(g.queue), 10 - 10 // MISS_EVERY["good"])

    def test_only_attackers_interrupt_and_only_good_ones(self):
        ev = self.ev("cast", 20, enemy=2)
        g = Bot(0, "good", "attacker", 1)
        g.plan(ev, [], [])
        self.assertEqual(g.queue, [(103, "target_3"), (104, "stun")])
        s = Bot(1, "good", "support", 2)
        s.plan(ev, [], [])
        self.assertEqual(s.queue, [])
        a = Bot(0, "average", "attacker", 1)
        a.plan(ev, [], [])
        self.assertEqual(a.queue, [])

    def test_fights_are_deterministic(self):
        a = fight(C, ["bear"], [12], "average", "sp1")
        b = fight(C, ["bear"], [12], "average", "sp1")
        self.assertEqual(a, b)


class TargetTests(unittest.TestCase):
    """Zielbilder des Balancings (Platzhalter, ADR-0034). Bandbreiten gelten für den Testspieler „average" bei gleicher Stufe."""

    def test_normal_mobs_are_solo_winnable_with_a_real_cost(self):
        bands = {"Wolf": (150, 300), "Wolfsrudel (2)": (450, 700), "Höhlenbär": (250, 450), "Irrlicht + Wolf": (250, 420), "Moorhexe": (100, 300),
                 "Moorhexe + Irrlicht": (300, 600), "Schattenjäger": (250, 450), "Steinwächter": (200, 400), "Totem-Beschwörer": (200, 400)}
        for name, (lo, hi) in bands.items():
            m = cell(name, 1, "average")
            self.assertGreaterEqual(m["win"], 900, name)
            self.assertTrue(lo <= m["hp_lost"] <= hi, (name, m))

    def test_losses_do_not_grow_with_party_size(self):
        for name in FAMILIES:
            if "Boss" in name or "Alpha" in name:
                continue
            losses = [cell(name, n, "average")["hp_lost"] for n in (1, 2, 3, 4)]
            self.assertEqual(losses, sorted(losses, reverse=True), (name, losses))

    def test_skill_is_rewarded_where_abilities_can_be_answered(self):
        for name in ("Höhlenbär", "Steinwächter", "Moorhexe + Irrlicht", "Totem-Beschwörer"):
            n, a, g = (cell(name, 1, s)["hp_lost"] for s in ("novice", "average", "good"))
            self.assertGreaterEqual(n, a, name)
            self.assertGreater(a, g, name)
        self.assertGreater(cell("Höhlenbär", 1, "novice")["hp_lost"], 2 * cell("Höhlenbär", 1, "good")["hp_lost"])

    def test_elite_pack_needs_two(self):
        self.assertLessEqual(cell("Alpha + 2 Wölfe", 1, "average")["win"], 200)
        self.assertEqual(cell("Alpha + 2 Wölfe", 1, "novice")["win"], 0)
        duo = cell("Alpha + 2 Wölfe", 2, "average")
        self.assertGreaterEqual(duo["win"], 700)
        self.assertTrue(400 <= duo["hp_lost"] <= 800, duo)
        quad = cell("Alpha + 2 Wölfe", 4, "average")
        self.assertGreaterEqual(quad["win"], 900)
        self.assertLessEqual(quad["hp_lost"], 400)

    def test_the_boss_needs_a_skilled_group(self):
        name = "Steinherz-Koloss (Boss)"
        for n in (1, 2, 3, 4):
            self.assertEqual(cell(name, n, "novice")["win"], 0, n)
        for n in (1, 2, 3):
            self.assertEqual(cell(name, n, "average")["win"], 0, n)
        for n in (1, 2):
            self.assertEqual(cell(name, n, "good")["win"], 0, n)
        for n in (3, 4):
            m = cell(name, n, "good")
            self.assertEqual(m["win"], 1000, n)
            self.assertGreaterEqual(m["hp_lost"], 150, n)                           # kein Spaziergang


class ReportTests(unittest.TestCase):
    def test_the_committed_report_matches_the_current_rules(self):
        self.assertEqual(DOC.read_text(encoding="utf-8"), report(C))

    def test_cli(self):
        import tempfile
        from mmo_sim import balance
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "r.md"
            self.assertEqual(balance.main(["b", "check", str(f)]), 1)
            self.assertEqual(balance.main(["b", "write", str(f)]), 0)
            self.assertEqual(balance.main(["b", "check", str(f)]), 0)
            f.write_text(f.read_text(encoding="utf-8").replace("Wolf", "Hund", 1), encoding="utf-8")
            self.assertEqual(balance.main(["b", "check", str(f)]), 1)
            self.assertEqual(balance.main(["b"]), 2)


if __name__ == "__main__":
    unittest.main()
