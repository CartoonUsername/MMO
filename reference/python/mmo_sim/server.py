"""Begegnungsverwaltung: der Server vergibt IDs, bestimmt Gegner, Stufe und Tag und erzeugt
den Begegnungsbericht aus der Simulation. Der Client liefert ausschließlich Eingabebefehle.

Schließt die in ADR-0003 beschriebene Vertrauensgrenze für den Bericht: Die Berichte der CEE
stammen aus dieser Komponente, nicht von außen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mmo_cee.history import Event
from mmo_cee.service import CharacterService

from .errors import SimError
from .fight import EncounterResult, simulate
from .group import GroupResult, simulate_group
from .pack import PackResult, simulate_pack, strongest
from .rules import MULTI_COMMANDS, skills


@dataclass(frozen=True)
class FinishResult:
    result: EncounterResult
    event: Event | None  # None, wenn die Begegnung keine bewertbaren Aktionen enthielt


@dataclass(frozen=True)
class GroupFinish:
    result: GroupResult
    events: dict[str, Event | None]  # je Teilnehmer; None, wenn er keine bewertbare Aktion hatte


@dataclass(frozen=True)
class PackFinish:
    result: PackResult
    events: dict[str, Event | None]


def build_report(cfg: dict[str, Any], encounter_id: str, opponent_type: str, day: int,
                 result: EncounterResult) -> dict[str, Any]:
    ticks_per_second = cfg["ticks_per_second"]
    duration = max(cfg["report"]["min_duration_s"], -(-result.ticks // ticks_per_second))
    return {
        "encounter_id": encounter_id,
        "opponent_type": opponent_type,
        "opponent_level": cfg["opponents"][opponent_type]["level"],
        "outcome": result.outcome,
        "duration_s": duration,
        "day": day,
        "actions": dict(result.actions),
    }


class EncounterServer:
    def __init__(self, cfg: dict[str, Any], service: CharacterService,
                 day_provider: Callable[[], int], server_id: str = "srv1") -> None:
        self.cfg, self.service, self.day_provider, self.server_id = cfg, service, day_provider, server_id
        self._counter = 0
        self._pending: dict[str, tuple[str, str, int]] = {}  # id -> (Charakter, Gegner, Tag)
        self._groups: dict[str, tuple[tuple[str, ...], str, int]] = {}  # id -> (Teilnehmer, Gegner, Tag)
        self._packs: dict[str, tuple[tuple[str, ...], tuple[str, ...], int]] = {}  # id -> (Teilnehmer, Gegner, Tag)
        self._finished: set[str] = set()

    def start(self, character_id: str, opponent_type: str) -> str:
        if opponent_type not in self.cfg["opponents"]:
            raise SimError(f"unbekannter Gegner: {opponent_type}")
        if self.service.state(character_id).parts["identity"]["kind"] is None:
            raise SimError("Charakter existiert nicht")
        self._counter += 1
        eid = f"{self.server_id}-enc-{self._counter:08d}"
        self._pending[eid] = (character_id, opponent_type, self.day_provider())
        return eid

    def finish(self, character_id: str, encounter_id: str, inputs: Any) -> FinishResult:
        if encounter_id in self._finished:
            raise SimError("Begegnung bereits abgeschlossen")
        entry = self._pending.get(encounter_id)
        if entry is None or entry[0] != character_id:
            raise SimError("Begegnung unbekannt oder gehört einem anderen Charakter")
        _, opponent_type, day = entry
        level = self.service.state(character_id).parts["identity"]["level"]
        allowed = self.service.allowed_commands(character_id)  # Fähigkeiten der Figur (ab Regeln v9), sonst alle Befehle
        equipped = self.service.equipped_abilities(character_id)  # ihre Wirkung legen die Simulationsregeln fest
        result = simulate(self.cfg, opponent_type, level, inputs, allowed, equipped)  # bei ungültigen Eingaben bleibt die Begegnung offen
        del self._pending[encounter_id]
        self._finished.add(encounter_id)
        if not result.actions:
            return FinishResult(result, None)
        report = build_report(self.cfg, encounter_id, opponent_type, day, result)
        event = self.service.record(character_id, "combat.encounter_resolved", report)
        return FinishResult(result, event)

    # -- Gruppenkampf (ADR-0022) -----------------------------------------------------------
    def _group_command_map(self, equipped: list[str] | None) -> set[str]:
        mapping = self.cfg.get("group", {}).get("ability_commands", {})
        return {mapping[a] for a in (equipped or []) if a in mapping}

    def start_group(self, character_ids: Any, opponent_type: str) -> str:
        g = self.cfg.get("group")
        if g is None:
            raise SimError("Diese Regeln kennen keinen Gruppenkampf")
        if opponent_type not in self.cfg["opponents"]:
            raise SimError(f"unbekannter Gegner: {opponent_type}")
        if (not isinstance(character_ids, (list, tuple)) or not 1 <= len(character_ids) <= g["max_party"]
                or len(set(character_ids)) != len(character_ids) or any(not isinstance(c, str) for c in character_ids)):
            raise SimError(f"Die Gruppe muss aus 1..{g['max_party']} verschiedenen Figuren bestehen")
        for c in character_ids:
            if not self.service.log.has(c):
                raise SimError("Charakter existiert nicht")
        self._counter += 1
        eid = f"{self.server_id}-enc-{self._counter:08d}"
        self._groups[eid] = (tuple(character_ids), opponent_type, self.day_provider())
        return eid

    def finish_group(self, encounter_id: str, inputs_by_character: Any) -> GroupFinish:
        """Schließt einen Gruppenkampf ab: jeder Teilnehmer liefert nur seine Eingaben; jeder erhält seinen eigenen Bericht
        (nur eigene Aktionszähler). Alle Berichte werden vorab validiert, damit nicht nur ein Teil aufgezeichnet wird."""
        if encounter_id in self._finished:
            raise SimError("Begegnung bereits abgeschlossen")
        entry = self._groups.get(encounter_id)
        if entry is None:
            raise SimError("Gruppenbegegnung unbekannt")
        party, opponent_type, day = entry
        if not isinstance(inputs_by_character, dict) or set(inputs_by_character) - set(party):
            raise SimError("Eingaben nur von Teilnehmern der Gruppe")
        specs = []
        for c in party:
            equipped = self.service.equipped_abilities(c)
            allowed = self.service.allowed_commands(c)
            if allowed is not None:
                allowed = sorted(set(allowed) | self._group_command_map(equipped))
            spec: dict[str, Any] = {"level": self.service.state(c).parts["identity"]["level"], "inputs": inputs_by_character.get(c, [])}
            if allowed is not None:
                spec["allowed"] = allowed
            if equipped is not None:
                spec["equipped"] = equipped
            specs.append(spec)
        result = simulate_group(self.cfg, opponent_type, specs)  # bei ungültigen Eingaben bleibt die Begegnung offen
        reports = {c: build_report(self.cfg, encounter_id, opponent_type, day, r) for c, r in zip(party, result.players) if r.actions}
        for c, rep in reports.items():
            self.service.projector.validate(self.service.state(c), "combat.encounter_resolved", rep)
        del self._groups[encounter_id]
        self._finished.add(encounter_id)
        events = {c: (self.service.record(c, "combat.encounter_resolved", reports[c]) if c in reports else None) for c in party}
        return GroupFinish(result, events)

    def _skill_command_set(self, equipped: list[str] | None) -> set[str]:
        """Eigene Fähigkeitsbefehle (ADR-0027): nur die der ausgerüsteten Fähigkeiten."""
        return {name for name, sk in skills(self.cfg).items() if sk["ability"] in (equipped or [])}

    # -- Kampf gegen mehrere Gegner (ADR-0026) ---------------------------------------------------
    def start_pack(self, character_ids: Any, opponent_types: Any) -> str:
        m = self.cfg.get("multi")
        if m is None:
            raise SimError("Diese Regeln kennen keinen Kampf gegen mehrere Gegner")
        if (not isinstance(opponent_types, (list, tuple)) or not 1 <= len(opponent_types) <= m["max_opponents"]
                or any(not isinstance(t, str) or t not in self.cfg["opponents"] for t in opponent_types)):
            raise SimError(f"Es müssen 1..{m['max_opponents']} bekannte Gegner sein")
        g = self.cfg["group"]
        if (not isinstance(character_ids, (list, tuple)) or not 1 <= len(character_ids) <= g["max_party"]
                or len(set(character_ids)) != len(character_ids) or any(not isinstance(c, str) for c in character_ids)):
            raise SimError(f"Die Gruppe muss aus 1..{g['max_party']} verschiedenen Figuren bestehen")
        for c in character_ids:
            if not self.service.log.has(c):
                raise SimError("Charakter existiert nicht")
        self._counter += 1
        eid = f"{self.server_id}-enc-{self._counter:08d}"
        self._packs[eid] = (tuple(character_ids), tuple(opponent_types), self.day_provider())
        return eid

    def finish_pack(self, encounter_id: str, inputs_by_character: Any) -> PackFinish:
        """Wie `finish_group`; der Bericht nennt den stärksten Gegner (höchste Stufe, bei Gleichstand der erste) – zusätzliche
        Gegner bringen keine zusätzlichen Punkte (Platzhalter, ADR-0026)."""
        if encounter_id in self._finished:
            raise SimError("Begegnung bereits abgeschlossen")
        entry = self._packs.get(encounter_id)
        if entry is None:
            raise SimError("Mehrgegnerbegegnung unbekannt")
        party, opponents, day = entry
        if not isinstance(inputs_by_character, dict) or set(inputs_by_character) - set(party):
            raise SimError("Eingaben nur von Teilnehmern der Gruppe")
        specs = []
        for c in party:
            equipped = self.service.equipped_abilities(c)
            allowed = self.service.allowed_commands(c)
            if allowed is not None:
                allowed = sorted(set(allowed) | self._group_command_map(equipped) | set(MULTI_COMMANDS) | self._skill_command_set(equipped))
            spec: dict[str, Any] = {"level": self.service.state(c).parts["identity"]["level"], "inputs": inputs_by_character.get(c, [])}
            if allowed is not None:
                spec["allowed"] = allowed
            if equipped is not None:
                spec["equipped"] = equipped
            specs.append(spec)
        result = simulate_pack(self.cfg, list(opponents), specs)
        main = strongest(self.cfg, opponents)
        reports = {c: build_report(self.cfg, encounter_id, main, day, r) for c, r in zip(party, result.players) if r.actions}
        for c, rep in reports.items():
            self.service.projector.validate(self.service.state(c), "combat.encounter_resolved", rep)
        del self._packs[encounter_id]
        self._finished.add(encounter_id)
        events = {c: (self.service.record(c, "combat.encounter_resolved", reports[c]) if c in reports else None) for c in party}
        return PackFinish(result, events)
