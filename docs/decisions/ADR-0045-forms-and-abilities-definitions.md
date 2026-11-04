# ADR-0045: Wesensformen und Fähigkeiten als Definitionen, Vorschau und bestätigte Annahme (AP 6)

Status: angenommen (Platzhaltertexte)

## Entscheidung
- Redaktionelle Definitionen in `mmo_cee/data/definitions_v1.json` (Name, Beschreibung, Tradeoff, Gegenspiel für Formen, Entscheidungen, Fähigkeiten; Bezeichnungen der Vor-/Nachteile). Mechanik bleibt in den CEE-Regeln; ein Test prüft, dass jede Form, Entscheidung, Modifikator und Fähigkeit eine Definition hat.
- `mmo_cee/forms.py`: reine Ableitung `essence_preview` (Status je Form: secret/progress/eligible/trial_passed/adopted/locked_in, Punkte, Beiträge, Vor-/Nachteile, Mindeststufe, fehlende Entdeckungen) und `ability_definitions`.
- Gateway: `essence.decide`, `essence.trial`, `essence.adopt` (braucht `ack = adopt:<Form>`); alle gehen durch die Essence Engine (Prüfung vor Annahme, einmalig, nicht umkehrbar, auditierbar im Ereignislog). Der Client entscheidet nie über Erfolg.
- `query.character` liefert `essence_preview` und `ability_defs`; das Charakterfenster zeigt Vorschau, Entscheidungen, Prüfung und Annahme mit doppelter Bestätigung.
- Keine neue CEE-Regelversion, keine Migration.

## Offen
Weitere Formen jenseits Element/Beruf (Forschung, Erkundung), Visual-/Animations-Schlüssel, Meilenstein-/Questanforderungen, finale Inhalte (alles Platzhalter).
