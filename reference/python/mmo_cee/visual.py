"""Visual Evolution Engine: deterministische Ableitung Charakterzustand -> Erscheinungsparameter.

Reine Funktion ohne eigenen Zustand und ohne eigene Ereignisse. Der Server berechnet die Parameter
aus dem Charakterzustand; Clients erhalten sie schreibgeschützt und können sie nicht vorgeben.
Ausgabe ist engine-neutral (gemeinsames Skelett, Morph-Gewichte, Materialparameter, Effektstärken,
Teile-IDs, Animations-Tags) und rein ganzzahlig (siehe ADR-0004). Alles Optische ist PLATZHALTER
(ADR-0008): die Mechanik ist belegt, nicht die Gestaltung.
"""
from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import Any

from .combat import direction_scores, style_profile
from .engine import CharacterState
from .errors import CEEError
from .history import _canonical as canonical_bytes
from .rules import Rules

SOURCE_KINDS = ("style", "element_attuned", "element_affinity", "profession", "combat_direction", "essence", "decision")
SECTIONS = ("morphs", "materials", "vfx")


def load_visual_rules(name: str = "visual_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_cee").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _parse(key: str) -> tuple[str, ...]:
    parts = tuple(key.split(":"))
    want = 3 if parts[0] == "decision" else 2
    if parts[0] not in SOURCE_KINDS or len(parts) != want or not all(parts):
        raise CEEError(f"Ungültige Quelle: {key!r}")
    return parts


def _known_targets(rules: Rules) -> dict[str, Any]:
    ess = rules["essence"]
    return {
        "style": rules["combat"]["dimensions"] if "combat" in rules else [],
        "element_attuned": rules["elements"]["all"], "element_affinity": rules["elements"]["all"],
        "profession": rules["professions"]["all"],
        "combat_direction": rules["combat"]["directions"] if "combat" in rules else [],
        "essence": list(ess["forms"]), "decision": ess.get("decisions", {}),
    }


def validate_visual_rules(rules: Rules, vr: dict[str, Any]) -> None:
    if int(rules.version) < vr["requires_cee_rules_min"]:
        raise CEEError(f"visual_rules benötigt CEE-Regeln >= v{vr['requires_cee_rules_min']} (vorhanden: v{rules.version})")
    q = vr["quantize_permille"]
    if not _is_int(q) or q <= 0 or 1000 % q:
        raise CEEError("quantize_permille muss ein positiver Teiler von 1000 sein")
    if not all(_is_int(vr["caps"][k]) and vr["caps"][k] > 0 for k in ("element_affinity", "profession_mastery", "direction_score", "style_total")):
        raise CEEError("caps müssen positive ganze Zahlen sein")
    known = _known_targets(rules)

    def check_source(key: str) -> None:
        kind, name, *rest = _parse(key)
        if name not in known[kind]:
            raise CEEError(f"Unbekanntes Quellziel: {key!r}")
        if kind == "decision" and rest[0] not in known["decision"][name]["options"]:
            raise CEEError(f"Unbekannte Option: {key!r}")

    for section in SECTIONS:
        for pname, p in vr[section].items():
            lo, hi = p.get("min", 0), p.get("max", 1000)
            if not (_is_int(p["base"]) and 0 <= lo <= hi <= 1000 and lo <= p["base"] <= hi):
                raise CEEError(f"{section}.{pname}: base/min/max ungültig")
            for key, w in p["from"].items():
                check_source(key)
                if not _is_int(w) or w < 0:
                    raise CEEError(f"{section}.{pname}: Gewichte müssen ganze Zahlen >= 0 sein")
            if "jitter" in p and not (_is_int(p["jitter"]) and 0 <= p["jitter"] <= 500):
                raise CEEError(f"{section}.{pname}: jitter muss 0..500 sein")
    if set(vr["palette"]) != set(rules["elements"]["all"]):
        raise CEEError("palette muss genau alle Elemente enthalten")
    for rgb in [*vr["palette"].values(), vr["skin_tint_base"]]:
        if len(rgb) != 3 or any(not _is_int(c) or not 0 <= c <= 255 for c in rgb):
            raise CEEError("Farben müssen [r,g,b] mit 0..255 sein")
    for slot, sel in vr["parts"].items():
        check_source(sel["source"])
        mins = [v["min"] for v in sel["variants"]]
        if not mins or mins[0] != 0 or any(b <= a for a, b in zip(mins, mins[1:])) or mins[-1] > 1000:
            raise CEEError(f"parts.{slot}: Varianten müssen bei 0 beginnen und aufsteigen")
    for t in vr["animation_tags"]:
        check_source(t["source"])
        if not _is_int(t["min"]) or not 0 < t["min"] <= 1000:
            raise CEEError(f"animation_tags.{t['tag']}: min muss 1..1000 sein")
    for form, layer in vr["essence_layers"].items():
        if form not in known["essence"]:
            raise CEEError(f"essence_layers: unbekannte Form {form!r}")
        for section in SECTIONS:
            for pname, delta in layer[section].items():
                if pname not in vr[section] or not _is_int(delta):
                    raise CEEError(f"essence_layers.{form}.{section}.{pname} ungültig")
        if len(layer["skin_tint_delta"]) != 3 or any(not _is_int(c) for c in layer["skin_tint_delta"]):
            raise CEEError(f"essence_layers.{form}: skin_tint_delta ungültig")


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _hash_int(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


class VisualEvolution:
    """Implementiert interfaces.VisualEvolution: appearance(state) -> dict."""

    def __init__(self, rules: Rules, visual_rules: dict[str, Any] | None = None) -> None:
        self.rules = rules
        self.vr = visual_rules or load_visual_rules()
        validate_visual_rules(rules, self.vr)

    # -- Quellen ----------------------------------------------------------------------
    def _sources(self, state: CharacterState) -> Any:
        caps, rules, parts = self.vr["caps"], self.rules, state.parts
        combat = parts.get("combat")
        if combat:
            total = sum(combat["points"].values())
            confidence = min(1000, total * 1000 // caps["style_total"])
            shares = style_profile(state, rules)
            dscores = direction_scores(state, rules)
        else:
            confidence, shares, dscores = 0, {}, {}
        from .professions import ProfessionEngine
        mastery = ProfessionEngine(rules).mastery_level
        attuned = set(parts["element"]["attuned"])
        decisions = parts["essence"].get("decisions", {})

        def value(key: str) -> int:
            kind, name, *rest = _parse(key)
            if kind == "style":
                return shares.get(name, 0) * confidence // 1000
            if kind == "element_attuned":
                return 1000 if name in attuned else 0
            if kind == "element_affinity":
                return min(1000, parts["element"]["affinity"][name] * 1000 // caps["element_affinity"])
            if kind == "profession":
                return min(1000, mastery(parts["profession"]["xp"].get(name, 0)) * 1000 // caps["profession_mastery"])
            if kind == "combat_direction":
                return min(1000, dscores.get(name, 0) * 1000 // caps["direction_score"])
            if kind == "essence":
                return 1000 if parts["essence"]["form"] == name else 0
            return 1000 if decisions.get(name) == rest[0] else 0

        return value

    # -- Ableitung --------------------------------------------------------------------
    def appearance(self, state: CharacterState) -> dict[str, Any]:
        vr = self.vr
        value = self._sources(state)
        form = state.parts["essence"]["form"]
        layer = vr["essence_layers"].get(form)
        q = vr["quantize_permille"]
        out: dict[str, Any] = {}
        for section in SECTIONS:
            vals: dict[str, int] = {}
            for pname, p in vr[section].items():
                v = p["base"] + sum(w * value(k) // 1000 for k, w in p["from"].items())
                if "jitter" in p:  # individuelle, stabile Variation je Figur (kein Zufall, kein Spielerbezug)
                    j = p["jitter"]
                    v += _hash_int(f"{state.character_id}|{pname}") % (2 * j + 1) - j
                if layer:
                    v += layer[section].get(pname, 0)
                v = _clamp(v, p.get("min", 0), p.get("max", 1000))
                vals[pname] = _clamp((v + q // 2) // q * q, p.get("min", 0), p.get("max", 1000))
            out[section] = vals

        attuned = sorted(state.parts["element"]["attuned"])
        aura = None
        if attuned:
            weights = [500 + value(f"element_affinity:{e}") // 2 for e in attuned]
            aura = [sum(vr["palette"][e][c] * w for e, w in zip(attuned, weights)) // sum(weights) for c in range(3)]
        tint = list(vr["skin_tint_base"])
        if layer:
            tint = [_clamp(c + d, 0, 255) for c, d in zip(tint, layer["skin_tint_delta"])]

        parts: dict[str, str] = {}
        for slot, sel in vr["parts"].items():
            v = value(sel["source"])
            parts[slot] = [x for x in sel["variants"] if x["min"] <= v][-1]["id"]
        tags = {t["tag"] for t in vr["animation_tags"] if value(t["source"]) >= t["min"]}
        if layer:
            parts.update(layer["parts"])
            tags.update(layer["tags"])

        base_class = state.parts["identity"]["base_class"]
        result = {
            "visual_rules_version": vr["version"], "cee_rules_version": self.rules.version,
            "skeleton": vr["skeleton"],
            "body_set": vr["classes"][base_class]["body_set"] if base_class else vr["default_body_set"],
            "base_class": base_class, "essence_form": form,
            "element_signature": attuned, "identity_seed": _hash_int(state.character_id),
            "morphs": out["morphs"], "materials": out["materials"], "vfx": out["vfx"],
            "colors": {"aura": aura, "skin_tint": tint},
            "parts": dict(sorted(parts.items())), "animation_tags": sorted(tags),
        }
        result["appearance_sha256"] = hashlib.sha256(canonical_bytes(result)).hexdigest()
        return result


def appearance_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Minimale Änderungsmenge für die Replikation (Abschnitt -> geänderte Schlüssel bzw. neuer Wert)."""
    diff: dict[str, Any] = {}
    for key, nv in new.items():
        if key == "appearance_sha256" or old.get(key) == nv:
            continue
        ov = old.get(key)
        if isinstance(nv, dict) and isinstance(ov, dict):
            diff[key] = {k: v for k, v in nv.items() if ov.get(k) != v}
        else:
            diff[key] = nv
    return diff
