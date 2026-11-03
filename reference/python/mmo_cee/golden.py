"""Golden Test Vectors: sprachneutrale Testfälle für die spätere Portierung (C++/C#/Rust).

Ein Vektor beschreibt ein Szenario als Folge von Schritten (Ereignistyp + Payload) mit der
erwarteten Reaktion der Referenzimplementierung: akzeptiert (inkl. Ereignis-Hash) oder
abgelehnt (Zustand und Log bleiben unverändert), dazu der Zustands-Hash nach jedem Schritt
und der vollständige Endzustand samt abgeleiteter Sichten.

Befehle (im Verzeichnis reference/python):
    python -m mmo_cee.golden write ../golden     # Vektoren neu erzeugen
    python -m mmo_cee.golden check ../golden     # committete Vektoren prüfen (Exit-Code 1 bei Abweichung)

Format und Prüfverfahren für Ports: reference/golden/README.md
"""
from __future__ import annotations

import hashlib
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from .combat import reached_directions, style_profile
from .discovery import discovery_progress, known_discoveries
from .essence import essence_profile, form_scores
from .errors import RuleViolation
from .history import _canonical as canonical_bytes
from .rules import load_rules
from .service import CharacterService

FORMAT_VERSION = 1
CHARACTER_ID = "c1"
EV = "combat.encounter_resolved"

Step = tuple[str, dict[str, Any]]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rules_file_sha256(name: str) -> str:
    return sha256_hex(resources.files("mmo_cee").joinpath("data", name).read_bytes())


def state_hash(parts: dict[str, Any]) -> str:
    return sha256_hex(canonical_bytes(parts))


# ---------------------------------------------------------------- Szenarien ----------
def enc(eid: str, **over: Any) -> dict[str, Any]:
    p: dict[str, Any] = {
        "encounter_id": eid, "opponent_type": "wolf", "opponent_level": 5, "outcome": "victory",
        "duration_s": 60, "day": 1, "actions": {"heavy_hit": 10},
    }
    p.update(over)
    return p


def _created(kind: str = "player") -> Step:
    return ("identity.created", {"kind": kind})


def _train(day: int, actions: dict[str, int], n: int = 6, tag: str = "") -> list[Step]:
    return [(EV, enc(f"{tag}d{day}-{i}", opponent_type=f"mob{i}", day=day, actions=actions)) for i in range(n)]


def scenario_identity_basic() -> dict[str, Any]:
    return {
        "description": "Erstellung, Klassenwahl (einmalig), XP/Level-Kurve und Obergrenze, ungültige Eingaben.",
        "rules_file": "rules_v3.json",
        "steps": [
            ("identity.xp_gained", {"amount": 5}),  # vor Erstellung -> abgelehnt
            _created(),
            _created(),  # doppelt -> abgelehnt
            ("identity.created", {"kind": "monster"}),
            ("identity.class_chosen", {"base_class": "mage"}),
            ("identity.class_chosen", {"base_class": "warrior"}),
            ("identity.class_chosen", {"base_class": "archer"}),
            ("identity.xp_gained", {"amount": 99}),
            ("identity.xp_gained", {"amount": 1}),
            ("identity.xp_gained", {"amount": 0}),
            ("identity.xp_gained", {"amount": -5}),
            ("identity.xp_gained", {"amount": 1.5}),
            ("identity.xp_gained", {"amount": "10"}),
            ("identity.xp_gained", {"amount": True}),
            ("identity.xp_gained", {"amount": 1000000000}),
            ("bogus.thing", {}),
        ],
    }


def scenario_element_limits() -> dict[str, Any]:
    return {
        "description": "Neun Elemente, Prägung ab Schwelle, zwei reguläre + ein Endgame-Element (Mindeststufe), Obergrenze drei.",
        "rules_file": "rules_v3.json",
        "steps": [
            _created(),
            ("identity.xp_gained", {"amount": 1000}),
            ("element.exposure", {"element": "metal", "amount": 5}),
            ("element.exposure", {"element": "fire", "amount": 99}),
            ("element.attuned", {"element": "fire"}),
            ("element.exposure", {"element": "fire", "amount": 1}),
            ("element.attuned", {"element": "fire"}),
            ("element.attuned", {"element": "fire"}),
            ("element.exposure", {"element": "wind", "amount": 100}),
            ("element.attuned", {"element": "wind"}),
            ("element.exposure", {"element": "light", "amount": 500}),
            ("element.attuned", {"element": "light"}),  # Stufe zu niedrig -> abgelehnt
            ("identity.xp_gained", {"amount": 160000}),
            ("element.attuned", {"element": "light"}),
            ("element.exposure", {"element": "earth", "amount": 500}),
            ("element.attuned", {"element": "earth"}),  # vierte -> abgelehnt
            ("element.exposure", {"element": "ice", "amount": 0}),
        ],
    }


def scenario_profession_mastery() -> dict[str, Any]:
    return {
        "description": "Berufserfahrung je Beruf, Meisterschaftsgrenzen, ungültige Berufe/Werte.",
        "rules_file": "rules_v3.json",
        "steps": [
            _created(),
            ("profession.work", {"profession": "smithing", "xp": 60}),
            ("profession.work", {"profession": "smithing", "xp": 40}),
            ("profession.work", {"profession": "smithing", "xp": 200}),
            ("profession.work", {"profession": "alchemy", "xp": 99}),
            ("profession.work", {"profession": "necromancy", "xp": 5}),
            ("profession.work", {"profession": "mining", "xp": 0}),
            ("profession.work", {"profession": "mining", "xp": 1000000}),
        ],
    }


def scenario_essence_path() -> dict[str, Any]:
    return {
        "description": "Wesensweg Mensch -> ember_kin (Platzhalter): Voraussetzungen, Prüfung, dauerhafte Annahme.",
        "rules_file": "rules_v3.json",
        "steps": [
            _created(),
            ("essence.trial_passed", {"form": "ember_kin"}),  # Voraussetzungen fehlen
            ("identity.xp_gained", {"amount": 10000}),
            ("element.exposure", {"element": "fire", "amount": 100}),
            ("element.attuned", {"element": "fire"}),
            ("essence.trial_passed", {"form": "ember_kin"}),  # Beruf fehlt
            ("profession.work", {"profession": "smithing", "xp": 700}),
            ("essence.adopted", {"form": "ember_kin"}),  # keine Prüfung -> abgelehnt
            ("essence.trial_passed", {"form": "dragon"}),
            ("essence.trial_passed", {"form": "ember_kin"}),
            ("essence.trial_passed", {"form": "ember_kin"}),  # doppelt
            ("essence.adopted", {"form": "ember_kin"}),
            ("essence.adopted", {"form": "stone_born"}),  # dauerhaft
            ("essence.trial_passed", {"form": "stone_born"}),
        ],
    }


def scenario_combat_validation() -> dict[str, Any]:
    return {
        "description": "Kampfbericht: exakte Punkte, Ergebnisfaktoren, Duplikate, Pflichtfelder, Wertebereiche, Aktionsraten-Grenzen.",
        "rules_file": "rules_v3.json",
        "steps": [
            _created(),
            (EV, enc("e1")),
            (EV, enc("e1")),  # Duplikat
            (EV, enc("e1b", actions={"dodge": 1}, opponent_type="x")),
            (EV, enc("e2", outcome="defeat", opponent_type="a")),
            (EV, enc("e3", outcome="fled", opponent_type="b")),
            (EV, enc("e4", outcome="draw")),
            (EV, enc("e5", points=999999)),  # clientseitige Punkte
            (EV, enc("e6", strength=5)),
            (EV, enc("e7", actions={"fireball": 3})),
            (EV, enc("e8", actions={})),
            (EV, enc("e9", actions={"heavy_hit": 0})),
            (EV, enc("e10", actions={"heavy_hit": 44})),  # Rate: 43 erlaubt
            (EV, enc("e11", actions={"heavy_hit": 43}, opponent_type="c")),
            (EV, enc("e12", duration_s=5, actions={"heavy_hit": 7})),
            (EV, enc("e13", duration_s=5, actions={"heavy_hit": 6}, opponent_type="d")),
            (EV, enc("e14", duration_s=4)),
            (EV, enc("e15", duration_s=3601)),
            (EV, enc("e16", opponent_level=0)),
            (EV, enc("e17", opponent_level=101)),
            (EV, enc("e18", day=-1)),
            (EV, enc("", opponent_type="y")),
            (EV, enc("x" * 65)),
            (EV, enc("e19", actions={"parry": 4, "perfect_dodge": 2}, opponent_type="e")),
            ("combat.grant_points", {"strength": 100}),
        ],
    }


def scenario_combat_antifarm() -> dict[str, Any]:
    steps: list[Step] = [_created()]
    steps += [(EV, enc(f"w{i}")) for i in range(8)]  # gleicher Gegnertyp: Abnahme
    steps += [(EV, enc("late", day=0, opponent_type="z"))]  # Tag springt zurück -> abgelehnt
    steps += _train(2, {"heavy_hit": 43}, n=30)  # Tageslimit
    steps += [(EV, enc("extra", opponent_type="fresh", day=2, actions={"heavy_hit": 43}))]  # kein Fortschritt mehr
    steps += _train(3, {"heavy_hit": 43, "block": 33}, n=30)  # Limit je Dimension, Tag 3 setzt fort
    steps += [(EV, enc("back", day=2, opponent_type="q"))]
    return {
        "description": "Anti-Farming: Wiederholungsabnahme je Gegnertyp, Tageslimit (voll/reduziert/hart), Tagwechsel, Tag nicht rückwärts.",
        "rules_file": "rules_v3.json",
        "steps": steps,
    }


def scenario_combat_directions_umbral() -> dict[str, Any]:
    dodger = {"dodge": 33, "perfect_dodge": 18, "light_hit": 120}
    steps: list[Step] = [_created(), ("identity.xp_gained", {"amount": 10000})]
    for day in range(1, 5):
        steps += _train(day, dodger, n=6)
    steps += [
        ("essence.trial_passed", {"form": "umbral_kin"}),  # Schattenprägung fehlt
        ("element.exposure", {"element": "shadow", "amount": 100}),
        ("element.attuned", {"element": "shadow"}),
        ("essence.trial_passed", {"form": "umbral_kin"}),
        ("essence.adopted", {"form": "umbral_kin"}),
        ("identity.class_chosen", {"base_class": "warrior"}),  # Grundklasse bleibt wählbar/erhalten
    ]
    return {
        "description": "Kampfrichtung skirmisher + Schattenprägung -> Wesensform umbral_kin (Platzhalter); mehrere Systeme zusammen.",
        "rules_file": "rules_v3.json",
        "steps": steps,
    }


def scenario_npc_pipeline() -> dict[str, Any]:
    steps: list[Step] = [_created("npc"), ("identity.xp_gained", {"amount": 400})]
    steps += [(EV, enc("npc-1", actions={"stun_applied": 8, "slow_applied": 10}))]
    steps += [(EV, enc("npc-1", actions={"stun_applied": 8}))]  # Duplikat
    for day in range(1, 5):
        steps += _train(day, {"stun_applied": 10, "slow_applied": 23}, n=6, tag="n")
    steps += [("profession.work", {"profession": "farming", "xp": 120})]
    return {
        "description": "NPC durchläuft dieselbe Pipeline wie Spieler (Kampf, Beruf, Richtungen).",
        "rules_file": "rules_v3.json",
        "steps": steps,
    }


def scenario_rules_v1_without_combat() -> dict[str, Any]:
    return {
        "description": "Regelversion 1 kennt keine Kampfentwicklung: combat.* wird abgelehnt, übrige Engines unverändert.",
        "rules_file": "rules_v1.json",
        "steps": [
            _created(),
            (EV, enc("e1")),
            ("element.exposure", {"element": "fire", "amount": 100}),
            ("element.attuned", {"element": "fire"}),
        ],
    }


VOW = "essence.decision_made"


def scenario_essence_scoring_ember() -> dict[str, Any]:
    return {
        "description": "Wesensbewertung (rules v4): Entscheidungen, gewichtete Punktzahl statt harter Schwelle, Prüfung, dauerhafte Annahme.",
        "rules_file": "rules_v4.json",
        "steps": [
            _created(),
            (VOW, {"decision_id": "ember_vow", "choice": "accept"}),  # Stufe 1 -> abgelehnt
            ("identity.xp_gained", {"amount": 10000}),
            (VOW, {"decision_id": "ghost", "choice": "accept"}),
            (VOW, {"decision_id": "ember_vow", "choice": "maybe"}),
            (VOW, {"decision_id": "ember_vow"}),
            (VOW, {"decision_id": "ember_vow", "choice": "accept", "points": 9999}),
            ("essence.trial_passed", {"form": "ember_kin"}),  # Punktzahl 0
            ("element.exposure", {"element": "fire", "amount": 100}),
            ("element.attuned", {"element": "fire"}),
            ("profession.work", {"profession": "smithing", "xp": 700}),
            (VOW, {"decision_id": "ember_vow", "choice": "accept"}),
            (VOW, {"decision_id": "ember_vow", "choice": "accept"}),  # doppelt
            (VOW, {"decision_id": "ember_vow", "choice": "refuse"}),  # keine Umentscheidung
            ("essence.trial_passed", {"form": "ember_kin"}),  # 558 < 600
            ("profession.work", {"profession": "smithing", "xp": 3000}),
            ("essence.adopted", {"form": "ember_kin"}),  # ohne Prüfung
            ("essence.trial_passed", {"form": "ember_kin"}),
            ("essence.trial_passed", {"form": "ember_kin"}),
            ("essence.adopted", {"form": "umbral_kin"}),
            ("essence.adopted", {"form": "ember_kin"}),
            (VOW, {"decision_id": "shadow_pact", "choice": "accept"}),  # nach Annahme
            ("essence.trial_passed", {"form": "stone_born"}),
        ],
    }


def scenario_essence_decision_path() -> dict[str, Any]:
    steps: list[Step] = [_created(), ("identity.xp_gained", {"amount": 10000}),
                         ("element.exposure", {"element": "water", "amount": 100}), ("element.attuned", {"element": "water"}),
                         ("profession.work", {"profession": "logistics", "xp": 3000}),
                         ("profession.work", {"profession": "trade", "xp": 1500})]
    for day in range(1, 7):
        steps += _train(day, {"ally_heal": 20}, n=6)
    steps += [
        ("essence.trial_passed", {"form": "tide_walker"}),  # ohne Entscheidung zu wenig Punkte
        (VOW, {"decision_id": "ember_vow", "choice": "refuse"}),
        ("essence.trial_passed", {"form": "tide_walker"}),
        ("essence.adopted", {"form": "tide_walker"}),
    ]
    return {
        "description": "Anderer Weg zu einer anderen Form: Wasser + Berufe + Unterstützungsrichtung + Ablehnung eines Gelübdes -> tide_walker (Platzhalter).",
        "rules_file": "rules_v4.json",
        "steps": steps,
    }


def scenario_essence_npc_two_candidates() -> dict[str, Any]:
    steps: list[Step] = [_created("npc"), ("identity.xp_gained", {"amount": 10000}),
                         ("element.exposure", {"element": "fire", "amount": 100}), ("element.attuned", {"element": "fire"}),
                         ("profession.work", {"profession": "smithing", "xp": 3700}),
                         (VOW, {"decision_id": "ember_vow", "choice": "accept"}),
                         ("element.exposure", {"element": "earth", "amount": 300}), ("element.attuned", {"element": "earth"}),
                         ("profession.work", {"profession": "mining", "xp": 1000000}),
                         ("profession.work", {"profession": "construction", "xp": 1000000}),
                         (VOW, {"decision_id": "mountain_oath", "choice": "accept"})]
    for day in range(1, 8):
        steps += _train(day, {"parry": 15, "block": 33}, n=6)
    steps += [("essence.trial_passed", {"form": "stone_born"}), ("essence.adopted", {"form": "stone_born"}),
              ("essence.trial_passed", {"form": "ember_kin"}), ("essence.adopted", {"form": "ember_kin"})]
    return {
        "description": "NPC erfüllt zwei Formen gleichzeitig, wählt eine; Wahl ist dauerhaft (Wesensform wird nicht gewechselt).",
        "rules_file": "rules_v4.json",
        "steps": steps,
    }


def _attune(element: str, amount: int = 100) -> list[Step]:
    return [("element.exposure", {"element": element, "amount": amount}), ("element.attuned", {"element": element})]


DEV, DMADE, DLEARNED = "discovery.evidence_gathered", "discovery.made", "discovery.learned"


def _gather(did: str, evidence: list[str]) -> list[Step]:
    return [(DEV, {"discovery_id": did, "evidence_id": e}) for e in evidence]


def _train_level(day: int, actions: dict[str, int], level: int, n: int = 6) -> list[Step]:
    return [(EV, enc(f"L{level}d{day}-{i}", opponent_type=f"mob{i}", opponent_level=level, day=day, actions=actions)) for i in range(n)]


def scenario_discovery_research() -> dict[str, Any]:
    iron = ["ore_sample_a", "ore_sample_b", "forge_trial"]
    return {
        "description": "Entdeckung (rules v5): eindeutige Beweise, Abschluss nur mit allen Beweisen und Voraussetzungen, Anerkennung, Lernen nur bei teilbaren Entdeckungen.",
        "rules_file": "rules_v5.json",
        "steps": [
            _created(), ("identity.xp_gained", {"amount": 10000}),
            (DEV, {"discovery_id": "ghost", "evidence_id": "x"}),
            (DEV, {"discovery_id": "iron_folding", "evidence_id": "frost_lily"}),
            (DEV, {"discovery_id": "twilight_rite", "evidence_id": "dusk_altar"}),  # Vorwissen fehlt
            (DEV, {"discovery_id": "iron_folding", "evidence_id": "ore_sample_a", "points": 5}),
            (DEV, {"discovery_id": "iron_folding", "evidence_id": "ore_sample_a"}),
            (DEV, {"discovery_id": "iron_folding", "evidence_id": "ore_sample_a"}),  # doppelt
            (DMADE, {"discovery_id": "iron_folding", "day": 1, "credit": "pioneer"}),  # unvollständig
            *_gather("iron_folding", iron[1:]),
            (DMADE, {"discovery_id": "iron_folding", "day": 1, "credit": "pioneer"}),  # Beruf fehlt
            ("profession.work", {"profession": "smithing", "xp": 700}),
            (DMADE, {"discovery_id": "iron_folding", "day": 1, "credit": "king"}),
            (DMADE, {"discovery_id": "iron_folding", "day": 1}),
            (DMADE, {"discovery_id": "iron_folding", "day": 3, "credit": "pioneer"}),
            (DMADE, {"discovery_id": "iron_folding", "day": 3, "credit": "pioneer"}),  # bekannt
            (DEV, {"discovery_id": "iron_folding", "evidence_id": "forge_trial"}),  # bekannt
            *_gather("old_shrine_map", ["shrine_mural", "hermit_story"]),
            (DMADE, {"discovery_id": "old_shrine_map", "day": 2, "credit": "discoverer"}),  # Tag zurück
            (DMADE, {"discovery_id": "old_shrine_map", "day": 3, "credit": "discoverer"}),
            (DLEARNED, {"discovery_id": "frostglass_recipe", "day": 4, "from_character": "teacher-1"}),  # Voraussetzungen fehlen
            ("profession.work", {"profession": "alchemy", "xp": 300}),
            *_attune("ice"),
            (DLEARNED, {"discovery_id": "frostglass_recipe", "day": 4, "from_character": "c1"}),  # sich selbst
            (DLEARNED, {"discovery_id": "frostglass_recipe", "day": 4, "from_character": ""}),
            (DLEARNED, {"discovery_id": "frostglass_recipe", "day": 4, "from_character": "teacher-1"}),
            (DLEARNED, {"discovery_id": "frostglass_recipe", "day": 5, "from_character": "teacher-2"}),  # bekannt
            (DLEARNED, {"discovery_id": "twilight_rite", "day": 5, "from_character": "teacher-1"}),  # nicht teilbar
            ("discovery.grant_all", {}),
        ],
    }


def scenario_discovery_secret_form() -> dict[str, Any]:
    steps: list[Step] = [_created(), ("identity.xp_gained", {"amount": 36100}), *_attune("light"), *_attune("shadow")]
    for day in range(1, 7):
        steps += _train_level(day, {"dodge": 33, "perfect_dodge": 18, "light_hit": 120}, 20)
    steps += [
        ("essence.trial_passed", {"form": "twilight_kin"}),  # genug Punkte, aber geheime Form ohne Entdeckung
        (DEV, {"discovery_id": "twilight_rite", "evidence_id": "dusk_altar"}),  # Vorwissen fehlt
        *_gather("old_shrine_map", ["shrine_mural", "hermit_story"]),
        (DMADE, {"discovery_id": "old_shrine_map", "day": 10, "credit": "pioneer"}),
        *_gather("twilight_rite", ["dusk_altar", "dawn_altar"]),
        (DMADE, {"discovery_id": "twilight_rite", "day": 11, "credit": "pioneer"}),  # Beweis fehlt
        (DEV, {"discovery_id": "twilight_rite", "evidence_id": "blended_light"}),
        (DMADE, {"discovery_id": "twilight_rite", "day": 11, "credit": "pioneer"}),
        ("essence.trial_passed", {"form": "twilight_kin"}),
        ("essence.adopted", {"form": "twilight_kin"}),
    ]
    return {
        "description": "Geheime Wesensform (Platzhalter twilight_kin): Punkte allein genügen nicht, die Entdeckung (mit Vorwissen-Kette) schaltet den Weg frei.",
        "rules_file": "rules_v5.json",
        "steps": steps,
    }


SCENARIOS = {
    "identity_basic": scenario_identity_basic,
    "element_limits": scenario_element_limits,
    "profession_mastery": scenario_profession_mastery,
    "essence_path": scenario_essence_path,
    "combat_validation": scenario_combat_validation,
    "combat_antifarm": scenario_combat_antifarm,
    "combat_directions_umbral": scenario_combat_directions_umbral,
    "npc_pipeline": scenario_npc_pipeline,
    "rules_v1_without_combat": scenario_rules_v1_without_combat,
    "essence_scoring_ember": scenario_essence_scoring_ember,
    "essence_decision_path": scenario_essence_decision_path,
    "essence_npc_two_candidates": scenario_essence_npc_two_candidates,
    "discovery_research": scenario_discovery_research,
    "discovery_secret_form": scenario_discovery_secret_form,
}


# ---------------------------------------------------------------- Ausführung ---------
def _derived(svc: CharacterService) -> dict[str, Any]:
    state = svc.state(CHARACTER_ID)
    out: dict[str, Any] = {"eligible_essences": svc.eligible_essences(CHARACTER_ID)}
    if "combat" in svc.rules:
        out["combat_directions"] = reached_directions(state, svc.rules)
        out["style_profile"] = style_profile(state, svc.rules)
    if "discovery" in svc.rules:  # ab rules v5
        out["known_discoveries"] = known_discoveries(state)
        out["discovery_progress"] = {d: discovery_progress(state, svc.rules, d) for d in svc.rules["discovery"]["discoveries"]}
    if "decisions" in svc.rules["essence"]:  # Bewertungsschema (rules v4+)
        out["essence_scores"] = form_scores(state, svc.rules)
        out["essence_profile"] = essence_profile(state, svc.rules)
    return out


def _run(rules_file: str, steps: list[Step]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    svc = CharacterService(rules=load_rules(rules_file))
    results: list[dict[str, Any]] = []
    for etype, payload in steps:
        # Vor dem ersten Schritt existiert der Charakter noch nicht -> leere Sicht
        prior_len = len(svc.log.events(CHARACTER_ID))
        prior = state_hash(svc.state(CHARACTER_ID).parts) if prior_len else None
        try:
            ev = svc.record(CHARACTER_ID, etype, payload)
            results.append({"type": etype, "payload": payload, "expect": "accepted", "seq": ev.seq,
                            "event_hash": ev.hash, "state_sha256": state_hash(svc.state(CHARACTER_ID).parts)})
        except RuleViolation:
            assert len(svc.log.events(CHARACTER_ID)) == prior_len, "abgelehntes Ereignis wurde aufgezeichnet"
            after = state_hash(svc.state(CHARACTER_ID).parts) if prior_len else None
            assert after == prior, "abgelehntes Ereignis veränderte den Zustand"
            results.append({"type": etype, "payload": payload, "expect": "rejected", "state_sha256": after})
    state = svc.state(CHARACTER_ID)
    final = json.loads(canonical_bytes(state.parts))  # kanonische, rein JSON-basierte Kopie
    return results, final, _derived(svc)


def build_vector(name: str) -> dict[str, Any]:
    sc = SCENARIOS[name]()
    results, final, derived = _run(sc["rules_file"], sc["steps"])
    return {
        "format": FORMAT_VERSION,
        "name": name,
        "description": sc["description"],
        "rules_file": sc["rules_file"],
        "rules_sha256": rules_file_sha256(sc["rules_file"]),
        "character_id": CHARACTER_ID,
        "steps": results,
        "final_state": final,
        "final_state_sha256": state_hash(final),
        "derived": derived,
    }


def verify_vector(vec: dict[str, Any]) -> list[str]:
    """Spielt einen Vektor gegen die Referenzimplementierung ab; Rückgabe: Liste von Abweichungen."""
    errs: list[str] = []
    if vec.get("format") != FORMAT_VERSION:
        return [f"unbekanntes Format {vec.get('format')!r}"]
    if rules_file_sha256(vec["rules_file"]) != vec["rules_sha256"]:
        errs.append(f"Regeldatei {vec['rules_file']} hat sich geändert (SHA-256 weicht ab)")
    steps = [(s["type"], s["payload"]) for s in vec["steps"]]
    results, final, derived = _run(vec["rules_file"], steps)
    for i, (want, got) in enumerate(zip(vec["steps"], results)):
        for key in ("expect", "seq", "event_hash", "state_sha256"):
            if want.get(key) != got.get(key):
                errs.append(f"Schritt {i} ({want['type']}): {key} erwartet {want.get(key)!r}, erhalten {got.get(key)!r}")
    if final != vec["final_state"]:
        errs.append("Endzustand weicht ab")
    if state_hash(final) != vec["final_state_sha256"]:
        errs.append("Endzustands-Hash weicht ab")
    if derived != vec["derived"]:
        errs.append("abgeleitete Sichten weichen ab")
    return errs


def render(vec: dict[str, Any]) -> str:
    return json.dumps(vec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("write", "check"):
        print(__doc__)
        return 2
    mode, out = argv[1], Path(argv[2])
    bad = 0
    if mode == "write":
        out.mkdir(parents=True, exist_ok=True)
    for name in SCENARIOS:
        text = render(build_vector(name))
        path = out / f"{name}.json"
        if mode == "write":
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"geschrieben: {path}")
        else:
            if not path.exists():
                print(f"FEHLT: {path}")
                bad += 1
            elif path.read_text(encoding="utf-8") != text:
                print(f"ABWEICHUNG: {path}")
                bad += 1
            else:
                print(f"ok: {path}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
