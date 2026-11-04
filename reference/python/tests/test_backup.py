"""Tests für Sicherung und Wiederherstellung (ADR-0037): Konsistenz, Prüfsummen, Schutz der Live-Daten, Aufbewahrung."""
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mmo_game import backup
from mmo_game.backup import BackupError
from mmo_game.game import GameServer
from mmo_world.persistence import Store


def make_data(root: Path, chars=("anna", "ben")) -> Path:
    data = root / "data"
    store = Store(data)
    g = GameServer()
    for c in chars:
        g.connect(c)
    g.save(store)
    (data / "accounts.json").write_text(json.dumps({"anna": {"hash": "x"}}), encoding="utf-8")
    return data


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = make_data(self.root)
        self.out = self.root / "backups"

    def tearDown(self):
        self.tmp.cleanup()

    def test_rundreise_gleicher_stand(self):
        arc = backup.create(self.data, self.out)
        self.assertTrue(arc.with_name(arc.name + ".sha256").exists())
        self.assertEqual(oct(arc.stat().st_mode & 0o777), "0o600")
        m = backup.verify_archive(arc)
        self.assertEqual(m["generation"], Store(self.data).current())
        t = self.root / "wieder"
        backup.restore(arc, t)
        self.assertEqual(Store(t).current(), Store(self.data).current())
        for rel in ("CURRENT", "accounts.json", "game_state.json"):
            self.assertEqual((t / rel).read_bytes(), (self.data / rel).read_bytes())
        self.assertEqual(sorted(Store(t).load().svc.log.character_ids()), ["anna", "ben"])

    def test_live_daten_bleiben_unveraendert(self):
        before = {str(p.relative_to(self.data)): p.read_bytes() for p in self.data.rglob("*") if p.is_file()}
        backup.create(self.data, self.out)
        after = {str(p.relative_to(self.data)): p.read_bytes() for p in self.data.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_beschaedigtes_archiv_wird_erkannt(self):
        arc = backup.create(self.data, self.out)
        raw = bytearray(arc.read_bytes())
        raw[len(raw) // 2] ^= 0xFF
        arc.write_bytes(bytes(raw))
        with self.assertRaises(BackupError):
            backup.verify_archive(arc)

    def test_fehlende_pruefsumme_und_falsche_pruefsumme(self):
        arc = backup.create(self.data, self.out)
        side = arc.with_name(arc.name + ".sha256")
        good = side.read_text()
        side.write_text("0" * 64 + "  x\n")
        with self.assertRaises(BackupError):
            backup.verify_archive(arc)
        side.unlink()
        with self.assertRaises(BackupError):
            backup.verify_archive(arc)
        side.write_text(good)
        backup.verify_archive(arc)

    def test_manipuliertes_archiv_mit_passender_pruefsumme_faellt_am_manifest_auf(self):
        arc = backup.create(self.data, self.out)
        forged = self.root / "forged.tar.gz"
        with tarfile.open(arc) as src, tarfile.open(forged, "w:gz") as dst:
            for m in src.getmembers():
                f = src.extractfile(m) if m.isreg() else None
                if m.name == "data/accounts.json":
                    body = b'{"evil":1}'
                    m.size = len(body)
                    f = io.BytesIO(body)
                dst.addfile(m, f)
        digest = hashlib.sha256(forged.read_bytes()).hexdigest()
        with self.assertRaisesRegex(BackupError, "beschädigt"):
            backup.verify_archive(forged, digest)

    def _forge(self, arc, change):
        """Baut ein Archiv mit gültiger Prüfsumme, in dem `change(files, manifest)` etwas verändert hat."""
        with tarfile.open(arc) as src:
            files = {m.name: src.extractfile(m).read() for m in src.getmembers() if m.isreg()}
        manifest = json.loads(files.pop("MANIFEST.json"))
        change(files, manifest)
        manifest["files"] = {n: hashlib.sha256(b).hexdigest() for n, b in files.items() if n != "MANIFEST.json"} if manifest.pop("_rehash", False) else manifest["files"]
        files["MANIFEST.json"] = json.dumps(manifest).encode()
        forged = self.root / "forged2.tar.gz"
        with tarfile.open(forged, "w:gz") as tf:
            for n, b in files.items():
                ti = tarfile.TarInfo(n)
                ti.size = len(b)
                tf.addfile(ti, io.BytesIO(b))
        return forged, hashlib.sha256(forged.read_bytes()).hexdigest()

    def test_manifest_muss_zum_archiv_passen_und_format_bekannt_sein(self):
        arc = backup.create(self.data, self.out)
        forged, d = self._forge(arc, lambda f, m: f.update({"extra/boese.txt": b"x"}))
        with self.assertRaisesRegex(BackupError, "Dateiliste"):
            backup.verify_archive(forged, d)
        forged, d = self._forge(arc, lambda f, m: m.update({"format": 99}))
        with self.assertRaisesRegex(BackupError, "formatformat|ormat"):
            backup.verify_archive(forged, d)

    def test_archivgroesse_ist_begrenzt(self):
        arc = backup.create(self.data, self.out)
        with mock.patch.object(backup, "MAX_MEMBERS", 2), self.assertRaisesRegex(BackupError, "zu groß"):
            backup.verify_archive(arc)

    def test_wiederherstellung_prueft_den_stand_vor_dem_austausch(self):
        arc = backup.create(self.data, self.out)
        gen = f"data/gen-{Store(self.data).current():06d}/snapshot.json"
        def corrupt(f, m):
            f[gen] = f[gen].replace(b"anna", b"anne", 1)
            m["_rehash"] = True
        forged, d = self._forge(arc, corrupt)
        self.assertTrue(backup.verify_archive(forged, d))                         # Archiv selbst ist stimmig ...
        side = forged.with_name(forged.name + ".sha256")
        side.write_text(f"{d}  x\n")
        live = self.root / "live2"
        shutil.copytree(self.data, live)
        before = {str(p.relative_to(live)): p.read_bytes() for p in live.rglob("*") if p.is_file()}
        with self.assertRaises(Exception):                                         # ... aber der Stand ist defekt: Lader lehnt ab
            backup.restore(forged, live, backup.confirm_phrase(forged))
        self.assertEqual(before, {str(p.relative_to(live)): p.read_bytes() for p in live.rglob("*") if p.is_file()})
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith(".restore-")], [])

    def test_unzulaessige_archiveintraege(self):
        for name in ("../evil", "/abs/evil"):
            bad = self.root / "bad.tar.gz"
            with tarfile.open(bad, "w:gz") as tf:
                ti = tarfile.TarInfo(name)
                ti.size = 1
                tf.addfile(ti, io.BytesIO(b"x"))
            with self.subTest(name), self.assertRaisesRegex(BackupError, "Unzulässig"):
                backup.verify_archive(bad, hashlib.sha256(bad.read_bytes()).hexdigest())
        link = self.root / "link.tar.gz"
        with tarfile.open(link, "w:gz") as tf:
            ti = tarfile.TarInfo("a")
            ti.type, ti.linkname = tarfile.SYMTYPE, "/etc/passwd"
            tf.addfile(ti)
        with self.assertRaisesRegex(BackupError, "Unzulässig"):
            backup.verify_archive(link, hashlib.sha256(link.read_bytes()).hexdigest())

    def test_wiederherstellung_in_belegtes_ziel_braucht_bestaetigung_und_behaelt_alte_daten(self):
        arc = backup.create(self.data, self.out)
        live = self.root / "live"
        shutil.copytree(self.data, live)
        (live / "marker.txt").write_text("alt")
        with self.assertRaisesRegex(BackupError, "RESTORE"):
            backup.restore(arc, live)
        with self.assertRaises(BackupError):
            backup.restore(arc, live, "RESTORE 00000000")
        self.assertEqual((live / "marker.txt").read_text(), "alt")               # nichts verändert
        res = backup.restore(arc, live, backup.confirm_phrase(arc))
        self.assertFalse((live / "marker.txt").exists())
        kept = Path(res["previous_data"])
        self.assertEqual((kept / "marker.txt").read_text(), "alt")               # alte Daten bleiben als Kopie
        self.assertEqual(Store(live).current(), Store(self.data).current())

    def test_wiederherstellung_in_leeres_oder_neues_ziel_ohne_bestaetigung(self):
        arc = backup.create(self.data, self.out)
        empty = self.root / "leer"
        empty.mkdir()
        backup.restore(arc, empty)
        self.assertTrue((empty / "CURRENT").exists())

    def test_leerer_speicher_wird_nicht_gesichert(self):
        with self.assertRaisesRegex(BackupError, "fehlt"):
            backup.create(self.root / "leer", self.out)
        (self.root / "leer").mkdir()
        with self.assertRaisesRegex(BackupError, "CURRENT"):
            backup.create(self.root / "leer", self.out)
        self.assertEqual(backup.list_backups(self.out), [])

    def test_defekter_stand_wird_nicht_als_sicherung_abgelegt(self):
        gen = self.data / f"gen-{Store(self.data).current():06d}"
        snap = gen / "snapshot.json"
        snap.write_bytes(snap.read_bytes().replace(b"anna", b"anne", 1))
        with self.assertRaises(BackupError):
            backup.create(self.data, self.out)
        self.assertEqual(backup.list_backups(self.out), [])
        self.assertEqual([p for p in self.out.iterdir()], [])                    # auch keine Reste

    def test_wechsel_des_zeigers_waehrend_der_kopie_fuehrt_zur_wiederholung(self):
        real = backup._read_current
        calls = {"n": 0}
        g = GameServer()
        g.connect("anna")

        def flaky(data):
            calls["n"] += 1
            if calls["n"] == 2:                                                  # nach dem ersten Kopieren schreibt der Server eine neue Generation
                g.save(Store(self.data))
            return real(data)
        with mock.patch.object(backup, "_read_current", flaky), mock.patch.object(backup.time, "sleep", lambda s: None):
            arc = backup.create(self.data, self.out)
        self.assertEqual(backup.verify_archive(arc)["generation"], Store(self.data).current())
        self.assertGreater(calls["n"], 3)

    def test_zusatzdateien_werden_mitgesichert(self):
        svc = self.root / "mmo.service"
        svc.write_text("[Unit]")
        arc = backup.create(self.data, self.out, [svc, self.root / "fehlt"])
        m = backup.verify_archive(arc)
        self.assertIn("extra/mmo.service", m["files"])
        self.assertNotIn("extra/fehlt", m["files"])

    def test_aufbewahrung(self):
        self.out.mkdir()
        start = dt.datetime(2026, 1, 1, 3, 0, 0)
        for i in range(40):                                                       # 40 Tage, je eine Sicherung
            n = (start + dt.timedelta(days=i)).strftime("mmo-backup-%Y%m%dT%H%M%SZ.tar.gz")
            (self.out / n).write_bytes(b"x")
            (self.out / (n + ".sha256")).write_text("x")
        (self.out / "andere.txt").write_text("bleibt")
        old_partial = self.out / ".partial-alt"
        old_partial.mkdir()
        os.utime(old_partial, (0, 0))
        removed = backup.prune(self.out, daily=14, weekly=4)
        left = [p.name for p in backup.list_backups(self.out)]
        self.assertIn("mmo-backup-20260209T030000Z.tar.gz", left)                 # jüngste bleibt
        self.assertEqual(len(left) + len(removed), 40)
        self.assertGreaterEqual(len(left), 14)
        self.assertLess(len(left), 20)
        self.assertTrue((self.out / "andere.txt").exists())
        self.assertFalse(old_partial.exists())
        self.assertFalse(any(not (self.out / (n + ".sha256")).exists() for n in left))
        self.assertFalse((self.out / (removed[0] + ".sha256")).exists())

    def test_prune_behaelt_immer_die_juengste(self):
        self.out.mkdir()
        (self.out / "mmo-backup-20260101T030000Z.tar.gz").write_bytes(b"x")
        self.assertEqual(backup.prune(self.out, daily=0, weekly=0), [])

    def test_cli(self):
        self.assertEqual(backup.main(["create", "--data", str(self.data), "--out", str(self.out)]), 0)
        arc = backup.list_backups(self.out)[0]
        self.assertEqual(backup.main(["verify", str(arc), "--full"]), 0)
        self.assertEqual(backup.main(["restore", str(arc), "--target", str(self.root / "x")]), 0)
        arc.write_bytes(b"kaputt")
        self.assertEqual(backup.main(["verify", str(arc)]), 1)


if __name__ == "__main__":
    unittest.main()
