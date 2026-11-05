# ADR-0062: Bereichswirkung der Kombinationszauber (AP 23)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §22–26, §74)
- Kombinationszauber (ADR-0061) tragen `riders` (Zusatzwirkungen), abgeleitet aus den Wirkbereichen ihrer Elemente (`element_rules_v1`): **Kontrolle** → Gegner 60 Ticks verlangsamt; **Schutz** → 30 Ticks nur 80 % Schaden am Spieler (nur wenn nicht schon eine Minderung läuft, kein Stapeln); **Beistand** → 15 Ausdauer zurück. Entladung/Zerrung stecken schon im Schaden; Bewegung, Beschwörung, Umgebung bleiben offen.
- Gleiche Bereiche stapeln nicht (je Bereich eine Wirkung); Verlangsamung verlängert höchstens bis zum späteren Ende.
- Regeln: `sim_rules_v12.json` (= v11 + `riders`), `game_rules_v15.json` (Standard). v11/v14 bleiben, Golden Vectors unverändert.
- Validierung: `riders` nur bei Kombinationen; nur `slow_ticks`, `mitigate{ticks,damage_permille 0..1000}`, `stamina`, alle positiv.

## Offen
- Klassenabhängige Umsetzung (3 Klassen × 8 Bereiche, wie im Katalog beschrieben), Bewegung/Beschwörung/Umgebung; Werte sind Platzhalter, nicht per Bots balanciert; Client ungeprüft.
