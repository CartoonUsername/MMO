# Golden Test Vectors

Sprachneutrale Testfälle der Character Evolution Engine. Sie legen fest, was **jede** Implementierung (Python-Referenz, spätere C++/C#/Rust-Engine) für dieselben Eingaben ergeben muss. Weichen zwei Implementierungen ab, ist die Abweichung ein Fehler – nie die Regel.

**Nicht von Hand ändern.** Die Dateien werden aus `reference/python/mmo_cee/golden.py` erzeugt:

```bash
cd reference/python
python -m mmo_cee.golden write ../golden    # neu erzeugen (nach bewusster Regel-/Logikänderung)
python -m mmo_cee.golden check ../golden    # prüfen (Exit-Code 1 bei Abweichung)
```

Die Python-Tests (`tests/test_golden.py`) schlagen fehl, wenn Code und Vektoren auseinanderlaufen. Eine bewusste Änderung am Verhalten erfordert: neue Regelversion (Regeldateien sind unveränderlich, ADR-0004), Vektoren neu erzeugen, Änderung im Commit begründen.

## Format (`format: 1`)

| Feld | Bedeutung |
|---|---|
| `name`, `description` | Szenario |
| `rules_file` | Datei in `reference/python/mmo_cee/data/` |
| `rules_sha256` | SHA-256 der Regeldatei-Bytes (Port muss dieselbe Datei laden; sie ist die gemeinsame Regelquelle) |
| `character_id` | immer `"c1"` (ein Charakter je Vektor) |
| `steps[]` | Schritte in Reihenfolge, siehe unten |
| `final_state` | Endzustand aller Engines (`parts`), nur Ganzzahlen, Strings, Listen, Objekte |
| `final_state_sha256` | SHA-256 der kanonischen JSON-Darstellung von `final_state` |
| `derived` | abgeleitete Sichten: `eligible_essences`, `combat_directions`, `style_profile` |

Schritt: `{type, payload, expect, [seq, event_hash], state_sha256}`

- `expect: "accepted"`: Ereignis wird aufgezeichnet. `seq` = Sequenznummer im Log (ab 0), `event_hash` = Hash des Ereignisses (siehe unten), `state_sha256` = Zustands-Hash danach.
- `expect: "rejected"`: Regelverstoß. Es wird **nichts** aufgezeichnet, der Zustand bleibt unverändert (`state_sha256` = Hash davor; `null`, wenn der Charakter noch nicht existiert). Fehlermeldungstexte sind absichtlich nicht Teil des Vertrags.

## Kanonisches JSON und Hashes

- `canonical(x)`: JSON mit **sortierten Schlüsseln**, Trennzeichen `,` und `:` ohne Leerzeichen, UTF-8, Nicht-ASCII nicht escapen. Die Vektoren verwenden nur ASCII.
- Zustandshash: `sha256(canonical(parts))`.
- Ereignishash: `sha256(canonical({character_id, seq, type, payload, rules_version, prev_hash, schema_version}))`; `prev_hash` des ersten Ereignisses = 64 × `"0"`, danach der Hash des Vorgängers; `schema_version` = 1; `rules_version` = `version` der Regeldatei.
- Ganzzahlen sind exakt (kein Gleitkomma in Zuständen). Payloads dürfen Gleitkommazahlen und Booleans als **ungültige** Eingaben enthalten (z. B. `1.5`, `true` als `amount`); ein Port muss sie ablehnen, nicht umwandeln.
- Ganzzahldivision rundet ab (positive Werte); Multiplikationsreihenfolge laut `combat.py` (`raw * scale * outcome * relevance * repeat // 10**9`).

## Prüfverfahren für einen Port

1. Regeldatei laden, SHA-256 mit `rules_sha256` vergleichen.
2. Neuen Charakter `c1` anlegen (leerer Log).
3. Jeden Schritt ausführen: validieren → bei Erfolg aufzeichnen und anwenden, bei Verstoß verwerfen.
4. Pro Schritt `expect`, `seq`, `event_hash`, `state_sha256` vergleichen.
5. Am Ende `final_state`, `final_state_sha256` und `derived` vergleichen.

## Szenarien

`identity_basic`, `element_limits`, `profession_mastery`, `essence_path`, `combat_validation`, `combat_antifarm`, `combat_directions_umbral`, `npc_pipeline`, `rules_v1_without_combat` (Regeln v1–v3 bzw. v1) sowie `essence_scoring_ember`, `essence_decision_path`, `essence_npc_two_candidates` (Regeln v4: Wesensbewertung, Entscheidungen; `derived` enthält dort zusätzlich `essence_scores` und `essence_profile`) sowie `discovery_research` und `discovery_secret_form` (Regeln v5: Entdeckungen; `derived` enthält zusätzlich `known_discoveries` und `discovery_progress`). Die Weltseite (Registry) ist noch nicht durch Golden Vectors abgedeckt. Zusammen decken sie jeden Ereignistyp mit akzeptierten **und** abgelehnten Beispielen ab (durch Test erzwungen).

## Simulation (`reference/golden_sim/sim_fights.json`)

Erzeugt/geprüft mit `python -m mmo_sim.golden write|check ../golden_sim` (Regeln: `mmo_sim/data/sim_rules_v1.json`, per SHA-256 gebunden).

Datei: Kopfzeile mit `format`, `name`, `rules_file`, `rules_sha256`, dann `cases` (ein Fall pro Zeile). Fall: `{name, opponent_type, player_level, inputs, expect, [result, report]}`.

- `inputs`: Liste `[tick, befehl]`, Befehle `light heavy dodge block stun slow flee`.
- `expect: "ok"`: `result = {outcome, ticks, actions, player_hp, opponent_hp, ignored_inputs, damage_ticks}`; `report` = erwarteter CEE-Bericht (Begegnungs-ID `golden-<name>`, Tag 1) oder `null`, wenn keine Aktion stattfand.
- `expect: "error"`: ungültige Eingabe (Typ, Bereich, Reihenfolge, Menge, unbekannter Gegner/Stufe); es wird nichts simuliert.
- Die Simulation ist rein ganzzahlig (Tick = 100 ms). Ereignisreihenfolge je Tick: Spielerbefehle, schwerer Treffer, Sieg-Prüfung, Gegner, Niederlage-Prüfung, Ausdauer-Regeneration (siehe `mmo_sim/fight.py`).
- Pseudozufällige Eingabemuster nutzen einen festen LCG (`x' = (1103515245·x + 12345) mod 2^31`); die Eingaben stehen aber ausgeschrieben in der Datei.

## Visual Evolution (`reference/golden_visual/appearance.json`)

Erzeugt/geprüft mit `python -m mmo_cee.golden_visual write|check ../golden_visual`. Kopfzeile: `format`, `cee_rules_file`/`cee_rules_sha256` (Regeln v4), `visual_rules_file`/`visual_rules_sha256`; danach `cases` (ein Fall pro Zeile): `{name, character_id, state, appearance}`.

- `state` sind die Teilzustände aller Engines (wie `final_state` der CEE-Vektoren); ein Port baut daraus `{character_id, parts: state}` und muss exakt `appearance` liefern, **inklusive** `appearance_sha256` (SHA-256 der kanonischen JSON-Darstellung aller übrigen Felder).
- Ableitung (siehe `mmo_cee/visual.py`): Quellen in Promille; `value = base + Σ gewicht × quelle // 1000` (Floor), Jitter `sha256("<character_id>|<parameter>")[0:4]` (big-endian) `mod (2j+1) − j`, danach Wesens-Delta, Klemmen auf `min/max` (Standard 0..1000), Quantisierung `(v + q//2) // q * q` und erneute Klemmung. Aura: `Σ palette[e] × w[e] // Σ w[e]` mit `w = 500 + affinitaet // 2`, Elemente alphabetisch sortiert. Alle Zahlen Ganzzahlen.
- Die Fälle decken Grundklassen, Elementpaare und Dreierkombination, Kampfstile, Berufe, Entscheidungen, drei Wesensformen und einen NPC ab; `fresh_human` und `fresh_human_other_id` zeigen: gleicher Zustand, andere Figur-ID → andere individuelle Variation.

Inhalte wie Wesensformen, Kampfrichtungen und Zahlen sind vorläufige Vorschläge; die Vektoren sichern nur, dass Implementierungen sie gleich behandeln.
