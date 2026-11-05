# ADR-0060: Raid-Balancing nach Gruppengröße (AP 21)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Messung (Balancing-Bots `mmo_sim.balance`, sim_rules_v10, Stufe 14/25, Richtwerte)
- Wächterhalle und Kammer der Splitter sind ab 6 Spielern kaum noch fordernd (Verlust unter 13 % der Lebenspunkte).
- Steinherz-Koloss mit Begleiter: 2 Spieler verlieren (auch gute), 4 gute Spieler gewinnen (36 % Verlust), 4 durchschnittliche verlieren, durchschnittliche gewinnen ab 6.
- Die Bots sind vereinfachte Modelle, kein Ersatz für echte Spieltests.

## Entscheidung (`game_rules_v13.json`, Standard; v12 bleibt)
- `guild_raid.min_members` von 2 auf **4**, damit der Raid nicht für Gruppen angeboten wird, die den Boss nicht schaffen können.
- Neue Etappen-Option **`min_party`**: eine Etappe wird nur bei ausreichender Gruppengröße gespielt. Die **Splitterwache** (2 Steinwächter + Imp) kommt ab 6 Mitgliedern vor dem Boss dazu. Der Durchlauf speichert seine Etappenliste (`stages`).
- Keine Änderung an der Simulation (weiter `sim_rules_v10`), keine CEE-Änderung, keine Weltmigration.

## Offen
- Echte Spieltests; Zuschlag der Gegner-Lebenspunkte je Mitglied bleibt 600 Promille. Mehr als 3 Gegner pro Kampf und weitere Raid-Mechaniken (Phasen, Pflichtrollen) fehlen. Kampfanzeige im Browser für 8 Teilnehmer nicht im Browser geprüft; `docs/BALANCE_REPORT.md` deckt weiter nur Gruppen bis 4 (sim_rules_v7) ab.
