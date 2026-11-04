# Sicherung und Wiederherstellung

Gilt für den Spielserver nach `deploy/setup.sh` (Daten `/var/lib/mmo`, Sicherungen `/var/backups/mmo`). Hintergrund: ADR-0037.

## Was gesichert wird
Die aktuelle Generation (`gen-N/`), `CURRENT`, `game_state.json`, `accounts.json` (mit Passwort-Hashes, Archiv ist 0600), dazu Dienstdatei, Caddyfile und `DEPLOY_INFO` (Commit des Deployments), falls vorhanden. Konsistenz: siehe ADR – der Server wird nicht gestoppt, ein sich änderndes `CURRENT` löst Wiederholung aus, der Stand wird vor dem Ablegen mit dem echten Lader geprüft.

## Automatik
`/etc/cron.d/mmo-backup`: täglich 03:17 → `/opt/mmo/scripts/backup_mmo.sh` (Log `/var/log/mmo-backup.log`). Aufbewahrung 14 Tage + 8 Wochen (`MMO_KEEP_DAILY`, `MMO_KEEP_WEEKLY`). Das Skript bricht ab, wenn weniger als das Doppelte der Datenmenge frei ist.

## Von Hand sichern / prüfen
```bash
sudo /opt/mmo/scripts/backup_mmo.sh
sudo /opt/mmo/scripts/restore_mmo.sh list
```

## Wiederherstellung testen (ungefährlich, Live-Daten bleiben unberührt)
```bash
sudo /opt/mmo/scripts/restore_mmo.sh test /var/backups/mmo/mmo-backup-<Zeit>.tar.gz
```
Prüft Prüfsumme, Manifest und lädt den Stand mit dem echten Lader in ein Temporärverzeichnis. Regelmäßig (z. B. monatlich) ausführen.

## Echte Rückspielung
1. `systemctl stop mmo` (Spieler werden getrennt; das Skript verweigert sonst).
2. `sudo /opt/mmo/scripts/restore_mmo.sh live <archiv>` – zeigt den Bestätigungssatz `RESTORE xxxxxxxx`, den du exakt eintippen musst.
3. Die alten Daten liegen danach unverändert unter `/var/lib/mmo.before-restore-<Zeit>` (erst löschen, wenn alles passt).
4. `systemctl start mmo`, Seite öffnen, einloggen, Figur prüfen.
Rückgängig machen: Dienst stoppen, `/var/lib/mmo` wegschieben, `…before-restore-…` zurückbenennen, Dienst starten.

## Grenzen
- Gleiche Platte = kein Schutz bei Serververlust/Löschung des VPS: Archive regelmäßig extern ablegen (z. B. `scp` auf den eigenen PC) und Hostinger-Snapshots/Backups prüfen. Hostinger bietet laut Preisseite „kostenlose wöchentliche Datensicherungen“ für KVM-Pläne; Umfang, Wiederherstellungsweg und Aufpreis für tägliche Backups bitte im hPanel nachsehen (nicht geprüft, nichts gebucht).
- Spieler, die zwischen letzter Speicherung und Sicherung gespielt haben, verlieren höchstens die Spielzeit seit der letzten automatischen Speicherung (alle 600 Ticks = 60 s).
- Ein Wechsel der Regelversion wird beim Laden abgelehnt (ADR-0014); Sicherungen sind nur mit passender Programmversion ladbar (`DEPLOY_INFO` nennt den Commit).
