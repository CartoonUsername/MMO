"""Golden Test Vectors der Visual Evolution: Charakterzustand (+ Charakter-ID) -> Erscheinungsparameter.

Ein Port der Ableitung bekommt `state` (Teilzustände aller Engines) und `character_id` und muss exakt
`appearance` liefern (inklusive appearance_sha256). Zustände entstehen durch echte Ereignisfolgen der
Referenz-CEE. Format: reference/golden/README.md (Abschnitt Visual Evolution).

    python -m mmo_cee.golden_visual write ../golden_visual
    python -m mmo_cee.golden_visual check ../golden_visual
"""
from __future__ import annotations

import hashlib
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from .engine import CharacterState
from .errors import RuleViolation
from .golden import (VOW, _created, _train, enc, scenario_essence_decision_path, scenario_essence_npc_two_candidates,
                     scenario_essence_scoring_ember, Step)
from .history import _canonical as canonical_bytes
from .rules import load_rules
from .service import CharacterService
from .visual import VisualEvolution, load_visual_rules

FORMAT_VERSION = 1
CEE_RULES = "rules_v4.json"
VISUAL_RULES = "visual_rules_v1.json"
NAME = "appearance"
EV = "combat.encounter_resolved"


def _sha(package_file: str, pkg: str = "mmo_cee") -> str:
    return hashlib.sha256(resources.files(pkg).joinpath("data", package_file).read_bytes()).hexdigest()


def _attune(e: str, amount: int = 100) -> list[Step]:
    return [("element.exposure", {"element": e, "amount": amount}), ("element.attuned", {"element": e})]


def cases() -> list[tuple[str, str, list[Step]]]:
    xp = ("identity.xp_gained", {"amount": 10000})
    heavy: list[Step] = []
    agile: list[Step] = []
    for day in range(1, 5):
        heavy += _train(day, {"heavy_hit": 43, "block": 33}, n=6)
        agile += _train(day, {"dodge": 33, "perfect_dodge": 18, "light_hit": 120}, n=6)
    caster: list[Step] = []
    for day in range(1, 7):
        caster += _train(day, {"ally_heal": 20, "stun_applied": 8}, n=6)
    out: list[tuple[str, str, list[Step]]] = [
        ("fresh_human", "c1", [_created()]),
        ("fresh_human_other_id", "alt-7", [_created()]),
        ("warrior_chosen", "c1", [_created(), ("identity.class_chosen", {"base_class": "warrior"})]),
        ("archer_chosen", "c1", [_created(), ("identity.class_chosen", {"base_class": "archer"})]),
        ("shaman_alchemist_chosen", "c1", [_created(), ("identity.class_chosen", {"base_class": "shaman_alchemist"})]),
        ("fire_attuned", "c1", [_created(), xp, *_attune("fire", 300)]),
        ("fire_and_water_unequal_affinity", "c1", [_created(), xp, *_attune("fire", 300), *_attune("water", 100)]),
        ("water_and_fire_reverse_order", "c1", [_created(), xp, *_attune("water", 100), *_attune("fire", 300)]),
        ("ice_and_nature_pair", "c1", [_created(), xp, *_attune("ice"), *_attune("nature", 200)]),
        ("three_elements_endgame", "c1", [_created(), ("identity.xp_gained", {"amount": 400000}),
                                          *_attune("shadow", 300), *_attune("light", 150), *_attune("electric", 120)]),
        ("exposed_not_attuned", "c1", [_created(), ("element.exposure", {"element": "earth", "amount": 250})]),
        ("heavy_fighter", "c1", [_created(), *heavy]),
        ("agile_fighter", "c1", [_created(), *agile]),
        ("support_controller", "c1", [_created(), *caster]),
        ("tiny_combat_history", "c1", [_created(), (EV, enc("e1", actions={"heavy_hit": 1}))]),
        ("smith_master", "c1", [_created(), ("profession.work", {"profession": "smithing", "xp": 10**6})]),
        ("miner_farmer_mid", "c1", [_created(), ("profession.work", {"profession": "mining", "xp": 1500}),
                                    ("profession.work", {"profession": "farming", "xp": 700})]),
        ("decision_refused_only", "c1", [_created(), xp, (VOW, {"decision_id": "ember_vow", "choice": "refuse"})]),
        ("warrior_ember_kin_adopted", "c1", [("identity.created", {"kind": "player"}), ("identity.class_chosen", {"base_class": "warrior"}),
                                             *scenario_essence_scoring_ember()["steps"][1:]]),
        ("tide_walker_adopted", "c1", scenario_essence_decision_path()["steps"]),
        ("npc_stone_born_adopted", "c1", scenario_essence_npc_two_candidates()["steps"]),
    ]
    return out


def run_case(name: str, cid: str, steps: list[Step]) -> dict[str, Any]:
    rules = load_rules(CEE_RULES)
    svc = CharacterService(rules=rules)
    for etype, payload in steps:
        try:
            svc.record(cid, etype, payload)
        except RuleViolation:
            pass  # abgelehnte Schritte ändern nichts (siehe CEE-Golden-Vektoren)
    state = svc.state(cid)
    parts = json.loads(canonical_bytes(state.parts))
    appearance = VisualEvolution(rules, load_visual_rules(VISUAL_RULES)).appearance(state)
    return {"name": name, "character_id": cid, "state": parts, "appearance": appearance}


def build_vector() -> dict[str, Any]:
    return {"format": FORMAT_VERSION, "name": NAME, "cee_rules_file": CEE_RULES, "cee_rules_sha256": _sha(CEE_RULES),
            "visual_rules_file": VISUAL_RULES, "visual_rules_sha256": _sha(VISUAL_RULES),
            "cases": [run_case(*c) for c in cases()]}


def verify_vector(vec: dict[str, Any]) -> list[str]:
    """Wendet die Ableitung auf die gespeicherten Zustände an (unabhängig vom Replay) und vergleicht."""
    if vec.get("format") != FORMAT_VERSION:
        return [f"unbekanntes Format {vec.get('format')!r}"]
    errs = []
    if _sha(vec["cee_rules_file"]) != vec["cee_rules_sha256"]:
        errs.append("CEE-Regeldatei hat sich geändert")
    if _sha(vec["visual_rules_file"]) != vec["visual_rules_sha256"]:
        errs.append("Visual-Regeldatei hat sich geändert")
    rules = load_rules(vec["cee_rules_file"])
    ve = VisualEvolution(rules, load_visual_rules(vec["visual_rules_file"]))
    for c in vec["cases"]:
        got = ve.appearance(CharacterState(c["character_id"], rules.version, json.loads(json.dumps(c["state"]))))
        if got != c["appearance"]:
            errs.append(f"Fall {c['name']}: Erscheinung weicht ab")
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
