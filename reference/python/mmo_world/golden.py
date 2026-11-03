"""Golden Test Vectors der Weltseite (Inventar, Entdeckungsregister, Herstellung, Handel, Firmen).

Ein Szenario ist ein Skript aus Operationen (siehe `OPS`) mit der erwarteten Reaktion der Referenzimplementierung
(ok mit Rückgabewert | Fehlerklasse) und dem SHA-256 des gesamten Weltzustands nach jedem Schritt. Der Weltzustand
umfasst Inventar, beide Register, die ID-Zähler der Dienste und je Figur den Zustands-Hash der CEE – die CEE-Logik
wird also mitgeprüft. Fehlermeldungstexte sind nicht Teil des Vertrags (nur die Fehlerklasse).

    python -m mmo_world.golden write ../golden_world
    python -m mmo_world.golden check ../golden_world

Format und Prüfverfahren für Ports: reference/golden/README.md (Abschnitt Weltseite).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from mmo_cee.errors import RuleViolation
from mmo_cee.history import _canonical as canonical_bytes

from . import persistence
from .company import goal_of, load_company_rules
from .errors import WorldError
from .persistence import PersistenceError
from .world import CEE_RULES, COMPANY_RULES, MARKET_RULES, PRICING_RULES, PRODUCTION_RULES, World

CEE_RULES_V8 = "rules_v8.json"

FORMAT_VERSION = 1
Op = dict[str, Any]


def _sha(pkg: str, name: str) -> str:
    return hashlib.sha256(resources.files(pkg).joinpath("data", name).read_bytes()).hexdigest()


def _jsonable(x: Any) -> Any:
    return json.loads(canonical_bytes(x)) if x is not None else None


# ---------------------------------------------------------------- Ausführungsumgebung ----
class Env(World):
    """Ausführungsumgebung der Skripte: eine Welt plus gemerkte Werte (Platzhalter)."""

    def __init__(self, cee_rules: str = CEE_RULES) -> None:
        super().__init__(cee_rules, COMPANY_RULES)
        self.saved: dict[str, Any] = {}

    def resolve(self, value: Any, op: Op) -> Any:
        """Platzhalter: "$disclosure" = aktuelle Offenlegung der Firma des Schritts, "$name" = gemerkter Wert."""
        if value == "$disclosure":
            return self.company.disclosure(op["company"])["hash"]
        if isinstance(value, str) and value.startswith("$") and value[1:] in self.saved:
            return self.saved[value[1:]]
        return value


def _craft(env: Env, a: Op) -> Any:
    r = env.crafting.craft(a["char"], a["recipe"], a["qty"], a["grade"], a.get("technique"), a.get("element"))
    return {"quality": r.quality, "consumed": r.consumed, "produced": r.produced, "profession_xp": r.profession_xp,
            "event_hash": r.event.hash}


def _trade(env: Env, a: Op) -> Any:
    r = env.trading.trade(a["seller"], a["buyer"], a["item_key"], a["qty"], a["price"])
    return {"trade_id": r.trade_id, "item_key": r.item_key, "quantity": r.quantity, "price": r.price,
            "reference": r.reference, "seller_event": r.seller_event.hash, "buyer_event": r.buyer_event.hash}


def _create(env: Env, a: Op) -> Any:
    env.svc.create(a["char"], a.get("kind", "player"))
    return env.svc.log.events(a["char"])[0].hash


def _disclosure(env: Env, a: Op) -> Any:
    d = env.company.disclosure(a["company"])
    if "save_as" in a:
        env.saved[a["save_as"]] = d["hash"]
    return d


def _set_day(env: Env, a: Op) -> None:
    env.day[0] = a["value"]


def _upgrade(env: Env, a: Op) -> Any:
    """Hebt die ganze Welt auf eine höhere Regelversion (Figuren aus `chars`, sonst alle, werden migriert)."""
    new = persistence.upgrade_world(env, a["to"], a.get("chars"))
    saved = env.saved
    env.__dict__.update(new.__dict__)
    env.saved = saved
    return {"rules": new.svc.rules.version, "lagging": [c for c in new.svc.log.character_ids() if new.svc.needs_migration(c)]}


def _migrate(env: Env, a: Op) -> Any:
    ev = env.svc.migrate(a["char"])
    return {"from": ev.payload["from"], "to": ev.payload["to"], "event_hash": ev.hash}


def _pricing(env: Env) -> Any:
    if env.pricing is None:
        raise WorldError("Preisdynamik ist mit diesen CEE-Regeln nicht aktiv")
    return env.pricing


def _maker(env: Env, side: str, a: Op) -> Any:
    p = _pricing(env)
    r = (p.sell_to_maker if side == "sell" else p.buy_from_maker)(a["char"], a["item_key"], a["qty"])
    return {"trade_id": r.trade_id, "price": r.price, "reference": r.reference, "quantity": r.quantity}


def _place(env: Env, a: Op) -> Any:
    r = env.exchange.place(a["char"], a["side"], a["item_key"], a["qty"], a["price"], a.get("ioc", False))
    return {"order_id": r.order_id, "remaining": r.remaining, "fills": [dataclasses.asdict(f) for f in r.fills]}


def _complete(env: Env, a: Op) -> Any:
    ev = env.discovery.complete(a["char"], a["discovery"])
    return {"credit": ev.payload["credit"], "event_hash": ev.hash}


OPS: dict[str, Callable[[Env, Op], Any]] = {
    "cee_create": _create,
    "cee_record": lambda e, a: e.svc.record(a["char"], a["type"], a["payload"]).hash,
    "deposit": lambda e, a: e.inv.deposit(a["owner"], a["key"], a["qty"]),
    "day": _set_day,
    "disc_gather": lambda e, a: e.discovery.gather(a["char"], a["discovery"], a["evidence"]).hash,
    "disc_complete": _complete,
    "disc_teach": lambda e, a: e.discovery.teach(a["teacher"], a["learner"], a["discovery"]).hash,
    "craft": _craft,
    "trade": _trade,
    "found": lambda e, a: e.company.found(a["char"], a["capital"]),
    "hire": lambda e, a: e.company.hire(a["actor"], a["company"], a["char"], a["wage"], a.get("share", 0)),
    "fire": lambda e, a: e.company.fire(a["actor"], a["company"], a["char"]),
    "resign": lambda e, a: e.company.resign(a["char"], a["company"]),
    "set_contract": lambda e, a: e.company.set_contract(a["actor"], a["company"], a["char"], a.get("wage"), a.get("share")),
    "promote": lambda e, a: e.company.promote(a["actor"], a["company"], a["char"]),
    "demote": lambda e, a: e.company.demote(a["actor"], a["company"], a["char"]),
    "upgrade": lambda e, a: e.company.upgrade_building(a["actor"], a["company"]),
    "revenue": lambda e, a: e.company.record_revenue(a["company"], a["amount"]),
    "advance_day": lambda e, a: e.company.advance_day(a["value"]),
    "poach": lambda e, a: e.company.poach(a["actor"], a["company"], a["char"], a["wage"]),
    "offer_shares": lambda e, a: e.company.offer_shares(a["char"], a["company"], a["qty"], a["price"]),
    "preempt": lambda e, a: e.company.preempt(a["char"], a["company"], a["offer"], a["qty"]),
    "purchase": lambda e, a: e.company.purchase(a["char"], a["company"], a["offer"], a["qty"], e.resolve(a["ack"], a)),
    "withdraw_offer": lambda e, a: e.company.withdraw_offer(a["char"], a["company"], a["offer"]),
    "grant_equity": lambda e, a: e.company.grant_equity(a["actor"], a["company"], a["char"], a["qty"]),
    "propose": lambda e, a: e.company.propose(a["char"], a["company"], a["kind"], a.get("candidate")),
    "vote": lambda e, a: e.company.vote(a["char"], a["company"], a["proposal"], a["yes"]),
    "close": lambda e, a: e.company.close_company(a["actor"], a["company"]),
    "disclosure": _disclosure,
    "prod_stock_in": lambda e, a: e.production.stock_in(a["actor"], a["company"], a["item_key"], a["qty"]),
    "prod_stock_out": lambda e, a: e.production.stock_out(a["actor"], a["company"], a["item_key"], a["qty"]),
    "prod_start": lambda e, a: e.production.start(a["actor"], a["company"], a["worker"], a["recipe"], a["batches"], a["grade"]),
    "prod_cancel": lambda e, a: e.production.cancel(a["actor"], a["company"], a["job"]),
    "prod_sell": lambda e, a: e.production.sell_to_npc(a["actor"], a["company"], a["item_key"], a["qty"]),
    "rules_upgrade": lambda e, a: _upgrade(e, a),
    "rules_migrate": lambda e, a: _migrate(e, a),
    "price_advance": lambda e, a: _pricing(e).advance(a["value"]),
    "price_shock": lambda e, a: _pricing(e).set_shock(a["item_key"], a["permille"], a["days"]),
    "maker_sell": lambda e, a: _maker(e, "sell", a),
    "maker_buy": lambda e, a: _maker(e, "buy", a),
    "market_place": _place,
    "market_cancel": lambda e, a: e.exchange.cancel(a["char"], a["order"]),
    "market_expire": lambda e, a: e.exchange.expire(a["value"]),
}


def execute(env: Env, op: Op) -> dict[str, Any]:
    """Führt einen Schritt aus; Rückgabe: {expect: ok|error, result|error: Klasse}."""
    try:
        res = OPS[op["op"]](env, op)
    except (WorldError, RuleViolation, PersistenceError) as e:
        return {"expect": "error", "error": type(e).__name__}
    return {"expect": "ok", "result": _jsonable(res)}


def run_script(script: list[Op], cee_rules: str = CEE_RULES) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    env = Env(cee_rules)
    steps = []
    for op in script:
        out = execute(env, op)
        snap = env.snapshot()
        steps.append({**op, **out, "world_sha256": hashlib.sha256(canonical_bytes(snap)).hexdigest()})
    return steps, env.snapshot()


# ---------------------------------------------------------------- Skript-Hilfen ----------
def C(char: str, kind: str = "player") -> Op:
    return {"op": "cee_create", "char": char, "kind": kind}


def R(char: str, type_: str, payload: dict[str, Any]) -> Op:
    return {"op": "cee_record", "char": char, "type": type_, "payload": payload}


def D(owner: str, key: str, qty: int) -> Op:
    return {"op": "deposit", "owner": owner, "key": key, "qty": qty}


def DAY(n: int) -> Op:
    return {"op": "day", "value": n}


def S(op: str, **kw: Any) -> Op:
    return {"op": op, **kw}


def XP(char: str, amount: int) -> Op:
    return R(char, "identity.xp_gained", {"amount": amount})


def WORK(char: str, profession: str, xp: int) -> Op:
    return R(char, "profession.work", {"profession": profession, "xp": xp})


def attune(char: str, element: str, amount: int = 100) -> list[Op]:
    return [R(char, "element.exposure", {"element": element, "amount": amount}), R(char, "element.attuned", {"element": element})]


def char_with_goal(goal: str, prefix: str = "e") -> str:
    cr = load_company_rules(COMPANY_RULES)
    i = 0
    while goal_of(cr, f"{prefix}{i}") != goal:
        i += 1
    return f"{prefix}{i}"


COIN = "coin@gold"


def person(char: str, **professions: int) -> list[Op]:
    """Neue Figur mit genug Erfahrung (Stufe) und optionalen Berufs-XP."""
    return [C(char), XP(char, 10000), *[WORK(char, p, x) for p, x in professions.items()]]


def co(n: int) -> str:
    return f"srv1-co-{n:08d}"


def G(char: str, discovery: str, evidence: str) -> Op:
    return S("disc_gather", char=char, discovery=discovery, evidence=evidence)


BLADE = "iron_blade@masterwork"  # Referenzwert je Stück: 120 * 2,5 = 300


def big_trade(seller: str, buyer: str, qty: int) -> Op:
    return S("trade", seller=seller, buyer=buyer, item_key=BLADE, qty=qty, price=qty * 300)


# ---------------------------------------------------------------- Szenarien --------------
def scenario_trade_inventory() -> list[Op]:
    t = lambda **kw: S("trade", seller=kw.pop("s", "a"), buyer=kw.pop("b", "b"), item_key=kw.pop("k", "iron_blade@fine"),  # noqa: E731
                      qty=kw.pop("q", 1), price=kw.pop("p", 100))
    return [
        *person("a"), *person("b"),
        D("a", "iron_blade@fine", 3), D("b", COIN, 1000),
        t(q=2, p=300),                      # ok (Referenz 360, Abweichung im Rahmen)
        t(q=2, p=300),                      # nur noch 1 Stück im Bestand
        t(s="a", b="a", q=1, p=10),         # Selbsthandel
        t(q=1, p=0),                        # Preis 0
        t(q=1, p=5000),                     # Käufer hat nicht genug Münzen / Preis weit über Referenz
        t(k="iron_blade", q=1, p=5),        # Schlüssel ohne Güteklasse
        t(b="ghost", q=1, p=100),           # unbekannter Käufer
        t(q=1, p=100),                      # ok, letztes Stück
        t(q=1, p=100),                      # Bestand leer
        D("a", "iron_blade@fine", 0),       # Einzahlung 0
        D("a", "kein-schluessel", 5),       # ungültiger Schlüssel
        t(s="b", b="a", k=COIN, q=100, p=100),  # Münzen als Handelsgut
    ]


def scenario_crafting() -> list[Op]:
    cr = lambda c, r, q, g, **kw: S("craft", char=c, recipe=r, qty=q, grade=g, **kw)  # noqa: E731
    return [
        *person("smith", smithing=700), *person("novice"),
        D("smith", "iron_ore@standard", 100), D("smith", "iron_ore@select", 10), D("smith", "charcoal@standard", 5),
        D("smith", "iron_ingot@standard", 4), D("novice", "iron_ore@standard", 4),
        cr("smith", "iron_ingot", 10, "standard"),
        cr("smith", "iron_ingot", 5, "select"),
        cr("smith", "iron_ingot", 21, "standard"),    # über max_batch
        cr("smith", "iron_ingot", 1, "legendary"),    # unbekannte Güteklasse
        cr("smith", "ghost", 1, "standard"),          # unbekanntes Rezept
        cr("novice", "iron_blade", 1, "standard"),    # Meisterschaft fehlt
        cr("novice", "iron_ingot", 3, "standard"),    # 6 Erz nötig, nur 4
        cr("novice", "iron_ingot", 2, "standard"),
        cr("smith", "frostglass", 1, "standard"),     # Entdeckung fehlt
        cr("smith", "iron_blade", 2, "standard"),     # Barren/Holzkohle: 4 Barren@standard + 2 Holzkohle
        cr("smith", "iron_blade", 1, "standard"),     # Barren aufgebraucht
        cr("smith", "iron_ingot", 10, "standard"),
        cr("smith", "iron_ingot", 10, "standard"),    # Wiederholungsabnahme je Rezept und Tag
        DAY(2),
        cr("smith", "iron_ingot", 10, "standard"),
        cr("ghost", "iron_ingot", 1, "standard"),     # unbekannte Figur
    ]


def scenario_discovery() -> list[Op]:
    return [
        *person("a", smithing=700), *person("b", smithing=700), *person("c", smithing=100),
        G("a", "iron_folding", "ore_sample_a"), G("a", "iron_folding", "ore_sample_a"),  # Wiederholung zählt nicht
        G("a", "iron_folding", "bogus"),                                                  # unbekannter Beweis
        G("a", "iron_folding", "ore_sample_b"),
        S("disc_complete", char="a", discovery="iron_folding"),                           # noch unvollständig
        G("a", "iron_folding", "forge_trial"),
        S("disc_complete", char="a", discovery="iron_folding"),                           # Pionier
        S("disc_complete", char="a", discovery="iron_folding"),                           # nur einmal
        DAY(3),
        S("disc_teach", teacher="a", learner="b", discovery="iron_folding"),              # Pionier lehrt im Fenster
        S("disc_teach", teacher="a", learner="c", discovery="iron_folding"),              # Voraussetzung fehlt
        S("disc_teach", teacher="b", learner="c", discovery="iron_folding"),              # Gelehrter darf im Fenster nicht lehren
        WORK("c", "smithing", 600),
        DAY(11),
        S("disc_teach", teacher="b", learner="c", discovery="iron_folding"),              # Fenster vorbei
        S("disc_teach", teacher="c", learner="b", discovery="iron_folding"),              # b kennt es schon
        S("disc_teach", teacher="a", learner="ghost", discovery="iron_folding"),
        G("b", "old_shrine_map", "shrine_mural"), G("b", "old_shrine_map", "hermit_story"),
        S("disc_complete", char="b", discovery="old_shrine_map"),
        *attune("b", "light"), *attune("b", "shadow"), XP("b", 200000),
        G("b", "twilight_rite", "dusk_altar"), G("b", "twilight_rite", "dawn_altar"), G("b", "twilight_rite", "blended_light"),
        S("disc_complete", char="b", discovery="twilight_rite"),                          # geheimes Wissen
        S("disc_teach", teacher="b", learner="c", discovery="twilight_rite"),             # nicht lehrbar
    ]


def _climb(boss: str, climber: str, company: str, markets: list[str]) -> list[Op]:
    """Echter Aufstieg bis Manager: Beförderungen an Tag 8/22/43; Handel liefert die Volumenpunkte (Bedingung der CEE)."""
    return [
        S("hire", actor=boss, company=company, char=climber, wage=100),
        DAY(8), S("advance_day", value=8), S("promote", actor=boss, company=company, char=climber),
        DAY(22), S("revenue", company=company, amount=4000), S("advance_day", value=22),
        S("promote", actor=boss, company=company, char=climber),
        DAY(43), S("revenue", company=company, amount=4000), S("advance_day", value=43),
        S("promote", actor=boss, company=company, char=climber),                    # Volumen fehlt noch
        *[big_trade(climber, m, 20) for m in markets],                              # 6 x 600 Volumen, 6 neue Kontakte
        S("promote", actor=boss, company=company, char=climber),                    # Manager
    ]


def scenario_company_lifecycle() -> list[Op]:
    w19, s1, g1 = char_with_goal("wage", "w"), char_with_goal("stability", "s"), char_with_goal("growth", "g")
    c1, c2 = co(1), co(2)
    return [
        *person("boss", trade=700), D("boss", COIN, 30000), *person("boss2", trade=700), D("boss2", COIN, 2000),
        *person(w19, trade=100), *person(s1, trade=700), *person(g1, trade=100), *person("out", trade=100),
        *person("e1", trade=100), *person("e2", trade=100), *person("e3", trade=100),
        S("found", char="boss", capital=999),                                           # unter dem Mindestkapital
        S("found", char="boss", capital=5000),                                          # Firma 1
        S("hire", actor="boss", company=c1, char=w19, wage=19),                         # Lohn knapp unter Bedarf (20)
        S("hire", actor="boss", company=c1, char=s1, wage=25, share=50),
        S("hire", actor="boss", company=c1, char=g1, wage=20),
        S("hire", actor="boss", company=c1, char="out", wage=4),                        # unter dem Mindestlohn
        S("hire", actor="boss", company=c1, char=s1, wage=25),                          # schon angestellt
        S("hire", actor="out", company=c1, char="out", wage=25),                        # keine Berechtigung
        S("hire", actor="boss", company=c1, char="out", wage=25, share=400),            # Gewinnbeteiligung über der Grenze
        S("revenue", company=c1, amount=3000),
        S("revenue", company=c1, amount=0),
        DAY(8), S("advance_day", value=8),                                              # 8 Tage: Zufriedenheit, Treue, Rufe
        S("advance_day", value=8),                                                      # nicht rückwärts / nicht doppelt
        S("promote", actor="boss", company=c1, char=s1),                                # Mastery 3, 7 Tage Dienstzeit: ok
        S("promote", actor="boss", company=c1, char=w19),                               # Meisterschaft zu niedrig
        S("promote", actor="out", company=c1, char=s1),
        S("set_contract", actor="boss", company=c1, char=s1, wage=60),
        S("set_contract", actor="boss", company=c1, char=s1, share=400),
        S("set_contract", actor="boss", company=c1, char="out", wage=60),
        S("upgrade", actor="boss", company=c1),                                         # Stufe 2 (5000 aus der Kasse)
        S("upgrade", actor="boss", company=c1),                                         # Kasse reicht für Stufe 3 nicht
        S("demote", actor="boss", company=c1, char=s1),
        S("demote", actor="boss", company=c1, char=s1),                                 # schon unterste Stufe
        S("fire", actor="boss", company=c1, char=g1),
        S("fire", actor="boss", company=c1, char=g1),
        S("resign", char=w19, company=c1),
        S("resign", char=w19, company=c1),
        S("hire", actor="boss", company=c1, char=g1, wage=40),                          # Wiedereinstellung
        S("found", char="boss2", capital=1000),                                         # Firma 2: kleine Kasse
        *[S("hire", actor="boss2", company=c2, char=e, wage=300) for e in ("e1", "e2", "e3")],
        DAY(20), S("advance_day", value=20),
        S("advance_day", value=60),                                                     # zu viele Tage auf einmal
        DAY(40), S("advance_day", value=40),                                            # Firma 2 kann nicht zahlen: Ruf, Kündigungen
        S("close", actor="boss2", company=c2),
        S("close", actor="boss2", company=c2),                                          # schon geschlossen
        S("revenue", company=c2, amount=10),                                            # geschlossen
    ]


def scenario_company_governance() -> list[Op]:
    c = co(1)
    markets = [f"mk{i}" for i in range(6)]
    off = lambda n: f"{c}-offer-{n}"  # noqa: E731
    prop = lambda n: f"{c}-prop-{n}"  # noqa: E731
    return [
        *person("boss", trade=700), D("boss", COIN, 30000), *person("climb", trade=24000), *person("inv"), D("inv", COIN, 10000),
        *[op for m in markets for op in (person(m, trade=100) + [D(m, COIN, 200000)])], D("climb", BLADE, 500),
        S("found", char="boss", capital=5000),
        *_climb("boss", "climb", c, markets),
        S("grant_equity", actor="boss", company=c, char="climb", qty=50),
        S("grant_equity", actor="boss", company=c, char="climb", qty=100),              # über 100 je Person
        S("grant_equity", actor="inv", company=c, char="climb", qty=10),                # keine Berechtigung
        S("offer_shares", char="boss", company=c, qty=300, price=10),
        S("offer_shares", char="inv", company=c, qty=1, price=10),                      # besitzt keine Anteile
        S("offer_shares", char="boss", company=c, qty=900, price=10),                   # nicht genug freie Anteile
        S("disclosure", company=c, save_as="d1"),
        S("purchase", char="inv", company=c, offer=off(1), qty=100, ack="$d1"),         # Vorkaufsfrist läuft noch
        S("preempt", char="inv", company=c, offer=off(1), qty=10),                      # noch kein Gesellschafter
        S("preempt", char="boss", company=c, offer=off(1), qty=10),                     # Verkäufer selbst
        S("preempt", char="climb", company=c, offer=off(1), qty=10),                    # Gesellschafter (50 Anteile): ok
        DAY(51),                                                                         # Frist (7 Tage ab Tag 43) abgelaufen
        S("preempt", char="climb", company=c, offer=off(1), qty=10),                    # zu spät
        S("purchase", char="inv", company=c, offer=off(1), qty=100, ack="deadbeef"),    # falsche Offenlegung
        S("purchase", char="boss", company=c, offer=off(1), qty=100, ack="$disclosure"),  # Selbstkauf
        S("purchase", char="inv", company=c, offer=off(1), qty=291, ack="$disclosure"),  # mehr als noch angeboten (290)
        S("purchase", char="inv", company=c, offer=off(1), qty=290, ack="$disclosure"),
        S("purchase", char="inv", company=c, offer=off(1), qty=1, ack="$disclosure"),   # erledigt
        S("offer_shares", char="inv", company=c, qty=100, price=20),
        S("withdraw_offer", char="boss", company=c, offer=off(2)),                      # fremdes Angebot
        S("withdraw_offer", char="inv", company=c, offer=off(2)),
        S("propose", char="inv", company=c, kind="appoint_ceo", candidate="climb"),     # Antrag 1
        S("propose", char="inv", company=c, kind="appoint_ceo", candidate="climb"),     # läuft schon
        S("propose", char="boss", company=c, kind="dismiss_ceo"),                       # kein Geschäftsführer
        S("propose", char="inv", company=c, kind="appoint_ceo", candidate="inv"),       # Kandidat nicht angestellt
        S("vote", char="inv", company=c, proposal=prop(1), yes=True),
        S("vote", char="inv", company=c, proposal=prop(1), yes=True),                   # doppelt
        S("vote", char="ghost", company=c, proposal=prop(1), yes=True),
        S("vote", char="boss", company=c, proposal=prop(1), yes=True),                  # Mehrheit: Ausführung scheitert (Dienstzeit)
        S("vote", char="boss", company=c, proposal=prop(1), yes=True),                  # nicht mehr offen
        S("propose", char="inv", company=c, kind="appoint_ceo", candidate="climb"),     # Antrag 2
        S("vote", char="boss", company=c, proposal=prop(2), yes=False),                 # Veto des Gründers
        S("propose", char="inv", company=c, kind="appoint_ceo", candidate="climb"),     # Antrag 3 (bleibt unbeantwortet)
        DAY(60), S("revenue", company=c, amount=4000), S("advance_day", value=60),
        S("vote", char="climb", company=c, proposal=prop(3), yes=True),                 # Frist (5 Tage) abgelaufen
        big_trade("climb", "mk0", 300),                                                  # Volumen 9000, Dienstzeit läuft
        DAY(75), S("advance_day", value=75),
        S("propose", char="boss", company=c, kind="appoint_ceo", candidate="climb"),    # Antrag 4
        S("vote", char="boss", company=c, proposal=prop(4), yes=True),                  # Geschäftsführer
        S("propose", char="boss", company=c, kind="appoint_ceo", candidate="climb"),    # es gibt schon einen
        S("fire", actor="boss", company=c, char="climb"),                                # nur per Beschluss
        S("demote", actor="boss", company=c, char="climb"),
        S("propose", char="inv", company=c, kind="dismiss_ceo"),                        # Antrag 5
        S("vote", char="inv", company=c, proposal=prop(5), yes=True),                   # 300 von 1000: noch keine Mehrheit
        S("vote", char="boss", company=c, proposal=prop(5), yes=True),                  # abberufen
        S("disclosure", company=c),
    ]


def scenario_company_poach_close() -> list[Op]:
    a, b = co(1), co(2)
    return [
        *person("boss", trade=700), D("boss", COIN, 30000), *person("rival", trade=700), D("rival", COIN, 30000),
        *person("inv"), D("inv", COIN, 5000), *person("e1", trade=700), *person("e2", trade=100), *person("e3", trade=100),
        S("found", char="boss", capital=3003),
        S("found", char="rival", capital=5000),
        S("hire", actor="boss", company=a, char="e1", wage=60),
        S("hire", actor="boss", company=a, char="e2", wage=20),
        S("hire", actor="boss", company=a, char="e3", wage=22),
        S("revenue", company=a, amount=500),
        DAY(5), S("advance_day", value=5),
        S("poach", actor="rival", company=b, char="e2", wage=21),                       # schlechteres Angebot
        S("poach", actor="rival", company=b, char="e2", wage=19),                       # noch schlechter
        S("poach", actor="rival", company=b, char="ghost", wage=50),
        S("poach", actor="rival", company=b, char="boss", wage=50),                     # nicht angestellt
        S("poach", actor="boss", company=a, char="e2", wage=50),                        # dieselbe Firma
        S("poach", actor="inv", company=b, char="e2", wage=50),                         # keine Berechtigung
        S("poach", actor="rival", company=b, char="e2", wage=45),
        S("poach", actor="rival", company=b, char="e3", wage=40),
        S("poach", actor="rival", company=b, char="e1", wage=120),
        S("offer_shares", char="boss", company=a, qty=667, price=1),
        DAY(13), S("revenue", company=a, amount=300), S("advance_day", value=13),
        S("close", actor="inv", company=a),                                              # noch ohne Anteile
        S("purchase", char="inv", company=a, offer=f"{a}-offer-1", qty=667, ack="$disclosure"),
        S("close", actor="boss", company=a),                                             # Gründer hält nur noch 333: nicht mehr Eigentümer
        S("close", actor="inv", company=b),                                              # fremde Firma
        S("close", actor="inv", company=a),                                              # Mehrheitsgesellschafter: Auszahlung 333/667
        S("close", actor="inv", company=a),                                              # schon geschlossen
        S("disclosure", company=a),
    ]


def scenario_production() -> list[Op]:
    c1, c2 = co(1), co(2)
    ore, ing = "iron_ore@standard", "iron_ingot@standard"
    PS = lambda actor, company, key, qty: S("prod_stock_in", actor=actor, company=company, item_key=key, qty=qty)  # noqa: E731
    START = lambda actor, company, worker, recipe, batches, grade: S("prod_start", actor=actor, company=company,  # noqa: E731
                                                                  worker=worker, recipe=recipe, batches=batches, grade=grade)
    return [
        *person("boss", trade=700), D("boss", COIN, 30000), *person("smith", smithing=700), *person("novice"),
        *person("alch", alchemy=700), *person("rival", trade=700), D("rival", COIN, 5000), *person("w1", smithing=700),
        *person("w2", smithing=100),
        D("boss", ore, 600), D("boss", ing, 60), D("boss", "charcoal@standard", 40), D("boss", "iron_blade@fine", 60),
        S("found", char="boss", capital=5000), S("found", char="rival", capital=1000),
        S("hire", actor="boss", company=c1, char="smith", wage=50), S("hire", actor="boss", company=c1, char="novice", wage=40),
        S("hire", actor="boss", company=c1, char="alch", wage=60),
        PS("boss", c1, ore, 100), PS("smith", c1, ore, 1),                  # Berechtigung fehlt
        PS("boss", c1, COIN, 1), PS("boss", c1, ore, 101),                  # Münzen sind keine Ware / Lager (200) voll
        PS("boss", c1, ing, 20), PS("boss", c1, "charcoal@standard", 20),
        S("prod_stock_out", actor="boss", company=c1, item_key=ore, qty=10), S("prod_stock_out", actor="boss", company=c1, item_key=ore, qty=500),
        START("boss", c1, "smith", "iron_ingot", 3, "standard"),            # Auftrag 1: 3 Chargen, 1 Tag je Charge
        START("boss", c1, "smith", "iron_ingot", 1, "standard"),            # Arbeiter belegt
        START("boss", c1, "novice", "iron_ingot", 1, "standard"),           # keine freie Linie (Stufe 1)
        START("smith", c1, "novice", "iron_ingot", 1, "standard"),          # keine Berechtigung
        START("boss", c1, "boss", "iron_ingot", 1, "standard"),             # kein Mitarbeiter
        START("boss", c1, "novice", "ghost", 1, "standard"),
        START("boss", c1, "novice", "iron_ingot", 11, "standard"),
        START("boss", c1, "novice", "iron_ingot", 1, "legendary"),
        S("revenue", company=c1, amount=6000), S("upgrade", actor="boss", company=c1),   # Stufe 2: zwei Linien, Lager 600
        START("boss", c1, "novice", "iron_blade", 1, "standard"),           # Meisterschaft fehlt (Material vorhanden)
        START("boss", c1, "alch", "frostglass", 1, "standard"),             # Entdeckung fehlt
        START("boss", c1, "novice", "iron_ingot", 20, "standard"),          # Material reicht nicht
        DAY(2), S("advance_day", value=2),                                  # Tag 1+2: zwei Chargen fertig
        PS("boss", c1, ing, 20),
        START("boss", c1, "novice", "iron_ingot", 1, "standard"),           # Auftrag 2
        START("boss", c1, "alch", "iron_ingot", 1, "standard"),             # beide Linien belegt
        DAY(4), S("advance_day", value=4),
        S("prod_sell", actor="boss", company=c1, item_key="iron_ingot@common", qty=20),   # NPC kauft zu 60 % des Referenzwerts
        S("prod_sell", actor="boss", company=c1, item_key="iron_blade@fine", qty=20),     # nicht im Lager
        S("prod_sell", actor="smith", company=c1, item_key="iron_ingot@common", qty=1),
        PS("boss", c1, "iron_blade@fine", 60),
        S("prod_sell", actor="boss", company=c1, item_key="iron_blade@fine", qty=40),     # Tageslimit des Abnehmers
        S("prod_sell", actor="boss", company=c1, item_key="iron_blade@fine", qty=16),   # 240 + 1728 = 1968: unter dem Limit
        DAY(5),
        S("prod_sell", actor="boss", company=c1, item_key="iron_blade@fine", qty=2),      # neuer Tag
        START("boss", c1, "smith", "iron_blade", 2, "standard"),            # Stufe 2: 2 Tage je Charge
        S("prod_cancel", actor="smith", company=c1, job=f"srv1-job-{3:08d}"),
        DAY(6), S("advance_day", value=6),
        S("prod_cancel", actor="boss", company=c1, job=f"srv1-job-{3:08d}"),  # angefangene Charge verloren, Rest zurück
        S("prod_cancel", actor="boss", company=c1, job=f"srv1-job-{3:08d}"),
        # Firma 2: kleine Kasse, Lohn bleibt aus -> Linie steht
        S("hire", actor="rival", company=c2, char="w1", wage=400), S("hire", actor="rival", company=c2, char="w2", wage=400),
        D("rival", ore, 60), PS("rival", c2, ore, 60),
        START("rival", c2, "w1", "iron_ingot", 3, "standard"),
        DAY(7), S("advance_day", value=7),
        DAY(12), S("advance_day", value=12),
        PS("boss", c1, ore, 60), START("boss", c1, "alch", "iron_ingot", 2, "standard"),   # Auftrag läuft beim Schließen weiter
        S("close", actor="boss", company=c1),                               # Ware und Auftragskonten gehen an den Gründer
        START("boss", c1, "smith", "iron_ingot", 1, "standard"),            # Firma geschlossen
        S("close", actor="rival", company=c2),
    ]


def MP(char: str, side: str, qty: int, price: int, key: str = "iron_blade@fine", **kw: Any) -> Op:
    return S("market_place", char=char, side=side, item_key=key, qty=qty, price=price, **kw)


def scenario_market() -> list[Op]:
    fine = "iron_blade@fine"  # Referenz 180 je Stück, Band 135..225
    return [
        *[op for c in "abcd" for op in (*person(c), D(c, COIN, 5000), D(c, fine, 30), D(c, "iron_blade@common", 10))],
        MP("a", "sell", 5, 190),                                    # ord 1 wartet (Ware hinterlegt)
        MP("b", "buy", 3, 170),                                     # ord 2 wartet (Münzen hinterlegt)
        MP("c", "buy", 5, 200),                                     # zahlt den Preis der wartenden Order (190)
        MP("a", "sell", 4, 200),                                    # ord: trifft nichts (Gebot 170 zu niedrig)
        MP("d", "sell", 2, 170),                                    # trifft Gebot 170 von b (Teilausführung)
        MP("d", "sell", 3, 170),                                    # 1 Stück ausgeführt, 2 warten im Buch
        MP("a", "buy", 1, 150),                                     # eigene Verkaufsorder (200) wird nicht gegen sich selbst ausgeführt
        MP("b", "sell", 6, 135, ioc=True),                          # IOC am Rand des Bandes, Rest verfällt
        MP("b", "buy", 1, 226),                                     # über dem Band
        MP("b", "buy", 1, 134),                                     # unter dem Band
        MP("b", "buy", 1, 180, key="iron_blade"),                   # Schlüssel ohne Güteklasse
        MP("b", "hold", 1, 180),                                    # ungültige Seite
        MP("ghost", "buy", 1, 180),
        MP("b", "buy", 2000, 180),                                  # Menge über dem Limit
        MP("b", "buy", 1000, 180),                                  # nicht genug Münzen
        S("market_cancel", char="b", order="srv1-ord-00000004"),    # fremde Order
        S("market_cancel", char="a", order="srv1-ord-00000004"),    # eigene Verkaufsorder zurücknehmen
        S("market_cancel", char="a", order="srv1-ord-00000004"),    # schon weg
        *[MP("d", "sell", 1, 220 + i % 3) for i in range(9)],       # Order-Limit je Figur: 10 (eine wartet schon)
        MP("d", "sell", 1, 221),
        DAY(5),
        MP("c", "buy", 10, 225),                                    # fegt das Buch leer (mehrere Preise, Preis-Zeit-Priorität)
        DAY(9),
        MP("a", "sell", 2, 200),
        S("market_expire", value=15),                               # a's Order (Tag 9 + 7 = 16) bleibt, alte verfallen
        S("market_expire", value=-1),
        S("market_expire", value=16),
        DAY(20),
        MP("b", "sell", 3, 150, key="iron_blade@common"),
        MP("c", "buy", 3, 150, key="iron_blade@common"),
        S("disclosure", company="srv1-co-00000001"),
    ]


# ---------------------------------------------------------------- Zufallsskripte ---------
class Rng:
    """Kleiner, in jeder Sprache nachbaubarer Zufall (xorshift32). Er dient nur zum ERZEUGEN der Skripte; die fertigen
    Skripte stehen ausgeschrieben in den Vektoren, Ports brauchen den Zufall nicht."""

    def __init__(self, seed: int) -> None:
        self.x = (seed * 2654435761 + 12345) & 0xFFFFFFFF or 1

    def next(self) -> int:
        x = self.x
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.x = x
        return x

    def below(self, n: int) -> int:
        return self.next() % n

    def pick(self, items: list[Any]) -> Any:
        return items[self.below(len(items))] if items else None


POP = [f"p{i}" for i in range(8)]
ITEMS = ["iron_blade@fine", "iron_blade@common", "healing_salve@common"]


def random_script(seed: int, steps: int) -> list[Op]:
    """Zustandsbewusst erzeugt (Auswahl nutzt den laufenden Weltzustand), aber vollständig als Skript ausgeschrieben."""
    rng, env = Rng(seed), Env()
    script: list[Op] = []

    def emit(op: Op) -> None:
        script.append(op)
        execute(env, op)

    for i, pid in enumerate(POP):
        for op in person(pid, trade=700 if i < 4 else 100, smithing=700 if i % 2 == 0 else 0):
            emit(op)
        emit(D(pid, COIN, 20000 + 1000 * i))
        emit(D(pid, "iron_blade@fine", 20))
        emit(D(pid, "iron_ore@standard", 60))
    reg = env.company_registry

    def companies(open_only: bool = True) -> list[str]:
        return [k for k, c in sorted(reg.companies.items()) if c["open"] or not open_only]

    def owner_of(c: dict[str, Any]) -> str:
        return max(sorted(c["shares"]), key=lambda h: c["shares"][h])

    for _ in range(steps):
        kind = rng.below(28)
        cs = companies()
        cid = rng.pick(cs) if cs and rng.below(10) else rng.pick(companies(False)) if reg.companies else "srv1-co-00000099"
        c = reg.companies.get(cid)
        me = rng.pick(POP)
        other = rng.pick([x for x in POP if x != me])
        wild = rng.below(12) == 0  # gelegentlich bewusst unpassende Beteiligte
        if kind <= 2:
            emit(S("trade", seller=me, buyer=other, item_key=rng.pick(ITEMS) if rng.below(4) else BLADE, qty=1 + rng.below(4),
                   price=50 + rng.below(700)))
        elif kind == 3:
            emit(S("craft", char=me, recipe=rng.pick(["iron_ingot", "iron_ingot", "iron_blade"]), qty=1 + rng.below(8),
                   grade=rng.pick(["standard", "rough", "select"])))
        elif kind == 4:
            emit(D(me, rng.pick(["iron_ore@standard", "charcoal@standard", "iron_ingot@standard"]), 1 + rng.below(30)))
        elif kind == 5 and len(cs) < 3 and rng.below(3):
            emit(S("found", char=me, capital=1000 + rng.below(4000)))
        elif c is None:
            n = env.day[0] + 1 + rng.below(3)
            emit(DAY(n))
            emit(S("advance_day", value=n))
        elif kind == 6:
            emit(S("hire", actor=owner_of(c) if not wild else me, company=cid, char=other, wage=15 + rng.below(80),
                   share=rng.below(80)))
        elif kind == 7:
            emit(S("fire", actor=owner_of(c), company=cid, char=rng.pick(sorted(c["employees"])) or other))
        elif kind == 8:
            emit(S("resign", char=rng.pick(sorted(c["employees"])) or me, company=cid))
        elif kind == 9:
            emit(S("set_contract", actor=owner_of(c), company=cid, char=rng.pick(sorted(c["employees"])) or other,
                   wage=15 + rng.below(80)))
        elif kind == 10:
            emit(S("promote", actor=owner_of(c), company=cid, char=rng.pick(sorted(c["employees"])) or other))
        elif kind == 11:
            emit(S("demote", actor=owner_of(c), company=cid, char=rng.pick(sorted(c["employees"])) or other))
        elif kind == 12:
            emit(S("upgrade", actor=owner_of(c), company=cid))
        elif kind in (13, 14):
            emit(S("revenue", company=cid, amount=100 + rng.below(1500)))
        elif kind == 15:
            emit(S("offer_shares", char=rng.pick(sorted(c["shares"])) if not wild else me, company=cid,
                   qty=1 + rng.below(300), price=1 + rng.below(20)))
        elif kind == 16:
            offers = sorted(k for k, o in c["offers"].items() if o["remaining"] > 0)
            oid = rng.pick(offers) or f"{cid}-offer-9"
            who = rng.pick(sorted(c["shares"]) + [me])
            if rng.below(2):
                emit(S("preempt", char=who, company=cid, offer=oid, qty=1 + rng.below(50)))
            else:
                emit(S("purchase", char=other, company=cid, offer=oid, qty=1 + rng.below(200), ack="$disclosure"))
        elif kind == 17:
            offers = sorted(c["offers"])
            emit(S("withdraw_offer", char=rng.pick(sorted(c["shares"])), company=cid, offer=rng.pick(offers) or f"{cid}-offer-9"))
        elif kind == 18:
            emit(S("grant_equity", actor=owner_of(c), company=cid, char=rng.pick(sorted(c["employees"])) or other,
                   qty=1 + rng.below(120)))
        elif kind == 19:
            emit(S("propose", char=rng.pick(sorted(c["shares"])), company=cid, kind=rng.pick(["appoint_ceo", "dismiss_ceo"]),
                   candidate=rng.pick(sorted(c["employees"]))))
        elif kind == 20:
            pending = sorted(k for k, p in c["proposals"].items() if p["status"] == "pending")
            emit(S("vote", char=rng.pick(sorted(c["shares"]) + [me]), company=cid, proposal=rng.pick(pending) or f"{cid}-prop-9",
                   yes=bool(rng.below(2))))
        elif kind == 21:
            emit(S("poach", actor=rng.pick(POP), company=cid, char=other, wage=15 + rng.below(150)))
        elif kind == 22 and rng.below(10) == 0:
            emit(S("close", actor=owner_of(c) if not wild else me, company=cid))
        else:
            n = env.day[0] + 1 + rng.below(6)
            emit(DAY(n))
            emit(S("advance_day", value=n))
    return script


def random_market_script(seed: int, steps: int) -> list[Op]:
    """Zustandsbewusstes Zufallsskript nur für den Markt (zwei Güter, fünf Figuren, wechselnde Tage)."""
    rng, env = Rng(seed), Env()
    script: list[Op] = []

    def emit(op: Op) -> None:
        script.append(op)
        execute(env, op)

    keys = ["iron_blade@fine", "iron_blade@common"]
    for c in "abcde":
        for op in (*person(c), D(c, COIN, 6000), D(c, keys[0], 40), D(c, keys[1], 40)):
            emit(op)
    ref = {keys[0]: 180, keys[1]: 120}
    for _ in range(steps):
        kind = rng.below(12)
        if kind < 8:
            k = rng.pick(keys)
            emit(MP(rng.pick(list("abcde")), "buy" if rng.below(2) else "sell", 1 + rng.below(5), ref[k] * (70 + rng.below(60)) // 100, key=k,
                    ioc=rng.below(5) == 0))
        elif kind < 10 and env.exchange.orders:
            oid = rng.pick(sorted(env.exchange.orders))
            who = env.exchange.orders[oid]["char"] if rng.below(8) else "a"
            emit(S("market_cancel", char=who, order=oid))
        else:
            n = env.day[0] + 1 + rng.below(4)
            emit(DAY(n))
            emit(S("market_expire", value=n))
    return script


def scenario_rules_migration() -> list[Op]:
    """Startet unter CEE-Regeln v7 und hebt die Welt mitten im Ablauf auf v8 (Migrationsereignisse in den Historien)."""
    fine, ore = "iron_blade@fine", "iron_ore@standard"
    return [
        *[op for c in "abc" for op in (*person(c, smithing=700, trade=700), D(c, COIN, 20000), D(c, fine, 30), D(c, ore, 60))],
        S("price_advance", value=1),                                              # v7: keine Preisdynamik
        S("trade", seller="a", buyer="b", item_key=fine, qty=2, price=360),       # v7-Bericht ohne Referenzfeld
        S("craft", char="a", recipe="iron_ingot", qty=5, grade="standard"),
        S("found", char="a", capital=3000), S("hire", actor="a", company=co(1), char="b", wage=40),
        MP("c", "sell", 3, 190), MP("b", "buy", 2, 170),
        S("rules_upgrade", to="rules_v7.json"),                                   # nicht höher
        S("rules_upgrade", to="rules_v99.json"),
        S("rules_upgrade", to="../data/rules_v8.json"),
        S("cee_record", char="a", type="identity.rules_migrated", payload={"from": "7", "to": "8"}),  # nur über die Migration
        S("rules_migrate", char="a"),                                             # Version 8 gibt es im v7-Dienst nicht
        S("rules_upgrade", to="rules_v8.json", chars=["a", "b"]),                 # c bleibt zurück
        S("rules_migrate", char="a"),                                             # a ist schon migriert
        S("trade", seller="a", buyer="b", item_key=fine, qty=2, price=360),       # jetzt mit gemeldetem Referenzwert
        S("trade", seller="a", buyer="c", item_key=fine, qty=1, price=180),       # c ist nicht migriert
        S("hire", actor="a", company=co(1), char="c", wage=40),
        S("craft", char="c", recipe="iron_ingot", qty=1, grade="standard"),
        MP("c", "sell", 1, 190), MP("a", "buy", 1, 190),                           # Orderbuch: c darf nicht teilnehmen
        S("price_advance", value=2),
        S("maker_sell", char="a", item_key=ore, qty=5), S("maker_sell", char="c", item_key=ore, qty=5),
        S("rules_migrate", char="c"),
        S("rules_migrate", char="c"),                                             # keine weitere Version
        S("trade", seller="c", buyer="b", item_key=fine, qty=1, price=180),
        S("hire", actor="a", company=co(1), char="c", wage=40),
        DAY(5), S("advance_day", value=5),
        S("maker_buy", char="c", item_key=ore, qty=5),
    ]


def scenario_price_dynamics() -> list[Op]:
    fine, ore = "iron_blade@fine", "iron_ore@standard"
    MS = lambda c, k, q: S("maker_sell", char=c, item_key=k, qty=q)  # noqa: E731
    MB = lambda c, k, q: S("maker_buy", char=c, item_key=k, qty=q)  # noqa: E731
    wash = [op for d in range(2, 12) for op in (DAY(d), MP("a", "sell", 5, 216), MP("b", "buy", 5, 216), S("price_advance", value=d))]
    return [
        *[op for c in "abc" for op in (*person(c), D(c, COIN, 20000), D(c, fine, 60), D(c, ore, 100))],
        S("trade", seller="a", buyer="b", item_key=fine, qty=2, price=360),        # Referenz = Tabellenwert (Faktor 1000)
        S("price_advance", value=1),
        S("price_advance", value=1),                                                # nicht rückwärts / nicht doppelt
        S("price_advance", value=40),                                               # zu viele Tage auf einmal
        MP("a", "sell", 1, 226), MP("a", "sell", 1, 225),                           # Band ±25 % um den Referenzwert
        *wash,                                                                      # Scheinhandel treibt den Faktor nur langsam und begrenzt
        S("trade", seller="a", buyer="b", item_key=fine, qty=1, price=216),         # CEE-Bericht trägt den aktuellen Referenzwert
        MP("a", "sell", 1, 250),                                                    # Band wandert mit dem Referenzwert (alt: max. 225)
        MP("a", "sell", 1, 256),
        S("price_shock", item_key=ore, permille=1300, days=5),
        S("price_shock", item_key=ore, permille=1000, days=5),                      # kein Schock
        S("price_shock", item_key=ore, permille=1301, days=5),
        S("price_shock", item_key=ore, permille=699, days=5),
        S("price_shock", item_key=ore, permille=1100, days=0),
        S("price_shock", item_key=ore, permille=1100, days=31),
        S("price_shock", item_key="ghost@fine", permille=1100, days=3),
        MS("a", ore, 10), MB("b", ore, 10),                                         # Händler: Spanne um den Referenzwert
        DAY(12), S("price_advance", value=12), DAY(13), S("price_advance", value=13),
        MB("b", ore, 40), MB("b", ore, 1),                                          # Tagesmenge des Händlers erschöpft
        MS("a", fine, 1),                                                           # Händler handelt nicht damit
        MS("a", ore, 0), MS("ghost", ore, 1), MS("npc:maker", ore, 1),
        MS("c", ore, 1000), MB("c", ore, 1),
        D("c", "iron_ore@rough", 1), MS("c", "iron_ore@rough", 1),                  # Preis wäre 0
        DAY(14), MB("b", ore, 40),                                                  # neuer Tag
        *[op for d in range(15, 30) for op in (DAY(d), S("price_advance", value=d))],   # Schock endet, Rückkehr zum Marktpreis
        MS("a", ore, 5),
    ]


def random_price_script(seed: int, steps: int) -> list[Op]:
    """Zustandsbewusstes Zufallsskript für Markt + Preisdynamik + Händler (CEE-Regeln v8)."""
    rng, env = Rng(seed), Env(CEE_RULES_V8)
    script: list[Op] = []

    def emit(op: Op) -> None:
        script.append(op)
        execute(env, op)

    keys = ["iron_blade@fine", "iron_ore@standard", "bread@common"]
    ref = {keys[0]: 180, keys[1]: 1, keys[2]: 3}
    for c in "abcd":
        for op in (*person(c), D(c, COIN, 30000), *[D(c, k, 80) for k in keys]):
            emit(op)
    for _ in range(steps):
        kind, who, k = rng.below(14), rng.pick(list("abcd")), rng.pick(keys)
        if kind < 5:
            r = ref[k] * (60 + rng.below(100)) // 100
            emit(MP(who, "buy" if rng.below(2) else "sell", 1 + rng.below(6), max(1, r), key=k, ioc=rng.below(6) == 0))
        elif kind < 8:
            emit(S("maker_sell" if rng.below(2) else "maker_buy", char=who, item_key=k, qty=1 + rng.below(12)))
        elif kind == 8:
            emit(S("price_shock", item_key=k, permille=1000 + rng.below(700) - 350, days=1 + rng.below(12)))
        elif kind == 9 and env.exchange.orders:
            oid = rng.pick(sorted(env.exchange.orders))
            emit(S("market_cancel", char=env.exchange.orders[oid]["char"], order=oid))
        else:
            n = env.day[0] + 1 + rng.below(3)
            emit(DAY(n))
            emit(S("price_advance", value=n))
            emit(S("market_expire", value=n))
    return script


# ---------------------------------------------------------------- Vektor ------------------
NAME = "world_scenarios"
RESULT_KEYS = ("expect", "result", "error", "world_sha256")

SCENARIOS: list[tuple[str, str, Callable[[], list[Op]]]] = [
    ("world_trade_inventory", "Handel und Inventar: Erfolg, Selbsthandel, Preis 0, leerer Bestand, ungültige Schlüssel",
     scenario_trade_inventory),
    ("world_crafting", "Herstellung: Verbrauch/Erzeugung, Güteklassen, Mengen, fehlende Voraussetzungen, Wiederholungsabnahme",
     scenario_crafting),
    ("world_discovery", "Entdeckungen: Beweise, Pionier, Lehrfenster, Voraussetzungen, geheimes Wissen",
     scenario_discovery),
    ("company_lifecycle", "Firma: Gründung, Einstellung, Löhne knapp unter Bedarf (negatives Floor), Beförderung, Ausbau, "
     "unbezahlte Mitarbeiter, Kündigungen, Schließung", scenario_company_lifecycle),
    ("company_governance", "Firma: Aufstieg bis Manager mit echtem Handel, Anteile, Vorkaufsrecht, Offenlegung, Beschlüsse, "
     "Veto, Ausführungsfehler, Geschäftsführer", scenario_company_governance),
    ("company_poach_close", "Firma: Abwerben (Annahme, schlechtere Angebote), Anteilsverkauf, Liquidation mit Rundungsrest",
     scenario_company_poach_close),
    ("company_production", "Firmenproduktion: Lager, Linien, Chargen, Qualitätsdeckel, Abnehmer mit Tageslimit, Abbruch, Stillstand, Schließung",
     scenario_production),
    ("market_orderbook", "Markt: Orderbuch, Preis-Zeit-Priorität, Teilausführung, IOC, Preisband, Limits, Verfall, Preisindex",
     scenario_market),
    ("random_market_3", "Zustandsbewusstes Zufallsskript nur für den Markt (Seed 3, 220 Aktionen), ausgeschrieben",
     lambda: random_market_script(3, 220)),
    ("random_world_4", "Zustandsbewusst erzeugtes Zufallsskript (Seed 4, 260 Schritte), ausgeschrieben",
     lambda: random_script(4, 260)),
    ("random_world_9", "Zustandsbewusst erzeugtes Zufallsskript (Seed 9, 260 Schritte), ausgeschrieben",
     lambda: random_script(9, 260)),
    ("price_dynamics", "Preisdynamik (CEE-Regeln v8): Referenzwert folgt dem Markt, Band wandert, Schocks, NPC-Händler mit Tagesmengen",
     scenario_price_dynamics),
    ("random_price_5", "Zustandsbewusstes Zufallsskript Markt + Preisdynamik + Händler (Seed 5, 260 Aktionen, Regeln v8), ausgeschrieben",
     lambda: random_price_script(5, 260)),
    ("rules_migration", "Regelversions-Migration: Welt von v7 auf v8 mitten im Ablauf, Migrationsereignisse, zurückgebliebene Figur",
     scenario_rules_migration),
]


SCENARIO_RULES: dict[str, str] = {"price_dynamics": CEE_RULES_V8, "random_price_5": CEE_RULES_V8}  # Szenarien, die nicht unter CEE_RULES laufen (z. B. Preisdynamik ab Regeln v8)


def run_scenario(name: str, description: str, script: list[Op]) -> dict[str, Any]:
    rules = SCENARIO_RULES.get(name, CEE_RULES)
    steps, final = run_script(script, rules)
    sc = {"name": name, "description": description, "steps": steps, "final": final,
          "final_world_sha256": hashlib.sha256(canonical_bytes(final)).hexdigest()}
    if rules != CEE_RULES:
        sc["cee_rules_file"] = rules
    return sc


def build_vector() -> dict[str, Any]:
    return {"format": FORMAT_VERSION, "name": NAME, "cee_rules_file": CEE_RULES, "cee_rules_sha256": _sha("mmo_cee", CEE_RULES),
            "company_rules_file": COMPANY_RULES, "company_rules_sha256": _sha("mmo_world", COMPANY_RULES),
            "market_rules_file": MARKET_RULES, "market_rules_sha256": _sha("mmo_world", MARKET_RULES),
            "production_rules_file": PRODUCTION_RULES, "production_rules_sha256": _sha("mmo_world", PRODUCTION_RULES),
            "pricing_rules_file": PRICING_RULES, "pricing_rules_sha256": _sha("mmo_world", PRICING_RULES),
            "extra_cee_rules": {f: _sha("mmo_cee", f) for f in sorted(set(SCENARIO_RULES.values()))},
            "scenarios": [run_scenario(n, d, f()) for n, d, f in SCENARIOS]}


def strip_result(step: Op) -> Op:
    return {k: v for k, v in step.items() if k not in RESULT_KEYS}


def verify_vector(vec: dict[str, Any]) -> list[str]:
    """Spielt jedes Skript neu ab und meldet jede Abweichung (Ergebnis, Fehlerklasse oder Welt-Hash) mit Schrittnummer."""
    if vec.get("format") != FORMAT_VERSION:
        return [f"unbekanntes Format {vec.get('format')!r}"]
    errs: list[str] = []
    if _sha("mmo_cee", vec["cee_rules_file"]) != vec["cee_rules_sha256"]:
        errs.append("CEE-Regeldatei hat sich geändert (SHA-256 weicht ab)")
    if _sha("mmo_world", vec["company_rules_file"]) != vec["company_rules_sha256"]:
        errs.append("Firmenregeln haben sich geändert (SHA-256 weicht ab)")
    if _sha("mmo_world", vec["market_rules_file"]) != vec["market_rules_sha256"]:
        errs.append("Marktregeln haben sich geändert (SHA-256 weicht ab)")
    if _sha("mmo_world", vec["production_rules_file"]) != vec["production_rules_sha256"]:
        errs.append("Produktionsregeln haben sich geändert (SHA-256 weicht ab)")
    if _sha("mmo_world", vec["pricing_rules_file"]) != vec["pricing_rules_sha256"]:
        errs.append("Preisregeln haben sich geändert (SHA-256 weicht ab)")
    for f, h in vec["extra_cee_rules"].items():
        if _sha("mmo_cee", f) != h:
            errs.append(f"CEE-Regeldatei {f} hat sich geändert (SHA-256 weicht ab)")
    for sc in vec["scenarios"]:
        steps, final = run_script([strip_result(s) for s in sc["steps"]], sc.get("cee_rules_file", vec["cee_rules_file"]))
        for i, (got, want) in enumerate(zip(steps, sc["steps"])):
            if got != want:
                errs.append(f"{sc['name']}: Schritt {i} ({want['op']}) weicht ab")
                break
        if final != sc["final"] or hashlib.sha256(canonical_bytes(final)).hexdigest() != sc["final_world_sha256"]:
            errs.append(f"{sc['name']}: Endzustand weicht ab")
    return errs


def _compact(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def render(vec: dict[str, Any]) -> str:
    """Kopfdaten, je Szenario ein Kopf, dann ein Schritt pro Zeile (kompakt, diff-freundlich)."""
    head = {k: v for k, v in vec.items() if k != "scenarios"}
    lines = [_compact(head)[:-1] + ',"scenarios":[']
    for si, sc in enumerate(vec["scenarios"]):
        lines.append("{" + ('"cee_rules_file":' + _compact(sc["cee_rules_file"]) + "," if "cee_rules_file" in sc else "")
                     + '"description":' + _compact(sc["description"]) + ',"final":' + _compact(sc["final"])
                     + ',"final_world_sha256":' + _compact(sc["final_world_sha256"]) + ',"name":' + _compact(sc["name"])
                     + ',"steps":[')
        lines += [_compact(st) + ("," if i < len(sc["steps"]) - 1 else "") for i, st in enumerate(sc["steps"])]
        lines.append("]}" + ("," if si < len(vec["scenarios"]) - 1 else ""))
    lines.append("]}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("write", "check"):
        print(__doc__)
        return 2
    mode, out = argv[1], Path(argv[2])
    path, text = out / f"{NAME}.json", render(build_vector())
    if mode == "write":
        out.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"geschrieben: {path}")
        return 0
    if not path.exists():
        print(f"FEHLT: {path}")
        return 1
    if path.read_text(encoding="utf-8") != text:
        print(f"ABWEICHUNG: {path}")
        return 1
    print(f"ok: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

