"""Headless-Testclient (und Referenz für den Unity-Client): spricht das Zeilen-JSON-Protokoll über asyncio."""
from __future__ import annotations

import asyncio
import json
from typing import Any


class Client:
    def __init__(self, host: str, port: int, account: str, password: str | None = None, token: str | None = None,
                 register: bool = False, ssl: Any = None) -> None:
        self.host, self.port, self.account = host, port, account
        self.password, self.token, self.register, self.ssl = password, token, register, ssl
        self.events: list[dict[str, Any]] = []
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._n = 0
        self.state: dict[str, Any] = {}
        self.session = ""

    async def connect(self) -> dict[str, Any]:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port, ssl=self.ssl)
        hello: dict[str, Any] = {"cmd": "register" if self.register else "hello", "account": self.account}
        if self.password is not None:
            hello["password"] = self.password
        if self.token is not None:
            hello["token"] = self.token
        self.writer.write((json.dumps(hello) + "\n").encode())
        await self.writer.drain()
        line = await self.reader.readline()
        welcome = json.loads(line) if line else {"ev": "error", "code": "closed"}
        self.session = welcome.get("session", "")
        self.token = welcome.get("token", self.token)
        if welcome.get("ev") != "welcome":
            return welcome
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
        task = getattr(self, "_task", None)
        if task is not None:
            task.cancel()
        self.writer.close()

    def seen(self, ev: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["ev"] == ev]
