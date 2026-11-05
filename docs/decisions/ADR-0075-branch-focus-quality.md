# ADR-0075: Aktiver Zweig gibt Gütepunkte (AP 53)

Status: angenommen (Vorschlag, Claude, autorisiert; Platzhalterwert)

## Entscheidung
- `rules_v10.professions.specialization.focus_quality` = 50: Für Rezepte des aktiven Berufszweigs steigt die Gütebewertung (`quality_score`) um 50 Punkte (zum Vergleich: eine Meisterschaftsstufe +40, eine Technik +100). Die Plausibilitätsgrenze (`quality_cap`) nutzt dieselbe Bewertung, Herstellungsberichte bleiben damit gültig.
- Gilt nur in Regeln mit Zweigwahl (v10); v9 und älter unverändert. Nur Rezepte des gewählten Zweigs, andere Rezepte unberührt.
- `rules_v10` war noch nicht ausgeliefert, daher erweitert; der Golden Vector `profession_specialization` wurde neu erzeugt (nur dieser).

## Offen
- Balancing: 50 Punkte können eine Gütestufe überspringen lassen (Schwellen 400/650/850); nicht per Bot gemessen. Anzeige im Client.
