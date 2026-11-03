"""Regeln der Kampfsimulation (versioniert, datengetrieben) und Verträglichkeit mit der CEE."""
from __future__ import annotations

import json
from importlib import resources
from typing import Any

from .errors import SimError

COMMANDS = ("light", "heavy", "dodge", "block", "stun", "slow", "flee")


def load_sim_rules(name: str = "sim_rules_v1.json") -> dict[str, Any]:
    cfg = json.loads(resources.files("mmo_sim").joinpath("data", name).read_text(encoding="utf-8"))
    validate_sim_rules(cfg)
    return cfg


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
    a = cfg["actions"]
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
    if cfg["report"]["min_duration_s"] < cee_rules["combat"]["encounter"]["min_duration_s"]:
        problems.append("report.min_duration_s liegt unter dem CEE-Minimum")
    if cfg["max_ticks"] // cfg["ticks_per_second"] > cee_rules["combat"]["encounter"]["max_duration_s"]:
        problems.append("max_ticks überschreitet die maximale CEE-Dauer")
    return problems
