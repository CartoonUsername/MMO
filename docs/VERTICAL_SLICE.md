# Vertical Slice: das erste spielbare Basisspiel

**Ziel:** Ein zusammenhängender, wirklich spielbarer Prototyp mit zwei gleichzeitig verbundenen Spielern in einer kleinen 3D-Welt: Bewegung, Kampf, Charakterentwicklung und eine einfache Wirtschaft – serverautoritativ. **Entscheidung (Produktverantwortlicher):** Engine Unity 6 (URP); Umfang: Charakter + Kampf, Server + Mehrspieler, Wirtschaft, kleine Spielwelt. Alles Konkrete (Zahlen, Orte, Beute) sind **Platzhalter**.

## Leitplanken
- Die Python-Referenz (`reference/python`) ist **verbindliches Regel- und Testorakel**. Der Spielserver ruft sie auf und ersetzt sie nicht: Kampf = `mmo_sim.pack` (live, Tick für Tick), Entwicklung/Herstellung/Handel/Gruppen = CEE und `mmo_world`.
- Der Client sendet nur Absichten. Position, Gegner, Kampf, Beute, Zeit und Inventar entstehen im Server.
- Bestehende CEE, Simulationen und Golden Vectors werden nicht verändert (alle bleiben byteidentisch; die Tests laufen mit).
- Keine kostenpflichtigen Dienste. Server läuft lokal (Python-Standardbibliothek), Unity-Personal ist kostenlos.

## Bausteine und Stand
| # | Baustein | Stand |
|---|---|---|
| 1 | Live-Kampf (`mmo_sim.live`): Eingaben während des Kampfes, Server vergibt den Tick, Ergebnis = Neuberechnung aus dem Eingabeprotokoll | **fertig** |
| 2 | Spielserver ohne Netzwerk (`mmo_game.game`): Raum 60 × 60 m, Bewegung mit Tempolimit, Gegner mit Aggro und Wiedererscheinen, Sammelpunkte, Kampf mit Gruppe und Beute, Tageswechsel | **fertig** |
| 3 | Transport (`mmo_game.net`): TCP mit zeilenweisem JSON, Anmeldung per Konto-Name (nur Entwicklung), Live-Ereignisse, Testclient (`mmo_game.client`) | **fertig** |
| 4 | Unity-Client (`client/unity`): Verbindung, Bewegung/Kamera, Kampfeingaben + Anzeige, Inventar/Herstellung/Handel-Oberfläche | **Quellcode vorhanden, nicht in Unity geprüft** (Unity läuft in dieser Umgebung nicht) |
| 5 | Persistenz: Welt (CEE, Inventar, Märkte, Gruppen) als Generationen im `Store`, Spielzustand (Tick, Gegner, Sammelpunkte, Positionen) daneben; Autosave und Speichern beim Beenden | **fertig** |
| 6 | Anmeldung: Konten mit PBKDF2-Hash, Sperren, Sitzungs-Token, TLS-Option | **fertig** (ADR-0029); offen: E-Mail/Passwort-Zurücksetzen, Kontoverwaltung |

## Spielablauf (End-to-End)
1. Beide Spieler verbinden sich (`hello`), treten bei (`game.join`) und erscheinen am Startpunkt.
2. Sie laufen (`game.move`), sammeln Erz/Kräuter/Wasser (`game.gather`), stellen mit `craft` Barren/Salbe her.
3. Sie handeln untereinander (`trade.offer`/`trade.accept`) oder über das Orderbuch (`market.*`).
4. Sie bilden eine Gruppe (`party.*`) und laufen zu den Wölfen; Annäherung löst den Kampf aus (Rudel bis 3 Gegner, Gruppenmitglieder in Reichweite kämpfen mit).
5. Im Kampf senden sie Befehle (`game.fight`: `light`, `heavy`, `dodge`, `block`, `stun`, `slow`, `sweep`, `target_n`, `heal`, `shield`, Fähigkeiten, `flee`); der Server schickt den Live-Zustand.
6. Sieg: Bericht an die CEE (Entwicklung), Beute (Münzen, Kräuter) nach Gruppenregeln. Niederlage: zurück zum Startpunkt. Flucht: kurze Schonfrist.

## Bedienung (Entwicklung)
```bash
cd reference/python
python -m mmo_game.net 7777 --data ./spielstand   # Spielserver mit Konten und Speicherung auf 127.0.0.1:7777 (Beenden mit Strg+C/SIGTERM speichert)
python -m mmo_game.net 7777 --insecure-dev        # ohne Konten, nur zum Testen auf dem eigenen Rechner
# außerhalb des eigenen Rechners (Konten + TLS sind Pflicht):
python -m mmo_game.net 7777 --host 0.0.0.0 --data ./spielstand --cert cert.pem --key key.pem
python -m unittest tests.test_game  # Ende-zu-Ende-Tests inkl. zwei TCP-Clients
```
Protokoll: `docs/PROTOCOL.md` (Weltbefehle) und `docs/VERTICAL_SLICE_PROTOCOL.md` (Spielschicht).
