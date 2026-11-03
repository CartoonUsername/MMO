"""Befehls-Gateway: prüft, begrenzt und führt Spielerbefehle aus. Siehe ADR-0019 und docs/PROTOCOL.md.

Pipeline je Nachricht (Reihenfolge ist Teil des Vertrags):
 1 Größe/JSON -> 2 Hülle (`v`, `id`, `cmd`, `args`) -> 3 Sitzung -> 4 Befehl bekannt -> 5 Argumente (genau die Schlüssel, Typen)
 -> 6 Berechtigung (handelnde Figur gehört zur Sitzung) -> 7 Idempotenz (gleiche Anfrage-ID = gleiche Antwort, ohne erneute
 Ausführung) -> 8 Ratenlimit -> 9 Ausführung in der Welt (Einzelschreiber) -> 10 Antwort + Audit.
Die Antwort enthält nie Ausnahmetexte als Vertrag: `code` ist maßgeblich, `message` nur für Menschen. Zeit ist die Serveruhr
(`clock()` in Ticks); der Client liefert nie Zeit oder Fortschritt.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from importlib import resources
from typing import Any, Callable

from mmo_cee.errors import CEEError
from mmo_world.errors import WorldError
from mmo_world.persistence import PersistenceError
from mmo_world.world import World

from .protocol import COMMANDS, Command

ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
CODES = ("ok", "bad_request", "unsupported_version", "unknown_session", "unknown_command", "forbidden", "duplicate_conflict",
         "rate_limited", "rejected", "rejected_by_rules", "server_error")


def load_protocol_rules(name: str = "protocol_rules_v1.json") -> dict[str, Any]:
    return json.loads(resources.files("mmo_server").joinpath("data", name).read_text(encoding="utf-8"))


def _canon(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fail(req_id: Any, code: str, message: str) -> dict[str, Any]:
    return {"v": 1, "id": req_id if isinstance(req_id, str) else None, "ok": False, "error": {"code": code, "message": message}}


class Sessions:
    """Server-seitige Sitzungen: Konto und die ihm gehörenden Figuren. (Anmeldung/Token-Prüfung ist Sache der Transportschicht;
    hier zählt nur, wem eine Sitzung gehört.)"""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def open(self, account_id: str, characters: list[str]) -> str:
        if not isinstance(account_id, str) or not ID_RE.fullmatch(account_id) or not characters:
            raise ValueError("Konto und mindestens eine Figur erforderlich")
        self._counter += 1
        sid = f"sess-{self._counter:08d}"
        self._sessions[sid] = {"account": account_id, "characters": frozenset(characters)}
        return sid

    def close(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def get(self, session_id: Any) -> dict[str, Any] | None:
        return self._sessions.get(session_id) if isinstance(session_id, str) else None


class Gateway:
    def __init__(self, world: World, sessions: Sessions, clock: Callable[[], int], rules: dict[str, Any] | None = None) -> None:
        self.world, self.sessions, self.clock = world, sessions, clock
        self.rules = rules or load_protocol_rules()
        self._seen: dict[str, OrderedDict[str, tuple[str, dict[str, Any]]]] = {}  # Konto -> Anfrage-ID -> (Fingerabdruck, Antwort)
        self._buckets: dict[tuple[str, str], list[int]] = {}  # (Figur, Gruppe) -> [Marken, letzter Tick]
        self.audit: list[dict[str, Any]] = []
        self._audit_head = "0" * 64

    # -- Hilfen ------------------------------------------------------------------------------------
    def _check_type(self, value: Any, code: str) -> bool:
        kind = code.rstrip("?")
        if kind == "s":
            return isinstance(value, str) and 1 <= len(value) <= self.rules["max_string_length"]
        if kind == "i":
            return isinstance(value, int) and not isinstance(value, bool) and abs(value) <= 10**12
        if kind == "b":
            return isinstance(value, bool)
        return False

    def _validate_args(self, cmd: Command, args: Any) -> str | None:
        if not isinstance(args, dict):
            return "args muss ein Objekt sein"
        required = {k for k, t in cmd.args.items() if not t.endswith("?")}
        extra, missing = set(args) - set(cmd.args), required - set(args)
        if extra or missing:
            return f"Felder unzulässig: {sorted(extra)}, fehlend: {sorted(missing)}"
        for k, v in args.items():
            if not self._check_type(v, cmd.args[k]):
                return f"Feld {k} hat den falschen Typ oder Wertebereich"
        return None

    def _take_token(self, character: str, group: str) -> bool:
        cfg = self.rules["rate"].get(group, self.rules["rate"]["default"])
        now = self.clock()
        marks, last = self._buckets.get((character, group), [cfg["capacity"], now])
        marks = min(cfg["capacity"], marks + max(0, now - last) * cfg["refill_per_tick"])
        ok = marks >= 1
        self._buckets[(character, group)] = [marks - 1 if ok else marks, now]
        return ok

    def _log(self, session: dict[str, Any] | None, req: Any, cmd: str, resp: dict[str, Any]) -> None:
        entry = {"tick": self.clock(), "account": session["account"] if session else None,
                 "id": req.get("id") if isinstance(req, dict) else None, "cmd": cmd,
                 "code": "ok" if resp["ok"] else resp["error"]["code"], "prev": self._audit_head}
        entry["hash"] = hashlib.sha256(_canon(entry).encode()).hexdigest()
        self._audit_head = entry["hash"]
        self.audit.append(entry)
        if len(self.audit) > self.rules["audit_limit"]:
            del self.audit[0]

    # -- Eingang -------------------------------------------------------------------------------------
    def handle(self, session_id: str, raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        req: Any = None
        cmd_name = "?"
        try:
            if isinstance(raw, (str, bytes)):
                if len(raw) > self.rules["max_message_bytes"]:
                    resp = _fail(None, "bad_request", "Nachricht zu groß")
                    self._log(session, None, cmd_name, resp)
                    return resp
                req = json.loads(raw)
            else:
                req = raw
            resp = self._process(session, req)
            cmd_name = req.get("cmd") if isinstance(req, dict) and isinstance(req.get("cmd"), str) else "?"
        except (ValueError, UnicodeDecodeError):
            resp = _fail(None, "bad_request", "Kein gültiges JSON")
        self._log(session, req, cmd_name, resp)
        return resp

    def _process(self, session: dict[str, Any] | None, req: Any) -> dict[str, Any]:
        if not isinstance(req, dict) or set(req) - {"v", "id", "cmd", "args"} or not {"v", "id", "cmd"} <= set(req):
            return _fail(req.get("id") if isinstance(req, dict) else None, "bad_request", "Hülle: v, id, cmd, args erwartet")
        rid = req["id"]
        if not isinstance(rid, str) or not ID_RE.fullmatch(rid):
            return _fail(None, "bad_request", "id muss 1-64 Zeichen [A-Za-z0-9_-] sein")
        if not isinstance(req["cmd"], str):
            return _fail(rid, "bad_request", "cmd muss eine Zeichenkette sein")
        if req["v"] != self.rules["protocol_version"]:
            return {**_fail(rid, "unsupported_version", "Protokollversion wird nicht unterstützt"),
                    "supported": [self.rules["protocol_version"]]}
        if session is None:
            return _fail(rid, "unknown_session", "Keine gültige Sitzung")
        cmd = COMMANDS.get(req["cmd"])
        if cmd is None:
            return _fail(rid, "unknown_command", "Unbekannter Befehl")
        args = req.get("args", {})
        problem = self._validate_args(cmd, args)
        if problem:
            return _fail(rid, "bad_request", problem)
        actor = args[cmd.actor] if cmd.actor else None
        if actor is not None and actor not in session["characters"]:
            return _fail(rid, "forbidden", "Die Figur gehört nicht zu dieser Sitzung")
        fp = _canon({"cmd": cmd.name, "args": args})
        seen = self._seen.setdefault(session["account"], OrderedDict())
        if cmd.mutating and rid in seen:
            old_fp, old = seen[rid]
            if old_fp != fp:
                return _fail(rid, "duplicate_conflict", "Anfrage-ID wurde mit anderem Inhalt verwendet")
            return {**old, "replayed": True}
        bucket_owner = actor if actor is not None else session["account"]
        if not self._take_token(bucket_owner, cmd.rate_group):
            return _fail(rid, "rate_limited", "Zu viele Anfragen")
        try:
            result = cmd.call(self.world, args)
            resp = {"v": 1, "id": rid, "ok": True, "result": result}
        except WorldError as e:
            resp = _fail(rid, "rejected", str(e))
        except CEEError as e:  # RuleViolation, IntegrityError, RulesVersionMismatch
            resp = _fail(rid, "rejected_by_rules", str(e))
        except PersistenceError as e:
            resp = _fail(rid, "server_error", str(e))
        except Exception:  # Programmierfehler: keine Details an den Client; der Betrieb muss den Zustand prüfen (siehe PROTOCOL.md)
            resp = _fail(rid, "server_error", "Interner Fehler")
        if cmd.mutating:  # auch Ablehnungen werden gemerkt: ein wiederholter Versuch ändert nichts mehr
            seen[rid] = (fp, resp)
            while len(seen) > self.rules["idempotency_window"]:
                seen.popitem(last=False)
        return resp

    def audit_ok(self) -> bool:
        prev = None
        for e in self.audit:
            body = {k: v for k, v in e.items() if k != "hash"}
            if hashlib.sha256(_canon(body).encode()).hexdigest() != e["hash"] or (prev is not None and e["prev"] != prev):
                return False
            prev = e["hash"]
        return True
