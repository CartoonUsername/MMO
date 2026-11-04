"""Golden Test Vectors des Gegnerfähigkeiten (Baukasten) (sprachneutral). Format: reference/golden/README.md (Abschnitt Gegnerfähigkeiten).

    python -m mmo_sim.golden_enemies write ../golden_enemies
    python -m mmo_sim.golden_enemies check ../golden_enemies
"""
from __future__ import annotations

import hashlib
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from .errors import SimError
from .enemies import abilities_at, roll_abilities
from .rules import load_sim_rules

FORMAT_VERSION = 1
RULES_FILE = "sim_rules_v6.json"
NAME = "enemy_rolls"


def rules_sha256() -> str:
    return hashlib.sha256(resources.files("mmo_sim").joinpath("data", RULES_FILE).read_bytes()).hexdigest()


def _p(inputs: Any, level: Any = 1, **kw: Any) -> dict[str, Any]:
    return {"level": level, "inputs": inputs, **kw}


SPAWNS = ("sp1", "sp2", "north_cave", "ruin_gate-7", "Ä")
DAYS = (0, 1, 2, 3, 7, 365)
HP = (1000, 999, 700, 699, 600, 599, 400, 399, 250, 249, 1, 0)


def cases() -> list[dict[str, Any]]:
    cfg = load_sim_rules(RULES_FILE)
    c: list[dict[str, Any]] = []
    for t in cfg["opponents"]:
        for sp in SPAWNS:
            for d in DAYS:
                c.append({"name": f"roll_{t}_{sp}_{d}", "kind": "roll", "type": t, "spawn": sp, "day": d})
    for t, o in cfg["opponents"].items():
        if o.get("phases"):
            for hp in HP:
                c.append({"name": f"phase_{t}_{hp}", "kind": "phase", "type": t, "base": o.get("abilities", []), "hp": hp})
    for name, (t, sp, d) in {
        "invalid_unknown_type": ("dragon", "sp1", 1), "invalid_empty_spawn": ("wolf", "", 1), "invalid_spawn_not_a_string": ("wolf", 5, 1),
        "invalid_negative_day": ("wolf", "sp1", -1), "invalid_day_bool": ("wolf", "sp1", True),
        "invalid_type_not_a_string": (None, "sp1", 1),
    }.items():
        c.append({"name": name, "kind": "roll", "type": t, "spawn": sp, "day": d})
    return c


def run_case(cfg: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    out = dict(case)
    try:
        if case["kind"] == "roll":
            out["result"] = {"abilities": roll_abilities(cfg, case["type"], case["spawn"], case["day"])}
        else:
            abil, factor = abilities_at(cfg, case["type"], case["base"], case["hp"])
            out["result"] = {"abilities": abil, "attack_interval_permille": factor}
    except (SimError, TypeError):
        out.pop("result", None)
        out["expect"] = "error"
        return out
    out["expect"] = "ok"
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
