# ADR-0076: Ausrüstungssets mit Setbonus (AP 61–63)

Status: angenommen (Vorschlag, Claude, autorisiert; Blueprint §31 „Setboni“ war offen; Platzhalterwerte)

## Entscheidung
- `equipment_rules_v2.json` (Standard; v1 bleibt) ergänzt `sets`: Teile (Gegenstands-IDs) und Bonusstufen (`pieces` → `effects`). Zwei Platzhaltersets: **Eisengebunden** (Eisenklinge + Eisenpanzer: schwere Treffer ×1,08) und **Wanderer** (Wams, Stiefel, Holzbuckler: 2 Teile Bewegung ×1,02, 3 Teile erlittener Schaden ×0,96).
- Zählung nach Gegenstands-ID, **unabhängig von der Güte**. Die Boni laufen durch dieselbe Zusammenführung (multiplikativ, Blockwert Minimum, Ausweichkosten additiv) und dieselben Kappen wie Gegenstände, sind also nicht unbegrenzt stapelbar.
- Validierung: Teile müssen existieren und eindeutig sein, Bonusstufen aufsteigend und nicht größer als das Set, Wirkungsschlüssel bekannt.
- Keine Persistenz nötig: abgeleitet aus den getragenen Teilen. Keine neue Geldquelle, kein Pay-to-win-Pfad.

## Offen
- Mehr Sets/Slots/Seltenheiten, Rezepte für Setteile, Anzeige im Unity-Client; Balancing nicht per Bot gemessen.
