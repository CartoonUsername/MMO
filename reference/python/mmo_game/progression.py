"""Progression aus dem Spielgeschehen (AP 3, ADR-0041): reine Berechnungen. Das Aufzeichnen in die CEE macht `GameServer`.

Grundsatz (Blueprint §70): Jede Quelle hat einen Grund und eine Grenze; triviale Wiederholung bringt kaum etwas. Alle Zahlen sind Platzhalter
in `game_rules_v3.json`."""
from __future__ import annotations

from typing import Any


def fight_xp(P: dict[str, Any], sim: dict[str, Any], types: list[str], factor_permille: dict[str, int]) -> int:
    """Erfahrung eines Sieges: Gegnerstufe × Faktor, je Art mit dem Beutefaktor (nimmt bei Wiederholung am selben Tag ab)."""
    total = 0
    for t in types:
        total += sim["opponents"][t]["level"] * P["fight_xp_per_level"] * factor_permille.get(t, 1000) // 1000
    return total


def element_exposure(P: dict[str, Any], sim: dict[str, Any], types: list[str], factor_permille: dict[str, int]) -> dict[str, int]:
    """Exposition gegenüber dem Element besiegter Gegner."""
    out: dict[str, int] = {}
    for t in types:
        el = sim["opponents"][t].get("element")
        n = P["fight_element_exposure"] * factor_permille.get(t, 1000) // 1000
        if el and n > 0:
            out[el] = out.get(el, 0) + n
    return out


def skill_exposure(P: dict[str, Any], commands: list[str], used_today: int) -> dict[str, int]:
    """Exposition durch eigene Elementfähigkeiten: je Einsatz ein fester Betrag; Grenze je Kampf und je Tag."""
    cap = min(P["skill_exposure_max_per_fight"], max(0, P["skill_exposure_daily_cap"] - used_today))
    out: dict[str, int] = {}
    left = cap
    for cmd in commands:
        spec = P["skill_exposure"].get(cmd)
        if spec and left > 0:
            out[spec[0]] = out.get(spec[0], 0) + spec[1]
            left -= 1
    return out


def gather_gain(P: dict[str, Any], item: str, gathered_today: int) -> tuple[str, int] | None:
    """Berufserfahrung für das Sammeln; nach dem Tageslimit nur noch ein Bruchteil."""
    spec = P["gather"].get(item.split("@")[0])
    if spec is None:
        return None
    xp = spec[1] if gathered_today < P["gather_daily_full"] else spec[1] * P["gather_reduced_permille"] // 1000
    return (spec[0], xp) if xp > 0 else None
