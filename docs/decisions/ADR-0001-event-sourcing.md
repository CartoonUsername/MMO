# ADR-0001: Event Sourcing mit Hash-Kette für die Charakterhistorie

**Status:** akzeptiert (technische Entscheidung, ändert keine Spielentscheidung)

**Kontext:** Millionen individueller Profile müssen nachvollziehbar, versionierbar und bei Regeländerungen neu berechenbar sein.

**Entscheidung:** Append-only Ereignisse pro Charakter, Zustand nur per Replay; Hash-Kette je Charakter; Regeln in versionierten Dateien.

**Folgen:** Regelwechsel (neue `rules_version`) erlauben Neuberechnung; Cheat-/Audit-Analyse möglich; höherer Speicherbedarf (später Snapshots, siehe Roadmap).

**Verworfen:** Direktes Mutieren von Charakterfeldern in einer Datenbank (nicht auditierbar, nicht reproduzierbar).
