# ADR-0036: Browser-Testclient über WebSocket

**Status:** angenommen (Testwerkzeug; die Engine-Entscheidung Unity bleibt unberührt)

## Kontext
Das Basisspiel soll zuerst im Spiel getestet werden, bevor weiter ausgebaut wird. Unity lässt sich in dieser Umgebung weder bauen noch starten, und nicht jeder Testrechner kann es ausführen. Der Spielserver soll deshalb ohne Zusatzinstallation von einem Browser aus spielbar sein.

## Entscheidung
- Der Spielserver (`mmo_game.net`) erkennt an der ersten Zeile, ob ein HTTP-Browser (`GET `) oder ein Zeilen-JSON-Client verbindet; beide Wege nutzen dieselbe Anmeldung, dieselben Befehle und dieselben Ereignisse (kleine Verbindungsschicht `LineConn`/`WsConn`).
- HTTP liefert genau eine Seite (`/`, `mmo_game/web/index.html`, ohne externe Abhängigkeiten, mit Content-Security-Policy, `no-store`), `/health` und sonst 404; es werden keine Dateien aus dem Dateisystem nach Pfad geliefert.
- `/ws` wechselt zu WebSocket (RFC 6455, nur Standardbibliothek in `mmo_game/ws.py`): Text-Nachrichten, Fragmente, Ping/Pong, Schließen; Client-Rahmen müssen maskiert sein; Nachrichten höchstens so groß wie eine Zeile (4096 Bytes), sonst Schließen mit 1009; Binärdaten 1003; ungültiges UTF-8 1007; Header höchstens 8 KiB/40 Zeilen.
- Schutz vor fremden Webseiten: trägt die Anfrage einen `Origin`, muss er zum `Host` passen, sonst 403. Anmeldung, Verdrängung, Verbindungsgrenzen, Pflicht von Konten und TLS außerhalb von 127.0.0.1 gelten unverändert.
- Der Client enthält keine Spiellogik: er zeigt nur Server-Zustand und sendet Absichten (Bewegen, Sammeln, Kampfbefehle, Verkaufen).

## Folgen
- Test im echten Browser (Playwright/Chromium) als Rauchtest; ohne Node/Playwright wird er übersprungen.
- Der Unity-Client bleibt das Ziel für die spätere Darstellung; der Browserclient ist Testwerkzeug und Referenz für das Protokoll.
- Nachtrag: Die Seite hat einklappbare Fenster **Gruppe** (gründen, einladen, annehmen/ablehnen, verlassen, auflösen, kicken, Anführer), **Handel** (Angebote senden, eingehende annehmen/ablehnen, ausgehende zurückziehen; Preis gilt für die ganze Menge) und **Herstellen** (feste Rezeptliste als Platzhalter, Güte, Menge). Sie senden nur vorhandene Befehle und zeigen Serverantworten; Fehler erscheinen als Text unter dem Fenster. Getestet auf Protokollebene (`test_fenster_gruppe_handel_herstellen_befehle`) und per Syntax-/Befehlsprüfung der Seite, **nicht** im echten Browser (Playwright fehlt auf dem VPS).
- Nachtrag 2: **Klick-Bewegung**: Boden anklicken läuft dorthin, Sammelpunkt anklicken läuft hin und sammelt, Gegner anklicken läuft hin (der Kampf startet wie bisher durch Nähe), WASD bricht ab. Der Client rechnet dafür einen Weg (A* auf einem 60-cm-Raster aus `game.map`) und sendet weiterhin nur `game.move`-Richtungen; Tempo, Hindernisse und Reichweiten prüft der Server. Im echten Browser (Chromium, lokale Serverkopie) geprüft: Boden, Sammelpunkt, Weg über die Brücke bis zum Kampf.
- Offene Punkte: Seite ist nur eine Testoberfläche; Verschlüsselung bei Fernzugriff bleibt TLS-Pflicht des Servers.
