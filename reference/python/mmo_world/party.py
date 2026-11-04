"""Gruppenbildung: Gruppen, Einladungen, Anführer, Beuteverteilung. Siehe ADR-0025.

* Eine Gruppe hat einen Anführer und bis zu `max_size` Mitglieder; jede Figur ist in höchstens einer Gruppe.
* Einladen darf nur der Anführer; die Eingeladene nimmt an oder lehnt ab, Einladungen verfallen nach `invite_days`.
  Ein vorläufiger Stufenabstand (`max_level_gap`) begrenzt, wen eine Gruppe aufnehmen kann (Vorschlag gegen Boosting).
* Verlässt der Anführer die Gruppe, geht die Führung an das dienstälteste Mitglied; bleibt nur eine Figur übrig, löst sich
  die Gruppe auf.
* Beute (serverintern, `distribute_loot`): nur Teilnehmer, die im Kampf beigetragen haben, sind berechtigt (kein Mitlaufen ohne
  Beitrag). Verteilung nach Modus: `round_robin` (reihum, Zeiger bleibt gespeichert), `leader` (alles an den Anführer),
  `finder` (alles an den genannten Finder). Die Gegenstände entstehen serverintern (`Inventory.deposit`).
* Der Weltdienst benachrichtigt Betroffene (ADR-0024). Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable

from mmo_cee.service import CharacterService

from .errors import WorldError
from .inventory import Inventory
from .market import TradeService


def load_party_rules(name: str = "party_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_party_rules(pr: dict[str, Any], cee_rules: Any) -> None:
    if int(cee_rules.version) < pr["requires_cee_rules_min"]:
        raise WorldError(f"party_rules benötigen CEE-Regeln >= v{pr['requires_cee_rules_min']}")
    for k in ("max_size", "invite_days", "max_pending_invites_per_target"):
        if not _is_int(pr[k]) or pr[k] < 1:
            raise WorldError(f"{k} muss >= 1 sein")
    if pr["max_size"] < 2 or not _is_int(pr["max_level_gap"]) or pr["max_level_gap"] < 0:
        raise WorldError("max_size >= 2 und max_level_gap >= 0 erforderlich")
    modes = pr["loot_modes"]
    if not modes or len(set(modes)) != len(modes) or pr["default_loot_mode"] not in modes or set(modes) - {"round_robin", "leader", "finder"}:
        raise WorldError("loot_modes ungültig")


class PartyService:
    def __init__(self, service: CharacterService, inventory: Inventory, trading: TradeService, rules: dict[str, Any],
                 day_provider: Callable[[], int], server_id: str = "srv1") -> None:
        validate_party_rules(rules, service.rules)
        self.cee, self.inv, self.trading, self.pr, self.day, self.server_id = service, inventory, trading, rules, day_provider, server_id
        self.notify: Callable[[str, str, dict[str, Any]], None] = lambda recipient, kind, data: None
        self.parties: dict[str, dict[str, Any]] = {}
        self.invites: dict[str, dict[str, Any]] = {}
        self.member_of: dict[str, str] = {}
        self._counters = {"party": 0, "invite": 0}

    @property
    def active(self) -> bool:
        return self._counters["party"] > 0

    # -- Hilfen ------------------------------------------------------------------------------
    def _known(self, character_id: Any) -> str:
        if not isinstance(character_id, str) or not self.cee.log.has(character_id):
            raise WorldError("Unbekannte Figur")
        return character_id

    def _party_of(self, character_id: str) -> dict[str, Any]:
        pid = self.member_of.get(character_id)
        if pid is None:
            raise WorldError("Figur ist in keiner Gruppe")
        return self.parties[pid]

    def _leader(self, actor: str) -> dict[str, Any]:
        p = self._party_of(actor)
        if p["leader"] != actor:
            raise WorldError("Nur der Anführer darf das")
        return p

    def level_of(self, character_id: str) -> int:
        return self.cee.state(character_id).parts["identity"]["level"]

    def view(self, character_id: str) -> dict[str, Any] | None:
        self._known(character_id)
        pid = self.member_of.get(character_id)
        if pid is None:
            return None
        p = self.parties[pid]
        return {"id": pid, "leader": p["leader"], "members": list(p["members"]), "loot": p["loot"]}

    def incoming(self, character_id: str) -> list[dict[str, Any]]:
        self._known(character_id)
        return [dict(i) for _, i in sorted(self.invites.items()) if i["to"] == character_id]

    def _members_notify(self, p: dict[str, Any], kind: str, data: dict[str, Any], skip: str | None = None) -> None:
        for m in p["members"]:
            if m != skip:
                self.notify(m, kind, data)

    def _drop_party(self, p: dict[str, Any]) -> None:
        for m in p["members"]:
            del self.member_of[m]
        for iid in [k for k, i in self.invites.items() if i["party"] == p["id"]]:
            del self.invites[iid]
        del self.parties[p["id"]]

    # -- Gruppe und Einladungen ------------------------------------------------------------------
    def create(self, leader: str) -> str:
        self.day()
        self._known(leader)
        if leader in self.member_of:
            raise WorldError("Figur ist bereits in einer Gruppe")
        self._counters["party"] += 1
        pid = f"{self.server_id}-party-{self._counters['party']:08d}"
        self.parties[pid] = {"id": pid, "leader": leader, "members": [leader], "loot": self.pr["default_loot_mode"], "rr": 0,
                             "day": self.day()}
        self.member_of[leader] = pid
        return pid

    def invite(self, actor: str, target: str) -> str:
        today = self.day()
        p = self._leader(actor)
        self._known(target)
        if target in self.member_of:
            raise WorldError("Die Figur ist bereits in einer Gruppe")
        if len(p["members"]) >= self.pr["max_size"]:
            raise WorldError("Die Gruppe ist voll")
        if any(i["party"] == p["id"] and i["to"] == target for i in self.invites.values()):
            raise WorldError("Die Figur ist bereits eingeladen")
        if len(self.incoming(target)) >= self.pr["max_pending_invites_per_target"]:
            raise WorldError("Die Figur hat zu viele offene Einladungen")
        levels = [self.level_of(m) for m in p["members"]] + [self.level_of(target)]
        if max(levels) - min(levels) > self.pr["max_level_gap"]:
            raise WorldError(f"Stufenabstand über {self.pr['max_level_gap']}")
        self._counters["invite"] += 1
        iid = f"{self.server_id}-inv-{self._counters['invite']:08d}"
        self.invites[iid] = {"id": iid, "party": p["id"], "from": actor, "to": target, "day": today, "expires": today + self.pr["invite_days"]}
        self.notify(target, "party.invited", {"invite": iid, "party": p["id"], "from": actor, "expires": today + self.pr["invite_days"]})
        return iid

    def _invite(self, iid: Any) -> dict[str, Any]:
        i = self.invites.get(iid) if isinstance(iid, str) else None
        if i is None:
            raise WorldError("Einladung unbekannt oder erledigt")
        return i

    def accept(self, character_id: str, invite_id: str) -> str:
        today = self.day()
        i = self._invite(invite_id)
        if i["to"] != character_id:
            raise WorldError("Nur die Eingeladene kann annehmen")
        if today >= i["expires"]:
            raise WorldError("Die Einladung ist abgelaufen")
        if character_id in self.member_of:
            raise WorldError("Figur ist bereits in einer Gruppe")
        p = self.parties[i["party"]]
        if len(p["members"]) >= self.pr["max_size"]:
            raise WorldError("Die Gruppe ist voll")
        levels = [self.level_of(m) for m in p["members"]] + [self.level_of(character_id)]
        if max(levels) - min(levels) > self.pr["max_level_gap"]:
            raise WorldError(f"Stufenabstand über {self.pr['max_level_gap']}")
        self._members_notify(p, "party.joined", {"party": p["id"], "character": character_id})
        p["members"].append(character_id)
        self.member_of[character_id] = p["id"]
        for k in [k for k, x in self.invites.items() if x["to"] == character_id]:
            del self.invites[k]  # alle anderen Einladungen der Figur erledigen sich
        return p["id"]

    def decline(self, character_id: str, invite_id: str) -> None:
        self.day()
        i = self._invite(invite_id)
        if i["to"] != character_id:
            raise WorldError("Nur die Eingeladene kann ablehnen")
        del self.invites[invite_id]
        self.notify(i["from"], "party.invite_declined", {"invite": invite_id, "by": character_id})

    def expire(self, day: int) -> list[str]:
        """Serverinterner Tagesschritt: räumt verfallene Einladungen ab."""
        if not _is_int(day) or day < 0:
            raise WorldError("day ungültig")
        gone = sorted(k for k, i in self.invites.items() if i["expires"] <= day)
        for k in gone:
            del self.invites[k]
        return gone

    # -- Mitglieder ------------------------------------------------------------------------------------
    def _remove(self, p: dict[str, Any], character_id: str, kind: str) -> None:
        was_leader = p["leader"] == character_id
        idx = p["members"].index(character_id)
        p["members"].remove(character_id)
        del self.member_of[character_id]
        if len(p["members"]) <= 1:  # eine einzelne Figur ist keine Gruppe
            rest = list(p["members"])
            self._drop_party(p)
            for m in rest:
                self.notify(m, "party.disbanded", {"party": p["id"], "reason": kind})
            return
        if p["rr"] > idx:
            p["rr"] -= 1  # Zeiger bleibt bei derselben Figur
        p["rr"] %= len(p["members"])
        self._members_notify(p, "party.left" if kind == "left" else "party.kicked", {"party": p["id"], "character": character_id})
        if was_leader:
            p["leader"] = p["members"][0]
            self._members_notify(p, "party.leader_changed", {"party": p["id"], "leader": p["leader"]})

    def leave(self, character_id: str) -> None:
        self.day()
        self._remove(self._party_of(character_id), character_id, "left")

    def kick(self, actor: str, member: str) -> None:
        self.day()
        p = self._leader(actor)
        if member == actor or member not in p["members"]:
            raise WorldError("Kein anderes Mitglied dieser Gruppe")
        self.notify(member, "party.kicked", {"party": p["id"], "character": member})
        self._remove(p, member, "kicked")

    def promote(self, actor: str, member: str) -> None:
        """Führung abgeben."""
        self.day()
        p = self._leader(actor)
        if member == actor or member not in p["members"]:
            raise WorldError("Kein anderes Mitglied dieser Gruppe")
        p["leader"] = member
        self._members_notify(p, "party.leader_changed", {"party": p["id"], "leader": member})

    def set_loot(self, actor: str, mode: str) -> None:
        self.day()
        p = self._leader(actor)
        if mode not in self.pr["loot_modes"]:
            raise WorldError("Unbekannter Beutemodus")
        p["loot"] = mode

    def disband(self, actor: str) -> None:
        self.day()
        p = self._leader(actor)
        members = list(p["members"])
        self._drop_party(p)
        for m in members:
            if m != actor:
                self.notify(m, "party.disbanded", {"party": p["id"], "reason": "disbanded"})

    # -- Kampf und Beute -----------------------------------------------------------------------------------
    def roster(self, leader: str) -> list[str]:
        """Teilnehmer eines Gruppenkampfs: die Mitglieder in Beitrittsreihenfolge (nur der Anführer startet)."""
        return list(self._leader(leader)["members"])

    def distribute_loot(self, party_id: str, item_key: str, qty: int, eligible: Any, finder: str | None = None) -> dict[str, int]:
        """Serverinterne Beuteverteilung an berechtigte Mitglieder (Teilnehmer mit Beitrag). Gegenstände entstehen hier."""
        self.day()
        p = self.parties.get(party_id) if isinstance(party_id, str) else None
        if p is None:
            raise WorldError("Gruppe unbekannt")
        self.trading.parse(item_key)
        if not _is_int(qty) or qty < 1:
            raise WorldError("Menge muss eine positive ganze Zahl sein")
        if (not isinstance(eligible, (list, tuple)) or not eligible or len(set(eligible)) != len(eligible)
                or any(e not in p["members"] for e in eligible)):
            raise WorldError("Berechtigte müssen eindeutige Mitglieder der Gruppe sein")
        order = [m for m in p["members"] if m in eligible]  # Beitrittsreihenfolge
        mode = p["loot"]
        alloc: dict[str, int] = {}
        if mode == "leader":
            alloc[p["leader"] if p["leader"] in eligible else order[0]] = qty
        elif mode == "finder":
            if finder not in eligible:
                raise WorldError("Finder muss ein berechtigtes Mitglied sein")
            alloc[finder] = qty
        else:  # round_robin: reihum ab dem Zeiger, nur berechtigte Mitglieder
            n = len(p["members"])
            for _ in range(qty):
                while p["members"][p["rr"]] not in eligible:
                    p["rr"] = (p["rr"] + 1) % n
                who = p["members"][p["rr"]]
                alloc[who] = alloc.get(who, 0) + 1
                p["rr"] = (p["rr"] + 1) % n
        for who, n_ in sorted(alloc.items()):
            self.inv.deposit(who, item_key, n_)
            self.notify(who, "party.loot", {"party": party_id, "item_key": item_key, "qty": n_})
        return dict(sorted(alloc.items()))

    # -- Invarianten und Persistenz -----------------------------------------------------------------------------
    def check(self) -> list[str]:
        errs: list[str] = []
        seen: dict[str, str] = {}
        for pid, p in sorted(self.parties.items()):
            if len(p["members"]) < 1 or len(p["members"]) > self.pr["max_size"] or len(set(p["members"])) != len(p["members"]):
                errs.append(f"{pid}: Mitgliederzahl/Eindeutigkeit ungültig")
            if p["leader"] not in p["members"]:
                errs.append(f"{pid}: Anführer ist kein Mitglied")
            if p["loot"] not in self.pr["loot_modes"] or not 0 <= p["rr"] < max(1, len(p["members"])):
                errs.append(f"{pid}: Beutezustand ungültig")
            for m in p["members"]:
                if m in seen:
                    errs.append(f"{m}: in mehreren Gruppen")
                seen[m] = pid
        if seen != self.member_of:
            errs.append("Mitgliederindex weicht von den Gruppen ab")
        for iid, i in sorted(self.invites.items()):
            if i["party"] not in self.parties or i["to"] in self.member_of:
                errs.append(f"{iid}: Einladung ohne Gruppe oder an ein Mitglied")
        return errs

    def to_json(self) -> str:
        return json.dumps({"counters": self._counters, "parties": self.parties, "invites": self.invites}, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        data = json.loads(text)
        self._counters, self.parties, self.invites = data["counters"], data["parties"], data["invites"]
        self.member_of = {m: pid for pid, p in self.parties.items() for m in p["members"]}
        problems = self.check()
        if problems:
            raise WorldError("; ".join(problems))
