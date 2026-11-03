# Architektur der Character Evolution Engine (CEE)

## Leitprinzipien

1. **Event Sourcing.** Die einzige Wahrheit ist die append-only Charakterhistorie. Jeder Zustand (Wesen, Elemente, Berufe …) ist eine deterministische Ableitung (Replay) aus dieser Historie.
2. **Serverautoritativ & nachvollziehbar.** Jedes Ereignis trägt `schema_version`, `rules_version` und einen Hash-Verweis auf den Vorgänger (Manipulationserkennung, Audit).
3. **Datengetrieben & versionierbar.** Schwellen, Wesensformen, Berufe stehen in versionierten Regeldateien (`rules_v1.json`), nicht im Code.
4. **Nur die Spielfigur.** Eingaben sind ausschließlich Spielereignisse der Figur; keine Analyse realer Persönlichkeit.
5. **Gleiche Pipeline für Spieler und NPCs.** `identity.created.kind` ist der einzige Unterschied.
6. **Engine-Isolation.** Jede Engine besitzt einen Teilzustand (`state.parts[name]`) und kennt nur Ereignisse ihres Präfixes; Querverweise lesen den Zustand anderer Engines nur lesend.

## Ablauf

```
record(type, payload) → Engine.validate(state, event)  (RuleViolation bei Regelbruch)
                      → EventLog.append (Hash-Kette)
                      → Engine.apply(state, event)
load(character)       → Replay des Logs durch dieselben Engines (deterministisch)
```

## Die zehn Engines

| # | Engine | Ereignis-Präfix | Status |
|---|---|---|---|
| 1 | Identity | `identity.` | **implementiert** (Typ Spieler/NPC, Klasse, XP/Level) |
| 2 | Essence (Wesen) | `essence.` | **implementiert** (gewichtete Bewertung aus der Historie, Entscheidungen, Prüfung, dauerhafte Annahme, Vor-/Nachteile; Legacy-Schema weiter gültig) |
| 3 | Combat Development | `combat.` | **implementiert** (Metriken, Entwicklungsrichtungen, Anti-Farming; ab Regeln v9 Fähigkeiten mit Ausrüstung und Befehlsfreigabe für die Simulation, ADR-0020; Wirkung als Modifikatoren in `sim_rules_v2`, ADR-0021; eigene Fähigkeitsbefehle/Raum offen; Gruppenkampf mit Unterstützung seit ADR-0022) |
| 4 | Element | `element.` | **implementiert** (9 Elemente, Prägung, 2 + 1 Limit) |
| 5 | Profession | `profession.` | **implementiert** (Erfahrung → Meisterschaftsstufe) |
| 6 | Discovery | `discovery.` | **implementiert** (Charakterseite in der CEE + Weltseite `mmo_world`, ADR-0009; Inhalte sind Platzhalter) |
| 7 | Crafting | `crafting.` | **implementiert** (Handwerksprofil aus Herstellungsberichten in der CEE + Server-Herstellung/Inventar in `mmo_world`, ADR-0010; Inhalte sind Platzhalter) |
| 8 | Economic Profile | `economy.` | **implementiert** (Handelsberichte, Laufbahn, Gründung in der CEE + Handelsdienst in `mmo_world`, ADR-0011; Firmensimulation und Märkte offen; Inhalte sind Platzhalter) |
| 9 | Character History | (Querschnitt) | **implementiert** (`history.py`: Log, Hash-Kette, Verifikation) |
| 10 | Visual Evolution | (keine Ereignisse) | **implementiert** (reine Ableitung Zustand → Erscheinungsparameter, ADR-0008; Optik ist Platzhalter) |

## Combat Development Engine (Details, siehe ADR-0003)

- Einziges Ereignis: `combat.encounter_resolved` – ein **serverseitig bestätigter Begegnungsbericht** mit beobachteten Aktionszählern (`actions: {Aktion: Anzahl}`), Gegnertyp/-stufe, Ergebnis, Dauer und Spieltag. Das Payload-Schema ist strikt: jedes unbekannte Feld (z. B. `points`, `strength`) wird abgelehnt.
- Punkte entstehen nur in der Engine: Aktionen → Dimensionen (Gewichte aus Regeln) × Ergebnis × Relevanz × Wiederholungsabnahme, danach Tageslimit je Dimension (voller Satz bis `full_cap`, reduziert bis `hard_cap`, dann 0).
- Exploit-Schutz: eindeutige `encounter_id` je Charakter, Plausibilität der Aktionsraten (`max_per_minute`, Dauer, Burst), Tag darf nicht zurückspringen, Wiederholungsabnahme je Gegnertyp und Tag, Abwertung trivialer Gegner.
- Entwicklungsrichtungen sind eine **abgeleitete Sicht** (`reached_directions`): gewichtete Summen der Dimensionspunkte gegen Stufenschwellen. Nicht exklusiv, Punkte sinken nie, jede Dimension bleibt unabhängig von der Grundklasse trainierbar.
- Ganzzahl-Arithmetik (Promille) für Bit-Identität bei der späteren C++-Portierung (ADR-0004).
- Grenze: Die Engine kann nur prüfen, was der Bericht behauptet. Dass der Bericht echt ist, muss der Gameplay-Server sicherstellen (siehe „Vertrauensgrenze“ in ADR-0003).

Querverbindung: Wesensformen können Mindeststufen von Kampfrichtungen verlangen (`combat_directions` in den Essence-Regeln); die Essence Engine liest dafür nur die abgeleitete Sicht der Combat Engine.

## Firmensimulation (ADR-0012)

`mmo_world.CompanyRegistry` (Weltzustand: Kasse als Inventarkonto, Gebäudelevel = Kapazität, Unternehmenslevel aus Umsatz, Anteile, Mitarbeiter, Angebote, Anträge) und `CompanyService` (Gründung, Einstellung/Entlassung/Verträge, Beförderung bis Manager, Gebäudeausbau, Tagesabschluss mit Gehalt/Gewinnbeteiligung/Zufriedenheit/Loyalität/Warnung/Kündigung/Reputation, Abwerben, Anteile mit Vorkaufsrecht und Offenlegungsbestätigung, Gesellschafterbeschlüsse mit Gründer-Veto, Schließung mit Liquidation). Mitarbeiter sind Figuren; Laufbahn und Gründung laufen über die CEE-Ereignisse aus ADR-0011. Reine Regelfunktionen in `mmo_world/company.py`; Regeln `mmo_world/data/company_rules_v1.json` (Platzhalter).

## Economic Profile (ADR-0011)

*Charakterseite* (`mmo_cee.economy`): `economy.trade_completed` (Referenzwert exakt aus Regeltabelle, Preisband, Wiederholungsabnahme je Handelspartner und Tag, Tageslimits, Netzwerkbonus nur für qualifizierte neue Partner), `economy.career_changed` (Karriereleiter mit Meisterschaft, Dienstzeit und Punkten; Beförderung nur eine Stufe; Firmenwechsel nur nach Austritt), `economy.company_founded`/`company_closed` (Gate, Höchstzahl offener Firmen, IDs nie wiederverwendbar). Abgeleitet: nicht-exklusive Handelsrichtungen und `economic_profile`. *Weltseite* (`mmo_world`): `TradeService` (atomare Übertragung von Ware und Münzen, beide Berichte vorab validiert, Rückbuchung bei Ausfall) und `Inventory.apply_many`. Schutz vor Scheinhandel: kein Selbsthandel, absurde Preise und Kleinsthandel bringen weder Volumen noch Netzwerk.

## Crafting Engine (ADR-0010)

*Charakterseite* (`mmo_cee.crafting`): `crafting.crafted` (serverbestätigter Bericht: Rezept, Technik, Element, Menge, Qualität, Tag) → Dimensionen (Menge, Feinarbeit, Innovation, Infusion), Materialfamilien und Element-Infusionen mit Wiederholungsabnahme und Tageslimits; nicht-exklusive Handwerksrichtungen als abgeleitete Sicht. Rezepte/Techniken folgen aus Berufsmeisterschaft und Entdeckungen. Die CEE prüft die Qualität auf Plausibilität (bestmögliche Stufe). *Weltseite* (`mmo_world`): atomares `Inventory` und `CraftingService` (Eingaben verbrauchen → Bericht → Ausgaben, vollständiger Rollback; Berufserfahrung nur aus gedeckelten Punkten). Ohne Eingangsmaterial entsteht keine Produktion.

## Discovery Engine (ADR-0009)

*Charakterseite* (`mmo_cee.discovery`): Ereignisse `discovery.evidence_gathered` (eindeutige Beweise), `discovery.made` (Abschluss mit Anerkennung), `discovery.learned` (nur teilbare Entdeckungen). *Weltseite* (`mmo_world`): `DiscoveryRegistry` (Pionier, Halter, endliches Lehrfenster) und `DiscoveryService` (transaktionale Verbindung beider Ebenen, Rollback bei Ablehnung). Unabhängige Forschung ist nie blockiert; nur das Lehren ist im Fenster dem Pionier vorbehalten. Entdeckungen speisen das Wesenssystem (Signal `discovery:<id>`, Gate `requires_discoveries` für geheime Formen). `RulesVersionMismatch` verhindert stilles Replay unter anderen Regeln.

## Visual Evolution (ADR-0008)

`VisualEvolution.appearance(state)` leitet aus dem Charakterzustand engine-neutrale Parameter ab: `body_set` (Grundklasse), Morphs, Materialien, Effektstärken, Aura-/Hautfarbe (freie Elementmischung), Teile-IDs, Animations-Tags, Signatur und Hash. Kein eigener Zustand, keine Ereignisse; nur der Server berechnet, Clients lesen. Regeln: `visual_rules_v1.json` (Platzhalter, validiert). Golden Vectors: `reference/golden_visual/`.

## Wesensbewertung (ADR-0007)

Regeln v4: Jede Wesensform hat gewichtete Signale (Elementprägung/-affinität, Kampfrichtung, Berufsmeisterschaft, Entscheidungen) und eine Schwelle; kein einzelnes Signal genügt allein. `essence.decision_made` bildet bewusste, einmalige Entscheidungen ab (Wirkung nur aus Regeldaten, vom Server ausgelöst). Abgeleitete Sichten: `form_scores` (Punkte/Beiträge/Prüfbarkeit), `essence_profile` (Vor-/Nachteile). Alle Inhalte sind Platzhalter.

## Serverseitiger Kampfkern `mmo_sim` (ADR-0006)

Deterministische 1:1-Simulation (Ganzzahlen, 10 Ticks/s). Der Client sendet nur Befehle; die Simulation entscheidet über Treffer, Ausweichen, Block, Parade, Betäubung und Verlangsamung und erzeugt daraus den Begegnungsbericht für `combat.encounter_resolved`. `EncounterServer` vergibt IDs, Gegner, Stufe und Tag. Die Verträglichkeit mit den CEE-Plausibilitätslimits wird rechnerisch (`check_compatibility`) und durch Spam-Tests geprüft. Alle Zahlen sind vorläufig. Absicherung: `reference/golden_sim/` (Golden Vectors der Simulation).

## Golden Test Vectors (ADR-0005)

`reference/golden/*.json` enthalten Szenarien mit erwarteten Ereignis-/Zustands-Hashes, abgelehnten Eingaben und abgeleiteten Sichten. Jede Portierung muss sie bit-identisch bestehen; Python-Tests erzwingen, dass die Vektoren mit der Referenz übereinstimmen. Format und Prüfverfahren: `reference/golden/README.md`. Die Weltseite (Inventar, Register, Herstellung, Handel, Firmen) hat eigene Skript-Vektoren mit Welt-Hash nach jedem Schritt: `reference/golden_world/` (ADR-0013).

## Persistenz und Migration (ADR-0014, Vorschlag)

`World` (`mmo_world/world.py`) verdrahtet CEE, Inventar, Register und Dienste. `mmo_world.persistence` speichert Historien (Hash-Ketten) und einen Weltsnapshot (Tag, Inventar, Register, Zähler, Zustands-Hashes) in atomaren Generationen (`Store`); `import_world` prüft beim Laden Format, Regel-Hashes, Ketten, abgeleiteten Zustand und Querbezüge und wirft sonst `PersistenceError`. Format-Migration über `MIGRATIONS`; Regelversionswechsel ist bewusst keine stille Migration (Vorschlag: aufgezeichnetes Migrationsereignis). Bekannte Lücke: Inventar ohne Besitzjournal.

## Markt und Preisbildung (ADR-0015)

`Exchange` (`mmo_world/exchange.py`): Orderbuch je Gut+Güteklasse mit Limit-Orders, Hinterlegung im Treuhandkonto, Preis-Zeit-Priorität (Preis der wartenden Order), Teilausführung, IOC, keine Selbstausführung, Preisband um den CEE-Referenzwert, Gebühr in die Geldsenke, Verfall nach Tagen, Preisindex (letzter Preis, gleitender Durchschnitt, Tagesverlauf). Ausführungen laufen über den `TradeService` (CEE-Berichte unverändert). Regeln: `market_rules_v1.json` (Platzhalter).

## Firmenproduktion (ADR-0016)

`ProductionService` (`mmo_world/production.py`): Firmenlager (Inventarkonto), Produktionslinien nach Gebäudestufe, Aufträge mit Arbeiter und Chargen, Fortschritt nur im Tagesabschluss und nur bei bezahltem, angestelltem Arbeiter, gedeckelte Ausbeute/Qualität, Betriebskosten in die Geldsenke, NPC-Abnehmer mit Tageslimit. Keine CEE-Berichte (kein Berufsfortschritt aus Offline-Produktion). Haken in `CompanyService` (`day_hooks`, `close_hooks`). Regeln: `production_rules_v1.json` (Platzhalter).

## Preisdynamik (ADR-0017, CEE-Regeln v8)

Ab `rules_v8.json` meldet der Server den Referenzwert jedes Handels (`payload.reference`); die CEE prüft nur eine feste Spanne um den Tabellenwert, der Replay bleibt deterministisch. `PricingService` (`mmo_world/pricing.py`): Preisfaktoren je Gut+Güte, die sich täglich dem Marktsignal (Orderbuch-Durchschnitt) und Schocks nähern (begrenzte Schritte und Spanne), und ein NPC-Händler mit Tagesmengen, der Extrempreise begrenzt. Orderbuch-Band und NPC-Abnehmer der Firmen nutzen denselben Referenzwert. Regeln: `pricing_rules_v1.json` (Platzhalter).

## Regelversions-Migration (ADR-0018)

Eine Figur wechselt die Regelversion durch ein aufgezeichnetes Ereignis `identity.rules_migrated` (neue Version, Hash des Zustands davor, Fingerabdrücke beider Regeln). `RulesChain` (`mmo_cee/migration.py`) spielt Historien mit mehreren Regelversionen ab; `CharacterService.migrate()` hebt eine Figur um eine Stufe an. Nicht migrierte Figuren sind lesbar, aber für alle Aktionen gesperrt. `persistence.upgrade_world` hebt eine ganze Welt (oder eine Teilmenge der Figuren) auf eine höhere CEE-Regeldatei.

## Server-Protokoll (ADR-0019, `docs/PROTOCOL.md`)

`mmo_server.Gateway` ist die Befehlsschicht zwischen Clients und Weltdiensten: JSON-Hülle `{v, id, cmd, args}`, exakter Befehlskatalog (nur Absichten, nie Zeit/Fortschritt/Ergebnisse), Berechtigung (handelnde Figur gehört zur Sitzung), Idempotenz je Konto, Ratenbegrenzung je Figur und Gruppe nach Serveruhr, hash-verkettetes Audit ohne Inhalte. Alles, was Fortschritt, Zeit, Geld oder Weltzustand setzt, ist serverintern. Transport, Anmeldung, Push, Echtzeit-Kampfkanal und Mehrserver-Betrieb sind in `docs/PROTOCOL.md` geplant.

## Zielarchitektur (Vorschlag, nicht bestätigt)

Der Python-Prototyp ist die **Referenzimplementierung** für Regeln und Tests. Die produktive Server-Engine (z. B. C++/Rust-Dienst oder Unreal-Dedicated-Server-Modul) übernimmt Datenformat (Event-Schema, Regel-JSON) und die Testvektoren des Prototyps. Die Unreal-Seite konsumiert nur den abgeleiteten State (Visual Evolution), schreibt nie direkt.
