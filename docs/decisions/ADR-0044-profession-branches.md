# ADR-0044: Berufszweige und Meisterstücke (AP 5)

Status: angenommen (Platzhalterwerte)

## Entscheidung
- Neue reine Ableitung `mmo_cee/branches.py` mit Daten `profession_rules_v1.json`: je Beruf Spezialisierungszweige (z. B. Schmied: Erzveredelung, Schwere Waffen & Hitze, Schattenlegierungen; Alchemist: Heilmittel, Glas & Frost, Schattenrezepturen).
- Zweigpunkte = Rezepteinsätze × Stufe × 100 + Technikeinsätze × 300 + Elementinfusion / 10; Stufen bei 1000 / 4000 / 12000. Quelle sind ausschließlich serverbestätigte Herstellungsberichte (`crafting.crafted`), also Material verbrauchende, tageslimitierte Tätigkeiten (kein Spammen, §71).
- Meisterstück = Rezept mindestens einmal in höchster Güte hergestellt; zusätzlich Liste offener Meisterstückziele je Beruf.
- Keine neue CEE-Regelversion, keine neuen Ereignisse, keine Migration; `query.character` liefert `profession_detail`, das Charakterfenster zeigt Zweige und Meisterstücke.

## Bewusst nicht entschieden
Zweige sind nicht exklusiv, es gibt keine Respezialisierung/Wechsel (Blueprint-Frage 10), keine finale Berufsliste (Frage 11). Offen: Experimentieren/neue Herstellungsverfahren (§16), Berufsanforderungen für Fähigkeiten, nur 4 Berufe mit Zweigen.
