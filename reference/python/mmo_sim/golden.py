"""Golden Test Vectors der Kampfsimulation (sprachneutral, für spätere Portierung).

Ein Fall = Gegner + Spielerstufe + Eingaben -> erwartetes Ergebnis (oder erwarteter Fehler) und der
daraus entstehende CEE-Bericht. Format-Beschreibung: reference/golden/README.md (Abschnitt Simulation).

    python -m mmo_sim.golden write ../golden_sim
    python -m mmo_sim.golden check ../golden_sim
"""
from __future__ import annotations

import hashlib
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from .errors import SimError
from .fight import simulate
from .rules import COMMANDS, load_sim_rules
from .server import build_report

FORMAT_VERSION = 1
RULES_FILE = "sim_rules_v1.json"
NAME = "sim_fights"


EXTRA_RULES = "sim_rules_v2.json"  # Regeln mit Fähigkeitswirkung (ADR-0021); Fälle nennen sie über `rules_file`


def rules_sha256(name: str = RULES_FILE) -> str:
    return hashlib.sha256(resources.files("mmo_sim").joinpath("data", name).read_bytes()).hexdigest()


def lights(n: int, step: int = 8, start: int = 0) -> list[list[Any]]:
    return [[start + i * step, "light"] for i in range(n)]


def pseudo_random_inputs(seed: int, n: int, max_tick: int) -> list[list[Any]]:
    """Fester LCG (ganzzahlig, portierbar): x' = (1103515245*x + 12345) mod 2^31."""
    x, t, out = seed, 0, []
    for _ in range(n):
        x = (1103515245 * x + 12345) % 2**31
        t += x % 4
        x = (1103515245 * x + 12345) % 2**31
        out.append([t, COMMANDS[x % 6]])  # Befehle 0..5, ohne "flee"
    return [i for i in out if i[0] < max_tick]


def cases() -> list[dict[str, Any]]:
    cfg = load_sim_rules()
    mt = cfg["max_ticks"]
    c: list[dict[str, Any]] = []

    def add(name: str, opp: str, level: int, inputs: Any, allowed: Any = None, equipped: Any = None, rules: str | None = None) -> None:
        case = {"name": name, "opponent_type": opp, "player_level": level, "inputs": inputs}
        if allowed is not None:  # Kampfausrüstung der Figur (ab CEE-Regeln v9); ohne: alle Befehle erlaubt
            case["allowed"] = allowed
        if equipped is not None:  # ausgerüstete Fähigkeiten; ihre Wirkung steht in den Regeln `rules_file`
            case["equipped"] = equipped
        if rules is not None:
            case["rules_file"] = rules
        c.append(case)

    for opp in cfg["opponents"]:
        add(f"idle_{opp}", opp, 1, [])
    add("lights_kill_dummy", "training_dummy", 1, lights(20))
    add("lights_spam_every_tick", "training_dummy", 1, [[t, "light"] for t in range(200)])
    add("heavy_chain_wolf", "wolf", 1, [[0, "heavy"], [20, "heavy"], [40, "heavy"]])
    for start in range(34, 43):
        add(f"dodge_at_{start}", "wolf", 1, [[start, "dodge"], [100, "flee"]])
    for start in range(34, 43):
        add(f"block_at_{start}", "wolf", 1, [[start, "block"], [100, "flee"]])
    add("parry_then_precise", "wolf", 1, [[39, "block"], [48, "light"], [100, "flee"]])
    add("parry_then_late_light", "wolf", 1, [[39, "block"], [60, "light"], [100, "flee"]])
    add("stun_cancels_attack", "wolf", 1, [[38, "stun"], [46, "light"], [200, "flee"]])
    add("slow_delays_attack", "wolf", 1, [[10, "slow"], [300, "flee"]])
    add("no_slow_baseline", "wolf", 1, [[0, "light"], [300, "flee"]])
    add("flee_immediately", "bear", 1, [[0, "flee"]])
    add("flee_after_actions", "bear", 5, [[0, "light"], [10, "stun"], [30, "flee"]])
    add("timeout_vs_dummy", "training_dummy", 1, [])
    add("level_scales_hp_low", "bear", 1, [])
    add("level_scales_hp_high", "bear", 30, [])
    add("dodge_every_cycle_bear", "bear", 12, [[t, "dodge"] for t in range(50, 600, 53)] + [[700, "flee"]])
    add("golem_hit_and_run", "stone_golem", 20, [[0, "heavy"], [20, "heavy"], [45, "dodge"], [66, "heavy"], [200, "flee"]])
    # Ausdauerdruck: Rotation Ausweichen -> Block -> Schwerer Angriff verlangt mehr Ausdauer als regeneriert wird;
    # die Zahl ignorierter Befehle ändert sich, wenn die Ausdauerprüfung fehlt.
    rotation = [[7 * (3 * k + j), cmd] for k in range(40) for j, cmd in enumerate(("dodge", "block", "heavy"))]
    add("stamina_pressure_golem", "stone_golem", 100, rotation)
    for opp in ("wolf", "bear", "stone_golem"):
        add(f"spam_all_commands_{opp}", opp, 1, [[t, cmd] for t in range(0, 120) for cmd in COMMANDS if cmd != "flee"])
    for seed in (1, 2, 3, 4, 5, 6, 7, 8):
        opp = list(cfg["opponents"])[seed % 4]
        add(f"pseudo_random_{seed}", opp, 1 + seed * 4, pseudo_random_inputs(seed, 120, mt))
    # Ungültige Eingaben (erwartet: Fehler, nichts wird simuliert)
    bad = {
        "invalid_not_a_list": ("wolf", 1, "light"),
        "invalid_item_shape": ("wolf", 1, [[0]]),
        "invalid_negative_tick": ("wolf", 1, [[-1, "light"]]),
        "invalid_float_tick": ("wolf", 1, [[1.5, "light"]]),
        "invalid_bool_tick": ("wolf", 1, [[True, "light"]]),
        "invalid_string_tick": ("wolf", 1, [["0", "light"]]),
        "invalid_tick_too_large": ("wolf", 1, [[mt, "light"]]),
        "invalid_unsorted": ("wolf", 1, [[5, "light"], [4, "light"]]),
        "invalid_command": ("wolf", 1, [[0, "fireball"]]),
        "invalid_too_many_inputs": ("wolf", 1, [[0, "light"]] * (cfg["max_inputs"] + 1)),
        "invalid_opponent": ("dragon", 1, []),
        "invalid_level_zero": ("wolf", 0, []),
        "invalid_level_float": ("wolf", 1.5, []),
    }
    for name, (opp, lvl, inputs) in bad.items():
        add(name, opp, lvl, inputs)
    # Befehlsfreigabe durch ausgerüstete Fähigkeiten: nicht erlaubte Befehle zählen als ignoriert (flee geht immer)
    base = ["light", "dodge", "block", "flee"]
    mixed = [[0, "heavy"], [20, "heavy"], [40, "stun"], [50, "slow"], [60, "light"], [70, "dodge"], [90, "block"], [200, "flee"]]
    add("allowed_base_only_wolf", "wolf", 1, mixed, base)
    add("allowed_all_wolf", "wolf", 1, mixed, list(COMMANDS))
    add("allowed_heavy_only_dummy", "training_dummy", 1, [[0, "heavy"], [20, "heavy"], [40, "stun"], [60, "heavy"]], base + ["heavy"])
    add("allowed_stun_cancels_attack", "wolf", 1, [[38, "stun"], [46, "light"], [200, "flee"]], base + ["stun"])
    add("allowed_without_stun_attack_lands", "wolf", 1, [[38, "stun"], [46, "light"], [200, "flee"]], base)
    add("allowed_empty_means_nothing_but_flee", "wolf", 1, [[0, "light"], [10, "flee"]], [])
    add("allowed_flee_cannot_be_withheld", "bear", 1, [[0, "flee"]], ["light"])
    add("allowed_spam_golem", "stone_golem", 20, [[t, cmd] for t in range(0, 60) for cmd in COMMANDS if cmd != "flee"], base + ["slow"])
    add("invalid_allowed_unknown_command", "wolf", 1, [[0, "light"]], ["fireball"])
    add("invalid_allowed_not_a_list", "wolf", 1, [[0, "light"]], "light")
    # Wirkung ausgerüsteter Fähigkeiten (sim_rules_v2): je Wirkung ein Vergleich ohne/mit Fähigkeit
    v2 = EXTRA_RULES
    light_run = [[0, "light"], [10, "light"], [20, "light"], [30, "light"], [200, "flee"]]
    hit_and_block = [[34, "block"], [50, "flee"]]
    add("fx_baseline_lights_dummy", "training_dummy", 1, light_run, None, [], v2)
    add("fx_ember_strike_lights_dummy", "training_dummy", 1, light_run, None, ["ember_strike"], v2)
    add("fx_power_strike_heavy_dummy", "training_dummy", 1, [[0, "heavy"], [40, "heavy"], [100, "flee"]], None, ["power_strike"], v2)
    add("fx_shield_wall_block_wolf", "wolf", 1, hit_and_block, None, ["shield_wall"], v2)
    add("fx_no_shield_block_wolf", "wolf", 1, hit_and_block, None, [], v2)
    add("fx_riposte_parry_then_late_light", "wolf", 1, [[39, "block"], [52, "light"], [100, "flee"]], None, ["riposte"], v2)
    add("fx_no_riposte_parry_then_late_light", "wolf", 1, [[39, "block"], [52, "light"], [100, "flee"]], None, [], v2)
    add("fx_flowing_step_dodge_chain", "bear", 12, [[t, "dodge"] for t in range(50, 400, 14)] + [[500, "flee"]], None, ["flowing_step"], v2)
    add("fx_no_flowing_step_dodge_chain", "bear", 12, [[t, "dodge"] for t in range(50, 400, 14)] + [[500, "flee"]], None, [], v2)
    add("fx_disrupting_blow_stun_wolf", "wolf", 1, [[38, "stun"], [95, "flee"]], None, ["disrupting_blow"], v2)
    add("fx_no_disrupting_blow_stun_wolf", "wolf", 1, [[38, "stun"], [95, "flee"]], None, [], v2)
    add("fx_hindering_mark_slow_wolf", "wolf", 1, [[0, "slow"], [87, "flee"]], None, ["hindering_mark"], v2)
    add("fx_no_hindering_mark_slow_wolf", "wolf", 1, [[0, "slow"], [87, "flee"]], None, [], v2)
    add("fx_veteran_focus_stamina_rotation", "stone_golem", 100, rotation, None, ["veteran_focus"], v2)
    add("fx_no_veteran_focus_stamina_rotation", "stone_golem", 100, rotation, None, [], v2)
    add("fx_twilight_veil_takes_less_damage", "bear", 1, [[300, "flee"]], None, ["twilight_veil"], v2)
    add("fx_no_twilight_veil_takes_full_damage", "bear", 1, [[300, "flee"]], None, [], v2)
    add("fx_all_stacked_golem", "stone_golem", 20, [[t, cmd] for t in range(0, 80) for cmd in COMMANDS if cmd != "flee"], None,
        ["power_strike", "disrupting_blow", "hindering_mark", "shield_wall", "riposte", "flowing_step", "ember_strike", "veteran_focus", "twilight_veil"], v2)
    add("fx_no_effect_entries_ally_mend", "wolf", 1, light_run, None, ["ally_mend", "ally_ward"], v2)
    add("fx_effects_ignored_without_rules_table", "training_dummy", 1, light_run, None, ["ember_strike"])  # sim_rules_v1: keine Wirkung
    add("fx_with_allowed_and_equipped", "wolf", 1, [[0, "heavy"], [20, "stun"], [40, "light"], [200, "flee"]],
        ["light", "dodge", "block", "flee", "heavy"], ["power_strike", "disrupting_blow"], v2)
    add("invalid_equipped_not_a_list", "wolf", 1, [[0, "light"]], None, "ember_strike", v2)
    add("invalid_equipped_duplicate", "wolf", 1, [[0, "light"]], None, ["ember_strike", "ember_strike"], v2)
    add("invalid_equipped_not_strings", "wolf", 1, [[0, "light"]], None, [5], v2)
    return c


def run_case(cfgs: dict[str, dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    out = {k: case[k] for k in ("name", "opponent_type", "player_level", "inputs", "allowed", "equipped", "rules_file") if k in case}
    cfg = cfgs[case.get("rules_file", RULES_FILE)]
    try:
        r = simulate(cfg, case["opponent_type"], case["player_level"], case["inputs"], case.get("allowed"), case.get("equipped"))
    except SimError:
        out["expect"] = "error"
        return out
    out["expect"] = "ok"
    out["result"] = {"outcome": r.outcome, "ticks": r.ticks, "actions": r.actions, "player_hp": r.player_hp,
                     "opponent_hp": r.opponent_hp, "ignored_inputs": r.ignored_inputs,
                     "damage_ticks": list(r.damage_ticks)}
    out["report"] = build_report(cfg, f"golden-{case['name']}", case["opponent_type"], 1, r) if r.actions else None
    return out


def _cfgs() -> dict[str, dict[str, Any]]:
    return {f: load_sim_rules(f) for f in (RULES_FILE, EXTRA_RULES)}


def build_vector() -> dict[str, Any]:
    cfgs = _cfgs()
    return {"format": FORMAT_VERSION, "name": NAME, "rules_file": RULES_FILE, "rules_sha256": rules_sha256(),
            "extra_rules": {EXTRA_RULES: rules_sha256(EXTRA_RULES)}, "cases": [run_case(cfgs, c) for c in cases()]}


def verify_vector(vec: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if vec.get("format") != FORMAT_VERSION:
        return [f"unbekanntes Format {vec.get('format')!r}"]
    if rules_sha256() != vec["rules_sha256"]:
        errs.append("Regeldatei hat sich geändert (SHA-256 weicht ab)")
    for f, h in vec.get("extra_rules", {}).items():
        if rules_sha256(f) != h:
            errs.append(f"Regeldatei {f} hat sich geändert (SHA-256 weicht ab)")
    cfgs = {f: load_sim_rules(f) for f in (vec["rules_file"], *vec.get("extra_rules", {}))}
    for want in vec["cases"]:
        got = run_case(cfgs, want)
        if got != want:
            errs.append(f"Fall {want['name']}: Abweichung")
    return errs


def _compact(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def render(vec: dict[str, Any]) -> str:
    """Kopfdaten und je ein Fall pro Zeile (kompakt, diff-freundlich)."""
    head = {k: v for k, v in vec.items() if k != "cases"}
    lines = [_compact(head)[:-1] + ',"cases":[']
    lines += [_compact(c) + ("," if i < len(vec["cases"]) - 1 else "") for i, c in enumerate(vec["cases"])]
    lines.append("]}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("write", "check"):
        print(__doc__)
        return 2
    mode, out = argv[1], Path(argv[2])
    path, text = out / f"{NAME}.json", render(build_vector())
    if mode == "write":
        out.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"geschrieben: {path}")
        return 0
    if not path.exists():
        print(f"FEHLT: {path}")
        return 1
    if path.read_text(encoding="utf-8") != text:
        print(f"ABWEICHUNG: {path}")
        return 1
    print(f"ok: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
