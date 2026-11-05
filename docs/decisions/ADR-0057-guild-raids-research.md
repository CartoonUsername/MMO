# ADR-0057: Gilden-Raids und Gildenforschung (AP 18)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §45, §47–49)
- **Gildenforschung** (`mmo_world/community.py`, `community_rules_v2.json`; v1 bleibt): Offiziere/Leitung starten eine Forschung, die Kosten kommen aus der **Gildenkasse** (Senke). Eine Forschung gleichzeitig, Dauer in Tagen (Fertigstellungstag wird beim nächsten Zugriff gesetzt, kein Zeitgeber). Voraussetzungen möglich. Technologien (Platzhalter): `scouting` (+1 Raid-Zutritt je Tag), `banners` (+5 Mitgliederplätze), `strongbox` (+25 % Raid-Zahlung in die Kasse, braucht `scouting`). Wirkungen bewusst klein: Einzelspieler verlieren keinen Zugang (§45/§49). Befehl `guild.research`; `query.guild` zeigt Stand und Technologien.
- **Gilden-Raid** (`game_rules_v11.json`; v10 bleibt): ein Dungeon mit `guild_raid` (`steinherz_krypta`, 3 Etappen, Steinherz-Koloss als Abschluss). Zutritt nur für Mitglieder **derselben Gilde** am Eingang (mind. 2, höchstens die Gruppengrenze der Simulation = 4), je Gilde und Tag 1 Zutritt (+ Forschung). Abschluss: persönliche Truhe wie im Dungeon plus Zahlung in die Gildenkasse; Gildenpunkte (8 je Beteiligtem), Weltchronik-Eintrag `raid_cleared` (Erstbezwinger-Titel). Ein Misserfolg zahlt nichts.
- Keine CEE-Änderung, keine Simulationsversion, keine Weltmigration. Protokollkatalog und Unity-Katalog wurden neu erzeugt.

## Nicht entschieden / offen
- **Raid-Größe:** Die Simulation kennt höchstens 4 Spieler je Kampf; „Raids" sind daher Gildentrupps. Größere Raids brauchen eine höhere Gruppengrenze (neue Simulationsregeln) oder mehrere Trupps.
- Raid-Mechaniken jenseits von Dungeon-Etappen (Phasen, Pflichtrollen), wöchentlicher statt täglicher Zutritt, Gildenchat, Gildenhäuser als Gebäude in der Welt.
- Client-Fenster für Forschung/Raid (Gilden-Fenster zeigt `research` noch nicht), in Browser und Unity nicht geprüft; Balancing der Platzhalterwerte.
