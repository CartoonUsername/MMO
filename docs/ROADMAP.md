# Priorisierter Entwicklungsplan (Character Evolution Engine)

Priorität 1 = zuerst. Jeder Schritt: kleiner Commit, Tests grün.

| Prio | Schritt | Status |
|---|---|---|
| 1 | Zustandsbericht, Architektur, ADRs | erledigt |
| 2 | Kern: Event-Log mit Hash-Kette, Projector, Regel-Loader | erledigt |
| 3 | Identity, Element, Profession, Essence (Basisregeln) | erledigt |
| 4 | Combat Development Engine: Metriken, Richtungen, Anti-Farming | **erledigt** (Fähigkeiten-Freischaltung bleibt offen, bis Fähigkeiten beschlossen sind) |
| 4b | Serverseitiger Kampfkern `mmo_sim` (1:1, Berichte aus Simulation) | **erledigt** (ADR-0006); Golden Vectors der Simulation erledigt; Befehlsfreigabe durch Fähigkeiten (Regeln v9, ADR-0020) und passive Wirkung (ADR-0021) erledigt; Gruppenkampf mit Heilen/Schild (ADR-0022) erledigt; Kampf gegen mehrere Gegner mit Fokus/Flächenangriff (ADR-0026) erledigt; eigene Fähigkeitsbefehle als Beispiel (ADR-0027) erledigt; offen: weitere Fähigkeitsarten/Elemente, Gegnerverhalten (Heiler/Bosse), Raum/Geometrie |
| 5 | Wesensmatrix erweitern: gewichtete Bewertung, Entscheidungsereignisse, Vor-/Nachteile (rules_v4, ADR-0007) | **erledigt** (Mechanik); offen: echte Formen/Inhalte, Wirkung der Modifikatoren, geheime Formen über Discovery |
| 6 | Discovery + Crafting | **erledigt** (Mechanik; Discovery ADR-0009, Crafting ADR-0010, Golden Vectors); offen: Werkzeuge/Werkstätten, Materialgewinnung, Märkte, Experimentieren |
| 7 | Economic Profile (Handel, Unternehmen, Karriere) | **erledigt** (Mechanik, ADR-0011, Golden Vectors); offen: regionale Preise, Weltereignisse als Schock-Auslöser, Logistik |
| 7a | Vertical Slice (Unity 6 URP, Spielserver `mmo_game`, `docs/VERTICAL_SLICE.md`) | **Server fertig und getestet** (ADR-0028); Unity-Client als Quellcode vorhanden, in Unity ungeprüft; Persistenz, Anmeldung (ADR-0029) sowie Gelände/Kollision (ADR-0030) und Gegnerbewegung (ADR-0031) fertig; Gegnerfähigkeiten (Regeln, Baukasten, Wirkung im Kampf, Spielserver; ADR-0032/0033) erstes Balancing (ADR-0034) und abgestimmte Beute (ADR-0035) fertig; offen: Kollision/Gelände, Client-Vorhersage |
| 7b | Firmensimulation (`mmo_world`: Register, Mitarbeiter, Gehälter, Loyalität, Abwerben, Anteile, Beschlüsse) | **erledigt** (Mechanik, ADR-0012); Firmenproduktion erledigt (Referenz, ADR-0016); Preisdynamik (Regeln v8, ADR-0017) erledigt; direkter Zwei-Parteien-Handel (ADR-0023) erledigt; Push-Ereignisse als Postfach mit Abruf (ADR-0024) erledigt; Gruppenbildung (ADR-0025) erledigt; Regelversions-Migration (ADR-0018) erledigt; offen: Aufträge/Kunden, Lieferketten, Filialen/Töchter, Dividenden; Golden Vectors der Weltseite erledigt (ADR-0013); Persistenz/Migration als Referenz erledigt (ADR-0014); Markt/Preisbildung (Orderbuch, ADR-0015) erledigt |
| 8 | Visual Evolution (State → Erscheinungsparameter, deterministisch) | **erledigt** (Mechanik, ADR-0008, Golden Vectors); offen: echte Optik/Assets, Ausrüstung/Kosmetik, Übergänge |
| 9 | Snapshots, Regel-Migration/Rebuild, Anti-Cheat-Plausibilitätsregeln | offen |
| 9b | Golden Test Vectors (Referenz ↔ Portierung) | **erledigt** (`reference/golden/`, ADR-0005) |
| 10 | Server-Schnittstelle (Protokoll) + Portierung/Anbindung Unreal | Befehlsschicht als Referenz erledigt (`mmo_server`, ADR-0019, `docs/PROTOCOL.md`); offen: Transport, Anmeldung, Push, Echtzeit-Kampfkanal, Mehrserver-Betrieb, Engine-Anbindung |

Nicht in dieser Phase: Kampfechos, Städte, Wirtschaftssimulation (eigene Module, greifen später über Ereignisse auf die CEE zu).
