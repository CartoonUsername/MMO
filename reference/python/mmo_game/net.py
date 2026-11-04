"""Transport des Spielservers: TCP mit zeilenweisem JSON (UTF-8, eine Nachricht je Zeile). Siehe ADR-0028 und docs/VERTICAL_SLICE.md.

Ablauf: Der Client verbindet sich, sendet `{"cmd":"hello","account":"<name>"}` und erhält `{"ev":"welcome",...}`; danach gelten
die Befehle des Protokolls (`game.*` und die Weltbefehle). Antworten haben `ok`, Ereignisse (`ev`) schiebt der Server selbst.
Entwicklungsstufe: keine Verschlüsselung und keine Passwörter, daher standardmäßig nur auf 127.0.0.1.
"""
from __future__ import annotations

import asyncio
import json
import signal
from typing import Any

from mmo_world.persistence import Store

from .game import MAX_LINE, GameServer

TICK_SECONDS = 0.1
MAX_CONNECTIONS = 16


class NetServer:
    def __init__(self, game: GameServer | None = None, host: str = "127.0.0.1", port: int = 7777, tick_seconds: float = TICK_SECONDS,
                 store: Store | None = None, autosave_ticks: int = 600) -> None:
        self.game, self.host, self.port, self.tick_seconds = game or GameServer(), host, port, tick_seconds
        self.store, self.autosave_ticks = store, autosave_ticks
        self._writers: dict[str, asyncio.StreamWriter] = {}
        self._server: asyncio.AbstractServer | None = None
        self._ticker: asyncio.Task[None] | None = None

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._client, self.host, self.port, limit=MAX_LINE * 2)
        self.port = self._server.sockets[0].getsockname()[1]
        self._ticker = asyncio.create_task(self._tick_loop())
        return self.port

    async def stop(self) -> None:
        if self._ticker:
            self._ticker.cancel()
        if self.store is not None:
            self.game.save(self.store)                         # beim Beenden speichern
        for w in list(self._writers.values()):
            w.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    @staticmethod
    async def _send(w: asyncio.StreamWriter, obj: dict[str, Any]) -> None:
        w.write((json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8"))
        try:
            await w.drain()
        except ConnectionError:
            pass

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self.tick_seconds)
            self.game.tick()
            if self.store is not None and self.autosave_ticks and self.game.tick_no % self.autosave_ticks == 0:
                self.game.save(self.store)
                self.store.prune(5)
            for sid, w in list(self._writers.items()):
                for ev in self.game.drain(sid):
                    await self._send(w, ev)

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        sid: str | None = None
        try:
            if len(self._writers) >= MAX_CONNECTIONS:
                await self._send(writer, {"ev": "error", "code": "server_full"})
                return
            line = await asyncio.wait_for(reader.readline(), timeout=10)
            try:
                hello = json.loads(line)
                if not isinstance(hello, dict) or hello.get("cmd") != "hello":
                    raise ValueError
                sid, chars = self.game.connect(hello.get("account"))
            except (ValueError, TypeError) as e:
                await self._send(writer, {"ev": "error", "code": "bad_hello", "message": str(e) or "hello erwartet"})
                return
            self._writers[sid] = writer
            await self._send(writer, {"ev": "welcome", "session": sid, "characters": chars, "tick": self.game.tick_no})
            while True:
                line = await reader.readline()
                if not line:
                    break
                if len(line) > MAX_LINE:
                    await self._send(writer, {"ev": "error", "code": "bad_request", "message": "Nachricht zu groß"})
                    break
                await self._send(writer, self.game.handle(sid, line.decode("utf-8", errors="replace")))
        except (asyncio.TimeoutError, ConnectionError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            pass
        finally:
            if sid is not None:
                self._writers.pop(sid, None)
                self.game.disconnect(sid)
            writer.close()


async def serve(host: str = "127.0.0.1", port: int = 7777, data: str | None = None) -> None:
    store = Store(data) if data else None
    game = GameServer.load(store) if store is not None and store.current() is not None else GameServer()
    srv = NetServer(game, host=host, port=port, store=store)
    p = await srv.start()
    print(f"Spielserver läuft auf {host}:{p} (Entwicklungsstufe, ohne Verschlüsselung)" + (f", Speicher: {data}" if data else ", ohne Speicherung"), flush=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)          # geordnetes Beenden: speichern, dann schließen
        except (NotImplementedError, RuntimeError):         # z. B. Windows
            pass
    try:
        await stop.wait()
    finally:
        await srv.stop()


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    data = args[args.index("--data") + 1] if "--data" in args else None
    port = int(args[0]) if args and args[0].isdigit() else 7777
    try:
        asyncio.run(serve("127.0.0.1", port, data))
    except KeyboardInterrupt:
        pass
