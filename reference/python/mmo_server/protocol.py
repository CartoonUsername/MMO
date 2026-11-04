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
