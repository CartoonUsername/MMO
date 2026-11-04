"""Forschung, Epochen und Entdecker auf Siedlungsebene (AP 12, ADR-0051). Serverautoritativ, ohne CEE-Ereignisse.

* Die **Weltepoche** setzt der Betrieb (`set_epoch`, bewusst kein Spielerbefehl): Techniken späterer Epochen sind gesperrt, bis die Welt dort ist.
* **Jede Siedlung** erforscht selbst (Blueprint §43): Bewohner zahlen Münzen/Material in ein Forschungsprojekt; danach läuft die Forschungszeit.
* Die erste Siedlung der Welt, die eine Technik abschließt, hat den **Entdecker** (wichtigster Beitragszahler): Titel und Chronikeintrag, dazu ein
  zeitlich begrenzter Vorsprung `lead_days`. Während des Vorsprungs können andere unabhängig zum vollen Preis forschen oder vom Entdecker eine
  **Lizenz** kaufen (Preis geht an den Entdecker, zahlt eine Figur der Käufer-Siedlung). Danach ist Übernahme für alle günstig. Niemand sperrt eine Technik dauerhaft.
* Wirkung: Siedlungsprojekte können Stufen an Techniken knüpfen (`requires_tech` in den Siedlungsregeln).
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable

from .errors import WorldError
from .inventory import Inventory
from .settlements import SettlementService


def load_research_rules(name: str = "research_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_research_rules(r: dict[str, Any], settlement_rules: dict[str, Any] | None = None) -> None:
    for k in ("lead_days", "license_price", "adopt_permille", "min_research_days"):
        if not _is_int(r[k]) or r[k] < 0:
            raise WorldError(f"research_rules.{k} ungültig")
    if not 1 <= r["adopt_permille"] <= 1000 or not r["epochs"]:
        raise WorldError("research_rules: adopt_permille/epochs ungültig")
    for tid, t in r["techs"].items():
        if not 0 <= t["epoch"] < len(r["epochs"]) or not _is_int(t["days"]) or t["days"] < 1:
            raise WorldError(f"research_rules: {tid}: Epoche/Dauer ungültig")
        if any(q not in r["techs"] or q == tid for q in t["requires"]):
            raise WorldError(f"research_rules: {tid}: Voraussetzung unbekannt")
        c = t["cost"]
        if not _is_int(c["coins"]) or c["coins"] < 0 or any(not _is_int(n) or n <= 0 for n in c["items"].values()):
            raise WorldError(f"research_rules: {tid}: Kosten ungültig")
    seen: set[str] = set()                                   # Voraussetzungen ohne Kreis
    def walk(t: str, path: tuple[str, ...]) -> None:
        if t in path:
            raise WorldError("research_rules: Voraussetzungskreis")
        for q in r["techs"][t]["requires"]:
            walk(q, path + (t,))
    for t in r["techs"]:
        walk(t, ())
    if settlement_rules:
        for pid, p in settlement_rules["projects"].items():
            for lv in p["levels"]:
                if lv.get("requires_tech") and lv["requires_tech"] not in r["techs"]:
                    raise WorldError(f"settlement_rules: {pid}: Technik {lv['requires_tech']} unbekannt")


class ResearchService:
    def __init__(self, settlements: SettlementService, inventory: Inventory, coin: str, rules: dict[str, Any],
                 day_provider: Callable[[], int]) -> None:
        validate_research_rules(rules, settlements.R)
        self.st, self.inv, self.coin, self.R, self.day = settlements, inventory, coin, rules, day_provider
        self.epoch = 0
        self.known: dict[str, dict[str, dict[str, Any]]] = {}     # Ort -> Technik -> {day, via}
        self.projects: dict[str, dict[str, Any]] = {}             # "ort:technik" -> {have, paid, licensed, permille, done_day, contrib}
        self.world: dict[str, dict[str, Any]] = {}                # Technik -> {site, char, day, lead_until}
        self.titles: dict[str, list[str]] = {}
        self.history: list[dict[str, Any]] = []
        self.last_day = 0
        self.record: Callable[..., Any] = lambda *a, **k: None                    # Chronik (AP 13)
        settlements.tech_known = self.knows

    @property
    def active(self) -> bool:
        return bool(self.epoch or self.known or self.projects or self.world or self.last_day)

    # -- Hilfen -------------------------------------------------------------------------
    def _tech(self, tech: str) -> dict[str, Any]:
        t = self.R["techs"].get(tech) if isinstance(tech, str) else None
        if t is None:
            raise WorldError("Unbekannte Technik")
        return t

    def knows(self, site: str, tech: str) -> bool:
        return tech in self.known.get(site, {})

    def set_epoch(self, n: int) -> None:
        """Nur für den Betrieb (Weltgeschichte/Updates). Epochen gehen nur vorwärts."""
        if not _is_int(n) or not self.epoch <= n < len(self.R["epochs"]):
            raise WorldError("Epoche ungültig (nur vorwärts, innerhalb der Liste)")
        self.epoch = n
        if n > 0:
            self.history.append({"day": self.day(), "kind": "epoch", "epoch": self.R["epochs"][n]["id"]})
            self.record("epoch", [], key=f"epoch:{n}", name=self.R["epochs"][n]["name"])

    def lead_active(self, tech: str, today: int | None = None) -> bool:
        w = self.world.get(tech)
        return bool(w) and (self.day() if today is None else today) < w["lead_until"]

    def _permille(self, tech: str, licensed: bool) -> int:
        if tech in self.world and (licensed or not self.lead_active(tech)):
            return self.R["adopt_permille"]
        return 1000

    def cost(self, tech: str, permille: int) -> dict[str, int]:
        c = self._tech(tech)["cost"]
        out = {k: max(1, n * permille // 1000) for k, n in c["items"].items()}
        if c["coins"]:
            out[self.coin] = max(1, c["coins"] * permille // 1000)
        return out

    def _days(self, tech: str, permille: int) -> int:
        d = self._tech(tech)["days"]
        return d if permille >= 1000 else max(self.R["min_research_days"], d * permille // 1000)

    # -- Aktionen -------------------------------------------------------------------------
    def start(self, char: str, site: str, tech: str) -> dict[str, Any]:
        t = self._tech(tech)
        self.st._need_open(site)
        if not self.st.is_resident(char, site):
            raise WorldError("Nur Grundstücksbesitzer des Ortes dürfen Forschung beginnen")
        if self.knows(site, tech):
            raise WorldError("Dieser Ort kennt die Technik schon")
        if f"{site}:{tech}" in self.projects:
            raise WorldError("Die Forschung läuft schon")
        if t["epoch"] > self.epoch:
            raise WorldError("Diese Technik gehört zu einer späteren Epoche der Welt")
        if any(not self.knows(site, q) for q in t["requires"]):
            raise WorldError("Voraussetzungen fehlen: " + ", ".join(q for q in t["requires"] if not self.knows(site, q)))
        pm = self._permille(tech, False)
        self.projects[f"{site}:{tech}"] = {"have": {}, "permille": pm, "licensed": False, "done_day": None, "contrib": {}}
        return {"permille": pm, "cost": self.cost(tech, pm)}

    def license(self, char: str, site: str, tech: str) -> None:
        """Kauft beim Entdecker eine Lizenz: danach gilt der günstige Übernahmepreis, auch während des Vorsprungs."""
        self._tech(tech)
        pr = self.projects.get(f"{site}:{tech}")
        w = self.world.get(tech)
        if pr is None or w is None:
            raise WorldError("Keine laufende Forschung oder noch niemand hat die Technik entdeckt")
        if not self.st.is_resident(char, site):
            raise WorldError("Nur Bewohner des Ortes dürfen eine Lizenz kaufen")
        if pr["licensed"] or pr["permille"] < 1000:
            raise WorldError("Schon günstig oder lizenziert")
        if pr["done_day"] is not None:
            raise WorldError("Forschung ist schon abgeschlossen")
        price = self.R["license_price"]
        if w["char"] == char:
            raise WorldError("Du bist selbst der Entdecker")
        self.inv.apply_many([(char, {self.coin: price}, {}), (w["char"], {}, {self.coin: price})])
        pr["licensed"], pr["permille"] = True, self.R["adopt_permille"]
        new = self.cost(tech, pr["permille"])
        self._reprice(site, tech, pr, new, char)

    def _reprice(self, site: str, tech: str, pr: dict[str, Any], new: dict[str, int], refund_to: str | None = None) -> None:
        """Preis gesunken: Eingezahltes über dem neuen Preis geht zurück (an die Lizenznehmer*in bzw. den größten Beitragszahler)."""
        back: dict[str, int] = {}
        for k in list(pr["have"]):
            extra = pr["have"][k] - new.get(k, 0)
            if extra > 0:
                back[k], pr["have"][k] = extra, new.get(k, 0)
        who = refund_to or (max(pr["contrib"].items(), key=lambda kv: (kv[1], kv[0]))[0] if pr["contrib"] else None)
        if back and who:
            self.inv.apply(who, {}, back)
        self._maybe_done(site, tech, pr)

    def contribute(self, char: str, site: str, tech: str, coins: int = 0, items: dict[str, int] | None = None) -> dict[str, Any]:
        self._tech(tech)
        pr = self.projects.get(f"{site}:{tech}")
        if pr is None:
            raise WorldError("Keine laufende Forschung")
        if not self.st.is_resident(char, site):
            raise WorldError("Nur Grundstücksbesitzer des Ortes dürfen beitragen")
        if pr["done_day"] is not None:
            raise WorldError("Die Forschungsarbeit läuft, es wird nichts mehr gebraucht")
        full = self.cost(tech, pr["permille"])
        want = dict(items or {})
        if coins:
            want[self.coin] = want.get(self.coin, 0) + coins
        if not want or any(not _is_int(q) or q <= 0 for q in want.values()):
            raise WorldError("Beitrag ungültig")
        for k, q in want.items():
            if k not in full:
                raise WorldError(f"{k} wird für diese Forschung nicht gebraucht")
            if pr["have"].get(k, 0) + q > full[k]:
                raise WorldError(f"Zu viel {k}: es fehlen nur {full[k] - pr['have'].get(k, 0)}")
        self.inv.apply(char, want, {})
        for k, q in want.items():
            pr["have"][k] = pr["have"].get(k, 0) + q
        pr["contrib"][char] = pr["contrib"].get(char, 0) + sum(want.values())
        self._maybe_done(site, tech, pr)
        return {"funded": pr["done_day"] is not None}

    def _maybe_done(self, site: str, tech: str, pr: dict[str, Any]) -> None:
        full = self.cost(tech, pr["permille"])
        if pr["done_day"] is None and all(pr["have"].get(k, 0) >= q for k, q in full.items()):
            pr["done_day"] = self.day() + self._days(tech, pr["permille"])

    # -- Tagesschritt -----------------------------------------------------------------------
    def advance(self, day: int) -> list[dict[str, Any]]:
        if not _is_int(day) or day <= self.last_day:
            return []
        out: list[dict[str, Any]] = []
        for key in sorted(self.projects):
            pr = self.projects[key]
            tech = key.split(":")[1]
            if pr["done_day"] is None and pr["permille"] == 1000 and tech in self.world and not self.lead_active(tech, day):
                pr["permille"] = self.R["adopt_permille"]          # Vorsprung vorbei: günstige Übernahme für alle
                self._reprice(key.split(":")[0], tech, pr, self.cost(tech, pr["permille"]))
            if pr["done_day"] is not None and pr["done_day"] <= day:
                site, tech = key.split(":")
                out.append(self._finish(site, tech, pr, day))
        self.last_day = day
        return out

    def _finish(self, site: str, tech: str, pr: dict[str, Any], day: int) -> dict[str, Any]:
        del self.projects[f"{site}:{tech}"]
        first = tech not in self.world
        via = "research" if first or pr["permille"] == 1000 else ("license" if pr["licensed"] else "adopt")
        self.known.setdefault(site, {})[tech] = {"day": day, "via": via}
        ev = {"kind": "tech", "tech": tech, "site": site, "first": first, "via": via}
        if first:
            top = sorted(pr["contrib"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            self.world[tech] = {"site": site, "char": top, "day": day, "lead_until": day + self.R["lead_days"]}
            self.titles.setdefault(top, []).append(f"Erfinder: {self._tech(tech)['name']}")
            ev["pioneer"] = top
            self.history.append({"day": day, "kind": "discovery", "tech": tech, "site": site, "char": top})
            self.record("tech_discovered", [top], key=f"tech:{tech}", name=self._tech(tech)["name"], site=site)
        return ev

    # -- Sicht -------------------------------------------------------------------------------
    def view(self, char: str) -> dict[str, Any]:
        today = self.day()
        mine = sorted({p["site"] for p in self.st.owned_by(char)})
        techs = {}
        for tid, t in self.R["techs"].items():
            w = self.world.get(tid)
            techs[tid] = {"name": t["name"], "epoch": t["epoch"], "locked": t["epoch"] > self.epoch, "requires": t["requires"], "days": t["days"],
                          "unlocks": t["unlocks"], "cost_full": self.cost(tid, 1000), "cost_now": self.cost(tid, self._permille(tid, False)),
                          "pioneer": None if w is None else {"site": w["site"], "char": w["char"], "day": w["day"], "lead_active": today < w["lead_until"], "lead_until": w["lead_until"]},
                          "known_in": sorted(s for s in self.known if tid in self.known[s])}
        running = []
        for key, pr in sorted(self.projects.items()):
            site, tech = key.split(":")
            need = self.cost(tech, pr["permille"])
            running.append({"site": site, "tech": tech, "permille": pr["permille"], "licensed": pr["licensed"], "done_day": pr["done_day"],
                            "need": {k: {"need": q, "have": pr["have"].get(k, 0)} for k, q in need.items()}})
        return {"epoch": {"index": self.epoch, **self.R["epochs"][self.epoch]}, "techs": techs, "running": running, "my_sites": mine,
                "titles": self.titles.get(char, []), "license_price": self.R["license_price"], "history": self.history[-20:]}

    def check(self) -> list[str]:
        errs = []
        for s, ks in self.known.items():
            for t in ks:
                if t not in self.R["techs"]:
                    errs.append(f"{s}: Technik {t} unbekannt")
                elif any(q not in ks for q in self.R["techs"][t]["requires"]):
                    errs.append(f"{s}: {t} ohne Voraussetzungen")
        for key in self.projects:
            site, tech = key.split(":")
            if tech not in self.R["techs"] or not self.st.is_open(site):
                errs.append(f"{key}: Forschung ungültig")
        return errs

    def to_json(self) -> str:
        return json.dumps({"epoch": self.epoch, "known": self.known, "projects": self.projects, "world": self.world, "titles": self.titles,
                           "history": self.history, "last_day": self.last_day}, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        d = json.loads(text)
        self.epoch, self.known, self.projects, self.world = d["epoch"], d["known"], d["projects"], d["world"]
        self.titles, self.history, self.last_day = d["titles"], d["history"], d["last_day"]
