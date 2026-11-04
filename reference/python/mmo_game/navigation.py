"""Wegfindung auf dem Gelände (A* auf einem Raster, ganzzahlig, deterministisch). Siehe ADR-0031.

* Raster aus Zellen von `cell` cm; eine Zelle ist begehbar, wenn die Figur in ihrer Mitte nicht blockiert ist.
* Kosten: 10 (gerade) bzw. 14 (diagonal) mal Mittel der Zellkosten (Zellkosten = 10 000 / Tempofaktor, ganzzahlig, ohne Rundung weiter); Diagonalen schneiden keine Ecken.
* Reihenfolge fest (Nachbarn in fester Reihenfolge, Gleichstand nach Zellnummer), damit gleiche Eingaben gleiche Wege ergeben.
Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import heapq

from .terrain import Terrain

NEIGHBOURS = ((1, 0, 10), (-1, 0, 10), (0, 1, 10), (0, -1, 10), (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14))


class Navigator:
    def __init__(self, terrain: Terrain, cell: int = 100, max_nodes: int = 8000) -> None:
        self.t, self.cell, self.max_nodes = terrain, cell, max_nodes
        self.cols = -(-terrain.w // cell)
        self.rows = -(-terrain.h // cell)
        self.cost: list[int | None] = []                       # Kosten je Zelle (None = blockiert), Index = y * cols + x
        for cy in range(self.rows):
            for cx in range(self.cols):
                px, py = self.center((cx, cy))
                f = None if terrain.blocked(px, py) else terrain.speed_permille(px, py)
                self.cost.append(None if not f else 10_000 // f)       # Straße 7, Gras 10, Matsch 16 (je 10 cm)
        self.min_cost = min(c for c in self.cost if c is not None)

    def center(self, c: tuple[int, int]) -> tuple[int, int]:
        return min(c[0] * self.cell + self.cell // 2, self.t.w), min(c[1] * self.cell + self.cell // 2, self.t.h)

    def cell_of(self, p: tuple[int, int]) -> tuple[int, int]:
        return min(max(p[0] // self.cell, 0), self.cols - 1), min(max(p[1] // self.cell, 0), self.rows - 1)

    def passable(self, c: tuple[int, int]) -> bool:
        return 0 <= c[0] < self.cols and 0 <= c[1] < self.rows and self.cost[c[1] * self.cols + c[0]] is not None

    def nearest_passable(self, c: tuple[int, int], limit: int = 6) -> tuple[int, int] | None:
        if self.passable(c):
            return c
        for d in range(1, limit + 1):
            ring = [(c[0] + dx, c[1] + dy) for dx in range(-d, d + 1) for dy in range(-d, d + 1) if max(abs(dx), abs(dy)) == d]
            ring.sort(key=lambda q: ((q[0] - c[0]) ** 2 + (q[1] - c[1]) ** 2, q))
            for q in ring:
                if self.passable(q):
                    return q
        return None

    def find_path(self, a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]] | None:
        """Wegpunkte (Zellmitten) von `a` nach `b`, ohne den Start, mit `b` selbst als letztem Punkt; [] wenn schon da, None ohne Weg."""
        s, g = self.nearest_passable(self.cell_of(a)), self.nearest_passable(self.cell_of(b))
        if s is None or g is None:
            return None
        if s == g:
            return [b]
        cols, mc = self.cols, self.min_cost

        def h(c: tuple[int, int]) -> int:
            dx, dy = abs(c[0] - g[0]), abs(c[1] - g[1])
            return mc * 2 * (10 * max(dx, dy) + 4 * min(dx, dy))        # Kosten in 1/20: exakt, nie überschätzt
        start, goal = s[1] * cols + s[0], g[1] * cols + g[0]
        best = {start: 0}
        came: dict[int, int] = {}
        heap = [(h(s), h(s), start)]
        done: set[int] = set()
        expanded = 0
        while heap:
            _, _, cur = heapq.heappop(heap)
            if cur in done:
                continue
            if cur == goal:
                path = [cur]
                while path[-1] in came:
                    path.append(came[path[-1]])
                cells = [(i % cols, i // cols) for i in reversed(path)][1:]
                pts = [self.center(c) for c in cells]
                return pts[:-1] + [b] if pts else [b]
            done.add(cur)
            expanded += 1
            if expanded > self.max_nodes:
                return None
            cx, cy = cur % cols, cur // cols
            for dx, dy, base in NEIGHBOURS:
                n = (cx + dx, cy + dy)
                if not self.passable(n):
                    continue
                if dx and dy and not (self.passable((cx + dx, cy)) and self.passable((cx, cy + dy))):
                    continue                                         # keine Ecken schneiden
                ni = n[1] * cols + n[0]
                step = base * (self.cost[cur] + self.cost[ni])             # type: ignore[operator]  # ohne Rundung (Einheit 1/20)
                ng = best[cur] + step
                if ng < best.get(ni, 1 << 60):
                    best[ni] = ng
                    came[ni] = cur
                    heapq.heappush(heap, (ng + h(n), h(n), ni))
        return None
