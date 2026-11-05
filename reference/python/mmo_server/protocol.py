"""Befehlskatalog des Spielserver-Protokolls (Planung und Referenz). Siehe ADR-0019 und docs/PROTOCOL.md.

Ein Befehl ist eine **Absicht** des Spielers; er enthält nie Fortschritt, Ergebnisse, Zeit oder Preisreferenzen. Der Katalog
legt je Befehl fest: Name, Argumente samt Typ, welches Argument die handelnde Figur ist (muss der Sitzung gehören) und den
Aufruf in der Welt. Alles, was nicht im Katalog steht, ist für Clients nicht erreichbar (`INTERNAL_ONLY` nennt die bewusst
nur serverinternen Operationen). Typkürzel: s = String, i = Ganzzahl (kein bool), b = bool, l = Liste von Strings (höchstens 16), `?` = optional.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable

from mmo_world.world import World
from mmo_world.errors import WorldError


@dataclass(frozen=True)
class Command:
    name: str
    args: dict[str, str]
    actor: str | None  # Argument, das die handelnde Figur der Sitzung enthält (None: reine öffentliche Abfrage)
    call: Callable[[World, dict[str, Any]], Any]
    mutating: bool = True
    rate_group: str = "default"


def _res(x: Any) -> Any:
    """Antwortdaten: nur JSON-Grundtypen; Ereignisse werden auf ihren Hash reduziert."""
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return {k: _res(v) for k, v in dataclasses.asdict(x).items() if k not in ("seller_event", "buyer_event", "event")}
    if hasattr(x, "hash") and hasattr(x, "payload"):
        return x.hash
    if isinstance(x, dict):
        return {k: _res(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_res(v) for v in x]
    return x


def _element_catalog(w: Any) -> dict[str, Any]:
    from mmo_cee.combos import catalog
    return catalog(w.svc.rules)


def _character_view(w: Any, char: str) -> dict[str, Any]:
    """Lesende Gesamtsicht auf die Charakterentwicklung (Identität, Elemente, Berufe, Wesen, Kampf, Wissen). Reine Ableitung aus dem Zustand."""
    svc = w.svc
    st = svc.state(char)
    p = st.parts

    def safe(f: Callable[[], Any], default: Any) -> Any:
        try:
            return f()
        except Exception:                      # ältere Regelversionen kennen manche Teile nicht
            return default
    ident = dict(p["identity"])
    return {
        "identity": ident,
        "rules_version": st.rules_version,
        "classes": list(svc.rules_of(char)["identity"]["classes"]),
        "elements": {"affinity": dict(p["element"]["affinity"]), "attuned": list(p["element"]["attuned"])},
        "professions": dict(p["profession"]["xp"]),
        "essence": {"form": p["essence"]["form"], "trials_passed": list(p["essence"]["trials_passed"]),
                    "profile": safe(lambda: svc.essence_profile(char), {}), "eligible": safe(lambda: svc.eligible_essences(char), []),
                    "scores": safe(lambda: svc.essence_scores(char), {})},
        "combat": {"directions": safe(lambda: svc.combat_directions(char), {}), "abilities": safe(lambda: svc.abilities(char), {}),
                   "loadout_slots": safe(lambda: svc.loadout_slots(char), 0), "equipped": safe(lambda: svc.equipped_abilities(char), None)},
        "knowledge": {"discoveries": safe(lambda: svc.known_discoveries(char), []), "recipes": safe(lambda: svc.known_recipes(char), []),
                      "techniques": safe(lambda: svc.known_techniques(char), []), "craft_profile": safe(lambda: svc.craft_profile(char), {})},
        "economy": safe(lambda: svc.economic_profile(char), {}),
        "appearance": safe(lambda: svc.appearance(char), {}),
        "layers": safe(lambda: svc.layers(char), {}),
        "essence_preview": safe(lambda: svc.essence_preview(char), {}),
        "ability_defs": safe(lambda: __import__("mmo_cee.forms", fromlist=["x"]).ability_definitions(svc.state(char), svc.rules_of(char), svc.abilities(char)), {}),
        "combinations": safe(lambda: svc.element_combinations(char), []),
        "profession_detail": safe(lambda: svc.profession_branches(char), {}),
        "specialization": safe(lambda: {k: v for k, v in svc.rules_of(char)["professions"]["specialization"].items() if not k.startswith("_")}, None),
        "discoveries": safe(lambda: {d: pr for d in svc.rules_of(char)["discovery"]["discoveries"]
                                     for pr in [svc.discovery_progress(char, d)] if pr["known"] or pr["evidence"]}, {}),
    }


def _company_view(w: World, cid: str, char: str) -> dict[str, Any]:
    from mmo_world.company import company_level, building
    c = w.company_registry.companies[cid]
    cr = w.company.cr
    jobs = [w.production.jobs[j] for j in w.production.jobs_of(cid)] if w.production.active or w.production.jobs else []
    return {"id": cid, "open": c["open"], "founder": c["founder"], "ceo": c["ceo"], "can_manage": c["open"] and w.company.can_manage(cid, char),
            "balance": w.company.balance(cid), "building_level": c["building_level"], "max_building_level": len(cr["building_levels"]),
            "level": company_level(cr, c["revenue_total"]), "reputation": c["reputation"],
            "max_employees": building(cr, c["building_level"])["max_employees"],
            "employees": [{"char": e, "wage": v["wage"], "satisfaction": v["satisfaction"], "loyalty": v["loyalty"], "status": v["status"]}
                          for e, v in sorted(c["employees"].items())],
            "shares": dict(sorted(c["shares"].items())),
            "stock": w.production.stock(cid), "capacity": w.production.capacity(c), "used": w.production.used_capacity(cid),
            "lines": w.production.lines(c), "jobs": [{k: j[k] for k in ("id", "worker", "recipe", "batches", "done", "progress", "stalled")} for j in jobs],
            "branches": w.branches.view(cid), "log": c["log"][-8:]}


def _my_companies(w: World, char: str) -> dict[str, Any]:
    mine = [cid for cid, c in sorted(w.company_registry.companies.items())
            if c["open"] and (char in c["employees"] or c["founder"] == char or c["ceo"] == char or c["shares"].get(char, 0) > 0)]
    return {"companies": [_company_view(w, cid, char) for cid in mine], "capital_min": w.company.cr["founding"]["capital_min"],
            "coins": w.inv.balance(char, w.trading.coin), "recipes": sorted(w.svc.rules["crafting"]["recipes"])}


def _market(w: World, char: str) -> dict[str, Any]:
    items = w.svc.rules["economy"]["items"]
    maker = w.pricing.pr["maker"]["items"] if w.pricing is not None else []
    return {"items": {k: v["class"] for k, v in items.items()}, "grades": sorted(w.svc.rules["economy"]["grade_permille"]),
            "maker_items": maker, "coin": w.trading.coin,
            "orders": [dict(w.exchange.orders[o]) for o in w.exchange.open_orders(char)], "band_permille": w.exchange.mr["band_permille"]}


def _market_quote(w: World, item_key: str) -> dict[str, Any]:
    item, grade = w.trading.parse(item_key)
    out = {**w.exchange.quote(item_key), "reference": w.trading.reference(item, grade, 1)}
    if w.pricing is not None and item in w.pricing.pr["maker"]["items"]:
        out["maker_buys_at"], out["maker_sells_at"] = w.pricing.quote(item_key, 1, "sell"), w.pricing.quote(item_key, 1, "buy")
        out["factor_permille"] = w.pricing.factor(item_key)
    return out


def _adopt(w: World, a: dict[str, Any]) -> Any:
    """Dauerhafte Annahme nur mit ausdrücklicher Bestätigung: `ack` muss `adopt:<form>` lauten (ADR-0045)."""
    if a["ack"] != "adopt:" + a["form"]:
        raise WorldError("Annahme braucht ausdrückliche Bestätigung (ack = adopt:<Form>)")
    return _res(w.svc.record(a["char"], "essence.adopted", {"form": a["form"]}))


def _c(name: str, args: str, actor: str | None, call: Callable[[World, dict[str, Any]], Any], mutating: bool = True,
       group: str | None = None) -> Command:
    schema = {k: v for k, v in (a.split(":") for a in args.split())} if args else {}
    if group is None:
        group = "query" if not mutating else name if name in ("market.place", "craft") else "default"
    return Command(name, schema, actor, call, mutating, group)


COMMANDS: dict[str, Command] = {c.name: c for c in [
    # Herstellung und Wissen
    _c("craft", "char:s recipe:s qty:i grade:s technique:s? element:s?", "char",
       lambda w, a: _res(w.crafting.craft(a["char"], a["recipe"], a["qty"], a["grade"], a.get("technique"), a.get("element")))),
    _c("discovery.complete", "char:s discovery:s", "char", lambda w, a: _res(w.discovery.complete(a["char"], a["discovery"]).payload)),
    _c("discovery.teach", "teacher:s learner:s discovery:s", "teacher", lambda w, a: _res(w.discovery.teach(a["teacher"], a["learner"], a["discovery"]))),
    # Markt (Handel zwischen Spielern läuft über das Orderbuch; direkter Handel braucht später Angebote mit Zustimmung)
    _c("market.place", "char:s side:s item_key:s qty:i price:i ioc:b?", "char",
       lambda w, a: _res(w.exchange.place(a["char"], a["side"], a["item_key"], a["qty"], a["price"], a.get("ioc", False)))),
    _c("market.cancel", "char:s order:s", "char", lambda w, a: _res(w.exchange.cancel(a["char"], a["order"]))),
    _c("maker.sell", "char:s item_key:s qty:i", "char", lambda w, a: _res(_pricing(w).sell_to_maker(a["char"], a["item_key"], a["qty"]))),
    _c("maker.buy", "char:s item_key:s qty:i", "char", lambda w, a: _res(_pricing(w).buy_from_maker(a["char"], a["item_key"], a["qty"]))),
    # Direkter Handel mit Zustimmung beider Seiten (Angebot -> Annahme)
    _c("trade.offer", "char:s to:s side:s item_key:s qty:i price:i", "char",
       lambda w, a: w.offers.make(a["char"], a["to"], a["side"], a["item_key"], a["qty"], a["price"])),
    _c("trade.accept", "char:s offer:s", "char", lambda w, a: _settle(w.offers.accept(a["char"], a["offer"]))),
    _c("trade.decline", "char:s offer:s", "char", lambda w, a: w.offers.decline(a["char"], a["offer"])),
    _c("trade.cancel", "char:s offer:s", "char", lambda w, a: w.offers.cancel(a["char"], a["offer"])),
    # Gruppen: bilden, einladen, Anführer, Beutemodus (die Beute selbst verteilt der Server nach dem Kampf)
    _c("party.form", "char:s", "char", lambda w, a: w.parties.create(a["char"])),
    _c("party.invite", "char:s target:s", "char", lambda w, a: w.parties.invite(a["char"], a["target"])),
    _c("party.accept", "char:s invite:s", "char", lambda w, a: w.parties.accept(a["char"], a["invite"])),
    _c("party.decline", "char:s invite:s", "char", lambda w, a: w.parties.decline(a["char"], a["invite"])),
    _c("party.leave", "char:s", "char", lambda w, a: w.parties.leave(a["char"])),
    _c("party.kick", "char:s member:s", "char", lambda w, a: w.parties.kick(a["char"], a["member"])),
    _c("party.promote", "char:s member:s", "char", lambda w, a: w.parties.promote(a["char"], a["member"])),
    _c("party.set_loot", "char:s mode:s", "char", lambda w, a: w.parties.set_loot(a["char"], a["mode"])),
    _c("party.disband", "char:s", "char", lambda w, a: w.parties.disband(a["char"])),
    # Benachrichtigungen: Postfach abrufen, quittieren, Arten stummschalten (Push läuft über den Transport; Abruf holt Verpasstes)
    _c("notify.ack", "char:s upto:i", "char", lambda w, a: w.outbox.ack(a["char"], a["upto"])),
    _c("notify.mute", "char:s kinds:l", "char", lambda w, a: w.outbox.mute(a["char"], a["kinds"])),
    _c("notify.unmute", "char:s kinds:l", "char", lambda w, a: w.outbox.unmute(a["char"], a["kinds"])),
    # Kampfentwicklung: Fähigkeiten ausrüsten (Tag setzt der Server)
    _c("combat.set_loadout", "char:s abilities:l", "char",
       lambda w, a: w.svc.record(a["char"], "combat.loadout_set", {"abilities": a["abilities"], "day": w.day[0]}).hash),
    # Firmen
    _c("company.found", "char:s capital:i", "char", lambda w, a: w.company.found(a["char"], a["capital"])),
    _c("company.close", "actor:s company:s", "actor", lambda w, a: _res(w.company.close_company(a["actor"], a["company"]))),
    _c("company.hire", "actor:s company:s char:s wage:i share:i?", "actor",
       lambda w, a: w.company.hire(a["actor"], a["company"], a["char"], a["wage"], a.get("share", 0))),
    _c("company.fire", "actor:s company:s char:s", "actor", lambda w, a: w.company.fire(a["actor"], a["company"], a["char"])),
    _c("company.resign", "char:s company:s", "char", lambda w, a: w.company.resign(a["char"], a["company"])),
    _c("company.set_contract", "actor:s company:s char:s wage:i? share:i?", "actor",
       lambda w, a: w.company.set_contract(a["actor"], a["company"], a["char"], a.get("wage"), a.get("share"))),
    _c("company.promote", "actor:s company:s char:s", "actor", lambda w, a: w.company.promote(a["actor"], a["company"], a["char"])),
    _c("company.demote", "actor:s company:s char:s", "actor", lambda w, a: w.company.demote(a["actor"], a["company"], a["char"])),
    _c("company.upgrade", "actor:s company:s", "actor", lambda w, a: w.company.upgrade_building(a["actor"], a["company"])),
    _c("company.poach", "actor:s company:s char:s wage:i", "actor", lambda w, a: _res(w.company.poach(a["actor"], a["company"], a["char"], a["wage"]))),
    _c("company.offer_shares", "char:s company:s qty:i price:i", "char", lambda w, a: w.company.offer_shares(a["char"], a["company"], a["qty"], a["price"])),
    _c("company.preempt", "char:s company:s offer:s qty:i", "char", lambda w, a: w.company.preempt(a["char"], a["company"], a["offer"], a["qty"])),
    _c("company.purchase", "char:s company:s offer:s qty:i ack:s", "char",
       lambda w, a: w.company.purchase(a["char"], a["company"], a["offer"], a["qty"], a["ack"])),
    _c("company.withdraw_offer", "char:s company:s offer:s", "char", lambda w, a: w.company.withdraw_offer(a["char"], a["company"], a["offer"])),
    _c("company.grant_equity", "actor:s company:s char:s qty:i", "actor", lambda w, a: w.company.grant_equity(a["actor"], a["company"], a["char"], a["qty"])),
    _c("company.propose", "char:s company:s kind:s candidate:s?", "char", lambda w, a: w.company.propose(a["char"], a["company"], a["kind"], a.get("candidate"))),
    _c("company.vote", "char:s company:s proposal:s yes:b", "char", lambda w, a: w.company.vote(a["char"], a["company"], a["proposal"], a["yes"])),
    # Firmenproduktion
    _c("production.stock_in", "actor:s company:s item_key:s qty:i", "actor", lambda w, a: w.production.stock_in(a["actor"], a["company"], a["item_key"], a["qty"])),
    _c("production.stock_out", "actor:s company:s item_key:s qty:i", "actor", lambda w, a: w.production.stock_out(a["actor"], a["company"], a["item_key"], a["qty"])),
    _c("production.start", "actor:s company:s worker:s recipe:s batches:i grade:s", "actor",
       lambda w, a: w.production.start(a["actor"], a["company"], a["worker"], a["recipe"], a["batches"], a["grade"])),
    _c("production.cancel", "actor:s company:s job:s", "actor", lambda w, a: _res(w.production.cancel(a["actor"], a["company"], a["job"]))),
    _c("production.sell", "actor:s company:s item_key:s qty:i", "actor", lambda w, a: w.production.sell_to_npc(a["actor"], a["company"], a["item_key"], a["qty"])),
    # Lesende Abfragen (keine Zustandsänderung, nicht idempotenzpflichtig)
    _c("query.quote", "item_key:s", None, lambda w, a: w.exchange.quote(a["item_key"]), mutating=False),
    _c("query.disclosure", "company:s", None, lambda w, a: _res(w.company.disclosure(a["company"])), mutating=False),
    _c("query.inventory", "char:s", "char", lambda w, a: w.inv.holdings(a["char"]), mutating=False),
    _c("query.economic_profile", "char:s", "char", lambda w, a: w.svc.economic_profile(a["char"]), mutating=False),
    _c("query.offers", "char:s", "char", lambda w, a: {"outgoing": [w.offers.offers[k] for k in w.offers.open_offers(a["char"])["outgoing"]],
                                                       "incoming": [w.offers.offers[k] for k in w.offers.open_offers(a["char"])["incoming"]]},
       mutating=False),
    _c("notify.fetch", "char:s after:i? limit:i?", "char", lambda w, a: w.outbox.fetch(a["char"], a.get("after", 0), a.get("limit", 50)),
       mutating=False),
    _c("query.party", "char:s", "char", lambda w, a: w.parties.view(a["char"]), mutating=False),
    _c("query.party_invites", "char:s", "char", lambda w, a: w.parties.incoming(a["char"]), mutating=False),
    _c("query.abilities", "char:s", None, lambda w, a: w.svc.abilities(a["char"]), mutating=False),
    _c("query.character", "char:s", "char", lambda w, a: _character_view(w, a["char"]), mutating=False),
    _c("character.choose_class", "char:s base_class:s", "char", lambda w, a: _res(w.svc.record(a["char"], "identity.class_chosen", {"base_class": a["base_class"]}))),
    _c("essence.decide", "char:s decision:s choice:s", "char",
       lambda w, a: _res(w.svc.record(a["char"], "essence.decision_made", {"decision_id": a["decision"], "choice": a["choice"]}))),
    _c("essence.trial", "char:s form:s", "char", lambda w, a: _res(w.svc.record(a["char"], "essence.trial_passed", {"form": a["form"]}))),
    _c("essence.adopt", "char:s form:s ack:s", "char", lambda w, a: _adopt(w, a)),
    _c("echo.activate", "char:s echo:s", "char", lambda w, a: w.echo.activate(a["char"], a["echo"])),
    _c("echo.release", "char:s echo:s", "char", lambda w, a: w.echo.release(a["char"], a["echo"])),
    _c("echo.equip", "char:s echo:s role:s", "char", lambda w, a: w.echo.equip(a["char"], a["echo"], a["role"])),
    _c("echo.unequip", "char:s echo:s", "char", lambda w, a: w.echo.unequip(a["char"], a["echo"])),
    _c("echo.upgrade", "char:s echo:s protect:b? request_id:s?", "char",
       lambda w, a: w.echo.upgrade(a["char"], a["echo"], a.get("protect", False), a.get("request_id"))),
    _c("echo.list", "char:s echo:s price:i", "char", lambda w, a: {"listing": w.echo.list_for_sale(a["char"], a["echo"], a["price"])}),
    _c("echo.cancel", "char:s listing:s", "char", lambda w, a: w.echo.cancel_listing(a["char"], a["listing"])),
    _c("echo.buy", "char:s listing:s", "char", lambda w, a: w.echo.buy(a["char"], a["listing"])),
    _c("query.settlements", "char:s", "char", lambda w, a: w.settlements.view(a["char"]), mutating=False),
    _c("settlement.found", "char:s site:s name:s", "char", lambda w, a: w.settlements.found(a["char"], a["site"], a["name"])),
    _c("plot.buy", "char:s site:s n:i", "char", lambda w, a: w.settlements.buy_plot(a["char"], a["site"], a["n"])),
    _c("plot.abandon", "char:s site:s n:i", "char", lambda w, a: w.settlements.abandon(a["char"], a["site"], a["n"])),
    _c("plot.build", "char:s site:s n:i building:s", "char", lambda w, a: {"level": w.settlements.build(a["char"], a["site"], a["n"], a["building"])}),
    _c("plot.stash_in", "char:s site:s n:i item_key:s qty:i", "char", lambda w, a: w.settlements.stash_in(a["char"], a["site"], a["n"], a["item_key"], a["qty"])),
    _c("plot.stash_out", "char:s site:s n:i item_key:s qty:i", "char", lambda w, a: w.settlements.stash_out(a["char"], a["site"], a["n"], a["item_key"], a["qty"])),
    _c("project.contribute", "char:s site:s project:s coins:i? item_key:s? qty:i?", "char",
       lambda w, a: w.settlements.contribute(a["char"], a["site"], a["project"], a.get("coins", 0),
                                              {a["item_key"]: a["qty"]} if a.get("item_key") else None)),
    _c("query.research", "char:s", "char", lambda w, a: w.research.view(a["char"]), mutating=False),
    _c("research.start", "char:s site:s tech:s", "char", lambda w, a: w.research.start(a["char"], a["site"], a["tech"])),
    _c("research.license", "char:s site:s tech:s", "char", lambda w, a: w.research.license(a["char"], a["site"], a["tech"])),
    _c("research.contribute", "char:s site:s tech:s coins:i? item_key:s? qty:i?", "char",
       lambda w, a: w.research.contribute(a["char"], a["site"], a["tech"], a.get("coins", 0), {a["item_key"]: a["qty"]} if a.get("item_key") else None)),
    _c("query.guild", "char:s", "char", lambda w, a: w.guilds.view(a["char"]), mutating=False),
    _c("guild.found", "char:s name:s tag:s", "char", lambda w, a: {"guild": w.guilds.found(a["char"], a["name"], a["tag"])}),
    _c("guild.invite", "char:s target:s", "char", lambda w, a: w.guilds.invite(a["char"], a["target"])),
    _c("guild.accept", "char:s guild:s", "char", lambda w, a: w.guilds.accept(a["char"], a["guild"])),
    _c("guild.decline", "char:s guild:s", "char", lambda w, a: w.guilds.decline(a["char"], a["guild"])),
    _c("guild.leave", "char:s", "char", lambda w, a: w.guilds.leave(a["char"])),
    _c("guild.kick", "char:s target:s", "char", lambda w, a: w.guilds.kick(a["char"], a["target"])),
    _c("guild.role", "char:s target:s role:s", "char", lambda w, a: w.guilds.set_role(a["char"], a["target"], a["role"])),
    _c("guild.disband", "char:s", "char", lambda w, a: w.guilds.disband(a["char"])),
    _c("guild.research", "char:s tech:s", "char", lambda w, a: w.guilds.research_start(a["char"], a["tech"])),
    _c("guild.stash", "char:s item_key:s qty:i", "char", lambda w, a: w.guilds.deposit(a["char"], a["item_key"], a["qty"])),
    _c("guild.take", "char:s item_key:s qty:i", "char", lambda w, a: w.guilds.withdraw(a["char"], a["item_key"], a["qty"])),
    _c("guild.contribute", "char:s coins:i? item_key:s? qty:i?", "char",
       lambda w, a: w.guilds.contribute(a["char"], a.get("coins", 0), {a["item_key"]: a["qty"]} if a.get("item_key") else None)),
    _c("query.chronicle", "offset:i? limit:i? kind:s?", None, lambda w, a: w.chronicle.page(a.get("offset", 0), a.get("limit", 20), a.get("kind")), mutating=False),
    _c("query.prestige", "char:s", "char", lambda w, a: dict(w.chronicle.prestige(a["char"]),
       research_titles=w.research.titles.get(a["char"], [])), mutating=False),
    _c("query.echoes", "char:s", "char", lambda w, a: w.echo.view(a["char"]), mutating=False),
    _c("profession.specialize", "char:s profession:s branch:s", "char", lambda w, a: w.specialize(a["char"], a["profession"], a["branch"])),
    _c("equip.wear", "char:s item_key:s", "char", lambda w, a: w.equipment.equip(a["char"], a["item_key"])),
    _c("equip.remove", "char:s slot:s", "char", lambda w, a: w.equipment.unequip(a["char"], a["slot"])),
    _c("equip.look", "char:s slot:s item:s?", "char", lambda w, a: w.equipment.set_look(a["char"], a["slot"], a.get("item"))),
    _c("query.equipment", "char:s", "char", lambda w, a: w.equipment.view(a["char"]), mutating=False),
    _c("query.my_companies", "char:s", "char", lambda w, a: _my_companies(w, a["char"]), mutating=False),
    _c("query.market", "char:s", "char", lambda w, a: _market(w, a["char"]), mutating=False),
    _c("query.market_quote", "item_key:s", None, lambda w, a: _market_quote(w, a["item_key"]), mutating=False),
    _c("company.branch_open", "actor:s company:s region:s", "actor", lambda w, a: {"branch": w.branches.open_branch(a["actor"], a["company"], a["region"])}),
    _c("company.branch_close", "actor:s company:s branch:s", "actor", lambda w, a: w.branches.close_branch(a["actor"], a["company"], a["branch"])),
    _c("company.branch_reopen", "actor:s company:s branch:s", "actor", lambda w, a: w.branches.reopen_branch(a["actor"], a["company"], a["branch"])),
    _c("query.element_catalog", "", None, lambda w, a: _element_catalog(w), mutating=False),
    _c("query.appearance", "char:s", None, lambda w, a: w.svc.appearance(a["char"]), mutating=False),
]}

# Bewusst NICHT für Clients erreichbar: alles, was Fortschritt, Zeit, Geld oder Weltzustand setzt (Vertrauensgrenze).
INTERNAL_ONLY: dict[str, str] = {
    "cee_create/cee_record": "Charaktererstellung und Ereignisse kommen vom Server (Berichte, Kampf, Herstellung)",
    "discovery.gather": "Beweise vergibt der Server aus Spielereignissen",
    "trade (direkt, ohne Zustimmung)": "Der Handelsdienst selbst ist intern; Clients handeln nur über Orderbuch oder Angebot/Annahme (`trade.*`)",
    "deposit/revenue": "Münzquellen sind serverintern",
    "party.loot (Beuteverteilung) / party_expire": "Beute verteilt der Server nach dem Kampf an Teilnehmer mit Beitrag; Einladungsfristen räumt der Tagesschritt ab",
    "advance_day/price_advance/market_expire": "Tagesschritte macht der Server nach seiner Uhr",
    "price_shock/rules_upgrade/rules_migrate": "Weltereignisse und Betriebsaktionen",
    "persistence (export/import/commit)": "Betrieb",
}


def _settle(s: Any) -> dict[str, Any]:
    t = s.trade
    return {"trade_id": t.trade_id, "price": t.price, "quantity": t.quantity, "item_key": t.item_key, "fee": s.fee}


def _pricing(w: World) -> Any:
    if w.pricing is None:
        from mmo_world.errors import WorldError
        raise WorldError("Preishändler ist mit diesen Regeln nicht aktiv")
    return w.pricing
