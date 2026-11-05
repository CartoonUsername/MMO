# ADR-0071: Werkzeug zum Anheben des Spielstands auf eine höhere CEE-Regelversion (AP 40)

Status: angenommen (Vorschlag, Claude, autorisiert)

## Entscheidung
- Eine geladene Welt behält ihre gespeicherte CEE-Regelversion, unabhängig von `game_rules_*`. Neuer Code mit `game_rules_v19` (CEE v10) läuft auf einem v9-Spielstand sicher weiter; nur `profession.specialize` wird abgelehnt.
- `python -m mmo_game.upgrade --data <Ordner> --to rules_v10.json` hebt den Stand bewusst an (`upgrade_world`, ADR-0018): schreibt eine **neue Generation**, alte Generationen bleiben (Rückweg), `game_state.json` wird auf die neue Generation übertragen (Kopie der alten Fassung als `game_state.gen-<n>.json`).
- Nur bei gestopptem Dienst und nach Sicherung (`scripts/backup_mmo.sh`). Ablehnungen (Zielversion nicht höher, ungültiger Dateiname) ändern nichts.

## Offen
- Nicht auf dem echten Spielstand erprobt; Ablauf siehe `docs/DEPLOY_PENDING.md`.
