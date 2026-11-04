"""Golden Test Vectors des Kampfs gegen mehrere Gegner (sprachneutral). Format: reference/golden/README.md (Abschnitt Mehrgegnerkampf).

    python -m mmo_sim.golden_pack write ../golden_pack
    python -m mmo_sim.golden_pack check ../golden_pack
"""
from __future__ import annotations

import hashlib
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from .errors import SimError
from .golden import pseudo_random_inputs
from .pack import simulate_pack, strongest
from .rules import load_sim_rules
from .server import build_report

FORMAT_VERSION = 1
RULES_FILE = "sim_rules_v5.json"
NAME = "sim_packs"


def rules_sha256() -> str:
    return hashlib.sha256(resources.files("mmo_sim").joinpath("data", RULES_FILE).read_bytes()).hexdigest()


def _p(inputs: Any, level: Any = 1, **kw: Any) -> dict[str, Any]:
    return {"level": level, "inputs": inputs, **kw}


def cases() -> list[dict[str, Any]]:
    c: list[dict[str, Any]] = []

    def add(name: str, opps: Any, players: Any) -> None:
        c.append({"name": name, "opponents": opps, "players": players})

    lights = lambda n, step=8, start=0: [[start + i * step, "light"] for i in range(n)]  # noqa: E731
    W = "wolf"
    add("solo_one_opponent", [W], [_p([[0, "light"], [10, "light"], [20, "heavy"], [50, "light"], [60, "block"], [100, "flee"]])])
    add("two_wolves_idle", [W, W], [_p([])])
    add("three_wolves_hp_scaling_party_of_two", [W, W, W], [_p([[0, "flee"]]), _p([[0, "flee"]])])
    add("focus_defaults_to_first", [W, "bear"], [_p([[0, "light"], [100, "flee"]])])
    add("target_switch", [W, "bear"], [_p([[0, "target_2"], [1, "light"], [100, "flee"]])])
    add("target_out_of_range_ignored", [W], [_p([[0, "target_3"], [1, "light"], [100, "flee"]])])
    add("target_dead_ignored", [W, "bear"], [_p(lights(10) + [[90, "target_1"], [95, "light"], [200, "flee"]], 30)])
    add("focus_falls_back_when_target_dies", [W, "bear"], [_p([[0, "target_1"]] + lights(14) + [[200, "flee"]], 30)])
    add("sweep_hits_all", [W, W, W], [_p([[0, "sweep"], [100, "flee"]])])
    add("sweep_cooldown_and_busy", [W, W], [_p([[0, "sweep"], [5, "sweep"], [14, "sweep"], [50, "sweep"], [100, "flee"]])])
    add("sweep_skips_the_fallen", [W, "bear"], [_p([[0, "target_1"]] + lights(14) + [[130, "sweep"], [200, "flee"]], 30)])
    add("sweep_counts_one_light_hit", [W, W, W], [_p([[0, "sweep"], [100, "flee"]])])
    add("sweep_needs_allowed", [W, W], [_p([[0, "sweep"], [100, "flee"]], allowed=["light", "flee"]),
                                        _p([[0, "sweep"], [100, "flee"]], allowed=["sweep", "flee"])])
    add("stun_only_focus", [W, W], [_p([[0, "target_2"], [1, "stun"], [100, "flee"]])])
    add("slow_only_focus", [W, W], [_p([[0, "slow"], [100, "flee"]])])
    add("stun_makes_only_that_one_vulnerable", [W, W], [_p([[0, "stun"], [10, "light"], [30, "target_2"], [31, "light"], [100, "flee"]])])
    add("heavy_follows_chosen_target", [W, "bear"], [_p([[0, "target_2"], [1, "heavy"], [3, "target_1"], [100, "flee"]])])
    add("heavy_and_lights_mixed", [W, "bear"], [_p([[0, "target_1"]] + lights(14, 8, 0)[:0] + [[0, "heavy"]], 30), _p(lights(3, 8, 1))])
    add("two_attackers_target_highest_threat", [W, W], [_p([[0, "light"], [100, "flee"]]), _p([[100, "flee"]])])
    add("each_opponent_attacks_on_its_own_clock", [W, "bear"], [_p([])])
    add("parry_staggers_only_that_opponent", [W, W], [_p([[39, "block"], [100, "flee"]]), _p([[48, "light"], [100, "flee"]])])
    add("heal_in_a_pack", [W, W], [_p([[0, "light"], [60, "flee"]]), _p([[41, "heal"], [60, "flee"]])])
    add("pack_victory", ["training_dummy", "training_dummy"], [_p([[0, "sweep"]] + lights(30, 8, 20))])
    add("pack_defeat", ["bear", "bear", "bear"], [_p([]), _p([])])
    add("pack_timeout", ["training_dummy", "training_dummy", "training_dummy"], [_p([])])
    add("equipment_in_a_pack", [W, W, W], [_p([[0, "sweep"]] + lights(20, 8, 20), 5, equipped=["ember_strike", "shield_wall"]), _p(lights(10), 5)])
    add("skill_ember_burns", ["bear"], [_p([[0, "cast_ember"], [100, "flee"]], 20)])
    add("skill_ember_burn_finishes_the_kill", [W], [_p([[0, "cast_ember"], [12, "light"], [60, "flee"]])])
    add("skill_ember_refresh_replaces_the_burn", [W, "bear"], [_p([[0, "cast_ember"], [80, "cast_ember"], [140, "flee"]], 20)])
    add("skill_ember_burn_stops_when_the_target_falls", [W, W], [_p([[0, "cast_ember"], [12, "sweep"], [40, "sweep"], [90, "flee"]], 20)])
    add("skill_ember_hits_the_focus", [W, "bear"], [_p([[0, "target_2"], [1, "cast_ember"], [100, "flee"]], 20)])
    add("skill_ember_counts_as_heavy_hit", [W], [_p([[0, "cast_ember"], [100, "flee"]])])
    add("skill_ember_threat_draws_the_opponent", [W], [_p([[100, "flee"]]), _p([[0, "cast_ember"], [100, "flee"]])])
    add("skill_ember_cooldown_busy_and_cost", [W, W, W], [_p([[0, "cast_ember"], [5, "cast_ember"], [12, "cast_ember"], [80, "cast_ember"], [100, "flee"]])])
    add("skill_dash_avoids_the_hit", [W], [_p([[36, "dash"], [100, "flee"]])])
    add("skill_dash_window_expires", [W], [_p([[20, "dash"], [100, "flee"]])])
    add("skill_dash_cooldown", [W], [_p([[36, "dash"], [40, "dash"], [100, "dash"], [150, "flee"]])])
    add("skill_veil_halves_damage", [W], [_p([[30, "veil"], [100, "flee"]])])
    add("skill_veil_stacks_with_block", [W], [_p([[30, "veil"], [38, "block"], [100, "flee"]])])
    add("skill_veil_ends", [W], [_p([[0, "veil"], [150, "flee"]])])
    add("skill_focus_surge_is_capped", [W], [_p([[0, "focus_surge"], [100, "flee"]])])
    add("skills_need_the_ability", [W], [_p([[0, "cast_ember"], [12, "dash"], [100, "flee"]], allowed=["light", "dash", "flee"])])
    add("skills_in_the_group", [W, W], [_p([[0, "cast_ember"], [100, "flee"]], 20), _p([[10, "veil"], [100, "flee"]], 20)])
    for seed in range(1, 9):
        opps = [("wolf", "bear", "stone_golem", "training_dummy")[(seed + k) % 4] for k in range(1 + seed % 3)]
        n = 1 + seed % 4
        specs = []
        for i in range(n):
            extra = [[3 + i, "target_2"], [30 + i, "sweep"], [70 + i, "target_1"], [120 + i, "sweep"],
                     [15 + i, "cast_ember"], [60 + i, "dash"], [100 + i, "veil"], [150 + i, "focus_surge"]]
            if i % 2:
                extra += [[5 + i, "heal"], [40 + i, "shield"]]
            ins = sorted(pseudo_random_inputs(seed * 10 + i, 160, 2500) + extra, key=lambda x: x[0])
            specs.append(_p(ins, 1 + seed * 3 + i, **({"equipped": ["power_strike", "ember_strike"]} if i == 0 else {})))
        add(f"pseudo_random_pack_{seed}", opps, specs)
    ok = _p([[0, "light"]])
    bad = {
        "invalid_no_opponents": ([], [ok]), "invalid_too_many_opponents": ([W] * 4, [ok]), "invalid_opponents_not_a_list": (W, [ok]),
        "invalid_unknown_opponent": ([W, "dragon"], [ok]), "invalid_opponent_not_a_string": ([5], [ok]),
        "invalid_empty_party": ([W], []), "invalid_too_many_players": ([W], [ok] * 5),
        "invalid_unknown_command": ([W], [_p([[0, "target_4"]])]), "invalid_allowed_unknown": ([W], [_p([], 1, allowed=["target_9"])]),
        "invalid_unsorted": ([W], [_p([[5, "sweep"], [4, "light"]])]),
        "invalid_unknown_skill": ([W], [_p([[0, "cast_nova"]])]), "invalid_allowed_unknown_skill": ([W], [_p([], 1, allowed=["cast_nova"])]),
    }
    for name, (opps, players) in bad.items():
        add(name, opps, players)
    return c


def run_case(cfg: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    out = {k: case[k] for k in ("name", "opponents", "players")}
    try:
        r = simulate_pack(cfg, case["opponents"], case["players"])
    except SimError:
        out["expect"] = "error"
        return out
    out["expect"] = "ok"
    out["result"] = {
        "outcome": r.outcome, "ticks": r.ticks, "opponent_hp": r.opponent_hp, "opponents": list(r.opponents),
        "players": [{"outcome": p.outcome, "ticks": p.ticks, "actions": p.actions, "player_hp": p.player_hp,
                     "ignored_inputs": p.ignored_inputs, "damage_ticks": list(p.damage_ticks)} for p in r.players]}
    out["reports"] = [build_report(cfg, f"golden-{case['name']}", strongest(cfg, case["opponents"]), 1, p) if p.actions else None for p in r.players]
    return out


def build_vector() -> dict[str, Any]:
    cfg = load_sim_rules(RULES_FILE)
    return {"format": FORMAT_VERSION, "name": NAME, "rules_file": RULES_FILE, "rules_sha256": rules_sha256(),
            "cases": [run_case(cfg, c) for c in cases()]}


def verify_vector(vec: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if vec.get("format") != FORMAT_VERSION:
        return [f"unbekanntes Format {vec.get('format')!r}"]
    if rules_sha256() != vec["rules_sha256"]:
        errs.append("Regeldatei hat sich geändert (SHA-256 weicht ab)")
    cfg = load_sim_rules(vec["rules_file"])
    for want in vec["cases"]:
        if run_case(cfg, want) != want:
            errs.append(f"Fall {want['name']}: Abweichung")
    return errs


def _compact(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def render(vec: dict[str, Any]) -> str:
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
