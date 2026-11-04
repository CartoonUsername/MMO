"""Persistenz der Welt: Snapshot-Umschlag, Prüfung beim Laden, Format-Migration, Speicher mit Generationen. Siehe ADR-0014.

Prinzipien (Vorschlag, nicht bestätigt):
* Die Historien der Figuren (Hash-Ketten) sind die Wahrheit über Charaktere. Inventar und Register haben kein Log; sie
  werden als Snapshot gespeichert und beim Laden gegen die Historien gegengeprüft (Zustands-Hashes, Konsistenz).
* Ein Speicherpunkt ist atomar: Logs und Snapshot gehören zu einer Generation; erst der Zeiger `CURRENT` macht sie gültig.
* Laden vertraut nichts: Format, Regel-Hashes, Ketten, Zustands-Hashes, Register-Invarianten und Querbezüge werden geprüft.
  Abweichung = `PersistenceError`, nie stilles Weiterarbeiten mit verfälschtem Zustand.
* Der Snapshot-Umschlag ist versioniert; ältere Formate werden schrittweise durch registrierte Migrationen angehoben.
* Eine Änderung der Regelversion ist keine stille Migration: Laden unter anderen Regeldateien wird abgelehnt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from importlib import resources
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote

from mmo_cee.errors import CEEError
from mmo_cee.history import Event, _canonical as canonical_bytes
from mmo_cee.rules import load_rules

from .company import CompanyRegistry
from .discovery import DiscoveryRegistry
from .errors import WorldError
from .inventory import Inventory
from .world import MARKET_RULES, PARTY_RULES, PRICING_RULES, PRODUCTION_RULES, TRADE_RULES, World

SNAPSHOT_FORMAT = 1
KIND = "mmo_world_snapshot"
Envelope = dict[str, Any]
Logs = dict[str, list[dict[str, Any]]]


class PersistenceError(Exception):
    """Gespeicherter Zustand ist unbrauchbar oder verfälscht – es wurde nichts geladen."""


def _sha(data: Any) -> str:
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def _file_sha(pkg: str, name: str) -> str:
    return hashlib.sha256(resources.files(pkg).joinpath("data", name).read_bytes()).hexdigest()


# ---------------------------------------------------------------- Export ------------------
def export_world(world: World) -> tuple[Envelope, Logs]:
    """Umschlag (Snapshot + Verweise auf die Logs) und die Logs je Figur (Ereignisse als JSON-Zeilen)."""
    snap = world.snapshot()
    logs: Logs = {}
    heads: dict[str, dict[str, Any]] = {}
    for cid in world.svc.log.character_ids():
        evs = world.svc.log.events(cid)
        logs[cid] = [{**e.body(), "hash": e.hash} for e in evs]
        heads[cid] = {"length": len(evs), "head": evs[-1].hash}
    env: Envelope = {
        "format": SNAPSHOT_FORMAT, "kind": KIND, "server_id": world.server_id, "saved_day": world.day[0],
        "rules": {"cee_file": world.cee_rules_file, "cee_sha256": _file_sha("mmo_cee", world.cee_rules_file),
                  "company_file": world.company_rules_file, "company_sha256": _file_sha("mmo_world", world.company_rules_file),
                  "market_file": MARKET_RULES, "market_sha256": _file_sha("mmo_world", MARKET_RULES),
                  "production_file": PRODUCTION_RULES, "production_sha256": _file_sha("mmo_world", PRODUCTION_RULES),
                  "trade_file": TRADE_RULES, "trade_sha256": _file_sha("mmo_world", TRADE_RULES),
                  "party_file": PARTY_RULES, "party_sha256": _file_sha("mmo_world", PARTY_RULES),
                  "pricing_file": PRICING_RULES if world.pricing is not None else None,
                  "pricing_sha256": _file_sha("mmo_world", PRICING_RULES) if world.pricing is not None else None},
        "world": snap, "world_sha256": _sha(snap), "log_heads": heads,
    }
    if world.outbox.active:  # Postfächer sind abgeleitet und nicht Teil des Weltzustands, werden aber mit gesichert
        boxes = json.loads(world.outbox.to_json())
        env["outbox"], env["outbox_sha256"] = boxes, _sha(boxes)
    return env, logs


# ---------------------------------------------------------------- Migration ---------------
MIGRATIONS: dict[int, Callable[[Envelope], Envelope]] = {}
"""Schritt n -> n+1 für Umschläge älterer Formate. Jede Migration ist eine reine Funktion auf dem Umschlag, setzt das
Feld `format` selbst und muss den Weltzustand (`world`, `world_sha256`) konsistent mitführen."""


def migrate_envelope(env: Envelope) -> Envelope:
    if not isinstance(env, dict) or env.get("kind") != KIND or not isinstance(env.get("format"), int):
        raise PersistenceError("Kein Weltsnapshot")
    out = json.loads(json.dumps(env))
    while out["format"] < SNAPSHOT_FORMAT:
        step = MIGRATIONS.get(out["format"])
        if step is None:
            raise PersistenceError(f"Keine Migration von Format {out['format']} bekannt")
        before = out["format"]
        out = step(out)
        if out.get("format") != before + 1:
            raise PersistenceError(f"Migration von Format {before} setzte das Format nicht auf {before + 1}")
    if out["format"] > SNAPSHOT_FORMAT:
        raise PersistenceError(f"Snapshot-Format {out['format']} ist neuer als dieser Server ({SNAPSHOT_FORMAT})")
    return out


# ---------------------------------------------------------------- Konsistenz --------------
def check_consistency(world: World) -> list[str]:
    """Querbezüge zwischen den Schichten; leere Liste = konsistent. (Register == CEE, Entdeckungen, Anteile.)"""
    errs: list[str] = []
    reg, svc = world.company_registry, world.svc
    for cid, comp_id in sorted(reg.employer.items()):
        c = reg.companies.get(comp_id)
        if c is None or cid not in c["employees"]:
            errs.append(f"{cid}: Register-Eintrag ohne Anstellung in {comp_id}")
            continue
        career = svc.state(cid).parts["economy"]["career"]
        if career.get("company_id") != comp_id:
            errs.append(f"{cid}: Register sagt {comp_id}, CEE sagt {career.get('company_id')}")
    for comp_id, c in sorted(reg.companies.items()):
        for cid in sorted(c["employees"]):
            if reg.employer.get(cid) != comp_id:
                errs.append(f"{cid}: Mitarbeiter von {comp_id} ohne Eintrag im Arbeitgeberindex")
        if c["ceo"] is not None and svc.state(c["ceo"]).parts["economy"]["career"].get("role") != "executive":
            errs.append(f"{comp_id}: Geschäftsführer {c['ceo']} ist in der CEE nicht 'executive'")
        founded = svc.state(c["founder"]).parts["economy"]["founded"].get(comp_id)
        if founded is None or founded["open"] != c["open"]:
            errs.append(f"{comp_id}: Gründungsstatus weicht von der CEE des Gründers ab")
    errs += [f"Markt: {m}" for m in world.exchange.check()]
    errs += [f"Gruppen: {m}" for m in world.parties.check()]
    errs += [f"Angebote: {m}" for m in world.offers.check()]
    errs += [f"Produktion: {m}" for m in world.production.check()]
    if world.pricing is not None:
        errs += [f"Preise: {m}" for m in world.pricing.check()]
    dreg = world.discovery_registry
    for did, rec in sorted(dreg.records.items()):
        for cid in sorted(rec["holders"]):
            if did not in svc.known_discoveries(cid):
                errs.append(f"{cid}: Register nennt Entdeckung {did}, die CEE kennt sie nicht")
    return errs


# ---------------------------------------------------------------- Import ------------------
def import_world(envelope: Envelope, logs: Logs) -> World:
    """Baut eine Welt aus Umschlag und Logs und prüft alles. Wirft `PersistenceError`; es entsteht nie eine halbe Welt."""
    try:
        return _import(envelope, logs)
    except PersistenceError:
        raise
    except (CEEError, WorldError, KeyError, TypeError, ValueError, AttributeError, OSError) as e:
        raise PersistenceError(f"Snapshot unbrauchbar: {type(e).__name__}: {e}") from e


def _import(envelope: Envelope, logs: Logs) -> World:
    env = migrate_envelope(envelope)
    rules = env["rules"]
    names = [rules["cee_file"], rules["company_file"], rules["market_file"], rules["production_file"], rules["trade_file"], rules["party_file"]]
    if rules["pricing_file"] is not None:
        names.append(rules["pricing_file"])
    for name in names:  # nur schlichte Dateinamen aus dem Paket, nie Pfade
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+\.json", name):
            raise PersistenceError("Ungültiger Regeldateiname")
    if _file_sha("mmo_cee", rules["cee_file"]) != rules["cee_sha256"]:
        raise PersistenceError("CEE-Regeldatei hat sich seit dem Speichern geändert (Regel-Migration ist eine bewusste Aktion)")
    if _file_sha("mmo_world", rules["company_file"]) != rules["company_sha256"]:
        raise PersistenceError("Firmenregeln haben sich seit dem Speichern geändert")
    if rules["market_file"] != MARKET_RULES or _file_sha("mmo_world", rules["market_file"]) != rules["market_sha256"]:
        raise PersistenceError("Marktregeln haben sich seit dem Speichern geändert")
    if (rules["pricing_file"], rules["pricing_sha256"]) != (None, None) and (
            rules["pricing_file"] != PRICING_RULES or _file_sha("mmo_world", rules["pricing_file"]) != rules["pricing_sha256"]):
        raise PersistenceError("Preisregeln haben sich seit dem Speichern geändert")
    if rules["party_file"] != PARTY_RULES or _file_sha("mmo_world", rules["party_file"]) != rules["party_sha256"]:
        raise PersistenceError("Gruppenregeln haben sich seit dem Speichern geändert")
    if rules["trade_file"] != TRADE_RULES or _file_sha("mmo_world", rules["trade_file"]) != rules["trade_sha256"]:
        raise PersistenceError("Handelsregeln haben sich seit dem Speichern geändert")
    if rules["production_file"] != PRODUCTION_RULES or _file_sha("mmo_world", rules["production_file"]) != rules["production_sha256"]:
        raise PersistenceError("Produktionsregeln haben sich seit dem Speichern geändert")
    if _sha(env["world"]) != env["world_sha256"]:
        raise PersistenceError("Weltzustand passt nicht zu seinem Hash")
    heads = env["log_heads"]
    if set(logs) != set(heads):
        raise PersistenceError("Logs und Snapshot nennen verschiedene Figuren")
    world = World(rules["cee_file"], rules["company_file"], env["server_id"])
    for cid in sorted(heads):
        rows = logs[cid]
        if len(rows) != heads[cid]["length"] or not rows or rows[-1]["hash"] != heads[cid]["head"]:
            raise PersistenceError(f"Log von {cid} passt nicht zum Snapshot (Länge/Kopf) – Speicherpunkt unvollständig?")
        events = [Event(**row) for row in rows]
        if any(e.character_id != cid for e in events):
            raise PersistenceError(f"Log von {cid} enthält fremde Ereignisse")
        world.svc.log.adopt(cid, events)  # prüft Hash-Kette
    if (world.pricing is not None) != (rules["pricing_file"] is not None):
        raise PersistenceError("Preisregeln passen nicht zu den CEE-Regeln")
    world.day[0] = env["saved_day"]
    if "outbox" in env:
        if _sha(env["outbox"]) != env.get("outbox_sha256"):
            raise PersistenceError("Postfächer passen nicht zu ihrem Hash")
        world.outbox.load(json.dumps(env["outbox"]))
    snap = env["world"]
    world.inv = Inventory.from_json(json.dumps(snap["inventory"]))
    world.discovery_registry = DiscoveryRegistry.from_json(world.svc.rules, json.dumps(snap["discovery"]))
    world.company_registry = CompanyRegistry.from_json(world.company_rules, json.dumps(snap["companies"]))
    world._wire(lambda: world.day[0])
    world.trading._counter, world.crafting._counter = snap["counters"]["trade"], snap["counters"]["craft"]
    if "exchange" in snap:
        world.exchange.load(json.dumps(snap["exchange"]))
    if "parties" in snap:
        world.parties.load(json.dumps(snap["parties"]))
    if "trade_offers" in snap:
        world.offers.load(json.dumps(snap["trade_offers"]))
    if "production" in snap:
        world.production.load(json.dumps(snap["production"]))
    if "pricing" in snap:
        if world.pricing is None:
            raise PersistenceError("Preisdaten ohne Preisdynamik in den Regeln")
        world.pricing.load(json.dumps(snap["pricing"]))
    if world.snapshot() != snap:  # Zustands-Hashes der Figuren aus den Historien + alle Register gegen den Snapshot
        raise PersistenceError("Aus den Historien abgeleiteter Zustand weicht vom Snapshot ab")
    problems = check_consistency(world)
    if problems:
        raise PersistenceError("Inkonsistenter Weltzustand: " + "; ".join(problems))
    return world


# ---------------------------------------------------------------- Regelversion ---------
def upgrade_world(world: World, target_cee_file: str, characters: list[str] | None = None) -> World:
    """Hebt die Welt auf eine höhere CEE-Regelversion (ADR-0018): lädt dieselben Historien unter den neuen Regeln
    (alte Ereignisse werden mit den alten Regeln abgeleitet) und zeichnet für die genannten Figuren (Standard: alle) die
    Migrationsereignisse auf. Nicht migrierte Figuren bleiben spielbar zurück, dürfen aber an keiner Weltaktion teilnehmen,
    bis auch sie migriert sind. Die übergebene Welt bleibt unverändert; bei jedem Fehler entsteht keine neue Welt."""
    if not isinstance(target_cee_file, str) or not re.fullmatch(r"[A-Za-z0-9_]+\.json", target_cee_file):
        raise PersistenceError("Ungültiger Regeldateiname")
    try:
        target = load_rules(target_cee_file)
    except (OSError, ValueError, KeyError) as e:
        raise PersistenceError(f"Regeldatei {target_cee_file!r} nicht ladbar") from e
    if int(target.version) <= int(world.svc.rules.version):
        raise PersistenceError("Die Zielversion muss höher sein als die aktuelle Regelversion")
    env, logs = export_world(world)
    env = json.loads(json.dumps(env))
    env["rules"]["cee_file"], env["rules"]["cee_sha256"] = target_cee_file, _file_sha("mmo_cee", target_cee_file)
    has_pricing = "dynamic_reference" in target["economy"]
    env["rules"]["pricing_file"] = PRICING_RULES if has_pricing else None
    env["rules"]["pricing_sha256"] = _file_sha("mmo_world", PRICING_RULES) if has_pricing else None
    new = import_world(env, json.loads(json.dumps(logs)))
    try:
        for cid in sorted(new.svc.log.character_ids()) if characters is None else characters:
            while new.svc.needs_migration(cid):
                new.svc.migrate(cid)
    except (CEEError, WorldError, KeyError) as e:
        raise PersistenceError(f"Migration fehlgeschlagen: {type(e).__name__}: {e}") from e
    problems = check_consistency(new)
    if problems:
        raise PersistenceError("Inkonsistenter Weltzustand nach der Migration: " + "; ".join(problems))
    return new


# ---------------------------------------------------------------- Speicher ----------------
class Store:
    """Verzeichnis mit Generationen: `gen-000001/{snapshot.json, logs/<id>.jsonl}` und Zeiger `CURRENT`.

    `commit` schreibt eine neue Generation vollständig und schaltet erst danach den Zeiger um (atomarer Austausch);
    ein Absturz davor lässt die letzte gültige Generation unberührt. Produktiv entspricht das einer Datenbanktransaktion,
    die Logs, Inventar und Register gemeinsam schreibt."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _gen_dir(self, n: int) -> Path:
        return self.path / f"gen-{n:06d}"

    def generations(self) -> list[int]:
        if not self.path.exists():
            return []
        return sorted(int(p.name[4:]) for p in self.path.iterdir() if p.is_dir() and p.name.startswith("gen-") and p.name[4:].isdigit())

    def current(self) -> int | None:
        ptr = self.path / "CURRENT"
        if not ptr.exists():
            return None
        try:
            data = json.loads(ptr.read_text(encoding="utf-8"))
            return int(data["generation"])
        except (ValueError, KeyError, TypeError) as e:
            raise PersistenceError("CURRENT ist unlesbar") from e

    def commit(self, world: World) -> int:
        env, logs = export_world(world)
        self.path.mkdir(parents=True, exist_ok=True)
        gens = self.generations()
        n = (gens[-1] if gens else 0) + 1
        tmp = self.path / f".tmp-gen-{n:06d}"
        if tmp.exists():
            shutil.rmtree(tmp)
        (tmp / "logs").mkdir(parents=True)
        for cid, rows in logs.items():
            lines = "".join(canonical_bytes(r).decode() + "\n" for r in rows)
            (tmp / "logs" / (quote(cid, safe="") + ".jsonl")).write_text(lines, encoding="utf-8", newline="\n")
        snap_bytes = canonical_bytes(env)
        (tmp / "snapshot.json").write_bytes(snap_bytes)
        os.replace(tmp, self._gen_dir(n))
        ptr = canonical_bytes({"generation": n, "snapshot_sha256": hashlib.sha256(snap_bytes).hexdigest()})
        ptr_tmp = self.path / "CURRENT.tmp"
        ptr_tmp.write_bytes(ptr)
        os.replace(ptr_tmp, self.path / "CURRENT")
        return n

    def load(self, generation: int | None = None) -> World:
        gen = generation if generation is not None else self.current()
        if gen is None:
            raise PersistenceError("Kein Speicherpunkt vorhanden")
        d = self._gen_dir(gen)
        if not (d / "snapshot.json").exists():
            raise PersistenceError(f"Generation {gen} fehlt")
        snap_bytes = (d / "snapshot.json").read_bytes()
        if generation is None:  # der Zeiger bürgt für den Inhalt der aktuellen Generation
            ptr = json.loads((self.path / "CURRENT").read_text(encoding="utf-8"))
            if ptr.get("snapshot_sha256") != hashlib.sha256(snap_bytes).hexdigest():
                raise PersistenceError("snapshot.json passt nicht zu CURRENT (verfälscht oder unvollständig)")
        try:
            envelope = json.loads(snap_bytes)
            logs: Logs = {}
            for f in sorted((d / "logs").glob("*.jsonl")):
                logs[unquote(f.stem)] = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line]
        except ValueError as e:
            raise PersistenceError(f"Speicherpunkt nicht lesbar: {e}") from e
        return import_world(envelope, logs)

    def load_latest_valid(self) -> tuple[int, World]:
        """Sucht rückwärts die jüngste Generation, die alle Prüfungen besteht (Wiederherstellung nach Defekt)."""
        for n in reversed(self.generations()):
            try:
                return n, self.load(n)
            except PersistenceError:
                continue
        raise PersistenceError("Keine gültige Generation gefunden")

    def prune(self, keep: int) -> list[int]:
        gens = self.generations()
        removed = gens[:-keep] if keep > 0 else gens
        cur = self.current()
        for n in removed:
            if n != cur:
                shutil.rmtree(self._gen_dir(n))
        return [n for n in removed if n != cur]
