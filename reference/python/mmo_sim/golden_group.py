"""Golden Test Vectors des Gruppenkampfs (sprachneutral). Format: reference/golden/README.md (Abschnitt Gruppenkampf).

    python -m mmo_sim.golden_group write ../golden_group
    python -m mmo_sim.golden_group check ../golden_group
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
from .group import simulate_group
from .rules import load_sim_rules
from .server import build_report

FORMAT_VERSION = 1
RULES_FILE = "sim_rules_v3.json"
NAME = "sim_groups"


def rules_sha256() -> str:
    return hashlib.sha256(resources.files("mmo_sim").joinpath("data", RULES_FILE).read_bytes()).hexdigest()


def _p(inputs: Any, level: Any = 1, **kw: Any) -> dict[str, Any]:
    return {"level": level, "inputs": inputs, **kw}


def cases() -> list[dict[str, Any]]:
    c: list[dict[str, Any]] = []

    def add(name: str, opp: str, players: Any) -> None:
        c.append({"name": name, "opponent_type": opp, "players": players})

    lights = lambda n, step=8, start=0: [[start + i * step, "light"] for i in range(n)]  # noqa: E731
    for n in (1, 2, 3, 4):
        add(f"hp_scaling_{n}_players", "wolf", [_p([[0, "flee"]]) for _ in range(n)])
    add("target_highest_threat_first", "wolf", [_p([[0, "light"], [60, "flee"]]), _p([[60, "flee"]])])
    add("target_highest_threat_second", "wolf", [_p([[60, "flee"]]), _p([[0, "light"], [60, "flee"]])])
    add("target_tie_lowest_index", "wolf", [_p([[60, "flee"]]), _p([[60, "flee"]])])
    add("retarget_when_target_fled", "wolf", [_p([[0, "light"], [38, "flee"]]), _p([[60, "flee"]])])
    add("dodge_counts_for_the_target_only", "wolf", [_p([[0, "light"], [37, "dodge"], [100, "flee"]]), _p([[37, "dodge"], [100, "flee"]])])
    add("parry_staggers_for_everyone", "wolf", [_p([[39, "block"], [100, "flee"]]), _p([[48, "light"], [100, "flee"]])])
    add("stun_makes_everyone_vulnerable", "wolf", [_p([[38, "stun"], [100, "flee"]]), _p([[46, "light"], [100, "flee"]])])
    add("heal_after_hit", "wolf", [_p([[0, "light"], [60, "flee"]]), _p([[41, "heal"], [60, "flee"]])])
    add("heal_capped_at_maximum", "bear", [_p([[0, "light"], [70, "flee"]]), _p([[60, "heal"], [70, "flee"]])])
    add("heal_nobody_hurt_is_ignored", "wolf", [_p([[0, "light"], [30, "flee"]]), _p([[10, "heal"], [11, "heal"], [30, "flee"]])])
    add("heal_alone_is_ignored", "wolf", [_p([[10, "heal"], [20, "flee"]])])
    add("heal_lowest_share_first", "stone_golem", [_p([[0, "light"], [400, "flee"]], 100), _p([[70, "heavy"], [400, "flee"]], 1),
                                                    _p([[130, "heal"], [400, "flee"]], 30)])
    add("heal_tie_goes_to_lowest_index", "stone_golem", [_p([[0, "light"], [400, "flee"]], 30), _p([[70, "heavy"], [400, "flee"]], 30),
                                                          _p([[130, "heal"], [400, "flee"]], 30)])
    add("heal_cooldown_and_busy", "bear", [_p([[0, "light"], [300, "flee"]]), _p([[60, "heal"], [61, "heal"], [75, "heal"], [101, "heal"], [300, "flee"]])])
    add("heal_threat_draws_the_opponent", "bear", [_p([[0, "light"], [300, "flee"]]), _p([[60, "heal"], [300, "flee"]]), _p([[300, "flee"]])])
    add("shield_absorbs_the_first_hit", "wolf", [_p([[0, "light"], [60, "flee"]]), _p([[20, "shield"], [60, "flee"]])])
    add("shield_partially_absorbs", "stone_golem", [_p([[0, "light"], [100, "flee"]], 30), _p([[30, "shield"], [100, "flee"]])])
    add("shield_expires", "wolf", [_p([[0, "light"], [200, "flee"]]), _p([[1, "shield"], [200, "flee"]])])
    add("shield_not_stacked", "wolf", [_p([[0, "light"], [200, "flee"]]), _p([[5, "shield"], [20, "shield"], [200, "flee"]])])
    add("shield_again_after_expiry", "wolf", [_p([[0, "light"], [200, "flee"]]), _p([[5, "shield"], [60, "shield"], [200, "flee"]])])
    add("shield_alone_is_ignored", "wolf", [_p([[5, "shield"], [20, "flee"]])])
    add("support_blocked_by_allowed", "wolf", [_p([[0, "light"], [60, "flee"]]), _p([[41, "heal"], [60, "flee"]], allowed=["light", "dodge", "block", "flee"])])
    add("support_allowed_explicitly", "wolf", [_p([[0, "light"], [60, "flee"]]), _p([[41, "heal"], [60, "flee"]], allowed=["heal", "flee"])])
    add("victory_shared_one_fled", "training_dummy", [_p(lights(60)), _p([[10, "flee"]])])
    add("all_fled", "training_dummy", [_p([[5, "flee"]]), _p([[9, "flee"]])])
    add("timeout_nobody_acts", "training_dummy", [_p([]), _p([])])
    add("everyone_defeated", "bear", [_p([]), _p([])])
    add("one_fled_one_defeated", "bear", [_p([[30, "flee"]]), _p([])])
    add("fallen_player_stops_acting", "stone_golem", [_p(lights(75), 1), _p([[400, "flee"]], 100)])
    add("flee_forfeits_pending_heavy", "training_dummy", [_p([[0, "heavy"], [6, "flee"]]), _p([[100, "flee"]])])
    add("equipment_applies_per_player", "bear", [_p(lights(30), 5, equipped=["ember_strike"]), _p(lights(30), 5), _p([[50, "block"], [300, "flee"]], 5, equipped=["shield_wall"])])
    add("solo_equals_single_player_group", "wolf", [_p([[0, "light"], [10, "light"], [20, "heavy"], [50, "light"], [60, "block"], [100, "flee"]])])
    for seed in range(1, 9):
        opp = ("wolf", "bear", "stone_golem", "training_dummy")[seed % 4]
        n = 2 + seed % 3
        specs = []
        for i in range(n):
            ins = sorted(pseudo_random_inputs(seed * 10 + i, 160, 2500) + ([[5 + i, "heal"], [40 + i, "shield"], [90 + i, "heal"]] if i % 2 else []),
                         key=lambda x: x[0])
            specs.append(_p(ins, 1 + seed * 3 + i, **({"equipped": ["power_strike", "ember_strike"]} if i == 0 else {})))
        add(f"pseudo_random_group_{seed}", opp, specs)
    ok = _p([[0, "light"]])
    bad = {
        "invalid_empty_party": ("wolf", []), "invalid_too_many_players": ("wolf", [ok] * 5), "invalid_players_not_a_list": ("wolf", "x"),
        "invalid_player_not_an_object": ("wolf", [5]), "invalid_missing_inputs": ("wolf", [{"level": 1}]),
        "invalid_extra_key": ("wolf", [{**ok, "xp": 5}]), "invalid_level_zero": ("wolf", [_p([], 0)]), "invalid_level_bool": ("wolf", [_p([], True)]),
        "invalid_unknown_command": ("wolf", [_p([[0, "fireball"]])]), "invalid_unsorted": ("wolf", [_p([[5, "light"], [4, "light"]])]),
        "invalid_allowed_unknown": ("wolf", [_p([], 1, allowed=["fireball"])]), "invalid_equipped_duplicate": ("wolf", [_p([], 1, equipped=["a", "a"])]),
        "invalid_opponent": ("dragon", [ok]),
    }
    for name, (opp, players) in bad.items():
        add(name, opp, players)
    return c


def run_case(cfg: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    out = {k: case[k] for k in ("name", "opponent_type", "players")}
    try:
        r = simulate_group(cfg, case["opponent_type"], case["players"])
    except SimError:
        out["expect"] = "error"
        return out
    out["expect"] = "ok"
    out["result"] = {
        "outcome": r.outcome, "ticks": r.ticks, "opponent_hp": r.opponent_hp,
        "players": [{"outcome": p.outcome, "ticks": p.ticks, "actions": p.actions, "player_hp": p.player_hp,
                     "ignored_inputs": p.ignored_inputs, "damage_ticks": list(p.damage_ticks)} for p in r.players]}
    out["reports"] = [build_report(cfg, f"golden-{case['name']}", case["opponent_type"], 1, p) if p.actions else None for p in r.players]
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
