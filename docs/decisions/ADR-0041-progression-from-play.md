# ADR-0041: Das Spielgeschehen speist die Charakterentwicklung (AP 3)

**Status:** angenommen (Spielschicht; Spielregeln `game_rules_v3.json`, Platzhalter; keine neue CEE-Regelversion)

## Kontext
Bisher flossen nur Kampfberichte (Kampfpunkte) und Herstellung (Berufserfahrung) in die Charakterentwicklung. Erfahrung (`identity.xp_gained`), Elementexposition (`element.exposure`) und Entdeckungsbeweise (`discovery.evidence_gathered`) wurden vom Spielserver nie aufgezeichnet; die Stufe blieb 1, Elemente wuchsen nicht. Blueprint §9, §10, §70.3: Berufe, Erkundung, Kampf prägen die Identität; **jede Quelle braucht einen Grund, triviale Wiederholung darf nicht unbegrenzt belohnt werden**.

## Entscheidung
Der Server zeichnet mit **vorhandenen** CEE-Ereignissen auf (keine neuen Ereignisarten, keine Regelversion der CEE):
- **Sieg im Kampf** (nur Teilnehmer mit Beitrag): Erfahrung = Gegnerstufe × 6 je Gegner, Elementexposition des besiegten Gegners (8 je Gegner); beides mit dem **Beutefaktor** (`loot_decay_permille`) der Figur – gleiche Art am selben Tag bringt weniger (bis 10 %). Niederlage und Flucht bringen nichts.
- **Elementfähigkeiten**: je Einsatz von `cast_ember` Feuerexposition (6), höchstens 10 je Kampf und 60 je Tag.
- **Sammeln**: Berufserfahrung (Erz→Bergbau, Kraut→Landwirtschaft, Wasser→Alchemie) mit Tageslimit (20 voll, danach 25 %).
- **Erkundung**: feste Orte (`pois`) geben je Figur einmalig einen Hinweis einer CEE-Entdeckung (hier: „Karte zum alten Schrein“, zwei Hinweise, beide Orte abseits von Gegnern); der Spieler schließt die Entdeckung selbst ab (`discovery.complete`).
- **Prägung**: `game.attune(element)` zeichnet `element.attuned` auf (dauerhaft; die CEE-Regeln prüfen Schwelle und Grenzen).
- Tageszähler (`daily`) beginnen mit jedem Spieltag neu und werden mit dem Spielzustand gespeichert; Ablehnungen der CEE landen im Spiellog statt im Spielfehler.
- Client: Hinweise im Log, Zahlen über der Figur, Charakter-Fenster mit Prägen-Knopf, Entdeckungen mit „Abschließen“, Erkundungsmeilensteine in der Lebensgeschichte.

## Folgen
- Alle Zahlen und Zuordnungen (Beruf je Ware, Hinweisorte, Elementgegner) sind Platzhalter, keine bestätigten Inhalte (Blueprint Fragen 11, 13).
- Offen für spätere Pakete: Erkundungsmeilensteine über feste Hinweisorte hinaus (Regionen), soziale/Gruppenbeiträge als Quelle, Wesensprüfungen im Spiel (AP 6), Tageszähler je Quelle weiter ausdifferenzieren, Botting-/Missbrauchserkennung (Blueprint §70.10) jenseits der Tagesgrenzen.
- Die Kampf-Entwicklung (Kampfpunkte) läuft weiter über den Bericht der CEE mit deren eigenen Tages- und Wiederholungsgrenzen.
