# ADR-0031: Gegnerbewegung und Wegfindung

**Status:** akzeptiert als Grundlage für den Vertical Slice. **Radien, Tempi und Fristen sind Platzhalter.**

**Kontext:** Gegner standen an ihrem Platz, der Kampf begann beim bloßen Näherkommen. Ein spielbarer Prototyp braucht Verfolgung, Rückkehr und Wege um Hindernisse (Fluss/Brücke), ohne dass Spieler die Gegner ausnutzen können.

**Entscheidungen**
1. **Zustände je Gegner:** `idle` (zu Hause), `chase` (verfolgt eine Figur), `return` (geht heim), `fight` (gebunden). Gegner im Zustand `return` bemerken niemanden, bis sie zu Hause sind (verhindert Ausnutzen durch Hin-und-Her-Laufen).
2. **Aufmerksamkeit:** Ein ruhender Gegner bemerkt eine Figur im Alarmradius (`aggro_radius`) bei freier Strecke (`clear_line`); sein Rudel (Gegner innerhalb `pack_radius`) schließt sich an. Figuren im Kampf oder mit Schonfrist werden nicht bemerkt.
3. **Kampfbeginn:** erst, wenn der Verfolger den Kampfradius (`engage_radius`) bei freier Strecke erreicht; das Rudel sind dann alle ruhenden/verfolgenden Gegner innerhalb `pack_radius`, höchstens `max_opponents`.
4. **Aufgeben:** Ziel getrennt, im Kampf oder geschützt, oder Gegner weiter als `leash_radius` von zu Hause, oder kein Weg → `return`. Nach einem Kampf ohne Sieg (Flucht, Niederlage) gehen die Gegner heim; nach einem Sieg erscheinen sie nach `respawn_ticks` zu Hause (Zustand zurückgesetzt).
5. **Wegfindung (`mmo_game/navigation.py`):** A* auf einem 100-cm-Raster, ganzzahlige Kosten (gerade 10, diagonal 14, geteilt durch das Geländetempo), keine Eckenschneider, feste Reihenfolge der Nachbarn (deterministisch), Begrenzung der Knotenzahl. Ein blockiertes Ziel (Spieler im Wasser) führt zur nächsten begehbaren Zelle. Wege werden alle `repath_ticks` oder bei Hängenbleiben neu berechnet und über freie Strecken geglättet.
6. **Bewegung:** gerade Schritte zum Wegpunkt mit Tempo je Gegnerart (Wolf 40, Bär 28, sonst 30 cm/Tick) mal Geländefaktor, ganzzahlig; Kollision und Gleiten wie bei Spielern (`Terrain.move_toward`).
7. **Persistenz:** Gegnerzustand und Positionen werden nicht gespeichert (Neustart = alle zu Hause); Lebend-/Tot-Zustand und Wiedererscheinen bleiben.
8. **Protokoll:** Gegnereinträge in `state` tragen `state` (idle/chase/return/fight).

**Absicherung:** `tests/test_enemy_ai.py` (Raster/Kosten, Pfade über die Brücke, Straße vor Matsch, keine Eckenschneider, Knotenlimit; Verfolgung mit Tempo je Art und Gelände, Kampfradius, Rudel, Leine mit Grenzwerten, Heimkehr, Flucht/Niederlage/Sieg, Zielverlust, Schonfrist, kein Weg, Hängenbleiben, Wiederholbarkeit, Persistenz); Mutationstests (siehe Statusbericht); ein Optimalitätstest vergleicht A*-Wege auf Zufallskarten mit einem unabhängigen Dijkstra und deckte eine zu große Heuristik (Rundung) auf, die behoben wurde (Kosten jetzt ohne Rundung in 1/20).

**Offen / Grenzen**
- Keine Kollision zwischen Gegnern/Spielern (Gegner können übereinander stehen), keine Formation, kein Umherstreifen im Ruhezustand, keine Fähigkeiten der Gegner (Heiler, Bosse), keine Bewegung im Kampf (der Kampf ist positionslos).
- 8-Richtungs-Raster mit geradem Folgen der Wegpunkte; keine echte Navmesh, keine Höhen.
- Die Last der Wegfindung ist nicht gemessen (kleine Karte, wenige Gegner).
