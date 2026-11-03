# MMO

3D-Action-MMORPG (Unreal Engine, Windows-PC). Alleinstellungsmerkmal: die **Character Evolution Engine** (CEE), die Spieler und NPCs ausschließlich anhand ihrer Spielhistorie individuell entwickelt.

## Stand

- `docs/STATUS_REPORT.md` – verifizierter Ist-Zustand
- `docs/ARCHITECTURE.md` – Architektur der zehn CEE-Engines
- `docs/ROADMAP.md` – priorisierter Plan
- `docs/decisions/` – Architekturentscheidungen (ADRs)
- `reference/python/` – Referenzimplementierung (nur Standardbibliothek)

## Tests ausführen

```bash
cd reference/python && python3 -m unittest discover -s . -t . -v
```
