# ADR-0058: Größere Kampfgruppen für Raids und Weltbosse (AP 19)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §33–35, §45, §55)
- Neue Simulationsregeln `sim_rules_v10.json` (= v9, aber `group.max_party` 8; die Validierung erlaubte schon bis 8). v9 und alle Golden Vectors bleiben unverändert. Neue Spielregeln `game_rules_v12.json` (Standard) verweisen auf v10.
- **Normale Gruppen bleiben bei 4** (`party_rules.max_size`), ebenso normale Dungeons. Größer wird nur dort, wo es gewollt ist:
  - **Gildenraid:** `guild_raid.max_members` (Steinherz-Krypta: 8). Das Beitrittslimit ist `min(max_members, max_party)`.
  - **Weltboss:** Spieler im Umkreis kämpfen bis zur Simulationsgrenze (jetzt 8) mit.
- Gegner-Lebenspunkte wachsen wie bisher um 600 Promille je zusätzlichem Mitglied (8 Spieler: 5,2-fach). Das ist der einzige Ausgleich; eigenes Raid-Balancing steht aus.
- Keine CEE-Änderung, keine Weltmigration.

## Nicht entschieden / offen
- Balancing großer Gruppen (Zuschlag je Mitglied, Gegneranzahl über 3 je Kampf, Bedrohung/Heilung bei 8 Spielern); Raids über 8 Spieler (mehrere Trupps).
- Lastverhalten von 8-Spieler-Kämpfen unter Netzlast; nur die Simulation wurde getestet (deterministisch, Grenzen 1..8).
- Clients (Browser/Unity) zeigen Kampfgruppen vermutlich nur bis 4 sauber an; nicht geprüft.
