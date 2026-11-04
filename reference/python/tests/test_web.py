"""Tests für den Browser-Testclient: WebSocket (RFC 6455), HTTP-Auslieferung, Herkunftsprüfung und Rauchtest im echten Browser (ADR-0036)."""
import asyncio
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mmo_game import ws
from mmo_game.auth import AccountStore
from mmo_game.net import NetServer

HERE = Path(__file__).parent
KEY = b"\x01\x02\x03\x04"


class FrameTests(unittest.TestCase):
    def test_rfc_beispiel_accept(self):
        self.assertEqual(ws.accept_key("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")   # Beispiel aus RFC 6455 §1.3

    def test_rfc_beispiel_maskierter_rahmen(self):
        raw = bytes([0x81, 0x85, 0x37, 0xfa, 0x21, 0x3d, 0x7f, 0x9f, 0x4d, 0x51, 0x58])   # „Hello“, maskiert (RFC 6455 §5.7)
        self.assertEqual(ws.encode_frame(ws.OP_TEXT, b"Hello", bytes([0x37, 0xfa, 0x21, 0x3d])), raw)

    def _read(self, data: bytes, limit: int = 100):
        class W:
            def __init__(s): s.out = b""
            def write(s, d): s.out += d
            async def drain(s): pass
        w = W()

        async def run():
            r = asyncio.StreamReader()
            r.feed_data(data)
            r.feed_eof()
            return await ws.read_message(r, w, limit)
        return asyncio.run(run()), w.out

    def test_laengen_und_fragmente(self):
        for n in (0, 125, 126, 300):
            msg, _ = self._read(ws.encode_frame(ws.OP_TEXT, b"a" * n, KEY), 1000)
            self.assertEqual(msg, "a" * n)
        f1 = bytes([0x01, 0x83]) + KEY + bytes(b ^ KEY[i % 4] for i, b in enumerate(b"abc"))      # Text ohne FIN
        f2 = ws.encode_frame(ws.OP_CONT, b"def", KEY)
        self.assertEqual(self._read(f1 + f2)[0], "abcdef")

    def test_ping_wird_beantwortet_close_endet(self):
        msg, out = self._read(ws.encode_frame(ws.OP_PING, b"x", KEY) + ws.encode_frame(ws.OP_TEXT, b"hi", KEY))
        self.assertEqual((msg, out), ("hi", ws.encode_frame(ws.OP_PONG, b"x")))
        msg, out = self._read(ws.encode_frame(ws.OP_CLOSE, struct.pack(">H", 1000), KEY))
        self.assertIsNone(msg)
        self.assertEqual(out[0], 0x88)

    def test_fehlerfaelle(self):
        cases = {
            "unmaskiert": (ws.encode_frame(ws.OP_TEXT, b"hi"), 1002),
            "reserviertes Bit": (bytes([0xC1, 0x80]) + KEY, 1002),
            "zu groß": (ws.encode_frame(ws.OP_TEXT, b"a" * 101, KEY), 1009),
            "binär": (ws.encode_frame(ws.OP_BIN, b"a", KEY), 1003),
            "kein UTF-8": (ws.encode_frame(ws.OP_TEXT, b"\xff\xfe", KEY), 1007),
            "Fortsetzung ohne Anfang": (ws.encode_frame(ws.OP_CONT, b"a", KEY), 1002),
            "unbekannter Opcode": (ws.encode_frame(3, b"a", KEY), 1002),
            "Steuerrahmen zu lang": (ws.encode_frame(ws.OP_PING, b"a" * 126, KEY), 1002),
            "Summe der Fragmente zu groß": (bytes([0x01, 0xE4]) + KEY + bytes(b ^ KEY[i % 4] for i, b in enumerate(b"a" * 100))
                                            + ws.encode_frame(ws.OP_CONT, b"a" * 10, KEY), 1009),
        }
        for name, (data, code) in cases.items():
            with self.subTest(name), self.assertRaises(ws.WsError) as cm:
                self._read(data)
            self.assertEqual(cm.exception.code, code)

    def test_riesige_laenge_wird_nicht_gelesen(self):
        data = bytes([0x81, 0xFF]) + struct.pack(">Q", 1 << 40) + KEY                 # 1 TiB angekündigt, nichts folgt
        with self.assertRaises(ws.WsError) as cm:
            self._read(data)
        self.assertEqual(cm.exception.code, 1009)


class WsClient:
    def __init__(self, reader, writer):
        self.r, self.w = reader, writer

    @classmethod
    async def open(cls, port, path="/ws", origin="same", extra=""):
        r, w = await asyncio.open_connection("127.0.0.1", port)
        host = f"127.0.0.1:{port}"
        head = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n"
        if origin == "same":
            head += f"Origin: http://{host}\r\n"
        elif origin:
            head += f"Origin: {origin}\r\n"
        w.write((head + extra + "\r\n").encode())
        await w.drain()
        status = (await r.readline()).decode()
        hdrs = {}
        while (line := await r.readline()) not in (b"\r\n", b""):
            k, _, v = line.decode().partition(":")
            hdrs[k.strip().lower()] = v.strip()
        return cls(r, w), status, hdrs

    async def send(self, obj):
        self.w.write(ws.encode_frame(ws.OP_TEXT, json.dumps(obj).encode(), KEY))
        await self.w.drain()

    async def recv(self):
        b0, b1 = await asyncio.wait_for(self.r.readexactly(2), 5)
        n = b1 & 0x7F
        if n == 126:
            (n,) = struct.unpack(">H", await self.r.readexactly(2))
        data = await self.r.readexactly(n)
        return b0 & 0x0F, data

    async def msg(self):
        op, data = await self.recv()
        self.last_op = op
        return json.loads(data) if op == ws.OP_TEXT else data


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.srv = NetServer(port=0, tick_seconds=0.02, auth=AccountStore(Path(self.tmp.name) / "a.json"))
        self.port = await self.srv.start()

    async def asyncTearDown(self):
        await self.srv.stop()
        self.tmp.cleanup()

    async def http(self, request: bytes) -> bytes:
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write(request)
        await w.drain()
        data = await asyncio.wait_for(r.read(), 5)
        w.close()
        return data

    async def test_seite_und_gesundheit(self):
        page = await self.http(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        self.assertTrue(page.startswith(b"HTTP/1.1 200"))
        self.assertIn(b"Content-Security-Policy", page)
        self.assertIn(b"no-store", page)
        self.assertIn(b"MMO Testclient", page)
        self.assertTrue((await self.http(b"GET /health HTTP/1.1\r\nHost: x\r\n\r\n")).endswith(b"ok"))
        self.assertTrue((await self.http(b"GET /etc/passwd HTTP/1.1\r\nHost: x\r\n\r\n")).startswith(b"HTTP/1.1 404"))
        self.assertTrue((await self.http(b"GET /../../x HTTP/1.1\r\nHost: x\r\n\r\n")).startswith(b"HTTP/1.1 404"))

    async def test_zu_viele_header(self):
        req = b"GET / HTTP/1.1\r\n" + b"".join(b"X-%d: a\r\n" % i for i in range(60)) + b"\r\n"
        self.assertTrue((await self.http(req)).startswith(b"HTTP/1.1 431"))
        self.assertTrue((await self.http(b"GET / HTTP/1.1\r\nX: " + b"a" * 9000 + b"\r\n\r\n")).startswith(b"HTTP/1.1 431"))

    async def test_upgrade_pruefungen(self):
        _, status, _ = await WsClient.open(self.port, origin="http://boese.example")
        self.assertIn("403", status)
        c, status, h = await WsClient.open(self.port, origin=None)       # ohne Origin (Nicht-Browser-Client) erlaubt
        self.assertIn("101", status)
        self.assertEqual(h["sec-websocket-accept"], "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")
        c.w.close()
        r = await self.http(b"GET /ws HTTP/1.1\r\nHost: x\r\n\r\n")      # kein Upgrade
        self.assertTrue(r.startswith(b"HTTP/1.1 400"))
        r = await self.http(b"GET /ws HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: abc\r\nSec-WebSocket-Version: 8\r\n\r\n")
        self.assertTrue(r.startswith(b"HTTP/1.1 400"))            # falsche Protokollversion

    async def test_anmeldung_und_spiel_ueber_websocket(self):
        a, status, _ = await WsClient.open(self.port)
        self.assertIn("101", status)
        await a.send({"cmd": "register", "account": "anna", "password": "passwort123"})
        w = await a.msg()
        self.assertEqual((w["ev"], w["characters"]), ("welcome", ["anna"]))
        await a.send({"v": 1, "id": "1", "cmd": "game.join", "args": {"char": "anna"}})
        j = await a.msg()
        self.assertTrue(j["ok"])
        self.assertEqual(j["result"]["you"]["pos"], [500, 500])
        await a.send({"v": 1, "id": "2", "cmd": "game.move", "args": {"char": "anna", "dx": 1, "dy": 0}})
        got = []
        for _ in range(30):                                                  # Antwort und Zustandsereignisse in beliebiger Reihenfolge
            m = await a.msg()
            got.append(m)
            if m.get("id") == "2":
                break
        self.assertTrue(any(m.get("id") == "2" and m["ok"] for m in got))
        await asyncio.sleep(0.5)
        await a.send({"v": 1, "id": "3", "cmd": "game.state", "args": {"char": "anna"}})
        while (m := await a.msg()).get("id") != "3":
            pass
        self.assertGreater(m["result"]["you"]["pos"][0], 500)
        a.w.close()

    async def _call(self, c, n, cmd, **args):
        await c.send({"v": 1, "id": f"x{n}", "cmd": cmd, "args": args})
        while (m := await c.msg()).get("id") != f"x{n}":
            pass
        return m

    async def test_fenster_gruppe_handel_herstellen_befehle(self):
        """Dieselben Befehle wie die Fenster im Browserclient (Gruppe, Handel, Herstellen), inklusive verständlicher Ablehnung."""
        cs = {}
        for name in ("anna", "ben"):
            c, _, _ = await WsClient.open(self.port)
            await c.send({"cmd": "register", "account": name, "password": "passwort123"})
            await c.msg()
            await self._call(c, 0, "game.join", char=name)
            cs[name] = c
        a, b = cs["anna"], cs["ben"]
        self.assertTrue((await self._call(a, 1, "party.form", char="anna"))["ok"])
        self.assertTrue((await self._call(a, 2, "party.invite", char="anna", target="ben"))["ok"])
        inv = (await self._call(b, 3, "query.party_invites", char="ben"))["result"]
        self.assertEqual([i["from"] for i in inv], ["anna"])
        self.assertTrue((await self._call(b, 4, "party.accept", char="ben", invite=inv[0]["id"]))["ok"])
        v = (await self._call(a, 5, "query.party", char="anna"))["result"]
        self.assertEqual((v["leader"], sorted(v["members"])), ("anna", ["anna", "ben"]))
        self.assertTrue((await self._call(b, 6, "party.leave", char="ben"))["ok"])
        # Handel: Kaufangebot hinterlegt Münzen; Gegenseite sieht es und lehnt ab
        o = await self._call(a, 7, "trade.offer", char="anna", to="ben", side="buy", item_key="iron_ore@standard", qty=2, price=20)
        self.assertTrue(o["ok"], o)
        seen = (await self._call(b, 8, "query.offers", char="ben"))["result"]["incoming"]
        self.assertEqual([(x["from"], x["qty"], x["price"]) for x in seen], [("anna", 2, 20)])
        self.assertTrue((await self._call(b, 9, "trade.decline", char="ben", offer=seen[0]["id"]))["ok"])
        self.assertEqual((await self._call(a, 10, "query.offers", char="anna"))["result"]["outgoing"], [])
        # Herstellen ohne Zutaten: abgelehnt, mit Meldung statt Absturz
        r = await self._call(a, 11, "craft", char="anna", recipe="iron_ingot", qty=1, grade="standard")
        self.assertFalse(r["ok"])
        self.assertTrue(r["error"]["message"])
        for c in cs.values():
            c.w.close()

    async def test_charakter_sicht_und_klassenwahl(self):
        c, _, _ = await WsClient.open(self.port)
        await c.send({"cmd": "register", "account": "anna", "password": "passwort123"})
        await c.msg()
        await self._call(c, 0, "game.join", char="anna")
        v = (await self._call(c, 1, "query.character", char="anna"))["result"]
        self.assertEqual((v["identity"]["base_class"], v["essence"]["form"], v["identity"]["level"]), (None, "human", 1))
        self.assertEqual(sorted(v["classes"]), ["archer", "shaman_alchemist", "warrior"])
        self.assertEqual(set(v["elements"]["affinity"]), {"fire", "water", "shadow", "light", "wind", "earth", "electric", "ice", "nature"})
        self.assertEqual([m["type"] for m in v["layers"]["life_story"]["milestones"]], ["identity.created"])
        self.assertTrue((await self._call(c, 2, "character.choose_class", char="anna", base_class="warrior"))["ok"])
        self.assertEqual((await self._call(c, 3, "query.character", char="anna"))["result"]["identity"]["base_class"], "warrior")
        v2 = (await self._call(c, 3, "query.character", char="anna"))["result"]["layers"]
        self.assertEqual([m["type"] for m in v2["life_story"]["milestones"]], ["identity.created", "identity.class_chosen"])
        self.assertEqual(v2["essence_identity"]["base_class"], "warrior")
        again = await self._call(c, 4, "character.choose_class", char="anna", base_class="archer")      # dauerhaft
        self.assertFalse(again["ok"])
        self.assertFalse((await self._call(c, 5, "character.choose_class", char="anna", base_class="paladin"))["ok"])
        c.w.close()

    def test_client_enthaelt_fenster_und_nur_bekannte_befehle(self):
        import re
        from mmo_server.protocol import COMMANDS
        html = (Path(__file__).parent.parent / "mmo_game" / "web" / "index.html").read_text(encoding="utf-8")
        for marker in ("onCanvasClick", "profession_detail", "findPath", 'id="bGather"'):          # Klick-Bewegung mit Wegfindung und Sammeln-Knopf
            self.assertIn(marker, html)
        for fid in ("wChar", "wParty", "wTrade", "wCraft"):
            self.assertIn(f'id="{fid}"', html)
        used = set(re.findall(r'(?:call|act)\((?:"[A-Za-z]+",)?"((?:party|trade|craft|query|maker)[A-Za-z_.]*)"', html))
        self.assertTrue({"party.form", "trade.offer", "craft", "query.offers", "query.party"} <= used, used)
        known = set(COMMANDS) if not isinstance(COMMANDS, dict) else set(COMMANDS)
        self.assertEqual(used - known, set())

    async def test_zwei_spieler_sehen_sich(self):
        cs = []
        for name in ("anna", "ben"):
            c, _, _ = await WsClient.open(self.port)
            await c.send({"cmd": "register", "account": name, "password": "passwort123"})
            await c.msg()
            await c.send({"v": 1, "id": "j", "cmd": "game.join", "args": {"char": name}})
            while (await c.msg()).get("id") != "j":
                pass
            cs.append(c)
        seen = False
        for _ in range(50):
            m = await cs[0].msg()
            if m.get("ev") == "state" and any(p["char"] == "ben" for p in m["players"]):
                seen = True
                break
        self.assertTrue(seen)
        for c in cs:
            c.w.close()

    async def test_falsches_passwort_und_schlechte_nachrichten(self):
        a, _, _ = await WsClient.open(self.port)
        await a.send({"cmd": "hello", "account": "niemand", "password": "passwort123"})
        self.assertEqual((await a.msg())["code"], "auth_failed")
        b, _, _ = await WsClient.open(self.port)
        b.w.write(ws.encode_frame(ws.OP_BIN, b"x", KEY))                    # Binärdaten statt Text
        await b.w.drain()
        op, data = await b.recv()
        self.assertEqual(op, ws.OP_CLOSE)
        self.assertEqual(struct.unpack(">H", data[:2])[0], 1003)
        c, _, _ = await WsClient.open(self.port)
        await c.send({"cmd": "register", "account": "x" * 3 + "yz", "password": "passwort123"})
        await c.msg()
        c.w.write(ws.encode_frame(ws.OP_TEXT, b"x" * 5000, KEY))            # größer als MAX_LINE
        await c.w.drain()
        op, data = await c.recv()
        self.assertEqual(op, ws.OP_CLOSE)
        self.assertEqual(struct.unpack(">H", data[:2])[0], 1009)

    async def test_verdraengung_ueber_zeilen_und_websocket(self):
        a, _, _ = await WsClient.open(self.port)
        await a.send({"cmd": "register", "account": "anna", "password": "passwort123"})
        await a.msg()
        from mmo_game.client import Client
        cl = Client("127.0.0.1", self.port, "anna", "passwort123")
        w = await cl.connect()
        self.assertEqual(w["ev"], "welcome")
        await asyncio.sleep(0.2)
        self.assertEqual(len(self.srv._writers), 1)
        await cl.close()


class ProxyTests(unittest.IsolatedAsyncioTestCase):
    async def _two(self, trust):
        with tempfile.TemporaryDirectory() as tmp:
            srv = NetServer(port=0, tick_seconds=0.05, auth=AccountStore(Path(tmp) / "a.json"), max_per_ip=1, trust_proxy=trust)
            port = await srv.start()
            res = []
            cs = []
            for i, name in enumerate(("anna", "ben")):
                try:
                    c, _, _ = await WsClient.open(port, extra=f"X-Forwarded-For: 10.0.0.{i + 1}\r\n")
                except (ConnectionError, asyncio.IncompleteReadError):          # Grenze je Adresse: Verbindung wird abgelehnt
                    res.append("error")
                    continue
                await c.send({"cmd": "register", "account": name, "password": "passwort123"})
                res.append((await c.msg()).get("ev"))
                cs.append(c)
            for c in cs:
                c.w.close()
            await srv.stop()
            return res

    async def test_hinter_proxy_zaehlt_echte_adresse(self):
        self.assertEqual(await self._two(True), ["welcome", "welcome"])

    async def test_ohne_vertrauen_wird_header_ignoriert(self):
        self.assertEqual(await self._two(False), ["welcome", "error"])      # beide gelten als 127.0.0.1, Grenze 1


def _have_browser() -> bool:
    if not shutil.which("node"):
        return False
    try:
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=20).stdout.strip()
        return subprocess.run(["node", "-e", "require('playwright')"], env={**os.environ, "NODE_PATH": npm_root}, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class BrowserSmoke(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(_have_browser(), "node/playwright nicht verfügbar")
    async def test_zwei_browser_spieler(self):
        with tempfile.TemporaryDirectory() as tmp:
            srv = NetServer(port=0, tick_seconds=0.1, auth=AccountStore(Path(tmp) / "a.json"), max_per_ip=8)
            port = await srv.start()
            npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
            proc = await asyncio.create_subprocess_exec("node", str(HERE / "browser" / "smoke.js"), str(port),
                                                        env={**os.environ, "NODE_PATH": npm_root},
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(proc.communicate(), 90)
            await srv.stop()
            self.assertEqual(proc.returncode, 0, (out + err).decode())
            self.assertIn("OK", out.decode())


if __name__ == "__main__":
    unittest.main()
