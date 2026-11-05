"""Gilden, Weltchronik und Prestige (AP 13, ADR-0052). Serverautoritativ, ohne CEE-Ereignisse.

* **Gilden** sind freiwillig: Gründen (Münzen als Senke), Einladen, Rollen (Leiter, Offizier, Mitglied), gemeinsame Kasse im Inventar
  `guild:<id>`, Gildenhaus als Gemeinschaftsprojekt (mehr Mitglieder). Aktivitätspunkte durch gemeinsame Siege und Beiträge.
  Nichts Grundlegendes hängt an einer Gilde; Einzelspieler verlieren keinen Zugang (§45, §49).
* **Weltchronik:** dauerhaft, nur anhängend. Dienste melden Weltereignisse (`record`).
* **Prestige:** Titel und Punkte aus Chronikereignissen. Titel für Erstleistungen sind Anerkennung, sperren aber keine Inhalte (§49).
Stadtpolitik ist nicht Teil davon (zurückgestellt, §46).
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable

from .errors import WorldError
from .inventory import Inventory


def load_community_rules(name: str = "community_rules_v2.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_community_rules(r: dict[str, Any]) -> None:
    g = r["guild"]
    for k in ("found_cost", "base_members", "max_invites_per_char"):
        if not _is_int(g[k]) or g[k] < 0:
            raise WorldError(f"community_rules.guild.{k} ungültig")
    if len(g["house"]["member_cap"]) != len(g["house"]["levels"]) + 1 or g["house"]["member_cap"][0] != g["base_members"]:
        raise WorldError("community_rules: member_cap passt nicht zu den Gildenhaus-Stufen")
    if g["roles"][0] != "leader":
        raise WorldError("community_rules: erste Rolle muss leader sein")
    res = g.get("research")
    if res is not None:
        for tid, tech in res["techs"].items():
            if not tech["cost"] or any(not _is_int(q) or q <= 0 for q in tech["cost"].values()) or not _is_int(tech["days"]) or tech["days"] < 1:
                raise WorldError(f"community_rules.guild.research.{tid} ungültig")
            if tech["requires"] is not None and tech["requires"] not in res["techs"]:
                raise WorldError(f"community_rules.guild.research.{tid}: unbekannte Voraussetzung")
            if not tech["effect"] or any(not _is_int(v) or v <= 0 for v in tech["effect"].values()):
                raise WorldError(f"community_rules.guild.research.{tid}: Wirkung ungültig")
    for k, v in r["chronicle"]["kinds"].items():
        if not _is_int(v["prestige"]) or v["prestige"] < 0:
            raise WorldError(f"community_rules.chronicle.{k} ungültig")


class Chronicle:
    def __init__(self, rules: dict[str, Any], day_provider: Callable[[], int]) -> None:
        validate_community_rules(rules)
        self.R, self.day = rules["chronicle"], day_provider
        self.entries: list[dict[str, Any]] = []
        self.firsts: dict[str, int] = {}                      # Schlüssel -> Eintragsnummer
        self.titles: dict[str, list[dict[str, Any]]] = {}
        self.chosen: dict[str, str] = {}                       # Figur -> gewählte Anzeigetitel-ID (AP 73)

    @property
    def active(self) -> bool:
        return bool(self.entries)

    def record(self, kind: str, chars: list[str], key: str | None = None, **data: Any) -> dict[str, Any] | None:
        """Meldet ein Weltereignis. `key` kennzeichnet Erstleistungen (nur der erste Eintrag mit diesem Schlüssel zählt als 'first')."""
        spec = self.R["kinds"].get(kind)
        if spec is None:
            raise WorldError("Unbekannte Chronikart")
        first = key is not None and key not in self.firsts
        if spec.get("first_only") and key is not None and not first:
            return None                                       # spätere Siege gehören nicht in die Chronik
        n = len(self.entries) + 1
        entry = {"n": n, "day": self.day(), "kind": kind, "chars": sorted(set(chars)), "first": first, "data": data}
        self.entries.append(entry)
        if first:
            self.firsts[key] = n
        if spec["title"] and (first or key is None):
            title = spec["title"].format(**{k: v for k, v in data.items()})
            for c in entry["chars"]:
                self.grant(c, f"{kind}:{key or n}", title)
        return entry

    def grant(self, char: str, tid: str, name: str) -> None:
        ts = self.titles.setdefault(char, [])
        if not any(t["id"] == tid for t in ts):
            ts.append({"id": tid, "name": name, "day": self.day()})

    def page(self, offset: int = 0, limit: int = 20, kind: str | None = None) -> dict[str, Any]:
        if not _is_int(offset) or not _is_int(limit) or offset < 0 or not 1 <= limit <= self.R["page_max"]:
            raise WorldError(f"offset >= 0, limit 1..{self.R['page_max']}")
        rows = [e for e in reversed(self.entries) if kind is None or e["kind"] == kind]          # neueste zuerst
        return {"total": len(rows), "entries": rows[offset:offset + limit]}

    def prestige(self, char: str) -> dict[str, Any]:
        pts = 0
        for e in self.entries:
            if char in e["chars"]:
                pts += self.R["kinds"][e["kind"]]["prestige"]
        cid = self.chosen.get(char)
        shown = next((t["name"] for t in self.titles.get(char, []) if t["id"] == cid), None)
        return {"points": pts, "titles": list(self.titles.get(char, [])), "chosen": cid if shown else None, "display": shown}

    def choose_title(self, char: str, title_id: str | None) -> dict[str, Any]:
        """Wählt einen verdienten Titel als Anzeigetitel (AP 73, ADR-0080); None entfernt ihn."""
        if title_id is None:
            self.chosen.pop(char, None)
        elif not isinstance(title_id, str) or not any(t["id"] == title_id for t in self.titles.get(char, [])):
            raise WorldError("Diesen Titel hast du nicht verdient")
        else:
            self.chosen[char] = title_id
        return self.prestige(char)

    def to_json(self) -> str:
        d: dict[str, Any] = {"entries": self.entries, "firsts": self.firsts, "titles": self.titles}
        if self.chosen:                                        # nur bei Bedarf: unveränderte Welten behalten ihren Zustand
            d["chosen"] = self.chosen
        return json.dumps(d, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        d = json.loads(text)
        self.entries, self.firsts, self.titles = d["entries"], d["firsts"], d["titles"]
        self.chosen = d.get("chosen", {})

    def check(self) -> list[str]:
        errs = [f"Eintrag {i + 1}: Nummer {e['n']}" for i, e in enumerate(self.entries) if e["n"] != i + 1]
        errs += [f"first {k}: Eintrag {n} fehlt" for k, n in self.firsts.items() if not 1 <= n <= len(self.entries)]
        return errs


class GuildService:
    def __init__(self, inventory: Inventory, coin: str, rules: dict[str, Any], day_provider: Callable[[], int],
                 char_exists: Callable[[str], bool] = lambda c: True) -> None:
        validate_community_rules(rules)
        self.inv, self.coin, self.R, self.day, self.exists = inventory, coin, rules["guild"], day_provider, char_exists
        self.guilds: dict[str, dict[str, Any]] = {}
        self.member_of: dict[str, str] = {}
        self.invites: dict[str, list[str]] = {}
        self._counter = 0
        self.record: Callable[..., Any] = lambda *a, **k: None

    @property
    def active(self) -> bool:
        return self._counter > 0

    @staticmethod
    def treasury(gid: str) -> str:
        return f"guild:{gid}"

    def _mine(self, char: str) -> dict[str, Any]:
        g = self.guilds.get(self.member_of.get(char, ""))
        if g is None:
            raise WorldError("Du bist in keiner Gilde")
        return g

    def _need_role(self, char: str, *roles: str) -> dict[str, Any]:
        g = self._mine(char)
        if g["members"][char] not in roles:
            raise WorldError("Dafür fehlt dir die Rolle in der Gilde")
        return g

    def capacity(self, g: dict[str, Any]) -> int:
        return self.R["house"]["member_cap"][g["house"]["level"]] + self.bonus(g, "member_cap")

    # -- Gildenforschung (AP 18, ADR-0057) -----------------------------------------------
    def _res(self, g: dict[str, Any]) -> dict[str, Any]:
        return g.setdefault("research", {"done": [], "active": None})

    def _settle(self, g: dict[str, Any]) -> None:
        """Eine laufende Forschung gilt ab ihrem Fertigstellungstag als abgeschlossen (kein Zeitgeber nötig)."""
        r = self._res(g)
        a = r["active"]
        if a and self.day() >= a["ready_day"]:
            r["done"].append(a["tech"])
            r["active"] = None
            self._log(g, "research_done", a["by"], tech=a["tech"])

    def bonus(self, g: dict[str, Any], key: str) -> int:
        res = self.R.get("research")
        if not res:
            return 0
        self._settle(g)
        return sum(res["techs"][t]["effect"].get(key, 0) for t in g["research"]["done"] if t in res["techs"])

    def research_start(self, char: str, tech: str) -> dict[str, Any]:
        g = self._need_role(char, "leader", "officer")
        res = self.R.get("research")
        if not res or tech not in res["techs"]:
            raise WorldError("Unbekannte Gildenforschung")
        spec = res["techs"][tech]
        self._settle(g)
        r = self._res(g)
        if tech in r["done"]:
            raise WorldError("Schon erforscht")
        if r["active"]:
            raise WorldError("Es läuft schon eine Forschung")
        if spec["requires"] and spec["requires"] not in r["done"]:
            raise WorldError(f"Voraussetzung fehlt: {res['techs'][spec['requires']]['name']}")
        self.inv.apply(self.treasury(g["id"]), dict(spec["cost"]), {})          # Kosten aus der Gildenkasse (Senke)
        r["active"] = {"tech": tech, "ready_day": self.day() + spec["days"], "by": char}
        self._log(g, "research_start", char, tech=tech)
        return {"tech": tech, "ready_day": r["active"]["ready_day"]}

    def research_view(self, g: dict[str, Any]) -> dict[str, Any] | None:
        res = self.R.get("research")
        if not res:
            return None
        self._settle(g)
        r = self._res(g)
        return {"techs": [{"id": tid, "name": s["name"], "cost": s["cost"], "days": s["days"], "requires": s["requires"], "effect": s["effect"],
                           "status": "done" if tid in r["done"] else "active" if r["active"] and r["active"]["tech"] == tid else "open"}
                          for tid, s in res["techs"].items()], "active": r["active"]}

    def found(self, char: str, name: str, tag: str) -> str:
        if char in self.member_of:
            raise WorldError("Du bist schon in einer Gilde")
        lo, hi = self.R["name_len"]
        tl, th = self.R["tag_len"]
        if not isinstance(name, str) or not lo <= len(name.strip()) <= hi or not isinstance(tag, str) or not tl <= len(tag.strip()) <= th:
            raise WorldError(f"Name {lo}..{hi} und Kürzel {tl}..{th} Zeichen")
        name, tag = name.strip(), tag.strip().upper()
        if any(g["name"].lower() == name.lower() or g["tag"] == tag for g in self.guilds.values()):
            raise WorldError("Name oder Kürzel schon vergeben")
        self.inv.apply(char, {self.coin: self.R["found_cost"]}, {})            # Senke
        self._counter += 1
        gid = f"gld-{self._counter:05d}"
        self.guilds[gid] = {"id": gid, "name": name, "tag": tag, "founded": self.day(), "members": {char: "leader"},
                            "house": {"level": 0, "have": {}}, "points": 0, "contrib": {}, "log": []}
        self.member_of[char] = gid
        self._log(self.guilds[gid], "founded", char)
        self.record("guild_founded", [char], name=name)
        return gid

    def _log(self, g: dict[str, Any], kind: str, char: str, **data: Any) -> None:
        g["log"].append({"day": self.day(), "kind": kind, "char": char, **data})
        del g["log"][:-50]

    def invite(self, char: str, target: str) -> None:
        g = self._need_role(char, "leader", "officer")
        if not self.exists(target):
            raise WorldError("Unbekannte Figur")
        if target in self.member_of:
            raise WorldError("Die Figur ist schon in einer Gilde")
        if len(g["members"]) >= self.capacity(g):
            raise WorldError("Die Gilde ist voll (Gildenhaus ausbauen)")
        inv = self.invites.setdefault(target, [])
        if g["id"] in inv:
            raise WorldError("Schon eingeladen")
        if len(inv) >= self.R["max_invites_per_char"]:
            raise WorldError("Die Figur hat zu viele offene Einladungen")
        inv.append(g["id"])

    def accept(self, char: str, gid: str) -> None:
        if char in self.member_of:
            raise WorldError("Du bist schon in einer Gilde")
        if gid not in self.invites.get(char, []):
            raise WorldError("Keine Einladung")
        g = self.guilds.get(gid)
        if g is None or len(g["members"]) >= self.capacity(g):
            raise WorldError("Die Gilde besteht nicht mehr oder ist voll")
        g["members"][char] = "member"
        self.member_of[char] = gid
        self.invites.pop(char, None)
        self._log(g, "joined", char)

    def decline(self, char: str, gid: str) -> None:
        if gid not in self.invites.get(char, []):
            raise WorldError("Keine Einladung")
        self.invites[char].remove(gid)
        if not self.invites[char]:
            del self.invites[char]

    def leave(self, char: str) -> None:
        g = self._mine(char)
        if g["members"][char] == "leader":
            if len(g["members"]) > 1:
                raise WorldError("Übergib zuerst die Leitung (Befördern zum Leiter) oder löse die Gilde auf")
            return self.disband(char)
        del g["members"][char], self.member_of[char]
        self._log(g, "left", char)

    def kick(self, char: str, target: str) -> None:
        g = self._need_role(char, "leader", "officer")
        role = g["members"].get(target)
        if role is None or target == char:
            raise WorldError("Ungültiges Ziel")
        if role == "leader" or (role == "officer" and g["members"][char] != "leader"):
            raise WorldError("Das darfst du nicht")
        del g["members"][target], self.member_of[target]
        self._log(g, "kicked", char, target=target)

    def set_role(self, char: str, target: str, role: str) -> None:
        g = self._need_role(char, "leader")
        if role not in self.R["roles"] or g["members"].get(target) is None or target == char:
            raise WorldError("Ungültige Rolle oder Ziel")
        if role == "leader":                                  # Übergabe der Leitung
            g["members"][char], g["members"][target] = "officer", "leader"
        else:
            g["members"][target] = role
        self._log(g, "role", char, target=target, role=role)

    def disband(self, char: str) -> None:
        g = self._need_role(char, "leader")
        t = self.treasury(g["id"])
        h = self.inv.holdings(t)
        if h:
            self.inv.apply_many([(t, h, {}), (char, {}, h)])                  # Kasse geht an die Leitung
        for m in g["members"]:
            del self.member_of[m]
        del self.guilds[g["id"]]
        for c in list(self.invites):
            self.invites[c] = [x for x in self.invites[c] if x != g["id"]]
            if not self.invites[c]:
                del self.invites[c]

    def deposit(self, char: str, item_key: str, qty: int) -> None:
        g = self._mine(char)
        if not _is_int(qty) or qty <= 0:
            raise WorldError("Menge ungültig")
        self.inv.apply_many([(char, {item_key: qty}, {}), (self.treasury(g["id"]), {}, {item_key: qty})])
        self._log(g, "deposit", char, item=item_key, qty=qty)

    def withdraw(self, char: str, item_key: str, qty: int) -> None:
        g = self._need_role(char, "leader", "officer")
        if not _is_int(qty) or qty <= 0:
            raise WorldError("Menge ungültig")
        self.inv.apply_many([(self.treasury(g["id"]), {item_key: qty}, {}), (char, {}, {item_key: qty})])
        self._log(g, "withdraw", char, item=item_key, qty=qty)

    def contribute(self, char: str, coins: int = 0, items: dict[str, int] | None = None) -> dict[str, Any]:
        """Beitrag zum Gildenhaus (wird verbaut)."""
        g = self._mine(char)
        h = g["house"]
        levels = self.R["house"]["levels"]
        if h["level"] >= len(levels):
            raise WorldError("Das Gildenhaus ist voll ausgebaut")
        need = levels[h["level"]]
        full = dict(need["items"])
        if need["coins"]:
            full[self.coin] = need["coins"]
        want = dict(items or {})
        if coins:
            want[self.coin] = want.get(self.coin, 0) + coins
        if not want or any(not _is_int(q) or q <= 0 for q in want.values()):
            raise WorldError("Beitrag ungültig")
        for k, q in want.items():
            if k not in full:
                raise WorldError(f"{k} wird für diese Stufe nicht gebraucht")
            if h["have"].get(k, 0) + q > full[k]:
                raise WorldError(f"Zu viel {k}: es fehlen nur {full[k] - h['have'].get(k, 0)}")
        self.inv.apply(char, want, {})
        for k, q in want.items():
            h["have"][k] = h["have"].get(k, 0) + q
        value = sum(want.values())
        g["contrib"][char] = g["contrib"].get(char, 0) + value
        g["points"] += value // 100 * self.R["points"]["contribute_per_100"]
        done = all(h["have"].get(k, 0) >= q for k, q in full.items())
        if done:
            h["level"] += 1
            h["have"] = {}
            self._log(g, "house", char, level=h["level"])
        return {"level": h["level"], "completed": done}

    def activity(self, char: str, kind: str) -> None:
        """Gemeinsame Siege (boss, dungeon) geben der Gilde Punkte."""
        gid = self.member_of.get(char)
        if gid is not None:
            self.guilds[gid]["points"] += self.R["points"][kind]

    CHAT_KEEP, CHAT_MAX_LEN, CHAT_PER_DAY = 50, 64, 30      # 64 = Stringgrenze des Protokolls

    def say(self, char: str, text: str) -> dict[str, Any]:
        """Gildenchat (AP 66, ADR-0078): kurze Nachricht an alle Mitglieder; Verlauf (letzte 50) und Tagesgrenze je Figur."""
        g = self._mine(char)
        if not isinstance(text, str):
            raise WorldError("Nachricht muss Text sein")
        text = text.strip()
        if not text or len(text) > self.CHAT_MAX_LEN or any(ord(c) < 32 for c in text):
            raise WorldError(f"Nachricht: 1 bis {self.CHAT_MAX_LEN} Zeichen, ohne Steuerzeichen")
        chat, today = g.setdefault("chat", []), self.day()
        if sum(1 for m in chat if m["char"] == char and m["day"] == today) >= self.CHAT_PER_DAY:
            raise WorldError("Tageslimit für Gildennachrichten erreicht")
        g["chat_n"] = g.get("chat_n", 0) + 1
        msg = {"n": g["chat_n"], "day": today, "char": char, "text": text}
        chat.append(msg)
        del chat[:-self.CHAT_KEEP]
        return msg

    def view(self, char: str) -> dict[str, Any]:
        gid = self.member_of.get(char)
        mine = None
        if gid:
            g = self.guilds[gid]
            h = g["house"]
            levels = self.R["house"]["levels"]
            nxt = None
            if h["level"] < len(levels):
                need = dict(levels[h["level"]]["items"])
                if levels[h["level"]]["coins"]:
                    need[self.coin] = levels[h["level"]]["coins"]
                nxt = {k: {"need": q, "have": h["have"].get(k, 0)} for k, q in need.items()}
            mine = {"id": gid, "name": g["name"], "tag": g["tag"], "role": g["members"][char], "founded": g["founded"], "points": g["points"],
                    "members": [{"char": m, "role": r, "contributed": g["contrib"].get(m, 0)} for m, r in sorted(g["members"].items())],
                    "capacity": self.capacity(g), "house": {"level": h["level"], "max": len(levels), "next": nxt}, "research": self.research_view(g),
                    "treasury": self.inv.holdings(self.treasury(gid)) if g["members"][char] in ("leader", "officer") else None, "log": g["log"][-15:], "chat": g.get("chat", [])[-30:]}
        return {"mine": mine, "invites": [{"id": i, "name": self.guilds[i]["name"], "tag": self.guilds[i]["tag"]} for i in self.invites.get(char, []) if i in self.guilds],
                "found_cost": self.R["found_cost"], "coins": self.inv.balance(char, self.coin),
                "directory": [{"id": g["id"], "name": g["name"], "tag": g["tag"], "members": len(g["members"]), "points": g["points"]}
                              for g in sorted(self.guilds.values(), key=lambda g: (-g["points"], g["id"]))][:50]}

    def check(self) -> list[str]:
        errs = []
        for gid, g in self.guilds.items():
            if sum(1 for r in g["members"].values() if r == "leader") != 1:
                errs.append(f"{gid}: genau ein Leiter erwartet")
            if len(g["members"]) > self.capacity(g):
                errs.append(f"{gid}: zu viele Mitglieder")
            for m in g["members"]:
                if self.member_of.get(m) != gid:
                    errs.append(f"{gid}: {m} nicht eingetragen")
        for m, gid in self.member_of.items():
            if gid not in self.guilds or m not in self.guilds[gid]["members"]:
                errs.append(f"{m}: Gilde {gid} passt nicht")
        return errs

    def to_json(self) -> str:
        return json.dumps({"counter": self._counter, "guilds": self.guilds, "member_of": self.member_of, "invites": self.invites},
                          sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        d = json.loads(text)
        self._counter, self.guilds, self.member_of, self.invites = d["counter"], d["guilds"], d["member_of"], d["invites"]
