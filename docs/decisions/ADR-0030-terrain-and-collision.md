# ADR-0030: Gelände und Kollision

**Status:** akzeptiert als Grundlage für den Vertical Slice. **Karte, Tempofaktoren und Radien sind Platzhalter.** Kein Navigationsnetz, keine Höhen.

**Kontext:** Die Zone war eine leere Fläche; Spieler liefen durch alles und Gegner griffen durch Hindernisse. Ein spielbarer Prototyp braucht begehbares und nicht begehbares Gelände, serverseitig entschieden (Vertrauensgrenze).

**Entscheidungen**
1. **Modul `mmo_game/terrain.py`**, ganzzahlig und deterministisch, Regeln im Abschnitt `terrain` von `game_rules_v1.json`: Geländearten mit Tempofaktor in Promille (0 = nicht begehbar: Wasser, Fels), Grundart, Rechtecke (spätere überdecken frühere, so entsteht eine Brücke über dem Fluss) und Kreishindernisse.
2. **Figur = Kreis** mit `player_radius` (40 cm). Begehbarkeit prüft Mittelpunkt und acht Randpunkte sowie den Zonenrand; Hindernisse als Kreisabstand.
3. **Bewegung:** Tempo des Geländes unter der Figur (Straße 130 %, Gras 100 %, Matsch 60 %); Diagonale ca. 0,7; bei Kollision Gleiten entlang einer Achse, sonst Stehenbleiben. Beim Laden wird geprüft, dass blockierende Gebiete und Hindernisse dicker sind als der längste Schritt (kein Durchtunneln).
4. **Spielregeln:** Startpunkt, Gegner und Sammelpunkte müssen auf begehbarem Boden liegen (sonst startet der Server nicht). Gegner greifen nur bei freier Strecke an (`clear_line`, Prüfpunkte alle 50 cm), also nicht über den Fluss. Fluchtpunkt und gespeicherte Positionen werden bei Bedarf zum nächsten begehbaren Punkt verschoben (`nearest_walkable`, feste Reihenfolge).
5. **Protokoll:** `game.map` liefert die statische Karte zur Darstellung; `state` meldet `you.ground`. Der Client entscheidet nichts über Begehbarkeit.

**Absicherung:** `tests/test_terrain.py` (Regeln inkl. Grenzwerte, Abfragen, Gleiten, kein Durchtunneln, Zufallslauf über die ganze Karte, Brücke, Aggro über den Fluss, Fluchtpunkt, Kartenänderung); Mutationstests (siehe Statusbericht).

**Offen / Grenzen**
- Keine Wegfindung für Gegner (sie stehen), keine Höhen/Hänge, keine bewegten Hindernisse, keine Kollision zwischen Spielern oder mit Gegnern, Sammeln ohne Sichtlinienprüfung.
- Die Karte ist ein kleines Beispiel (Fluss, See, Felsen, Matsch); ein Karteneditor oder Import aus Unity fehlt.
- Die Client-Darstellung der Karte ist im Unity-Code vorhanden, aber ungeprüft.
