# Codex als zweiter Entwickler (Claude Code bleibt Lead)

Quelle: offizielle Anleitung des Plugins <https://github.com/openai/codex-plugin-cc> (Stand der Prüfung: heute; vor Ausführung die Seite noch einmal ansehen). **Status: nicht installiert** – die Einrichtung muss auf dem Zielrechner (Hostinger-VPS, `/root/MMO`) von dir mit deinem ChatGPT-Konto bestätigt werden; die Cloud-Sitzung, in der dieses Dokument entstand, hat weder den VPS noch dein ChatGPT-Login.

## Voraussetzungen prüfen (auf dem VPS)
```bash
claude --version
node --version     # mindestens 18.18
npm --version
codex --version    # falls fehlt: siehe unten
```

## Installation (laut Plugin-Anleitung)
```bash
npm install -g @openai/codex
```
In Claude Code (auf dem VPS):
```
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

## Anmeldung mit deinem ChatGPT-Konto (kein API-Key, kein Zusatz-Abo)
Das Plugin nennt `!codex login`. Auf einem Server ohne Browser funktioniert laut mehreren Drittquellen (Details dort nicht einheitlich, bitte gegen die aktuelle Codex-Doku prüfen: <https://developers.openai.com/codex/cli/reference/#codex-login>) der Gerätecode-Weg:
```bash
codex login --device-auth
```
Ablauf: Der Server zeigt eine Adresse und einen Code → du öffnest die Adresse **auf deinem PC**, meldest dich bei ChatGPT an und gibst den Code ein. Falls es abgelehnt wird, muss in den ChatGPT-Sicherheitseinstellungen „Device-Code-Anmeldung“ erlaubt sein. Ersatzweg: `ssh -L 1455:localhost:1455 root@<server>` und `codex login`, dann im Browser deines PCs die angezeigte Adresse öffnen. Die Nutzung zählt auf die Codex-Limits deines ChatGPT-Tarifs; es entsteht keine API-Abrechnung, solange du **nicht** den API-Key-Weg wählst.
Die Zugangsdaten landen in `~/.codex/` des VPS – nie ins Repository kopieren (`.gitignore` schließt `.codex/` aus).

## Abnahmetest (nach der Anmeldung)
1. `/codex:setup` meldet „bereit“.
2. `/codex:review` auf dem aktuellen Branch (schreibgeschützt) liefert ein Ergebnis.
3. `/codex:rescue --background "Prüfe mmo_game/backup.py auf Fehler, ändere nichts"` → `/codex:status` → `/codex:result`.
4. Claude bewertet das Ergebnis und übernimmt oder verwirft es.

## Arbeitsregeln
- Codex arbeitet nie auf `main`/Produktion und nie in `/opt/mmo/python`. Jede schreibende Aufgabe läuft in einem eigenen Worktree und Branch: `git worktree add ../mmo-codex-<aufgabe> -b codex/<aufgabe> claude/awesome-dirac-9k6p3n`.
- Aufgaben sind klein und prüfbar (ein Modul, eine Testlücke, ein Review), mit Auftrag „Tests ausführen, Golden Vectors nicht ändern, neue Regeln nur mit neuer Regelversion“.
- Claude liest jeden Codex-Diff, führt die komplette Suite aus und merged erst dann in den Arbeitsbranch. Review-Gate (`/codex:setup --enable-review-gate`) nur auf ausdrücklichen Wunsch (verbraucht Limits).
- Geeignete Codex-Aufgaben: unabhängige Reviews, zusätzliche Tests für Mutations-Überlebende, Fehleranalyse; Claude: Architektur, Regeln, Integration.
