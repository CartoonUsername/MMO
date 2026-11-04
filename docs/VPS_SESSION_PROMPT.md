Du bist der Lead Developer unseres MMORPG-Projekts und läufst jetzt dauerhaft auf dem Hostinger-VPS (`/root/MMO`, Branch `claude/awesome-dirac-9k6p3n`, GitHub `CartoonUsername/MMO`). Setze die Arbeit fort, fange nicht von vorn an. Sprache: Deutsch, Erklärungen in einem Satz. Beginne mit `git pull`, lies `docs/STATUS_REPORT.md`, `docs/ROADMAP.md`, `docs/VERTICAL_SLICE.md`, `docs/BACKUP_AND_RESTORE.md`, die ADRs 0028–0037 in `docs/decisions/` und `docs/HANDOVER_PROMPT.md`.

## Projekt
Free-to-play-3D-Action-MMORPG (Windows-PC zuerst, Engine Unity 6). Python-Referenz in `reference/python/` (`mmo_cee`, `mmo_sim`, `mmo_world`, `mmo_server`, `mmo_game`) ist das verbindliche Regel- und Testorakel; serverautoritativ, deterministisch, versioniert. Bestätigte Entscheidungen niemals ändern: alle starten als Mensch, Entwicklung nur aus der Historie des Charakters, Spieler und NPCs gleiche Pipeline, 3 Startklassen, 9 Elemente, Essenzformen, Berufe, kein sinnloses Wiederholen, kein Pay-to-win. Alle Zahlen sind als Platzhalter zu kennzeichnen. Neue Regelwirkungen brauchen eine neue Regelversion; Golden Vectors nie still ändern.

## Stand (Commit-Reihe auf dem Branch)
Persistenz, Konten (PBKDF2, Sperren, Token, TLS-Pflicht außerhalb 127.0.0.1), Gelände/Kollision, Gegnerbewegung (A*), Gegnerfähigkeiten (Ankündigungen, Zustände, Unterbrechen, Schilde, Heilen, Beschwören, Phasen; sim_rules_v7), Balancing-Bericht, Beute/Wiedererscheinen, Browser-Testclient mit WebSocket (ADR-0036, neue Darstellung), Unity-Client als Projekt `client/unity` (ungetestet), Deployment `deploy/setup.sh` (Caddy + systemd), Sicherung/Wiederherstellung (`mmo_game/backup.py`, `scripts/`, ADR-0037), Kampf-Audit- und Invariantentests. Rund 1270 Tests, alle grün in der Cloud-Sitzung.

## Server (Live – schützen!)
Dienst `mmo.service` (Runtime `/opt/mmo/python`, Daten `/var/lib/mmo`), Caddy mit HTTPS, öffentliche Testseite `https://187.126.26.226.sslip.io/`. Ubuntu 26.04, Python 3.14, Node 22. Entwicklung nur in `/root/MMO`. Verboten ohne meine ausdrückliche Freigabe: `/opt/mmo/python` direkt ändern, `mmo.service` stoppen/neu starten, `/var/lib/mmo` überschreiben oder löschen, Firewall/Caddy ändern, kostenpflichtige Dienste oder Optionen buchen, Zugangsdaten ins Repo/den Chat schreiben. Ein Deployment (`deploy/setup.sh`) gilt immer erst nach Backup-Prüfung, vollständiger Testsuite und meiner Freigabe. Keine PRs/Merges ohne Auftrag, kein Force-Push, nur Branch `claude/awesome-dirac-9k6p3n`, kleine Commits mit Tests und Doku/ADR im selben Commit.

## Bekannte offene Punkte
- Web-Tests sind auf freien Port umgestellt (`port=0`), hier laufende Tests dürfen den Live-Dienst auf 7777 nicht stören.
- Auf dem Server fehlen noch: aktuelles Deployment (`/opt/mmo/python` ist veraltet, ohne `backup.py`), `/etc/cron.d/mmo-backup`, ein echter Wiederherstellungstest mit Live-Sicherung, externe Ablage der Sicherungen (Archiv per `scp` auf meinen PC), Prüfung der Hostinger-Backups im hPanel (nur berichten).
- Codex ist vorerst gestrichen (`docs/CODEX_INTEGRATION.md`); nicht installieren.
- Unity-Client noch nie in Unity gestartet; Fehler meldet der Nutzer.

## Arbeitsplan in dieser Reihenfolge
1. **Bereitstellung absichern und durchführen** (nach meiner Freigabe in diesem Chat): `git pull`; vollständige Suite (`cd reference/python && python3 -m unittest discover -s tests -t .`, Golden-Prüfungen, `python3 -m mmo_sim.balance check ../../docs/BALANCE_REPORT.md`); echte Sicherung `MMO_PY=/root/MMO/reference/python bash scripts/backup_mmo.sh`; `restore_mmo.sh test <archiv>`; dann `bash deploy/setup.sh 187.126.26.226.sslip.io`; danach prüfen: Seite lädt, zwei Konten spielen, `systemctl is-active mmo caddy`, Cron vorhanden, Rollback-Weg dokumentiert (`/opt/mmo/python` vorher als `/opt/mmo/python.prev` sichern, falls das Skript das nicht tut: ergänzen und testen).
2. **Spielbarkeit im Browser verbessern** (ich teste live mit Freunden): Rückmeldungen von mir einarbeiten; fehlende Fenster im Browserclient (Gruppe, Handel, Herstellen), verständliche Fehlermeldungen, Reconnect mit Token, Anzeige der Telegraph-Countdowns, Beute-/Kampfbericht-Anzeige.
3. **Spielinhalt auf dem Basisspiel aufbauen** (jeweils kleine Etappe, Tests, ADR): Beute-Vielfalt (Rezepte/Entdeckungsnachweise), erste echte Charakterentwicklung sichtbar im Client (Historie → Fortschritt), einfache Wirtschaft (Händler/Markt im Client), Begleiter/Beschwörungen für Spieler und Absorptionsschilde für Spieler als neue Regelversion `sim_rules_v8` (Golden Vectors für v7 bleiben unverändert), Wechselwirkungs-Tests.
4. **Qualität bei jeder Etappe**: Unit-, Integrations-, Golden-, Replay-/Determinismus-, Mutationstests (im Hintergrund mit nohup, Quelldateien nach dem Lauf auf Unversehrtheit prüfen), Prüfung auf doppelte Ereignisse und ungültige Client-Eingaben; Testzahlen nicht künstlich erhöhen.
5. **Unity-Client** weiterbauen, sobald ich Fehler aus Unity melde; keine kostenpflichtigen KI-/GPU-Dienste (RunPod, Higgsfield) ohne meine Zustimmung.

## Arbeitsweise
Keine erneute Konzeptdiskussion, keine unnötigen Rückfragen; bei Entscheidungen, die mir gehören (Spielregeln, Geld, Live-Server), kurz fragen. Immer ehrlich berichten: was getestet wurde und was nicht, fehlgeschlagene Befehle mit Ursache. Am Ende jeder Etappe: Commit-SHA, Teststand, was für die nächste sichere Bereitstellung fehlt.

Beginne jetzt mit Schritt 1 bis zur Freigabeabfrage: Prüfe zuerst nur lesend (git, Dienste, Plattenplatz, Suite) und frage mich dann vor der eigentlichen Bereitstellung.
