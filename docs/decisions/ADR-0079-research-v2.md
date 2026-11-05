# ADR-0079: Mehr Techniken, höhere Projektstufen an Forschung gebunden (AP 70)

Status: angenommen (Vorschlag, Claude, autorisiert; Platzhalterwerte; Epochen-Inhalte waren offen)

## Entscheidung
- `research_rules_v2.json` (Standard; v1 bleibt): drei neue Techniken — **Marktrecht** (Epoche 0, 5 Tage), **Lagerwesen** (Epoche 0, 5 Tage), **Stadtrecht** (Epoche 1, braucht Marktrecht, 10 Tage).
- In `settlement_rules_v2` (noch nicht ausgeliefert) verlangen jetzt Stufe 2 von **Marktplatz** (Marktrecht), **Lagerhaus** (Lagerwesen), **Rathaus** (Stadtrecht) und **Hafen** (Dampfkraft, Epoche 1) die jeweilige Technik des Ortes; Stufe 1 bleibt frei. Bereits gebaute Stufen bleiben unberührt, nur künftige Beiträge werden geprüft.
- Damit hängen die Epochen der Welt an echten Inhalten: Epoche 1 („Frühe Industrie“) schaltet Stadtrecht und Dampfkraft frei.

## Offen
- Weitere Epochen, Produktionsvorsprung, Spezialisierung je Ort; Balancing der Kosten.
