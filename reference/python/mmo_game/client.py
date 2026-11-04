"""Headless-Testclient (und Referenz für den Unity-Client): spricht das Zeilen-JSON-Protokoll über asyncio."""
from __future__ import annotations

import asyncio
import json
from typing import Any


class Client:
    def __init__(self, host: str, port: int, account: str) -> None:
        self.host, self.port, self.account = host, port, account
        self.events: list[dict[str, Any]] = []
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._n = 0
        self.state: dict[str, Any] = {}
        self.session = ""

    async def connect(self) -> dict[str, Any]:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        self.writer.write((json.dumps({"cmd": "hello", "account": self.account}) + "\n").encode())
        await self.writer.drain()
        welcome = json.loads(await self.reader.readline())
        self.session = welcome.get("session", "")
        self._task = asyncio.create_task(self._read())
        return welcome

    async def _read(self) -> None:
        while True:
            line = await self.reader.readline()
            if not line:
                return
            msg = json.loads(line)
            if "ev" in msg:
                if msg["ev"] == "state":
                    self.state = msg
                self.events.append(msg)
            elif msg.get("id") in self._pending:
                self._pending.pop(msg["id"]).set_result(msg)

    async def call(self, cmd: str, **args: Any) -> dict[str, Any]:
        self._n += 1
        rid = f"{self.account}-{self._n}"
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        self.writer.write((json.dumps({"v": 1, "id": rid, "cmd": cmd, "args": args}) + "\n").encode())
        await self.writer.drain()
        return await asyncio.wait_for(fut, timeout=10)

    async def close(self) -> None:
        self._task.cancel()
        self.writer.close()

    def seen(self, ev: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["ev"] == ev]
