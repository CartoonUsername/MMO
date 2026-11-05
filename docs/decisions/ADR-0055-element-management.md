# ADR-0055: Aktives Elementmanagement im Kampf (AP 16)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §26, Frage 6)
- Jedes **geprägte** Element (CEE: max. 2 reguläre + 1 Endgame-Element) schaltet im Kampf seinen Zauber frei: `cast_ember` (Feuer, bestehend) und neu `cast_water`, `cast_earth`, `cast_nature`, `cast_electric`, `cast_ice`, `cast_wind`, `cast_light`, `cast_shadow`. Die Prägung außerhalb des Kampfes ist die Ausrüstung; es gibt keinen Wechsel der Prägung im Kampf.
- **Wechsel im Kampf kostet Zeit:** Nach einem Elementzauber ist ein anderes Element erst nach `elements.switch_ticks` (40 Ticks = 4 s) wirkbar; das gleiche Element nur nach der normalen Abklingzeit. Ein zu früher Wechsel wird wie ein ungültiger Befehl ignoriert (kostet nichts).
- Neue Regeln: `sim_rules_v9.json` (= v8 + 8 Zauber + `switch_ticks`), `game_rules_v10.json` (Standard; `element_abilities`, Elementexposition der neuen Zauber). v8/v9 und alle Golden Vectors bleiben unverändert. Keine CEE-Änderung, keine Weltmigration.
- Spielschicht: `game.elements` (geprägte Elemente, Zauberbefehle, Wechselzeit); `game.kit` enthält die freigeschalteten Zauber (Kit-Leiste des Clients ist datengetrieben).

## Nicht entschieden / offen
- Dreier- und Domänenskills, Wechselwirkung von Elementkombinationen im Kampf (Katalog existiert seit AP 4a).
- Eigene Werte je Element (derzeit alle Zauber mit der Vorlage von `cast_ember`).
- Darstellung/Effekte im Client; im echten Browser und in Unity nicht geprüft.
