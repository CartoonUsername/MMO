import asyncio
import json
import os
import shutil
import ssl
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from mmo_game import GameServer
from mmo_game.auth import ACCOUNT_RE, AccountStore, AuthError
from mmo_game.client import Client
from mmo_game.net import NetServer

FAST = {"iterations": 1000}


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def store(clock=None, path=None, **opt):
    return AccountStore(path, {**FAST, **opt}, clock or FakeClock())


def code(fn, *a):
    try:
        fn(*a)
    except AuthError as e:
        return e.code
    return None


class AccountTests(unittest.TestCase):
    def test_register_login_and_wrong_password(self):
        s = store()
        t = s.register("1.1.1.1", "anna", "geheim-passwort")
        self.assertTrue(t)
        self.assertTrue(s.login("1.1.1.1", "anna", "geheim-passwort"))
        self.assertEqual(code(s.login, "1.1.1.1", "anna", "falsches-passwort"), "auth_failed")
        self.assertEqual(code(s.login, "1.1.1.1", "niemand", "geheim-passwort"), "auth_failed")      # unbekanntes Konto: gleiche Meldung

    def test_password_length_limits_are_inclusive(self):
        s = store()
        s.register("ip", "a1", "x" * 8)
        s.register("ip", "a2", "y" * 128)
        self.assertEqual(code(s.register, "ip", "a3", "z" * 7), "weak_password")
        self.assertEqual(code(s.register, "ip", "a3", "z" * 129), "weak_password")
        self.assertTrue(s.login("ip", "a2", "y" * 128))
        self.assertEqual(code(s.login, "ip", "a2", "y" * 129), "auth_failed")

    def test_unknown_accounts_cost_the_same_hashing_work(self):
        s = store()
        s.register("ip", "anna", "geheim-passwort")
        calls = []
        real = s._hash
        s._hash = lambda *a: calls.append(a) or real(*a)
        code(s.login, "ip", "anna", "falsch-falsch")
        known = len(calls)
        code(s.login, "ip", "niemand", "falsch-falsch")
        self.assertEqual((known, len(calls) - known), (1, 1))

    def test_a_lock_expires_with_a_fresh_failure_count(self):
        clock = FakeClock()
        s = store(clock, max_failures=3, lock_seconds=10, ip_failures=100)
        s.register("ip", "anna", "geheim-passwort")
        for _ in range(3):
            code(s.login, "ip", "anna", "falsch-falsch")
        clock.t += 10
        self.assertEqual(code(s.login, "ip", "anna", "falsch-falsch"), "auth_failed")        # ein Fehlversuch, nicht sofort wieder gesperrt
        self.assertTrue(s.login("ip", "anna", "geheim-passwort"))

    def test_tokens_are_long_and_random(self):
        s = store()
        tokens = {s.register("ip", f"a{i}", "geheim-passwort") for i in range(5)}
        self.assertEqual(len(tokens), 5)
        self.assertTrue(all(len(t) >= 43 for t in tokens))

    def test_revoke_invalidates_a_valid_token(self):
        s = store()
        t = s.register("ip", "anna", "geheim-passwort")
        s.revoke("anna")
        self.assertEqual(code(s.resume, "ip", "anna", t), "auth_failed")
        s.revoke("anna")                                                                      # zweimal ist harmlos
        self.assertTrue(s.login("ip", "anna", "geheim-passwort"))

    def test_passwords_are_never_stored(self):
        s = store()
        s.register("1.1.1.1", "anna", "geheim-passwort")
        s.register("1.1.1.1", "ben", "geheim-passwort")
        rec_a, rec_b = s.accounts["anna"], s.accounts["ben"]
        self.assertNotIn("geheim-passwort", json.dumps(s.accounts))
        self.assertNotEqual(rec_a["salt"], rec_b["salt"])                    # eigenes Salz
        self.assertNotEqual(rec_a["hash"], rec_b["hash"])                    # gleiches Passwort, anderer Hash
        self.assertEqual(len(bytes.fromhex(rec_a["salt"])), 16)
        self.assertEqual(rec_a["iterations"], 1000)

    def test_registration_rules(self):
        s = store()
        self.assertEqual(code(s.register, "ip", "anna", "kurz"), "weak_password")
        self.assertEqual(code(s.register, "ip", "anna", "x" * 129), "weak_password")
        self.assertEqual(code(s.register, "ip", "anna", 12345678), "weak_password")
        self.assertEqual(code(s.register, "ip", "anna", None), "weak_password")
        for bad in ("", "a b", None, 5, "x" * 65, "ä"):
            self.assertEqual(code(s.register, "ip", bad, "geheim-passwort"), "bad_request", bad)
        s.register("ip", "anna", "geheim-passwort")
        self.assertEqual(code(s.register, "ip", "anna", "anderes-passwort"), "account_exists")
        self.assertEqual(code(s.login, "ip", "anna", "anderes-passwort"), "auth_failed")      # Registrierung überschreibt nichts
        self.assertTrue(ACCOUNT_RE.fullmatch("a_b-1"))

    def test_account_lockout_after_failures_and_unlock(self):
        clock = FakeClock()
        s = store(clock, max_failures=3, lock_seconds=60, ip_failures=100)
        s.register("1.1.1.1", "anna", "geheim-passwort")
        for _ in range(3):
            self.assertEqual(code(s.login, "2.2.2.2", "anna", "falsch-falsch"), "auth_failed")
        self.assertEqual(code(s.login, "3.3.3.3", "anna", "geheim-passwort"), "locked")        # auch mit richtigem Passwort
        clock.t += 59
        self.assertEqual(code(s.login, "3.3.3.3", "anna", "geheim-passwort"), "locked")
        clock.t += 1
        self.assertTrue(s.login("3.3.3.3", "anna", "geheim-passwort"))

    def test_failures_reset_after_success(self):
        s = store(max_failures=3, ip_failures=100)
        s.register("1.1.1.1", "anna", "geheim-passwort")
        for _ in range(2):
            code(s.login, "ip", "anna", "falsch-falsch")
        s.login("ip", "anna", "geheim-passwort")
        for _ in range(2):
            code(s.login, "ip", "anna", "falsch-falsch")
        self.assertTrue(s.login("ip", "anna", "geheim-passwort"))                            # noch nicht gesperrt

    def test_ip_lockout_and_window(self):
        clock = FakeClock()
        s = store(clock, ip_failures=3, ip_window_seconds=100, max_failures=100)
        s.register("1.1.1.1", "anna", "geheim-passwort")
        for i in range(3):
            code(s.login, "9.9.9.9", f"x{i}", "falsch-falsch")
        self.assertEqual(code(s.login, "9.9.9.9", "anna", "geheim-passwort"), "locked")
        self.assertTrue(s.login("8.8.8.8", "anna", "geheim-passwort"))                       # andere Adresse unberührt
        clock.t += 100
        self.assertTrue(s.login("9.9.9.9", "anna", "geheim-passwort"))

    def test_registration_rate_limit_per_address(self):
        clock = FakeClock()
        s = store(clock, register_per_ip=2, register_window_seconds=60)
        s.register("ip", "a1", "geheim-passwort")
        s.register("ip", "a2", "geheim-passwort")
        self.assertEqual(code(s.register, "ip", "a3", "geheim-passwort"), "rate_limited")
        s.register("other", "a3", "geheim-passwort")
        clock.t += 60
        s.register("ip", "a4", "geheim-passwort")

    def test_tokens_resume_expire_and_are_single(self):
        clock = FakeClock()
        s = store(clock, token_seconds=100)
        t1 = s.register("ip", "anna", "geheim-passwort")
        t2 = s.resume("ip", "anna", t1)
        self.assertNotEqual(t1, t2)
        self.assertEqual(code(s.resume, "ip", "anna", t1), "auth_failed")                    # altes Token ungültig
        t3 = s.login("ip", "anna", "geheim-passwort")
        self.assertEqual(code(s.resume, "ip", "anna", t2), "auth_failed")                    # ein Token je Konto
        clock.t += 99
        t4 = s.resume("ip", "anna", t3)
        clock.t += 100
        self.assertEqual(code(s.resume, "ip", "anna", t4), "auth_failed")                    # abgelaufen
        s.revoke("anna")
        self.assertEqual(code(s.resume, "ip", "anna", t4), "auth_failed")
        for bad in (None, 5, "", "x" * 200):
            self.assertEqual(code(s.resume, "ip", "anna", bad), "auth_failed")
        self.assertEqual(code(s.resume, "ip", "niemand", "x"), "auth_failed")

    def test_tokens_are_stored_hashed_only(self):
        s = store()
        t = s.register("ip", "anna", "geheim-passwort")
        self.assertNotIn(t, json.dumps(list(s.tokens.values())))
        self.assertEqual(len(s.tokens["anna"][0]), 64)

    def test_wrong_tokens_count_towards_the_address_limit(self):
        s = store(ip_failures=2)
        s.register("ip0", "anna", "geheim-passwort")
        code(s.resume, "evil", "anna", "a")
        code(s.resume, "evil", "anna", "b")
        self.assertEqual(code(s.resume, "evil", "anna", "c"), "locked")

    def test_file_persistence_permissions_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "accounts.json"
            s = store(path=path)
            s.register("ip", "anna", "geheim-passwort")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertFalse(path.with_name("accounts.json.tmp").exists())
            s2 = store(path=path)
            self.assertTrue(s2.login("ip", "anna", "geheim-passwort"))
            self.assertEqual(s2.tokens.get("anna") is not None, True)
            for bad in ("kaputt", "[]", json.dumps({"format": 2, "accounts": {}}),
                        json.dumps({"format": 1, "accounts": {"a b": {"salt": "00", "hash": "00", "iterations": 1}}}),
                        json.dumps({"format": 1, "accounts": {"anna": {"salt": "zz", "hash": "00", "iterations": 1}}}),
                        json.dumps({"format": 1, "accounts": {"anna": {"salt": "00"}}})):
                path.write_text(bad)
                with self.assertRaises(AuthError):
                    store(path=path)

    def test_passwords_with_unicode_work(self):
        s = store()
        s.register("ip", "anna", "pässwörd-日本語-1")
        self.assertTrue(s.login("ip", "anna", "pässwörd-日本語-1"))
        self.assertEqual(code(s.login, "ip", "anna", "passwoerd-日本語-1"), "auth_failed")


class NetAuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.auth = AccountStore(None, {**FAST, "max_failures": 3})
        self.srv = NetServer(port=0, tick_seconds=0.002, auth=self.auth)
        self.port = await self.srv.start()

    async def asyncTearDown(self):
        await self.srv.stop()

    async def raw(self, obj):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write((json.dumps(obj) + "\n").encode())
        await w.drain()
        line = await asyncio.wait_for(r.readline(), 3)
        w.close()
        return json.loads(line) if line else None

    async def test_register_then_login_then_resume(self):
        a = Client("127.0.0.1", self.port, "anna", password="geheim-passwort", register=True)
        w = await a.connect()
        self.assertEqual(w["ev"], "welcome")
        self.assertTrue(w["token"])
        self.assertTrue((await a.call("game.join", char="anna"))["ok"])
        await a.close()
        b = Client("127.0.0.1", self.port, "anna", password="geheim-passwort")
        w2 = await b.connect()
        self.assertEqual(w2["ev"], "welcome")
        self.assertNotEqual(w2["token"], w["token"])
        tok = b.token
        await b.close()
        c = Client("127.0.0.1", self.port, "anna", token=tok)
        w3 = await c.connect()
        self.assertEqual(w3["ev"], "welcome")
        self.assertNotEqual(c.token, tok)                                            # Token wurde erneuert
        await c.close()
        d = Client("127.0.0.1", self.port, "anna", token=tok)
        self.assertEqual((await d.connect())["code"], "auth_failed")                 # altes Token ungültig

    async def test_bad_logins_and_malformed_hellos(self):
        self.assertEqual((await self.raw({"cmd": "hello", "account": "anna", "password": "x"}))["code"], "auth_failed")
        self.assertEqual((await self.raw({"cmd": "hello", "account": "anna"}))["code"], "auth_failed")        # weder Passwort noch Token
        self.assertEqual((await self.raw({"cmd": "register", "account": "anna", "password": "kurz"}))["code"], "weak_password")
        self.assertEqual((await self.raw({"cmd": "frobnicate", "account": "anna"}))["code"], "bad_hello")
        self.assertEqual((await self.raw([1, 2]))["code"], "bad_hello")
        self.assertEqual((await self.raw({"cmd": "hello", "account": "a b", "password": "geheim-passwort"}))["code"], "bad_request")
        self.assertEqual((await self.raw({"cmd": "register", "account": "anna", "password": "geheim-passwort"}))["ev"], "welcome")
        self.assertEqual((await self.raw({"cmd": "register", "account": "anna", "password": "geheim-passwort"}))["code"], "account_exists")

    async def test_game_commands_need_authentication(self):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write(b'{"v":1,"id":"x","cmd":"game.join","args":{"char":"anna"}}\n')
        await w.drain()
        out = json.loads(await asyncio.wait_for(r.readline(), 3))
        self.assertEqual(out["ev"], "error")
        self.assertEqual(await asyncio.wait_for(r.readline(), 3), b"")               # Verbindung geschlossen
        self.assertNotIn("anna", self.srv.game.players)
        w.close()

    async def test_lockout_over_the_network(self):
        await self.raw({"cmd": "register", "account": "anna", "password": "geheim-passwort"})
        for _ in range(3):
            await self.raw({"cmd": "hello", "account": "anna", "password": "falsch-falsch"})
        out = await self.raw({"cmd": "hello", "account": "anna", "password": "geheim-passwort"})
        self.assertEqual(out["code"], "locked")

    async def test_a_new_login_replaces_the_old_connection(self):
        a = Client("127.0.0.1", self.port, "anna", password="geheim-passwort", register=True)
        await a.connect()
        await a.call("game.join", char="anna")
        b = Client("127.0.0.1", self.port, "anna", password="geheim-passwort")
        self.assertEqual((await b.connect())["ev"], "welcome")
        await asyncio.sleep(0.1)
        self.assertEqual(len([s for s in self.srv._writers]), 1)
        self.assertTrue((await b.call("game.join", char="anna"))["ok"])
        with self.assertRaises((ConnectionError, asyncio.TimeoutError, asyncio.IncompleteReadError)):
            await a.call("game.state", char="anna")                                  # alte Verbindung ist zu
        await b.close()

    async def test_connections_per_address_are_limited(self):
        srv = NetServer(port=0, tick_seconds=0.002, auth=self.auth, max_per_ip=2)
        port = await srv.start()
        conns = [await asyncio.open_connection("127.0.0.1", port) for _ in range(2)]
        r, w = await asyncio.open_connection("127.0.0.1", port)
        self.assertEqual(json.loads(await asyncio.wait_for(r.readline(), 3))["code"], "server_full")
        for _, ww in conns + [(r, w)]:
            ww.close()
        await asyncio.sleep(0.1)
        r2, w2 = await asyncio.open_connection("127.0.0.1", port)           # Plätze sind wieder frei
        w2.write(b'{"cmd":"hello","account":"x","password":"y"}\n')
        await w2.drain()
        self.assertEqual(json.loads(await asyncio.wait_for(r2.readline(), 3))["code"], "auth_failed")
        w2.close()
        await srv.stop()


class SecurityConfigTests(unittest.TestCase):
    def test_non_loopback_requires_accounts_and_tls(self):
        with self.assertRaises(ValueError):
            NetServer(host="0.0.0.0", port=0)
        with self.assertRaises(ValueError):
            NetServer(host="0.0.0.0", port=0, auth=AccountStore(None, FAST))
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        with self.assertRaises(ValueError):
            NetServer(host="0.0.0.0", port=0, ssl_context=ctx)
        NetServer(host="0.0.0.0", port=0, auth=AccountStore(None, FAST), ssl_context=ctx)
        NetServer(host="127.0.0.1", port=0)


@unittest.skipUnless(shutil.which("openssl"), "openssl nicht verfügbar")
class TlsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(d / "k.pem"), "-out", str(d / "c.pem"),
                        "-days", "1", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                       check=True, capture_output=True)
        sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        sctx.load_cert_chain(d / "c.pem", d / "k.pem")
        self.cert = d / "c.pem"
        self.srv = NetServer(port=0, tick_seconds=0.002, auth=AccountStore(None, FAST), ssl_context=sctx)
        self.port = await self.srv.start()

    async def asyncTearDown(self):
        await self.srv.stop()
        self.tmp.cleanup()

    async def test_login_over_tls_and_plain_connection_fails(self):
        cctx = ssl.create_default_context(cafile=str(self.cert))
        c = Client("127.0.0.1", self.port, "anna", password="geheim-passwort", register=True, ssl=cctx)
        self.assertEqual((await c.connect())["ev"], "welcome")
        self.assertTrue((await c.call("game.join", char="anna"))["ok"])
        await c.close()
        r, w = await asyncio.open_connection("127.0.0.1", self.port)                 # Klartext gegen TLS-Server
        w.write(b'{"cmd":"hello","account":"x","password":"geheim-passwort"}\n')
        try:
            await w.drain()
            out = await asyncio.wait_for(r.read(100), 3)
        except (ConnectionError, asyncio.TimeoutError):
            out = b""
        self.assertNotIn(b"welcome", out)
        w.close()
        untrusting = ssl.create_default_context()                                    # unbekanntes Zertifikat wird abgelehnt
        with self.assertRaises(ssl.SSLError):
            await asyncio.open_connection("127.0.0.1", self.port, ssl=untrusting)


if __name__ == "__main__":
    unittest.main()
