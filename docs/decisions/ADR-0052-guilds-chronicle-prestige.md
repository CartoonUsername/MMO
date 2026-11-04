# ADR-0052: Gilden, Weltchronik, Prestige (AP 13)

Status: angenommen (Zahlen sind Entwürfe, siehe `community_rules_v1.json`; Blueprint §45 „noch nicht vollständig ausgearbeitet“, §48 Vorschlag)

## Entscheidung
- Neue Weltdienste in `mmo_world/community.py`; keine CEE-Ereignisse, keine Migration; Snapshot-Schlüssel `guilds` und `chronicle` nur bei Aktivität.
- **Gilden:** freiwillig, eine je Figur. Gründen (Münzen als Senke), Einladen/Annehmen, Rollen Leiter/Offizier/Mitglied, Leitung übergeben, Entfernen, Auflösen (Kasse geht an die Leitung). Gemeinsame Kasse im Inventar `guild:<id>` (Einzahlen alle, Auszahlen Offiziere/Leitung). **Gildenhaus** als Gemeinschaftsprojekt (Stufen erhöhen die Mitgliederzahl). Aktivitätspunkte durch Weltboss-Siege, Dungeon-Erstabschlüsse und Beiträge. Nichts Grundlegendes hängt an einer Gilde; Einzelspieler verlieren keinen Zugang (§45, §49).
- **Weltchronik:** dauerhaft, nur anhängend, nummeriert. Dienste melden über `record`: Siedlungsgründung, Technik-Erstentdeckung, neue Epoche, Gildengründung, Weltboss-Erstsieg, Dungeon-Erstabschluss. Spätere Siege wiederholen den Eintrag nicht. Neue Einträge gehen als `chronicle` an alle Spieler.
- **Prestige:** Ruhmpunkte aus Chronikeinträgen, Titel für Erstleistungen. Titel sind Anerkennung und sperren nichts (§49: keine unfaire Exklusivität).
- Befehlsnamen `guild.stash/take` statt deposit/withdraw (deposit ist serverintern reserviert).
- Client: Fenster „Gilde“ und „Chronik und Ruhm“.

## Offen
Gildenhäuser als Gebäude in der Welt, gemeinsame Gildenforschung, Raids, Veranstaltungen/Treffpunkte, Unterstützung für Einzelspieler über das Mindestmaß hinaus, Gildenchat, seltene/serverexklusive Inhalte mit Bedingungen je Feature (§49), Stadtpolitik (zurückgestellt).
