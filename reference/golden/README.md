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

`identity_basic`, `element_limits`, `profession_mastery`, `essence_path`, `combat_validation`, `combat_antifarm`, `combat_directions_umbral`, `npc_pipeline`, `rules_v1_without_combat` (Regeln v1–v3 bzw. v1) sowie `essence_scoring_ember`, `essence_decision_path`, `essence_npc_two_candidates` (Regeln v4: Wesensbewertung, Entscheidungen; `derived` enthält dort zusätzlich `essence_scores` und `essence_profile`) sowie `discovery_research` und `discovery_secret_form` (Regeln v5: Entdeckungen; `derived` enthält zusätzlich `known_discoveries` und `discovery_progress`). sowie `crafting_validation`, `crafting_antifarm`, `crafting_discovery_techniques` und `crafting_directions` (Regeln v6: Herstellungsberichte; `derived` enthält zusätzlich `known_recipes`, `known_techniques`, `craft_direction_scores`, `craft_directions` und `craft_profile`). sowie `economy_trade_validation`, `economy_wash_trading`, `economy_career_founding` und `economy_directions` (Regeln v7: Handel, Laufbahn, Gründung; `derived` enthält zusätzlich `economic_profile`, `economic_direction_scores` und `economic_directions`) sowie `combat_abilities_loadout` (Regeln v9: Fähigkeiten freischalten, `combat.loadout_set` mit Platzgrenze nach Stufe; `derived` enthält zusätzlich `unlocked_abilities`, `ability_progress`, `loadout_slots` und `allowed_commands`) und `economy_dynamic_reference` (Regeln v8: Handelsberichte mit serverseitig gemeldetem `reference`, Spanne, Gutschrift nach gemeldetem Wert). Die Weltseite hat eigene Vektoren (Abschnitt „Weltseite“). Zusammen decken sie jeden Ereignistyp mit akzeptierten **und** abgelehnten Beispielen ab (durch Test erzwungen).

## Simulation (`reference/golden_sim/sim_fights.json`)

Erzeugt/geprüft mit `python -m mmo_sim.golden write|check ../golden_sim` (Regeln: `mmo_sim/data/sim_rules_v1.json` als Standard und `sim_rules_v2.json` für Fälle mit Fähigkeitswirkung, beide per SHA-256 gebunden).

Datei: Kopfzeile mit `format`, `name`, `rules_file`, `rules_sha256`, `extra_rules` (weitere Regeldateien -> SHA-256), dann `cases` (ein Fall pro Zeile). Fall: `{name, opponent_type, player_level, inputs, expect, [result, report]}`.

- `inputs`: Liste `[tick, befehl]`, Befehle `light heavy dodge block stun slow flee`.
- `expect: "ok"`: `result = {outcome, ticks, actions, player_hp, opponent_hp, ignored_inputs, damage_ticks}`; `report` = erwarteter CEE-Bericht (Begegnungs-ID `golden-<name>`, Tag 1) oder `null`, wenn keine Aktion stattfand.
- Optional `allowed` (Liste von Befehlen): Kampfausrüstung der Figur (CEE-Regeln v9). Befehle außerhalb der Liste zählen als `ignored_inputs` und werden nicht ausgeführt; `flee` geht immer; ohne das Feld sind alle Befehle erlaubt. Ungültiges `allowed` (unbekannter Befehl, keine Liste) = Fehler.
- Optional `equipped` (Liste eindeutiger Fähigkeitsnamen) und `rules_file` (Standard: Kopf-Datei): Die Wirkung ausgerüsteter Fähigkeiten steht in `ability_effects` der Regeldatei (ADR-0021). Zusammensetzung: `*_permille` multiplizieren (Fähigkeiten alphabetisch, je Schritt abgerundet), `block_damage_permille` = Minimum, `*_bonus`/`*_delta` addieren. Anwendung: leicht/präzise Schaden, schwerer Schaden, Betäubungs-/Verlangsamungsdauer, Parade-Schwäche des Gegners, Ausweichen-Kosten/-Abklingzeit (nur Ausweichen), Ausdauerregeneration je Tick, erlittener Schaden (auch bei Block), Block-Durchlass. Fähigkeiten ohne Eintrag und Regeln ohne Tabelle: keine Wirkung. Ungültiges `equipped` = Fehler.
- `expect: "error"`: ungültige Eingabe (Typ, Bereich, Reihenfolge, Menge, unbekannter Gegner/Stufe); es wird nichts simuliert.
- Die Simulation ist rein ganzzahlig (Tick = 100 ms). Ereignisreihenfolge je Tick: Spielerbefehle, schwerer Treffer, Sieg-Prüfung, Gegner, Niederlage-Prüfung, Ausdauer-Regeneration (siehe `mmo_sim/fight.py`).
- Pseudozufällige Eingabemuster nutzen einen festen LCG (`x' = (1103515245·x + 12345) mod 2^31`); die Eingaben stehen aber ausgeschrieben in der Datei.

## Visual Evolution (`reference/golden_visual/appearance.json`)

Erzeugt/geprüft mit `python -m mmo_cee.golden_visual write|check ../golden_visual`. Kopfzeile: `format`, `cee_rules_file`/`cee_rules_sha256` (Regeln v4), `visual_rules_file`/`visual_rules_sha256`; danach `cases` (ein Fall pro Zeile): `{name, character_id, state, appearance}`.

- `state` sind die Teilzustände aller Engines (wie `final_state` der CEE-Vektoren); ein Port baut daraus `{character_id, parts: state}` und muss exakt `appearance` liefern, **inklusive** `appearance_sha256` (SHA-256 der kanonischen JSON-Darstellung aller übrigen Felder).
- Ableitung (siehe `mmo_cee/visual.py`): Quellen in Promille; `value = base + Σ gewicht × quelle // 1000` (Floor), Jitter `sha256("<character_id>|<parameter>")[0:4]` (big-endian) `mod (2j+1) − j`, danach Wesens-Delta, Klemmen auf `min/max` (Standard 0..1000), Quantisierung `(v + q//2) // q * q` und erneute Klemmung. Aura: `Σ palette[e] × w[e] // Σ w[e]` mit `w = 500 + affinitaet // 2`, Elemente alphabetisch sortiert. Alle Zahlen Ganzzahlen.
- Die Fälle decken Grundklassen, Elementpaare und Dreierkombination, Kampfstile, Berufe, Entscheidungen, drei Wesensformen und einen NPC ab; `fresh_human` und `fresh_human_other_id` zeigen: gleicher Zustand, andere Figur-ID → andere individuelle Variation.

Inhalte wie Wesensformen, Kampfrichtungen und Zahlen sind vorläufige Vorschläge; die Vektoren sichern nur, dass Implementierungen sie gleich behandeln.

## Weltseite (`reference/golden_world/world_scenarios.json`)

Erzeugt/geprüft mit `python -m mmo_world.golden write|check ../golden_world` (Regeln: `rules_v7.json`, `company_rules_v1.json`, `market_rules_v1.json`, `production_rules_v1.json` und `pricing_rules_v1.json`, alle per SHA-256 gebunden; Szenarien mit Preisdynamik laufen unter `rules_v8.json`). Abgedeckt: Inventar, Entdeckungsregister und -dienst, Herstellung, Handel, Markt/Orderbuch, Firmenproduktion, Firmenregister und -dienst (inkl. Anteile, Beschlüsse, Abwerben, Liquidation) – jeweils zusammen mit der CEE (Figuren sind echte CEE-Figuren).

Datei: Kopfzeile (`format`, `name`, `cee_rules_file/_sha256`, `company_rules_file/_sha256`, `market_rules_file/_sha256`, `production_rules_file/_sha256`, `pricing_rules_file/_sha256`, `extra_cee_rules` = Regeldateien zusätzlich zur Standarddatei samt SHA-256), dann `scenarios`. Szenario: `{name, description, steps, final, final_world_sha256}`, ein Schritt pro Zeile. Ein Schritt ist die **Operation** (`op` plus Argumente) und die **erwartete Reaktion**: `expect: "ok"` mit `result` (Rückgabewert, `null` wenn keiner) oder `expect: "error"` mit `error` (nur die Fehlerklasse `WorldError` = Weltregel verletzt, `RuleViolation` = CEE lehnt ab, `PersistenceError` = Speicher-/Migrationsprüfung; Fehlertexte sind **nicht** Teil des Vertrags), und `world_sha256` = SHA-256 (kanonisches JSON) des gesamten Weltzustands **nach** dem Schritt.

- **Weltzustand** (`final` bzw. Eingabe des Hashes): `{day, inventory, discovery, companies, counters{trade,craft}, characters{id: state_sha256}}`, plus `exchange` (Orderbuch, Zähler, Preisstatistik) – dieser Schlüssel fehlt, solange nie eine Order gestellt wurde – ebenso `production` (Aufträge, Zähler, Abnehmer-Tagessummen), solange die Produktion nie benutzt wurde, und `pricing` (Faktoren, Schocks, Tagesmengen des Händlers; nur unter v8). `inventory`/`discovery`/`companies` sind die JSON-Snapshots der Register (`to_json`), `characters` die Zustands-Hashes der CEE (wie in den CEE-Vektoren). Ein Port muss diese Struktur nicht intern so halten, aber Hashes und Snapshots exakt liefern.
- **Operationen** (`op`): `cee_create cee_record deposit day disc_gather disc_complete disc_teach craft trade found hire fire resign set_contract promote demote upgrade revenue advance_day poach offer_shares preempt purchase withdraw_offer grant_equity propose vote close disclosure rules_upgrade rules_migrate price_advance price_shock maker_sell maker_buy market_place market_cancel market_expire prod_stock_in prod_stock_out prod_start prod_cancel prod_sell`. Argumente stehen im Schritt (siehe `OPS` in `mmo_world/golden.py`). `day` setzt die Serverzeit; sie kann nur vorwärts laufen, die Dienste lesen sie bei jedem Aufruf.
- **Platzhalter:** `"$disclosure"` als `ack` eines Kaufs = Hash der *aktuellen* Offenlegung der Firma des Schritts; `save_as` bei `disclosure` merkt einen Hash unter einem Namen, `"$name"` liest ihn wieder.
- **Abgelehnte Schritte** ändern die Welt nicht, mit zwei bewussten Ausnahmen: (a) eine Aktion, die nach der ID-Vergabe scheitert (Herstellung, Handel, Order – z. B. durch eine CEE-Ablehnung), verbraucht die ID (nur der Zähler steigt, IDs werden nie wiederverwendet); (b) eine Abstimmung nach Fristende setzt den Antrag auf `expired` und wird dennoch abgelehnt.
- **Münzen:** Quelle ist nur `deposit`, `revenue`, `prod_sell` und `maker_sell` (serverintern); alle anderen Schritte erhalten die Summe (Test über alle Szenarien; `world:sink` zählt mit).
- **Szenarien:** `world_trade_inventory`, `world_crafting`, `world_discovery`, `company_lifecycle` (u. a. Lohn 19 bei Bedarf 20: `19·1000//20 = 950`, negative Zufriedenheitsänderung mit Floor-Division, unbezahlte Mitarbeiter, Kündigungen), `company_governance` (echter Aufstieg bis Manager über Handel, Vorkaufsrecht, Offenlegung, Beschlüsse, Veto, Ausführungsfehler, Geschäftsführer), `company_poach_close` (Abwerben angenommen/abgelehnt, Liquidation mit Rundungsrest) `rules_migration` (Start unter CEE v7, `rules_upgrade` auf v8 mitten im Ablauf mit zwei von drei Figuren, `rules_migrate` für den Nachzügler; die Welt wechselt die Regeln, das Szenario trägt die Startdatei), `price_dynamics` und `random_price_5` (CEE-Regeln v8: Referenzwert folgt dem Markt, Schocks, NPC-Händler; diese Szenarien tragen `cee_rules_file`, alle anderen laufen unter der Kopf-Datei), `company_production` (Lager, Linien, Chargen, Stillstand, Abnehmer mit Tageslimit, Abbruch, Schließung), `market_orderbook` (Preis-Zeit-Priorität, Teilausführung, IOC, Preisband, Limits, Verfall, Gebühr), `random_market_3` sowie `random_world_4` und `random_world_9`: zustandsbewusst erzeugte Zufallsskripte (xorshift32, Seeds 4 und 9, je 260 Aktionen), die **vollständig ausgeschrieben** in der Datei stehen – ein Port braucht den Zufallsgenerator nicht.
- **Prüfverfahren:** Szenario lesen, neue Welt anlegen (Regeln wie im Kopf), Schritt für Schritt Operation ausführen, Reaktion und `world_sha256` vergleichen; am Ende `final` und `final_world_sha256`. Die Referenz tut dasselbe in `verify_vector` und meldet die erste abweichende Schrittnummer je Szenario.

Alle Inhalte (Rezepte, Preise, Firmenregeln) sind vorläufige Platzhalter; die Vektoren sichern nur, dass Implementierungen sie gleich behandeln.

### Regelversions-Migration (ADR-0018) – was ein Port nachbilden muss

- **Ereignis** `identity.rules_migrated`, aufgezeichnet unter der **neuen** Regelversion, Payload `{from, to, state_sha256, from_rules_sha256, to_rules_sha256}`; genau eine Stufe in der Reihe der Regelversionen (numerisch sortiert); Clients dürfen es nicht aufzeichnen.
- `state_sha256` = SHA-256 des kanonischen JSON (sortierte Schlüssel, kompakte Trenner, `ensure_ascii=false`) der Teilzustände (`parts`) unmittelbar vor der Migration; `*_rules_sha256` = SHA-256 desselben kanonischen JSON der **Regeldaten** (nicht der Dateibytes).
- **Replay:** bis zum Ereignis mit den alten Regeln ableiten; am Ereignis Stufe, Hashes, Ereignis-Regelversion und „nicht vor der Erstellung“ prüfen (sonst Integritätsfehler), Teilzustände übernehmen, neue Engines mit ihrem Anfangszustand ergänzen, danach die neuen Regeln anwenden. Ereignisse unter einer anderen Version ohne vorherige Migration sind ein Fehler.
- **Sperre:** Eine Figur mit älterer Regelversion nimmt an keiner validierten Aktion teil (Fehlerklasse `RuleViolation`), bis sie migriert ist.

## Gruppenkampf (`reference/golden_group/sim_groups.json`)

Erzeugt/geprüft mit `python -m mmo_sim.golden_group write|check ../golden_group` (Regeln: `mmo_sim/data/sim_rules_v3.json`, per SHA-256 gebunden). Kopf: `format`, `name`, `rules_file`, `rules_sha256`; danach `cases` (ein Fall pro Zeile): `{name, opponent_type, players, expect, [result, reports]}`.

- `players`: Liste von 1 bis `group.max_party` Spielern `{level, inputs, [allowed], [equipped]}` (Felder wie im Einzelkampf; zusätzliche Befehle `heal`, `shield`).
- `expect: "ok"`: `result = {outcome, ticks, opponent_hp, players: [{outcome, ticks, actions, player_hp, ignored_inputs, damage_ticks}]}` und `reports` = je Spieler der erwartete CEE-Bericht (Begegnungs-ID `golden-<name>`, Tag 1) oder `null` ohne Aktionen. `expect: "error"`: ungültige Eingabe, nichts wird simuliert.
- **Ablauf je Tick:** Spieler in Indexreihenfolge verarbeiten ihre Befehle (Flucht: Spieler scheidet aus, sein vorgemerkter schwerer Treffer verfällt; nicht erlaubte Befehle zählen als ignoriert); sind keine Kämpfer mehr übrig, endet der Kampf (Ticks = aktueller Tick); schwere Treffer lösen sich in Indexreihenfolge auf; Sieg-Prüfung (Ticks = Tick+1); Gegner; Spieler mit Lebenspunkten <= 0 scheiden aus (Niederlage, Ticks = Tick+1); sind keine Kämpfer mehr übrig, endet der Kampf; Ausdauer-Regeneration der Kämpfer.
- **Gegner:** Leben = `hp · (1000 + p · (n − 1)) // 1000` (p = `opponent_hp_per_extra_member_permille`). Beim Beginn eines Angriffs Ziel = kämpfender Spieler mit der höchsten **Bedrohung** (verursachter Schaden aus leichten/präzisen/schweren Treffern + `heilung · heal_permille // 1000`), Gleichstand: kleinster Index; bei Auflösung neu wählen, falls das Ziel nicht mehr kämpft. Ausweichen/Blocken/Parieren zählen beim Ziel.
- **Heilen:** Ziel = kämpfender Verbündeter (nicht man selbst) mit `hp < max_hp` und kleinstem `hp · 1000 // max_hp`, Gleichstand: kleinster Index; Heilmenge `min(amount, max_hp − hp)`; kein Ziel, Busy, zu wenig Ausdauer oder Abklingzeit = ignoriert (ohne Kosten). **Schild:** Ziel = kämpfender Verbündeter ohne aktives Schild (`shield_hp > 0` und `t < shield_until`) mit der höchsten Bedrohung (Gleichstand: kleinster Index); setzt `shield_hp = absorb`, `shield_until = t + ticks` (ersetzt kein aktives). Schaden wird zuerst vom aktiven Schild geschluckt; ein vollständig geschluckter Schlag erzeugt keinen Eintrag in `damage_ticks`.
- **Ausgang je Spieler:** `victory` (kämpfte bis zum Sieg), `defeat` (ausgefallen), `fled` (geflohen oder Zeitlimit); Gruppe: `victory`; sonst `defeat`, wenn jemand ausgefallen ist und keiner mehr kämpft, sonst `fled`.
- Mit genau einem Spieler und ohne `heal`/`shield` ist das Ergebnis identisch zum Einzelkampf (Fall `solo_equals_single_player_group` und der Äquivalenztest der Referenz).

