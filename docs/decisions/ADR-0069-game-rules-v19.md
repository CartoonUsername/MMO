# ADR-0069: Spielschicht auf CEE-Regeln v10 (AP 34, game_rules_v19)

Status: angenommen (Vorschlag, Claude, autorisiert)

## Entscheidung
- `game_rules_v19.json` (Standard) = v18 mit `cee_rules: rules_v10.json`. Damit ist die Berufs-Zweigwahl (ADR-0068) im Spiel über `profession.specialize` erreichbar.
- Ältere game_rules bleiben (v18 und früher laufen weiter auf CEE v9).
- Test über das Protokoll: erste Wahl kostenlos, Wechsel in der Abklingzeit abgelehnt.

## Offen
- Der gewählte Zweig hat noch keine Spielwirkung; Clients zeigen ihn nicht an.
