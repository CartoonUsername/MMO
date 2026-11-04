# ADR-0046: Kampfechos und Resonanz +0..+30 (AP 7)

Status: angenommen (Platzhalterwerte; Blueprint-Fragen 7–9 bleiben offen)

## Entscheidung
- Neuer Weltdienst `mmo_world/echo.py` (`EchoService`, Regeln `echo_rules_v1.json`, in `World` verdrahtet). Ein Echo ist ein einzigartiges Objekt mit Definition, Besitzer, Bindung, Resonanzstufe und Pechschutzzähler; er erscheint im Weltsnapshot nur, wenn Echos existieren – alte Snapshots und Golden Vectors bleiben unverändert. Keine CEE-Regeländerung, keine Migration.
- Zustände: unaktiviert (handelbar) → aktiviert + charaktergebunden → mit Resonanzsiegel wieder handelbar; Resonanzstufe, Aktivierung und Pechschutz bleiben beim Verkauf erhalten.
- Upgrade (atomar): alle Prüfungen vor jeder Änderung; Kosten (Staub + Münzen) werden immer fällig; Erfolg +1; Fehlschlag verliert nur die Kosten. Ab `drop_from_level` sinkt die Stufe um 1, außer ein Schutzstein verhindert es (nur dann verbraucht). Echos werden nie zerstört. Pechschutz: +Promille je Fehlschlag bis Obergrenze, Reset bei Erfolg.
- Zufall nur serverseitig: SHA-256 aus geheimem, persistiertem Seed, Echo-ID und Versuchszähler (nachvollziehbar, vom Client nicht beeinflussbar/vorhersagbar). `request_id` macht Wiederholungen idempotent (Replay-Schutz).
- Handel: Angebot/Kauf atomar über Inventar (Münzen, Gebühr 5 %), ein Echo kann nicht doppelt angeboten oder verkauft werden. Persönliche Meisterschaft (Figur × Tradition, Tageslimit) wechselt nicht mit dem Objekt.
- Haupttradition + Hybrid-Plätze (1 + 2 als Platzhalter, Klassenprüfung, keine doppelte Tradition).
- Bezug im Spiel (`game_rules_v5`): erster Sieg über Alpha-Wolf / Schattenjäger / Steinherz-Koloss schenkt einmalig ein Echo; Siege liefern Resonanzstaub (Koloss: Schutzstein, Siegel); Meisterschaft pro Sieg mit ausgerüsteter Haupttradition.
- Gateway: `echo.activate/release/equip/unequip/upgrade/list/cancel/buy`, `query.echoes`; Client-Fenster „Kampfechos“.

## Nicht entschieden / offen
Anzahl gleichzeitig ausrüstbarer Echos (Frage 7), echte Raten/Kosten (8), serverexklusive Echos (9). Noch **nicht** umgesetzt: Wirkung der Echos im Kampf (Fähigkeiten/Passive fließen noch nicht in die Simulation), Visual-/Animationsassets (nur Schlüssel `echo/<def>/<band>`), Benachrichtigungen, Rechte-Hash der Echo-Regeln im Weltumschlag.
