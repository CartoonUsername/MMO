# ADR-0048: Regionen, Gefahrenstufen, Dungeon und Weltboss (AP 9)

Status: angenommen (Platzhalterwerte)

## Entscheidung
- Neue Spielregeln `game_rules_v7` (Standard). Die Zone (6000×6000 cm) ist in 7 benannte Regionen mit Gefahrenstufe 1–5 und empfohlener Stufe geteilt. **Normale Regionen sind nie durch Stufen gesperrt** (nur Warnung bei Gefahr ≥ 4), mutige Spieler dürfen früh hinein. Gefahr belohnt: Beute- und Erfahrungsbonus je Stufe (1000/1000/1100/1250/1500 ‰).
- Besondere Regionen können Voraussetzungen verlangen (`requires`): das „Verborgene Tal“ verlangt die Entdeckung `old_shrine_map` (aus den Erkundungshinweisen, AP 3). Der Server lässt den Schritt entfallen und meldet den Grund (`region_blocked`); der Client kann das nicht umgehen.
- Gegnervielfalt: Steingolems in den Schattenhöhen (Beute und Respawn je Art); `stone_imp` bleibt Beschworener/Dungeon-Gegner ohne Beute.
- Dungeon „Alte Mine“: Gruppen-Durchlauf in 3 Etappen (feste Gegnergruppen), 3 Zutritte pro Tag und Figur, Abschlusstruhe einmal pro Tag. Nutzt die vorhandene Live-Kampf-/Report-Maschinerie (Server berechnet jede Etappe neu und reicht Berichte an die CEE). Niederlage/Flucht/Verbindungsabbruch beendet den Durchlauf. **Logisch instanziert** (eigene Gruppe/Etappen, Karten-Gegner ignorieren Teilnehmer), aber noch keine räumlich getrennte Instanz.
- Weltboss (Steinherz-Koloss): Spieler im Umkreis kämpfen mit (bis zur Gruppengrenze), serverweite Meldungen bei Erscheinen/Besiegen, Kiste für alle mit Beitrag.
- Client: HUD zeigt Region/Gefahr, Ereignisse im Log, Knopf „Dungeon betreten“ am Eingang. Befehle `game.world`, `game.dungeon_enter`.
- Keine CEE-Regeländerung, keine Migration. Ältere Simulationen ohne die Dungeon-/Boss-Gegner schalten diese Inhalte ab statt zu scheitern.

## Offen
Mehrere Server-Regionen/echte Instanzen (AP 14), Reisepunkte/Schiffe/Tore, Fortbewegungsstufen und Epochen (§35), Weltboss-Terminplanung und größere Schlachtzüge, Kartenzeichnung der Regionen im Client, weitere Gegnerarten und Ökologie.
