# ADR-0034: Balancing mit deterministischen Testspielern

**Status:** akzeptiert als Methode und erster Stand. **Alle Werte (Lebenspunkte, Schaden, Zielbänder) sind Platzhalter**; die Testspieler sind vereinfachte Modelle und ersetzen keine echten Spieltests.

**Kontext:** Nach den Gegnerfähigkeiten (ADR-0032/0033) waren die Gegner entweder trivial (normale Mobs) oder unlösbar (Boss). Ziele laut Entscheidung des Produktverantwortlichen: normale Mobs solo schaffbar, Elite zu zweit, Boss ab 3–4 Spielern.

**Entscheidungen**
1. **Werkzeug `mmo_sim.balance`:** Deterministische Bots spielen über dieselbe Schnittstelle wie ein Client (`LiveEncounter`: Ankündigungen lesen, Anzeigezustand lesen, Befehle senden). Stufen: `novice` (nur leichte Schläge), `average` (Reaktionszeit 6 Ticks, einfaches Ausweichen, jeder dritte Versuch misslingt), `good` (3 Ticks, Parade/perfektes Ausweichen, Unterbrechen und Heilerpriorität, jeder fünfte Versuch misslingt; in Gruppen heilen und schützen die Spieler 2 und 4). Zu kurze Vorwarnzeit kann nicht beantwortet werden; vor einer anstehenden Abwehr schlagen Bots nicht zu (Sperrzeit).
2. **Ankündigung normaler Angriffe:** Neuer Schalter `enemy_abilities.telegraph_basic` (in `sim_rules_v7`): Auch normale Angriffe erzeugen ein `telegraph` (`kind: basic`, `ability: basic_attack`) – für die Client-Anzeige und die Abwehr. Nur Anzeige, keine Wirkung auf den Kampf.
3. **Neue Regelversion `sim_rules_v7.json`** (v6 und alle Vektoren bleiben unverändert): Lebenspunkte der Familien erhöht (Wolf 300→850, Bär 900→2100, Moorhexe 350→1650, Steinwächter 1500→2400 …), Rudelwelpen (`wolf_pup`) als Beschworene statt Wölfen, Heilen des Irrlichts 30 %→20 %, Alpha 900→1300; Boss mit eigenen kürzeren Fähigkeiten (`colossus_slam` Vorwarnung 8, `colossus_quake` 8), 7000 Leben, Schaden 240. Der Spielserver nutzt v7; der Steinwächter steht nicht mehr im Rudelradius des Bosses.
4. **Zielbänder (Testspieler `average`, gleiche Stufe, als Tests kodiert in `tests/test_balance.py`):** normale Mobs und kleine Gruppen solo ≥ 90 % Sieg mit Verlust zwischen ca. 10 % und 70 % der Lebenspunkte je Familie; Verlust sinkt mit der Gruppengröße; Fertigkeit wird belohnt (novice > average > good bei Antwortbarem); Alpha-Rudel solo ≤ 20 % Sieg, zu zweit ≥ 70 % (Verlust 40–80 %), zu viert ≥ 90 %; Boss: nie für `novice`, nie unter 3 Spielern für `average`, `good` erst ab 3 Spielern mit spürbarem Verlust.
5. **Bericht:** `docs/BALANCE_REPORT.md` wird mit `python -m mmo_sim.balance write docs/BALANCE_REPORT.md` erzeugt; ein Test hält ihn mit den Regeln synchron (`check`). Er zeigt je Familie und Gruppengröße Sieg ‰ / Dauer / Verlust für alle drei Stufen.

**Absicherung:** `tests/test_balance.py` (Regeln v7, Bots, Zielbänder, Berichtssynchronität, Kommandozeile), `tests/test_enemy_sim.py` (Ankündigung normaler Angriffe); Mutationstests der Ankündigung (alle erkannt).

**Offen / Grenzen**
- Die Bots sind Modelle: echte Spieler reagieren anders, Gegnerwirkung hängt stark von Ausweich-Treffsicherheit ab; Ergebnisse sind Richtwerte. Echte Spieltests müssen die Zielbänder bestätigen oder verschieben.
- Mehrere Stufen-Unterschiede (Unter-/Übertraining), Ausrüstung, Fähigkeiten der Spieler (Ausrüstung, Elemente, Wesensformen) und Heiler-/Tank-Rollen sind nicht modelliert. Beute-Mengen sind noch nicht auf die neue Schwierigkeit abgestimmt (Wirtschaft).
- Kampfdauer liegt bei 15–140 s; ob das zum Tempo des Spiels passt, ist eine Designfrage.
