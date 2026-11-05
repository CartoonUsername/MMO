# ADR-0068: Zweigwahl und Respezialisierung der Berufe (AP 33, rules_v10)

Status: angenommen (**Vorschlag, Claude, autorisiert**; Blueprint-Frage 10, Platzhalterwerte)

## Entscheidung
- Neue CEE-Regelversion `rules_v10.json` (= v9 + `professions.specialization`: `cooldown_days` 7, `cost_first` 0, `cost_change` 500).
- Neues Ereignis `profession.specialize {profession, branch, day}`. Voraussetzung: Erfahrung im Beruf (xp > 0), gültiger Zweig des Berufs, `day` nicht negativ und nicht zurückspringend; ein Wechsel auf einen anderen Zweig erst nach der Abklingzeit. Älterer Regelversionen kennen das Ereignis nicht (abgelehnt).
- Zustand: `parts["profession"]["spec"][beruf] = {branch, day}`, **erst bei Gebrauch angelegt**; unveränderte Zustände und alle alten Golden Vectors bleiben identisch.
- Zweigpunkte und Meisterstücke bleiben als Historie erhalten (sie sind aus den Herstellungsberichten abgeleitet und sinken nie). Die Wahl ändert sie nicht, sie markiert nur den aktiven Zweig (`profession_branches`: `chosen`, `chosen_day`).
- Münzkosten trägt die Weltschicht: `World.specialize` prüft vorab, nimmt die Münzen (Senke, keine neue Geldquelle) und schreibt dann das Ereignis. Befehl `profession.specialize`.
- Golden Vector `profession_specialization` (rules v10).

## Offen
- Die Spielschicht (`game_rules_*`) läuft weiter auf `rules_v9`, die Zweigwahl ist dort noch nicht aktiv; dafür wäre ein `game_rules_v19` mit `cee_rules: rules_v10.json` nötig.
- Der aktive Zweig hat noch keine spielerische Wirkung (nur Auswahl und Anzeige). Clients zeigen ihn nicht an. Keine Berufswechsel zwischen Berufen, keine Berufsliste (Frage 11).
