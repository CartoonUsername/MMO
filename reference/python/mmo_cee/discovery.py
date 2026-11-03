"""Discovery Engine (Charakterseite): Was weiß diese Figur?

Entdeckungen (Rezepte, Techniken, Regionen, Wissen, Technologien) entstehen aus *Beweisen*
(`discovery.evidence_gathered`: eindeutige, vom Server vergebene IDs, je Figur nur einmal) und werden
bei erfüllten Voraussetzungen abgeschlossen (`discovery.made`) oder von anderen gelernt
(`discovery.learned`, nur wenn die Entdeckung teilbar ist). Wer Erster war und wer lehren darf, ist
Weltzustand und liegt in `mmo_world.DiscoveryRegistry`; die CEE speichert nur das Ergebnis je Figur
(Anerkennung `credit`). Der Spielserver löst alle Ereignisse aus (Vertrauensgrenze wie ADR-0003).
Siehe ADR-0009; Inhalte in den Regeln sind Platzhalter.
"""
from __future__ import annotations

from typing import Any

from .engine import CharacterState, Engine
from .errors import CEEError, RuleViolation
from .history import Event
from .professions import ProfessionEngine
from .rules import Rules

CREDITS_MADE = ("pioneer", "discoverer")
EVIDENCE_KEYS = frozenset({"discovery_id", "evidence_id"})
MADE_KEYS = frozenset({"discovery_id", "day", "credit"})
LEARNED_KEYS = frozenset({"discovery_id", "day", "from_character"})


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_discovery_rules(rules: Rules) -> None:
    cfg = rules["discovery"]
    maxw = cfg["max_window_days"]
    if not _is_int(maxw) or maxw <= 0 or not _is_int(cfg["default_pioneer_window_days"]) \
            or not 0 < cfg["default_pioneer_window_days"] <= maxw:
        raise CEEError("discovery: Fensterwerte ungültig (endlich und <= max_window_days)")
    disc = cfg["discoveries"]
    for did, d in disc.items():
        if d["kind"] not in cfg["kinds"]:
            raise CEEError(f"{did}: unbekannte Art")
        ev = d["evidence"]
        if not ev or len(set(ev)) != len(ev) or any(not isinstance(e, str) or not e for e in ev):
            raise CEEError(f"{did}: evidence muss eine nichtleere Liste eindeutiger Strings sein")
        if not isinstance(d["shareable"], bool):
            raise CEEError(f"{did}: shareable muss bool sein")
        w = d.get("pioneer_window_days", cfg["default_pioneer_window_days"])
        if not _is_int(w) or not 0 < w <= maxw:
            raise CEEError(f"{did}: pioneer_window_days muss 1..{maxw} sein (kein dauerhaftes Monopol)")
        req = d["requires"]
        if not _is_int(req.get("min_level", 1)) or req.get("min_level", 1) < 1:
            raise CEEError(f"{did}: min_level ungültig")
        for p, m in req.get("professions", {}).items():
            if p not in rules["professions"]["all"] or not _is_int(m) or m < 1:
                raise CEEError(f"{did}: Berufsvoraussetzung ungültig ({p})")
        for el in req.get("elements_attuned", []):
            if el not in rules["elements"]["all"]:
                raise CEEError(f"{did}: unbekanntes Element {el}")
        for pre in req.get("discoveries", []):
            if pre not in disc or pre == did:
                raise CEEError(f"{did}: ungültige Voraussetzung {pre}")
        if any(not isinstance(x, list) or any(not isinstance(i, str) for i in x) for x in d["grants"].values()):
            raise CEEError(f"{did}: grants müssen Listen von Strings sein")
    # Voraussetzungen müssen einen azyklischen Graphen bilden (sonst wäre Entdecken unmöglich)
    state: dict[str, int] = {}

    def visit(n: str) -> None:
        if state.get(n) == 1:
            raise CEEError(f"Zyklische Voraussetzungen bei {n}")
        if state.get(n) == 2:
            return
        state[n] = 1
        for pre in disc[n]["requires"].get("discoveries", []):
            visit(pre)
        state[n] = 2

    for n in disc:
        visit(n)


def requirements_missing(state: CharacterState, rules: Rules, req: dict[str, Any]) -> list[str]:
    parts = state.parts
    missing: list[str] = []
    if parts["identity"]["level"] < req.get("min_level", 1):
        missing.append(f"level>={req['min_level']}")
    mastery = ProfessionEngine(rules).mastery_level
    for p, m in sorted(req.get("professions", {}).items()):
        if mastery(parts["profession"]["xp"].get(p, 0)) < m:
            missing.append(f"profession:{p}>={m}")
    for el in req.get("elements_attuned", []):
        if el not in parts["element"]["attuned"]:
            missing.append(f"attuned:{el}")
    for d in req.get("discoveries", []):
        if d not in parts["discovery"]["known"]:
            missing.append(f"discovery:{d}")
    return missing


def known_discoveries(state: CharacterState) -> list[str]:
    return sorted(state.parts.get("discovery", {}).get("known", {}))


def discovery_progress(state: CharacterState, rules: Rules, discovery_id: str) -> dict[str, Any]:
    d = rules["discovery"]["discoveries"][discovery_id]
    part = state.parts["discovery"]
    have = list(part["evidence"].get(discovery_id, []))
    missing = requirements_missing(state, rules, d["requires"])
    known = discovery_id in part["known"]
    return {"known": known, "evidence": have, "evidence_needed": len(d["evidence"]),
            "evidence_missing": [e for e in d["evidence"] if e not in have],
            "missing_requirements": missing,
            "ready": (not known) and len(have) == len(d["evidence"]) and not missing}


class DiscoveryEngine(Engine):
    name = "discovery"

    def __init__(self, rules: Rules) -> None:
        super().__init__(rules)
        validate_discovery_rules(rules)
        self.disc = rules["discovery"]["discoveries"]

    def initial(self) -> dict[str, Any]:
        return {"evidence": {}, "known": {}, "last_day": 0}

    # -- Validierung ---------------------------------------------------------------
    def _common(self, state: CharacterState, payload: dict[str, Any], keys: frozenset[str]) -> tuple[str, dict[str, Any]]:
        if set(payload) != keys:
            raise RuleViolation(f"Ungültige Felder (erwartet: {sorted(keys)})")
        did = payload["discovery_id"]
        if not isinstance(did, str) or did not in self.disc:
            raise RuleViolation("Unbekannte Entdeckung")
        if did in state.parts["discovery"]["known"]:
            raise RuleViolation("Entdeckung ist bereits bekannt")
        return did, self.disc[did]

    def _day(self, state: CharacterState, payload: dict[str, Any]) -> None:
        day = payload["day"]
        if not _is_int(day) or day < 0:
            raise RuleViolation("day muss eine nichtnegative ganze Zahl sein")
        if day < state.parts["discovery"]["last_day"]:
            raise RuleViolation("day darf nicht zurückspringen")

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        part = state.parts["discovery"]
        if type == "discovery.evidence_gathered":
            did, d = self._common(state, payload, EVIDENCE_KEYS)
            ev = payload["evidence_id"]
            if not isinstance(ev, str) or ev not in d["evidence"]:
                raise RuleViolation("Unbekannter Beweis für diese Entdeckung")
            if ev in part["evidence"].get(did, []):
                raise RuleViolation("Beweis wurde bereits gesammelt")
            blocked = [p for p in d["requires"].get("discoveries", []) if p not in part["known"]]
            if blocked:
                raise RuleViolation(f"Vorwissen fehlt: {blocked}")
        elif type == "discovery.made":
            did, d = self._common(state, payload, MADE_KEYS)
            self._day(state, payload)
            if payload["credit"] not in CREDITS_MADE:
                raise RuleViolation("Unbekannte Anerkennung")
            if len(part["evidence"].get(did, [])) != len(d["evidence"]):
                raise RuleViolation("Nicht alle Beweise gesammelt")
            missing = requirements_missing(state, self.rules, d["requires"])
            if missing:
                raise RuleViolation(f"Voraussetzungen fehlen: {missing}")
        elif type == "discovery.learned":
            did, d = self._common(state, payload, LEARNED_KEYS)
            self._day(state, payload)
            if not d["shareable"]:
                raise RuleViolation("Diese Entdeckung kann nicht gelehrt werden")
            src = payload["from_character"]
            if not isinstance(src, str) or not src or src == state.character_id:
                raise RuleViolation("from_character ungültig")
            missing = requirements_missing(state, self.rules, d["requires"])
            if missing:
                raise RuleViolation(f"Voraussetzungen fehlen: {missing}")
        else:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")

    # -- Anwendung -----------------------------------------------------------------
    def apply(self, state: CharacterState, event: Event) -> None:
        part, pl = state.parts["discovery"], event.payload
        if event.type == "discovery.evidence_gathered":
            part["evidence"].setdefault(pl["discovery_id"], []).append(pl["evidence_id"])
        elif event.type == "discovery.made":
            part["known"][pl["discovery_id"]] = {"how": "researched", "credit": pl["credit"], "day": pl["day"], "seq": event.seq}
            part["last_day"] = pl["day"]
        else:
            part["known"][pl["discovery_id"]] = {"how": "learned", "credit": "learner", "day": pl["day"],
                                                 "seq": event.seq, "from": pl["from_character"]}
            part["last_day"] = pl["day"]
