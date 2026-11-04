"""Golden Test Vectors des Kämpfe mit Gegnerfähigkeiten (sprachneutral). Format: reference/golden/README.md (Abschnitt Gegnerfähigkeiten im Kampf).

    python -m mmo_sim.golden_enemy_fights write ../golden_enemy_fights
    python -m mmo_sim.golden_enemy_fights check ../golden_enemy_fights
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
from .enemies import roll_abilities
from .pack import simulate_pack, strongest
from .rules import load_sim_rules
from .server import build_report

FORMAT_VERSION = 1
RULES_FILE = "sim_rules_v6.json"
NAME = "sim_enemy_fights"


def rules_sha256() -> str:
    return hashlib.sha256(resources.files("mmo_sim").joinpath("data", RULES_FILE).read_bytes()).hexdigest()


def _p(inputs: Any, level: Any = 1, **kw: Any) -> dict[str, Any]:
    return {"level": level, "inputs": inputs, **kw}


def cases() -> list[dict[str, Any]]:
    cfg = load_sim_rules(RULES_FILE)
    c: list[dict[str, Any]] = []

    def add(name: str, opps: Any, players: Any, abilities: Any = None) -> None:
        c.append({"name": name, "opponents": opps, "abilities": abilities, "players": players})

    B, F, F2 = "bear", [[200, "flee"]], [[900, "flee"]]       # Bär: Takt 45 + Vorwarnzeit 8; die erste Handlung liegt bei Tick 45
    add("slam_hit", [B], [_p(F, 30)], [["heavy_slam"]])
    add("slam_dodge", [B], [_p([[55, "dodge"]] + F, 30)], [["heavy_slam"]])
    add("slam_perfect_dodge", [B], [_p([[56, "dodge"]] + F, 30)], [["heavy_slam"]])
    add("slam_block", [B], [_p([[54, "block"]] + F, 30)], [["heavy_slam"]])
    add("slam_parry", [B], [_p([[56, "block"]] + F, 30)], [["heavy_slam"]])
    add("slam_evade_skill", [B], [_p([[54, "dash"]] + F, 30, equipped=["flowing_step"])], [["heavy_slam"]])
    add("slam_stun_does_not_interrupt", [B], [_p([[50, "stun"]] + F, 30)], [["heavy_slam"]])
    add("slam_goes_to_highest_threat", [B], [_p(F, 30), _p([[0, "heavy"]] + F, 30)], [["heavy_slam"]])
    add("area_two_players_one_dodges", [B], [_p(F, 30), _p([[59, "dodge"]] + F, 30)], [["ground_pound"]])
    add("area_parry", [B], [_p([[60, "block"]] + F, 30), _p(F, 30)], [["ground_pound"]])
    add("stunning_blow", [B], [_p([[40, "light"], [60, "light"], [75, "light"], [90, "light"]] + F, 30)], [["stunning_blow"]])
    add("stunning_blow_dodged", [B], [_p([[52, "dodge"], [60, "light"]] + F, 30)], [["stunning_blow"]])
    add("crippling_bite", [B], [_p([[0, "light"], [8, "light"], [60, "light"], [70, "light"]] + F, 30)], [["crippling_bite"]])
    add("burning_curse_burns", [B], [_p(F, 30)], [["burning_curse"]])
    add("burning_curse_interrupted_by_stun", [B], [_p([[50, "stun"]] + F, 30)], [["burning_curse"]])
    add("burning_curse_interrupted_by_heavy", [B], [_p([[42, "heavy"]] + F, 30)], [["burning_curse"]])
    add("burning_curse_shielded_ally", [B], [_p(F, 30), _p([[70, "shield"]] + F, 30)], [["burning_curse"]])
    add("stone_skin_absorbs", [B], [_p([[i * 8, "light"] for i in range(10, 40)] + F2, 30)], [["stone_skin"]])
    add("stone_skin_broken_by_precise_hit", [B], [_p([[56, "stun"], [70, "light"]] + F, 30)], [["stone_skin"]])
    add("stone_skin_broken_by_parry", [B], [_p([[111, "block"]] + F, 30)], [["stone_skin", "heavy_slam"]])
    add("stone_skin_not_broken_by_heavy", [B], [_p([[60, "heavy"]] + F, 30)], [["stone_skin"]])
    add("mend_heals_wounded_ally", ["wisp_healer", "wolf"], [_p([[0, "target_2"], [1, "light"], [9, "light"], [17, "light"]] + F, 30)], None)
    add("mend_interrupted", ["wisp_healer", "wolf"], [_p([[0, "target_2"], [1, "light"], [9, "light"], [17, "light"], [20, "target_1"], [62, "stun"]] + F, 30)], None)
    add("howl_hastes_the_pack", ["wolf", "wolf"], [_p(F, 30)], [["howl"], []])
    add("howl_needs_an_ally", ["wolf"], [_p(F, 30)], [["howl"]])
    add("call_pack_summons", ["totem_caller"], [_p([[500, "flee"]], 50)], None)
    add("call_pack_victory_needs_summons", ["totem_caller"], [_p([[62, "heavy"], [80, "heavy"]] + [[100 + i * 50, "sweep"] for i in range(30)] + [[3000, "flee"]], 50)], None)
    add("call_imps_summons_stone_imps", [B], [_p([[500, "flee"]], 50)], [["call_imps"]])
    add("alpha_phases", ["alpha_wolf"], [_p([[i * 8, "light"] for i in range(0, 120)] + [[1500, "flee"]], 30), _p([[i * 8 + 3, "light"] for i in range(0, 120)] + [[1500, "flee"]], 30)], None)
    add("colossus_three_players", ["stone_heart_colossus"], [_p(sorted([[i * 8 + k, "light"] for i in range(1, 300)] + [[i * 40 + k, "block"] for i in range(1, 60)]) + [[2800, "flee"]], 50) for k in range(3)], None)
    add("boss_and_warden", ["stone_heart_colossus", "stone_warden"], [_p([[400, "flee"]], 50), _p([[400, "flee"]], 50)], None)
    for t in ("alpha_wolf", "wisp_healer", "bog_witch", "stone_warden", "shadow_hunter", "totem_caller"):
        add(f"template_{t}", [t], [_p([[i * 8, "light"] for i in range(0, 60)] + [[700, "flee"]], 30)], None)
    for seed in range(1, 11):
        types = ["alpha_wolf", "bog_witch", "wisp_healer", "stone_warden", "totem_caller", "shadow_hunter", "wolf", "bear"]
        opps = [types[(seed + k * 3) % len(types)] for k in range(1 + seed % 3)]
        abil = [roll_abilities(cfg, t, f"sp{seed}-{k}", seed) for k, t in enumerate(opps)]
        specs = []
        for i in range(1 + seed % 3):
            ins = sorted(pseudo_random_inputs(seed * 10 + i, 200, 2500) + [[5 + i, "heal"], [40 + i, "shield"], [60 + i, "target_2"], [90 + i, "sweep"]], key=lambda x: x[0])
            specs.append(_p(ins, 10 + seed * 3 + i))
        add(f"pseudo_random_{seed}", opps, specs, abil)
    ok = _p([[0, "light"]])
    bad = {
        "invalid_abilities_not_a_list": (["wolf"], [ok], "heavy_slam"), "invalid_abilities_length": (["wolf"], [ok], [[], []]),
        "invalid_unknown_ability": (["wolf"], [ok], [["nonsense"]]), "invalid_duplicate_ability": (["wolf"], [ok], [["howl", "howl"]]),
        "invalid_ability_entry": (["wolf"], [ok], [5]), "invalid_unknown_command": (["wolf"], [_p([[0, "target_7"]])], None),
    }
    for name, (opps, players, abil) in bad.items():
        add(name, opps, players, abil)
    return c


def run_case(cfg: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    out = {k: case[k] for k in ("name", "opponents", "abilities", "players")}
    try:
        r = simulate_pack(cfg, case["opponents"], case["players"], case["abilities"])
    except SimError:
        out["expect"] = "error"
        return out
    out["expect"] = "ok"
    out["result"] = {
        "outcome": r.outcome, "ticks": r.ticks, "opponent_hp": r.opponent_hp, "opponents": list(r.opponents), "events": [dict(e) for e in r.events],
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
