# ADR-0020: Kampffähigkeiten und Ausrüstung (Combat Development Engine, Regeln v9)

**Status:** akzeptiert als technische Grundlage. **Alle Fähigkeiten, Voraussetzungen, Plätze und Befehle in `rules_v9.json` sind Platzhalter**, keine bestätigten Spielinhalte (ADR-0003 ließ „konkrete Fähigkeiten“ offen).

**Kontext:** Bestätigt: Kampf ist dritte-Person-Action; die Entwicklung folgt allein dem Kampfverhalten (Richtungen, nicht exklusiv, ohne Reset-Zwang); Spieler und NPCs laufen durch dieselbe Pipeline; serverautoritativ. Bisher gab es nur Entwicklungsrichtungen und Stufen, aber nichts, was daraus im Kampf folgt.

**Entscheidungen**
1. **Neue Regelversion `rules_v9.json`** (= v8 + `combat.abilities` + `combat.loadout`). Ältere Versionen sind unverändert (kein Teilzustand, kein Ereignis, alle bisherigen Golden Vectors byte-identisch).
2. **Freischaltung ist abgeleitet, nie gespeichert:** Eine Fähigkeit hat Voraussetzungen aus Wachstumsgrößen – Richtung+Stufe (`reached_directions`), geprägte Elemente, Charakterstufe, Wesensform. Weil Punkte, Prägungen, Stufe und Wesensform nie sinken, sind Freischaltungen **dauerhaft**; ein Wechsel des Stils nimmt nichts weg („kein Zwang auf einen Stil“). `ability_blockers` nennt, was fehlt (für die UI und Tests).
3. **Ausrüstung ist ein Ereignis** `combat.loadout_set {abilities, day}` (neuer Zustand `combat.loadout`, `loadout_day`): nur freigeschaltete, eindeutige Fähigkeiten, höchstens so viele wie die Platztabelle nach Stufe erlaubt (`slots_by_level`, Platzhalter 2/3/4 bei Stufe 1/10/25), Tag nicht rückwärts; Neusetzen ist jederzeit erlaubt (kostenlos, kein Wiederholen-Zwang). Das Gateway setzt den Tag selbst (`combat.set_loadout`, Liste von Namen).
4. **Befehlsfreigabe für die Simulation:** `allowed_commands` = Grundbefehle (`light dodge block flee`) ∪ Befehle der **ausgerüsteten** Fähigkeiten (`heavy` ← power_strike, `stun` ← disrupting_blow, `slow` ← hindering_mark). `simulate(..., allowed)` ignoriert nicht erlaubte Befehle (zählt sie als `ignored_inputs`, `flee` geht immer); `EncounterServer.finish` übergibt die Freigabe der Figur. Ohne Fähigkeiten in den Regeln (≤ v8) gilt `None` = alle Befehle, wie bisher. Fähigkeiten ohne Simulationsbefehl (`command: null`: Schild, Konter, Unterstützung, Element, …) sind schon freischalt- und ausrüstbar, wirken aber erst, wenn Gruppen/Raum/Zustände in der Simulation existieren.
5. **Migration:** v8→v9 ergänzt `combat.loadout=[]`, `loadout_day=0` (erste echte Zustandsmigration, `STATE_MIGRATIONS`, ADR-0018); der Fortschritt zählt sofort für die Freischaltung. `upgrade_world` läuft von v7 über v8 nach v9.
6. **Golden Vectors:** CEE-Szenario `combat_abilities_loadout` (v9; `derived`: `unlocked_abilities`, `ability_progress`, `loadout_slots`, `allowed_commands`); Simulationsfälle mit `allowed` (neues optionales Feld, bisherige Fälle unverändert).
7. **Validierung der Regeldaten:** Richtung/Stufe müssen existieren, Voraussetzungsschlüssel bekannt, Befehle eindeutig und kein Grundbefehl, `flee` immer Grundbefehl, Platztabelle bei Stufe 1 beginnend und nicht fallend.

**Absicherung:** `tests/test_abilities.py` (21 Tests: Regelprüfung, jede Voraussetzungsart inkl. Grenzen, Ereignis-Ablehnungen, Plätze nach Stufe, Replay, ältere Regeln unberührt, Simulationsfreigabe inkl. Begegnungsserver, Migration, Welt-Upgrade, Gateway) plus Golden Vectors; Mutationstests (zwei Überlebende sind gleichwertig bzw. wurden mit Tests geschlossen).

**Offen / Grenzen**
- Wirkung der Fähigkeiten: passive Modifikatoren seit ADR-0021; offen sind eigene Fähigkeitsbefehle (Kosten, Abklingzeit, Zustände), Gruppen-/Unterstützungskampf, Raum/Winkel, Kampfechos, Elementfähigkeiten in der Simulation, Fähigkeitsstufen/Verbesserung durch Nutzung.
- Der Spieler wählt aus freigeschalteten Fähigkeiten; ob Fähigkeiten zusätzlich gelernt/entdeckt werden (Verbindung zum Entdeckungssystem) ist offen.
- Zahlen, Namen und Zuordnung zu Befehlen sind Vorschläge; ein Balancing steht aus.
