# ADR-0004: Ganzzahl-Arithmetik und Regelversionierung

**Status:** akzeptiert

1. **Keine Gleitkommazahlen** in Regeln und Berechnungen. Faktoren in Promille (1000 = 1,0), Division nur als Ganzzahldivision (abrunden), Multiplikationsreihenfolge fest. Grund: Bit-identisches Ergebnis in Python und der späteren C++-Portierung (Golden Vectors).
2. **Regelversionen sind unveränderlich.** Jede inhaltliche Änderung oder Erweiterung erzeugt eine neue Datei (`rules_vN.json`) mit neuer `version`. Bestehende Versionen werden nicht editiert. Jedes Ereignis speichert die `rules_version`, unter der es aufgezeichnet wurde.
3. **Standardregeln** (`load_rules()`) zeigen auf die neueste Version; ältere bleiben ladbar und getestet.
4. **Engines sind optional je Regelversion:** `default_projector` hängt die Combat Engine nur ein, wenn die Regeln einen `combat`-Abschnitt enthalten.
5. Offen: Migration bestehender Logs zwischen Regelversionen (Neuberechnung unter neuer Version vs. Einfrieren) – Roadmap 9.
