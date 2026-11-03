"""Economic Profile (Charakterseite): wirtschaftliche Entwicklung aus serverbestätigten Berichten.

Ereignisse (alle vom Spielserver ausgelöst, Vertrauensgrenze wie ADR-0003/0006/0009/0010):
* `economy.trade_completed`  - ein abgeschlossener Handel aus Sicht einer Seite (Käufer oder Verkäufer).
* `economy.career_changed`   - Laufbahn: Einstellung, Beförderung (immer nur eine Stufe), Zurückstufung, Austritt.
* `economy.company_founded` / `economy.company_closed` - Unternehmensgründung und -schließung (Besitz ist
  getrennt von der Laufbahn: Eigentümer und Geschäftsführer sind verschiedene Rollen).

Schutz vor Scheinhandel (Wash Trading): Handel mit sich selbst ist unzulässig; der Referenzwert wird aus einer
Regeltabelle exakt berechnet (nicht vom Bericht behauptet); Preise weit neben dem Referenzwert zählen nicht;
Wiederholungsabnahme je Handelspartner und Tag; Tageslimits; neue Handelspartner geben einen Netzwerkbonus.
Spezialisierungen sind abgeleitet und nicht exklusiv. Siehe ADR-0011; alle Inhalte sind Platzhalter.
"""
from __future__ import annotations

from typing import Any

from .engine import CharacterState, Engine
from .errors import CEEError, RuleViolation
from .history import Event
from .professions import ProfessionEngine
from .rules import Rules

TRADE, CAREER, FOUNDED, CLOSED = ("economy.trade_completed", "economy.career_changed",
                                  "economy.company_founded", "economy.company_closed")
TRADE_KEYS = frozenset({"trade_id", "role", "counterparty", "item_id", "grade", "quantity", "value", "day"})
TRADE_KEYS_DYNAMIC = TRADE_KEYS | {"reference"}  # ab rules_v8: serverseitig gemeldeter Referenzwert
CAREER_KEYS = frozenset({"company_id", "role", "day"})
COMPANY_KEYS = frozenset({"company_id", "day"})
ROLES_OF_TRADE = ("buyer", "seller")


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _short_str(v: Any) -> bool:
    return isinstance(v, str) and 1 <= len(v) <= 64


# ---------------------------------------------------------------- Regelprüfung -------
def validate_economy_rules(rules: Rules) -> None:
    cfg = rules["economy"]
    cur = cfg["currency"]
    if not _short_str(cur["item"]) or not _short_str(cur["grade"]):
        raise CEEError("economy.currency ungültig")
    classes = cfg["item_classes"]
    if not classes or len(set(classes)) != len(classes):
        raise CEEError("economy.item_classes ungültig")
    for k, v in cfg["grade_permille"].items():
        if not _is_int(v) or not 0 < v <= 10000:
            raise CEEError(f"grade_permille.{k} ungültig")
    for item, d in cfg["items"].items():
        if "@" in item or d["class"] not in classes or not _is_int(d["base_value"]) or d["base_value"] <= 0:
            raise CEEError(f"items.{item} ungültig")
    if cur["item"] in cfg["items"]:
        raise CEEError("Die Währung darf kein handelbarer Gegenstand sein")
    if "crafting" in rules:  # alles Herstellbare und Verbrauchte muss einen Wert haben
        for rid, r in rules["crafting"]["recipes"].items():
            for it in [*r["inputs"], r["output"]["item"]]:
                if it not in cfg["items"]:
                    raise CEEError(f"Rezept {rid}: Gegenstand {it!r} hat keinen Handelswert")
        for g in [*rules["crafting"]["material_grades"], *rules["crafting"]["tiers"]]:
            if g not in cfg["grade_permille"]:
                raise CEEError(f"Güte/Qualität {g!r} hat keinen Wertfaktor")
    if "dynamic_reference" in cfg:
        ms = cfg["dynamic_reference"]["max_shift_permille"]
        if not _is_int(ms) or not 0 <= ms <= 900:
            raise CEEError("dynamic_reference.max_shift_permille muss 0..900 sein")
    t = cfg["trade"]
    for k in ("max_quantity", "max_value", "value_per_point"):
        if not _is_int(t[k]) or t[k] <= 0:
            raise CEEError(f"trade.{k} muss eine positive ganze Zahl sein")
    if not _is_int(t["max_deviation_permille"]) or not 0 <= t["max_deviation_permille"] <= 1000:
        raise CEEError("trade.max_deviation_permille muss 0..1000 sein")
    if not _is_int(t["network_bonus_points"]) or t["network_bonus_points"] < 0:
        raise CEEError("trade.network_bonus_points ungültig")
    if not _is_int(t["network_min_credited_value"]) or t["network_min_credited_value"] < 1:
        raise CEEError("trade.network_min_credited_value muss >= 1 sein")
    rep = t["counterparty_repeat_permille"]
    if not rep or any(not _is_int(v) or not 0 < v <= 1000 for v in rep):
        raise CEEError("trade.counterparty_repeat_permille ungültig")
    dims = cfg["dimensions"]
    if set(dims) != {"volume", "network"}:
        raise CEEError("economy.dimensions muss genau volume und network enthalten")
    d = cfg["daily"]
    if not 0 < d["full_cap"] <= d["hard_cap"] or not 0 <= d["reduced_permille"] <= 1000:
        raise CEEError("economy.daily inkonsistent")
    roles = cfg["career"]["roles"]
    if len(roles) < 2 or len(set(roles)) != len(roles):
        raise CEEError("career.roles ungültig")
    gates = cfg["career"]["gates"]
    if set(gates) != set(roles[1:]):
        raise CEEError("career.gates muss genau alle Stufen über der Einstiegsstufe enthalten")
    for role, g in gates.items():
        if any(not _is_int(g[k]) or g[k] < 0 for k in ("min_best_mastery", "min_tenure_days")) or g["min_best_mastery"] > 10:
            raise CEEError(f"career.gates.{role} ungültig")
        if set(g.get("min_points", {})) - set(dims) or any(not _is_int(v) or v < 0 for v in g.get("min_points", {}).values()):
            raise CEEError(f"career.gates.{role}.min_points ungültig")
    f = cfg["founding"]
    if any(not _is_int(f[k]) or f[k] < 0 for k in ("min_level", "min_best_mastery", "max_open_companies")) or f["max_open_companies"] < 1:
        raise CEEError("economy.founding ungültig")
    sources = {f"dim:{x}" for x in dims} | {f"class:{c}" for c in classes}
    for name, dr in cfg["directions"].items():
        if not dr["weights"] or set(dr["weights"]) - sources or any(not _is_int(w) or w <= 0 for w in dr["weights"].values()):
            raise CEEError(f"Richtung {name}: Gewichte ungültig")
        th = dr["tier_thresholds"]
        if not th or th[0] <= 0 or any(b <= a for a, b in zip(th, th[1:])):
            raise CEEError(f"Richtung {name}: Schwellen müssen streng aufsteigend und positiv sein")


# ---------------------------------------------------------------- Werte --------------
def reference_value(rules: Rules, item_id: str, grade: str, quantity: int) -> int:
    """Referenzwert aus der Regeltabelle (Basiswert x Stufenfaktor x Menge, ganzzahlig abgerundet)."""
    cfg = rules["economy"]
    return cfg["items"][item_id]["base_value"] * cfg["grade_permille"][grade] * quantity // 1000


def reference_bounds(rules: Rules, table_ref: int) -> tuple[int, int]:
    """Zulässige Spanne des gemeldeten Referenzwerts um den Tabellenwert (nur mit economy.dynamic_reference)."""
    shift = rules["economy"]["dynamic_reference"]["max_shift_permille"]
    return table_ref * (1000 - shift) // 1000, -(-table_ref * (1000 + shift) // 1000)


def trade_reference(rules: Rules, payload: dict[str, Any]) -> int:
    """Referenzwert eines Handels: ab v8 der gemeldete (innerhalb der Spanne geprüfte), sonst der Tabellenwert."""
    if "dynamic_reference" in rules["economy"]:
        return payload["reference"]
    return reference_value(rules, payload["item_id"], payload["grade"], payload["quantity"])


def credited_value(rules: Rules, value: int, reference: int) -> int:
    """Gutgeschriebener Wert: 0 bei zu großer Abweichung vom Referenzwert, sonst das Minimum beider."""
    dev = rules["economy"]["trade"]["max_deviation_permille"]
    if abs(value - reference) * 1000 > dev * reference:
        return 0
    return min(value, reference)


def best_mastery(state: CharacterState, rules: Rules) -> int:
    m = ProfessionEngine(rules).mastery_level
    xps = state.parts["profession"]["xp"].values()
    return max((m(x) for x in xps), default=0)


def _today(part: dict[str, Any], day: int, dims: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    d = part["daily"]
    if day > d["day"]:
        return {x: 0 for x in dims}, {}
    return dict(d["points"]), dict(d["counterparties"])


def trade_gains(state: CharacterState, rules: Rules, payload: dict[str, Any]) -> dict[str, int]:
    """Punkte je Dimension (rein, ganzzahlig): Wert x Wiederholungsabnahme, Netzwerkbonus, Tageslimits."""
    cfg, part = rules["economy"], state.parts["economy"]
    t = cfg["trade"]
    today, repeats = _today(part, payload["day"], cfg["dimensions"])
    ref = trade_reference(rules, payload)
    credited = credited_value(rules, payload["value"], ref)
    rep = t["counterparty_repeat_permille"]
    decay = rep[min(repeats.get(payload["counterparty"], 0), len(rep) - 1)]
    raw = {"volume": credited // t["value_per_point"] * decay // 1000,
           # Netzwerkbonus nur für einen *echten* Handel mit neuem Partner (Mindestwert, Preis nahe am Referenzwert)
           "network": t["network_bonus_points"] if (payload["counterparty"] not in part["counterparties"]
                                                    and credited >= t["network_min_credited_value"]) else 0}
    cap = cfg["daily"]
    gains: dict[str, int] = {}
    for dim, g in raw.items():
        p = today[dim]
        full = min(g, max(0, cap["full_cap"] - p))
        reduced = (g - full) * cap["reduced_permille"] // 1000
        gains[dim] = full + min(reduced, max(0, cap["hard_cap"] - p - full))
    return gains


# ---------------------------------------------------------------- Abgeleitete Sichten ----
def _value(part: dict[str, Any], source: str) -> int:
    kind, name = source.split(":")
    return part["points"][name] if kind == "dim" else part["classes"][name]


def economic_direction_scores(state: CharacterState, rules: Rules) -> dict[str, int]:
    part = state.parts["economy"]
    return {n: sum(_value(part, s) * w // 1000 for s, w in d["weights"].items())
            for n, d in rules["economy"]["directions"].items()}


def economic_directions(state: CharacterState, rules: Rules) -> dict[str, int]:
    """Handelsrichtung -> Stufe (>= 1); nicht exklusiv, Punkte sinken nie."""
    scores = economic_direction_scores(state, rules)
    return {n: tier for n, d in rules["economy"]["directions"].items()
            if (tier := sum(1 for t in d["tier_thresholds"] if scores[n] >= t))}


def economic_profile(state: CharacterState, rules: Rules) -> dict[str, Any]:
    part, roles = state.parts["economy"], rules["economy"]["career"]["roles"]
    career = part["career"]
    return {"role": career["role"], "company_id": career["company_id"],
            "rung": roles.index(career["role"]) if career["role"] else -1, "best_rung": career["best_rung"],
            "companies_open": sum(1 for c in part["founded"].values() if c["open"]),
            "companies_founded_total": len(part["founded"]), "network_size": len(part["counterparties"]),
            "trades": len(part["trades"])}


# ---------------------------------------------------------------- Engine ---------------
class EconomyEngine(Engine):
    name = "economy"

    def __init__(self, rules: Rules) -> None:
        super().__init__(rules)
        validate_economy_rules(rules)
        self.cfg = rules["economy"]
        self.dynamic = "dynamic_reference" in self.cfg

    def initial(self) -> dict[str, Any]:
        c = self.cfg
        return {"points": {d: 0 for d in c["dimensions"]}, "classes": {k: 0 for k in c["item_classes"]},
                "counterparties": {}, "trades": {}, "last_day": 0,
                "daily": {"day": 0, "points": {d: 0 for d in c["dimensions"]}, "counterparties": {}},
                "career": {"company_id": None, "role": None, "since_day": 0, "best_rung": -1, "changes": 0},
                "founded": {}}

    # -- Validierung -------------------------------------------------------------------
    @staticmethod
    def _keys(payload: dict[str, Any], keys: frozenset[str]) -> None:
        if set(payload) != keys:
            raise RuleViolation(f"Ungültige Felder (unzulässig: {sorted(set(payload) - keys)}, fehlend: {sorted(keys - set(payload))})")

    def _day(self, state: CharacterState, payload: dict[str, Any]) -> None:
        day = payload["day"]
        if not _is_int(day) or day < 0:
            raise RuleViolation("day muss eine nichtnegative ganze Zahl sein")
        if day < state.parts["economy"]["last_day"]:
            raise RuleViolation("day darf nicht zurückspringen")

    def _validate_trade(self, state: CharacterState, p: dict[str, Any]) -> None:
        part, cfg = state.parts["economy"], self.cfg
        self._keys(p, TRADE_KEYS_DYNAMIC if self.dynamic else TRADE_KEYS)
        if not _short_str(p["trade_id"]):
            raise RuleViolation("trade_id muss ein String mit 1-64 Zeichen sein")
        if p["trade_id"] in part["trades"]:
            raise RuleViolation("Handel wurde bereits gewertet")
        if p["role"] not in ROLES_OF_TRADE or not isinstance(p["role"], str):
            raise RuleViolation("role muss 'buyer' oder 'seller' sein")
        if not _short_str(p["counterparty"]):
            raise RuleViolation("counterparty muss ein String mit 1-64 Zeichen sein")
        if p["counterparty"] == state.character_id:
            raise RuleViolation("Handel mit sich selbst ist unzulässig")
        if not isinstance(p["item_id"], str) or p["item_id"] not in cfg["items"]:
            raise RuleViolation("Unbekannter Gegenstand")
        if not isinstance(p["grade"], str) or p["grade"] not in cfg["grade_permille"]:
            raise RuleViolation("Unbekannte Güte/Qualität")
        t = cfg["trade"]
        if not _is_int(p["quantity"]) or not 1 <= p["quantity"] <= t["max_quantity"]:
            raise RuleViolation("quantity außerhalb des gültigen Bereichs")
        if not _is_int(p["value"]) or not 1 <= p["value"] <= t["max_value"]:
            raise RuleViolation("value außerhalb des gültigen Bereichs")
        if self.dynamic:
            lo, hi = reference_bounds(self.rules, reference_value(self.rules, p["item_id"], p["grade"], p["quantity"]))
            if not _is_int(p["reference"]) or not lo <= p["reference"] <= hi:
                raise RuleViolation(f"reference außerhalb der zulässigen Spanne ({lo}..{hi})")
        self._day(state, p)

    def _validate_career(self, state: CharacterState, p: dict[str, Any]) -> None:
        part, cfg = state.parts["economy"], self.cfg["career"]
        roles = cfg["roles"]
        self._keys(p, CAREER_KEYS)
        self._day(state, p)
        cid, role = p["company_id"], p["role"]
        cur = part["career"]
        if (cid is None) != (role is None):
            raise RuleViolation("company_id und role müssen beide gesetzt oder beide null sein")
        if role is None:  # Austritt
            if cur["role"] is None:
                raise RuleViolation("Figur ist nicht angestellt")
            return
        if not _short_str(cid) or not isinstance(role, str) or role not in roles:
            raise RuleViolation("Ungültige Firma oder Rolle")
        if cur["role"] is None:  # Einstellung nur auf der Einstiegsstufe
            if role != roles[0]:
                raise RuleViolation(f"Einstellung nur als {roles[0]!r}")
            return
        if cid != cur["company_id"]:
            raise RuleViolation("Firmenwechsel nur nach Austritt")
        new, old = roles.index(role), roles.index(cur["role"])
        if new == old:
            raise RuleViolation("Rolle unverändert")
        if new < old:
            return  # Zurückstufung (Entscheidung der Firma) ist zulässig
        if new != old + 1:
            raise RuleViolation("Beförderung nur um genau eine Stufe")
        gate = cfg["gates"][role]
        missing = []
        if best_mastery(state, self.rules) < gate["min_best_mastery"]:
            missing.append(f"best_mastery>={gate['min_best_mastery']}")
        if p["day"] - cur["since_day"] < gate["min_tenure_days"]:
            missing.append(f"tenure>={gate['min_tenure_days']}d")
        for dim, need in gate.get("min_points", {}).items():
            if part["points"][dim] < need:
                missing.append(f"points.{dim}>={need}")
        if missing:
            raise RuleViolation(f"Beförderungsvoraussetzungen fehlen: {missing}")

    def _validate_company(self, state: CharacterState, type: str, p: dict[str, Any]) -> None:
        part, cfg = state.parts["economy"], self.cfg["founding"]
        self._keys(p, COMPANY_KEYS)
        self._day(state, p)
        if not _short_str(p["company_id"]):
            raise RuleViolation("company_id muss ein String mit 1-64 Zeichen sein")
        known = part["founded"].get(p["company_id"])
        if type == CLOSED:
            if known is None or not known["open"]:
                raise RuleViolation("Unternehmen ist nicht offen")
            return
        if known is not None:
            raise RuleViolation("Unternehmen wurde bereits gegründet")
        missing = []
        if state.parts["identity"]["level"] < cfg["min_level"]:
            missing.append(f"level>={cfg['min_level']}")
        if best_mastery(state, self.rules) < cfg["min_best_mastery"]:
            missing.append(f"best_mastery>={cfg['min_best_mastery']}")
        if sum(1 for c in part["founded"].values() if c["open"]) >= cfg["max_open_companies"]:
            missing.append(f"max_open_companies<{cfg['max_open_companies']}")
        if missing:
            raise RuleViolation(f"Gründungsvoraussetzungen fehlen: {missing}")

    def validate(self, state: CharacterState, type: str, payload: dict[str, Any]) -> None:
        if type == TRADE:
            self._validate_trade(state, payload)
        elif type == CAREER:
            self._validate_career(state, payload)
        elif type in (FOUNDED, CLOSED):
            self._validate_company(state, type, payload)
        else:
            raise RuleViolation(f"Unbekannter Ereignistyp: {type}")

    # -- Anwendung ---------------------------------------------------------------------
    def apply(self, state: CharacterState, event: Event) -> None:
        part, p = state.parts["economy"], event.payload
        part["last_day"] = p["day"]
        if event.type == TRADE:
            gains = trade_gains(state, self.rules, p)
            today, repeats = _today(part, p["day"], self.cfg["dimensions"])
            for d, g in gains.items():
                part["points"][d] += g
                today[d] += g
            cls = self.cfg["items"][p["item_id"]]["class"]
            part["classes"][cls] += gains["volume"]
            repeats[p["counterparty"]] = repeats.get(p["counterparty"], 0) + 1
            part["daily"] = {"day": p["day"], "points": today, "counterparties": repeats}
            ref = trade_reference(self.rules, p)
            if credited_value(self.rules, p["value"], ref) >= self.cfg["trade"]["network_min_credited_value"]:
                # Netzwerk = Partner mit mindestens einem qualifizierten (echten) Handel
                part["counterparties"][p["counterparty"]] = part["counterparties"].get(p["counterparty"], 0) + 1
            part["trades"][p["trade_id"]] = event.seq
        elif event.type == CAREER:
            roles = self.cfg["career"]["roles"]
            c = part["career"]
            c["changes"] += 1
            c["since_day"] = p["day"]
            c["company_id"], c["role"] = p["company_id"], p["role"]
            if p["role"] is not None:
                c["best_rung"] = max(c["best_rung"], roles.index(p["role"]))
        elif event.type == FOUNDED:
            part["founded"][p["company_id"]] = {"day": p["day"], "open": True, "seq": event.seq}
        else:
            part["founded"][p["company_id"]]["open"] = False
