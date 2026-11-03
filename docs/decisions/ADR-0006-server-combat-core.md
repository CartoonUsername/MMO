# ADR-0006: Serverseitiger Kampfkern (mmo_sim) erzeugt die Begegnungsberichte

**Status:** akzeptiert als technische Grundlage. Alle Zahlen, Gegner, Befehle und Zeitfenster sind **vorläufige Referenzwerte**, keine beschlossenen Spielinhalte oder Balancing.

**Kontext:** ADR-0003 nannte eine Vertrauensgrenze: Die CEE kann keine plausibel gefälschten Kampfberichte erkennen. Berichte müssen deshalb aus einer serverseitigen Simulation stammen.

**Entscheidungen**
1. **Eigenes Paket `mmo_sim`**, getrennt von `mmo_cee`. Die CEE kennt nur Berichte; die Simulation kennt Kampfmechanik. Abhängigkeit nur in eine Richtung (`mmo_sim` → `mmo_cee`).
2. **Deterministisch, ganzzahlig, ohne Zufall** (Tick = 100 ms). Gleiche Eingaben → gleiches Ergebnis, passend zur Vorgabe „keine zufälligen, unkontrollierbaren Kampfentscheidungen“ und zur späteren Portierung (ADR-0004).
3. **Der Client sendet nur Befehle** (`light`, `heavy`, `dodge`, `block`, `stun`, `slow`, `flee`) mit Tick. Ausführung, Treffer, Ausweichen, Block und Parade entscheidet die Simulation anhand von Ausdauer, Busy-Zeit, Abklingzeit und Zeitfenstern. Nicht ausführbare Befehle werden ignoriert und gezählt, ungültige Eingaben (Typ, Bereich, Reihenfolge, Menge) lehnen die ganze Einreichung ab.
4. **Der Server vergibt Begegnungs-ID, bestimmt Gegner, Gegnerstufe und Spieltag.** Eine ID ist an einen Charakter gebunden und genau einmal abschließbar. Ungültige Eingaben lassen die Begegnung offen, ein erfolgreicher Abschluss verbraucht sie. Begegnungen ohne bewertbare Aktion erzeugen kein CEE-Ereignis.
5. **Verträglichkeit mit der CEE ist prüfbar:** `max_actions_per_minute` berechnet die theoretische Obergrenze je Aktion aus den Simulationsregeln, `check_compatibility` vergleicht sie mit den CEE-Limits. Ein Test fährt zusätzlich Spam-, Timing- und 120 Pseudozufallsmuster gegen alle Gegner und verlangt, dass die CEE jeden erzeugten Bericht akzeptiert.
6. Regeln versioniert in `mmo_sim/data/sim_rules_v1.json` (unveränderlich, ADR-0004).

**Bekannte Grenzen / offen**
- Nur 1:1 und ohne Raum/Geometrie (keine Position, kein Winkel); Unterstützungsaktionen (`ally_heal`, `ally_shield`) und Gruppen sind noch nicht simuliert, die CEE kennt sie bereits.
- Zeitlimit zählt als `fled` (Vorschlag); Mindestdauer des Berichts 5 s (CEE-Minimum), kürzere Kämpfe werden aufgerundet.
- Dummy-/Mob-Farming wird durch die CEE-Wiederholungsabnahme auf 10 % des Ertrags begrenzt; das Tageslimit greift gegen *denselben* Gegnertyp praktisch nie. Ob das Spielziel ist, ist eine Balancingfrage.
- Boosting zwischen kooperierenden Spielern und Mehrfachaccounts bleibt ungelöst.
- Die Simulation ist noch nicht durch Golden Vectors abgesichert (Portierung später relevant).
