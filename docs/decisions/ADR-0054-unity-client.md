# ADR-0054: Unity-Client auf Stand des Browser-Clients (AP 15)

Status: angenommen. Engine: **Unity 6** (Nutzer-Bestätigung am 04.11.2026; der Blueprint nennt Unreal nur als Vorschlag, Frage 23 – damit entschieden, der Blueprint-Hinweis bleibt als Hintergrund).

## Entscheidung
- **Transport:** WebSocket (`wss://…/ws`) wie der Browser; nur so erreicht der Client den gehosteten Server hinter Caddy/TLS. Der alte TCP-Weg bleibt in `NetClient` für lokale Tests.
- **Katalog erzeugt, nicht abgeschrieben:** `mmo_server/unitygen.py` erzeugt `Protocol.g.cs` aus `protocol.py`. Der Client setzt die handelnde Figur (`char`/`actor`/`teacher`) aus dem Katalog; Test erzwingt Übereinstimmung.
- **Datengetriebene Fenster** statt 12 handgeschriebener Oberflächen: `Panels.cs` ordnet je Fenster eine Abfrage und die zugehörigen Befehle zu; Anzeige und Formulare entstehen aus Serverdaten und Katalog. Neue Befehle erscheinen nach `unitygen write` ohne Clientcode. Der Server entscheidet alles.
- **Kampf:** Fertigkeitsleiste aus dem Klassen-Kit (`game.kit`), Abklingzeit zur Anzeige. Region, Dungeon-Etappe und Dungeon-Eingang im HUD; neue Ereignisse im Log.
- **Prüfbarkeit ohne Unity:** UnityEngine-freie Teile laufen unter .NET gegen einen echten Testserver (`scripts/check_unity_core.sh`, optional im Python-Test mit `MMO_TEST_UNITY=1`); alle Skripte werden gegen Nachbildungen der Unity-Schnittstellen übersetzt (`Tests~/CompileCheck`). Das findet Tipp-/Typfehler, ersetzt aber keinen Test in Unity. `dotnet-sdk-10.0` wurde dafür auf dem Entwicklungsserver installiert.

## Offen
Erster echter Lauf in Unity (Fehler meldet der Nutzer), 3D-Darstellung von Gebäuden/Siedlungen/Regionen, Animationen, Vorhersage/Interpolation, Eingabe-Neuzuordnung, Karten-/Minimap, schönere Oberfläche (UI Toolkit statt OnGUI), Charakter-Aussehen aus `appearance`, Audio, Ladezustände.
