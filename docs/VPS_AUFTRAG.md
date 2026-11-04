# Auftrag für Claude Code auf dem Hostinger-VPS

Du läufst jetzt **auf dem Server** (`/root/MMO`, Branch `claude/awesome-dirac-9k6p3n`). Lies zuerst `docs/STATUS_REPORT.md`, `docs/BACKUP_AND_RESTORE.md`, `docs/CODEX_INTEGRATION.md`, `docs/decisions/ADR-0036*.md`, `ADR-0037*.md`. Ein Teil ist bereits fertig (in einer Cloud-Sitzung entwickelt und getestet); hier fehlt die **Prüfung und Einrichtung auf dem echten Server**. Nicht von vorn anfangen, keine doppelten Module.

## Schutzregeln (immer)
- Entwicklung nur in `/root/MMO`. `/opt/mmo/python` nicht direkt ändern. `mmo.service` nicht stoppen/neu starten, `/var/lib/mmo` nie überschreiben oder löschen, Firewall/Caddy nicht ändern, kein Deployment ohne ausdrückliche Freigabe des Nutzers.
- Keine kostenpflichtigen Dienste/Optionen buchen, keine Zugangsdaten ins Repository oder in den Chat. Antworten an den Nutzer auf Deutsch, Erklärungen in einem Satz.

## Schritt 1 – Bestandsaufnahme (nur lesen)
Berichte: `git log --oneline -8`, `git status`; `systemctl status mmo caddy --no-pager`; Unit-Datei `/etc/systemd/system/mmo.service`; Inhalt/Größe von `/var/lib/mmo` (nur `ls -la`, `du -sh`); freier Platz (`df -h`); `/etc/cron.d`, `/etc/cron.daily` (vorhandene Backup-Jobs); `/var/backups/mmo`; `/opt/mmo` (Unterschied zu `/root/MMO` per `diff -rq`, nur anzeigen); `python3 --version`; `journalctl -u mmo -n 50 --no-pager`. Prüfe, ob Hostinger-Snapshots/Backups sichtbar sind (nur berichten, nichts buchen).

## Schritt 2 – Sicherung real prüfen (Live-Daten nur lesen)
1. Tests in `/root/MMO/reference/python`: `python3 -m unittest tests.test_backup tests.test_combat_audit tests.test_web` (müssen grün sein).
2. `bash scripts/backup_mmo.sh` mit `MMO_BACKUP_DIR=/root/backup-test` (nicht in `/var/backups/mmo`), dann `bash scripts/restore_mmo.sh test <archiv>` – nur Testverzeichnis. Berichte Generation, Dateianzahl, Dauer.
3. **Nicht** `restore_mmo.sh live` ausführen. Lege der Nutzerin/dem Nutzer vor, ob `deploy/setup.sh` (installiert Skripte und Cron `/etc/cron.d/mmo-backup`) jetzt ausgeführt werden soll – nur nach Ja.

## Schritt 3 – Codex einrichten (offizielles Plugin `openai/codex-plugin-cc`)
Lies die aktuelle Anleitung (https://github.com/openai/codex-plugin-cc), prüfe `node --version` (≥18.18), `npm install -g @openai/codex`, im Claude-Code-Fenster `/plugin marketplace add openai/codex-plugin-cc`, `/plugin install codex@openai-codex`, `/reload-plugins`, `/codex:setup`. Anmeldung mit dem ChatGPT-Konto des Nutzers: `codex login --device-auth` – erkläre dem Nutzer genau, was er auf seinem PC im Browser tun muss. Keine API-Keys. Danach Abnahmetest laut `docs/CODEX_INTEGRATION.md` (schreibgeschütztes `/codex:review`, ein `/codex:rescue --background`-Prüfauftrag ohne Änderungen). Codex schreibt nie in `/opt/mmo` und nur in eigene Worktrees/Branches (`codex/<aufgabe>`).

## Schritt 4 – Entwicklung fortsetzen
Prüfe die bereits vorhandenen Kampfmechaniken (ADR-0032/0033/0034, `mmo_sim/pack.py`, `mmo_sim/enemies.py`, `mmo_game/game.py`) gegen die Liste: Ankündigungen, Zustände, Unterbrechen, Schilde/Absorption, Heilung/Unterstützung, Beschwörungen/Begleiter, Bossphasen, Gruppenmechaniken, Wechselwirkungen, Serverautorität. Nenne echte Lücken (z. B. Begleiter für Spieler, Absorption für Spielerschilde, Wechselwirkungs-Tests) und schlage dem Nutzer die nächste kleine Etappe vor; Regeländerungen nur mit neuer Regelversion, Golden Vectors nicht still ändern, Tests/Mutationstests, ADR + Doku im selben Commit, Push nur auf `claude/awesome-dirac-9k6p3n`. Lasse Codex unabhängig reviewen (`/codex:review`) und bewerte das Ergebnis.

## Abschlussbericht (Deutsch)
Git-Stand, Backup-Ergebnisse (Test in Temp-Verzeichnis), Codex-Status, Aufgabenverteilung, Befunde, Tests, Commit-SHAs, was für die nächste sichere Bereitstellung fehlt.
