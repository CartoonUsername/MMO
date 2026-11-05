# ADR-0074: Erstes Meisterstück je Rezept in der Weltchronik (AP 46/47)

Status: angenommen (Vorschlag, Claude, autorisiert; Platzhalterwerte)

## Entscheidung
- Neue Chronikart `masterpiece_first` in `community_rules_v3.json` (Standard; v2 bleibt): Titel „Erstes Meisterstück: <Rezept>“, 15 Ruhmpunkte, `first_only`: Nur wer ein Rezept als Erste(r) in der höchsten Güte herstellt, kommt in die Chronik.
- `CraftingService.masterpiece`-Haken (Welt verdrahtet ihn auf die Chronik), ausgelöst bei Spitzengüte. Rezeptname = Rezept-ID mit Leerzeichen. Ältere Gemeinschaftsregeln ohne die Art: Haken tut nichts, Herstellung unberührt.
- Browser-Chronik zeigt „fertigte als Erste ein Meisterstück: …“ (AP 47).
- Kein Gildenpunkte-/Rundruf-Pfad (der liegt in der Spielschicht und wird für Herstellungen nicht durchlaufen).

## Offen
- Seit AP 55 durch einen echten Herstellungsweg getestet (Schmiedekunst Stufe 10, Eisenbarren aus ausgewähltem Erz = Meisterwerk).
- Schöne Rezeptnamen, serverweiter Hinweis.
