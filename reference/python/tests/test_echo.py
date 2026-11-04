"""AP 7: Kampfecho und Resonanz +0..+30 (ADR-0046)."""
import copy
import unittest

from mmo_world import persistence
from mmo_world.echo import EchoService, load_echo_rules, validate_echo_rules
from mmo_world.errors import WorldError
from mmo_world.world import World

COIN = "coin@gold"
DUST, WARD, SEAL = "resonance_dust@standard", "ward_stone@standard", "resonance_seal@standard"


def world(klass=("a", "warrior"), more=()):
    w = World("rules_v9.json")
    for c, k in (klass, *more):
        w.svc.create(c, "player")
        w.svc.record(c, "identity.class_chosen", {"base_class": k})
        w.inv.deposit(c, COIN, 10**6)
        w.inv.deposit(c, DUST, 1000)
    return w


class Rules(unittest.TestCase):
    def test_shipped_rules_valid(self):
        r = load_echo_rules()
        validate_echo_rules(r)
        self.assertEqual(len(r["success_permille"]), 30)

    def test_invalid_rules(self):
        r = load_echo_rules()
        bad = copy.deepcopy(r)
        bad["success_permille"] = bad["success_permille"][:-1]
        with self.assertRaises(WorldError):
            validate_echo_rules(bad)


class Lifecycle(unittest.TestCase):
    def test_mint_activate_class_check(self):
        w = world()
        e = w.echo.mint("wolf_tradition", "a")
        self.assertTrue(w.echo.view("a")["echoes"][0]["tradable"])
        w.echo.activate("a", e)
        v = w.echo.view("a")["echoes"][0]
        self.assertEqual((v["bound"], v["tradable"], v["resonance"]), (True, False, 0))
        x = w.echo.mint("ember_tradition", "a")
        w.svc.create("m", "player")
        w.svc.record("m", "identity.class_chosen", {"base_class": "archer"})
        w.echo.echoes[x]["owner"] = "m"
        with self.assertRaises(WorldError):
            w.echo.activate("m", x)                        # Bogenschütze kann Glut-Tradition nicht nutzen

    def test_only_owner_acts(self):
        w = world(more=(("b", "warrior"),))
        e = w.echo.mint("wolf_tradition", "a")
        for f in (lambda: w.echo.activate("b", e), lambda: w.echo.upgrade("b", e), lambda: w.echo.list_for_sale("b", e, 5)):
            with self.assertRaises(WorldError):
                f()

    def test_equip_slots_and_unique_tradition(self):
        w = world()
        ids = [w.echo.mint(d, "a") for d in ("wolf_tradition", "ember_tradition", "stone_tradition")]
        for i in ids:
            w.echo.activate("a", i)
        w.echo.equip("a", ids[0], "main")
        with self.assertRaises(WorldError):
            w.echo.equip("a", ids[1], "main")
        w.echo.equip("a", ids[1], "hybrid")
        w.echo.equip("a", ids[2], "hybrid")
        dup = w.echo.mint("stone_tradition", "a")
        w.echo.activate("a", dup)
        with self.assertRaises(WorldError):
            w.echo.equip("a", dup, "hybrid")
        w.echo.unequip("a", ids[1])
        self.assertEqual(w.echo.loadout("a")["hybrid"], [ids[2]])
        self.assertEqual(w.echo.check(), [])


class Upgrade(unittest.TestCase):
    def setUp(self):
        self.w = world()
        self.w.echo.seed = "test-seed"
        self.e = self.w.echo.mint("wolf_tradition", "a")
        self.w.echo.activate("a", self.e)

    def test_needs_activation_and_materials(self):
        w = world()
        e = w.echo.mint("wolf_tradition", "a")
        with self.assertRaises(WorldError):
            w.echo.upgrade("a", e)
        w.echo.activate("a", e)
        w.inv.apply("a", {DUST: 1000}, {})
        with self.assertRaises(WorldError):
            w.echo.upgrade("a", e)
        self.assertEqual((w.echo.echoes[e]["resonance"], w.echo.echoes[e]["attempts"], w.inv.balance("a", COIN)), (0, 0, 10**6))

    def test_atomic_costs_and_result_server_side(self):
        before = (self.w.inv.balance("a", DUST), self.w.inv.balance("a", COIN))
        r = self.w.echo.upgrade("a", self.e)
        self.assertEqual((before[0] - self.w.inv.balance("a", DUST), before[1] - self.w.inv.balance("a", COIN)), (r["cost"]["dust"], r["cost"]["coins"]))
        self.assertEqual(r["after"], self.w.echo.echoes[self.e]["resonance"])

    def test_replay_is_idempotent(self):
        a = self.w.echo.upgrade("a", self.e, request_id="r1")
        bal = self.w.inv.balance("a", DUST)
        b = self.w.echo.upgrade("a", self.e, request_id="r1")
        self.assertTrue(b["replayed"])
        self.assertEqual((a["after"], self.w.inv.balance("a", DUST), self.w.echo.echoes[self.e]["attempts"]), (b["after"], bal, 1))

    def test_never_destroyed_and_bounds_hold_over_many_attempts(self):
        w = self.w
        w.inv.deposit("a", DUST, 10**5)
        w.inv.deposit("a", COIN, 10**8)
        for i in range(400):
            try:
                w.echo.upgrade("a", self.e)
            except WorldError:
                break
            self.assertIn(self.e, w.echo.echoes)
            self.assertTrue(0 <= w.echo.echoes[self.e]["resonance"] <= 30)
        self.assertEqual(w.echo.check(), [])

    def test_drop_only_from_threshold_and_protection(self):
        w, e = self.w, self.w.echo.echoes[self.e]
        w.inv.deposit("a", DUST, 10**5)
        w.inv.deposit("a", COIN, 10**8)
        e["resonance"] = 12
        w.echo.R["success_permille"] = [0] * 30             # erzwingt Fehlschläge
        w.echo.R["pity"]["cap_permille"] = 0
        r = w.echo.upgrade("a", self.e)
        self.assertEqual((r["success"], r["after"]), (False, 11))     # Stufenverlust
        w.inv.deposit("a", WARD, 1)
        r = w.echo.upgrade("a", self.e, protect=True)
        self.assertEqual((r["success"], r["protected"], r["after"], w.inv.balance("a", WARD)), (False, True, 11, 0))
        e["resonance"] = 3                                   # unter der Schwelle: kein Verlust, Schutz bleibt ungenutzt
        w.inv.deposit("a", WARD, 1)
        r = w.echo.upgrade("a", self.e, protect=True)
        self.assertEqual((r["after"], r["protected"], w.inv.balance("a", WARD)), (3, False, 1))
        with self.assertRaises(WorldError):                  # Schutz verlangt, aber keiner da
            w.inv.apply("a", {WARD: 1}, {})
            w.echo.upgrade("a", self.e, protect=True)

    def test_pity_raises_chance_and_resets_on_success(self):
        w, e = self.w, self.w.echo.echoes[self.e]
        w.inv.deposit("a", DUST, 10**5)
        w.echo.R["success_permille"] = [0] * 30
        w.echo.upgrade("a", self.e)
        w.echo.upgrade("a", self.e)
        self.assertEqual((e["pity"], w.echo.chance(e)), (2, 2 * w.echo.R["pity"]["step_permille"]))
        w.echo.R["success_permille"] = [1000] * 30
        self.assertTrue(w.echo.upgrade("a", self.e)["success"])
        self.assertEqual(e["pity"], 0)

    def test_max_level(self):
        self.w.echo.echoes[self.e]["resonance"] = 30
        with self.assertRaises(WorldError):
            self.w.echo.upgrade("a", self.e)

    def test_outcome_deterministic_for_seed_and_not_by_client(self):
        w2 = world()
        w2.echo.seed = "test-seed"
        e2 = w2.echo.mint("wolf_tradition", "a")
        w2.echo.activate("a", e2)
        a = [self.w.echo.upgrade("a", self.e)["success"] for _ in range(8)]
        b = [w2.echo.upgrade("a", e2)["success"] for _ in range(8)]
        self.assertEqual(a, b)


class Trading(unittest.TestCase):
    def setUp(self):
        self.w = world(more=(("b", "warrior"),))
        self.e = self.w.echo.mint("wolf_tradition", "a")

    def test_unactivated_tradable_bound_not(self):
        self.w.echo.activate("a", self.e)
        with self.assertRaises(WorldError):
            self.w.echo.list_for_sale("a", self.e, 100)

    def test_seal_release_and_sale_keeps_resonance_not_mastery(self):
        w = self.w
        w.echo.activate("a", self.e)
        w.echo.equip("a", self.e, "main")
        w.echo.echoes[self.e]["resonance"] = 7
        self.assertEqual(w.echo.grant_mastery("a", 500), 60)             # Tageslimit
        self.assertEqual(w.echo.grant_mastery("a", 500), 0)
        with self.assertRaises(WorldError):
            w.echo.release("a", self.e)                                  # ausgerüstet
        w.echo.unequip("a", self.e)
        with self.assertRaises(WorldError):
            w.echo.release("a", self.e)                                  # kein Siegel
        w.inv.deposit("a", SEAL, 1)
        w.echo.release("a", self.e)
        self.assertEqual(w.inv.balance("a", SEAL), 0)
        lid = w.echo.list_for_sale("a", self.e, 1000)
        a0, b0 = w.inv.balance("a", COIN), w.inv.balance("b", COIN)
        res = w.echo.buy("b", lid)
        self.assertEqual((res["resonance"], res["fee"]), (7, 50))
        self.assertEqual((w.inv.balance("a", COIN) - a0, b0 - w.inv.balance("b", COIN)), (950, 1000))
        v = w.echo.view("b")["echoes"][0]
        self.assertEqual((v["resonance"], v["activated"], v["bound"]), (7, True, False))
        self.assertEqual(w.echo.mastery_level("b", "wolf_tradition"), 0)  # Meisterschaft bleibt bei der Verkäuferin
        self.assertEqual(w.echo.mastery["a"]["wolf_tradition"], 60)
        w.echo.activate("b", self.e)
        self.assertTrue(w.echo.upgrade("b", self.e)["after"] in (6, 7, 8))
        self.assertEqual(w.echo.check(), [])

    def test_no_double_sale_no_duplication(self):
        w = self.w
        lid = w.echo.list_for_sale("a", self.e, 10)
        with self.assertRaises(WorldError):
            w.echo.list_for_sale("a", self.e, 10)                        # nicht zweimal anbieten
        w.echo.buy("b", lid)
        with self.assertRaises(WorldError):
            w.echo.buy("b", lid)                                         # Angebot ist weg
        self.assertEqual(sum(1 for e in w.echo.echoes.values() if e["owner"] == "b"), 1)

    def test_buy_needs_coins_and_leaves_nothing_changed(self):
        w = self.w
        lid = w.echo.list_for_sale("a", self.e, 10**7)
        with self.assertRaises(WorldError):
            w.echo.buy("b", lid)
        self.assertEqual((w.echo.echoes[self.e]["owner"], lid in w.echo.listings), ("a", True))
        with self.assertRaises(WorldError):
            w.echo.buy("a", lid)
        w.echo.cancel_listing("a", lid)
        self.assertTrue(w.echo.tradable(w.echo.echoes[self.e]))


class Persistence(unittest.TestCase):
    def test_roundtrip_and_old_snapshots_unchanged(self):
        w = world()
        self.assertNotIn("echoes", w.snapshot())
        e = w.echo.mint("wolf_tradition", "a")
        w.echo.activate("a", e)
        w.echo.equip("a", e, "main")
        w.echo.upgrade("a", e, request_id="x")
        env, logs = persistence.export_world(w)
        w2 = persistence.import_world(env, logs)
        self.assertEqual(w2.echo.to_json(), w.echo.to_json())
        self.assertEqual(persistence.check_consistency(w2), [])
        self.assertEqual(w2.echo.upgrade("a", e, request_id="x")["replayed"], True)


if __name__ == "__main__":
    unittest.main()


class GameIntegration(unittest.TestCase):
    def test_first_kill_awards_once_and_materials(self):
        from mmo_game.game import GameServer
        g = GameServer()
        g.world.svc.create("anna", "player")
        r = g._echo_gains("anna", ["alpha_wolf"])
        self.assertEqual(r["echoes"], ["wolf_tradition"])
        self.assertEqual(g.world.inv.balance("anna", "resonance_dust@standard"), 6)
        r2 = g._echo_gains("anna", ["alpha_wolf"])
        self.assertNotIn("echoes", r2)                                   # nur einmal
        self.assertEqual(sum(1 for e in g.world.echo.echoes.values() if e["owner"] == "anna"), 1)
        g.world.svc.record("anna", "identity.class_chosen", {"base_class": "warrior"})
        e = next(iter(g.world.echo.echoes))
        g.world.echo.activate("anna", e)
        g.world.echo.equip("anna", e, "main")
        self.assertEqual(g._echo_gains("anna", ["wolf"])["mastery"], 10)
