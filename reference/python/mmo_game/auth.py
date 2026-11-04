"""Konten und Anmeldung des Spielservers (nur Standardbibliothek). Siehe ADR-0029.

* Passwörter werden nie gespeichert: pro Konto ein zufälliges Salz und PBKDF2-HMAC-SHA256 (Durchläufe konfigurierbar).
* Anmeldung und Registrierung sind pro Adresse und pro Konto begrenzt (Sperre nach Fehlversuchen); unbekannte Konten und falsche
  Passwörter sehen für den Client gleich aus (gleiche Meldung, gleicher Rechenaufwand).
* Nach erfolgreicher Anmeldung gibt der Server ein zufälliges Sitzungs-Token aus (kurz gültig, nur als Hash gespeichert, ein Token
  je Konto), mit dem sich der Client nach einem Verbindungsabbruch ohne Passwort wieder anmeldet.
* Die Kontodatei liegt im Datenverzeichnis (Rechte 0600, atomar geschrieben). Alle Zahlen sind Platzhalter.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any, Callable

ACCOUNT_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


class AuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


DEFAULTS: dict[str, int] = {
    "iterations": 200_000, "min_password": 8, "max_password": 128,
    "max_failures": 5, "lock_seconds": 60,               # Fehlversuche je Konto
    "ip_failures": 20, "ip_window_seconds": 300,         # Fehlversuche je Adresse
    "register_per_ip": 5, "register_window_seconds": 3600,
    "token_seconds": 3600,
}


class _Window:
    """Zählt Ereignisse je Schlüssel in einem gleitenden Zeitfenster."""

    def __init__(self, limit: int, seconds: int, clock: Callable[[], float]) -> None:
        self.limit, self.seconds, self.clock = limit, seconds, clock
        self.events: dict[str, list[float]] = {}

    def _prune(self, key: str) -> list[float]:
        now = self.clock()
        kept = [t for t in self.events.get(key, []) if now - t < self.seconds]
        if kept:
            self.events[key] = kept
        else:
            self.events.pop(key, None)
        return kept

    def full(self, key: str) -> bool:
        return len(self._prune(key)) >= self.limit

    def add(self, key: str) -> None:
        self._prune(key)
        self.events.setdefault(key, []).append(self.clock())


class AccountStore:
    def __init__(self, path: str | Path | None = None, options: dict[str, int] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.opt = {**DEFAULTS, **(options or {})}
        self.path = Path(path) if path else None
        self.clock = clock
        self.accounts: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, tuple[str, float]] = {}      # Konto -> (Hash des Tokens, Ablauf)
        self.locked_until: dict[str, float] = {}
        self.failures: dict[str, int] = {}
        self.ip_fail = _Window(self.opt["ip_failures"], self.opt["ip_window_seconds"], clock)
        self.ip_reg = _Window(self.opt["register_per_ip"], self.opt["register_window_seconds"], clock)
        if self.path is not None and self.path.exists():
            self._load()

    # -- Persistenz --------------------------------------------------------------------
    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            if data.get("format") != 1:
                raise ValueError
            accounts = data["accounts"]
            for name, rec in accounts.items():
                if not ACCOUNT_RE.fullmatch(name) or set(rec) != {"salt", "hash", "iterations"}:
                    raise ValueError
                bytes.fromhex(rec["salt"])
                bytes.fromhex(rec["hash"])
            self.accounts = accounts
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise AuthError("corrupt", "Kontodatei unlesbar") from e

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"format": 1, "accounts": self.accounts}, sort_keys=True, separators=(",", ":")))
        os.replace(tmp, self.path)

    # -- Hilfen -------------------------------------------------------------------------
    def _hash(self, password: str, salt: bytes, iterations: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

    def _check_password_shape(self, password: Any) -> str:
        if not isinstance(password, str) or not self.opt["min_password"] <= len(password) <= self.opt["max_password"]:
            raise AuthError("weak_password", f"Passwort muss {self.opt['min_password']}..{self.opt['max_password']} Zeichen lang sein")
        return password

    def _check_name(self, account: Any) -> str:
        if not isinstance(account, str) or not ACCOUNT_RE.fullmatch(account):
            raise AuthError("bad_request", "Ungültiger Kontoname")
        return account

    # -- Registrierung und Anmeldung -------------------------------------------------------
    def register(self, ip: str, account: Any, password: Any) -> str:
        account = self._check_name(account)
        password = self._check_password_shape(password)
        if self.ip_reg.full(ip):
            raise AuthError("rate_limited", "Zu viele Registrierungen von dieser Adresse")
        if account in self.accounts:
            raise AuthError("account_exists", "Konto existiert bereits")
        self.ip_reg.add(ip)
        salt = os.urandom(16)
        self.accounts[account] = {"salt": salt.hex(), "iterations": self.opt["iterations"],
                                  "hash": self._hash(password, salt, self.opt["iterations"]).hex()}
        self._save()
        return self.issue(account)

    def login(self, ip: str, account: Any, password: Any) -> str:
        account = self._check_name(account)
        if not isinstance(password, str) or len(password) > self.opt["max_password"]:
            raise AuthError("auth_failed", "Anmeldung fehlgeschlagen")
        if self.ip_fail.full(ip):
            raise AuthError("locked", "Zu viele Fehlversuche von dieser Adresse")
        if self.locked_until.get(account, 0.0) > self.clock():
            raise AuthError("locked", "Konto vorübergehend gesperrt")
        rec = self.accounts.get(account)
        if rec is None:                                     # gleicher Aufwand wie bei einem echten Konto
            self._hash(password, b"\0" * 16, self.opt["iterations"])
            ok = False
        else:
            ok = hmac.compare_digest(self._hash(password, bytes.fromhex(rec["salt"]), rec["iterations"]).hex(), rec["hash"])
        if not ok:
            self.ip_fail.add(ip)
            if rec is not None:
                n = self.failures.get(account, 0) + 1
                self.failures[account] = n
                if n >= self.opt["max_failures"]:
                    self.locked_until[account] = self.clock() + self.opt["lock_seconds"]
                    self.failures[account] = 0
            raise AuthError("auth_failed", "Anmeldung fehlgeschlagen")
        self.failures.pop(account, None)
        return self.issue(account)

    # -- Sitzungs-Token ----------------------------------------------------------------------
    def issue(self, account: str) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens[account] = (hashlib.sha256(token.encode()).hexdigest(), self.clock() + self.opt["token_seconds"])
        return token

    def resume(self, ip: str, account: Any, token: Any) -> str:
        """Wiederanmeldung mit Token (nach Verbindungsabbruch). Gibt ein frisches Token aus; das alte wird ungültig."""
        account = self._check_name(account)
        if self.ip_fail.full(ip):
            raise AuthError("locked", "Zu viele Fehlversuche von dieser Adresse")
        cur = self.tokens.get(account)
        ok = (isinstance(token, str) and len(token) <= 128 and cur is not None and cur[1] > self.clock()
              and hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), cur[0]))
        if not ok:
            self.ip_fail.add(ip)
            raise AuthError("auth_failed", "Anmeldung fehlgeschlagen")
        return self.issue(account)

    def revoke(self, account: str) -> None:
        self.tokens.pop(account, None)
