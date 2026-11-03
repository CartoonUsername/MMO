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
| 3 | Combat Development | `combat.` | Schnittstelle (`interfaces.py`), nicht implementiert |
| 4 | Element | `element.` | **implementiert** (9 Elemente, Prägung, 2 + 1 Limit) |
| 5 | Profession | `profession.` | **implementiert** (Erfahrung → Meisterschaftsstufe) |
| 6 | Discovery | `discovery.` | Schnittstelle, nicht implementiert |
| 7 | Crafting | `crafting.` | Schnittstelle, nicht implementiert |
| 8 | Economic Profile | `economy.` | Schnittstelle, nicht implementiert |
| 9 | Character History | (Querschnitt) | **implementiert** (`history.py`: Log, Hash-Kette, Verifikation) |
| 10 | Visual Evolution | `visual.` | Schnittstelle, nicht implementiert (reine Ableitung aus State) |

## Zielarchitektur (Vorschlag, nicht bestätigt)

Der Python-Prototyp ist die **Referenzimplementierung** für Regeln und Tests. Die produktive Server-Engine (z. B. C++/Rust-Dienst oder Unreal-Dedicated-Server-Modul) übernimmt Datenformat (Event-Schema, Regel-JSON) und die Testvektoren des Prototyps. Die Unreal-Seite konsumiert nur den abgeleiteten State (Visual Evolution), schreibt nie direkt.
