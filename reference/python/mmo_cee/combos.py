"""Elementkombinationen (AP 4a, ADR-0042): 36 Paare und 84 Dreier, ungeordnet, klassenabhängige Umsetzung.

Reine, datengetriebene Ableitung aus `element_rules_v1.json` (Platzhalter) und dem Zustand. Schreibt nichts. Wirkungen im Kampf sind
nicht Teil dieses Moduls (AP 4b); hier entsteht der Katalog: welche Kombination was für welche Klasse bedeuten soll, mit Gegenspiel.
"""
from __future__ import annotations

import json
from importlib import resources
from itertools import combinations
from typing import Any

from .engine import CharacterState
from .rules import Rules

ELEMENT_RULES = "element_rules_v1.json"


def load_element_rules(name: str = ELEMENT_RULES) -> dict[str, Any]:
    return json.loads(resources.files("mmo_cee").joinpath("data", name).read_text(encoding="utf-8"))


def combo_key(elements: list[str] | tuple[str, ...]) -> str:
    """Reihenfolgeunabhängiger Schlüssel (`fire+wind`); doppelte oder fehlende Elemente sind ungültig."""
    if len(set(elements)) != len(elements) or not 2 <= len(elements) <= 3:
        raise ValueError("Kombination braucht 2 oder 3 verschiedene Elemente")
    return "+".join(sorted(elements))


def all_combinations(rules: Rules, size: int) -> list[str]:
    return [combo_key(c) for c in combinations(sorted(rules["elements"]["all"]), size)]


def describe(rules: Rules, el: dict[str, Any], elements: list[str] | tuple[str, ...], base_class: str | None) -> dict[str, Any]:
    """Beschreibung einer Kombination, für eine Klasse (oder `None` = alle Klassen). Wirkbereiche der Elemente werden vereint."""
    key = combo_key(elements)
    names = [e for e in key.split("+")]
    domains: list[str] = []
    for e in names:
        for d in el["elements"][e]["domains"]:
            domains.append(d)
    cap = el["limits"]["max_same_domain_per_combination"]
    count: dict[str, int] = {}
    for d in domains:                                   # gleiche Bereiche verstärken sich, aber höchstens bis zur Grenze (kein unbegrenztes Stapeln)
        count[d] = count.get(d, 0) + 1
    order = list(dict.fromkeys(domains))
    classes = [base_class] if base_class else list(el["delivery"])
    return {"key": key, "elements": names, "names": [el["elements"][e]["name"] for e in names], "size": len(names),
            "domains": [{"domain": d, "name": el["domains"][d]["name"], "weight": min(count[d], cap), "counterplay": el["domains"][d]["counterplay"]} for d in order],
            "variants": {c: [el["delivery"][c][d] for d in order] for c in classes if c in el["delivery"]}}


def catalog(rules: Rules, el: dict[str, Any] | None = None) -> dict[str, Any]:
    el = el or load_element_rules()
    return {"elements": {e: {"name": v["name"], "domains": list(v["domains"])} for e, v in el["elements"].items()},
            "domains": el["domains"], "pairs": [describe(rules, el, k.split("+"), None) for k in all_combinations(rules, 2)],
            "triples": [describe(rules, el, k.split("+"), None) for k in all_combinations(rules, 3)], "limits": el["limits"]}


def unlocked(state: CharacterState, rules: Rules, el: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Kombinationen aus den geprägten Elementen: jedes Paar (frei kombinierbar) und – nur mit drei Prägungen – die Dreierkombination."""
    el = el or load_element_rules()
    att = sorted(state.parts["element"]["attuned"])
    cls = state.parts["identity"]["base_class"]
    out = [describe(rules, el, list(c), cls) for c in combinations(att, 2)]
    if len(att) >= el["limits"]["triple_requires_attuned"]:
        out.append(describe(rules, el, att[:3], cls))
    return out
