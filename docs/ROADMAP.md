# Priorisierter Entwicklungsplan (Character Evolution Engine)

Priorität 1 = zuerst. Jeder Schritt: kleiner Commit, Tests grün.

| Prio | Schritt | Status |
|---|---|---|
| 1 | Zustandsbericht, Architektur, ADRs | erledigt |
| 2 | Kern: Event-Log mit Hash-Kette, Projector, Regel-Loader | erledigt |
| 3 | Identity, Element, Profession, Essence (Basisregeln) | erledigt |
| 4 | Combat Development Engine: Metriken, Richtungen, Anti-Farming | **erledigt** (Fähigkeiten-Freischaltung bleibt offen, bis Fähigkeiten beschlossen sind) |
| 5 | Wesensmatrix erweitern (inkl. Kampfrichtungen als Wesensvoraussetzung) (mehr Formen, Gewichtung statt harter Schwellen, Entscheidungsereignisse) | offen |
| 6 | Discovery + Crafting (Rezept-/Verfahrensentdeckung, Seltenheit) | offen |
| 7 | Economic Profile (Handel, Unternehmen, Karriere) | offen |
| 8 | Visual Evolution (State → Erscheinungsparameter, deterministisch) | offen |
| 9 | Snapshots, Regel-Migration/Rebuild, Anti-Cheat-Plausibilitätsregeln | offen |
| 10 | Server-Schnittstelle (Protokoll) + Portierung/Anbindung Unreal | offen |

Nicht in dieser Phase: Kampfechos, Städte, Wirtschaftssimulation (eigene Module, greifen später über Ereignisse auf die CEE zu).
