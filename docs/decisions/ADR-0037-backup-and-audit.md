# ADR-0037: Sicherung/Wiederherstellung des Spielstands und Kampf-Audit

**Status:** angenommen (Betriebswerkzeug, keine Spielregel)

## Kontext
Der Test-Server auf dem VPS hält Konten und Spielstände. Vorhanden war nur ein tägliches `tar` des Datenverzeichnisses: ohne Prüfsumme, ohne Konsistenzprüfung gegen laufende Speicherungen, ohne Wiederherstellungsverfahren.

## Entscheidung
- Der Speicher ist ein **Dateispeicher** (Generationen `gen-N/` + Zeiger `CURRENT`, `game_state.json`, `accounts.json`), keine Datenbank. Das Modul `mmo_game.backup` sichert konsistent: Zeiger lesen → zugehörige Generation und Nebendateien in ein Zwischenverzeichnis kopieren → Zeiger erneut lesen (geändert: Wiederholung) → den Stand mit dem echten Lader prüfen (Hash-Ketten) → `tar.gz` mit `MANIFEST.json` (SHA-256 je Datei) → Archiv erneut prüfen → erst dann atomar unter dem endgültigen Namen ablegen, plus `.sha256`-Datei. Unvollständiges trägt `.partial-*` und zählt nie als Sicherung.
- Wiederherstellung prüft zuerst (Prüfsumme, Archivaufbau ohne absolute Pfade, `..`, Links, Manifest, Lader). In ein leeres/neues Ziel ohne Rückfrage (Testverzeichnis); in ein belegtes Ziel nur mit dem Bestätigungssatz `RESTORE <8 Zeichen der Prüfsumme>`, und die vorhandenen Daten werden **nie gelöscht**, sondern als `.before-restore-<Zeit>` beiseitegestellt. Das Skript verlangt außerdem einen gestoppten Dienst und startet ihn nicht selbst.
- Aufbewahrung: 14 tägliche + 8 wöchentliche, die jüngste immer; gelöscht werden nur gültig benannte Sicherungen und alte `.partial-*`.
- Archive sind nur für den Besitzer lesbar (enthalten Passwort-Hashes). Eine Sicherung auf derselben Platte schützt nicht vor Serververlust: externe Kopie bleibt Aufgabe des Betreibers (kein Dienst ohne Zustimmung gebucht).
- Zusätzlich `tests/test_combat_audit.py`: jedes Kampfereignis genau einmal, ein Ergebnis je Ankündigung, Gruppenkampf, ungültige Eingaben ändern nichts. Der Audit fand keinen Fehler.

## Folgen
Neue Dateien: `mmo_game/backup.py`, `scripts/backup_mmo.sh`, `scripts/restore_mmo.sh`, `docs/BACKUP_AND_RESTORE.md`; `deploy/setup.sh` installiert sie und ersetzt den alten Cron-Job. Offen: externe Ablage, Überwachung fehlgeschlagener Sicherungen (nur Log `/var/log/mmo-backup.log`).
