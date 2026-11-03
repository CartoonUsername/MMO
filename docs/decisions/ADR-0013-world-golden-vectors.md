# ADR-0013: Golden Vectors der Weltseite

**Status:** akzeptiert. Die Inhalte der Szenarien (Rezepte, Preise, Firmenregeln) sind Platzhalter.

**Kontext:** ADR-0005 sichert die CEE, die Simulation und die Optik ab. Die Weltseite (Inventar, Entdeckungsregister, Herstellung, Handel, Firmen; ADR-0009 bis ADR-0012) ist Logik mit Zustand und Rollback; ein Port muss sie ebenso bit-identisch nachbilden können – einschließlich Ablehnungen und Floor-Division bei negativen Werten.

**Entscheidungen**
1. **Skripte statt Einzelfälle.** Ein Szenario ist eine Folge von Operationen mit erwarteter Reaktion (ok + Rückgabewert | Fehlerklasse) und dem SHA-256 des **gesamten Weltzustands nach jedem Schritt**. So fällt eine Abweichung am ersten betroffenen Schritt auf, auch wenn sie erst später sichtbar würde.
2. **Weltzustand umfasst alles:** Inventar, beide Register, die ID-Zähler der Dienste und die CEE-Zustands-Hashes aller Figuren – die CEE-Logik wird mitgeprüft.
3. **Nur Fehlerklassen, keine Texte.** `WorldError` (Weltregel) und `RuleViolation` (CEE). Ob eine Ablehnung die Welt verändert, steht im Hash des Schritts (Ausnahmen: verbrauchte Herstellungs-ID, `expired`-Antrag).
4. **Echte Abläufe statt Fixtures.** Aufstiege laufen über Einstellung, Tagesabschluss, Beförderung und echten Handel (Volumenpunkte aus der CEE). Zielbezogene Figuren werden über die stabile Ziel-Ableitung gewählt; Lohn 19 bei Bedarf 20 erzeugt negative Floor-Fälle.
5. **Zufallsskripte werden ausgeschrieben.** Zwei zustandsbewusste Skripte (Seeds 4 und 9) wählen Operationen anhand des laufenden Weltzustands (offene Firmen, Angebote, Anträge), gelegentlich bewusst unpassend. Der Generator (xorshift32) liegt nur in der Referenz; die Datei enthält fertige Skripte.
6. **Einheitlich mit ADR-0005:** kanonisches JSON, Ganzzahlen, Erzeugung per `write`, Prüfung per `check`, Test erzwingt Byte-Gleichheit mit der Regenerierung; Regeldateien per SHA-256 gebunden.

**Absicherung:** `tests/test_world_golden.py` (Regenerierung byte-gleich, Manipulationen werden erkannt, jede Operation mit Erfolgs- und Fehlerbeispiel, Münzerhaltung, unveränderte Welt bei Ablehnung, negative Floor-Fälle, echte Endzustände, deterministische Zufallsskripte).

**Offen / Grenzen**
- Die Vektoren fixieren das aktuelle Verhalten, auch Eigenheiten (Herstellungs-ID wird bei späterem Scheitern verbraucht). Änderungen am Weltverhalten erfordern neue Regelversionen oder Formatversion und bewusstes Neuerzeugen.
- Persistenz, Migration und Netzwerkprotokoll sind nicht Teil der Vektoren; Snapshots (`to_json`) sind Bestandteil des Zustands, aber noch kein Speicherformat-Vertrag.
- Mehrere Dienste gleichzeitig (Parallelität) werden nicht abgedeckt; die Reihenfolge der Schritte ist Teil des Vertrags.
