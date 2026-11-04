# Technischer Zustandsbericht

Stand: 2026-11-03 · Arbeitsbranch `claude/awesome-dirac-9k6p3n` · `main` unverändert (nur `README.md` mit `# MMO`)

> Korrektur: Frühere Fassungen dieses Berichts beschrieben zuerst den Ausgangszustand („kein Code“) und hängten den Stand nach der Implementierung an. Dieser Bericht beschreibt ausschließlich den **aktuellen** Zustand des Arbeitsbranches. Der Ausgangszustand steht nur noch im Abschnitt „Historie“.

## Aktueller Zustand (verifiziert durch Testlauf)

| Bereich | Stand |
|---|---|
| Referenzimplementierung | `reference/python/mmo_cee/` – **vorhanden**, nur Standardbibliothek |
| Implementierte Engines | Identity, Element, Profession, Essence, Combat Development, Visual Evolution, Discovery, Crafting, **Economic Profile** + Character History (Event-Log, Hash-Kette, Replay) |
| Regeln | `rules_v1.json` (ohne Kampf), `rules_v2.json` (v1 + `combat`), `rules_v3.json` (v2 + Wesensform mit Kampfrichtungs-Voraussetzung), `rules_v4.json` (v3 + Wesensbewertung mit Entscheidungen, ADR-0007), `rules_v5.json` (v4 + Entdeckungen, geheime Wesensform, ADR-0009), `rules_v6.json` (v5 + Handwerk: Rezepte, Techniken, ADR-0010), `rules_v7.json` (v6 + Wirtschaft: Handel, Laufbahn, Gründung, ADR-0011); v1–v6 unverändert, Standard ist v7 |
| Tests | **1228** `unittest`-Tests, alle grün (`cd reference/python && python -m unittest discover -s . -t . -v`) |
| Weltzustand | `reference/python/mmo_world/` – `DiscoveryRegistry` (Pionier, Lehrfenster), `DiscoveryService` (transaktional mit der CEE), `Inventory` (atomar), `CraftingService` (Herstellung, ADR-0010) `TradeService` (Handel, ADR-0011) sowie `CompanyRegistry`/`CompanyService` (Firmensimulation, ADR-0012; Regeln `company_rules_v1.json`) |
| Kampfsimulation | `reference/python/mmo_sim/` – deterministischer 1:1-Kampfkern, `EncounterServer` (ADR-0006), `sim_rules_v1.json` (vorläufige Werte) |
| Golden Test Vectors | `reference/golden/` (CEE, 24 Szenarien, `mmo_cee.golden`) `reference/golden_sim/` (Simulation, 96 Fälle, `mmo_sim.golden`) `reference/golden_group/` (Gruppenkampf, 57 Fälle, `mmo_sim.golden_group`), `reference/golden_pack/` (Mehrgegnerkampf, `mmo_sim.golden_pack`), `reference/golden_enemies/` (Gegner-Baukasten, `mmo_sim.golden_enemies`), `reference/golden_enemy_fights/` (Kämpfe mit Gegnerfähigkeiten, `mmo_sim.golden_enemy_fights`), `reference/golden_visual/` (Visual Evolution, 21 Fälle, `mmo_cee.golden_visual`) und `reference/golden_world/` (Weltseite, 17 Szenarien mit Welt-Hash je Schritt, `mmo_world.golden`, ADR-0013); Format: `reference/golden/README.md` |
| Dokumentation | `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, ADR-0001 bis ADR-0012, `Game/PRODUCTION_READINESS.md`, `Game/WINDOWS_SETUP_CHECKLIST.md` |
| Unreal-Projekt | nicht vorhanden (bewusst; erst nach Windows-Checkliste und Freigabe) |

## Noch nicht implementiert

Weitere Arten eigener Fähigkeitsbefehle und Elementwirkungen (vier Beispiele gibt es, ADR-0027), Fähigkeitsstufen, Raumkampf (Gruppenkampf ohne Raum ist da, ADR-0022; mehrere Gegner ohne Raum, ADR-0026), Produktion/Offline-Produktion/Aufträge der Firmen, Filialen/Töchter, Dividenden, Märkte/Preisbildung/NPC-Wirtschaft, Werkzeuge/Werkstätten/Materialgewinnung, Wirkung der Entdeckungen auf Wirtschaft/Städte, Persistenz von Registry und Inventar, echte Optik/Assets zur Visual Evolution (nur Parametermechanik), Persistenz/Snapshots, Server-Protokoll, C++-Portierung (Vektoren liegen bereit).

## Nicht bestätigte Inhalte (Vorschläge)

- Wesensformen, Gewichte, Schwellen, Entscheidungen und Vor-/Nachteile in den Regeldateien (`ember_kin`, `umbral_kin`, `stone_born`, `tide_walker`, `grove_warden`) sind Platzhalter zur Mechanikprüfung.
- Kampfdimensionen (Kraft, Präzision, Mobilität, Kontrolle, Verteidigung, Unterstützung), Aktionstypen, Entwicklungsrichtungen (`vanguard`, `duelist`, …), alle Gewichte, Schwellen, Tageslimits und Raten in `rules_v2.json` sind **vorläufige technische Vorschläge**, kein beschlossenes Balancing.
- Bestätigte Spielentscheidungen aus dem Briefing (9 Elemente, max. 2 + 1 Endgame-Element, dauerhafte Wesensform, Start als Mensch, serverseitige Entwicklung, Spieler und NPCs gleiche Pipeline) sind unverändert umgesetzt.

## Umgebung

Python 3.13, kein pytest; Tests mit `unittest`. Keine externen Abhängigkeiten.

## Historie

1. `d64029e` Ausgangszustand: nur `README.md`, kein Code, kein Prototyp.
2. `1b07107` Zustandsbericht, Architektur, Roadmap.
3. `ba3d1b0` Event-Log, Identity/Element/Profession/Essence, 36 Tests.
4. `961f534` Production-Readiness-Doku, Windows-Checkliste, LFS-/Unreal-Ignore-Regeln.
5. `062b52c` Combat Development Engine, Regeln v2, 76 Tests.
6. `40316a5` Essence-Voraussetzung `combat_directions`, Regeln v3, 83 Tests.
7. `e608983`..`007b950` RunPod-Prüfskript, Engine-Vergleichsprotokoll (Entwurf).
7. `c6c5069` Golden Test Vectors, 96 Tests.
8. `aed6ca6` Serverseitiger Kampfkern `mmo_sim`, 128 Tests.
9. `428e9ba` Golden Vectors der Simulation, 140 Tests.
10. `4a2a156`/`d3b2ae6` Wesensbewertung (rules v4), 166 Tests.
11. `2efc9c3` Visual Evolution Engine, 199 Tests.
12. `ee32e2c` Discovery Engine (CEE + `mmo_world`), Regeln v5, Schutz vor Replay unter fremder Regelversion, 250 Tests.
13. `ad54492` Crafting Engine (CEE + Inventar/Herstellung in `mmo_world`), Regeln v6, 315 Tests.
14. `a4221dc` Economic Profile (CEE + Handelsdienst in `mmo_world`), Regeln v7, 379 Tests – damit sind alle zehn CEE-Engines als Referenz umgesetzt.
15. `fe2dfd6` Firmensimulation in `mmo_world` (ADR-0012), 477 Tests.
16. `c5337a2` Golden Vectors der Weltseite (ADR-0013), 491 Tests.
17. `21e859d` Persistenz und Migration (ADR-0014, Referenz `mmo_world.persistence`), 526 Tests.
18. `f97447d` Markt und Preisbildung (ADR-0015, `mmo_world.exchange`), 555 Tests.
19. `3be3865`/`1541175` Firmenproduktion (ADR-0016, `mmo_world.production`), 585 Tests.
20. `5c805da` Preisdynamik mit CEE-Regeln v8 (ADR-0017, `mmo_world.pricing`), 619 Tests.
21. `1ed1699` Regelversions-Migration (ADR-0018, `mmo_cee.migration`, `persistence.upgrade_world`), 643 Tests.
22. `ff62c55` Server-Protokoll: Planung (`docs/PROTOCOL.md`) und Referenz der Befehlsschicht (ADR-0019, `mmo_server`), 676 Tests.
23. `818467b` Combat Development: Fähigkeiten, Ausrüstung, Befehlsfreigabe in der Simulation (Regeln v9, ADR-0020), 698 Tests.
24. `c7495d9` Wirkung der Fähigkeiten in der Simulation (`sim_rules_v2`, ADR-0021), 723 Tests.
25. `b9f3e9b` Gruppenkampf mit Unterstützung (`mmo_sim.group`, `sim_rules_v3`, ADR-0022), 765 Tests.
26. `3fc1cdf` Direkter Zwei-Parteien-Handel (`mmo_world.direct_trade`, ADR-0023), 784 Tests.
27. `1029797` Push-Ereignisse: Postfach mit Abruf, Quittung, Stummschaltung (`mmo_world.notifications`, ADR-0024), 813 Tests.
28. `65049c1` Gruppenbildung: Gruppen, Einladungen, Anführer, Beuteverteilung (`mmo_world.party`, ADR-0025; Stufenabstand nur Platzhalter, Boosting-Regeln offen), 845 Tests.
29. `42f52fb` Kampf gegen mehrere Gegner mit Fokus und Flächenangriff (`mmo_sim.pack`, `sim_rules_v4`, ADR-0026), 887 Tests.
30. `2752a6b` Eigene Fähigkeitsbefehle: Kosten, Abklingzeit, Brand/Ausweichen/Schleier/Ausdauer (`skills`, `sim_rules_v5`, ADR-0027), 913 Tests.
31. `fb0a837`/`3c8e884` Vertical Slice, Server-Teil: Live-Kampf (`mmo_sim.live`), Spielserver mit Raum, Sammeln, Gruppenkampf und Beute (`mmo_game`), TCP-Transport, zwei-Spieler-Tests, Unity-Client-Quellen (ungeprüft), ADR-0028, 963 Tests.
32. `d7635fa` Spielstand-Speicherung des Spielservers (Generationen, Autosave, Speichern beim Beenden, Wiederaufnahme von Positionen/Gegnern/Begegnungszählern), 974 Tests.
33. `7ab9c95` Anmeldung: Konten mit PBKDF2, Sperren, Sitzungs-Token, TLS-Option, Pflicht für nicht-lokale Adressen (`mmo_game.auth`, ADR-0029), 999 Tests.
34. `a11c3da` Gelände und Kollision im Spielserver (`mmo_game.terrain`: Tempo je Gelände, Wasser/Fels, Brücke, Gleiten, Aggro nur mit freier Strecke, ADR-0030), 1027 Tests.
35. `5285019` Gegnerbewegung: Aufmerksamkeit, Verfolgung mit A*-Wegfindung über die Brücke, Kampf ab Kampfradius, Leine, Heimkehr (`mmo_game.navigation`, ADR-0031), 1076 Tests.
36. `0780ea4` Gegnerfähigkeiten, Schritt 1: Regeln `sim_rules_v6` (Fähigkeiten, Vorlagen, Phasen, Takt-Boden), reproduzierbarer Baukasten je Spawn-Punkt und Tag (`mmo_sim.enemies`, Golden Vectors `golden_enemies`, ADR-0032); Wirkung im Kampf folgt, 1116 Tests.
37. `fa26eef` Gegnerfähigkeiten, Schritte 2–5: Wirkung in der Simulation (Ankündigungen, Zustände auf Spielern, Unterbrechen, Schilde, Heilen, Verstärken, Beschwören, Phasen), Berichte mit Plausibilitätsgrenze, Spielserver (Baukasten je Spawn und Tag, `telegraph`/`enemy_event`, neue Gegner und Boss), Golden Vectors `golden_enemy_fights`, ADR-0033, 1193 Tests.
38. `5b0cba7` Balancing: deterministische Testspieler (`mmo_sim.balance`), Bericht `docs/BALANCE_REPORT.md`, `sim_rules_v7` (Lebenspunkte, Rudelwelpen, Boss-Fähigkeiten, Ankündigung normaler Angriffe), Zielbänder als Tests, ADR-0034, 1212 Tests.
39. `b3dc697` Beute auf die Schwierigkeit abgestimmt (Wertbänder gegen das Balancing), Beuteabnahme je Figur/Art/Tag, Wiedererscheinen je Gegnerart (ADR-0035), 1228 Tests.
40. (dieser Stand) Browser-Testclient: WebSocket (RFC 6455) und Spielseite direkt vom Spielserver, Herkunftsprüfung, Rauchtest mit zwei Browser-Spielern (ADR-0036).

Plan: `docs/ROADMAP.md`.
