# ADR-0064: Bewegungswirkung der Kombinationszauber (AP 25)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §22–26)
- Kombinationszauber mit Wirkbereich **Bewegung** (Wind, Schatten) tragen den Rider `evade_ticks: 8`: ein kurzes Ausweichfenster, in dem Gegnertreffer verfehlen (vorhandener Mechanismus `evade_until`). Verlängert höchstens, stapelt nicht.
- Regeln: `sim_rules_v14.json` (= v13 + Rider bei 64 Kombinationen), `game_rules_v17.json` (Standard). Ältere Versionen und Golden Vectors bleiben.
- Validierung: `evade_ticks` positive Ganzzahl, nur bei Kombinationen.

## Offen
- Beschwörung und Umgebung ohne Wirkung; Wert nicht per Bots balanciert; Client zeigt Riders nicht an.
- Die Spielschicht gibt die Grundklasse im Kampfstart weiter (Test `GameLayer` ergänzt, AP 24).
