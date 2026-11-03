# Architektur der Character Evolution Engine (CEE)

## Leitprinzipien

1. **Event Sourcing.** Die einzige Wahrheit ist die append-only Charakterhistorie. Jeder Zustand (Wesen, Elemente, Berufe …) ist eine deterministische Ableitung (Replay) aus dieser Historie.
2. **Serverautoritativ & nachvollziehbar.** Jedes Ereignis trägt `schema_version`, `rules_version` und einen Hash-Verweis auf den Vorgänger (Manipulationserkennung, Audit).
3. **Datengetrieben & versionierbar.** Schwellen, Wesensformen, Berufe stehen in versionierten Regeldateien (`rules_v1.json`), nicht im Code.
4. **Nur die Spielfigur.** Eingaben sind ausschließlich Spielereignisse der Figur; keine Analyse realer Persönlichkeit.
5. **Gleiche Pipeline für Spieler und NPCs.** `identity.created.kind` ist der einzige Unterschied.
6. **Engine-Isolation.** Jede Engine besitzt einen Teilzustand (`state.parts[name]`) und kennt nur Ereignisse ihres Präfixes; Querverweise lesen den Zustand anderer Engines nur lesend.

## Ablauf

```
record(type, payload) → Engine.validate(state, event)  (RuleViolation bei Regelbruch)
                      → EventLog.append (Hash-Kette)
                      → Engine.apply(state, event)
load(character)       → Replay des Logs durch dieselben Engines (deterministisch)
```

## Die zehn Engines

| # | Engine | Ereignis-Präfix | Status |
|---|---|---|---|
| 1 | Identity | `identity.` | **implementiert** (Typ Spieler/NPC, Klasse, XP/Level) |
| 2 | Essence (Wesen) | `essence.` | **implementiert** (Eignung, Prüfung, dauerhafte Annahme) |
| 3 | Combat Development | `combat.` | **implementiert** (Metriken, Entwicklungsrichtungen, Anti-Farming; konkrete Fähigkeiten offen) |
| 4 | Element | `element.` | **implementiert** (9 Elemente, Prägung, 2 + 1 Limit) |
| 5 | Profession | `profession.` | **implementiert** (Erfahrung → Meisterschaftsstufe) |
| 6 | Discovery | `discovery.` | Schnittstelle, nicht implementiert |
| 7 | Crafting | `crafting.` | Schnittstelle, nicht implementiert |
| 8 | Economic Profile | `economy.` | Schnittstelle, nicht implementiert |
| 9 | Character History | (Querschnitt) | **implementiert** (`history.py`: Log, Hash-Kette, Verifikation) |
| 10 | Visual Evolution | `visual.` | Schnittstelle, nicht implementiert (reine Ableitung aus State) |

## Combat Development Engine (Details, siehe ADR-0003)

- Einziges Ereignis: `combat.encounter_resolved` – ein **serverseitig bestätigter Begegnungsbericht** mit beobachteten Aktionszählern (`actions: {Aktion: Anzahl}`), Gegnertyp/-stufe, Ergebnis, Dauer und Spieltag. Das Payload-Schema ist strikt: jedes unbekannte Feld (z. B. `points`, `strength`) wird abgelehnt.
- Punkte entstehen nur in der Engine: Aktionen → Dimensionen (Gewichte aus Regeln) × Ergebnis × Relevanz × Wiederholungsabnahme, danach Tageslimit je Dimension (voller Satz bis `full_cap`, reduziert bis `hard_cap`, dann 0).
- Exploit-Schutz: eindeutige `encounter_id` je Charakter, Plausibilität der Aktionsraten (`max_per_minute`, Dauer, Burst), Tag darf nicht zurückspringen, Wiederholungsabnahme je Gegnertyp und Tag, Abwertung trivialer Gegner.
- Entwicklungsrichtungen sind eine **abgeleitete Sicht** (`reached_directions`): gewichtete Summen der Dimensionspunkte gegen Stufenschwellen. Nicht exklusiv, Punkte sinken nie, jede Dimension bleibt unabhängig von der Grundklasse trainierbar.
- Ganzzahl-Arithmetik (Promille) für Bit-Identität bei der späteren C++-Portierung (ADR-0004).
- Grenze: Die Engine kann nur prüfen, was der Bericht behauptet. Dass der Bericht echt ist, muss der Gameplay-Server sicherstellen (siehe „Vertrauensgrenze“ in ADR-0003).

Querverbindung: Wesensformen können Mindeststufen von Kampfrichtungen verlangen (`combat_directions` in den Essence-Regeln); die Essence Engine liest dafür nur die abgeleitete Sicht der Combat Engine.

## Serverseitiger Kampfkern `mmo_sim` (ADR-0006)

Deterministische 1:1-Simulation (Ganzzahlen, 10 Ticks/s). Der Client sendet nur Befehle; die Simulation entscheidet über Treffer, Ausweichen, Block, Parade, Betäubung und Verlangsamung und erzeugt daraus den Begegnungsbericht für `combat.encounter_resolved`. `EncounterServer` vergibt IDs, Gegner, Stufe und Tag. Die Verträglichkeit mit den CEE-Plausibilitätslimits wird rechnerisch (`check_compatibility`) und durch Spam-Tests geprüft. Alle Zahlen sind vorläufig.

## Golden Test Vectors (ADR-0005)

`reference/golden/*.json` enthalten Szenarien mit erwarteten Ereignis-/Zustands-Hashes, abgelehnten Eingaben und abgeleiteten Sichten. Jede Portierung muss sie bit-identisch bestehen; Python-Tests erzwingen, dass die Vektoren mit der Referenz übereinstimmen. Format und Prüfverfahren: `reference/golden/README.md`.

## Zielarchitektur (Vorschlag, nicht bestätigt)

Der Python-Prototyp ist die **Referenzimplementierung** für Regeln und Tests. Die produktive Server-Engine (z. B. C++/Rust-Dienst oder Unreal-Dedicated-Server-Modul) übernimmt Datenformat (Event-Schema, Regel-JSON) und die Testvektoren des Prototyps. Die Unreal-Seite konsumiert nur den abgeleiteten State (Visual Evolution), schreibt nie direkt.
