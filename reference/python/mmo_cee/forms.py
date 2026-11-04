"""Wesensformen und Fähigkeiten als Definitionen mit Vorschau (AP 6, ADR-0045).

Reine Ableitung: verbindet die CEE-Regeln (Mechanik) mit `definitions_v1.json` (Texte, Platzhalter). Schreibt nichts. Die Annahme
einer Form geschieht ausschließlich über die Ereignisse der Essence Engine (Prüfung, Annahme), die dauerhaft und nicht umkehrbar sind.
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .engine import CharacterState
from .essence import form_scores
from .rules import Rules

DEFINITIONS = "definitions_v1.json"


def load_definitions(name: str = DEFINITIONS) -> dict[str, Any]:
    return json.loads(resources.files("mmo_cee").joinpath("data", name).read_text(encoding="utf-8"))


def essence_preview(state: CharacterState, rules: Rules, defs: dict[str, Any] | None = None) -> dict[str, Any]:
    defs = defs or load_definitions()
    part = state.parts["essence"]
    scores = form_scores(state, rules)
    known = state.parts.get("discovery", {}).get("known", {})
    level = state.parts["identity"]["level"]
    forms = []
    for fid, f in rules["essence"]["forms"].items():
        if "signals" not in f:
            continue
        sc, d = scores[fid], defs["forms"].get(fid, {})
        missing = [x for x in f.get("requires_discoveries", []) if x not in known]
        status = "adopted" if part["form"] == fid else "locked_in" if part["form"] != "human" else "trial_passed" if fid in part["trials_passed"] \
            else "eligible" if sc["eligible"] else "secret" if missing else "progress"
        mods = f.get("modifiers", {})
        label = defs["modifiers"]
        forms.append({"id": fid, "name": d.get("name", fid), "text": d.get("text", ""), "status": status, "score": sc["score"], "threshold": sc["threshold"],
                      "min_level": f.get("min_level", 1), "level_ok": level >= f.get("min_level", 1), "requires_discoveries": missing,
                      "contributions": {k: v for k, v in sc["contributions"].items() if v},
                      "advantages": {label.get(k, k): v for k, v in mods.get("advantages", {}).items()},
                      "disadvantages": {label.get(k, k): v for k, v in mods.get("disadvantages", {}).items()},
                      "tradeoff": d.get("tradeoff", ""), "counterplay": d.get("counterplay", ""), "permanent": True})
    decs = []
    for did, dd in rules["essence"].get("decisions", {}).items():
        d = defs["decisions"].get(did, {})
        decs.append({"id": did, "name": d.get("name", did), "text": d.get("text", ""), "min_level": dd.get("min_level", 1),
                     "options": {o: d.get("options", {}).get(o, o) for o in dd["options"]},
                     "chosen": part["decisions"].get(did), "available": part["form"] == "human" and level >= dd.get("min_level", 1)})
    return {"form": part["form"], "forms": forms, "decisions": decs,
            "warning": "Eine angenommene Wesensform ist dauerhaft und nicht umkehrbar. Entscheidungen können nicht zurückgenommen werden."}


def ability_definitions(state: CharacterState, rules: Rules, abilities: dict[str, Any], defs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fähigkeiten mit Name, Beschreibung, Tradeoff, Gegenspiel und offenen Voraussetzungen (aus `svc.abilities`)."""
    defs = defs or load_definitions()
    return {k: {**v, **{x: defs["abilities"].get(k, {}).get(x, "") for x in ("name", "text", "tradeoff", "counterplay")}} for k, v in abilities.items()}
