"""AP 23: Bereichswirkung der Kombinationszauber (sim_rules_v12, game_rules_v15, ADR-0062)."""
import unittest

from mmo_sim import SimError, simulate_pack
from mmo_sim.rules import load_sim_rules, validate_sim_rules

V11 = load_sim_rules("sim_rules_v11.json")
V12 = load_sim_rules("sim_rules_v12.json")


def hp_after(cfg, inputs, enemy="wolf"):
    r = simulate_pack(cfg, [enemy], [{"level": 1, "inputs": inputs}])
    return r


class Riders(unittest.TestCase):
    def test_rules_valid_v11_untouched(self):
        validate_sim_rules(V12)
        self.assertFalse(any("riders" in s for s in V11["skills"].values() if isinstance(s, dict)))

    def test_riders_follow_domains(self):
        sk = V12["skills"]
        self.assertEqual(sk["combo_fire_water"]["riders"], {"slow_ticks": 60, "stamina": 15})      # water: Beistand+Kontrolle
        self.assertNotIn("riders", sk["combo_fire_shadow"])                                         # Entladung/Zerrung/Beschwörung/Bewegung
        self.assertEqual(set(sk["combo_ice_light"]["riders"]), {"slow_ticks", "mitigate", "stamina"})

    def test_control_rider_slows_enemy(self):
        # Wolf (Natur): beide Zauber gleich stark gegen ihn; die Verlangsamung verzögert seine Treffer -> weniger Schaden am Spieler
        a = hp_after(V11, [[0, "combo_electric_fire"], [200, "flee"]])
        b = hp_after(V12, [[0, "combo_electric_fire"], [200, "flee"]])
        self.assertEqual(a.opponent_hp, b.opponent_hp)
        self.assertEqual(a.players[0].damage_ticks, (40, 80, 120, 160))
        self.assertEqual(b.players[0].damage_ticks, (40, 97, 137, 177))      # Verlangsamung verzögert die Folgetreffer

    def test_stamina_rider_refunds(self):
        # combo_light_water kostet 45, gibt 15 zurück; 2 Zauber im Abstand der Abklingzeit sind sicher möglich
        r = hp_after(V12, [[0, "combo_light_water"], [120, "combo_light_water"], [130, "flee"]], "bear")
        self.assertLess(r.opponent_hp, V12["opponents"]["bear"]["hp"] - 2 * 200)

    def test_mobility_rider_evades_a_hit(self):                       # AP 25
        V13 = load_sim_rules("sim_rules_v13.json")
        V14 = load_sim_rules("sim_rules_v14.json")
        self.assertEqual(V14["skills"]["combo_fire_wind"]["riders"], {"slow_ticks": 60, "evade_ticks": 8})
        self.assertNotIn("evade_ticks", V14["skills"]["combo_earth_fire"].get("riders", {}))
        self.assertNotIn("evade_ticks", V13["skills"]["combo_fire_wind"].get("riders", {}))
        run = lambda c, cmd: simulate_pack(c, ["wolf"], [{"level": 1, "inputs": [[35, cmd], [60, "flee"]]}]).players[0]
        self.assertEqual(run(V13, "combo_fire_wind").damage_ticks, (40,))              # Treffer in v13
        self.assertEqual(run(V14, "combo_fire_wind").damage_ticks, ())                 # in v14 ausgewichen
        self.assertEqual(run(V14, "combo_earth_fire").damage_ticks, (40,))             # ohne Bewegungsbereich nicht
        bad = {**V14, "skills": {**V14["skills"], "combo_fire_wind": {**V14["skills"]["combo_fire_wind"], "riders": {"evade_ticks": 0}}}}
        with self.assertRaises(SimError):
            validate_sim_rules(bad)

    def test_invalid_riders_rejected(self):
        base = V12["skills"]["combo_fire_water"]
        for bad in ({"slow_ticks": 0}, {"slow_ticks": True}, {"x": 1}, {"mitigate": {"ticks": 5, "damage_permille": 1500}}, "slow"):
            cfg = {**V12, "skills": {**V12["skills"], "combo_fire_water": {**base, "riders": bad}}}
            with self.assertRaises(SimError, msg=str(bad)):
                validate_sim_rules(cfg)
        single = {**V12, "skills": {**V12["skills"], "cast_water": {**V12["skills"]["cast_water"], "riders": {"slow_ticks": 5}}}}
        with self.assertRaises(SimError):
            validate_sim_rules(single)


if __name__ == "__main__":
    unittest.main()
