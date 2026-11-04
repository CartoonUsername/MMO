"""Gegnerfähigkeiten: Regeln, Prüfung und reproduzierbarer Baukasten (ADR-0032). Die Wirkung im Kampf folgt in der Simulation (ADR-0033).

* Gegnervorlagen (`opponents`) tragen Rolle, Element, feste Fähigkeiten (`abilities`), einen Zufallsbaukasten (`pool`) mit Gefahrengrenze
  (`danger_cap`) und optional Phasen (`phases`, ab einem Lebensanteil kommen Fähigkeiten hinzu und der Angriffstakt wird schneller).
* Der „Zufall" ist reproduzierbar: `roll_abilities` bestimmt die Zusatzfähigkeiten allein aus (Gegnerart, Spawn-Punkt, Tag) mit SHA-256 und
  ganzzahliger Rechnung; gleiche Eingaben liefern in jeder Sprache dieselbe Auswahl (Golden Vectors `reference/golden_enemies`).
* Jede Fähigkeit mit Wirkung auf Spieler hat eine Vorwarnzeit und mindestens eine Antwort der Spieler; Bosse werden nicht gewürfelt.
Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .errors import SimError

KINDS = ("slam", "area", "state", "cast", "shield", "heal_ally", "buff_allies", "summon")
STATES = ("stun", "slow", "burn")
ROLES = ("swarm", "brute", "caster", "support", "guardian", "controller", "summoner", "elite", "boss")
ELEMENTS = ("fire", "water", "shadow", "light", "wind", "earth", "electric", "ice", "nature")
BREAKERS = ("parry", "precise_hit", "heavy_hit")


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def ability_table(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return dict(cfg.get("enemy_abilities", {}).get("abilities", {}))


def validate_enemy_rules(cfg: dict[str, Any]) -> None:
    ea = cfg["enemy_abilities"]
    answers = ea["answers"]
    if not answers or len(set(answers)) != len(answers) or any(not isinstance(a, str) for a in answers):
        raise SimError("enemy_abilities.answers ungültig")
    mc = ea.get("min_attack_cycle")
    if not _is_int(mc) or mc < 1:
        raise SimError("enemy_abilities.min_attack_cycle muss eine positive ganze Zahl sein")
    for name, o in cfg["opponents"].items():
        if o["attack_interval"] > 0 and o["attack_interval"] + o["windup"] < mc:
            raise SimError(f"Gegner {name}: Angriffstakt + Vorwarnzeit unter dem Boden min_attack_cycle")
    table = ea["abilities"]
    if not table:
        raise SimError("enemy_abilities.abilities darf nicht leer sein")
    for name, a in table.items():
        w = f"Fähigkeit {name}"
        if not isinstance(name, str) or not name.isidentifier() or a.get("kind") not in KINDS:
            raise SimError(f"{w}: Name oder Art ungültig")
        if not _is_int(a.get("windup")) or a["windup"] < 1:
            raise SimError(f"{w}: windup (Vorwarnung) muss >= 1 sein")
        if not _is_int(a.get("cooldown")) or a["cooldown"] < 1 or not _is_int(a.get("danger")) or a["danger"] < 0:
            raise SimError(f"{w}: cooldown/danger ungültig")
        if not isinstance(a.get("interruptible"), bool):
            raise SimError(f"{w}: interruptible fehlt")
        ans = a.get("answers")
        if not ans or len(set(ans)) != len(ans) or any(x not in answers for x in ans):
            raise SimError(f"{w}: mindestens eine bekannte Antwort erforderlich")
        if a["interruptible"] and "interrupt" not in ans and "kill_caster" not in ans:
            raise SimError(f"{w}: unterbrechbar, aber ohne Antwort 'interrupt'/'kill_caster'")
        if "rollable" in a and not isinstance(a["rollable"], bool):
            raise SimError(f"{w}: rollable muss true/false sein")
        if "group" in a and (not isinstance(a["group"], str) or not a["group"]):
            raise SimError(f"{w}: group ungültig")
        kind = a["kind"]
        pos = ("damage_permille", "ticks", "tick_damage", "interval", "absorb", "amount_permille", "attack_interval_permille", "count", "max_alive")
        for key in pos:
            if key in a and (not _is_int(a[key]) or a[key] < 1):
                raise SimError(f"{w}: {key} muss eine positive ganze Zahl sein")
        if kind in ("slam", "area") and "damage_permille" not in a:
            raise SimError(f"{w}: damage_permille fehlt")
        if kind == "state":
            if a.get("state") not in STATES or "ticks" not in a or "damage_permille" not in a:
                raise SimError(f"{w}: state/ticks/damage_permille erforderlich")
        if kind == "cast":
            if a.get("state") != "burn" or not all(k in a for k in ("ticks", "interval", "tick_damage")) or not a["interruptible"]:
                raise SimError(f"{w}: Zauber braucht state=burn, ticks, interval, tick_damage und muss unterbrechbar sein")
        if kind == "shield":
            br = a.get("breakable_by")
            if "absorb" not in a or "ticks" not in a or not br or any(b not in BREAKERS for b in br) or "break_shield" not in ans:
                raise SimError(f"{w}: Schild braucht absorb, ticks, breakable_by (bekannt) und die Antwort break_shield")
        if kind == "heal_ally" and "amount_permille" not in a:
            raise SimError(f"{w}: amount_permille fehlt")
        if kind == "buff_allies" and (a.get("buff") != "haste" or "attack_interval_permille" not in a or "ticks" not in a):
            raise SimError(f"{w}: buff=haste, attack_interval_permille, ticks erforderlich")
        if kind == "summon":
            s = a.get("summon")
            if s not in cfg["opponents"] or "count" not in a or "max_alive" not in a or a["max_alive"] < a["count"]:
                raise SimError(f"{w}: summon/count/max_alive ungültig")
            if any(table.get(x, {}).get("kind") == "summon" for x in cfg["opponents"][s].get("abilities", [])):
                raise SimError(f"{w}: beschworene Gegner dürfen nicht selbst beschwören")
    for name, o in cfg["opponents"].items():
        _validate_template(name, o, table, cfg)


def _validate_template(name: str, o: dict[str, Any], table: dict[str, Any], cfg: dict[str, Any]) -> None:
    keys = {"role", "element", "abilities", "pool", "danger_cap", "phases"}
    if not keys & set(o):
        return                                              # alte Vorlage ohne Fähigkeiten
    w = f"Gegner {name}"
    if o.get("role") not in ROLES or o.get("element") not in ELEMENTS:
        raise SimError(f"{w}: Rolle/Element ungültig")
    fixed = o.get("abilities", [])
    if not isinstance(fixed, list) or len(set(fixed)) != len(fixed) or any(a not in table for a in fixed):
        raise SimError(f"{w}: abilities müssen eindeutige bekannte Fähigkeiten sein")
    pool = o.get("pool", {"count": [0, 0], "entries": {}})
    lo, hi = pool["count"]
    entries = pool["entries"]
    if not (_is_int(lo) and _is_int(hi) and 0 <= lo <= hi) or hi > len(entries):
        raise SimError(f"{w}: pool.count ungültig")
    for a, wt in entries.items():
        if a not in table or table[a].get("rollable", True) is False or not _is_int(wt) or wt < 1 or a in fixed:
            raise SimError(f"{w}: pool-Eintrag {a} ungültig (unbekannt, nicht würfelbar, Gewicht oder schon fest)")
    cap = o.get("danger_cap", 0)
    if not _is_int(cap) or cap < 0:
        raise SimError(f"{w}: danger_cap ungültig")
    if o["role"] == "boss" and (hi != 0 or entries):
        raise SimError(f"{w}: Bosse werden nicht gewürfelt")
    base = sum(table[a]["danger"] for a in fixed)
    if base > cap:
        raise SimError(f"{w}: feste Fähigkeiten überschreiten die Gefahrengrenze")
    phases = o.get("phases", [])
    last = 1000
    all_phase = set(fixed)
    for ph in phases:
        at = ph.get("at_permille")
        if not _is_int(at) or not 0 < at < last or any(a not in table for a in ph.get("add", [])):
            raise SimError(f"{w}: Phase ungültig (absteigende Schwellen 1..999, bekannte Fähigkeiten)")
        pm = ph.get("attack_interval_permille", 1000)
        if not _is_int(pm) or not 100 <= pm <= 1000:
            raise SimError(f"{w}: attack_interval_permille 100..1000")
        for a in ph.get("add", []):
            if a in all_phase:
                raise SimError(f"{w}: Fähigkeit {a} kommt doppelt vor")
            all_phase.add(a)
        last = at


# -- reproduzierbarer Baukasten -----------------------------------------------------------------
def _stream(seed: bytes):
    i = 0
    while True:
        d = hashlib.sha256(seed + b"|" + str(i).encode()).digest()
        for k in range(4):
            yield int.from_bytes(d[8 * k:8 * k + 8], "big")
        i += 1


def roll_abilities(cfg: dict[str, Any], enemy_type: str, spawn_id: str, day: int) -> list[str]:
    """Feste Fähigkeiten plus die gewürfelten Zusatzfähigkeiten dieser Vorlage an diesem Spawn-Punkt an diesem Tag.

    Zufallsstrom: SHA-256 über `"<Art>|<Spawn>|<Tag>"`, daraus 64-Bit-Zahlen (big-endian). Ablauf: Anzahl = lo + z % (hi - lo + 1);
    je Zug unter den noch erlaubten Einträgen (Gefahrengrenze, Gruppe) nach Gewicht wählen (z % Gesamtgewicht, Einträge in Dateireihenfolge).
    """
    o = cfg["opponents"].get(enemy_type)
    if o is None or not isinstance(spawn_id, str) or not spawn_id or not _is_int(day) or day < 0:
        raise SimError("Gegnerart, Spawn-Punkt und Tag ungültig")
    table = ability_table(cfg)
    fixed = list(o.get("abilities", []))
    pool = o.get("pool")
    if not pool or pool["count"][1] == 0:
        return fixed
    z = _stream(f"{enemy_type}|{spawn_id}|{day}".encode("utf-8"))
    lo, hi = pool["count"]
    count = lo + next(z) % (hi - lo + 1)
    chosen = list(fixed)
    danger = sum(table[a]["danger"] for a in chosen)
    groups = {table[a]["group"] for a in chosen if table[a].get("group")}
    remaining = dict(pool["entries"])
    rolled = 0
    while rolled < count:
        ok = {a: w for a, w in remaining.items()
              if danger + table[a]["danger"] <= o["danger_cap"] and table[a].get("group") not in groups}
        if not ok:
            break
        r = next(z) % sum(ok.values())
        for a, w in ok.items():
            if r < w:
                break
            r -= w
        chosen.append(a)
        danger += table[a]["danger"]
        if table[a].get("group"):
            groups.add(table[a]["group"])
        del remaining[a]
        rolled += 1
    return chosen


def effective_interval(cfg: dict[str, Any], enemy_type: str, factor: int) -> int:
    """Angriffstakt (Ticks) nach Phasen-/Verstärkungsfaktor in Promille, nie unter dem Boden `min_attack_cycle` (abzüglich Vorwarnzeit)."""
    o = cfg["opponents"][enemy_type]
    return max(o["attack_interval"] * factor // 1000, cfg["enemy_abilities"]["min_attack_cycle"] - o["windup"])


def abilities_at(cfg: dict[str, Any], enemy_type: str, base: list[str], hp_permille: int) -> tuple[list[str], int]:
    """Fähigkeiten und Angriffstakt-Faktor (Promille, kleiner = schneller) einer Vorlage bei einem Lebensanteil (1000 = voll).
    Phasen gelten, sobald der Anteil unter die Schwelle fällt (`hp_permille < at_permille`); sie addieren sich."""
    out = list(base)
    factor = 1000
    for ph in cfg["opponents"][enemy_type].get("phases", []):
        if hp_permille < ph["at_permille"]:
            out += [a for a in ph.get("add", []) if a not in out]
            factor = ph.get("attack_interval_permille", 1000)
    return out, factor
