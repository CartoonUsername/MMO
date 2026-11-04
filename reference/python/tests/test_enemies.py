import copy
import hashlib
import unittest
from collections import Counter

from mmo_cee.rules import load_rules
from mmo_sim import SimError, simulate_pack
from mmo_sim.enemies import ELEMENTS, KINDS, abilities_at, ability_table, effective_interval, roll_abilities, validate_enemy_rules
from mmo_sim.rules import check_compatibility, load_sim_rules, validate_sim_rules

C = load_sim_rules("sim_rules_v6.json")
C5 = load_sim_rules("sim_rules_v5.json")
R9 = load_rules("rules_v9.json")
TABLE = ability_table(C)
NEW = ["alpha_wolf", "wisp_healer", "bog_witch", "stone_warden", "shadow_hunter", "totem_caller", "stone_imp", "stone_heart_colossus"]


def bad(mutate):
    cfg = copy.deepcopy(C)
    mutate(cfg)
    with _Raises():
        validate_sim_rules(cfg)


class _Raises:
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            raise AssertionError("SimError erwartet")
        return issubclass(et, SimError)


class RulesTests(unittest.TestCase):
    def test_shipped_rules_are_valid_and_compatible(self):
        validate_sim_rules(C)
        self.assertEqual(check_compatibility(C, R9), [])
        for t in NEW:
            self.assertIn(t, C["opponents"])
        self.assertEqual(C["version"], "6")

    def test_elements_match_the_cee(self):
        cee = set(R9["elements"]["all"])
        self.assertEqual(set(ELEMENTS), cee)
        self.assertTrue(all(o.get("element", "fire") in cee for o in C["opponents"].values()))
        self.assertLessEqual(max(o["level"] for o in C["opponents"].values()), R9["combat"]["encounter"]["max_opponent_level"])

    def test_every_dangerous_ability_has_a_warning_and_an_answer(self):
        for name, a in TABLE.items():
            self.assertGreaterEqual(a["windup"], 1, name)
            self.assertTrue(a["answers"], name)
            if a["interruptible"]:
                self.assertTrue({"interrupt", "kill_caster"} & set(a["answers"]), name)
            self.assertIn(a["kind"], KINDS)

    def test_roster_covers_the_decided_families_and_all_roles(self):
        roles = {o["role"] for o in C["opponents"].values() if "role" in o}
        self.assertEqual(roles, {"swarm", "brute", "caster", "support", "guardian", "controller", "summoner", "elite", "boss"})
        self.assertEqual(C["opponents"]["wisp_healer"]["abilities"], ["mend"])

    def test_old_files_have_no_enemy_abilities_and_still_load(self):
        self.assertNotIn("enemy_abilities", C5)
        for name in ("sim_rules_v1.json", "sim_rules_v2.json", "sim_rules_v3.json", "sim_rules_v4.json", "sim_rules_v5.json"):
            load_sim_rules(name)

    def test_new_rules_do_not_change_old_fights(self):
        from mmo_sim.golden import pseudo_random_inputs
        for seed in range(1, 16):
            opp = ("wolf", "bear", "stone_golem", "training_dummy")[seed % 4]
            specs = [{"level": 5 + seed, "inputs": sorted(pseudo_random_inputs(seed * 10 + i, 120, 2500) + [[5, "sweep"]], key=lambda x: x[0])} for i in range(1 + seed % 3)]
            self.assertEqual(simulate_pack(C, [opp], specs), simulate_pack(C5, [opp], specs), seed)

    # -- Fähigkeiten -----------------------------------------------------------------------
    def test_ability_validation(self):
        ab = lambda cfg: cfg["enemy_abilities"]["abilities"]  # noqa: E731
        bad(lambda c: c["enemy_abilities"].update(answers=[]))
        bad(lambda c: c["enemy_abilities"].update(answers=["dodge", "dodge"]))
        bad(lambda c: c["enemy_abilities"].update(abilities={}))
        bad(lambda c: ab(c).update({"bad name": dict(ab(c)["heavy_slam"])}))
        bad(lambda c: ab(c)["heavy_slam"].update(kind="teleport"))
        bad(lambda c: ab(c)["heavy_slam"].update(windup=0))
        bad(lambda c: ab(c)["heavy_slam"].update(windup=True))
        bad(lambda c: ab(c)["heavy_slam"].update(cooldown=0))
        bad(lambda c: ab(c)["heavy_slam"].update(danger=-1))
        bad(lambda c: ab(c)["heavy_slam"].update(interruptible="nein"))
        bad(lambda c: ab(c)["heavy_slam"].update(answers=[]))
        bad(lambda c: ab(c)["heavy_slam"].update(answers=["dodge", "flying"]))
        bad(lambda c: ab(c)["heavy_slam"].update(answers=["dodge", "dodge"]))
        bad(lambda c: ab(c)["heavy_slam"].update(interruptible=True))                     # unterbrechbar ohne Antwort
        bad(lambda c: ab(c)["mend"].update(interruptible="ja"))                             # Typ prüfen, obwohl die Antworten passen
        bad(lambda c: c["enemy_abilities"].update(answers=c["enemy_abilities"]["answers"] + ["dodge"]))     # Doppelte im Katalog
        bad(lambda c: c["enemy_abilities"].update(answers=c["enemy_abilities"]["answers"] + [5]))
        bad(lambda c: ab(c)["heavy_slam"].update(rollable="ja"))
        bad(lambda c: ab(c)["heavy_slam"].update(group=""))
        bad(lambda c: ab(c)["heavy_slam"].update(damage_permille=0))
        bad(lambda c: ab(c)["heavy_slam"].pop("damage_permille"))
        bad(lambda c: ab(c)["ground_pound"].pop("damage_permille"))
        bad(lambda c: ab(c)["stunning_blow"].update(state="freeze"))
        bad(lambda c: ab(c)["stunning_blow"].pop("ticks"))
        bad(lambda c: ab(c)["stunning_blow"].pop("damage_permille"))
        bad(lambda c: ab(c)["burning_curse"].update(state="stun"))
        bad(lambda c: ab(c)["burning_curse"].pop("tick_damage"))
        bad(lambda c: ab(c)["burning_curse"].pop("interval"))
        bad(lambda c: ab(c)["burning_curse"].update(interruptible=False, answers=["dodge"]))
        bad(lambda c: ab(c)["stone_skin"].pop("absorb"))
        bad(lambda c: ab(c)["stone_skin"].update(breakable_by=[]))
        bad(lambda c: ab(c)["stone_skin"].update(breakable_by=["magic"]))
        bad(lambda c: ab(c)["stone_skin"].update(answers=["focus"]))                     # ohne break_shield
        bad(lambda c: ab(c)["mend"].pop("amount_permille"))
        bad(lambda c: ab(c)["howl"].update(buff="invisible"))
        bad(lambda c: ab(c)["howl"].pop("attack_interval_permille"))
        bad(lambda c: ab(c)["howl"].pop("ticks"))
        bad(lambda c: ab(c)["call_pack"].update(summon="dragon"))
        bad(lambda c: ab(c)["call_pack"].update(max_alive=1))                             # kleiner als count
        bad(lambda c: ab(c)["call_pack"].pop("count"))
        bad(lambda c: c["opponents"]["wolf"].update(abilities=["call_pack"]))             # Wölfe dürfen nicht beschwören, weil call_pack Wölfe ruft

    def test_boundary_values_are_accepted(self):
        cfg = copy.deepcopy(C)
        cfg["enemy_abilities"]["abilities"]["heavy_slam"].update(windup=1, cooldown=1, danger=0)
        validate_sim_rules(cfg)
        cfg["enemy_abilities"]["abilities"]["call_pack"].update(max_alive=2)
        validate_sim_rules(cfg)

    # -- Vorlagen ----------------------------------------------------------------------------
    def test_template_validation(self):
        o = lambda cfg, n: cfg["opponents"][n]  # noqa: E731
        bad(lambda c: o(c, "wolf").update(role="king"))
        bad(lambda c: o(c, "wolf").update(element="metal"))
        bad(lambda c: o(c, "bog_witch").update(abilities=["burning_curse", "burning_curse"]))
        bad(lambda c: o(c, "bog_witch").update(abilities=["nonsense"]))
        bad(lambda c: o(c, "bog_witch").update(abilities="burning_curse"))
        bad(lambda c: o(c, "bog_witch")["pool"].update(count=[2, 1]))
        bad(lambda c: o(c, "bog_witch")["pool"].update(count=[0, 9]))
        bad(lambda c: o(c, "bog_witch")["pool"].update(count=[-1, 1]))
        bad(lambda c: o(c, "bog_witch")["pool"]["entries"].update(ghost=1))
        bad(lambda c: o(c, "bog_witch")["pool"]["entries"].update(burning_curse=1))        # steht schon fest
        bad(lambda c: o(c, "bog_witch")["pool"]["entries"].update(crippling_bite=0))
        bad(lambda c: o(c, "bog_witch")["pool"]["entries"].update(crippling_bite=True))
        bad(lambda c: o(c, "bog_witch")["pool"]["entries"].update(call_imps=1))           # nicht würfelbar
        bad(lambda c: o(c, "bog_witch").update(danger_cap=-1))
        bad(lambda c: o(c, "training_dummy").update(danger_cap=True))
        bad(lambda c: o(c, "stone_heart_colossus")["pool"].update(entries={"crippling_bite": 1}))   # Boss: auch ein Eintrag bei Anzahl 0 ist verboten
        bad(lambda c: o(c, "bog_witch").update(danger_cap=1))                              # feste Fähigkeiten überschreiten die Grenze
        bad(lambda c: o(c, "stone_heart_colossus")["pool"].update(count=[0, 1], entries={"crippling_bite": 1}))   # Bosse werden nicht gewürfelt
        bad(lambda c: o(c, "alpha_wolf")["phases"].reverse())
        bad(lambda c: o(c, "alpha_wolf")["phases"][0].update(at_permille=1000))
        bad(lambda c: o(c, "alpha_wolf")["phases"][0].update(at_permille=0))
        bad(lambda c: o(c, "alpha_wolf")["phases"][0].update(add=["ghost"]))
        bad(lambda c: o(c, "alpha_wolf")["phases"][0].update(attack_interval_permille=99))
        bad(lambda c: o(c, "alpha_wolf")["phases"][0].update(attack_interval_permille=1001))
        bad(lambda c: o(c, "alpha_wolf")["phases"][1].update(add=["crippling_bite"]))      # doppelt
        bad(lambda c: o(c, "alpha_wolf")["phases"][1].update(add=["howl"]))                 # steht schon fest
        cfg = copy.deepcopy(C)
        cfg["opponents"]["alpha_wolf"]["phases"][0]["at_permille"] = 999
        cfg["opponents"]["alpha_wolf"]["phases"][1]["at_permille"] = 1
        validate_sim_rules(cfg)

    def test_templates_without_the_new_keys_are_ignored(self):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["plain"] = {"level": 1, "hp": 10, "attack_interval": 0, "windup": 0, "damage": 0, "stagger": 0}
        validate_sim_rules(cfg)

    def test_summoned_enemies_may_not_summon(self):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["stone_imp"]["abilities"] = ["call_pack"]
        cfg["opponents"]["stone_imp"]["danger_cap"] = 3
        with _Raises():
            validate_sim_rules(cfg)


class RollTests(unittest.TestCase):
    def test_same_input_same_result_and_known_values(self):
        self.assertEqual(roll_abilities(C, "wolf", "sp1", 1), roll_abilities(C, "wolf", "sp1", 1))
        self.assertEqual(roll_abilities(C, "wolf", "sp1", 1), ["crippling_bite"])        # Festwert: dient auch als Vektor
        self.assertEqual(roll_abilities(C, "bog_witch", "sp1", 1), ["burning_curse", "stone_skin"])
        self.assertEqual(roll_abilities(C, "alpha_wolf", "sp1", 1), ["howl"])
        self.assertEqual(roll_abilities(C, "alpha_wolf", "sp2", 1), ["howl", "heavy_slam"])

    def test_the_stream_definition_is_exactly_sha256_of_type_spawn_day(self):
        d0 = hashlib.sha256(b"wolf|sp1|1|0").digest()
        z0 = int.from_bytes(d0[:8], "big")
        count = 0 + z0 % 2                                                                # Anzahl 0..1
        z1 = int.from_bytes(d0[8:16], "big")
        picked = []
        if count:
            picked = ["crippling_bite" if z1 % 4 < 3 else "howl"]                         # Gewichte 3 und 1 in Dateireihenfolge
        self.assertEqual(roll_abilities(C, "wolf", "sp1", 1), picked)

    def test_inputs_change_the_result(self):
        results = {tuple(roll_abilities(C, "bog_witch", f"sp{i}", d)) for i in range(20) for d in range(5)}
        self.assertGreater(len(results), 6)
        by_spawn = {tuple(roll_abilities(C, "bog_witch", f"sp{i}", 1)) for i in range(30)}
        by_day = {tuple(roll_abilities(C, "bog_witch", "sp1", d)) for d in range(30)}
        self.assertGreater(len(by_spawn), 3)
        self.assertGreater(len(by_day), 3)

    def test_fixed_abilities_always_come_first_and_stay(self):
        for t, o in C["opponents"].items():
            for i in range(25):
                r = roll_abilities(C, t, f"s{i}", i)
                self.assertEqual(r[: len(o.get("abilities", []))], o.get("abilities", []), t)

    def test_rolled_abilities_respect_counts_danger_groups_and_pools(self):
        for t, o in C["opponents"].items():
            if "pool" not in o:
                continue
            lo, hi = o["pool"]["count"]
            for i in range(60):
                r = roll_abilities(C, t, f"s{i}", i % 7)
                extra = r[len(o["abilities"]):]
                self.assertTrue(lo >= 0 and len(extra) <= hi, (t, r))
                self.assertEqual(len(set(r)), len(r), (t, r))
                self.assertTrue(set(extra) <= set(o["pool"]["entries"]), (t, r))
                self.assertLessEqual(sum(TABLE[a]["danger"] for a in r), o["danger_cap"], (t, r))
                groups = [TABLE[a]["group"] for a in extra if TABLE[a].get("group")]
                fixed_groups = {TABLE[a]["group"] for a in o["abilities"] if TABLE[a].get("group")}
                self.assertEqual(len(groups), len(set(groups)), (t, r))
                self.assertFalse(set(groups) & fixed_groups, (t, r))

    def test_counts_and_weights_follow_the_pool(self):
        counts = Counter(len(roll_abilities(C, "bog_witch", f"s{i}", 1)) - 1 for i in range(600))
        self.assertEqual(set(counts), {0, 1, 2})
        for n in (0, 1, 2):
            self.assertGreater(counts[n], 120)                                              # grob gleichverteilt über 0..2
        first = Counter(roll_abilities(C, "wolf", f"s{i}", 3)[0:1][0] for i in range(900) if roll_abilities(C, "wolf", f"s{i}", 3))
        self.assertGreater(first["crippling_bite"], 2 * first["howl"])                      # Gewicht 3 gegen 1

    def test_danger_cap_blocks_expensive_additions(self):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["bog_witch"]["danger_cap"] = 2                                     # genau die feste Fähigkeit (danger 2)
        validate_sim_rules(cfg)
        for i in range(40):
            self.assertEqual(roll_abilities(cfg, "bog_witch", f"s{i}", 1), ["burning_curse"])
        cfg["opponents"]["bog_witch"]["danger_cap"] = 3                                     # eine billige Zusatzfähigkeit (danger 1) passt noch
        validate_sim_rules(cfg)
        sizes = {len(roll_abilities(cfg, "bog_witch", f"s{i}", 1)) for i in range(80)}
        self.assertEqual(sizes, {1, 2})
        for i in range(80):
            r = roll_abilities(cfg, "bog_witch", f"s{i}", 1)
            self.assertTrue(len(r) == 1 or r[1] == "crippling_bite")

    def test_the_running_danger_total_limits_multiple_picks(self):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["bog_witch"]["pool"]["count"] = [3, 3]
        cfg["opponents"]["bog_witch"]["danger_cap"] = 5                                     # fest 2; Rest 3 von (1, 2, 2)
        validate_sim_rules(cfg)
        totals = Counter()
        for i in range(120):
            r = roll_abilities(cfg, "bog_witch", f"s{i}", 1)
            total = sum(TABLE[a]["danger"] for a in r)
            self.assertLessEqual(total, 5, r)
            totals[total] += 1
        self.assertGreater(totals[5], 0)                                                    # die Grenze wird auch ausgeschöpft

    def test_groups_exclude_each_other_when_rolled(self):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["shadow_hunter"].update(abilities=[], pool={"count": [2, 2], "entries": {"heavy_slam": 1, "stunning_blow": 1, "crippling_bite": 1}}, danger_cap=9)
        validate_sim_rules(cfg)
        for i in range(60):
            r = roll_abilities(cfg, "shadow_hunter", f"s{i}", 1)
            self.assertEqual(len(r), 2)
            self.assertLessEqual(sum(1 for a in r if a in ("heavy_slam", "stunning_blow")), 1, r)

    def test_a_fixed_group_member_blocks_the_rest_of_its_group(self):
        r = [roll_abilities(C, "shadow_hunter", f"s{i}", 1) for i in range(80)]
        self.assertTrue(all("heavy_slam" not in x for x in r))                              # stunning_blow (burst) ist fest

    def test_bosses_and_summons_are_not_rolled(self):
        for i in range(20):
            self.assertEqual(roll_abilities(C, "stone_heart_colossus", f"s{i}", i), ["heavy_slam", "ground_pound"])
            self.assertEqual(roll_abilities(C, "stone_imp", f"s{i}", i), [])

    def test_templates_without_a_pool_return_their_fixed_abilities(self):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["plain"] = {"level": 1, "hp": 10, "attack_interval": 0, "windup": 0, "damage": 0, "stagger": 0}
        self.assertEqual(roll_abilities(cfg, "plain", "sp", 1), [])

    def test_invalid_inputs(self):
        for args in (("dragon", "sp1", 1), (None, "sp1", 1), ("wolf", "", 1), ("wolf", 5, 1), ("wolf", None, 1), ("wolf", "sp1", -1),
                     ("wolf", "sp1", True), ("wolf", "sp1", 1.0), ("wolf", "sp1", "1")):
            with self.assertRaises(SimError, msg=str(args)):
                roll_abilities(C, *args)
        roll_abilities(C, "wolf", "sp1", 0)

    def test_exhausted_pools_stop_without_error(self):
        cfg = copy.deepcopy(C)
        cfg["opponents"]["wolf"]["pool"] = {"count": [2, 2], "entries": {"crippling_bite": 1, "howl": 1}}
        for i in range(20):
            self.assertEqual(sorted(roll_abilities(cfg, "wolf", f"s{i}", 1)), ["crippling_bite", "howl"])

    def test_unicode_spawn_ids_are_hashed_as_utf8(self):
        self.assertEqual(roll_abilities(C, "bog_witch", "Ä", 1), roll_abilities(C, "bog_witch", "Ä", 1))
        self.assertNotEqual({tuple(roll_abilities(C, "bog_witch", s, 1)) for s in ("Ä", "A", "Ae")}, {()})


class CycleFloorTests(unittest.TestCase):
    def test_every_template_respects_the_floor_and_the_cee_rates(self):
        floor = C["enemy_abilities"]["min_attack_cycle"]
        for t, o in C["opponents"].items():
            if o["attack_interval"] > 0:
                self.assertGreaterEqual(o["attack_interval"] + o["windup"], floor, t)
        self.assertEqual(check_compatibility(C, R9), [])

    def test_floor_validation(self):
        bad(lambda c: c["enemy_abilities"].update(min_attack_cycle=0))
        bad(lambda c: c["enemy_abilities"].update(min_attack_cycle=True))
        bad(lambda c: c["enemy_abilities"].pop("min_attack_cycle"))
        bad(lambda c: c["opponents"]["shadow_hunter"].update(attack_interval=35))                  # 35 + 4 = 39 < 40
        cfg = copy.deepcopy(C)
        cfg["opponents"]["shadow_hunter"]["attack_interval"] = 36                                   # 36 + 4 = 40: erlaubt
        validate_sim_rules(cfg)
        cfg["opponents"]["training_dummy"]["attack_interval"] = 0                                   # ohne Angriff: kein Boden
        validate_sim_rules(cfg)

    def test_effective_interval_never_goes_below_the_floor(self):
        self.assertEqual(effective_interval(C, "alpha_wolf", 1000), 35)
        self.assertEqual(effective_interval(C, "alpha_wolf", 850), 35)                              # 29 < 35: Boden
        self.assertEqual(effective_interval(C, "alpha_wolf", 700), 35)                              # 24 -> Boden 40 - 5
        self.assertEqual(effective_interval(C, "stone_heart_colossus", 650), 60 * 650 // 1000)     # 39 >= 24: bleibt
        self.assertEqual(effective_interval(C, "stone_heart_colossus", 1000), 60)
        self.assertEqual(effective_interval(C, "bear", 500), max(45 * 500 // 1000, 40 - 8))


class PhaseTests(unittest.TestCase):
    def test_phases_trigger_below_the_threshold_and_accumulate(self):
        base = ["howl"]
        self.assertEqual(abilities_at(C, "alpha_wolf", base, 1000), (["howl"], 1000))
        self.assertEqual(abilities_at(C, "alpha_wolf", base, 600), (["howl"], 1000))                   # genau auf der Schwelle: noch nicht
        self.assertEqual(abilities_at(C, "alpha_wolf", base, 599), (["howl", "crippling_bite"], 850))
        self.assertEqual(abilities_at(C, "alpha_wolf", base, 250), (["howl", "crippling_bite"], 850))
        self.assertEqual(abilities_at(C, "alpha_wolf", base, 249), (["howl", "crippling_bite", "call_pack"], 700))
        self.assertEqual(abilities_at(C, "alpha_wolf", base, 0), (["howl", "crippling_bite", "call_pack"], 700))

    def test_boss_has_three_phases(self):
        b = ["heavy_slam", "ground_pound"]
        self.assertEqual(abilities_at(C, "stone_heart_colossus", b, 699)[0], b + ["stone_skin"])
        self.assertEqual(abilities_at(C, "stone_heart_colossus", b, 399)[0], b + ["stone_skin", "call_imps"])
        a, f = abilities_at(C, "stone_heart_colossus", b, 249)
        self.assertEqual((a, f), (b + ["stone_skin", "call_imps", "stunning_blow"], 650))

    def test_base_is_not_modified_and_phaseless_templates_pass_through(self):
        base = ["howl"]
        abilities_at(C, "alpha_wolf", base, 100)
        self.assertEqual(base, ["howl"])
        self.assertEqual(abilities_at(C, "wolf", ["x"], 10), (["x"], 1000))

    def test_an_ability_already_present_is_not_added_twice(self):
        out, _ = abilities_at(C, "alpha_wolf", ["howl", "crippling_bite"], 100)
        self.assertEqual(out.count("crippling_bite"), 1)


if __name__ == "__main__":
    unittest.main()
