"""Essence Engine: Wesensentwicklung. Start als Mensch; Annahme per Prüfung + Entscheidung, dauerhaft.

Zwei Regelschemata je Wesensform (beide gültig, damit alte Regelversionen unverändert bleiben):
* Legacy (rules v1-v3): harte Voraussetzungen (`attuned_all`, `professions`, `combat_directions`, `min_level`).
* Bewertung (rules v4+): gewichtete Signale aus der Spielhistorie (`signals`, `threshold`), serverseitig
  vergebene Entscheidungen (`essence.decision_made`) und Vor-/Nachteile (`modifiers`). Siehe ADR-0007.

Alle Zahlen in Promille/Punkten als Ganzzahlen; Zustände sind reine Ableitungen aus dem Log.
"""
from __future__ import annotations

from typing import Any

from .combat import direction_scores, reached_directions
from .engine import CharacterState, Engine
from .errors import CEEError, RuleViolation
from .history import Event
from .professions import ProfessionEngine
from .rules import Rules

SIGNAL_KINDS = ("element_attuned", "element_affinity", "combat_direction", "profession", "decision", "discovery")
DECISION_KEYS = frozenset({"decision_id", "choice"})


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


# ------------------------------------------------------------------ Regelprüfung -------
def parse_signal(key: str) -> tuple[str, str, str | None]:
    parts = key.split(":")
    if parts[0] not in SIGNAL_KINDS or len(parts) != (3 if parts[0] == "decision" else 2) or not all(parts):
        raise CEEError(f"Ungültiges Signal: {key!r}")
    return parts[0], parts[1], (parts[2] if len(parts) == 3 else None)


def validate_essence_rules(rules: Rules) -> None:
    """Prüft Bewertungsformen auf Konsistenz und mechanische Mindestanforderungen.

    Leitplanken (keine Balancing-Aussage): Eine Form braucht mindestens zwei Belege (kein einzelnes
    Signal darf die Schwelle allein erreichen), jede Form hat Vor- und Nachteile, und deren Summen
    liegen innerhalb einer Bandbreite (Wettbewerbsfähigkeit der Pfade, Vorschlag).
    """
    cfg = rules["essence"]
    if not any("signals" in f for f in cfg["forms"].values()):
        return
    caps = cfg["signal_caps"]
    if not all(_is_int(caps[k]) and caps[k] > 0 for k in ("element_affinity", "direction_score", "profession_mastery")):
        raise CEEError("essence.signal_caps müssen positive ganze Zahlen sein")
    decisions = cfg.get("decisions", {})
    for did, d in decisions.items():
        if len(d["options"]) < 2 or len(set(d["options"])) != len(d["options"]):
            raise CEEError(f"Entscheidung {did}: mindestens zwei verschiedene Optionen nötig")
    directions = rules["combat"]["directions"] if "combat" in rules else {}
    for form, f in cfg["forms"].items():
        if "signals" not in f:
            continue
        weights = f["signals"]
        if not weights or any(not _is_int(w) or w <= 0 for w in weights.values()):
            raise CEEError(f"Form {form}: Gewichte müssen positive ganze Zahlen sein")
        if not _is_int(f["threshold"]) or not 0 < f["threshold"] <= sum(weights.values()):
            raise CEEError(f"Form {form}: threshold nicht erreichbar")
        if max(weights.values()) >= f["threshold"]:
            raise CEEError(f"Form {form}: ein einzelnes Signal darf die Schwelle nicht allein erreichen")
        for key in weights:
            kind, name, choice = parse_signal(key)
            known = {
                "element_attuned": rules["elements"]["all"], "element_affinity": rules["elements"]["all"],
                "combat_direction": directions, "profession": rules["professions"]["all"], "decision": decisions,
                "discovery": rules["discovery"]["discoveries"] if "discovery" in rules else {},
            }[kind]
            if name not in known:
                raise CEEError(f"Form {form}: unbekanntes Signalziel {key!r}")
            if kind == "decision" and choice not in decisions[name]["options"]:
                raise CEEError(f"Form {form}: unbekannte Option in {key!r}")
        for need in f.get("requires_discoveries", []):
            if "discovery" not in rules or need not in rules["discovery"]["discoveries"]:
                raise CEEError(f"Form {form}: unbekannte Entdeckung {need!r} in requires_discoveries")
        adv, dis = f["modifiers"]["advantages"], f["modifiers"]["disadvantages"]
        if not adv or not dis:
            raise CEEError(f"Form {form}: Vor- UND Nachteile erforderlich")
        if any(not _is_int(v) or v <= 0 for v in [*adv.values(), *dis.values()]):
            raise CEEError(f"Form {form}: Modifikatorwerte müssen positive ganze Zahlen sein")
        if abs(sum(adv.values()) - sum(dis.values())) > cfg["balance"]["max_net_imbalance"]:
            raise CEEError(f"Form {form}: Vor-/Nachteile außerhalb der Bandbreite")


# ------------------------------------------------------------------ Abgeleitete Sichten --
def signal_value(state: CharacterState, rules: Rules, key: str) -> int:
    """Wert eines Signals in Promille (0..1000), rein aus dem Zustand abgeleitet."""
    kind, name, choice = parse_signal(key)
    caps = rules["essence"]["signal_caps"]
    if kind == "element_attuned":
        return 1000 if name in state.parts["element"]["attuned"] else 0
    if kind == "element_affinity":
        return min(1000, state.parts["element"]["affinity"][name] * 1000 // caps["element_affinity"])
    if kind == "combat_direction":
        if "combat" not in state.parts:
            return 0
        return min(1000, direction_scores(state, rules)[name] * 1000 // caps["direction_score"])
    if kind == "profession":
        xp = state.parts["profession"]["xp"].get(name, 0)
        return min(1000, ProfessionEngine(rules).mastery_level(xp) * 1000 // caps["profession_mastery"])
    if kind == "discovery":
        return 1000 if name in state.parts.get("discovery", {}).get("known", {}) else 0
    return 1000 if state.parts["essence"].get("decisions", {}).get(name) == choice else 0


def form_scores(state: CharacterState, rules: Rules) -> dict[str, dict[str, Any]]:
    """Punktzahl, Beiträge und Prüfbarkeit aller Bewertungsformen (nur solange die Figur Mensch ist)."""
    human = state.parts["essence"]["form"] == "human"
    level = state.parts["identity"]["level"]
    out: dict[str, dict[str, Any]] = {}
    for form, f in rules["essence"]["forms"].items():
        if "signals" not in f:
            continue
        contrib = {k: w * signal_value(state, rules, k) // 1000 for k, w in f["signals"].items()}
        score = sum(contrib.values())
        known = state.parts.get("discovery", {}).get("known", {})
        gated = all(d in known for d in f.get("requires_discoveries", []))  # geheime Formen: nur durch Entdeckungen
        out[form] = {"score": score, "threshold": f["threshold"], "contributions": contrib,
                     "eligible": human and gated and level >= f.get("min_level", 1) and score >= f["threshold"]}
    return out


def essence_profile(state: CharacterState, rules: Rules) -> dict[str, Any]:
    """Vor-/Nachteile der angenommenen Wesensform (leer, solange die Figur Mensch ist)."""
    form = state.parts["essence"]["form"]
    f = rules["essence"]["forms"].get(form)
    if form == "human" or not f or "modifiers" not in f:
        return {"form": form, "advantages": {}, "disadvantages": {}}
    return {"form": form, "advantages": dict(f["modifiers"]["advantages"]),
            "disadvantages": dict(f["modifiers"]["disadvantages"])}


def eligible_forms(state: CharacterState, rules: Rules) -> list[str]:
    """Wesensformen, deren Voraussetzungen die Spielhistorie derzeit erfüllt."""
    if state.parts["essence"]["form"] != "human":
        return []
    prof = ProfessionEngine(rules)
    level = state.parts["identity"]["level"]
    attuned = set(state.parts["element"]["attuned"])
    scores = form_scores(state, rules)
    result = []
    for form, req in rules["essence"]["forms"].items():
        if "signals" in req:
            if scores[form]["eligible"]:
                result.append(form)
            continue
        if level < req.get("min_level", 1):
            continue
        if not set(req.get("attuned_all", [])) <= attuned:
            continue
        need = req.get("combat_directions", {})
        if need:
            reached = reached_directions(state, rules) if "combat" in state.parts else {}
            if any(reached.get(d, 0) < t for d, t in need.items()):
                continue
        mastery = {p: prof.mastery_level(x) for p, x in state.parts["profession"]["xp"].items()}
        if any(mastery.get(p, 0) < m for p, m in req.get("professions", {}).items()):
            continue
        result.append(form)
    return sorted(result)


# ------------------------------------------------------------------ Engine -----------
class EssenceEngine(Engine):
    name = "essence"

    def __init__(self, rules: Rules) -> None:
        super().__init__(rules)
        validate_essence_rules(rules)

    def initial(self) -> dict[str, Any]:
        part: dict[str, Any] = {"form": "human", "trials_passed": [], "adopted_at_seq": None}
        if "decisions" in self.rules["essence"]:  # Zustand älterer Regelversionen bleibt unverändert
            part["decisions"] = {}
        return part

    def _validate_decision(self, state: CharacterState, payload: dict[str, Any]) -> None:
        decisions = self.rules["essence"].get("decisions")
        if decisions is None:
            raise RuleViolation("Unbekannter Ereignistyp: essence.decision_made")
        if set(payload) != DECISION_KEYS:
            raise RuleViolation("Ungültige Felder für essence.decision_made")
        did, choice = payload["decision_id"], payload["choice"]
        if not isinstance(did, str) or did not in decisions:
            raise RuleViolation("Unbekannte Entscheidung")
        if not isinstance(choice, str) or choice not in decisions[did]["options"]:
            raise RuleViolation("Unbekannte Option")
        part = state.parts["essence"]
        if part["form"] != "human":
            raise RuleViolation("Wesensform ist dauerhaft und bereits angenommen")
        if did in part["decisions"]:
            raise RuleViolation("Entscheidung wurde bereits getroffen")
        if state.parts["identity"]["level"] < decisions[did].get("min_level", 1):
            raise RuleViolation("Mindeststufe für diese Entscheidung nicht erreicht")

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        if type == "essence.decision_made":
            return self._validate_decision(state, payload)
        part = state.parts["essence"]
        form = payload.get("form")
        if not isinstance(form, str) or form not in self.rules["essence"]["forms"]:
            raise RuleViolation("Unbekannte Wesensform")
        if part["form"] != "human":
            raise RuleViolation("Wesensform ist dauerhaft und bereits angenommen")
        if type == "essence.trial_passed":
            if form not in eligible_forms(state, self.rules):
                raise RuleViolation("Voraussetzungen für diese Wesensprüfung nicht erfüllt")
            if form in part["trials_passed"]:
                raise RuleViolation("Prüfung bereits bestanden")
        elif type == "essence.adopted":
            if form not in part["trials_passed"]:
                raise RuleViolation("Wesensprüfung nicht bestanden")
        else:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")

    def apply(self, state: CharacterState, event: Event) -> None:
        part = state.parts["essence"]
        if event.type == "essence.decision_made":
            part["decisions"][event.payload["decision_id"]] = event.payload["choice"]
        elif event.type == "essence.trial_passed":
            part["trials_passed"].append(event.payload["form"])
        elif event.type == "essence.adopted":
            part["form"] = event.payload["form"]
            part["adopted_at_seq"] = event.seq
