# CLAUDE.md – Arbeitsregeln für dieses Repository

Vor jeder größeren Änderung lesen: `MMORPG_MASTER_BLUEPRINT.md` (identisch mit `docs/MASTER_BLUEPRINT.md` und `VISION_2026-11-03.md` auf `main`), `docs/IMPLEMENTATION_STATUS.md`, `docs/DECISIONS_AND_OPEN_QUESTIONS.md`, `docs/BUILD_PLAN.md`.

## Arbeitsweise (Blueprint §78/§79)
1. Bestätigt, Vorschlag und offen unterscheiden. Nichts als implementiert melden, was nur Spezifikation ist.
2. Kleine Schritte, Tests zusammen mit der Umsetzung, Tests wirklich ausführen und das echte Ergebnis berichten.
3. Neue Regelwirkung = neue Regelversion; alte Golden Vectors bleiben gültig.
4. Jede Entscheidung bekommt einen ADR in `docs/decisions/`; `IMPLEMENTATION_STATUS.md`, `BUILD_PLAN.md` und `CHANGELOG.md` mitpflegen.
5. Keine Geheimnisse committen. Keine unnötigen Abhängigkeiten. Keine Inhalte aus dem Blueprint still löschen.
6. Verboten: Pay-to-win, Echtgeld-Upgrade-Lotterie, unendliche passive Geldquellen, frei generierte Skills/Wesensformen ohne Designerregeln. Stadtpolitik bleibt zurückgestellt.

## Entscheidungsbefugnis
Der Projektinhaber (Ideengeber) hat am 2026-11-05 erlaubt, offene Designfragen (§57) ohne Rückfrage zu entscheiden. Solche Entscheidungen gelten als **Vorschlag (Claude, autorisiert)**: konfigurierbar bauen, im Dokument kennzeichnen, jederzeit änderbar.

## Tests
`cd reference/python && python3 -m unittest discover -s . -t .`
