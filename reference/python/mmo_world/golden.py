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

import hashlib
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from mmo_cee.errors import RuleViolation
from mmo_cee.golden import state_hash
from mmo_cee.history import _canonical as canonical_bytes
from mmo_cee.rules import load_rules
from mmo_cee.service import CharacterService

from .company import CompanyRegistry, goal_of, load_company_rules
from .company_service import CompanyService
from .crafting import CraftingService
from .discovery import DiscoveryRegistry
from .errors import WorldError
from .inventory import Inventory
from .market import TradeService
from .service import DiscoveryService

FORMAT_VERSION = 1
CEE_RULES = "rules_v7.json"
COMPANY_RULES = "company_rules_v1.json"
Op = dict[str, Any]


def _sha(pkg: str, name: str) -> str:
    return hashlib.sha256(resources.files(pkg).joinpath("data", name).read_bytes()).hexdigest()


def _jsonable(x: Any) -> Any:
    return json.loads(canonical_bytes(x)) if x is not None else None


# ---------------------------------------------------------------- Ausführungsumgebung ----
class Env:
    def __init__(self) -> None:
        self.svc = CharacterService(rules=load_rules(CEE_RULES))
        self.inv = Inventory()
        self.day = [1]
        self.chars: list[str] = []
        self.saved: dict[str, Any] = {}
        clock = lambda: self.day[0]  # noqa: E731
        self.discovery_registry = DiscoveryRegistry(self.svc.rules)
        self.discovery = DiscoveryService(self.svc, self.discovery_registry, clock)
        self.crafting = CraftingService(self.svc, self.inv, clock)
        self.trading = TradeService(self.svc, self.inv, clock)
        self.company_rules = load_company_rules(COMPANY_RULES)
        self.company_registry = CompanyRegistry(self.company_rules)
        self.company = CompanyService(self.svc, self.inv, self.company_registry, clock)

    def snapshot(self) -> dict[str, Any]:
        return {"day": self.day[0], "inventory": json.loads(self.inv.to_json()),
                "discovery": json.loads(self.discovery_registry.to_json()),
                "companies": json.loads(self.company_registry.to_json()),
                "counters": {"trade": self.trading._counter, "craft": self.crafting._counter},
                "characters": {c: state_hash(json.loads(canonical_bytes(self.svc.state(c).parts))) for c in sorted(self.chars)}}

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
    env.chars.append(a["char"])
    return env.svc.log.events(a["char"])[0].hash


def _disclosure(env: Env, a: Op) -> Any:
    d = env.company.disclosure(a["company"])
    if "save_as" in a:
        env.saved[a["save_as"]] = d["hash"]
    return d


def _set_day(env: Env, a: Op) -> None:
    env.day[0] = a["value"]


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
}


def execute(env: Env, op: Op) -> dict[str, Any]:
    """Führt einen Schritt aus; Rückgabe: {expect: ok|error, result|error: Klasse}."""
    try:
        res = OPS[op["op"]](env, op)
    except (WorldError, RuleViolation) as e:
        return {"expect": "error", "error": type(e).__name__}
    return {"expect": "ok", "result": _jsonable(res)}


def run_script(script: list[Op]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    env = Env()
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
    ("random_world_4", "Zustandsbewusst erzeugtes Zufallsskript (Seed 4, 260 Schritte), ausgeschrieben",
     lambda: random_script(4, 260)),
    ("random_world_9", "Zustandsbewusst erzeugtes Zufallsskript (Seed 9, 260 Schritte), ausgeschrieben",
     lambda: random_script(9, 260)),
]


def run_scenario(name: str, description: str, script: list[Op]) -> dict[str, Any]:
    steps, final = run_script(script)
    return {"name": name, "description": description, "steps": steps, "final": final,
            "final_world_sha256": hashlib.sha256(canonical_bytes(final)).hexdigest()}


def build_vector() -> dict[str, Any]:
    return {"format": FORMAT_VERSION, "name": NAME, "cee_rules_file": CEE_RULES, "cee_rules_sha256": _sha("mmo_cee", CEE_RULES),
            "company_rules_file": COMPANY_RULES, "company_rules_sha256": _sha("mmo_world", COMPANY_RULES),
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
    for sc in vec["scenarios"]:
        steps, final = run_script([strip_result(s) for s in sc["steps"]])
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
        lines.append('{"description":' + _compact(sc["description"]) + ',"final":' + _compact(sc["final"])
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
