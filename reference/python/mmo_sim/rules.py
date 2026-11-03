"""Regeln der Kampfsimulation (versioniert, datengetrieben) und Verträglichkeit mit der CEE."""
from __future__ import annotations

import copy
import json
from importlib import resources
from typing import Any

from .errors import SimError

COMMANDS = ("light", "heavy", "dodge", "block", "stun", "slow", "flee")


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

    return {
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


def check_compatibility(cfg: dict[str, Any], cee_rules: Any) -> list[str]:
    """Meldet Aktionen, deren mögliche Rate das Plausibilitätslimit der CEE übersteigt."""
    problems = []
    cee_actions = cee_rules["combat"]["actions"]
    for action, rate in max_actions_per_minute(cfg).items():
        limit = cee_actions[action]["max_per_minute"]
        if rate > limit:
            problems.append(f"{action}: Simulation erlaubt bis {rate}/min, CEE-Limit {limit}/min")
    effects = ability_effects(cfg)
    catalog = {k for k in cee_rules["combat"].get("abilities", {}) if not k.startswith("_")}
    for name in sorted(set(effects) - catalog):
        problems.append(f"ability_effects.{name}: Fähigkeit existiert in den CEE-Regeln nicht")
    if cfg["report"]["min_duration_s"] < cee_rules["combat"]["encounter"]["min_duration_s"]:
        problems.append("report.min_duration_s liegt unter dem CEE-Minimum")
    if cfg["max_ticks"] // cfg["ticks_per_second"] > cee_rules["combat"]["encounter"]["max_duration_s"]:
        problems.append("max_ticks überschreitet die maximale CEE-Dauer")
    return problems
