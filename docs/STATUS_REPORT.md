# Technischer Zustandsbericht

Stand: 2026-11-03 · Arbeitsbranch `claude/awesome-dirac-9k6p3n` · `main` unverändert (nur `README.md` mit `# MMO`)

> Korrektur: Frühere Fassungen dieses Berichts beschrieben zuerst den Ausgangszustand („kein Code“) und hängten den Stand nach der Implementierung an. Dieser Bericht beschreibt ausschließlich den **aktuellen** Zustand des Arbeitsbranches. Der Ausgangszustand steht nur noch im Abschnitt „Historie“.

## Aktueller Zustand (verifiziert durch Testlauf)

| Bereich | Stand |
|---|---|
| Referenzimplementierung | `reference/python/mmo_cee/` – **vorhanden**, nur Standardbibliothek |
| Implementierte Engines | Identity, Element, Profession, Essence, **Combat Development** + Character History (Event-Log, Hash-Kette, Replay) |
| Regeln | `rules_v1.json` (unverändert, ohne Kampf), `rules_v2.json` (v1 + `combat`); Standard ist v2 |
| Tests | **76** `unittest`-Tests, alle grün (`cd reference/python && python -m unittest discover -s . -t . -v`) |
| Dokumentation | `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, ADR-0001 bis ADR-0004, `Game/PRODUCTION_READINESS.md`, `Game/WINDOWS_SETUP_CHECKLIST.md` |
| Unreal-Projekt | nicht vorhanden (bewusst; erst nach Windows-Checkliste und Freigabe) |

## Noch nicht implementiert

Konkrete Kampffähigkeiten (nur Entwicklungsrichtungen und Stufen), Discovery, Crafting, Economic Profile, Visual Evolution (nur Schnittstellen in `interfaces.py`), Persistenz/Snapshots, Server-Protokoll.

## Nicht bestätigte Inhalte (Vorschläge)

- Wesensformen in `rules_v1.json`/`rules_v2.json` (`ember_kin`, …) sind Platzhalter zur Mechanikprüfung.
- Kampfdimensionen (Kraft, Präzision, Mobilität, Kontrolle, Verteidigung, Unterstützung), Aktionstypen, Entwicklungsrichtungen (`vanguard`, `duelist`, …), alle Gewichte, Schwellen, Tageslimits und Raten in `rules_v2.json` sind **vorläufige technische Vorschläge**, kein beschlossenes Balancing.
- Bestätigte Spielentscheidungen aus dem Briefing (9 Elemente, max. 2 + 1 Endgame-Element, dauerhafte Wesensform, Start als Mensch, serverseitige Entwicklung, Spieler und NPCs gleiche Pipeline) sind unverändert umgesetzt.

## Umgebung

Python 3.13, kein pytest; Tests mit `unittest`. Keine externen Abhängigkeiten.

## Historie

1. `d64029e` Ausgangszustand: nur `README.md`, kein Code, kein Prototyp.
2. `1b07107` Zustandsbericht, Architektur, Roadmap.
3. `ba3d1b0` Event-Log, Identity/Element/Profession/Essence, 36 Tests.
4. `961f534` Production-Readiness-Doku, Windows-Checkliste, LFS-/Unreal-Ignore-Regeln.
5. (dieser Stand) Combat Development Engine, Regeln v2, 76 Tests.

Plan: `docs/ROADMAP.md`.
