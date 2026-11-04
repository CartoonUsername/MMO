"""Ausrüstung und Transmog (AP 8, ADR-0047). Serverautoritativ.

* Getragene Gegenstände liegen im Inventar des Pseudo-Besitzers `worn:<Figur>` (Menge bleibt erhalten, nichts wird dupliziert); sie sind
  damit nicht handelbar, solange sie getragen werden.
* Wirkungen kommen aus den Regeln und skalieren mit der Qualitätsstufe des Gegenstands (`grade_permille` der CEE-Wirtschaft).
  Summe über alle Slots, begrenzt durch Kappen. Schwere/leichte Ausrüstung haben Vor- und Nachteile (Schutz vs. Beweglichkeit/Ausweichkosten).
* Transmog: `look[slot]` ersetzt nur die Darstellung. Erlaubt sind nur Aussehen aus der Garderobe (einmal getragene Gegenstände).
  Werte und Aussehen sind getrennt.
Alle Zahlen sind Platzhalter (Blueprint §31: Slots, Seltenheiten, Setboni offen).
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable

from mmo_cee.service import CharacterService

from .errors import WorldError
from .inventory import Inventory

SIM_KEYS = ("heavy_damage_permille", "light_damage_permille", "damage_taken_permille", "block_damage_permille", "dodge_cost_delta")


def load_equipment_rules(name: str = "equipment_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def worn_owner(char: str) -> str:
    return f"worn:{char}"


def validate_equipment_rules(r: dict[str, Any], cee_rules: Any) -> None:
    grades = cee_rules["economy"]["grade_permille"]
    for iid, it in r["items"].items():
        if it["slot"] not in r["slots"] or it["weight"] not in r["weight_classes"]:
            raise WorldError(f"equipment_rules: {iid}: Slot/Gewicht unbekannt")
        for k, v in it["effects"].items():
            if k not in SIM_KEYS + ("move_permille",) or not isinstance(v, int) or isinstance(v, bool):
                raise WorldError(f"equipment_rules: {iid}: Wirkung {k!r} ungültig")
    if not grades:
        raise WorldError("equipment_rules: keine Gütestufen")


class EquipmentService:
    def __init__(self, service: CharacterService, inventory: Inventory, rules: dict[str, Any]) -> None:
        validate_equipment_rules(rules, service.rules)
        self.cee, self.inv, self.R = service, inventory, rules
        self.worn: dict[str, dict[str, str]] = {}       # Figur -> Slot -> Gegenstandsschlüssel (item@grade)
        self.look: dict[str, dict[str, str]] = {}       # Figur -> Slot -> Aussehen (Gegenstands-ID)
        self.wardrobe: dict[str, list[str]] = {}        # Figur -> freigeschaltete Aussehen (Gegenstands-IDs)

    @property
    def active(self) -> bool:
        return bool(self.worn or self.look or self.wardrobe)

    # -- Hilfen -------------------------------------------------------------------
    def _parse(self, item_key: str) -> tuple[str, str, dict[str, Any]]:
        if not isinstance(item_key, str) or item_key.count("@") != 1:
            raise WorldError("Ungültiger Gegenstandsschlüssel")
        item, grade = item_key.split("@")
        d = self.R["items"].get(item)
        if d is None:
            raise WorldError("Das ist keine Ausrüstung")
        if grade not in self.cee.rules["economy"]["grade_permille"]:
            raise WorldError("Unbekannte Gütestufe")
        return item, grade, d

    def _scale(self, key: str, base: int, grade: str) -> int:
        g = self.cee.rules["economy"]["grade_permille"][grade]
        if key in ("block_damage_permille", "damage_taken_permille", "light_damage_permille", "heavy_damage_permille", "move_permille"):
            return 1000 + (base - 1000) * g // 1000
        return base * g // 1000                              # additive Werte (Kosten) skalieren ebenfalls

    def effects(self, char: str) -> dict[str, int]:
        """Gesamtwirkung der getragenen Ausrüstung (nur gesetzte Schlüssel), begrenzt durch die Kappen."""
        out: dict[str, int] = {}
        for item_key in self.worn.get(char, {}).values():
            item, grade, d = self._parse(item_key)
            for k, v in d["effects"].items():
                v = self._scale(k, v, grade)
                if k not in out:
                    out[k] = v
                elif k == "block_damage_permille":
                    out[k] = min(out[k], v)
                elif k == "dodge_cost_delta":
                    out[k] += v
                else:
                    out[k] = out[k] * v // 1000
        c = self.R["caps"]
        if "damage_taken_permille" in out:
            out["damage_taken_permille"] = max(c["damage_taken_permille_min"], out["damage_taken_permille"])
        for k in ("heavy_damage_permille", "light_damage_permille"):
            if k in out:
                out[k] = max(1, min(c[k + "_max"] if k + "_max" in c else 10000, out[k]))
        if "block_damage_permille" in out:
            out["block_damage_permille"] = max(c["block_damage_permille_min"], min(1000, out["block_damage_permille"]))
        if "move_permille" in out:
            out["move_permille"] = max(c["move_permille_min"], min(c["move_permille_max"], out["move_permille"]))
        if "dodge_cost_delta" in out:
            out["dodge_cost_delta"] = max(-c["dodge_cost_delta_max"], min(c["dodge_cost_delta_max"], out["dodge_cost_delta"]))
        return out

    def sim_gear(self, char: str) -> dict[str, int]:
        """Teil der Wirkungen, den die Kampfsimulation kennt."""
        return {k: v for k, v in self.effects(char).items() if k in SIM_KEYS}

    def move_permille(self, char: str) -> int:
        return self.effects(char).get("move_permille", 1000)

    # -- Aktionen ---------------------------------------------------------------------
    def equip(self, char: str, item_key: str) -> dict[str, Any]:
        item, grade, d = self._parse(item_key)
        st = self.cee.state(char).parts["identity"]
        if st["level"] < d["min_level"]:
            raise WorldError(f"Benötigt Stufe {d['min_level']}")
        if d["classes"] is not None and st.get("base_class") not in d["classes"]:
            raise WorldError("Deine Klasse kann das nicht tragen" if st.get("base_class") else "Wähle zuerst eine Grundklasse")
        slots = self.worn.setdefault(char, {})
        old = slots.get(d["slot"])
        if old:                                              # atomar: neuen Gegenstand anlegen, alten ins Inventar zurück
            self.inv.apply_many([(char, {item_key: 1}, {old: 1}), (worn_owner(char), {old: 1}, {item_key: 1})])
        else:
            self.inv.apply_many([(char, {item_key: 1}, {}), (worn_owner(char), {}, {item_key: 1})])
        slots[d["slot"]] = item_key
        wd = self.wardrobe.setdefault(char, [])
        if item not in wd:
            wd.append(item)
        return self.view(char)

    def unequip(self, char: str, slot: str) -> dict[str, Any]:
        item_key = self.worn.get(char, {}).get(slot)
        if item_key is None:
            raise WorldError("Nichts getragen")
        self.inv.apply_many([(worn_owner(char), {item_key: 1}, {}), (char, {}, {item_key: 1})])
        del self.worn[char][slot]
        if not self.worn[char]:
            del self.worn[char]
        return self.view(char)

    def set_look(self, char: str, slot: str, item: str | None) -> dict[str, Any]:
        if slot not in self.R["slots"]:
            raise WorldError("Unbekannter Slot")
        if item is None:
            self.look.get(char, {}).pop(slot, None)
            if char in self.look and not self.look[char]:
                del self.look[char]
            return self.view(char)
        d = self.R["items"].get(item)
        if d is None or d["slot"] != slot:
            raise WorldError("Dieses Aussehen passt nicht in den Slot")
        if item not in self.wardrobe.get(char, []):
            raise WorldError("Dieses Aussehen ist noch nicht freigeschaltet (einmal tragen)")
        self.look.setdefault(char, {})[slot] = item
        return self.view(char)

    # -- Sicht ----------------------------------------------------------------------------
    def appearance(self, char: str) -> dict[str, Any]:
        """Dargestellte Teile je Slot: Transmog-Aussehen, sonst das getragene Stück, sonst nichts. Getrennt von den Werten."""
        out: dict[str, Any] = {}
        for s in self.R["slots"]:
            worn = self.worn.get(char, {}).get(s)
            shown = self.look.get(char, {}).get(s) or (worn.split("@")[0] if worn else None)
            out[s] = {"look": self.R["items"][shown]["look"] if shown else None, "name": self.R["items"][shown]["name"] if shown else None,
                      "transmog": bool(self.look.get(char, {}).get(s))}
        return out

    def view(self, char: str) -> dict[str, Any]:
        worn = {}
        for s in self.R["slots"]:
            k = self.worn.get(char, {}).get(s)
            if k:
                item, grade, d = self._parse(k)
                worn[s] = {"key": k, "name": d["name"], "grade": grade, "weight": d["weight"], "style": d["style"]}
        inv = self.inv.holdings(char)
        bag = []
        for k, n in inv.items():
            try:
                item, grade, d = self._parse(k)
            except WorldError:
                continue
            bag.append({"key": k, "qty": n, "name": d["name"], "slot": d["slot"], "grade": grade, "weight": d["weight"], "style": d["style"],
                        "classes": d["classes"], "min_level": d["min_level"], "effects": {e: self._scale(e, v, grade) for e, v in d["effects"].items()}})
        wd = self.wardrobe.get(char, [])
        return {"slots": list(self.R["slots"]), "worn": worn, "bag": bag, "effects": self.effects(char), "appearance": self.appearance(char),
                "look": dict(self.look.get(char, {})),
                "wardrobe": [{"item": i, "name": self.R["items"][i]["name"], "slot": self.R["items"][i]["slot"]} for i in wd]}

    # -- Konsistenz / Persistenz --------------------------------------------------------------
    def check(self) -> list[str]:
        errs: list[str] = []
        for char, slots in self.worn.items():
            for s, k in slots.items():
                try:
                    _, _, d = self._parse(k)
                except WorldError:
                    errs.append(f"{char}: {k} ist keine Ausrüstung")
                    continue
                if d["slot"] != s:
                    errs.append(f"{char}: {k} im falschen Slot {s}")
                if self.inv.balance(worn_owner(char), k) < 1:
                    errs.append(f"{char}: {k} getragen, aber nicht im Tragebestand")
        for char, lk in self.look.items():
            for s, i in lk.items():
                if i not in self.wardrobe.get(char, []):
                    errs.append(f"{char}: Aussehen {i} nicht in der Garderobe")
        return errs

    def to_json(self) -> str:
        return json.dumps({"worn": self.worn, "look": self.look, "wardrobe": self.wardrobe}, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        d = json.loads(text)
        self.worn, self.look, self.wardrobe = d["worn"], d["look"], d["wardrobe"]
