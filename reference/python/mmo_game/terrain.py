"""Gelände und Kollision (ganzzahlig, deterministisch). Siehe ADR-0030.

* Die Zone besteht aus einer Grundart (`default`) und übereinander gelegten Rechtecken (`regions`, spätere überdecken frühere).
  Jede Geländeart hat einen Tempofaktor in Promille; 0 = nicht begehbar (Wasser, Fels).
* Hindernisse (`obstacles`) sind Kreise (Bäume, Felsen), nicht begehbar.
* Die Figur ist ein Kreis mit `player_radius`: Begehbarkeit eines Punktes heißt, dass der Kreis nichts Blockierendes berührt.
* Bewegung: Schritt mit dem Tempo des Geländes unter der Figur; Kollision durch Gleiten entlang einer Achse; Schritte sind kürzer als jedes
  Hindernis dick ist (wird beim Laden geprüft), damit nichts durchtunnelt wird.
Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

from typing import Any

from mmo_sim.errors import SimError


class TerrainError(SimError):
    pass


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


class Terrain:
    def __init__(self, cfg: dict[str, Any], zone: dict[str, Any], speed: int) -> None:
        self.w, self.h, self.radius = zone["width"], zone["height"], cfg["player_radius"]
        self.kinds: dict[str, int] = cfg["kinds"]
        self.default: str = cfg["default"]
        self.regions: list[tuple[str, tuple[int, int, int, int]]] = [(r["kind"], tuple(r["rect"])) for r in cfg["regions"]]  # type: ignore[misc]
        self.obstacles: list[tuple[int, int, int]] = [(o["at"][0], o["at"][1], o["r"]) for o in cfg["obstacles"]]
        self.speed = speed
        self._validate(cfg)

    def _validate(self, cfg: dict[str, Any]) -> None:
        if not _is_int(self.radius) or self.radius < 1 or not self.kinds or self.default not in self.kinds:
            raise TerrainError("terrain: player_radius/kinds/default ungültig")
        if any(not _is_int(f) or not 0 <= f <= 3000 for f in self.kinds.values()) or self.kinds[self.default] == 0:
            raise TerrainError("terrain: Tempofaktoren 0..3000, Grundart muss begehbar sein")
        longest = self.speed * max(self.kinds.values()) // 1000
        for kind, (x1, y1, x2, y2) in self.regions:
            if kind not in self.kinds or not all(_is_int(v) for v in (x1, y1, x2, y2)) or not (0 <= x1 < x2 <= self.w and 0 <= y1 < y2 <= self.h):
                raise TerrainError("terrain: Gebiet ungültig")
            if self.kinds[kind] == 0 and min(x2 - x1, y2 - y1) <= longest:
                raise TerrainError("terrain: blockierendes Gebiet dünner als ein Schritt")
        for (x, y, r), o in zip(self.obstacles, cfg["obstacles"]):
            if not (_is_int(x) and _is_int(y) and _is_int(r)) or r * 2 <= longest or not (0 <= x <= self.w and 0 <= y <= self.h):
                raise TerrainError("terrain: Hindernis ungültig oder dünner als ein Schritt")
            if o.get("kind") not in self.kinds or self.kinds[o["kind"]] != 0:
                raise TerrainError("terrain: Hindernisart muss blockieren")

    # -- Abfragen ----------------------------------------------------------------------
    def kind_at(self, x: int, y: int) -> str:
        kind = self.default
        for k, (x1, y1, x2, y2) in self.regions:
            if x1 <= x <= x2 and y1 <= y <= y2:
                kind = k
        return kind

    def speed_permille(self, x: int, y: int) -> int:
        return self.kinds[self.kind_at(x, y)]

    def blocked(self, x: int, y: int) -> bool:
        """Berührt die Figur (Kreis mit Radius) bei (x, y) etwas Blockierendes oder den Zonenrand? Geprüft werden der Mittelpunkt und
        acht Punkte auf dem Kreisrand (achsenparallele Gebiete werden dadurch sicher erkannt)."""
        r = self.radius
        if x < r or y < r or x > self.w - r or y > self.h - r:
            return True
        d = r * 707 // 1000
        for ox, oy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r), (d, d), (d, -d), (-d, d), (-d, -d)):
            if self.kinds[self.kind_at(x + ox, y + oy)] == 0:
                return True
        for cx, cy, cr in self.obstacles:
            if (x - cx) ** 2 + (y - cy) ** 2 < (cr + r) ** 2:
                return True
        return False

    def clear_line(self, a: tuple[int, int], b: tuple[int, int], step: int = 50) -> bool:
        """Sichtlinie/Weg: Punkte entlang der Strecke (alle `step` cm) sind nicht blockiert (die Endpunkte zählen nicht mit)."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = max(abs(dx), abs(dy)) // step
        for i in range(1, n):
            x, y = a[0] + dx * i // n, a[1] + dy * i // n
            if self.blocked(x, y):
                return False
        return True

    # -- Bewegung ----------------------------------------------------------------------
    def step(self, pos: tuple[int, int], dx: int, dy: int) -> tuple[int, int]:
        s = self.speed * self.speed_permille(*pos) // 1000
        if dx and dy:
            s = s * 707 // 1000
        for cand in ((pos[0] + dx * s, pos[1] + dy * s), (pos[0] + dx * s, pos[1]), (pos[0], pos[1] + dy * s)):
            if cand != pos and not self.blocked(*cand):
                return cand
        return pos

    def nearest_walkable(self, pos: tuple[int, int], step: int = 50, limit: int = 3000) -> tuple[int, int]:
        """Der nächste begehbare Punkt in Ringen um `pos` (Reihenfolge fest: nach Abstand, dann x, dann y)."""
        x0, y0 = pos
        if not self.blocked(x0, y0):
            return pos
        for d in range(step, limit + 1, step):
            ring = [(x0 + dx, y0 + dy) for dx in range(-d, d + 1, step) for dy in range(-d, d + 1, step) if max(abs(dx), abs(dy)) == d]
            ring.sort(key=lambda p: ((p[0] - x0) ** 2 + (p[1] - y0) ** 2, p[0], p[1]))
            for p in ring:
                if not self.blocked(*p):
                    return p
        raise TerrainError("kein begehbarer Punkt gefunden")

    def export(self) -> dict[str, Any]:
        """Statische Karte für Clients (Darstellung); die Regeln der Begehbarkeit bleiben beim Server."""
        return {"w": self.w, "h": self.h, "default": self.default, "kinds": self.kinds,
                "regions": [{"kind": k, "rect": list(r)} for k, r in self.regions],
                "obstacles": [{"at": [x, y], "r": r} for x, y, r in self.obstacles], "player_radius": self.radius}
