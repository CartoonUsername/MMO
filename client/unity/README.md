# Unity-Client (Unity 6)

**Stand (AP 15):** Der Quellcode ist **noch nie in Unity gestartet** (Unity läuft auf dem Entwicklungsserver nicht). Geprüft ist alles, was ohne Unity prüfbar ist:
* `Protocol.g.cs` (Befehlskatalog) wird aus dem Server erzeugt; ein Test erzwingt Übereinstimmung.
* `NetClient.cs` (WebSocket), `Panels.cs` (Fenster, Formulare) laufen unter .NET gegen einen echten Testserver: `bash scripts/check_unity_core.sh` (braucht `dotnet`).
* Alle Skripte lassen sich gegen Nachbildungen der Unity-Schnittstellen übersetzen (`Tests~/CompileCheck`) – findet Tippfehler/Typfehler, **ersetzt keinen Test in Unity**.
Fehler, die erst in Unity auftreten (Darstellung, Eingabe, Packages), meldest du bitte; ich behebe sie.

## Einrichten
1. Unity Hub → „Add“ → „Add project from disk“ → `client/unity` wählen, Unity-6-Version nehmen. Eingebaute Render-Pipeline; das JSON-Paket holt das Projekt selbst.
2. Leere Szene öffnen, Play drücken: der Controller legt sich selbst an und zeigt die Anmeldemaske.
3. Server-Adresse: gehostet `wss://187.126.26.226.sslip.io/ws` (Standard), lokal `ws://127.0.0.1:7777/ws` (Server: `cd reference/python && python -m mmo_game.net 7777 --data ./spielstand`). Beim ersten Mal „Konto anlegen“.

## Bedienung
WASD laufen · E sammeln · Kampf: Fertigkeitsleiste unten aus dem Klassen-Kit (Tasten 1–9, Maus links = erster Eintrag, Abklingzeit sichtbar), Tab zweites Ziel, F fliehen · Dungeon-Eingang: Knopf erscheint in der Nähe.
Menüleiste unten: **Figur, Ausrüstung, Echos, Markt, Herstellen, Gruppe, Handel, Firma, Siedlung, Forschung, Gilde, Chronik**. Jedes Fenster zeigt die Serverdaten und bietet die Befehle als Formular (Felder und Typen aus dem Katalog; die handelnde Figur setzt der Client). Ereignisse (Weltboss, Marktnachrichten, Forschung, Chronik, Grundstücksverfall) erscheinen im Log links unten.

## Grenzen
Platzhaltergrafik (Primitive), keine Animation, keine Vorhersage, einfache Glättung, Oberfläche mit OnGUI und rohen Formularen – ein Test-Client für die Spielregeln, kein Endprodukt. Gebäude, Siedlungen und Kartenregionen werden noch nicht in der 3D-Welt gezeichnet.
