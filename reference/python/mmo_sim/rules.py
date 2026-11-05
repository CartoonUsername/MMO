"""Regeln der Kampfsimulation (versioniert, datengetrieben) und Verträglichkeit mit der CEE."""
from __future__ import annotations

import copy
import json
from importlib import resources
from typing import Any

from .errors import SimError

COMMANDS = ("light", "heavy", "dodge", "block", "stun", "slow", "flee")
GROUP_COMMANDS = ("heal", "shield")  # nur im Gruppenkampf (ADR-0022)
MULTI_COMMANDS = ("sweep", "target_1", "target_2", "target_3")  # nur im Kampf gegen mehrere Gegner (ADR-0026)


def load_sim_rules(name: str = "sim_rules_v1.json") -> dict[str, Any]:
    cfg = json.loads(resources.files("mmo_sim").joinpath("data", name).read_text(encoding="utf-8"))
    validate_sim_rules(cfg)
    return cfg


EFFECT_KEYS = {
    # Schlüssel -> (Art, Mindestwert, Höchstwert); Art: mul = Promille-Faktor, min = Minimum, add = Summe
    "heavy_damage_permille": ("mul", 1, 10000), "light_damage_permille": ("mul", 1, 10000),
    "damage_taken_permille": ("mul", 1, 10000), "block_damage_permille": ("min", 0, 1000),
    "stun_ticks_bonus": ("add", -100, 100), "slow_ticks_bonus": ("add", -100, 100),
    "parry_stagger_bonus": ("add", -100, 100), "dodge_cost_delta": ("add", -100, 100),
    "dodge_cooldown_delta": ("add", -100, 100), "stamina_regen_bonus": ("add", 0, 20),
}


def ability_effects(cfg: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {k: v for k, v in cfg.get("ability_effects", {}).items() if not k.startswith("_")}


def combine_effects(cfg: dict[str, Any], equipped: Any) -> dict[str, int]:
    """Gesamtwirkung der ausgerüsteten Fähigkeiten (leer = keine Änderung). Unbekannte Namen ohne Wirkung sind erlaubt
    (z. B. Fähigkeiten für Gruppen), ungültige Eingaben nicht."""
    if equipped is None:
        return {}
    if not isinstance(equipped, (list, tuple)) or any(not isinstance(a, str) for a in equipped) or len(set(equipped)) != len(equipped):
        raise SimError("equipped muss eine Liste eindeutiger Fähigkeitsnamen sein")
    table, out = ability_effects(cfg), {}
    for name in sorted(equipped):
        for key, val in table.get(name, {}).items():
            kind = EFFECT_KEYS[key][0]
            if key not in out:
                out[key] = val
            elif kind == "mul":
                out[key] = out[key] * val // 1000
            elif kind == "min":
                out[key] = min(out[key], val)
            else:
                out[key] += val
    return out


def merge_gear(cfg: dict[str, Any], fx: dict[str, int], gear: Any) -> dict[str, int]:
    """Wirkungen getragener Ausrüstung (Schlüssel wie `EFFECT_KEYS`, bereits zusammengefasst) auf die Fähigkeitswirkung legen und prüfen."""
    if gear is None:
        return fx
    if not isinstance(gear, dict):
        raise SimError("gear muss ein Objekt sein")
    out = dict(fx)
    for key, val in gear.items():
        if key not in EFFECT_KEYS:
            raise SimError(f"gear: unbekannte Wirkung {key!r}")
        kind, lo, hi = EFFECT_KEYS[key]
        if not isinstance(val, int) or isinstance(val, bool) or not lo <= val <= hi:
            raise SimError(f"gear.{key}: Wert außerhalb {lo}..{hi}")
        if key not in out:
            out[key] = val
        elif kind == "mul":
            out[key] = out[key] * val // 1000
        elif kind == "min":
            out[key] = min(out[key], val)
        else:
            out[key] += val
    return out


def validate_group_rules(cfg: dict[str, Any]) -> None:
    g = cfg["group"]

    def ok(v: Any, lo: int = 1) -> bool:
        return isinstance(v, int) and not isinstance(v, bool) and v >= lo

    if not ok(g["max_party"]) or g["max_party"] > 8:
        raise SimError("group.max_party muss 1..8 sein")
    if not ok(g["opponent_hp_per_extra_member_permille"], 0):
        raise SimError("group.opponent_hp_per_extra_member_permille muss >= 0 sein")
    h, s = g["heal"], g["shield"]
    if not (ok(h["amount"]) and ok(h["cost"], 0) and ok(h["busy"]) and ok(h["cooldown"], 0)):
        raise SimError("group.heal ungültig")
    if not (ok(s["absorb"]) and ok(s["ticks"]) and ok(s["cost"], 0) and ok(s["busy"]) and ok(s["cooldown"], 0)):
        raise SimError("group.shield ungültig")
    if not ok(g["threat"]["heal_permille"], 0):
        raise SimError("group.threat.heal_permille ungültig")
    cmds = g["ability_commands"]
    if any(c not in GROUP_COMMANDS for c in cmds.values()) or len(set(cmds.values())) != len(cmds):
        raise SimError("group.ability_commands: nur heal/shield, je Befehl höchstens eine Fähigkeit")


SKILL_KINDS = ("burst_dot", "evade", "mitigate", "restore_stamina")  # Arten eigener Fähigkeitsbefehle (ADR-0027)


def skills(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in cfg.get("skills", {}).items() if not k.startswith("_")}


def skill_commands(cfg: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(skills(cfg)))


def element_permille(cfg: dict[str, Any], attacker: str | None, defender: str | None) -> int:
    """Schadensfaktor (Promille) eines Elements gegen ein Element; 1000 ohne `elements`-Tabelle oder ohne Angabe."""
    el = cfg.get("elements")
    if not el or not attacker or not defender:
        return 1000
    if attacker == defender:
        return el["same_permille"]
    if defender in el["strong"].get(attacker, ()):
        return el["strong_permille"]
    if attacker in el["strong"].get(defender, ()):
        return el["weak_permille"]
    return 1000


def validate_element_rules(cfg: dict[str, Any]) -> None:
    el = cfg["elements"]
    for k in ("strong_permille", "weak_permille", "same_permille"):
        if not isinstance(el.get(k), int) or isinstance(el.get(k), bool) or not 1 <= el[k] <= 3000:
            raise SimError(f"elements.{k} ungültig")
    if el["weak_permille"] > 1000 or el["strong_permille"] < 1000:
        raise SimError("elements: strong >= 1000 >= weak nötig")
    sw = el.get("switch_ticks", 0)
    if not isinstance(sw, int) or isinstance(sw, bool) or not 0 <= sw <= 600:
        raise SimError("elements.switch_ticks ungültig (0..600)")
    names = set(el["strong"]) | {x for v in el["strong"].values() for x in v}
    for a, ds in el["strong"].items():
        if not isinstance(ds, list) or a in ds:
            raise SimError(f"elements.strong.{a} ungültig")
    for name, s in skills(cfg).items():
        if "element" in s and s["element"] not in names:
            raise SimError(f"skills.{name}: unbekanntes Element")


def validate_skill_rules(cfg: dict[str, Any]) -> None:
    if "multi" not in cfg:
        raise SimError("skills brauchen multi")

    def ok(v: Any, lo: int = 1) -> bool:
        return isinstance(v, int) and not isinstance(v, bool) and v >= lo

    taken = set(COMMANDS + GROUP_COMMANDS + MULTI_COMMANDS)
    seen: set[str] = set()
    for name, s in skills(cfg).items():
        if name in taken or not name.isidentifier():
            raise SimError(f"skills.{name}: Name ungültig oder schon als Befehl vergeben")
        if not isinstance(s.get("ability"), str) or not s["ability"] or s["ability"] in seen:
            raise SimError(f"skills.{name}: ability fehlt oder ist schon vergeben")
        seen.add(s["ability"])
        if s.get("kind") not in SKILL_KINDS or not (ok(s.get("cost"), 0) and ok(s.get("busy")) and ok(s.get("cooldown"), 0)):
            raise SimError(f"skills.{name}: kind/cost/busy/cooldown ungültig")
        if s.get("counts_as") not in (None, "heavy_hit"):
            raise SimError(f"skills.{name}: counts_as nur heavy_hit oder null")
        kind = s["kind"]
        if kind == "burst_dot":
            d = s.get("dot")
            if not ok(s.get("damage")) or not isinstance(d, dict) or not (ok(d.get("interval")) and ok(d.get("damage")) and ok(d.get("ticks"))):
                raise SimError(f"skills.{name}: damage/dot ungültig")
        elif kind == "evade":
            if not ok(s.get("ticks")):
                raise SimError(f"skills.{name}: ticks ungültig")
        elif kind == "mitigate":
            if not ok(s.get("ticks")) or not ok(s.get("damage_permille"), 0) or s["damage_permille"] > 1000:
                raise SimError(f"skills.{name}: ticks/damage_permille ungültig")
        elif not ok(s.get("amount")):
            raise SimError(f"skills.{name}: amount ungültig")


def validate_multi_rules(cfg: dict[str, Any]) -> None:
    if "group" not in cfg:
        raise SimError("multi braucht group")
    m = cfg["multi"]

    def ok(v: Any, lo: int = 1) -> bool:
        return isinstance(v, int) and not isinstance(v, bool) and v >= lo

    if not ok(m["max_opponents"]) or m["max_opponents"] > len(MULTI_COMMANDS) - 1:
        raise SimError(f"multi.max_opponents muss 1..{len(MULTI_COMMANDS) - 1} sein")
    s = m["sweep"]
    if not (ok(s["cost"], 0) and ok(s["busy"]) and ok(s["cooldown"], 0) and ok(s["damage"])):
        raise SimError("multi.sweep ungültig")


def validate_sim_rules(cfg: dict[str, Any]) -> None:
    def positive(v: Any) -> bool:
        return isinstance(v, int) and not isinstance(v, bool) and v > 0

    for key in ("ticks_per_second", "max_ticks", "max_inputs"):
        if not positive(cfg[key]):
            raise SimError(f"{key} muss eine positive ganze Zahl sein")
    for name in ("light", "precise", "heavy", "dodge", "block", "stun", "slow"):
        a = cfg["actions"].get(name)
        if a is None or not positive(a["busy"]) or a["cost"] < 0 or a["cooldown"] < 0:
            raise SimError(f"Aktion {name} fehlt oder ist ungültig")
    if cfg["actions"]["precise"]["busy"] < cfg["actions"]["light"]["busy"]:
        raise SimError("precise.busy darf nicht kürzer sein als light.busy")
    if "group" in cfg:
        validate_group_rules(cfg)
    if "multi" in cfg:
        validate_multi_rules(cfg)
    if "skills" in cfg:
        validate_skill_rules(cfg)
    if "elements" in cfg:
        validate_element_rules(cfg)
    if "enemy_abilities" in cfg:
        from .enemies import validate_enemy_rules
        validate_enemy_rules(cfg)
    for name, eff in ability_effects(cfg).items():
        if not isinstance(eff, dict) or not eff or set(eff) - set(EFFECT_KEYS):
            raise SimError(f"ability_effects.{name}: unbekannte oder fehlende Wirkung")
        for key, val in eff.items():
            _, lo, hi = EFFECT_KEYS[key]
            if not isinstance(val, int) or isinstance(val, bool) or not lo <= val <= hi:
                raise SimError(f"ability_effects.{name}.{key}: Wert außerhalb {lo}..{hi}")
    for name, o in cfg["opponents"].items():
        if not positive(o["hp"]) or not positive(o["level"]):
            raise SimError(f"Gegner {name}: hp/level müssen positiv sein")
        if o["attack_interval"] < 0 or (o["attack_interval"] > 0 and not positive(o["windup"])):
            raise SimError(f"Gegner {name}: Angriffsparameter ungültig")


def _per_minute(cfg: dict[str, Any], period_ticks: int) -> int:
    return 60 * cfg["ticks_per_second"] // period_ticks


def max_actions_per_minute(cfg: dict[str, Any]) -> dict[str, int]:
    """Obere Schranke der in einem Bericht möglichen Aktionszähler je Minute (CEE-Aktionsnamen).

    Offensive Aktionen sind durch Busy-/Cooldown-Zeiten begrenzt, defensive zusätzlich durch die
    Angriffsfrequenz des schnellsten angreifenden Gegners (Verlangsamung/Betäubung/Parade
    verlängern den Takt nur).
    """
    a = copy.deepcopy(cfg["actions"])
    # Bestfall: alle Fähigkeiten, die eine Aktion schneller machen, gleichzeitig ausgerüstet
    best_cd = sum(min(0, e.get("dodge_cooldown_delta", 0)) for e in ability_effects(cfg).values())
    a["dodge"]["cooldown"] = max(0, a["dodge"]["cooldown"] + best_cd)
    cycles = [o["attack_interval"] + o["windup"] for o in cfg["opponents"].values() if o["attack_interval"] > 0]
    attack_bound = _per_minute(cfg, min(cycles)) if cycles else 0

    def period(name: str) -> int:
        return max(a[name]["busy"], a[name]["cooldown"], 1)

    def defensive(name: str) -> int:
        return min(_per_minute(cfg, period(name)), attack_bound)

    group = {}
    if "group" in cfg:  # Unterstützung im Gruppenkampf: begrenzt durch Busy/Abklingzeit
        g = cfg["group"]
        group = {"ally_heal": _per_minute(cfg, max(g["heal"]["busy"], g["heal"]["cooldown"], 1)),
                 "ally_shield": _per_minute(cfg, max(g["shield"]["busy"], g["shield"]["cooldown"], 1))}
    extra = {}
    for sk in skills(cfg).values():  # Einsätze eigener Befehle zählen als CEE-Aktion
        if sk["counts_as"]:
            extra[sk["counts_as"]] = extra.get(sk["counts_as"], 0) + _per_minute(cfg, max(sk["busy"], sk["cooldown"], 1))
    out = {
        **group,
        "light_hit": _per_minute(cfg, period("light")),
        "precise_hit": _per_minute(cfg, period("precise")),
        "heavy_hit": _per_minute(cfg, period("heavy")),
        "dodge": defensive("dodge"),
        "perfect_dodge": defensive("dodge"),
        "block": defensive("block"),
        "parry": defensive("block"),
        "stun_applied": _per_minute(cfg, period("stun")),
        "slow_applied": _per_minute(cfg, period("slow")),
    }
    for k, v in extra.items():
        out[k] += v
    return out


def check_compatibility(cfg: dict[str, Any], cee_rules: Any) -> list[str]:
    """Meldet Aktionen, deren mögliche Rate das Plausibilitätslimit der CEE übersteigt."""
    problems = []
    cee_actions = cee_rules["combat"]["actions"]
    for action, rate in max_actions_per_minute(cfg).items():
        limit = cee_actions[action]["max_per_minute"]
        if rate > limit:
            problems.append(f"{action}: Simulation erlaubt bis {rate}/min, CEE-Limit {limit}/min")
    effects = ability_effects(cfg)
    cat_skills = {k for k in cee_rules["combat"].get("abilities", {}) if not k.startswith("_")}
    for name, sk in sorted(skills(cfg).items()):
        if sk["ability"] not in cat_skills:
            problems.append(f"skills.{name}: Fähigkeit {sk['ability']} existiert in den CEE-Regeln nicht")
    for name in sorted(set(cfg.get("group", {}).get("ability_commands", {})) - {k for k in cee_rules["combat"].get("abilities", {}) if not k.startswith("_")}):
        problems.append(f"group.ability_commands.{name}: Fähigkeit existiert in den CEE-Regeln nicht")
    catalog = {k for k in cee_rules["combat"].get("abilities", {}) if not k.startswith("_")}
    for name in sorted(set(effects) - catalog):
        problems.append(f"ability_effects.{name}: Fähigkeit existiert in den CEE-Regeln nicht")
    if cfg["report"]["min_duration_s"] < cee_rules["combat"]["encounter"]["min_duration_s"]:
        problems.append("report.min_duration_s liegt unter dem CEE-Minimum")
    if cfg["max_ticks"] // cfg["ticks_per_second"] > cee_rules["combat"]["encounter"]["max_duration_s"]:
        problems.append("max_ticks überschreitet die maximale CEE-Dauer")
    return problems
