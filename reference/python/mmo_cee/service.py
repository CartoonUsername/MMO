"""CharacterService: validiert, zeichnet auf, projiziert. Gleiche Pipeline für Spieler und NPCs."""
from __future__ import annotations

from typing import Any

from .combat import CombatEngine, ability_progress, allowed_commands, loadout_slots, reached_directions, unlocked_abilities
from .discovery import DiscoveryEngine, discovery_progress, known_discoveries
from .crafting import CraftingEngine, craft_directions, craft_profile, known_recipes, known_techniques
from .economy import EconomyEngine, economic_directions, economic_profile
from .elements import ElementEngine
from .engine import CharacterState, Projector
from .essence import EssenceEngine, eligible_forms, essence_profile, form_scores
from .errors import RuleViolation
from .history import Event, EventLog
from .identity import IdentityEngine
from .migration import MIGRATION_TYPE, RulesChain, check_migration, migrate_parts, migration_payload, next_version
from .professions import ProfessionEngine
from .rules import Rules, load_rules, older_rules
from .visual import VisualEvolution


def default_projector(rules: Rules) -> Projector:
    engines = [IdentityEngine(rules), ElementEngine(rules), ProfessionEngine(rules), EssenceEngine(rules)]
    if "combat" in rules:  # rules_v1 kennt keine Kampfentwicklung
        engines.append(CombatEngine(rules))
    if "discovery" in rules:  # ab rules_v5
        engines.append(DiscoveryEngine(rules))
    if "crafting" in rules:  # ab rules_v6
        engines.append(CraftingEngine(rules))
    if "economy" in rules:  # ab rules_v7
        engines.append(EconomyEngine(rules))
    return Projector(engines, rules)


class CharacterService:
    def __init__(self, rules: Rules | None = None, log: EventLog | None = None,
                 history_rules: dict[str, Rules] | None = None) -> None:
        """`rules` gelten für neue Ereignisse; `history_rules` (Version -> Regeln) erlauben das Abspielen älterer
        Historien samt aufgezeichneter Migration (ADR-0018). Ohne sie verweigert das Abspielen fremde Regelversionen."""
        self.rules = rules or load_rules()
        self.log = log or EventLog()
        self.projector = default_projector(self.rules)
        self.rules_by_version: dict[str, Rules] = {**(history_rules or {}), self.rules.version: self.rules}
        self.chain = RulesChain({v: (self.projector if v == self.rules.version else default_projector(r))
                                 for v, r in self.rules_by_version.items()}, self.rules.version)
        self._states: dict[str, CharacterState] = {}
        self._visual_by_version: dict[str, VisualEvolution] = {}

    def create(self, character_id: str, kind: str) -> CharacterState:
        return self._record(character_id, "identity.created", {"kind": kind})[1]

    def record(self, character_id: str, type: str, payload: dict[str, Any]) -> Event:
        return self._record(character_id, type, payload)[0]

    def _record(self, character_id: str, type: str, payload: dict[str, Any]) -> tuple[Event, CharacterState]:
        if type == MIGRATION_TYPE:
            raise RuleViolation("Regelversionswechsel nur über migrate()")
        state = self.state(character_id)
        self.projector.validate(state, type, payload)
        event = self.log.append(character_id, type, payload, self.rules.version)
        self.projector.apply(state, event)
        return event, state

    def state(self, character_id: str) -> CharacterState:
        if character_id not in self._states:
            self.log.verify(character_id)
            self._states[character_id] = self.chain.replay(character_id, self.log.events(character_id))
        return self._states[character_id]

    # -- Regelversionswechsel (ADR-0018) -------------------------------------------------------
    def rules_of(self, character_id: str) -> Rules:
        """Regeln, unter denen der Zustand der Figur gerade abgeleitet ist (bei nicht migrierten Figuren die ältere Version)."""
        return self.rules_by_version[self.state(character_id).rules_version]

    def needs_migration(self, character_id: str) -> bool:
        return self.log.has(character_id) and self.state(character_id).rules_version != self.rules.version

    def migrate(self, character_id: str) -> Event:
        """Hebt eine Figur um genau eine Regelversion an (aufgezeichnetes Ereignis). Mehrfach aufrufen, bis `needs_migration`
        falsch ist. Bestehender Fortschritt bleibt vollständig erhalten."""
        if not self.log.has(character_id):
            raise RuleViolation("Charakter wurde noch nicht erstellt")
        state = self.state(character_id)
        old = self.rules_by_version[state.rules_version]
        target = next_version(list(self.rules_by_version), state.rules_version)
        if target is None:
            raise RuleViolation("Figur läuft bereits unter der neuesten bekannten Regelversion")
        new = self.rules_by_version[target]
        payload = migration_payload(state, old, new)
        check_migration(state, payload, old, new, list(self.rules_by_version))
        old_proj, new_proj = self.chain.projectors[old.version], self.chain.projectors[new.version]
        parts = migrate_parts(old_proj, new_proj, state.parts, old.version, new.version)  # kann ablehnen, vor dem Schreiben
        event = self.log.append(character_id, MIGRATION_TYPE, payload, new.version)
        self._states[character_id] = CharacterState(character_id, new.version, parts)
        return event

    def rebuild(self, character_id: str) -> CharacterState:
        """Verifiziert die Kette und leitet den Zustand frisch aus der Historie ab."""
        self._states.pop(character_id, None)
        return self.state(character_id)

    def eligible_essences(self, character_id: str) -> list[str]:
        return eligible_forms(self.state(character_id), self.rules_of(character_id))

    def combat_directions(self, character_id: str) -> dict[str, int]:
        """Erreichte Entwicklungsrichtungen -> Stufe (mehrere gleichzeitig möglich)."""
        return reached_directions(self.state(character_id), self.rules_of(character_id))

    def abilities(self, character_id: str) -> dict:
        """Fähigkeiten mit Stand: fehlende Voraussetzungen, Befehl, ausgerüstet (nur ab Regeln v9, sonst leer)."""
        rules = self.rules_of(character_id)
        return ability_progress(self.state(character_id), rules) if "abilities" in rules["combat"] else {}

    def unlocked_abilities(self, character_id: str) -> list[str]:
        rules = self.rules_of(character_id)
        return unlocked_abilities(self.state(character_id), rules) if "abilities" in rules["combat"] else []

    def loadout_slots(self, character_id: str) -> int:
        rules = self.rules_of(character_id)
        return loadout_slots(self.state(character_id), rules) if "abilities" in rules["combat"] else 0

    def equipped_abilities(self, character_id: str) -> list[str] | None:
        """Ausgerüstete Fähigkeiten; None, wenn die Regeln der Figur keine Fähigkeiten kennen."""
        rules = self.rules_of(character_id)
        return list(self.state(character_id).parts["combat"]["loadout"]) if "abilities" in rules["combat"] else None

    def allowed_commands(self, character_id: str) -> list[str] | None:
        """Simulationsbefehle der Figur; None, wenn ihre Regeln keine Fähigkeiten kennen (dann gilt jeder Befehl)."""
        rules = self.rules_of(character_id)
        return allowed_commands(self.state(character_id), rules) if "abilities" in rules["combat"] else None

    def essence_scores(self, character_id: str) -> dict[str, dict]:
        """Punktzahl/Beiträge/Prüfbarkeit der Bewertungsformen (leer bei Regeln ohne Bewertungsformen)."""
        return form_scores(self.state(character_id), self.rules_of(character_id))

    def essence_profile(self, character_id: str) -> dict:
        """Vor-/Nachteile der angenommenen Wesensform."""
        return essence_profile(self.state(character_id), self.rules_of(character_id))

    def appearance(self, character_id: str) -> dict:
        """Erscheinungsparameter (Visual Evolution): reine, serverseitige Ableitung aus dem Zustand."""
        rules = self.rules_of(character_id)
        if rules.version not in self._visual_by_version:
            self._visual_by_version[rules.version] = VisualEvolution(rules)
        return self._visual_by_version[rules.version].appearance(self.state(character_id))

    def known_discoveries(self, character_id: str) -> list[str]:
        return known_discoveries(self.state(character_id))

    def discovery_progress(self, character_id: str, discovery_id: str) -> dict:
        """Beweise, fehlende Voraussetzungen und Abschlussbereitschaft einer Entdeckung."""
        return discovery_progress(self.state(character_id), self.rules_of(character_id), discovery_id)

    def known_recipes(self, character_id: str) -> list[str]:
        return known_recipes(self.state(character_id), self.rules_of(character_id))

    def known_techniques(self, character_id: str) -> list[str]:
        return known_techniques(self.state(character_id), self.rules_of(character_id))

    def craft_directions(self, character_id: str) -> dict[str, int]:
        """Handwerks-Spezialisierungen -> Stufe (mehrere gleichzeitig möglich)."""
        return craft_directions(self.state(character_id), self.rules_of(character_id))

    def craft_profile(self, character_id: str) -> dict[str, int]:
        return craft_profile(self.state(character_id), self.rules_of(character_id))

    def economic_directions(self, character_id: str) -> dict[str, int]:
        """Handelsrichtungen -> Stufe (mehrere gleichzeitig möglich)."""
        return economic_directions(self.state(character_id), self.rules_of(character_id))

    def layers(self, character_id: str) -> dict:
        """Drei Schichten: Lebensgeschichte, aktuelles Profil, Wesenidentität (reine Ableitung, ADR-0040)."""
        from .layers import layers
        return layers(self.log.events(character_id), self.state(character_id), self.rules_of(character_id))

    def economic_profile(self, character_id: str) -> dict:
        """Laufbahn, Unternehmen, Netzwerkgröße, Anzahl Handel."""
        return economic_profile(self.state(character_id), self.rules_of(character_id))
