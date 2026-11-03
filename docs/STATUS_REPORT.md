# Technischer Zustandsbericht

Stand: 2026-11-03 · Arbeitsbranch `claude/awesome-dirac-9k6p3n` · `main` unverändert (nur `README.md` mit `# MMO`)

> Korrektur: Frühere Fassungen dieses Berichts beschrieben zuerst den Ausgangszustand („kein Code“) und hängten den Stand nach der Implementierung an. Dieser Bericht beschreibt ausschließlich den **aktuellen** Zustand des Arbeitsbranches. Der Ausgangszustand steht nur noch im Abschnitt „Historie“.

## Aktueller Zustand (verifiziert durch Testlauf)

| Bereich | Stand |
|---|---|
| Referenzimplementierung | `reference/python/mmo_cee/` – **vorhanden**, nur Standardbibliothek |
| Implementierte Engines | Identity, Element, Profession, Essence, Combat Development, Visual Evolution, **Discovery** + Character History (Event-Log, Hash-Kette, Replay) |
| Regeln | `rules_v1.json` (ohne Kampf), `rules_v2.json` (v1 + `combat`), `rules_v3.json` (v2 + Wesensform mit Kampfrichtungs-Voraussetzung), `rules_v4.json` (v3 + Wesensbewertung mit Entscheidungen, ADR-0007), `rules_v5.json` (v4 + Entdeckungen, geheime Wesensform, ADR-0009); v1–v4 unverändert, Standard ist v5 |
| Tests | **250** `unittest`-Tests, alle grün (`cd reference/python && python -m unittest discover -s . -t . -v`) |
| Weltzustand | `reference/python/mmo_world/` – `DiscoveryRegistry` (Pionier, Lehrfenster), `DiscoveryService` (transaktional mit der CEE) |
| Kampfsimulation | `reference/python/mmo_sim/` – deterministischer 1:1-Kampfkern, `EncounterServer` (ADR-0006), `sim_rules_v1.json` (vorläufige Werte) |
| Golden Test Vectors | `reference/golden/` (CEE, 14 Szenarien, `mmo_cee.golden`) `reference/golden_sim/` (Simulation, 61 Fälle, `mmo_sim.golden`) und `reference/golden_visual/` (Visual Evolution, 21 Fälle, `mmo_cee.golden_visual`); Format: `reference/golden/README.md` |
| Dokumentation | `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, ADR-0001 bis ADR-0009, `Game/PRODUCTION_READINESS.md`, `Game/WINDOWS_SETUP_CHECKLIST.md` |
| Unreal-Projekt | nicht vorhanden (bewusst; erst nach Windows-Checkliste und Freigabe) |

## Noch nicht implementiert

Konkrete Kampffähigkeiten (nur Entwicklungsrichtungen und Stufen), Gruppen-/Raumkampf und Unterstützungsaktionen in der Simulation, Crafting, Economic Profile (nur Schnittstellen in `interfaces.py`), Wirkung der Entdeckungen auf Crafting/Wirtschaft/Städte, Registry-Persistenz, echte Optik/Assets zur Visual Evolution (nur Parametermechanik), Persistenz/Snapshots, Server-Protokoll, C++-Portierung (Vektoren liegen bereit).

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
12. (dieser Stand) Discovery Engine (CEE + `mmo_world`), Regeln v5, Schutz vor Replay unter fremder Regelversion, 250 Tests.

Plan: `docs/ROADMAP.md`.
