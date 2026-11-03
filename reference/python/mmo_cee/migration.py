"""Migration einer Figur zwischen Regelversionen. Siehe ADR-0018 (setzt den Vorschlag aus ADR-0014 um).

Eine Figur wechselt die Regelversion nie still. Der Wechsel ist ein **aufgezeichnetes Ereignis** am Ende ihrer Kette
(`identity.rules_migrated`, aufgezeichnet unter der NEUEN Regelversion). Es enthält:
* `from`/`to`   - alte und neue Regelversion (genau eine Stufe in der Reihe der mitgelieferten Versionen),
* `state_sha256` - Hash des Zustands unmittelbar vor der Migration (kanonisches JSON der Teilzustände),
* `from_rules_sha256`/`to_rules_sha256` - Fingerabdrücke der exakten Regeln.
Beim Abspielen werden alte Ereignisse mit den alten Regeln abgeleitet, der Zustand wird an dieser Stelle in die neue Version
überführt (neue Engines starten mit ihrem Anfangszustand, optionale Schrittfunktionen in `STATE_MIGRATIONS`), danach gilt die
neue Version. Weicht Zustandshash oder Regelfingerabdruck ab, ist die Historie nicht mehr reproduzierbar: `IntegrityError`.
Der Zeitpunkt der Migration ist Sache der Spielserver-Schicht (der Spieler wird nicht schlechter gestellt: alle Teilzustände
bleiben erhalten; eine Migration darf nie Fortschritt entfernen).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from .engine import CharacterState, Projector
from .errors import IntegrityError, RuleViolation, RulesVersionMismatch
from .history import Event
from .rules import Rules

MIGRATION_TYPE = "identity.rules_migrated"
MIGRATION_KEYS = frozenset({"from", "to", "state_sha256", "from_rules_sha256", "to_rules_sha256"})

def _v8_to_v9(parts: dict[str, Any]) -> dict[str, Any]:
    """v9 führt die Kampfausrüstung ein (combat.loadout/loadout_day); bestehender Fortschritt bleibt, die Ausrüstung ist leer."""
    parts["combat"].setdefault("loadout", [])
    parts["combat"].setdefault("loadout_day", 0)
    return parts


# (von, nach) -> Funktion Teilzustände -> Teilzustände (nur bei strukturellen Änderungen; v7 -> v8 braucht keine)
STATE_MIGRATIONS: dict[tuple[str, str], Callable[[dict[str, Any]], dict[str, Any]]] = {("8", "9"): _v8_to_v9}


def parts_hash(parts: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def next_version(versions: list[str], current: str) -> str | None:
    """Nächsthöhere Version in der Reihe der bekannten Versionen (oder None)."""
    higher = sorted((v for v in versions if int(v) > int(current)), key=int)
    return higher[0] if higher else None


def migrate_parts(old: Projector, new: Projector, parts: dict[str, Any], frm: str, to: str) -> dict[str, Any]:
    out = json.loads(json.dumps(parts))  # tiefe Kopie
    step = STATE_MIGRATIONS.get((frm, to))
    if step is not None:
        out = step(out)
    lost = sorted(set(out) - set(new.engines))
    if lost:
        raise RuleViolation(f"Migration würde Teilzustände entfernen: {lost}")
    for name, engine in new.engines.items():
        out.setdefault(name, engine.initial())
    return out


def migration_payload(state: CharacterState, old_rules: Rules, new_rules: Rules) -> dict[str, Any]:
    return {"from": old_rules.version, "to": new_rules.version, "state_sha256": parts_hash(state.parts),
            "from_rules_sha256": old_rules.sha256, "to_rules_sha256": new_rules.sha256}


def check_migration(state: CharacterState, payload: dict[str, Any], old_rules: Rules, new_rules: Rules, versions: list[str]) -> None:
    """Prüft ein Migrationsereignis gegen den Zustand davor; wirft RuleViolation (beim Aufzeichnen) bzw. wird beim Abspielen
    in IntegrityError umgedeutet."""
    if set(payload) != MIGRATION_KEYS:
        raise RuleViolation(f"Ungültige Felder (erwartet: {sorted(MIGRATION_KEYS)})")
    if payload["from"] != state.rules_version or payload["from"] != old_rules.version:
        raise RuleViolation("Migration beginnt nicht bei der aktuellen Regelversion der Figur")
    if payload["to"] != new_rules.version or next_version(versions, payload["from"]) != payload["to"]:
        raise RuleViolation("Migration muss genau eine Stufe in der Reihe der Regelversionen weitergehen")
    if payload["from_rules_sha256"] != old_rules.sha256 or payload["to_rules_sha256"] != new_rules.sha256:
        raise RuleViolation("Regelfingerabdruck stimmt nicht")
    if payload["state_sha256"] != parts_hash(state.parts):
        raise RuleViolation("Zustandshash stimmt nicht")


class RulesChain:
    """Projectoren aller bekannten Regelversionen; spielt Historien mit Migrationsereignissen ab."""

    def __init__(self, projectors: dict[str, Projector], current: str) -> None:
        self.projectors = dict(sorted(projectors.items(), key=lambda kv: int(kv[0])))
        self.versions, self.current = list(self.projectors), current

    def replay(self, character_id: str, events: list[Event]) -> CharacterState:
        if not events:
            return self.projectors[self.current].new_state(character_id)
        if events[0].rules_version not in self.projectors:
            raise RulesVersionMismatch(
                f"Ereignis seq=0 von {character_id} wurde unter Regelversion {events[0].rules_version} aufgezeichnet, "
                f"bekannt sind {self.versions}")
        proj = self.projectors[events[0].rules_version]
        state = proj.new_state(character_id)
        for e in events:
            if e.type == MIGRATION_TYPE:
                if state.parts["identity"]["kind"] is None:
                    raise IntegrityError(f"Migration von {character_id} vor der Erstellung (seq={e.seq})")
                new = self.projectors.get(e.rules_version)
                if new is None:
                    raise RulesVersionMismatch(f"Migration von {character_id} (seq={e.seq}) auf unbekannte Regelversion {e.rules_version}")
                try:
                    check_migration(state, e.payload, proj.rules, new.rules, self.versions)
                except RuleViolation as err:
                    raise IntegrityError(f"Migration von {character_id} bei seq={e.seq} nicht reproduzierbar: {err}") from err
                if e.rules_version != e.payload["to"]:
                    raise IntegrityError(f"Migration von {character_id} bei seq={e.seq}: Ereignis-Regelversion weicht ab")
                state = CharacterState(character_id, new.rules.version,
                                       migrate_parts(proj, new, state.parts, proj.rules.version, new.rules.version))
                proj = new
                continue
            if e.rules_version != proj.rules.version:
                raise RulesVersionMismatch(
                    f"Ereignis seq={e.seq} von {character_id} wurde unter Regelversion {e.rules_version} aufgezeichnet, "
                    f"geladen ist {proj.rules.version} (ohne aufgezeichnete Migration)")
            proj.apply(state, e)
        return state
