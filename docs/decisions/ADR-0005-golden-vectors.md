# ADR-0005: Golden Test Vectors als Vertrag zwischen Referenz und Portierung

**Status:** akzeptiert (technisch)

**Kontext:** Regeln dürfen nicht doppelt und abweichend implementiert werden (Handover Teil 12). Die produktive Engine wird später in einer anderen Sprache gebaut.

**Entscheidung**
1. Szenarien werden als JSON-Vektoren in `reference/golden/` committet und aus Python erzeugt (`mmo_cee.golden`).
2. Ein Vektor enthält Schritte mit erwarteter Reaktion (akzeptiert mit Ereignis-Hash / abgelehnt mit unverändertem Zustand), Zustands-Hash je Schritt, Endzustand und abgeleitete Sichten.
3. Die Regeldatei ist die gemeinsame Quelle und wird per SHA-256 gebunden; geänderte Regeldateien werden dadurch erkannt (Regelversionen sind unveränderlich, ADR-0004).
4. Python-Tests erzwingen: Vektoren = Regeneration (byte-gleich), Replay ohne Abweichung, Manipulationen werden erkannt, jeder Ereignistyp hat akzeptierte und abgelehnte Beispiele, Zustände sind ganzzahlig.
5. Fehlermeldungstexte sind nicht Teil des Vertrags (sprachabhängig).

**Folgen:** Jede Verhaltensänderung der Referenz erzwingt bewusstes Neu-Erzeugen und eine Regelversion. Ein Port gilt als korrekt, wenn alle Vektoren bit-identisch bestehen.

**Grenzen:** Die Vektoren beweisen Übereinstimmung nur für die abgedeckten Szenarien; neue Mechaniken brauchen neue Szenarien. Kanonisches JSON wurde nur mit ASCII geprüft.
