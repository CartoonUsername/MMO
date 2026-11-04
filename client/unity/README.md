# Unity-Client (Vertical Slice)

**Stand:** Quellcode vorhanden, **in dieser Entwicklungsumgebung nicht kompiliert oder in Unity getestet** (Unity läuft hier nicht). Der Server und das Protokoll sind getestet (`reference/python/tests/test_game.py`, inkl. zwei TCP-Clients); der Client hält sich an `docs/VERTICAL_SLICE_PROTOCOL.md`.

## Einrichten (Unity 6, 3D (URP), kostenlos in der Personal-Lizenz)
1. Neues Projekt „3D (URP)“ anlegen.
2. Package Manager → „Add package by name“ → `com.unity.nuget.newtonsoft-json` (für JSON).
3. Den Ordner `Assets/Scripts` aus diesem Verzeichnis in das Projekt kopieren.
4. Leere Szene öffnen, ein leeres GameObject anlegen, `GameController` anhängen, dort `account` setzen (z. B. `spieler1` bzw. `spieler2` im zweiten Editor/Build).
5. Server starten: `cd reference/python && python -m mmo_game.net 7777`, dann in Unity Play drücken.

## Steuerung
WASD laufen · E sammeln · im Kampf: Linksklick leicht, Rechtsklick schwer, Leertaste ausweichen, Q blocken, 1 betäuben, 2 verlangsamen, 3 Rundumschlag, 4 heilen, 5 Schild, Tab zweites Ziel, F fliehen, R/C/V Fähigkeiten (nur mit Ausrüstung). Seitenleiste: Gruppe, Herstellen, Handel.

## Grenzen
Platzhaltergrafik (Primitive), keine Animation, keine Vorhersage, einfache Glättung, Oberfläche mit OnGUI. Das ist ein Test-Client für die Spielregeln, kein Endprodukt.
