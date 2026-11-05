"""Grundstücke, Spielersiedlungen und Gemeinschaftsprojekte (AP 11, ADR-0050). Serverautoritativ, ohne CEE-Ereignisse.

* Orte (`sites`) sind vorgesehene Siedlungsgebiete. Die Hauptstadt besteht von Anfang an, andere Orte gründet eine Figur gegen Münzen
  (Geldsenke). Die Gründung gibt KEINE Sonderrechte (Stadtpolitik ist zurückgestellt, Blueprint §46).
* Grundstücke sind persönlich: kaufen, bebauen (Haus, Geschäft), Lager im Gebäude (Besitz bleibt im Inventar des Grundstücks).
  Tägliche Steuer aus dem Inventar; wird sie sieben Tage nicht gezahlt, verfällt das Grundstück (Lager geht zurück an die Figur).
* Gemeinschaftsprojekte (Straße, Marktplatz, Lagerhaus, Mauer, Hafen, Rathaus) füllen Bewohner (Grundstücksbesitzer) mit Münzen und
  Material; ist eine Stufe voll, steigt sie, und ihre Wirkung gilt für den ganzen Ort. Beiträge werden je Figur mitgezählt.
Alle Zahlen sind Platzhalter (Blueprint Frage 18).
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, Callable

from .errors import WorldError
from .inventory import Inventory


def load_settlement_rules(name: str = "settlement_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_world").joinpath("data", name).read_text(encoding="utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_settlement_rules(r: dict[str, Any]) -> None:
    for k in ("found_cost", "max_plots_per_player", "forfeit_after_unpaid_days", "medium_every"):
        if not _is_int(r[k]) or r[k] < 1:
            raise WorldError(f"settlement_rules.{k} ungültig")
    for sid, s in r["sites"].items():
        if not _is_int(s["plots"]) or s["plots"] < 1 or not _is_int(s["price_permille"]):
            raise WorldError(f"settlement_rules: Ort {sid} ungültig")
    for kind in ("buildings", "projects"):
        for bid, b in r[kind].items():
            if not b["levels"]:
                raise WorldError(f"settlement_rules: {bid} ohne Stufen")
            for lv in b["levels"]:
                if not _is_int(lv["coins"]) or lv["coins"] < 0 or any(not _is_int(n) or n <= 0 for n in lv["items"].values()):
                    raise WorldError(f"settlement_rules: {bid}: Kosten ungültig")
    for sz in r["plot_sizes"].values():
        if sz["building_levels"] > min(len(b["levels"]) for b in r["buildings"].values()):
            raise WorldError("settlement_rules: building_levels größer als vorhandene Stufen")
    for pid, p in r["projects"].items():
        for k, arr in p["effect"].items():
            if len(arr) != len(p["levels"]) + 1:
                raise WorldError(f"settlement_rules: {pid}.{k}: Wirkungsliste passt nicht zu den Stufen")


class SettlementService:
    def __init__(self, inventory: Inventory, coin: str, rules: dict[str, Any], day_provider: Callable[[], int],
                 char_exists: Callable[[str], bool] = lambda c: True) -> None:
        validate_settlement_rules(rules)
        self.inv, self.coin, self.R, self.day, self.exists = inventory, coin, rules, day_provider, char_exists
        self.founded: dict[str, dict[str, Any]] = {}      # Ort -> {name, founder, day}
        self.plots: dict[str, dict[str, Any]] = {}        # "ort:nr" -> {site, n, size, owner, building, level, unpaid, bought}
        self.projects: dict[str, dict[str, Any]] = {}     # "ort:projekt" -> {level, have}
        self.contrib: dict[str, dict[str, int]] = {}      # Figur -> {Ort: Wert}
        self.sales: dict[str, dict[str, Any]] = {}        # "ort:nr" -> {seller, buyer, price, day}: Verkaufsangebot (AP 43)
        self.last_day = 0
        self.notify: Callable[[str, str, dict[str, Any]], None] = lambda recipient, kind, data: None   # Postausgang (AP 51)
        self.record: Callable[..., Any] = lambda *a, **k: None                    # Chronik (AP 13)
        self.tech_known: Callable[[str, str], bool] = lambda site, tech: True      # von ResearchService überschrieben (AP 12)

    @property
    def active(self) -> bool:
        return bool(self.founded or self.plots or self.projects or self.last_day)

    # -- Hilfen ---------------------------------------------------------------------------
    def _site(self, site: str) -> dict[str, Any]:
        s = self.R["sites"].get(site) if isinstance(site, str) else None
        if s is None:
            raise WorldError("Unbekannter Ort")
        return s

    def is_open(self, site: str) -> bool:
        return self._site(site).get("capital", False) or site in self.founded

    def _need_open(self, site: str) -> dict[str, Any]:
        s = self._site(site)
        if not self.is_open(site):
            raise WorldError("Dieser Ort ist noch nicht gegründet")
        return s

    def size_of(self, n: int) -> str:
        return "medium" if n % self.R["medium_every"] == 0 else "small"

    def price(self, site: str, size: str) -> int:
        return self.R["plot_sizes"][size]["price"] * self._site(site)["price_permille"] // 1000

    def owned_by(self, char: str) -> list[dict[str, Any]]:
        return [p for _, p in sorted(self.plots.items()) if p["owner"] == char]

    def is_resident(self, char: str, site: str) -> bool:
        return any(p["site"] == site for p in self.owned_by(char))

    def plot_limit(self, char: str) -> int:
        bonus = max([self.effects(s).get("plot_limit_bonus", 0) for s in {p["site"] for p in self.owned_by(char)}] or [0])
        return self.R["max_plots_per_player"] + bonus

    def _plot(self, site: str, n: int) -> dict[str, Any]:
        p = self.plots.get(f"{site}:{n}") if _is_int(n) else None
        if p is None:
            raise WorldError("Grundstück nicht vergeben")
        return p

    @staticmethod
    def stash_owner(site: str, n: int) -> str:
        return f"plot:{site}:{n}"

    def _take(self, char: str, coins: int, items: dict[str, int]) -> None:
        remove = dict(items)
        if coins:
            remove[self.coin] = remove.get(self.coin, 0) + coins
        if remove:
            self.inv.apply(char, remove, {})              # prüft vollständig, bevor etwas geändert wird; Münzen verschwinden (Senke)

    # -- Wirkungen --------------------------------------------------------------------------
    def level(self, site: str, project: str) -> int:
        return self.projects.get(f"{site}:{project}", {}).get("level", 0)

    def effects(self, site: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for pid, p in self.R["projects"].items():
            for k, arr in p["effect"].items():
                out[k] = arr[self.level(site, pid)]
        return out

    def points(self, site: str) -> int:
        return sum(self.level(site, pid) for pid in self.R["projects"])

    def stage(self, site: str) -> str:
        name = self.R["stages"][0][0]
        for nm, need in self.R["stages"]:
            if self.points(site) >= need:
                name = nm
        return name

    def fee_discount_permille(self, char: str) -> int:
        """Marktgebühren-Rabatt (Promille der Gebühr) durch den Marktplatz: bester Wert unter den Orten, in denen die Figur ein Grundstück besitzt (AP 29)."""
        return max([self.effects(p["site"])["fee_discount_permille"] for p in self.owned_by(char) if self.is_open(p["site"])] or [0])

    def tax_of(self, p: dict[str, Any]) -> int:
        """Tagessteuer eines Grundstücks; die Mauer des Ortes senkt sie (wall_tax_relief, AP 64, ADR-0077)."""
        tax = self.R["plot_sizes"][p["size"]]["tax_per_day"]
        if self.R.get("wall_tax_relief"):
            tax -= tax * self.effects(p["site"])["raid_defence_permille"] // 1000
        return tax

    def order_bonus(self, char: str) -> int:
        """Zusätzliche offene Marktorders durch den Hafen: bester Wert (Handelsreichweite x orders_per_reach) unter den offenen Orten mit Grundstück der Figur (AP 41)."""
        per = self.R.get("orders_per_reach", 0)
        return per * max([self.effects(p["site"])["trade_reach"] for p in self.owned_by(char) if self.is_open(p["site"])] or [0])

    def road_permille(self, region: str | None) -> int:
        """Bewegungsbonus durch Straßen: bester Wert unter den gegründeten Orten der Region (vom Spiel je Position abgefragt)."""
        return max([self.effects(s)["move_permille"] for s, d in self.R["sites"].items() if d["region"] == region and self.is_open(s)] or [0])

    # -- Aktionen -----------------------------------------------------------------------------
    def found(self, char: str, site: str, name: str) -> None:
        s = self._site(site)
        lo, hi = self.R["name_len"]
        if s.get("capital") or site in self.founded:
            raise WorldError("Dieser Ort besteht schon")
        if not isinstance(name, str) or not lo <= len(name.strip()) <= hi:
            raise WorldError(f"Name {lo}..{hi} Zeichen")
        if any(f["name"].lower() == name.strip().lower() for f in self.founded.values()):
            raise WorldError("Name schon vergeben")
        self._take(char, self.R["found_cost"], {})
        self.founded[site] = {"name": name.strip(), "founder": char, "day": self.day()}
        self.record("settlement_founded", [char], key=f"site:{site}", name=name.strip())

    def buy_plot(self, char: str, site: str, n: int) -> None:
        s = self._need_open(site)
        if not _is_int(n) or not 1 <= n <= s["plots"]:
            raise WorldError("Grundstücksnummer ungültig")
        if f"{site}:{n}" in self.plots:
            raise WorldError("Grundstück ist schon vergeben")
        if len(self.owned_by(char)) >= self.plot_limit(char):
            raise WorldError("Grenze für persönliche Grundstücke erreicht")
        size = self.size_of(n)
        self._take(char, self.price(site, size), {})
        self.plots[f"{site}:{n}"] = {"site": site, "n": n, "size": size, "owner": char, "building": None, "level": 0, "unpaid": 0, "bought": self.day()}

    def abandon(self, char: str, site: str, n: int) -> None:
        p = self._plot(site, n)
        if p["owner"] != char:
            raise WorldError("Das Grundstück gehört dir nicht")
        self._release(p)

    def _release(self, p: dict[str, Any]) -> None:
        so = self.stash_owner(p["site"], p["n"])
        h = self.inv.holdings(so)
        if h:
            self.inv.apply_many([(so, h, {}), (p["owner"], {}, h)])
        del self.plots[f"{p['site']}:{p['n']}"]
        self.sales.pop(f"{p['site']}:{p['n']}", None)

    # -- Grundstückshandel (AP 43, ADR-0073) ---------------------------------------------------
    def _need_sales(self) -> None:
        if not self.R.get("sale_days"):
            raise WorldError("Grundstückshandel gibt es in diesen Regeln nicht")

    def sell_plot(self, char: str, site: str, n: int, buyer: str | None, price: int) -> dict[str, Any]:
        self._need_sales()
        p = self._plot(site, n)
        if p["owner"] != char:
            raise WorldError("Das Grundstück gehört dir nicht")
        if buyer is not None and (not isinstance(buyer, str) or buyer == char or not self.exists(buyer)):       # None = offenes Angebot (AP 56)
            raise WorldError("Käufer ungültig")
        if not _is_int(price) or not 0 <= price <= self.R["max_sale_price"]:
            raise WorldError("Preis ungültig")
        if p["unpaid"]:
            raise WorldError("Offene Steuer: erst bezahlen lassen")
        if self.used(p):
            raise WorldError("Das Lager muss vor dem Verkauf leer sein")
        offer = {"seller": char, "buyer": buyer, "price": price, "day": self.day()}
        self.sales[f"{site}:{n}"] = offer
        if buyer is not None:
            self.notify(buyer, "plot.sale_offered", {"plot": f"{site}:{n}", "seller": char, "price": price})
        return dict(offer, site=site, n=n)

    def cancel_sale(self, char: str, site: str, n: int) -> None:
        o = self.sales.get(f"{site}:{n}") if _is_int(n) else None
        if o is None or o["seller"] != char:
            raise WorldError("Kein eigenes Verkaufsangebot für dieses Grundstück")
        if o["buyer"] is not None:
            self.notify(o["buyer"], "plot.sale_cancelled", {"plot": f"{site}:{n}", "seller": char})
        del self.sales[f"{site}:{n}"]

    def accept_sale(self, char: str, site: str, n: int) -> dict[str, Any]:
        self._need_sales()
        o = self.sales.get(f"{site}:{n}") if _is_int(n) else None
        if o is None or o["seller"] == char or (o["buyer"] is not None and o["buyer"] != char):
            raise WorldError("Kein Verkaufsangebot an dich für dieses Grundstück")
        p = self._plot(site, n)
        if p["owner"] != o["seller"] or p["unpaid"] or self.used(p):
            del self.sales[f"{site}:{n}"]                              # Angebot nicht mehr gültig
            raise WorldError("Das Angebot ist nicht mehr gültig")
        if len(self.owned_by(char)) >= self.plot_limit(char):
            raise WorldError("Grenze für persönliche Grundstücke erreicht")
        fee = o["price"] * self.R["sale_fee_permille"] // 1000
        if o["price"] > self.inv.balance(char, self.coin):
            raise WorldError("Zu wenig Münzen")
        if o["price"]:
            self.inv.apply_many([(char, {self.coin: o["price"]}, {}), (o["seller"], {}, {self.coin: o["price"] - fee})])   # Gebühr verschwindet (Senke)
        p["owner"] = char
        del self.sales[f"{site}:{n}"]
        self.notify(o["seller"], "plot.sold", {"plot": f"{site}:{n}", "buyer": char, "price": o["price"], "fee": fee})
        return {"site": site, "n": n, "seller": o["seller"], "price": o["price"], "fee": fee}

    def build(self, char: str, site: str, n: int, building: str) -> int:
        p = self._plot(site, n)
        if p["owner"] != char:
            raise WorldError("Das Grundstück gehört dir nicht")
        b = self.R["buildings"].get(building) if isinstance(building, str) else None
        if b is None:
            raise WorldError("Unbekanntes Gebäude")
        cap = self.R["plot_sizes"][p["size"]]["building_levels"]
        if p["building"] is None:
            lv = 0
        elif p["building"] != building:
            raise WorldError("Hier steht schon ein anderes Gebäude")
        else:
            lv = p["level"]
        if lv >= min(cap, len(b["levels"])):
            raise WorldError("Höchste Ausbaustufe für dieses Grundstück erreicht")
        c = b["levels"][lv]
        self._take(char, c["coins"], c["items"])
        p["building"], p["level"] = building, lv + 1
        return lv + 1

    def capacity(self, p: dict[str, Any]) -> int:
        if p["building"] is None:
            return 0
        base = self.R["plot_sizes"][p["size"]]["stash"]
        per = self.R["buildings"][p["building"]]["stash_permille"][p["level"] - 1]
        return base * per // 1000 + self.effects(p["site"]).get("stash_bonus", 0)

    def used(self, p: dict[str, Any]) -> int:
        return sum(self.inv.holdings(self.stash_owner(p["site"], p["n"])).values())

    def stash_in(self, char: str, site: str, n: int, item_key: str, qty: int) -> None:
        p = self._plot(site, n)
        if p["owner"] != char:
            raise WorldError("Das Grundstück gehört dir nicht")
        if not _is_int(qty) or qty <= 0:
            raise WorldError("Menge ungültig")
        if self.used(p) + qty > self.capacity(p):
            raise WorldError("Das Lager ist voll (oder es steht kein Gebäude)")
        self.inv.apply_many([(char, {item_key: qty}, {}), (self.stash_owner(site, n), {}, {item_key: qty})])

    def stash_out(self, char: str, site: str, n: int, item_key: str, qty: int) -> None:
        p = self._plot(site, n)
        if p["owner"] != char:
            raise WorldError("Das Grundstück gehört dir nicht")
        if not _is_int(qty) or qty <= 0:
            raise WorldError("Menge ungültig")
        self.inv.apply_many([(self.stash_owner(site, n), {item_key: qty}, {}), (char, {}, {item_key: qty})])

    def contribute(self, char: str, site: str, project: str, coins: int = 0, items: dict[str, int] | None = None) -> dict[str, Any]:
        self._need_open(site)
        pr = self.R["projects"].get(project) if isinstance(project, str) else None
        if pr is None:
            raise WorldError("Unbekanntes Projekt")
        if pr.get("needs_coast") and not self._site(site).get("coast"):
            raise WorldError("Hier ist kein Hafen möglich")
        if not self.is_resident(char, site):
            raise WorldError("Nur Grundstücksbesitzer des Ortes dürfen beitragen")
        key = f"{site}:{project}"
        st = self.projects.setdefault(key, {"level": 0, "have": {}})
        if st["level"] >= len(pr["levels"]):
            raise WorldError("Projekt ist voll ausgebaut")
        need = pr["levels"][st["level"]]
        if need.get("requires_tech") and not self.tech_known(site, need["requires_tech"]):
            raise WorldError(f"Dieser Ort kennt die Technik {need['requires_tech']} noch nicht")
        want = dict(items or {})
        if coins:
            want[self.coin] = want.get(self.coin, 0) + coins
        if not want or any(not _is_int(q) or q <= 0 for q in want.values()):
            raise WorldError("Beitrag ungültig")
        full = dict(need["items"])
        if need["coins"]:
            full[self.coin] = need["coins"]
        for k, q in want.items():
            if k not in full:
                raise WorldError(f"{k} wird für diese Stufe nicht gebraucht")
            if st["have"].get(k, 0) + q > full[k]:
                raise WorldError(f"Zu viel {k}: es fehlen nur {full[k] - st['have'].get(k, 0)}")
        self.inv.apply(char, want, {})                    # Beitrag wird verbaut (Senke)
        for k, q in want.items():
            st["have"][k] = st["have"].get(k, 0) + q
        self.contrib.setdefault(char, {})
        self.contrib[char][site] = self.contrib[char].get(site, 0) + sum(want.values())
        done = all(st["have"].get(k, 0) >= q for k, q in full.items())
        if done:
            st["level"] += 1
            st["have"] = {}
        return {"level": st["level"], "completed": done}

    # -- Tagesschritt -------------------------------------------------------------------------
    def advance(self, day: int) -> list[dict[str, Any]]:
        if not _is_int(day) or day <= self.last_day:
            return []
        out: list[dict[str, Any]] = []
        start = max(self.last_day, day - self.R["max_catch_up_days"])      # alte Welten: nicht rückwirkend abrechnen
        for _ in range(start + 1, day + 1):
            for key in sorted(self.plots):
                p = self.plots[key]
                tax = self.tax_of(p)
                if self.inv.balance(p["owner"], self.coin) >= tax:
                    self.inv.apply(p["owner"], {self.coin: tax}, {})
                    p["unpaid"] = 0
                else:
                    p["unpaid"] += 1
                    if p["unpaid"] >= self.R["forfeit_after_unpaid_days"]:
                        out.append({"kind": "plot_forfeit", "site": p["site"], "n": p["n"], "owner": p["owner"]})
                        self._release(p)
        days = self.R.get("sale_days", 0)
        for key in [k for k, o in sorted(self.sales.items()) if day - o["day"] > days]:
            o = self.sales.pop(key)                                     # Angebot verfallen
            for who in (o["seller"], o["buyer"]):
                if who is not None:
                    self.notify(who, "plot.sale_expired", {"plot": key})
        self.last_day = day
        return out

    # -- Sicht ---------------------------------------------------------------------------------
    def plot_view(self, p: dict[str, Any]) -> dict[str, Any]:
        return {"n": p["n"], "size": p["size"], "owner": p["owner"], "building": p["building"], "level": p["level"],
                "unpaid": p["unpaid"], "tax": self.tax_of(p),
                "capacity": self.capacity(p), "used": self.used(p)}

    def site_view(self, site: str) -> dict[str, Any]:
        s = self._site(site)
        opened = self.is_open(site)
        free = [{"n": n, "size": self.size_of(n), "price": self.price(site, self.size_of(n))}
                for n in range(1, s["plots"] + 1) if f"{site}:{n}" not in self.plots] if opened else []
        projs = {}
        for pid, pr in self.R["projects"].items():
            if pr.get("needs_coast") and not s.get("coast"):
                continue
            st = self.projects.get(f"{site}:{pid}", {"level": 0, "have": {}})
            nxt = None
            if st["level"] < len(pr["levels"]):
                lv = pr["levels"][st["level"]]
                need = dict(lv["items"])
                if lv["coins"]:
                    need[self.coin] = lv["coins"]
                nxt = {k: {"need": q, "have": st["have"].get(k, 0)} for k, q in need.items()}
            projs[pid] = {"name": pr["name"], "level": st["level"], "max": len(pr["levels"]), "next": nxt,
                          "requires_tech": (pr["levels"][st["level"]].get("requires_tech") if st["level"] < len(pr["levels"]) else None)}
            rt = projs[pid]["requires_tech"]
            projs[pid]["tech_known"] = True if rt is None else bool(self.tech_known(site, rt))
        return {"id": site, "name": self.founded.get(site, {}).get("name", s["name"]), "region": s["region"], "capital": bool(s.get("capital")),
                "open": opened, "found_cost": None if opened else self.R["found_cost"], "founder": self.founded.get(site, {}).get("founder"),
                "stage": self.stage(site) if opened else None, "effects": self.effects(site) if opened else {},
                "plots": [self.plot_view(p) for _, p in sorted(self.plots.items()) if p["site"] == site], "free_plots": free, "projects": projs}

    def view(self, char: str) -> dict[str, Any]:
        mine = [dict(self.plot_view(p), site=p["site"]) for p in self.owned_by(char)]
        return {"sites": [self.site_view(s) for s in self.R["sites"]], "mine": mine, "plot_limit": self.plot_limit(char),
                "contributed": dict(sorted(self.contrib.get(char, {}).items())), "buildings": {k: {"name": b["name"], "levels": b["levels"]} for k, b in self.R["buildings"].items()},
                "coins": self.inv.balance(char, self.coin), "fee_discount_permille": self.fee_discount_permille(char),
                "order_bonus": self.order_bonus(char), "orders_per_reach": self.R.get("orders_per_reach", 0),
                "sales_out": [dict(o, plot=k) for k, o in sorted(self.sales.items()) if o["seller"] == char],
                "sales_in": [dict(o, plot=k) for k, o in sorted(self.sales.items()) if o["buyer"] == char],
                "sales_open": [dict(o, plot=k) for k, o in sorted(self.sales.items()) if o["buyer"] is None and o["seller"] != char][:50],
                "sale_fee_permille": self.R.get("sale_fee_permille", 0), "sale_days": self.R.get("sale_days", 0)}

    def check(self) -> list[str]:
        errs = []
        for key, o in self.sales.items():
            if key not in self.plots or self.plots[key]["owner"] != o["seller"]:
                errs.append(f"{key}: Verkaufsangebot ohne passendes Grundstück")
        for key, p in self.plots.items():
            if p["site"] not in self.R["sites"] or not self.is_open(p["site"]):
                errs.append(f"{key}: Ort nicht gegründet")
            if not self.exists(p["owner"]):
                errs.append(f"{key}: Besitzer {p['owner']} unbekannt")
            if p["building"] is not None and p["building"] not in self.R["buildings"]:
                errs.append(f"{key}: Gebäude {p['building']} unbekannt")
            if self.used(p) > self.capacity(p):
                errs.append(f"{key}: Lager überfüllt")
        return errs

    def to_json(self) -> str:
        d = {"founded": self.founded, "plots": self.plots, "projects": self.projects, "contrib": self.contrib, "last_day": self.last_day}
        if self.sales:                                                 # nur bei Bedarf: unveränderte Welten behalten ihren bisherigen Zustand
            d["sales"] = self.sales
        return json.dumps(d, sort_keys=True, separators=(",", ":"))

    def load(self, text: str) -> None:
        d = json.loads(text)
        self.founded, self.plots, self.projects, self.contrib, self.last_day = d["founded"], d["plots"], d["projects"], d["contrib"], d["last_day"]
        self.sales = d.get("sales", {})
