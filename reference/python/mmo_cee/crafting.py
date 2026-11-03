"""Crafting Engine (Charakterseite): Handwerksprofil und Spezialisierung aus Herstellungsberichten.

Ereignis `crafting.crafted` ist ein serverbestätigter Herstellungsbericht (Vertrauensgrenze wie bei
Kampfberichten, ADR-0003/0006/0009). Punkte entstehen nur in dieser Engine: Dimensionen
(volume/finesse/innovation/infusion), Materialfamilien und Element-Infusionen, mit Wiederholungsabnahme
je Rezept und Tag sowie Tageslimits je Dimension. Spezialisierungen (`craft_directions`) sind abgeleitet,
nicht exklusiv und nie rückgängig zu machen. Rezepte/Techniken werden über Berufsmeisterschaft und
Entdeckungen (Discovery Engine) freigeschaltet. Siehe ADR-0010; alle Inhalte sind Platzhalter.
"""
from __future__ import annotations

from typing import Any

from .engine import CharacterState, Engine
from .errors import CEEError, RuleViolation
from .history import Event
from .professions import ProfessionEngine
from .rules import Rules

CRAFT_EVENT = "crafting.crafted"
PAYLOAD_KEYS = frozenset({"craft_id", "recipe_id", "technique_id", "element", "quantity", "quality", "day"})


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


# ---------------------------------------------------------------- Regelprüfung -------
def validate_crafting_rules(rules: Rules) -> None:
    cfg = rules["crafting"]
    tiers = cfg["tiers"]
    if len(tiers) < 2 or len(set(tiers)) != len(tiers):
        raise CEEError("crafting.tiers ungültig")
    th = [cfg["quality_thresholds"][t] for t in tiers]
    if th[0] != 0 or any(not _is_int(x) for x in th) or any(b <= a for a, b in zip(th, th[1:])):
        raise CEEError("crafting.quality_thresholds müssen bei 0 beginnen und aufsteigen")
    if set(cfg["quality_permille"]) != set(tiers) or any(not _is_int(v) or not 0 <= v <= 1000 for v in cfg["quality_permille"].values()):
        raise CEEError("crafting.quality_permille ungültig")
    q = cfg["quality"]
    if any(not _is_int(q[k]) or q[k] < 0 for k in ("per_mastery", "technique_bonus", "material_weight")):
        raise CEEError("crafting.quality ungültig")
    grades = cfg["material_grades"]
    if not grades or any(not _is_int(v) or not 0 <= v <= 1000 for v in grades.values()):
        raise CEEError("crafting.material_grades ungültig")
    dims, fams = cfg["dimensions"], cfg["families"]
    if not dims or not fams or len(set(dims)) != len(dims) or len(set(fams)) != len(fams):
        raise CEEError("crafting.dimensions/families ungültig")
    d = cfg["daily"]
    if not 0 < d["full_cap"] <= d["hard_cap"] or not 0 <= d["reduced_permille"] <= 1000:
        raise CEEError("crafting.daily inkonsistent")
    if not cfg["repeat_recipe_permille"] or any(not _is_int(v) or not 0 < v <= 1000 for v in cfg["repeat_recipe_permille"]):
        raise CEEError("crafting.repeat_recipe_permille ungültig")
    for k in ("first_craft_bonus_points", "technique_innovation_permille"):
        if not _is_int(cfg[k]) or cfg[k] < 0:
            raise CEEError(f"crafting.{k} ungültig")

    disc = rules["discovery"]["discoveries"] if "discovery" in rules else {}
    for rid, r in cfg["recipes"].items():
        if r["profession"] not in rules["professions"]["all"]:
            raise CEEError(f"{rid}: unbekannter Beruf")
        if not _is_int(r["min_mastery"]) or not 0 <= r["min_mastery"] <= 10 or not _is_int(r["tier"]) or not 1 <= r["tier"] <= 9:
            raise CEEError(f"{rid}: min_mastery/tier ungültig")
        if r["family"] not in fams:
            raise CEEError(f"{rid}: unbekannte Materialfamilie")
        if not r["inputs"] or any(not isinstance(i, str) or not _is_int(n) or n <= 0 for i, n in r["inputs"].items()):
            raise CEEError(f"{rid}: inputs ungültig")
        if not _is_int(r["output"]["qty"]) or r["output"]["qty"] <= 0 or not isinstance(r["output"]["item"], str):
            raise CEEError(f"{rid}: output ungültig")
        if not _is_int(r["max_batch"]) or not 1 <= r["max_batch"] <= 100 or not _is_int(r["base_quality"]) or r["base_quality"] < 0:
            raise CEEError(f"{rid}: max_batch/base_quality ungültig")
        if not isinstance(r["infusible"], bool):
            raise CEEError(f"{rid}: infusible muss bool sein")
        need = r.get("requires_discovery")
        if need is not None and (need not in disc or rid not in disc[need]["grants"].get("recipes", [])):
            raise CEEError(f"{rid}: requires_discovery {need!r} muss das Rezept freischalten (grants.recipes)")
    for tid, t in cfg["techniques"].items():
        need = t["requires_discovery"]
        if need not in disc or tid not in disc[need]["grants"].get("techniques", []):
            raise CEEError(f"{tid}: requires_discovery {need!r} muss die Technik freischalten (grants.techniques)")
        if not t["recipes"] or any(r not in cfg["recipes"] for r in t["recipes"]):
            raise CEEError(f"{tid}: unbekannte Rezepte")
        if not _is_int(t["input_permille"]) or not 0 < t["input_permille"] <= 1000 or not _is_int(t.get("quality_bonus", 0)) or t.get("quality_bonus", 0) < 0:
            raise CEEError(f"{tid}: input_permille/quality_bonus ungültig")
    for did, dd in disc.items():  # jede freigeschaltete Technik/jedes Rezept muss existieren
        for r in dd["grants"].get("recipes", []):
            if r not in cfg["recipes"]:
                raise CEEError(f"Entdeckung {did} schaltet unbekanntes Rezept {r} frei")
        for t in dd["grants"].get("techniques", []):
            if t not in cfg["techniques"]:
                raise CEEError(f"Entdeckung {did} schaltet unbekannte Technik {t} frei")
    sources = {f"dim:{x}" for x in dims} | {f"family:{x}" for x in fams} | {f"element:{x}" for x in rules["elements"]["all"]}
    for name, dr in cfg["directions"].items():
        if not dr["weights"] or set(dr["weights"]) - sources or any(not _is_int(w) or w <= 0 for w in dr["weights"].values()):
            raise CEEError(f"Richtung {name}: Gewichte ungültig")
        t = dr["tier_thresholds"]
        if not t or t[0] <= 0 or any(b <= a for a, b in zip(t, t[1:])):
            raise CEEError(f"Richtung {name}: Schwellen müssen streng aufsteigend und positiv sein")


# ---------------------------------------------------------------- Qualität & Verfügbarkeit
def mastery_of(state: CharacterState, rules: Rules, profession: str) -> int:
    return ProfessionEngine(rules).mastery_level(state.parts["profession"]["xp"].get(profession, 0))


def known_discoveries_of(state: CharacterState) -> dict[str, Any]:
    return state.parts.get("discovery", {}).get("known", {})


def known_techniques(state: CharacterState, rules: Rules) -> list[str]:
    known = known_discoveries_of(state)
    return sorted(t for t, d in rules["crafting"]["techniques"].items() if d["requires_discovery"] in known)


def recipe_blockers(state: CharacterState, rules: Rules, recipe_id: str) -> list[str]:
    r = rules["crafting"]["recipes"][recipe_id]
    out = []
    if mastery_of(state, rules, r["profession"]) < r["min_mastery"]:
        out.append(f"profession:{r['profession']}>={r['min_mastery']}")
    need = r.get("requires_discovery")
    if need and need not in known_discoveries_of(state):
        out.append(f"discovery:{need}")
    return out


def known_recipes(state: CharacterState, rules: Rules) -> list[str]:
    return sorted(r for r in rules["crafting"]["recipes"] if not recipe_blockers(state, rules, r))


def quality_score(state: CharacterState, rules: Rules, recipe_id: str, technique_id: str | None, material_permille: int) -> int:
    cfg = rules["crafting"]
    r = cfg["recipes"][recipe_id]
    score = r["base_quality"] + mastery_of(state, rules, r["profession"]) * cfg["quality"]["per_mastery"]
    if technique_id:
        score += cfg["techniques"][technique_id].get("quality_bonus", cfg["quality"]["technique_bonus"])
    return score + material_permille * cfg["quality"]["material_weight"] // 1000


def quality_tier(rules: Rules, score: int) -> str:
    cfg = rules["crafting"]
    best = cfg["tiers"][0]
    for t in cfg["tiers"]:
        if score >= cfg["quality_thresholds"][t]:
            best = t
    return best


def quality_cap(state: CharacterState, rules: Rules, recipe_id: str, technique_id: str | None) -> str:
    """Beste überhaupt erreichbare Qualitätsstufe (bestes Material) – Plausibilitätsgrenze für Berichte."""
    best = max(rules["crafting"]["material_grades"].values())
    return quality_tier(rules, quality_score(state, rules, recipe_id, technique_id, best))


def craft_blockers(state: CharacterState, rules: Rules, recipe_id: str, technique_id: str | None,
                   element: str | None, quantity: int) -> list[str]:
    """Alles, was diese Herstellung für die Figur unmöglich macht (leer = zulässig)."""
    cfg = rules["crafting"]
    if recipe_id not in cfg["recipes"]:
        return ["unbekanntes Rezept"]
    r = cfg["recipes"][recipe_id]
    out = [f"fehlt: {b}" for b in recipe_blockers(state, rules, recipe_id)]
    if not _is_int(quantity) or not 1 <= quantity <= r["max_batch"]:
        out.append(f"quantity 1..{r['max_batch']}")
    if technique_id is not None:
        t = cfg["techniques"].get(technique_id)
        if t is None:
            out.append("unbekannte Technik")
        else:
            if t["requires_discovery"] not in known_discoveries_of(state):
                out.append(f"Technik unbekannt: {technique_id}")
            if recipe_id not in t["recipes"]:
                out.append("Technik passt nicht zum Rezept")
    if element is not None:
        if element not in rules["elements"]["all"]:
            out.append("unbekanntes Element")
        elif not r["infusible"]:
            out.append("Rezept nicht infusionsfähig")
        elif element not in state.parts["element"]["attuned"]:
            out.append("Element nicht geprägt")
    return out


# ---------------------------------------------------------------- Abgeleitete Sichten ----
def _direction_value(part: dict[str, Any], source: str) -> int:
    kind, name = source.split(":")
    return part[{"dim": "points", "family": "families", "element": "elements"}[kind]][name]


def craft_direction_scores(state: CharacterState, rules: Rules) -> dict[str, int]:
    part = state.parts["crafting"]
    return {n: sum(_direction_value(part, s) * w // 1000 for s, w in d["weights"].items())
            for n, d in rules["crafting"]["directions"].items()}


def craft_directions(state: CharacterState, rules: Rules) -> dict[str, int]:
    """Spezialisierung -> Stufe (>= 1); nicht exklusiv, Punkte sinken nie."""
    scores = craft_direction_scores(state, rules)
    return {n: tier for n, d in rules["crafting"]["directions"].items()
            if (tier := sum(1 for t in d["tier_thresholds"] if scores[n] >= t))}


def craft_profile(state: CharacterState, rules: Rules) -> dict[str, int]:
    """Anteil jeder Dimension an der Gesamtentwicklung in Promille (abgerundet)."""
    pts = state.parts["crafting"]["points"]
    total = sum(pts.values())
    return {d: (p * 1000 // total if total else 0) for d, p in pts.items()}


# ---------------------------------------------------------------- Engine ---------------
def _today(part: dict[str, Any], day: int, dims: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    d = part["daily"]
    if day > d["day"]:
        return {x: 0 for x in dims}, {}
    return dict(d["points"]), dict(d["recipes"])


def craft_gains(state: CharacterState, rules: Rules, payload: dict[str, Any]) -> dict[str, int]:
    """Punkte je Dimension nach Wiederholungsabnahme und Tageslimit (rein, deterministisch, ganzzahlig)."""
    cfg, part = rules["crafting"], state.parts["crafting"]
    today, repeats = _today(part, payload["day"], cfg["dimensions"])
    r = cfg["recipes"][payload["recipe_id"]]
    unit = payload["quantity"] * r["tier"] * 100
    raw = {d: 0 for d in cfg["dimensions"]}
    raw["volume"] = unit
    raw["finesse"] = unit * cfg["quality_permille"][payload["quality"]] // 1000
    if payload["technique_id"]:
        raw["innovation"] = unit * cfg["technique_innovation_permille"] // 1000
    if payload["element"]:
        raw["infusion"] = unit
    rep = cfg["repeat_recipe_permille"]
    decay = rep[min(repeats.get(payload["recipe_id"], 0), len(rep) - 1)]
    bonus = cfg["first_craft_bonus_points"] if payload["recipe_id"] not in part["recipes"] else 0
    cap = cfg["daily"]
    gains: dict[str, int] = {}
    for dim, v in raw.items():
        g = v * decay // 1000 + (bonus if dim == "innovation" else 0)
        p = today[dim]
        full = min(g, max(0, cap["full_cap"] - p))
        reduced = (g - full) * cap["reduced_permille"] // 1000
        gains[dim] = full + min(reduced, max(0, cap["hard_cap"] - p - full))
    return gains


class CraftingEngine(Engine):
    name = "crafting"

    def __init__(self, rules: Rules) -> None:
        super().__init__(rules)
        validate_crafting_rules(rules)
        self.cfg = rules["crafting"]

    def initial(self) -> dict[str, Any]:
        c = self.cfg
        return {"points": {d: 0 for d in c["dimensions"]}, "families": {f: 0 for f in c["families"]},
                "elements": {e: 0 for e in self.rules["elements"]["all"]}, "recipes": {}, "techniques": {},
                "crafts": {}, "daily": {"day": 0, "points": {d: 0 for d in c["dimensions"]}, "recipes": {}}}

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        if type != CRAFT_EVENT:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")
        part, cfg = state.parts["crafting"], self.cfg
        if set(payload) != PAYLOAD_KEYS:
            raise RuleViolation(f"Ungültige Felder (unzulässig: {sorted(set(payload) - PAYLOAD_KEYS)}, fehlend: {sorted(PAYLOAD_KEYS - set(payload))})")
        cid = payload["craft_id"]
        if not isinstance(cid, str) or not 1 <= len(cid) <= 64:
            raise RuleViolation("craft_id muss ein String mit 1-64 Zeichen sein")
        if cid in part["crafts"]:
            raise RuleViolation("Herstellung wurde bereits gewertet")
        rid, tid, el = payload["recipe_id"], payload["technique_id"], payload["element"]
        if not isinstance(rid, str) or rid not in cfg["recipes"]:
            raise RuleViolation("Unbekanntes Rezept")
        if tid is not None and not isinstance(tid, str):
            raise RuleViolation("technique_id muss String oder null sein")
        if el is not None and not isinstance(el, str):
            raise RuleViolation("element muss String oder null sein")
        day = payload["day"]
        if not _is_int(day) or day < 0:
            raise RuleViolation("day muss eine nichtnegative ganze Zahl sein")
        if day < part["daily"]["day"]:
            raise RuleViolation("day darf nicht zurückspringen")
        if not isinstance(payload["quality"], str) or payload["quality"] not in cfg["tiers"]:
            raise RuleViolation("Unbekannte Qualitätsstufe")
        blockers = craft_blockers(state, self.rules, rid, tid, el, payload["quantity"])
        if blockers:
            raise RuleViolation(f"Herstellung nicht zulässig: {blockers}")
        cap = quality_cap(state, self.rules, rid, tid)
        if cfg["tiers"].index(payload["quality"]) > cfg["tiers"].index(cap):
            raise RuleViolation(f"Unplausible Qualität: {payload['quality']} > {cap}")

    def apply(self, state: CharacterState, event: Event) -> None:
        part, pl, cfg = state.parts["crafting"], event.payload, self.cfg
        gains = craft_gains(state, self.rules, pl)
        today, repeats = _today(part, pl["day"], cfg["dimensions"])
        r = cfg["recipes"][pl["recipe_id"]]
        for d, g in gains.items():
            part["points"][d] += g
            today[d] += g
        part["families"][r["family"]] += gains["volume"]
        if pl["element"]:
            part["elements"][pl["element"]] += gains["infusion"]
        repeats[pl["recipe_id"]] = repeats.get(pl["recipe_id"], 0) + 1
        part["daily"] = {"day": pl["day"], "points": today, "recipes": repeats}
        entry = part["recipes"].setdefault(pl["recipe_id"], {"count": 0, "best": 0})
        entry["count"] += 1
        entry["best"] = max(entry["best"], cfg["tiers"].index(pl["quality"]))
        if pl["technique_id"]:
            part["techniques"][pl["technique_id"]] = part["techniques"].get(pl["technique_id"], 0) + 1
        part["crafts"][pl["craft_id"]] = event.seq
