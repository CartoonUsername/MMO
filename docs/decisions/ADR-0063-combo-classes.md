# ADR-0063: Klassenwirkung der Kombinationszauber (AP 24)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §24: dieselbe Kombination wirkt je Klasse anders)
- Spieler-Angabe `class` (Grundklasse) verstärkt je eine Zusatzwirkung der Kombinationszauber (ADR-0062): **Krieger** stärkere Schadensminderung (65 % statt 80 %), **Bogenschütze** längere Verlangsamung (×2), **Schamane/Alchemist** doppelte Ausdauer-Rückgabe. Die Werte stehen in `combo_classes` der Regeldatei, nie im Code.
- Regeln: `sim_rules_v13.json` (= v12 + `combo_classes`), `game_rules_v16.json` (Standard). Ältere Versionen und Golden Vectors bleiben; ohne `class` oder in v12 und älter ändert sich nichts, eine unbekannte Klasse wird abgelehnt.
- Spielschicht: beim Kampfstart setzt `game.py` `class` aus der Grundklasse der Figur.

## Offen
- Klassenwirkung nur für die drei Zusatzwirkungen (nicht für Bewegung, Beschwörung, Umgebung); Werte nicht per Bots balanciert; Client zeigt die Klassenwirkung nicht an.
