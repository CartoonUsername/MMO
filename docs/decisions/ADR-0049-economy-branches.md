# ADR-0049: Wirtschaft – Filialen, Offline-Deckel, Weltereignisse, Markt-/Firmenfenster (AP 10)

Status: angenommen (Zahlen sind Entwürfe, siehe `branch_rules_v1.json`)

## Entscheidung
- **Filialen** als Weltdienst `BranchService` (`mmo_world/branches.py`), nicht als CEE-Ereignisse: Eröffnen kostet einmalig Münzen, laufende Kosten pro Tag gehen in die Senke. Jede Filiale gibt zusätzliche Produktionslinien und Lagerplatz; Anzahl begrenzt durch die Unternehmensstufe. Ist die Kasse leer, wird die Filiale nach einigen Tagen „ruhend“ und kann gegen Gebühr wieder geöffnet werden. Schließt die Firma, verschwinden ihre Filialen.
- **Offline-Deckel**: War die Leitung (Gründer/Verwalter) länger als `active_within_days` nicht online, laufen nur `offline_lines` Aufträge weiter. Keine unendliche Geldquelle (Blueprint §75). Aktivität wird beim Beitritt und Tageswechsel vermerkt.
- **Weltereignisse** (`economy_events` in `game_rules_v8.json`): zufällig, mit Dauer und Preisschocks (schlechte Ernte, Grenzkrieg, neue Mine/Hafen, Monsterüberfall); als `economy_event` an Spieler gesendet und in `game.world.economy_news` sichtbar.
- **Client**: Fenster „Markt“ (Kurs, Aufträge, NPC-Händler, Nachrichten) und „Firma“ (gründen, Personal, Lager, Produktion, Filialen, Offline-Warnung). Der Server entscheidet; der Client zeigt nur Absichten.
- Keine CEE-Regeländerung, keine Migration; Snapshot-Schlüssel `branches` nur bei Aktivität, alte Snapshots und Golden-Vektoren unverändert.

## Offen
Töchter (eigene Firmen mit Mutterbeteiligung), NPC-Lebensprofile, Handelsrouten zwischen Regionen, Feintuning aller Zahlen.
