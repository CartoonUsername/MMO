# ADR-0003: Combat Development Engine – Begegnungsberichte, Mehrdimensionalität, Anti-Farming

**Status:** akzeptiert als technische Grundlage. Dimensionen, Aktionen, Richtungen und alle Zahlen sind **Vorschläge** (kein beschlossenes Balancing).

**Kontext:** Die Spielhistorie soll bestimmen, wie ein Charakter kämpft. Mehrere Richtungen gleichzeitig, kein Zwang auf einen Stil, gleiche Pipeline für Spieler/NPCs, reproduzierbar, nicht farmbar.

**Entscheidungen**
1. **Ein Ereignis, Beobachtungen statt Punkte.** `combat.encounter_resolved` trägt nur beobachtete Aktionszähler. Fortschrittspunkte berechnet allein die Engine; Felder mit Punkten werden abgelehnt.
2. **Begegnungs-ID** ist je Charakter einmalig; Wiederholung → `RuleViolation`, nichts wird aufgezeichnet.
3. **Plausibilitätsgrenzen** je Aktion (`max_per_minute`, Dauer, Burst) – unmögliche Berichte werden abgelehnt statt still gekürzt, damit Bugs/Cheats sichtbar werden.
4. **Abnehmende Erträge** statt harter Sperre: Wiederholung desselben Gegnertyps am selben Tag, triviale Gegner, Tageslimit je Dimension (voll → reduziert → 0). Ergebnis (Sieg/Niederlage/Flucht) gewichtet; Niederlagen bringen weniger, aber Fortschritt.
5. **Zeit = `day`** (vom Server gesetzt, monoton). Keine Wanduhr im Replay → deterministisch.
6. **Richtungen sind abgeleitet**, nicht gespeichert, nicht exklusiv, ohne Reset-Zwang; Punkte sinken nie.
7. **Regeln versioniert**: neue Datei `rules_v2.json`; `rules_v1.json` bleibt unverändert und lauffähig (ohne Kampf).
8. Regeldaten werden beim Start validiert (`validate_combat_rules`), Fehlkonfiguration bricht früh ab.

**Vertrauensgrenze (wichtig):** Die Engine kann keine gefälschten Berichte erkennen, die plausibel aussehen. Sie begrenzt den Schaden (Raten, Tageslimits, Einmaligkeit). Der Gameplay-Server muss Berichte selbst aus seiner Kampfsimulation erzeugen; Clients dürfen sie nie senden. Globale Eindeutigkeit der `encounter_id` über Charaktere hinweg und die Teilnehmerzuordnung sind Aufgabe des Servers. **Seit ADR-0006** erzeugt `mmo_sim` die Berichte und vergibt die IDs (Teilnehmerzuordnung/Gruppen weiter offen).

**Bekannte Grenzen / offen**
- `state.encounters` wächst unbegrenzt; Snapshots/Archivierung folgen mit Persistenz (Roadmap 9). Pruning würde Replay-Schutz schwächen und braucht eigene Entscheidung.
- Mehrere Accounts/Bots, Boosting zwischen kooperierenden Spielern: nicht durch diese Engine lösbar; Tageslimits dämpfen es nur.
- Konkrete Fähigkeiten pro Richtung/Stufe: seit ADR-0020 (Regeln v9) als freischaltbare, ausrüstbare Fähigkeiten definiert; ihre Wirkung über die Befehlsfreigabe hinaus ist offen.
