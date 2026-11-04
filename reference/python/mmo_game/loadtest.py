"""Lastmessung ohne Netzwerk (AP 14, ADR-0053): N Bots laufen im selben Prozess gegen den Spielserver.

Gemessen wird die Dauer eines Ticks (Budget: 100 ms bei 10 Ticks/s) und der Speicher. Die Bots laufen zufällig herum, kämpfen und
nutzen gelegentlich Abfragen, wie echte Clients. Reine Messung: kein Zustand wird gespeichert.

    python -m mmo_game.loadtest 50 600        # 50 Bots, 600 Ticks
"""
from __future__ import annotations

import random
import statistics
import sys
import time
import tracemalloc
from typing import Any

from .game import GameServer

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (0, 0)]


def run(bots: int = 20, ticks: int = 300, seed: int = 1, measure_memory: bool = False) -> dict[str, Any]:
    rng = random.Random(seed)
    g = GameServer()
    sess = []
    for i in range(bots):
        name = f"bot{i:04d}"
        sid, _ = g.connect(name)
        g.handle(sid, {"v": 1, "id": "j", "cmd": "game.join", "args": {"char": name}})
        sess.append((name, sid))
    if measure_memory:
        tracemalloc.start()
    times: list[float] = []
    for t in range(ticks):
        for name, sid in sess:
            if rng.random() < 0.05:
                dx, dy = rng.choice(DIRS)
                g.handle(sid, {"v": 1, "id": f"m{t}", "cmd": "game.move", "args": {"char": name, "dx": dx, "dy": dy}})
            if name in g.fight_of and t % 8 == 0:
                g.handle(sid, {"v": 1, "id": f"f{t}", "cmd": "game.fight", "args": {"char": name, "input": "light"}})
            if rng.random() < 0.01:
                g.handle(sid, {"v": 1, "id": f"q{t}", "cmd": "query.inventory", "args": {"char": name}})
        t0 = time.perf_counter()
        g.tick()
        times.append((time.perf_counter() - t0) * 1000)
        for _, sid in sess:
            g.drain(sid)
    mem = None
    if measure_memory:
        mem = tracemalloc.get_traced_memory()[1] / 1e6
        tracemalloc.stop()
    times.sort()
    return {"bots": bots, "ticks": ticks, "p50_ms": round(statistics.median(times), 2), "p95_ms": round(times[int(len(times) * 0.95) - 1], 2),
            "max_ms": round(times[-1], 2), "fights": len(g.fights), "peak_mb": None if mem is None else round(mem, 1)}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    print(run(n, k))
