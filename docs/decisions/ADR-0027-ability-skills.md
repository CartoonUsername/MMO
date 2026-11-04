# ADR-0027: Eigene Fähigkeitsbefehle

**Status:** akzeptiert als technische Grundlage. **Alle Zahlen und Fähigkeiten in `sim_rules_v5.json` (Abschnitt `skills`) sind Platzhalter**, kein Balancing, keine bestätigten Spielinhalte.

**Kontext:** Bisher geben Fähigkeiten (ADR-0020/0021) nur Grundbefehle frei (`heavy`, `stun`, `slow`) oder wirken passiv. Es fehlen Fähigkeiten mit eigenem Einsatz: Kosten, Abklingzeit, Wirkung und Zustände.

**Entscheidungen**
1. **Abschnitt `skills`** in den Simulationsregeln (nicht in den CEE-Regeln): jeder Eintrag ist ein eigener Befehl mit `ability` (Fähigkeit der CEE, höchstens ein Befehl je Fähigkeit), `kind`, `cost`, `busy`, `cooldown` und `counts_as`. Die CEE bleibt unverändert; `check_compatibility` meldet unbekannte Fähigkeiten und Raten über dem CEE-Limit (Einsätze mit `counts_as` fließen in `max_actions_per_minute` ein).
2. **Vier Arten:** `burst_dot` (Sofortschaden plus Brand: `dot.damage` alle `dot.interval` Ticks für `dot.ticks` Ticks; ein neuer Einsatz ersetzt den laufenden Brand; Brandschaden erhöht die Bedrohung des Wirkenden und endet mit dem Gegner), `evade` (Treffer innerhalb von `ticks` Ticks gehen ins Leere, nur für den Wirkenden), `mitigate` (erlittener Schaden `damage_permille` für `ticks` Ticks, wirkt zusätzlich zu Block und passiven Modifikatoren), `restore_stamina` (Ausdauer + `amount`, höchstens Maximum).
3. **Nur in der Mehrgegner-Simulation** (`mmo_sim.pack`, die den allgemeinen Fall enthält); Einzel- und Gruppensimulation bleiben unverändert (alle bisherigen Vektoren byteidentisch). Unter Regeln ohne `skills` ist das Ergebnis identisch (Äquivalenztest v4 gegen v5).
4. **Freigabe:** Der Server schaltet den Befehl nur frei, wenn die zugehörige Fähigkeit ausgerüstet ist (bei Figuren mit Regeln ≥ v9); Figuren ohne Fähigkeitssystem (ältere Regeln) dürfen alle Befehle. `allowed` in der Simulation sperrt ihn wie jeden anderen Befehl.
5. **Entwicklung:** Nur `cast_ember` zählt (ein `heavy_hit` je Einsatz); die übrigen Befehle bringen keine Entwicklungspunkte (kein Farmen von Nutzbefehlen).
6. **Golden Vectors:** `golden_pack` läuft jetzt unter `sim_rules_v5.json` (Fälle für Brand, Ersatz, Abbruch, Bedrohung, Ausweichfenster, Schleier mit Block, Grenzen, Fehlerfälle).

**Absicherung:** `tests/test_pack.py` (Regeln, Äquivalenz, Mechanik inkl. Fenstergrenzen, Server), Mutationstests (siehe Statusbericht).

**Offen / Grenzen**
- Vier Beispielfähigkeiten; weitere Arten (Gebiet, Kanalisierung, Beschwörung, Heilung über Zeit) und Elementwirkungen fehlen, ebenso Fähigkeitsstufen und Verbesserungen.
- Nur im Mehrgegnerkampf verfügbar; Einzel-/Gruppenkampf kennen die Befehle nicht.
- Kein Raum, keine Reichweite; Entwicklungspunkte für Nutzbefehle sind nicht entschieden.
