"""Transport des Spielservers: TCP mit zeilenweisem JSON (UTF-8, eine Nachricht je Zeile). Siehe ADR-0028 und docs/VERTICAL_SLICE.md.

Ablauf: Der Client verbindet sich und sendet als erste Zeile eine Anmeldung (mit Konten, `auth` gesetzt):
  {"cmd":"register","account":"anna","password":"…"}   neues Konto            -> welcome mit "token"
  {"cmd":"hello","account":"anna","password":"…"}      Anmeldung             -> welcome mit "token"
  {"cmd":"hello","account":"anna","token":"…"}         Wiederanmeldung       -> welcome mit neuem "token"
Danach gelten die Befehle des Protokolls (`game.*` und die Weltbefehle). Fehler: `{"ev":"error","code":…}` und Verbindungsende.
Ohne `auth` (nur Entwicklung, `--insecure-dev`) genügt `{"cmd":"hello","account":"anna"}`. Nicht-lokale Adressen verlangen Konten
und TLS (siehe `serve`).
"""
from __future__ import annotations

import asyncio
import json
import signal
import ssl
from pathlib import Path
from typing import Any

from mmo_world.persistence import Store

from .auth import AccountStore, AuthError
from .game import MAX_LINE, GameServer

TICK_SECONDS = 0.1
MAX_CONNECTIONS = 16
MAX_PER_IP = 4
LOOPBACK = ('127.0.0.1', '::1', 'localhost')


class NetServer:
    def __init__(self, game: GameServer | None = None, host: str = "127.0.0.1", port: int = 7777, tick_seconds: float = TICK_SECONDS,
                 store: Store | None = None, autosave_ticks: int = 600, auth: AccountStore | None = None,
                 ssl_context: ssl.SSLContext | None = None, max_per_ip: int = MAX_PER_IP) -> None:
        self.game, self.host, self.port, self.tick_seconds = game or GameServer(), host, port, tick_seconds
        self.store, self.autosave_ticks, self.auth, self.ssl, self.max_per_ip = store, autosave_ticks, auth, ssl_context, max_per_ip
        if host not in LOOPBACK and (auth is None or ssl_context is None):
            raise ValueError("Nicht-lokale Adressen verlangen Konten (auth) und TLS (ssl_context)")
        self._ips: dict[str, int] = {}
        self._writers: dict[str, asyncio.StreamWriter] = {}
        self._server: asyncio.AbstractServer | None = None
        self._ticker: asyncio.Task[None] | None = None

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._client, self.host, self.port, limit=MAX_LINE * 2, ssl=self.ssl)
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

    def _authenticate(self, ip: str, hello: dict[str, Any]) -> tuple[Any, str | None]:
        """Prüft die erste Nachricht; Rückgabe: (Konto, Token oder None ohne Konten). Wirft AuthError."""
        if self.auth is None:
            if hello.get("cmd") != "hello":
                raise AuthError("bad_hello", "hello erwartet")
            return hello.get("account"), None
        cmd, account = hello.get("cmd"), hello.get("account")
        if cmd == "register":
            return account, self.auth.register(ip, account, hello.get("password"))
        if cmd == "hello" and "token" in hello:
            return account, self.auth.resume(ip, account, hello["token"])
        if cmd == "hello":
            return account, self.auth.login(ip, account, hello.get("password"))
        raise AuthError("bad_hello", "register oder hello erwartet")

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        sid: str | None = None
        peer = writer.get_extra_info("peername")
        ip = str(peer[0]) if peer else "?"
        counted = False
        try:
            if len(self._writers) >= MAX_CONNECTIONS or self._ips.get(ip, 0) >= self.max_per_ip:
                await self._send(writer, {"ev": "error", "code": "server_full"})
                return
            self._ips[ip] = self._ips.get(ip, 0) + 1
            counted = True
            line = await asyncio.wait_for(reader.readline(), timeout=10)
            try:
                hello = json.loads(line)
                if not isinstance(hello, dict):
                    raise AuthError("bad_hello", "hello erwartet")
                account, token = self._authenticate(ip, hello)
                old = next((x for x in list(self._writers) if (self.game.sessions.get(x) or {}).get("account") == account), None)
                if old is not None:                               # neue Anmeldung verdrängt die alte Verbindung
                    self._writers[old].close()
                    self.game.disconnect(old)
                    self._writers.pop(old, None)
                sid, chars = self.game.connect(account)
            except AuthError as e:
                await self._send(writer, {"ev": "error", "code": e.code, "message": e.message})
                return
            except (ValueError, TypeError) as e:
                await self._send(writer, {"ev": "error", "code": "bad_hello", "message": str(e) or "hello erwartet"})
                return
            self._writers[sid] = writer
            welcome = {"ev": "welcome", "session": sid, "characters": chars, "tick": self.game.tick_no}
            if token is not None:
                welcome["token"] = token
            await self._send(writer, welcome)
            while True:
                line = await reader.readline()
                if not line:
                    break
                if len(line) > MAX_LINE:
                    await self._send(writer, {"ev": "error", "code": "bad_request", "message": "Nachricht zu groß"})
                    break
                await self._send(writer, self.game.handle(sid, line.decode("utf-8", errors="replace")))
        except (asyncio.TimeoutError, ConnectionError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ssl.SSLError):
            pass
        finally:
            if counted:
                self._ips[ip] = max(0, self._ips.get(ip, 1) - 1)
            if sid is not None and self._writers.get(sid) is writer:
                self._writers.pop(sid, None)
                self.game.disconnect(sid)
            writer.close()


async def serve(host: str = "127.0.0.1", port: int = 7777, data: str | None = None, insecure_dev: bool = False,
                cert: str | None = None, key: str | None = None) -> None:
    store = Store(data) if data else None
    game = GameServer.load(store) if store is not None and store.current() is not None else GameServer()
    auth = None if insecure_dev else AccountStore(Path(data) / "accounts.json" if data else None)
    ctx = None
    if cert and key:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
    srv = NetServer(game, host=host, port=port, store=store, auth=auth, ssl_context=ctx)
    p = await srv.start()
    mode = ("ohne Konten (nur Entwicklung)" if auth is None else "mit Konten") + (", TLS" if ctx else ", ohne TLS")
    print(f"Spielserver läuft auf {host}:{p} ({mode})" + (f", Speicher: {data}" if data else ", ohne Speicherung"), flush=True)
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


def _arg(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    port = int(args[0]) if args and args[0].isdigit() else 7777
    try:
        asyncio.run(serve(_arg(args, "--host") or "127.0.0.1", port, _arg(args, "--data"), "--insecure-dev" in args,
                          _arg(args, "--cert"), _arg(args, "--key")))
    except KeyboardInterrupt:
        pass
