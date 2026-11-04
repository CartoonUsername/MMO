"""Balancing-Werkzeug: deterministische Testspieler (Bots) und Kampfreihen gegen die Gegnerfamilien (ADR-0034).

Die Bots lesen wie ein Client nur Ankündigungen (`telegraph`) und den Anzeigezustand (`view`) und senden Befehle über `LiveEncounter` –
sie sehen also nichts, was ein Spieler nicht sähe. Fertigkeitsstufen:

* `novice`  – schlägt nur leicht zu, reagiert auf nichts.
* `average` – weicht Wucht-/Flächen-/Zustandsangriffen aus (einfaches Ausweichen), sonst wie Anfänger.
* `good`    – pariert Wuchtschläge, weicht Flächenschlägen perfekt aus, unterbricht Zauber/Heiler/Beschwörer mit Betäubung, nimmt Heiler und
  Beschwörer zuerst aufs Korn; in Gruppen heilen und schützen die hinteren Spieler.
Alle Werte sind Platzhalter; Ergebnisse sind Richtwerte für das Balancing, kein Beleg für echtes Spielverhalten.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .enemies import roll_abilities
from .live import LiveEncounter

SKILLS = ("novice", "average", "good")


@dataclass
class Outcome:
    outcome: str
    ticks: int
    hp_lost: list[int]            # Anteil verlorener Lebenspunkte je Spieler in Promille
    deaths: int
    summons: int


# Reaktionszeit in Ticks (Anzeige bis Befehl) und Fehlermuster (jeder n-te Versuch misslingt) je Fertigkeitsstufe – Platzhalter
REACTION = {"novice": 99, "average": 6, "good": 3}
MISS_EVERY = {"novice": 1, "average": 3, "good": 5}


class Bot:
    def __init__(self, idx: int, skill: str, role: str, group_size: int) -> None:
        self.idx, self.skill, self.role, self.group = idx, skill, role, group_size
        self.queue: list[tuple[int, str]] = []
        self.tries = 0                                                     # Abwehrversuche (für das Fehlermuster)

    def _misses(self) -> bool:
        self.tries += 1
        return self.tries % MISS_EVERY[self.skill] == 0

    def plan(self, ev: dict[str, Any], types: list[str], abilities: list[list[str]]) -> None:
        if self.skill == "novice":
            return
        t, kind, ticks, tgt = ev["t"], ev["kind"], ev["ticks"], ev["target"]
        end = t + ticks
        if ticks < REACTION[self.skill] + 2:                              # zu kurze Vorwarnung: nicht zu beantworten
            return
        if kind in ("basic", "slam", "state") and tgt != self.idx:
            return
        if kind in ("basic", "slam", "state", "area"):
            if self._misses():
                return
            if self.skill == "good" and kind in ("basic", "slam"):
                self.queue.append((end - 1, "block"))                      # Parade: Block beginnt 1 Tick vor der Wirkung
            elif self.skill == "good":
                self.queue.append((end - 1, "dodge"))                      # perfektes Ausweichen
            else:
                self.queue.append((end - 2, "dodge"))                      # einfaches Ausweichen
            return
        if self.skill == "good" and kind in ("cast", "heal_ally", "buff_allies", "summon") and self.role == "attacker" and ticks >= REACTION[self.skill] + 4:
            self.queue.append((t + REACTION[self.skill], f"target_{ev['enemy'] + 1}"))
            self.queue.append((t + REACTION[self.skill] + 1, "stun"))

    def act(self, e: LiveEncounter, now: int) -> None:
        v = e.view()
        me = v["players"][self.idx]
        if me["state"] != "active":
            return
        due = [q for q in self.queue if q[0] <= now]
        self.queue = [q for q in self.queue if q[0] > now]
        for _, cmd in sorted(due):
            e.submit(self.idx, cmd)
        if me["busy"] > 0 or me["stunned"] > 0 if "stunned" in me else me["busy"] > 0:
            return
        if self.role == "support" and self.skill != "novice":
            hurt = [i for i, p in enumerate(v["players"]) if p["state"] == "active" and p["hp"] * 1000 < 600 * p["max_hp"]]
            if hurt and "heal" not in me["cooldowns"] and me["stamina"] >= 20:
                e.submit(self.idx, "heal")
                return
            if self.skill == "good" and "shield" not in me["cooldowns"] and me["stamina"] >= 15 and now % 90 == 0:
                e.submit(self.idx, "shield")
                return
        if any(q[0] <= now + 8 for q in self.queue):                      # eine Abwehr steht an: nicht in einen Schlag hineinlaufen (Sperrzeit)
            return
        # Ziel: Heiler/Beschwörer zuerst (nur „good“), sonst der erste Lebende
        want = self.pick_target(v, e)
        if want != me["focus"] and want < 6:
            e.submit(self.idx, f"target_{want + 1}")
        if "light" not in me["cooldowns"] and me["stamina"] >= 8:
            e.submit(self.idx, "light")

    def pick_target(self, v: dict[str, Any], e: LiveEncounter) -> int:
        opp = v["opponents"]
        alive = [i for i, o in enumerate(opp) if o["alive"]]
        if not alive:
            return 0
        if self.skill == "good":
            priority = [i for i in alive if any(a in ("mend", "call_pack", "call_imps") for a in self.abilities_of(e, i))]
            if priority:
                return priority[0]
        return alive[0]

    @staticmethod
    def abilities_of(e: LiveEncounter, i: int) -> list[str]:
        sim = e._sim
        return sim.es[i].base_abil if i < len(sim.es) else []


def fight(cfg: dict[str, Any], opponents: list[str], levels: list[int], skill: str, spawn: str, day: int = 1, max_ticks: int = 3000) -> Outcome:
    abilities = [roll_abilities(cfg, t, f"{spawn}-{k}", day) for k, t in enumerate(opponents)]
    e = LiveEncounter(cfg, opponents, [{"level": lv} for lv in levels], abilities)
    bots = [Bot(i, skill, "attacker" if i == 0 or len(levels) < 3 and i == 0 else ("support" if i % 2 == 1 and len(levels) >= 2 else "attacker"), len(levels))
            for i in range(len(levels))]
    while not e.done and e.t < max_ticks:
        for ev in e.drain_events():
            if ev["type"] == "telegraph":
                for b in bots:
                    b.plan(ev, opponents, abilities)
        for b in bots:
            b.act(e, e.t)
        e.advance()
    res = e.result
    if res is None:                                                     # Zeitlimit des Werkzeugs
        for b in bots:
            e.submit(b.idx, "flee")
        e.advance()
        res = e.result
    maxes = [1000 + 20 * lv for lv in levels]
    lost = [1000 - max(0, p.player_hp) * 1000 // m for p, m in zip(res.players, maxes)]
    return Outcome(res.outcome, res.ticks, lost, sum(1 for p in res.players if p.outcome == "defeat"), max(0, len(res.opponents) - len(opponents)))


def matrix(cfg: dict[str, Any], opponents: list[str], levels: list[int], skill: str, spawns: int = 12, days: tuple[int, ...] = (1,)) -> dict[str, Any]:
    outs = [fight(cfg, opponents, levels, skill, f"sp{i}", d) for i in range(spawns) for d in days]
    n = len(outs)
    wins = [o for o in outs if o.outcome == "victory"]
    return {"n": n, "win": 1000 * len(wins) // n,
            "seconds": (sum(o.ticks for o in outs) // n) // 10,
            "hp_lost": (sum(sum(o.hp_lost) // len(o.hp_lost) for o in wins) // len(wins)) if wins else 1000,
            "deaths": sum(o.deaths for o in outs) * 1000 // (n * len(levels))}


# ---------------------------------------------------------------- Berichte ----
FAMILIES: dict[str, tuple[list[str], int]] = {
    "Wolf": (["wolf"], 5), "Wolfsrudel (2)": (["wolf", "wolf"], 5), "Höhlenbär": (["bear"], 12),
    "Irrlicht + Wolf": (["wisp_healer", "wolf"], 6), "Moorhexe": (["bog_witch"], 9), "Moorhexe + Irrlicht": (["bog_witch", "wisp_healer"], 9),
    "Schattenjäger": (["shadow_hunter"], 11), "Steinwächter": (["stone_warden"], 14), "Totem-Beschwörer": (["totem_caller"], 12),
    "Alpha + 2 Wölfe": (["alpha_wolf", "wolf", "wolf"], 8), "Steinherz-Koloss (Boss)": (["stone_heart_colossus"], 25),
}
RULES_FILE = "sim_rules_v7.json"
SPAWNS = 6


def report(cfg: dict[str, Any]) -> str:
    lines = [
        "# Balancing-Bericht (erzeugt von `python -m mmo_sim.balance write`)",
        "",
        f"Regeln: `{RULES_FILE}`. **Alle Zahlen sind Platzhalter**; die Testspieler (`mmo_sim.balance`) sind vereinfachte Modelle, kein Ersatz für echte Spieltests.",
        "",
        "Testspieler: **novice** schlägt nur leicht zu; **average** reagiert ab 6 Ticks Vorwarnung mit einfachem Ausweichen und verfehlt jeden dritten Versuch; "
        "**good** reagiert ab 3 Ticks, pariert Wuchtschläge und normale Angriffe, weicht Flächenschlägen perfekt aus, unterbricht Zauber/Heiler/Beschwörer und verfehlt jeden fünften Versuch; "
        "in Gruppen heilen und schützen die Spieler 2 und 4. Alle Spieler haben die Stufe der Gegnerfamilie, Gegnerleben wächst mit der Gruppengröße. "
        f"Je Zelle {SPAWNS} verschiedene Spawn-Punkte (andere Zusatzfähigkeiten), Tag 1.",
        "",
        "Zellen: `Sieg ‰ / Dauer / Verlust` (Anteil verlorener Lebenspunkte der Überlebenden in ‰).",
        "",
    ]
    for name, (opp, lvl) in FAMILIES.items():
        lines += [f"## {name} (Stufe {lvl})", "", "| Gruppe | novice | average | good |", "|---|---|---|---|"]
        for n in (1, 2, 3, 4):
            cells = []
            for sk in SKILLS:
                m = matrix(cfg, opp, [lvl] * n, sk, spawns=1 if "Boss" in name else SPAWNS)
                cells.append(f"{m['win']} ‰ / {m['seconds']} s / {m['hp_lost']}")
            lines.append(f"| {n} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    import sys
    from pathlib import Path

    from .rules import load_sim_rules
    if len(argv) != 3 or argv[1] not in ("write", "check"):
        print("python -m mmo_sim.balance write|check <Datei.md>")
        return 2
    text = report(load_sim_rules(RULES_FILE))
    path = Path(argv[2])
    if argv[1] == "write":
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"geschrieben: {path}")
        return 0
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        print(f"ABWEICHUNG: {path}")
        return 1
    print(f"ok: {path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
