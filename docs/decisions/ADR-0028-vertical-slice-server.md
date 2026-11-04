# ADR-0028: Spielserver für den Vertical Slice

**Status:** akzeptiert als Grundlage für den ersten spielbaren Prototyp. **Alle Zahlen und Orte (`game_rules_v1.json`) sind Platzhalter.**

**Kontext:** Bisher gibt es Regelwerk und Befehlsschicht, aber keinen laufenden Spielserver und keinen Raum. Der Produktverantwortliche hat entschieden, zuerst ein spielbares Basisspiel mit Unity 6 (URP) zu bauen (`docs/VERTICAL_SLICE.md`).

**Entscheidungen**
1. **Eigene Schicht `mmo_game`** über den bestehenden Paketen; CEE, `mmo_sim`, `mmo_world`, `mmo_server` und alle Golden Vectors bleiben unverändert (die einzigen Änderungen in `mmo_sim`: `pack.run` zerlegt in `tick`, neues `live.py`, `pack_specs` im Server – Verhalten und Vektoren identisch).
2. **Server rein tickgetrieben und netzwerkfrei testbar** (`GameServer.connect/handle/tick/drain/disconnect`); der Transport (`NetServer`, asyncio, TCP mit Zeilen-JSON) ist eine dünne Hülle. Zeit = Ticks (10/s); ein Tag = 6000 Ticks (Platzhalter) und löst Ablauf von Orders, Angeboten, Einladungen, Firmenhooks und Preisdynamik aus.
3. **Live-Kampf = Referenzsimulation:** `LiveEncounter` führt `mmo_sim.pack` Tick für Tick; der Server vergibt den Tick jeder Eingabe. Am Ende wird aus dem Eingabeprotokoll neu simuliert (`finish_pack`); weicht das Ergebnis vom Live-Ergebnis ab, wird es protokolliert (Test: nie). Bericht und Entwicklung entstehen nur so.
4. **Raum minimal:** 2D-Zone in Zentimetern, Richtungsbewegung (−1/0/1) mit festem Tempo, Diagonalen auf ca. 0,7 begrenzt, Weltgrenzen; Gegner stehen an Heimatpunkten, Annäherung (Aggro-Radius) startet den Kampf gegen das Rudel in der Nähe (bis `max_opponents`); Gruppenmitglieder in Reichweite kämpfen mit; Gegner und Teilnehmer sind während des Kampfes gebunden. Gefallene Gegner erscheinen nach `respawn_ticks` wieder.
5. **Ausgänge:** Sieg → Bericht, Beute (Münzen gleichmäßig an Teilnehmer mit Beitrag, Gegenstände nach Gruppenmodus); Niederlage → Startpunkt; Flucht/Verbindungsabbruch → Austritt mit Schonfrist.
6. **Vertrauensgrenze:** Client sendet nur Richtungen, Sammelabsichten und Kampfbefehle; Figur muss zur Sitzung gehören; Befehlsbudget; Nachrichtengröße begrenzt; Kampfbefehle werden gegen die Befehlsmenge der Regeln und das Fähigkeitsfreigabesystem geprüft.
7. **Anmeldung (nur Entwicklung):** Kontoname = Figur; keine Passwörter, Standardbindung 127.0.0.1. Echte Anmeldung/TLS sind offen und vor jedem Mehrspieler-Test außerhalb des lokalen Netzes zu ergänzen.

**Absicherung:** `tests/test_live.py`, `tests/test_game.py` (Bewegung, Sammeln, Herstellen, Handel, Solo- und Gruppenkampf, Abbruch, Tageswechsel, zwei TCP-Clients), Mutationstests (siehe Statusbericht).

**Offen / Grenzen**
- Keine Persistenz des Spielstands beim Neustart, keine Kollision/Hindernisse/Höhen, keine Interpolation/Vorhersage im Client, kein Chat, Markt ortsunabhängig, eine Zone.
- Gegner-KI ist nur „stehen und kämpfen"; Tempo/Aggro sind ungetestete Platzhalter.
