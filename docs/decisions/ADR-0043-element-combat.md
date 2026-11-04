# ADR-0043: Elementwirkung im Kampf (AP 4b)

Status: angenommen (Platzhalterwerte)

## Entscheidung
- Neue Simulationsregeln `sim_rules_v8.json` (= v7 + Abschnitt `elements`); v7 und alle Golden Vectors bleiben unverändert.
- Fähigkeitsbefehle können ein `element` tragen. Gegen Gegner mit `element` gilt: stark ×1,25, schwach ×0,8, gleiches Element ×0,75, sonst ×1,0 (Promille in `elements`). Gilt für Sofort- und Zeitschaden (`cast_ember` = Feuer).
- Stärken-Tabelle (`elements.strong`) ist Platzhalter; Schwäche ist die Umkehrung.
- Neue Spielregeln `game_rules_v4.json` (Standard) verweisen auf `sim_rules_v8`; v3 bleibt erhalten. Keine CEE-Regeländerung, daher keine Weltmigration.

## Nicht entschieden (offen, Blueprint §26 / Frage 6)
Wie Elemente im Kampf gewechselt/verwaltet werden. Weitere Elementskills je Wirkungsdomäne und Wechselwirkung mit Kontrolle/Verteidigung folgen in einem Folgeschritt.
