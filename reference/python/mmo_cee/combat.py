"""Combat Development Engine: Kampfverhalten -> mehrdimensionale Entwicklung.

Grundsätze (siehe ADR-0003):
* Eingabe ist ausschließlich ein serverseitig bestätigter Begegnungsbericht
  (`combat.encounter_resolved`) mit *beobachteten Aktionszählern*. Punkte
  berechnet allein diese Engine aus den versionierten Regeln; ein Client kann
  keine Fortschrittspunkte vorgeben.
* Jede Begegnung (`encounter_id`) zählt je Charakter genau einmal.
* Abnahmegrenzen gegen Farming: Plausibilität der Aktionsraten, abnehmende Erträge
  gegen wiederholte Gegnertypen, Relevanz (zu schwache Gegner), Tageslimits.
* Alle Berechnungen in Ganzzahlen (Promille) -> deterministisch und portierbar.
* Entwicklungsrichtungen sind abgeleitet, nicht exklusiv und nie zurücknehmbar-zwingend:
  Punkte sinken nie, jede Dimension ist jederzeit trainierbar.
* Dimensionen, Aktionen und Richtungen sind VORLÄUFIGE Vorschläge (rules_v2.json).
"""
from __future__ import annotations

from typing import Any

from .engine import CharacterState, Engine
from .errors import CEEError, RuleViolation
from .history import Event
from .rules import Rules

ENCOUNTER_EVENT = "combat.encounter_resolved"
LOADOUT_EVENT = "combat.loadout_set"  # ab rules_v9 (Fähigkeiten, ADR-0020)
_LOADOUT_KEYS = frozenset({"abilities", "day"})
_REQUIRE_KEYS = frozenset({"direction", "tier", "elements_attuned", "min_level", "essence_form"})
_PAYLOAD_KEYS = frozenset(
    {"encounter_id", "opponent_type", "opponent_level", "outcome", "duration_s", "day", "actions"}
)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_combat_rules(cfg: dict[str, Any]) -> None:
    """Prüft die Konsistenz der Regeldaten (Konfigurationsfehler -> CEEError)."""
    dims = set(cfg["dimensions"])
    if not dims:
        raise CEEError("combat.dimensions darf nicht leer sein")
    for name, a in cfg["actions"].items():
        if not a["weights"] or not set(a["weights"]) <= dims:
            raise CEEError(f"Aktion {name}: unbekannte oder fehlende Dimension")
        if any(not _is_int(w) or w <= 0 for w in a["weights"].values()) or a["max_per_minute"] <= 0:
            raise CEEError(f"Aktion {name}: Gewichte/Rate müssen positiv sein")
    for name, d in cfg["directions"].items():
        if not d["weights"] or not set(d["weights"]) <= dims:
            raise CEEError(f"Richtung {name}: unbekannte oder fehlende Dimension")
        t = d["tier_thresholds"]
        if not t or any(b <= a for a, b in zip(t, t[1:])) or t[0] <= 0:
            raise CEEError(f"Richtung {name}: Schwellen müssen streng aufsteigend und positiv sein")
    daily = cfg["daily"]
    if not 0 < daily["full_cap"] <= daily["hard_cap"] or not 0 <= daily["reduced_permille"] <= 1000:
        raise CEEError("combat.daily inkonsistent")
    if not cfg["repeat_opponent_permille"] or not cfg["outcome_permille"]:
        raise CEEError("combat: repeat_opponent_permille/outcome_permille dürfen nicht leer sein")
    if "abilities" in cfg:
        _validate_abilities(cfg)


def _validate_abilities(cfg: dict[str, Any]) -> None:
    ab = {k: v for k, v in cfg["abilities"].items() if not k.startswith("_")}
    if not ab:
        raise CEEError("combat.abilities darf nicht leer sein")
    lo = cfg["loadout"]
    base = lo["base_commands"]
    if not base or len(set(base)) != len(base) or "flee" not in base:
        raise CEEError("loadout.base_commands muss eindeutig sein und flee enthalten")
    slots = lo["slots_by_level"]
    if (not slots or slots[0][0] != 1 or any(not _is_int(l) or not _is_int(n) or n < 1 for l, n in slots)
            or any(b[0] <= a[0] or b[1] < a[1] for a, b in zip(slots, slots[1:]))):
        raise CEEError("loadout.slots_by_level: bei Stufe 1 beginnen, Stufen aufsteigend, Plätze nicht fallend, mindestens 1")
    commands: dict[str, str] = {}
    for name, a in ab.items():
        req = a["requires"]
        if not isinstance(name, str) or not name or set(req) - _REQUIRE_KEYS:
            raise CEEError(f"Fähigkeit {name}: ungültige Voraussetzungen")
        if "direction" in req:
            d = cfg["directions"].get(req["direction"])
            if d is None or not _is_int(req.get("tier")) or not 1 <= req["tier"] <= len(d["tier_thresholds"]):
                raise CEEError(f"Fähigkeit {name}: Richtung/Stufe ungültig")
        elif "tier" in req:
            raise CEEError(f"Fähigkeit {name}: tier braucht direction")
        if "min_level" in req and (not _is_int(req["min_level"]) or req["min_level"] < 1):
            raise CEEError(f"Fähigkeit {name}: min_level ungültig")
        if a["command"] is not None:
            if a["command"] in base or a["command"] in commands:
                raise CEEError(f"Fähigkeit {name}: Befehl {a['command']!r} ist Grundbefehl oder schon vergeben")
            commands[a["command"]] = name


class CombatEngine(Engine):
    name = "combat"

    def __init__(self, rules: Rules) -> None:
        super().__init__(rules)
        self.cfg = rules["combat"]
        validate_combat_rules(self.cfg)

    def initial(self) -> dict[str, Any]:
        zero = {d: 0 for d in self.cfg["dimensions"]}
        part = {
            "points": dict(zero),
            "encounters": {},  # encounter_id -> seq des bestätigten Ereignisses
            "daily": {"day": 0, "points": dict(zero), "opponents": {}},
            "stats": {o: 0 for o in self.cfg["outcome_permille"]},
        }
        if "abilities" in self.cfg:  # ab rules_v9
            part["loadout"], part["loadout_day"] = [], 0
        return part

    # ---- Validierung -------------------------------------------------------
    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        if type == LOADOUT_EVENT and "abilities" in self.cfg:
            return self._validate_loadout(state, payload)
        if type != ENCOUNTER_EVENT:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")
        cfg, part = self.cfg, state.parts["combat"]
        keys = set(payload)
        if keys != _PAYLOAD_KEYS:
            extra, missing = sorted(keys - _PAYLOAD_KEYS), sorted(_PAYLOAD_KEYS - keys)
            raise RuleViolation(f"Ungültige Felder (unzulässig: {extra}, fehlend: {missing})")

        eid = payload["encounter_id"]
        if not isinstance(eid, str) or not 1 <= len(eid) <= 64:
            raise RuleViolation("encounter_id muss ein String mit 1-64 Zeichen sein")
        if eid in part["encounters"]:
            raise RuleViolation("Begegnung wurde bereits gewertet")
        otype = payload["opponent_type"]
        if not isinstance(otype, str) or not 1 <= len(otype) <= 64:
            raise RuleViolation("opponent_type muss ein String mit 1-64 Zeichen sein")
        enc = cfg["encounter"]
        lvl = payload["opponent_level"]
        if not _is_int(lvl) or not 1 <= lvl <= enc["max_opponent_level"]:
            raise RuleViolation("opponent_level außerhalb des gültigen Bereichs")
        if payload["outcome"] not in cfg["outcome_permille"]:
            raise RuleViolation("Unbekanntes Begegnungsergebnis")
        dur = payload["duration_s"]
        if not _is_int(dur) or not enc["min_duration_s"] <= dur <= enc["max_duration_s"]:
            raise RuleViolation("duration_s außerhalb des gültigen Bereichs")
        day = payload["day"]
        if not _is_int(day) or day < 0:
            raise RuleViolation("day muss eine nichtnegative ganze Zahl sein")
        if day < part["daily"]["day"]:
            raise RuleViolation("day darf nicht zurückspringen")

        actions = payload["actions"]
        if not isinstance(actions, dict) or not actions:
            raise RuleViolation("actions darf nicht leer sein")
        for name, count in actions.items():
            if name not in cfg["actions"]:
                raise RuleViolation(f"Unbekannte Aktion: {name}")
            if not _is_int(count) or count <= 0:
                raise RuleViolation("Aktionszähler müssen positive ganze Zahlen sein")
            limit = cfg["actions"][name]["max_per_minute"] * dur // 60 + enc["burst_allowance"]
            if count > limit:
                raise RuleViolation(f"Unplausible Aktionsrate: {name}={count} > {limit}")

    # ---- Berechnung (rein, deterministisch) ----------------------------------
    def _validate_loadout(self, state: CharacterState, p: dict[str, Any]) -> None:
        part = state.parts["combat"]
        if set(p) != _LOADOUT_KEYS:
            raise RuleViolation(f"Ungültige Felder (unzulässig: {sorted(set(p) - _LOADOUT_KEYS)}, fehlend: {sorted(_LOADOUT_KEYS - set(p))})")
        day, chosen = p["day"], p["abilities"]
        if not _is_int(day) or day < 0:
            raise RuleViolation("day muss eine nichtnegative ganze Zahl sein")
        if day < part["loadout_day"]:
            raise RuleViolation("day darf nicht zurückspringen")
        if not isinstance(chosen, list) or any(not isinstance(a, str) for a in chosen):
            raise RuleViolation("abilities muss eine Liste von Namen sein")
        if len(set(chosen)) != len(chosen):
            raise RuleViolation("Fähigkeit doppelt gewählt")
        slots = loadout_slots(state, self.rules)
        if len(chosen) > slots:
            raise RuleViolation(f"Nur {slots} Plätze verfügbar")
        for a in chosen:
            if a not in self.cfg["abilities"] or a.startswith("_"):
                raise RuleViolation(f"Unbekannte Fähigkeit: {a}")
            missing = ability_blockers(state, self.rules, a)
            if missing:
                raise RuleViolation(f"Fähigkeit {a} nicht freigeschaltet: {missing}")

    def _today(self, part: dict[str, Any], day: int) -> tuple[dict[str, int], dict[str, int]]:
        d = part["daily"]
        if day > d["day"]:
            return {x: 0 for x in self.cfg["dimensions"]}, {}
        return dict(d["points"]), dict(d["opponents"])

    def compute_gains(self, state: CharacterState, payload: dict[str, Any]) -> dict[str, int]:
        cfg, part = self.cfg, state.parts["combat"]
        today, opponents = self._today(part, payload["day"])

        raw = {d: 0 for d in cfg["dimensions"]}
        for name, count in payload["actions"].items():
            for dim, w in cfg["actions"][name]["weights"].items():
                raw[dim] += count * w

        repeats = cfg["repeat_opponent_permille"]
        repeat_pm = repeats[min(opponents.get(payload["opponent_type"], 0), len(repeats) - 1)]
        outcome_pm = cfg["outcome_permille"][payload["outcome"]]
        rel = cfg["relevance"]
        level = state.parts["identity"]["level"]
        relevance_pm = rel["trivial_permille"] if payload["opponent_level"] + rel["trivial_level_gap"] < level else 1000

        cap = cfg["daily"]
        gains: dict[str, int] = {}
        for dim, r in raw.items():
            g = r * cfg["point_scale"] * outcome_pm * relevance_pm * repeat_pm // 10**9
            p = today[dim]
            full = min(g, max(0, cap["full_cap"] - p))
            reduced = (g - full) * cap["reduced_permille"] // 1000
            room = max(0, cap["hard_cap"] - p - full)
            gains[dim] = full + min(reduced, room)
        return gains

    def apply(self, state: CharacterState, event: Event) -> None:
        part, pl = state.parts["combat"], event.payload
        if event.type == LOADOUT_EVENT:
            part["loadout"], part["loadout_day"] = list(pl["abilities"]), pl["day"]
            return
        gains = self.compute_gains(state, pl)
        today, opponents = self._today(part, pl["day"])
        for dim, g in gains.items():
            part["points"][dim] += g
            today[dim] += g
        opponents[pl["opponent_type"]] = opponents.get(pl["opponent_type"], 0) + 1
        part["daily"] = {"day": pl["day"], "points": today, "opponents": opponents}
        part["encounters"][pl["encounter_id"]] = event.seq
        part["stats"][pl["outcome"]] += 1


# ---- Abgeleitete Sichten (keine eigenen Ereignisse, keine eigene Wahrheit) ----------
def direction_scores(state: CharacterState, rules: Rules) -> dict[str, int]:
    points = state.parts["combat"]["points"]
    return {
        name: sum(points[dim] * w // 1000 for dim, w in d["weights"].items())
        for name, d in rules["combat"]["directions"].items()
    }


def reached_directions(state: CharacterState, rules: Rules) -> dict[str, int]:
    """Richtung -> erreichte Stufe (>= 1). Nicht exklusiv: beliebig viele gleichzeitig."""
    scores = direction_scores(state, rules)
    result = {}
    for name, d in rules["combat"]["directions"].items():
        tier = sum(1 for t in d["tier_thresholds"] if scores[name] >= t)
        if tier:
            result[name] = tier
    return result


def style_profile(state: CharacterState, rules: Rules) -> dict[str, int]:
    """Anteil jeder Dimension an der Gesamtentwicklung in Promille (ganzzahlig, abgerundet)."""
    points = state.parts["combat"]["points"]
    total = sum(points.values())
    return {d: (p * 1000 // total if total else 0) for d, p in points.items()}


# ---- Fähigkeiten (abgeleitet aus der Entwicklung; ab rules_v9) --------------------------
def ability_catalog(rules: Rules) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in rules["combat"].get("abilities", {}).items() if not k.startswith("_")}


def ability_blockers(state: CharacterState, rules: Rules, ability: str) -> list[str]:
    """Was einer Fähigkeit zur Freischaltung noch fehlt (leer = freigeschaltet). Nur Wachstumsgrößen -> dauerhaft."""
    req = ability_catalog(rules)[ability]["requires"]
    out: list[str] = []
    if "direction" in req:
        tier = reached_directions(state, rules).get(req["direction"], 0)
        if tier < req["tier"]:
            out.append(f"direction:{req['direction']}>={req['tier']}")
    attuned = state.parts["element"]["attuned"]
    out += [f"attuned:{e}" for e in req.get("elements_attuned", []) if e not in attuned]
    if "min_level" in req and state.parts["identity"]["level"] < req["min_level"]:
        out.append(f"level>={req['min_level']}")
    if "essence_form" in req and state.parts["essence"]["form"] != req["essence_form"]:
        out.append(f"form:{req['essence_form']}")
    return out


def unlocked_abilities(state: CharacterState, rules: Rules) -> list[str]:
    return sorted(a for a in ability_catalog(rules) if not ability_blockers(state, rules, a))


def ability_progress(state: CharacterState, rules: Rules) -> dict[str, dict[str, Any]]:
    cat = ability_catalog(rules)
    return {a: {"kind": d["kind"], "command": d["command"], "missing": ability_blockers(state, rules, a),
                "equipped": a in state.parts["combat"].get("loadout", [])} for a, d in cat.items()}


def loadout_slots(state: CharacterState, rules: Rules) -> int:
    level = state.parts["identity"]["level"]
    return max((n for lv, n in rules["combat"]["loadout"]["slots_by_level"] if level >= lv), default=0)


def allowed_commands(state: CharacterState, rules: Rules) -> list[str]:
    """Simulationsbefehle, die die Figur nutzen darf: Grundbefehle plus die der ausgerüsteten (freigeschalteten) Fähigkeiten."""
    cfg = rules["combat"]
    cat = ability_catalog(rules)
    extra = {cat[a]["command"] for a in state.parts["combat"]["loadout"] if cat[a]["command"] is not None}
    return sorted(set(cfg["loadout"]["base_commands"]) | extra)
