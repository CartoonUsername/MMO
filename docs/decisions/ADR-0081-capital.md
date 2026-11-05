# ADR-0081: Hauptstadt als Ort im Spiel (AP 95)

Status: angenommen (Vorschlag, Claude, autorisiert; Blueprint §36 ist bestätigt, das Layout ist es nicht)

## Entscheidung
- Neue Regelversion `game_rules_v20` (= v19 + Block `capital`; sonst unverändert, getestet). v19 und ältere bleiben gültig, ihnen fehlt die Hauptstadt (`game.capital` antwortet mit `not_available`).
- **Layout (Platzhalter, Zentimeter):** Kreis um (2900, 1300), Radius 550, in der Region `crossing`, verbunden mit dem Ort `hauptstadt` der Siedlungsregeln. Fünf Viertel (Marktplatz, Handwerksviertel, Gildenhalle, Rathaus, Handelskontor), drei Tore (West/Ost/Süd zeigen auf `sunmeadow`, `fangvale`, `moor`) und sechs NPC-Markierungen ohne Dialog.
- **Schutzzone** (`safe: true`): Wer im Kreis steht, wird von Gegnern nicht bemerkt; Verfolger geben auf und kehren heim. Kämpfe, die schon laufen, werden nicht abgebrochen.
- **Abfrage** `game.capital`: Layout, wo die Figur ist (`here`: Viertel oder `null` außerhalb), `safe_here`. Der Zustand (`game.state`) trägt `you.capital` ({district, safe} oder `null`), das Ereignis `capital` meldet Betreten und Verlassen.
- **Prüfung beim Start** (`TerrainError`): Ort muss in den Siedlungsregeln Hauptstadt sein und zur Region passen, Kreis liegt ganz in der Region, Viertel/Tore/NPCs liegen im Kreis, sind eindeutig und begehbar, Tore führen in eine andere bekannte Region, kein Gegner steht innerhalb.
- Der Startpunkt (500, 500) bleibt unverändert, damit der Einstieg und alle Tests gleich bleiben.
- Standardregeln des Servers sind jetzt v20. Vier Testdateien, die die offene Landschaft voraussetzen (Gegner-KI, Kampfprüfung, Kombinationen, Gegnerfähigkeiten), sind ausdrücklich auf v19 gepinnt.

## Offen (nicht entschieden, nichts davon ist gebaut)
- Ortsbindung der Dienste (Markt, Herstellen, Gilde nur in der Hauptstadt?). Bisher stehen sie überall zur Verfügung; `services` nennt nur die gedachte Zuordnung.
- Startpunkt und Wiederbelebung in der Hauptstadt (Einstiegsfluss der Anfänger ändert sich dadurch).
- Dialoge und Dienste der NPCs, Tor-Reise, Darstellung (Gebäude, Straßen) im Browser und in Unity, Größe und Form (Kreis ist ein Platzhalter).
- Ob die Schutzzone auch PvP einschließt (PvP gibt es noch nicht).
