"""Berufszweige und Meisterstücke (AP 5, ADR-0044).

Reine Ableitung aus `profession_rules_v1.json` (Platzhalter) und dem Craft-Zustand; schreibt nichts, ändert keine CEE-Regeln.
Zweige sind nicht exklusiv, ihre Punkte sinken nie. Ein Meisterstück ist ein Rezept, das mindestens einmal in der höchsten Güte
hergestellt wurde (`best` = Index der höchsten Stufe).
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .engine import CharacterState
from .rules import Rules

PROFESSION_RULES = "profession_rules_v1.json"


def load_profession_rules(name: str = PROFESSION_RULES) -> dict[str, Any]:
    return json.loads(resources.files("mmo_cee").joinpath("data", name).read_text(encoding="utf-8"))


def branch_points(part: dict[str, Any], rules: Rules, pr: dict[str, Any], br: dict[str, Any]) -> int:
    recipes = rules["crafting"]["recipes"]
    pts = sum(part["recipes"].get(r, {}).get("count", 0) * recipes[r]["tier"] * 100 for r in br["recipes"] if r in recipes)
    pts += sum(part["techniques"].get(t, 0) * pr["technique_points"] for t in br["techniques"])
    pts += sum(part["elements"].get(e, 0) for e in br["elements"]) // pr["element_divisor"]
    return pts


def profession_view(state: CharacterState, rules: Rules, pr: dict[str, Any] | None = None) -> dict[str, Any]:
    pr = pr or load_profession_rules()
    part, top = state.parts["crafting"], len(rules["crafting"]["tiers"]) - 1
    recipes = rules["crafting"]["recipes"]
    out: dict[str, Any] = {}
    for pid, p in pr["professions"].items():
        branches = {}
        for bid, br in p["branches"].items():
            pts = branch_points(part, rules, pr, br)
            level = sum(1 for t in pr["branch_thresholds"] if pts >= t)
            nxt = next((t for t in pr["branch_thresholds"] if pts < t), None)
            branches[bid] = {"name": br["name"], "points": pts, "level": level, "next": nxt}
        masterpieces = sorted(r for r, e in part["recipes"].items() if e["best"] >= top and recipes.get(r, {}).get("profession") == pid)
        goals = sorted(r for r, v in recipes.items() if v["profession"] == pid and r not in masterpieces)
        out[pid] = {"name": p["name"], "xp": state.parts["profession"]["xp"].get(pid, 0) if "profession" in state.parts else 0,
                    "branches": branches, "masterpieces": masterpieces, "masterpiece_goals": goals}
    return out
