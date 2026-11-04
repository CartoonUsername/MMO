"""Sicherung und Wiederherstellung des Spielstands (ADR-0037).

Der Spielstand ist ein Dateispeicher (kein Datenbankserver): `Store` schreibt Generationen `gen-NNNNNN/` und schaltet den Zeiger `CURRENT`
atomar um; daneben liegen `game_state.json` (Spielschicht) und `accounts.json` (Konten, enthält Passwort-Hashes – Archiv ist nur für den Besitzer lesbar).

Eine laufende Datei-Kopie wäre nicht konsistent. Deshalb: den Zeiger lesen, die zugehörige Generation und die Nebendateien in ein Zwischenverzeichnis
kopieren, den Zeiger erneut lesen (geändert → Wiederholung), den Stand mit dem echten Lader prüfen (Hash-Ketten), erst dann archivieren und das
Archiv unter dem endgültigen Namen ablegen. Unvollständige Sicherungen tragen den Namen `.partial-*` und gelten nie als Sicherung.

Aufruf: python -m mmo_game.backup create|verify|restore|prune|list ...   (siehe docs/BACKUP_AND_RESTORE.md)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import platform
import re
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from mmo_world.persistence import PersistenceError, Store

FORMAT = 1
NAME_RE = re.compile(r"^mmo-backup-(\d{8}T\d{6}Z)\.tar\.gz$")
SIDE_FILES = ("game_state.json", "accounts.json")
MAX_MEMBERS = 100_000
MAX_UNPACKED = 8 * 1024 ** 3


class BackupError(Exception):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_current(data: Path) -> bytes | None:
    p = data / "CURRENT"
    return p.read_bytes() if p.exists() else None


def _copy_consistent(data: Path, stage: Path, attempts: int = 6) -> tuple[int, str | None]:
    """Kopiert Zeiger, aktuelle Generation und Nebendateien als zusammengehörigen Stand; Rückgabe: (Generation, Hinweis)."""
    last: Exception | None = None
    for i in range(attempts):
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        before = _read_current(data)
        if before is None:
            raise BackupError("Kein Speicherpunkt (CURRENT fehlt) – nichts zu sichern")
        try:
            gen = int(json.loads(before)["generation"])
            shutil.copytree(data / f"gen-{gen:06d}", stage / f"gen-{gen:06d}")
            (stage / "CURRENT").write_bytes(before)
            for name in SIDE_FILES:
                if (data / name).exists():
                    shutil.copy2(data / name, stage / name)
            after = _read_current(data)
            note = None
            gs = stage / "game_state.json"
            if gs.exists():
                try:
                    if json.loads(gs.read_text(encoding="utf-8")).get("generation") != gen:
                        note = "game_state.json gehört zu einer anderen Generation"
                        if after == before and i < attempts - 1:      # Server schreibt gerade: kurz warten und neu versuchen
                            time.sleep(0.4)
                            continue
                except ValueError:
                    note = "game_state.json unlesbar"
            if after == before:
                return gen, note
        except (OSError, ValueError, KeyError) as e:                  # Generation wurde während des Kopierens ersetzt
            last = e
        time.sleep(0.4)
    raise BackupError(f"Kein konsistenter Stand erreicht (Speicherung läuft dauernd?): {last}")


def create(data_dir: str | Path, out_dir: str | Path, extras: list[str | Path] | None = None, note: str = "") -> Path:
    data, out = Path(data_dir), Path(out_dir)
    if not data.is_dir():
        raise BackupError(f"Datenverzeichnis fehlt: {data}")
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final = out / f"mmo-backup-{ts}.tar.gz"
    if final.exists():
        raise BackupError(f"Sicherung existiert schon: {final.name}")
    partial = out / f".partial-{ts}-{os.getpid()}"
    try:
        stage = partial / "payload"
        gen, hint = _copy_consistent(data, stage / "data")
        # Der gesicherte Stand muss mit dem echten Lader ladbar sein (Hash-Ketten, Regel-Hashes, Zustands-Hashes).
        try:
            Store(stage / "data").load(gen)
        except PersistenceError as e:
            raise BackupError(f"Gesicherter Stand besteht die Prüfung nicht: {e}") from e
        for x in extras or []:
            xp = Path(x)
            if xp.is_file():
                (stage / "extra").mkdir(exist_ok=True)
                shutil.copy2(xp, stage / "extra" / xp.name)
        files = {str(p.relative_to(stage)): _sha(p) for p in sorted(stage.rglob("*")) if p.is_file()}
        manifest: dict[str, Any] = {"format": FORMAT, "created": ts, "generation": gen, "files": files, "hint": hint, "note": note,
                                    "host": platform.node(), "python": platform.python_version(), "source": str(data)}
        (stage / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
        tmp_tar = partial / "archive.tar.gz"
        old = os.umask(0o077)
        try:
            with tarfile.open(tmp_tar, "w:gz") as tf:
                for p in sorted(stage.rglob("*")):
                    tf.add(p, arcname=str(p.relative_to(stage)), recursive=False, filter=_norm)
        finally:
            os.umask(old)
        digest = _sha(tmp_tar)
        verify_archive(tmp_tar, digest)                              # das fertige Archiv wird vor dem Ablegen noch einmal gelesen
        os.replace(tmp_tar, final)
        side = final.with_name(final.name + ".sha256")
        side.write_text(f"{digest}  {final.name}\n", encoding="utf-8")
        os.chmod(final, 0o600)
        return final
    finally:
        shutil.rmtree(partial, ignore_errors=True)


def _norm(ti: tarfile.TarInfo) -> tarfile.TarInfo:
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = ""
    ti.mode = 0o700 if ti.isdir() else 0o600
    return ti


def _expected_digest(archive: Path, expected: str | None) -> str:
    if expected:
        return expected.lower()
    side = archive.with_name(archive.name + ".sha256")
    if not side.exists():
        raise BackupError(f"Prüfsummen-Datei fehlt: {side.name}")
    m = re.match(r"^([0-9a-f]{64})\s", side.read_text(encoding="utf-8").lower())
    if not m:
        raise BackupError("Prüfsummen-Datei unlesbar")
    return m.group(1)


def _safe_members(tf: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = tf.getmembers()
    if len(members) > MAX_MEMBERS or sum(m.size for m in members) > MAX_UNPACKED:
        raise BackupError("Archiv zu groß")
    for m in members:
        p = Path(m.name)
        if p.is_absolute() or ".." in p.parts or not (m.isreg() or m.isdir()):
            raise BackupError(f"Unzulässiger Archiveintrag: {m.name!r}")
    return members


def verify_archive(archive: str | Path, expected: str | None = None) -> dict[str, Any]:
    """Prüft Prüfsumme, Archivaufbau und Manifest (jede Datei gegen ihren SHA-256). Rückgabe: Manifest."""
    a = Path(archive)
    if not a.is_file():
        raise BackupError(f"Archiv fehlt: {a}")
    want = _expected_digest(a, expected)
    if _sha(a) != want:
        raise BackupError("Prüfsumme des Archivs stimmt nicht – Archiv beschädigt oder verändert")
    with tarfile.open(a, "r:gz") as tf:
        members = _safe_members(tf)
        names = {m.name for m in members if m.isreg()}
        mf = tf.extractfile("MANIFEST.json") if "MANIFEST.json" in names else None
        if mf is None:
            raise BackupError("MANIFEST.json fehlt")
        manifest = json.loads(mf.read().decode("utf-8"))
        if manifest.get("format") != FORMAT:
            raise BackupError("Unbekanntes Sicherungsformat")
        listed = set(manifest["files"])
        if listed != names - {"MANIFEST.json"}:
            raise BackupError("Dateiliste im Manifest passt nicht zum Archiv")
        for name, sha in manifest["files"].items():
            f = tf.extractfile(name)
            if f is None or hashlib.sha256(f.read()).hexdigest() != sha:
                raise BackupError(f"Datei beschädigt: {name}")
    return manifest


def _extract(archive: Path, dest: Path) -> dict[str, Any]:
    with tarfile.open(archive, "r:gz") as tf:
        _safe_members(tf)
        for m in tf.getmembers():
            target = dest / m.name
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(m)
                assert src is not None
                with open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    return json.loads((dest / "MANIFEST.json").read_text(encoding="utf-8"))


def confirm_phrase(archive: str | Path) -> str:
    return "RESTORE " + _expected_digest(Path(archive), None)[:8]


def restore(archive: str | Path, target: str | Path, confirm: str | None = None) -> dict[str, Any]:
    """Stellt `data/` aus dem Archiv in `target` wieder her und prüft das Ergebnis mit dem echten Lader.

    * `target` fehlt oder ist leer: Wiederherstellung (z. B. in ein Testverzeichnis), keine Bestätigung nötig.
    * `target` enthält Daten: nur mit `confirm == confirm_phrase(archive)`; die vorhandenen Daten werden NICHT gelöscht,
      sondern als `<target>.before-restore-<Zeit>` beiseitegestellt."""
    a, t = Path(archive), Path(target)
    manifest = verify_archive(a)
    t.parent.mkdir(parents=True, exist_ok=True)
    occupied = t.exists() and (not t.is_dir() or any(t.iterdir()))
    if occupied and confirm != confirm_phrase(a):
        raise BackupError(f"Ziel enthält Daten. Zum Überschreiben (die alten Daten bleiben als Kopie erhalten) bestätigen mit: {confirm_phrase(a)!r}")
    work = Path(tempfile.mkdtemp(prefix=".restore-", dir=t.parent))
    try:
        _extract(a, work)
        data = work / "data"
        gen = manifest["generation"]
        Store(data).load(gen)                                         # Prüfung vor dem Austausch
        kept = None
        if occupied:
            kept = t.with_name(t.name + ".before-restore-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            os.replace(t, kept)
        elif t.exists():
            t.rmdir()
        os.replace(data, t)
        os.chmod(t, 0o700)
        manifest["restored_to"], manifest["previous_data"] = str(t), str(kept) if kept else None
        return manifest
    finally:
        shutil.rmtree(work, ignore_errors=True)


def list_backups(out_dir: str | Path) -> list[Path]:
    return sorted(p for p in Path(out_dir).glob("mmo-backup-*.tar.gz") if NAME_RE.match(p.name))


def prune(out_dir: str | Path, daily: int = 14, weekly: int = 8, now: dt.datetime | None = None) -> list[str]:
    """Behält die neuesten `daily` Sicherungen und je eine pro Kalenderwoche für die letzten `weekly` Wochen (die älteste der Woche);
    löscht nur gültig benannte, überzählige Sicherungen samt Prüfsummen-Datei und alte `.partial-*`-Reste (älter als 1 Tag). Die jüngste bleibt immer."""
    out = Path(out_dir)
    items = list_backups(out)
    keep = set(p.name for p in items[-daily:]) if daily > 0 else set()
    if items:
        keep.add(items[-1].name)
    weeks: dict[tuple[int, int], Path] = {}
    for p in items:
        d = dt.datetime.strptime(NAME_RE.match(p.name).group(1), "%Y%m%dT%H%M%SZ")        # type: ignore[union-attr]
        weeks.setdefault(d.isocalendar()[:2], p)
    for p in sorted(weeks.values())[-weekly:] if weekly > 0 else []:
        keep.add(p.name)
    removed = []
    for p in items:
        if p.name not in keep:
            p.unlink()
            p.with_name(p.name + ".sha256").unlink(missing_ok=True)
            removed.append(p.name)
    cutoff = (now or dt.datetime.now(dt.timezone.utc)).timestamp() - 86400
    for p in out.glob(".partial-*"):
        if p.stat().st_mtime < cutoff:
            shutil.rmtree(p, ignore_errors=True)
    return removed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mmo_game.backup")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--data", required=True); c.add_argument("--out", required=True)
    c.add_argument("--extra", action="append", default=[], help="zusätzliche Datei (z. B. Dienstdatei, Caddyfile)"); c.add_argument("--note", default="")
    v = sub.add_parser("verify"); v.add_argument("archive"); v.add_argument("--full", action="store_true", help="zusätzlich mit dem echten Lader in einem Temporärverzeichnis laden")
    r = sub.add_parser("restore"); r.add_argument("archive"); r.add_argument("--target", required=True); r.add_argument("--confirm", default=None)
    p = sub.add_parser("prune"); p.add_argument("--out", required=True); p.add_argument("--daily", type=int, default=14); p.add_argument("--weekly", type=int, default=8)
    ls = sub.add_parser("list"); ls.add_argument("--out", required=True)
    ph = sub.add_parser("phrase"); ph.add_argument("archive")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "create":
            print(create(a.data, a.out, a.extra, a.note))
        elif a.cmd == "verify":
            m = verify_archive(a.archive)
            if a.full:
                with tempfile.TemporaryDirectory() as tmp:
                    restore(a.archive, Path(tmp) / "data")
            print(f"OK Generation {m['generation']}, {len(m['files'])} Dateien" + (f", Hinweis: {m['hint']}" if m.get("hint") else ""))
        elif a.cmd == "restore":
            m = restore(a.archive, a.target, a.confirm)
            print(f"Wiederhergestellt nach {m['restored_to']} (Generation {m['generation']})" + (f"; alte Daten gesichert unter {m['previous_data']}" if m["previous_data"] else ""))
        elif a.cmd == "prune":
            for n in prune(a.out, a.daily, a.weekly):
                print("gelöscht:", n)
        elif a.cmd == "list":
            for q in list_backups(a.out):
                print(q.name, q.stat().st_size)
        elif a.cmd == "phrase":
            print(confirm_phrase(a.archive))
    except (BackupError, PersistenceError, tarfile.TarError, OSError, ValueError, KeyError) as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
