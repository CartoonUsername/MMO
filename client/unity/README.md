# Unity-Client (Vertical Slice)

**Stand:** Quellcode vorhanden, **in dieser Entwicklungsumgebung nicht kompiliert oder in Unity getestet** (Unity läuft hier nicht). Der Server und das Protokoll sind getestet (`reference/python/tests/test_game.py`, inkl. zwei TCP-Clients); der Client hält sich an `docs/VERTICAL_SLICE_PROTOCOL.md`.

## Einrichten (Unity 6, kostenlos in der Personal-Lizenz)
1. Unity Hub → „Add“ → „Add project from disk“ → diesen Ordner (`client/unity`) wählen; bei Versionsabfrage die installierte Unity-6-Version nehmen (Hub bietet es an). Das Projekt nutzt die eingebaute Render-Pipeline (kein URP nötig) und holt das JSON-Paket selbst.
2. Beliebige (auch leere) Szene öffnen und Play drücken: der Controller legt sich selbst an und zeigt eine Anmeldemaske (Adresse, Port, Konto, Passwort; „Konto anlegen“ beim ersten Mal).
3. Server: lokal `cd reference/python && python -m mmo_game.net 7777 --data ./spielstand` (Adresse `127.0.0.1`), oder die Adresse eines gehosteten Servers eintragen (öffentliche Server verlangen TLS, siehe `docs/VERTICAL_SLICE.md`).

## Steuerung
WASD laufen · E sammeln · im Kampf: Linksklick leicht, Rechtsklick schwer, Leertaste ausweichen, Q blocken, 1 betäuben, 2 verlangsamen, 3 Rundumschlag, 4 heilen, 5 Schild, Tab zweites Ziel, F fliehen, R/C/V Fähigkeiten (nur mit Ausrüstung). Seitenleiste: Gruppe, Herstellen, Handel.

## Grenzen
Platzhaltergrafik (Primitive), keine Animation, keine Vorhersage, einfache Glättung, Oberfläche mit OnGUI. Das ist ein Test-Client für die Spielregeln, kein Endprodukt.
