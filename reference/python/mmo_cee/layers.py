"""Drei Schichten der Charakteridentität (Blueprint §12, ADR-0040) – reine, lesende Ableitung aus Ereignislog und Zustand.

1. **Lebensgeschichte** (`life_story`): dauerhafte, validierte Meilensteine aus dem Ereignislog. Nur anhängend: neue Ereignisse
   fügen Einträge hinten an, nichts davon verschwindet, wenn sich aktuelle Schwerpunkte verschieben.
2. **Aktuelles Profil** (`current_profile`): gegenwärtige Schwerpunkte, Affinitäten und Meisterschaften. Darf sich verschieben.
3. **Wesenidentität** (`essence_identity`): Grundklasse, Wesensform, geprägte Elemente, Entscheidungen. Nach der Annahme dauerhaft.

Nichts hier schreibt oder verändert Ereignisse; es analysiert ausschließlich belegbare Spielhandlungen der Figur (keine realen Personendaten).
"""
from __future__ import annotations

from typing import Any

from .combat import reached_directions
from .crafting import craft_profile
from .economy import economic_profile
from .engine import CharacterState
from .essence import essence_profile
from .history import Event
from .identity import IdentityEngine
from .professions import ProfessionEngine
from .rules import Rules

# Ereignisarten, die immer ein Meilenstein sind; andere (Erfahrung, Exposition, Arbeit, Beweise) fließen nur in Zähler und Profil ein.
ALWAYS = ("identity.created", "identity.class_chosen", "element.attuned", "essence.trial_passed", "essence.decision_made", "essence.adopted",
          "discovery.made", "discovery.learned", "economy.company_founded", "economy.company_closed", "economy.career_changed")
COUNTERS = {"combat.encounter_resolved": "encounters", "crafting.crafted": "crafts", "economy.trade_completed": "trades",
            "discovery.evidence_gathered": "evidence", "profession.work": "work_sessions"}


def life_story(events: list[Event], rules: Rules) -> dict[str, Any]:
    """Meilensteine in Ereignisreihenfolge plus Zähler. Erste Siege je Gegnerart und erste Herstellung je Rezept sind Meilensteine."""
    ident = IdentityEngine(rules)
    xp, level = 0, 1
    seen_win: set[str] = set()
    seen_craft: set[str] = set()
    out: list[dict[str, Any]] = []
    counts = {v: 0 for v in COUNTERS.values()}
    for e in events:
        p = e.payload
        if e.type in COUNTERS:
            counts[COUNTERS[e.type]] += 1
        if e.type in ALWAYS:
            data = {k: p[k] for k in ("base_class", "element", "form", "decision_id", "choice", "discovery_id", "credit", "company_id", "role", "kind", "day") if k in p}
            out.append({"seq": e.seq, "type": e.type, "data": data})
        elif e.type == "identity.xp_gained":
            xp += p["amount"]
            nl = ident.level_for(xp)
            while level < nl:
                level += 1
                out.append({"seq": e.seq, "type": "identity.level_reached", "data": {"level": level}})
        elif e.type == "combat.encounter_resolved" and p.get("outcome") == "victory" and p.get("opponent_type") not in seen_win:
            seen_win.add(p["opponent_type"])
            out.append({"seq": e.seq, "type": "combat.first_victory", "data": {"opponent_type": p["opponent_type"], "day": p.get("day")}})
        elif e.type == "crafting.crafted" and p.get("recipe_id") not in seen_craft:
            seen_craft.add(p["recipe_id"])
            out.append({"seq": e.seq, "type": "crafting.first_craft", "data": {"recipe_id": p["recipe_id"], "day": p.get("day")}})
    return {"milestones": out, "counts": counts, "event_count": len(events), "head_hash": events[-1].hash if events else None}


def current_profile(state: CharacterState, rules: Rules) -> dict[str, Any]:
    """Gegenwärtige Schwerpunkte. Rohwerte je Bereich ohne Gewichtung (Blueprint: Gewichte sind Balancing, nicht hier festgelegt)."""
    p = state.parts
    pe = ProfessionEngine(rules)
    professions = {k: {"xp": v, "mastery": pe.mastery_level(v)} for k, v in sorted(p["profession"]["xp"].items())}
    try:
        directions = reached_directions(state, rules)
    except Exception:                                   # ältere Regelversionen ohne Kampfentwicklung
        directions = {}
    try:
        craft = craft_profile(state, rules)
    except Exception:
        craft = {}
    try:
        econ = economic_profile(state, rules)
    except Exception:
        econ = {}
    return {
        "level": p["identity"]["level"],
        "elements": {"affinity": dict(p["element"]["affinity"]), "leading": [k for k, v in sorted(p["element"]["affinity"].items(), key=lambda kv: (-kv[1], kv[0])) if v > 0][:3]},
        "professions": professions,
        "combat": {"points": dict(p["combat"]["points"]) if "combat" in p else {}, "directions": directions},
        "crafting": craft,
        "economy": econ,
        "research": {"discoveries": len(p["discovery"]["known"]) if "discovery" in p else 0},
    }


def essence_identity(state: CharacterState, rules: Rules) -> dict[str, Any]:
    """Dauerhafte Identität: Klasse, Wesensform (mit Vor-/Nachteilen), geprägte Elemente, getroffene Entscheidungen."""
    ess = state.parts["essence"]
    return {
        "base_class": state.parts["identity"]["base_class"],
        "form": ess["form"],
        "form_adopted": ess["form"] != "human",
        "adopted_at_seq": ess.get("adopted_at_seq"),
        "decisions": dict(ess.get("decisions", {})),
        "trials_passed": list(ess.get("trials_passed", [])),
        "attuned_elements": list(state.parts["element"]["attuned"]),
        "profile": essence_profile(state, rules),
        "permanent": ess["form"] != "human",
    }


def layers(events: list[Event], state: CharacterState, rules: Rules) -> dict[str, Any]:
    return {"life_story": life_story(events, rules), "current_profile": current_profile(state, rules), "essence_identity": essence_identity(state, rules)}
