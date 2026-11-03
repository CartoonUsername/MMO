# Priorisierter Entwicklungsplan (Character Evolution Engine)

Priorität 1 = zuerst. Jeder Schritt: kleiner Commit, Tests grün.

| Prio | Schritt | Status |
|---|---|---|
| 1 | Zustandsbericht, Architektur, ADRs | erledigt |
| 2 | Kern: Event-Log mit Hash-Kette, Projector, Regel-Loader | erledigt |
| 3 | Identity, Element, Profession, Essence (Basisregeln) | erledigt |
| 4 | Combat Development Engine: Metriken, Richtungen, Anti-Farming | **erledigt** (Fähigkeiten-Freischaltung bleibt offen, bis Fähigkeiten beschlossen sind) |
| 4b | Serverseitiger Kampfkern `mmo_sim` (1:1, Berichte aus Simulation) | **erledigt** (ADR-0006); Golden Vectors der Simulation erledigt; offen: Unterstützung/Gruppen, Raum/Geometrie |
| 5 | Wesensmatrix erweitern: gewichtete Bewertung, Entscheidungsereignisse, Vor-/Nachteile (rules_v4, ADR-0007) | **erledigt** (Mechanik); offen: echte Formen/Inhalte, Wirkung der Modifikatoren, geheime Formen über Discovery |
| 6 | Discovery + Crafting (Rezept-/Verfahrensentdeckung, Seltenheit) | offen |
| 7 | Economic Profile (Handel, Unternehmen, Karriere) | offen |
| 8 | Visual Evolution (State → Erscheinungsparameter, deterministisch) | offen |
| 9 | Snapshots, Regel-Migration/Rebuild, Anti-Cheat-Plausibilitätsregeln | offen |
| 9b | Golden Test Vectors (Referenz ↔ Portierung) | **erledigt** (`reference/golden/`, ADR-0005) |
| 10 | Server-Schnittstelle (Protokoll) + Portierung/Anbindung Unreal | offen |

Nicht in dieser Phase: Kampfechos, Städte, Wirtschaftssimulation (eigene Module, greifen später über Ereignisse auf die CEE zu).
