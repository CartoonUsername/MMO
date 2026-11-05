# ADR-0067: Marktplatz-Rabatt 250/500 ‰ (settlement_rules_v2, AP 31)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung
- Neue Regelversion `settlement_rules_v2.json` (Standard in `World`): `market_square` gibt 0 / 250 / 500 ‰ Rabatt auf die Börsengebühr (2 % → 1,5 % → 1 %). Kosten unverändert.
- Grund: Rechnung in `docs/BALANCE_MARKET_SQUARE.md`; mit 100/200 ‰ lohnte sich das Projekt praktisch nie.
- `settlement_rules_v1.json` bleibt erhalten. Golden Vectors unverändert gültig (sie nutzen keinen Marktplatz).

## Offen
- Nicht per Bot gemessen; echter Handelsumsatz unbekannt. Weiter ansehen, sobald Spieldaten vorliegen.
