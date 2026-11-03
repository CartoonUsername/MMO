"""Firmenproduktion: Läger, Produktionslinien, Aufträge, Abnehmer. Siehe ADR-0016.

* Das Lager einer Firma ist ihr Inventarkonto `company:<id>` (neben den Münzen); die Lagerkapazität kommt vom Gebäude.
* Ein Auftrag (`start`) bindet eine Linie (Anzahl nach Gebäudestufe) und einen Mitarbeiter, der das Rezept beherrscht.
  Die Eingaben aller Chargen werden sofort aus dem Lager in ein Auftragskonto `production:<id>` gelegt.
* Fortschritt gibt es nur im Tagesabschluss (`CompanyService.advance_day`) und nur an Tagen, an denen der Arbeiter noch
  angestellt ist und seinen Lohn erhalten hat. Eine Charge dauert je nach Rezeptstufe Tage; zum Abschluss müssen Lagerplatz
  und Betriebskosten (Geldsenke) vorhanden sein, sonst wartet sie.
* Ausbeute und Qualität sind gedeckelt (Massenfertigung erreicht keine Meisterqualität). Es entstehen KEINE CEE-Berichte:
  Offline-Produktion bringt keinen Berufsfortschritt (bestätigte Leitlinie: Offline-Produktion begrenzt).
* Abnehmer: ein serverinterner NPC-Händler kauft Lagerware zu einem Bruchteil des Referenzwerts mit Tageslimit je Firma;
  der Erlös ist Firmenumsatz (`record_revenue`).
Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable

from mmo_cee.crafting import quality_score, quality_tier, recipe_blockers
from mmo_cee.economy import reference_value
from mmo_cee.service import CharacterService

from .company import CompanyRegistry, building
from .company_service import CompanyService, SINK
from .errors import WorldError
from .inventory import Inventory, key


def load_production_rules(name: str = "production_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_production_rules(pr: dict[str, Any], cee_rules: Any, company_rules: dict[str, Any]) -> None:
    if int(cee_rules.version) < pr["requires_cee_rules_min"] or "crafting" not in cee_rules:
        raise WorldError("production_rules benötigen CEE-Regeln mit Herstellung (>= v7)")
    lv = pr["lines_by_building_level"]
    if len(lv) != len(company_rules["building_levels"]) or any(not _is_int(x) or x < 1 for x in lv) or lv != sorted(lv):
        raise WorldError("lines_by_building_level muss je Gebäudestufe ein aufsteigender Wert >= 1 sein")
    tiers = {str(r["tier"]) for r in cee_rules["crafting"]["recipes"].values()}
    for table in ("days_per_batch_by_tier", "upkeep_per_batch_by_tier"):
        if not tiers <= set(pr[table]) or any(not _is_int(v) or v < 1 for v in pr[table].values()):
            raise WorldError(f"{table} muss alle Rezeptstufen mit Werten >= 1 abdecken")
    for k in ("batch_size", "max_batches_per_job"):
        if not _is_int(pr[k]) or pr[k] < 1:
            raise WorldError(f"{k} ungültig")
    if not _is_int(pr["output_permille"]) or not 1 <= pr["output_permille"] <= 1000:
        raise WorldError("output_permille muss 1..1000 sein")
    if pr["max_quality"] not in cee_rules["crafting"]["tiers"]:
        raise WorldError("max_quality unbekannt")
    n = pr["npc_buyer"]
    if not _is_int(n["permille"]) or not 1 <= n["permille"] <= 1000 or not _is_int(n["daily_cap"]) or n["daily_cap"] < 1:
        raise WorldError("npc_buyer ungültig")
    maxb = max(r["max_batch"] for r in cee_rules["crafting"]["recipes"].values())
    if pr["batch_size"] > min(r["max_batch"] for r in cee_rules["crafting"]["recipes"].values()) or maxb < 1:
        raise WorldError("batch_size übersteigt die Chargengrenze eines Rezepts")


def job_owner(job_id: str) -> str:
    return f"production:{job_id}"


class ProductionService:
    def __init__(self, service: CharacterService, inventory: Inventory, companies: CompanyService, rules: dict[str, Any],
                 day_provider: Callable[[], int], server_id: str = "srv1", trading: Any = None) -> None:
        self.cee, self.inv, self.cs, self.reg, self.pr = service, inventory, companies, companies.reg, rules
        self.trading = trading  # liefert den aktuellen Referenzwert (Preisdynamik); ohne: Regeltabelle
        validate_production_rules(rules, service.rules, companies.cr)
        self.day, self.server_id, self.coin = day_provider, server_id, companies.coin
        self.crafting = service.rules["crafting"]
        self.jobs: dict[str, dict[str, Any]] = {}
        self.npc_sold: dict[str, dict[str, int]] = {}
        self._counter = 0
        companies.day_hooks.append(self._tick)
        companies.close_hooks.append(self._on_close)

    @property
    def active(self) -> bool:
        return self._counter > 0 or bool(self.npc_sold)

    # -- Lager ---------------------------------------------------------------------------
    def store_of(self, company_id: str) -> str:
        return self.reg.treasury_owner(company_id)

    def stock(self, company_id: str) -> dict[str, int]:
        return {k: v for k, v in self.inv.holdings(self.store_of(company_id)).items() if k != self.coin}

    def used_capacity(self, company_id: str) -> int:
        return sum(self.stock(company_id).values())

    def capacity(self, c: dict[str, Any]) -> int:
        return building(self.reg.cr, c["building_level"])["storage"]

    def _item(self, item_key: str) -> tuple[str, str]:
        if item_key == self.coin:
            raise WorldError("Münzen sind kein Lagerware")
        if not isinstance(item_key, str) or item_key.count("@") != 1:
            raise WorldError("Ungültiger Gegenstandsschlüssel")
        name, grade = item_key.split("@")
        if name not in self.cee.rules["economy"]["items"] or grade not in self.cee.rules["economy"]["grade_permille"]:
            raise WorldError("Unbekannter Gegenstand")
        return name, grade

    @staticmethod
    def _qty(q: Any) -> int:
        if not _is_int(q) or q < 1:
            raise WorldError("Menge muss eine positive ganze Zahl sein")
        return q

    def stock_in(self, actor: str, company_id: str, item_key: str, qty: int) -> None:
        self.day()
        c = self.cs._need_manage(company_id, actor)
        self._item(item_key)
        self._qty(qty)
        if self.used_capacity(company_id) + qty > self.capacity(c):
            raise WorldError("Lagerkapazität überschritten")
        self.inv.apply_many([(actor, {item_key: qty}, {}), (self.store_of(company_id), {}, {item_key: qty})])

    def stock_out(self, actor: str, company_id: str, item_key: str, qty: int) -> None:
        self.day()
        self.cs._need_manage(company_id, actor)
        self._item(item_key)
        self._qty(qty)
        self.inv.apply_many([(self.store_of(company_id), {item_key: qty}, {}), (actor, {}, {item_key: qty})])

    # -- Aufträge --------------------------------------------------------------------------
    def lines(self, c: dict[str, Any]) -> int:
        return self.pr["lines_by_building_level"][c["building_level"] - 1]

    def jobs_of(self, company_id: str) -> list[str]:
        return sorted(k for k, j in self.jobs.items() if j["company"] == company_id)

    def per_batch_inputs(self, recipe_id: str, grade: str) -> dict[str, int]:
        return {key(m, grade): n * self.pr["batch_size"] for m, n in self.crafting["recipes"][recipe_id]["inputs"].items()}

    def batch_output(self, recipe_id: str) -> int:
        return self.crafting["recipes"][recipe_id]["output"]["qty"] * self.pr["batch_size"] * self.pr["output_permille"] // 1000

    def start(self, actor: str, company_id: str, worker: str, recipe_id: str, batches: int, grade: str) -> str:
        self.day()
        c = self.cs._need_manage(company_id, actor)
        if not isinstance(recipe_id, str) or recipe_id not in self.crafting["recipes"]:
            raise WorldError("Unbekanntes Rezept")
        if not isinstance(grade, str) or grade not in self.crafting["material_grades"]:
            raise WorldError("Unbekannte Materialgüte")
        if not _is_int(batches) or not 1 <= batches <= self.pr["max_batches_per_job"]:
            raise WorldError(f"Chargen 1..{self.pr['max_batches_per_job']}")
        if not isinstance(worker, str) or worker not in c["employees"]:
            raise WorldError("Arbeiter ist hier nicht angestellt")
        if any(j["worker"] == worker for j in self.jobs.values()):
            raise WorldError("Arbeiter ist bereits einem Auftrag zugeteilt")
        if len(self.jobs_of(company_id)) >= self.lines(c):
            raise WorldError("Keine freie Produktionslinie (Gebäude ausbauen)")
        state = self.cee.state(worker)
        blockers = recipe_blockers(state, self.cee.rules, recipe_id)
        if blockers:
            raise WorldError(f"Arbeiter beherrscht das Rezept nicht: {blockers}")
        recipe = self.crafting["recipes"][recipe_id]
        score = quality_score(state, self.cee.rules, recipe_id, None, self.crafting["material_grades"][grade])
        tiers = self.crafting["tiers"]
        quality = min(quality_tier(self.cee.rules, score), self.pr["max_quality"], key=tiers.index)
        need = {k: n * batches for k, n in self.per_batch_inputs(recipe_id, grade).items()}
        self._counter += 1
        jid = f"{self.server_id}-job-{self._counter:08d}"
        try:
            self.inv.apply_many([(self.store_of(company_id), need, {}), (job_owner(jid), {}, need)])
        except WorldError:
            self._counter -= 1
            raise
        self.jobs[jid] = {"id": jid, "company": company_id, "worker": worker, "recipe": recipe_id, "grade": grade,
                          "quality": quality, "batches": batches, "done": 0, "progress": 0, "stalled": 0,
                          "tier": recipe["tier"], "start_day": self.day()}
        self.reg.log(c, self.day(), "production_started", job=jid, recipe=recipe_id, batches=batches)
        return jid

    def cancel(self, actor: str, company_id: str, job_id: str) -> dict[str, int]:
        self.day()
        c = self.cs._need_manage(company_id, actor)
        j = self.jobs.get(job_id) if isinstance(job_id, str) else None
        if j is None or j["company"] != company_id:
            raise WorldError("Auftrag unbekannt")
        per = self.per_batch_inputs(j["recipe"], j["grade"])
        left = j["batches"] - j["done"]
        refund_batches = left - (1 if j["progress"] > 0 else 0)  # die angefangene Charge ist verloren
        refund = {k: n * refund_batches for k, n in per.items() if n * refund_batches}
        burn = {k: n * left - refund.get(k, 0) for k, n in per.items() if n * left - refund.get(k, 0)}
        owner = job_owner(job_id)
        ops: list[tuple[str, dict[str, int], dict[str, int]]] = [(owner, {k: n * left for k, n in per.items()}, {})]
        space = max(0, self.capacity(c) - self.used_capacity(company_id))
        to_store: dict[str, int] = {}
        to_actor: dict[str, int] = {}
        for k in sorted(refund):  # was im Lager keinen Platz hat, geht an den auftraggebenden Verwalter
            fit = min(refund[k], space)
            space -= fit
            if fit:
                to_store[k] = fit
            if refund[k] - fit:
                to_actor[k] = refund[k] - fit
        if to_store:
            ops.append((self.store_of(company_id), {}, to_store))
        if to_actor:
            ops.append((actor, {}, to_actor))
        self.inv.apply_many(ops)
        del self.jobs[job_id]
        self.reg.log(c, self.day(), "production_cancelled", job=job_id, refunded=dict(sorted(refund.items())), lost=dict(sorted(burn.items())))
        return refund

    # -- Verkauf ----------------------------------------------------------------------------
    def npc_price(self, item_key: str, qty: int) -> int:
        name, grade = self._item(item_key)
        ref = self.trading.reference(name, grade, qty) if self.trading is not None else reference_value(self.cee.rules, name, grade, qty)
        return ref * self.pr["npc_buyer"]["permille"] // 1000

    def sell_to_npc(self, actor: str, company_id: str, item_key: str, qty: int) -> int:
        today = self.day()
        self.cs._need_manage(company_id, actor)
        self._item(item_key)
        self._qty(qty)
        if self.inv.balance(self.store_of(company_id), item_key) < qty:
            raise WorldError("Nicht genug Ware im Lager")
        proceeds = self.npc_price(item_key, qty)
        if proceeds < 1:
            raise WorldError("Erlös wäre 0")
        rec = self.npc_sold.get(company_id)
        sold = rec["coins"] if rec and rec["day"] == today else 0
        if sold + proceeds > self.pr["npc_buyer"]["daily_cap"]:
            raise WorldError("Tageslimit des Abnehmers überschritten")
        self.inv.apply(self.store_of(company_id), {item_key: qty}, {})
        self.cs.record_revenue(company_id, proceeds)
        self.npc_sold[company_id] = {"day": today, "coins": sold + proceeds}
        return proceeds

    # -- Tagesabschluss (Haken in CompanyService) ---------------------------------------------
    def _tick(self, c: dict[str, Any], d: int, paid: dict[str, bool]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for jid in self.jobs_of(c["id"]):
            j = self.jobs[jid]
            if not paid.get(j["worker"], False):  # entlassen, gekündigt oder unbezahlt
                j["stalled"] += 1
                continue
            days_needed = self.pr["days_per_batch_by_tier"][str(j["tier"])]
            if j["progress"] < days_needed:
                j["progress"] += 1
            if j["progress"] < days_needed:
                continue
            outq = self.batch_output(j["recipe"])
            upkeep = self.pr["upkeep_per_batch_by_tier"][str(j["tier"])]
            store = self.store_of(c["id"])
            if self.used_capacity(c["id"]) + outq > self.capacity(c) or self.inv.balance(store, self.coin) < upkeep:
                j["stalled"] += 1  # Charge fertig, wartet auf Lagerplatz bzw. Betriebskosten
                continue
            per = self.per_batch_inputs(j["recipe"], j["grade"])
            produced = {key(self.crafting["recipes"][j["recipe"]]["output"]["item"], j["quality"]): outq}
            self.inv.apply_many([(job_owner(jid), per, {}), (store, {self.coin: upkeep}, produced), (SINK, {}, {self.coin: upkeep})])
            j["done"] += 1
            j["progress"] = 0
            if j["done"] == j["batches"]:
                del self.jobs[jid]
                self.reg.log(c, d, "production_done", job=jid, recipe=j["recipe"], batches=j["batches"])
                out.append({"day": d, "company": c["id"], "kind": "production_done", "job": jid})
        return out

    def _on_close(self, c: dict[str, Any]) -> None:
        """Schließung: Ware und Auftragskonten gehen an den Gründer (Platzhalter-Regel), Aufträge enden."""
        for jid in self.jobs_of(c["id"]):
            held = self.inv.holdings(job_owner(jid))
            if held:
                self.inv.apply_many([(job_owner(jid), held, {}), (c["founder"], {}, held)])
            del self.jobs[jid]
        goods = self.stock(c["id"])
        if goods:
            self.inv.apply_many([(self.store_of(c["id"]), goods, {}), (c["founder"], {}, goods)])

    # -- Invarianten und Persistenz ------------------------------------------------------------
    def check(self) -> list[str]:
        errs: list[str] = []
        owners = {o for o in self.inv._stacks if o.startswith("production:")}
        for jid, j in sorted(self.jobs.items()):
            c = self.reg.companies.get(j["company"])
            if c is None or not c["open"]:
                errs.append(f"{jid}: Firma fehlt oder ist geschlossen")
            if not 0 <= j["done"] < j["batches"] or j["progress"] < 0:
                errs.append(f"{jid}: Fortschritt ungültig")
            left = j["batches"] - j["done"]
            want = {k: n * left for k, n in self.per_batch_inputs(j["recipe"], j["grade"]).items()}
            if self.inv.holdings(job_owner(jid)) != dict(sorted(want.items())):
                errs.append(f"{jid}: Auftragskonto deckt die Restchargen nicht exakt")
            owners.discard(job_owner(jid))
        errs += [f"{o}: Auftragskonto ohne Auftrag" for o in sorted(owners)]
        return errs

    def to_json(self) -> str:
        return json.dumps({"counter": self._counter, "jobs": self.jobs, "npc_sold": self.npc_sold}, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        data = json.loads(text)
        self._counter, self.jobs, self.npc_sold = data["counter"], data["jobs"], data["npc_sold"]
        problems = self.check()
        if problems:
            raise WorldError("; ".join(problems))
