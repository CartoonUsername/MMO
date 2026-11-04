# ADR-0047: Ausrüstung mit Wirkung und Transmog (AP 8)

Status: angenommen (Platzhalterwerte; Blueprint §31: Slots, Seltenheiten, Setboni, Rezepte offen)

## Entscheidung
- Neuer Weltdienst `mmo_world/equipment.py` (Regeln `equipment_rules_v1.json`): 4 Platzhalter-Slots (Waffe, Nebenhand, Brust, Füße), 7 Gegenstände mit Gewichtsklasse (leicht/mittel/schwer), Klassen- und Stufenanforderung. Gegenstände sind normale Inventarschlüssel `item@grade`; Getragenes liegt im Pseudo-Inventar `worn:<Figur>` (keine Duplikation, nicht handelbar solange getragen). Snapshot nur, wenn Ausrüstung existiert – alte Snapshots/Golden Vectors unverändert. Keine CEE-Regeländerung.
- Wirkung ist echt: Schaden (leicht/schwer), erlittener Schaden, Blockwirkung und Ausweichkosten gehen als `gear` in die Kampfsimulation (neue optionale Spielerangabe, geprüft gegen `EFFECT_KEYS`; ohne `gear` ändert sich nichts); Lauftempo wirkt in der Spielschicht. Qualitätsstufe skaliert die Abweichung (`grade_permille`), Kappen begrenzen die Summe.
- Tradeoffs: schwere Rüstung schützt mehr, kostet aber Ausweichkosten und Tempo; Bogen ist schnell, aber schwach bei schweren Treffern.
- Transmog: `equip.look` ersetzt nur die Darstellung, erlaubt sind nur einmal getragene Aussehen der Garderobe und passender Slot; Werte bleiben unverändert. Andere Spieler erhalten die dargestellten Teile im Zustandsabzug (`look`).
- Fundquelle (`game_rules_v6`, Standard): Gegner lassen mit 15 % Wahrscheinlichkeit (deterministischer Hash) Ausrüstung fallen. Gateway: `equip.wear/remove/look`, `query.equipment`; Client-Fenster „Ausrüstung“.

## Offen
Finale Slots, Seltenheiten, Setboni, Herstellungsrezepte (nur `iron_blade` ist heute herstellbar), Waffen-Angriffsmuster und alternative Kampfstile, Animationsbindung, Darstellung der Teile im Client (Schlüssel `gear/<item>` werden geliefert, aber noch nicht gezeichnet), Verknüpfung mit Resonanz/Echos.
