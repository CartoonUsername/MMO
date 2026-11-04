# ADR-0035: Beute auf Schwierigkeit abgestimmt, Beuteabnahme, Wiedererscheinen

**Status:** akzeptiert als erster Stand. **Alle Mengen, Werte und Zeiten sind Platzhalter.**

**Kontext:** Nach dem Balancing (ADR-0034) dauern Kämpfe länger und kosten mehr Lebenspunkte; die ursprüngliche Beute (z. B. 6 Münzen je Wolf) stand in keinem Verhältnis dazu und ließ sich zudem endlos wiederholen („kein stumpfes Wiederholen“ ist eine bestätigte Entscheidung).

**Entscheidungen**
1. **Bezugsgröße:** Sammeln an einem Erzpunkt bringt rund **1,6 Münzen/s** (3 Erz zu 8 Münzen alle 15 s, ohne Risiko). Kampfbeute soll dem Spieler **ca. 2 Münzen/s** einbringen, gerechnet als Beutewert ÷ (Spieleranzahl × (Kampfdauer + 15 s Weg/Wartezeit) × (1 + Lebenspunkteverlust)), mit den Werten des Balancing-Berichts (Testspieler `average`; Boss: `good`, 4 Spieler). Bänder (als Tests): normale Gegner 1,4–3,0, Boss 2,0–4,0.
2. **Beutetabellen** (`drops` in `game_rules_v1.json`): Münzen plus Rohstoffe, die Berufe brauchen (Kräuter, Erz, Barren, Holz, Kohle, Glassand, Frostlilie); Wert = Münzen + Gegenstände zum Referenzwert der Wirtschaft. Beispiele (Wert): Wolf 80, Höhlenbär 158, Moorhexe 150, Steinwächter 204, Alpha 380, Steinherz-Koloss rund 2000 (mit zwei feinen Eisenklingen). Beschworene (`wolf_pup`, `stone_imp`) bringen nichts.
3. **Beuteabnahme** (`loot_decay_permille`: 1000, 1000, 1000, 750, 500, 250, 100): je Figur, Gegnerart und Spieltag sinkt die Menge ab dem vierten Kill; der Zähler beginnt mit jedem Tageswechsel neu und wird mit dem Spielstand gespeichert (nur am selben Tag). In Gruppen gilt der Mittelwert der Faktoren der beitragenden Figuren; es zählt jede beitragende Figur. Mengen werden abgerundet, Einträge mit 0 entfallen. `fight_end` meldet `loot_factor` je Gegnerart.
4. **Wiedererscheinen** (`respawn_ticks_by_type`): Alpha 3 min, Steinwächter 2 min, Boss 10 min (sonst 40 s), damit seltene Gegner nicht dauerhaft farmbar sind.
5. Die Abnahme betrifft nur Beute, **nicht** die Entwicklung der Figur (dort gilt weiter die Wiederholungsabnahme der CEE).

**Absicherung:** `tests/test_loot.py` (Tabellen, Wertbänder gegen das Balancing, Tabelle Kill für Kill, Rundung, je Figur und Art, Gruppenmittel, nur Beitragende, Tageswechsel, Persistenz, Wiedererscheinen je Art, Ereignisfeld); Mutationstests (alle erkannt bis auf eine äquivalente).

**Offen / Grenzen**
- Die Bänder sind aus Modellspielern abgeleitet; echte Spieler (und Marktpreise der Wirtschaft) können Beute entwerten oder überbewerten. Marktpreisdynamik wirkt auf den Referenzwert der Rohstoffe, die Tabellen sind aber fest.
- Keine seltenen Zufallsbeuten, keine Rezeptteile oder Entdeckungsbeweise als Beute, keine Beute-Bindung (handelbar sofort).
- Gruppenbeute verteilt Gegenstände nach dem Gruppenmodus, Münzen gleichmäßig; keine Würfel-/Bedarfsregeln.
