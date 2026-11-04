# Spielserver-Protokoll – Planung und Referenz

**Status:** Vorschlag (ADR-0019). Nichts hiervon ist bestätigter Spielinhalt; Zahlen sind Platzhalter. Die Referenz in
`reference/python/mmo_server/` setzt die **Befehlsschicht** um (Prüfung, Berechtigung, Idempotenz, Ratenbegrenzung, Audit); Transport,
Anmeldung, Echtzeit-Kampfkanal und Mehrserver-Betrieb sind hier geplant, aber noch nicht gebaut.

## 1. Leitplanken (aus den bestätigten Entscheidungen)

1. **Serverautoritativ.** Clients senden **Absichten** (Befehle, Eingaben), nie Ergebnisse, Fortschritt, Zeit, Preise oder Referenzwerte.
   Berichte an die Charakter-Engine kommen vom Server (Kampf, Herstellung, Handel, Entdeckung).
2. **Gleiche Pipeline für Spieler und NPCs:** NPC-Handlungen laufen durch dieselben Weltdienste wie Spielerbefehle, nur ohne Sitzung.
3. **Deterministisch und überprüfbar:** gleiche Nachrichtenfolge + gleiche Serveruhr = gleiche Welt (Test in der Referenz).
4. **Keine Vorteile durch Bezahlen / kein sinnloses Wiederholen:** Ratenbegrenzung, Idempotenz und die Engine-Deckel ergänzen sich; das
   Protokoll schafft keine Sonderwege.
5. **Windows-PC zuerst, Engine offen:** Das Protokoll ist engine-neutral (JSON-Hülle, versioniert); Unreal/Unity sind reine Clients.

## 2. Schichten

| Schicht | Aufgabe | Stand |
|---|---|---|
| Transport | TLS-gesicherte, geordnete Verbindung für Befehle (Vorschlag: WebSocket über TLS oder gRPC-Stream); später ein getrennter Echtzeitkanal für den Kampf (Vorschlag: QUIC/UDP mit Sequenznummern) | geplant |
| Anmeldung | Konto -> kurzlebiges Sitzungstoken; Zuordnung Sitzung -> Konto -> Figuren; **nie Passwörter/Token im Spielprotokoll oder Log** | geplant |
| **Befehls-Gateway** | Hülle, Typen, Berechtigung, Idempotenz, Rate, Audit, Aufruf der Weltdienste | **Referenz vorhanden** |
| Weltdienste | `mmo_world` (Handel, Markt, Firmen, Produktion, Preise), `mmo_cee` (Figuren) | vorhanden |
| Persistenz | Generationen/Datenbank (ADR-0014), Regelmigration (ADR-0018) | vorhanden (Referenz) |
| Echtzeit-Kampf | `mmo_sim` (10 Ticks/s) mit Eingabeströmen; Berichte an die CEE | Kern vorhanden, Kanal geplant |

## 3. Nachrichtenhülle (Version 1)

Anfrage: `{"v": 1, "id": "<1-64 Zeichen [A-Za-z0-9_-]>", "cmd": "<Befehl>", "args": {...}}` – genau diese Schlüssel.
Antwort: `{"v": 1, "id": "<id>", "ok": true, "result": ...}` oder `{"v": 1, "id": "<id>"|null, "ok": false, "error": {"code": "...", "message": "..."}}`;
bei Wiederholung zusätzlich `"replayed": true`. Nur `code` ist Vertrag, `message` ist Menschentext. Nachrichten sind höchstens
`max_message_bytes` groß, Zeichenketten 1–64 Zeichen, Ganzzahlen bis 10^12, keine Gleitkommazahlen, keine unbekannten Felder.

### Fehlercodes

| code | Bedeutung | Client-Verhalten |
|---|---|---|
| `bad_request` | Hülle/Argumente ungültig, JSON kaputt, zu groß | Fehler beheben; die Anfrage-ID bleibt frei |
| `unsupported_version` | `v` unbekannt; Antwort nennt `supported` | Client aktualisieren |
| `unknown_session` | keine gültige Sitzung | neu anmelden |
| `unknown_command` | Befehl nicht im Katalog | – |
| `forbidden` | handelnde Figur gehört nicht zur Sitzung | – (Manipulation oder Fehler) |
| `duplicate_conflict` | Anfrage-ID mit anderem Inhalt wiederverwendet | neue ID wählen |
| `rate_limited` | Eimer leer | später mit **derselben** ID wiederholen |
| `rejected` | Weltregel verletzt (`WorldError`), nichts geändert | Anzeige für den Spieler |
| `rejected_by_rules` | Charakterregeln lehnen ab (`RuleViolation`), z. B. Figur nicht migriert | Anzeige / Migration abwarten |
| `server_error` | Speicher-/Programmfehler (ohne Details) | später erneut; Betrieb informieren |

## 4. Pipeline (Reihenfolge ist Vertrag)

1 Größe/JSON -> 2 Hülle -> 3 Version -> 4 Sitzung -> 5 Befehl bekannt -> 6 Argumente (exakte Schlüssel, Typen) -> 7 Berechtigung
(das Argument „handelnde Figur“ muss zur Sitzung gehören; Zielfiguren dürfen fremd sein) -> 8 Idempotenz -> 9 Ratenlimit ->
10 Ausführung (Einzelschreiber) -> 11 Antwort + Audit.

- **Idempotenz:** Je Konto merkt der Server die letzten `idempotency_window` schreibenden Anfragen samt Antwort (auch Ablehnungen). Gleiche
  ID + gleicher Inhalt = gleiche Antwort ohne erneute Ausführung (Netzwerk-Wiederholungen sind sicher); gleiche ID + anderer Inhalt =
  `duplicate_conflict`. Fehlerhafte/verbotene/ratenbegrenzte Anfragen verbrauchen die ID nicht. Lesende Abfragen werden nicht gespeichert.
- **Ratenbegrenzung:** Eimer je (Figur bzw. Konto bei Abfragen ohne Figur, Gruppe) mit Kapazität und Nachfüllung je Server-Tick; Wiederholungen
  und ungültige Anfragen kosten nichts. Das ergänzt, ersetzt aber nicht die Deckel der Engines.
- **Audit:** Hash-verkettetes Protokoll (Tick, Konto, Anfrage-ID, Befehl, Ergebniscode) **ohne Inhalte**; begrenzte Länge.
- **Reihenfolge:** Die Welt hat einen Schreiber; Befehle werden nacheinander ausgeführt (Reihenfolge = Ankunft, bei Gleichzeitigkeit nach
  Serverregel). Zeit ist die Serveruhr.

## 5. Befehlskatalog (aus `mmo_server/protocol.py` erzeugt: `python -m mmo_server.docgen`)

<!-- KATALOG:BEGIN -->
| Befehl | Argumente | handelnde Figur | Art | Ratengruppe |
|---|---|---|---|---|
| `craft` | char:s, recipe:s, qty:i, grade:s, technique?:s, element?:s | char | schreibend | craft |
| `discovery.complete` | char:s, discovery:s | char | schreibend | default |
| `discovery.teach` | teacher:s, learner:s, discovery:s | teacher | schreibend | default |
| `market.place` | char:s, side:s, item_key:s, qty:i, price:i, ioc?:b | char | schreibend | market.place |
| `market.cancel` | char:s, order:s | char | schreibend | default |
| `maker.sell` | char:s, item_key:s, qty:i | char | schreibend | default |
| `maker.buy` | char:s, item_key:s, qty:i | char | schreibend | default |
| `trade.offer` | char:s, to:s, side:s, item_key:s, qty:i, price:i | char | schreibend | default |
| `trade.accept` | char:s, offer:s | char | schreibend | default |
| `trade.decline` | char:s, offer:s | char | schreibend | default |
| `trade.cancel` | char:s, offer:s | char | schreibend | default |
| `party.form` | char:s | char | schreibend | default |
| `party.invite` | char:s, target:s | char | schreibend | default |
| `party.accept` | char:s, invite:s | char | schreibend | default |
| `party.decline` | char:s, invite:s | char | schreibend | default |
| `party.leave` | char:s | char | schreibend | default |
| `party.kick` | char:s, member:s | char | schreibend | default |
| `party.promote` | char:s, member:s | char | schreibend | default |
| `party.set_loot` | char:s, mode:s | char | schreibend | default |
| `party.disband` | char:s | char | schreibend | default |
| `notify.ack` | char:s, upto:i | char | schreibend | default |
| `notify.mute` | char:s, kinds:l | char | schreibend | default |
| `notify.unmute` | char:s, kinds:l | char | schreibend | default |
| `combat.set_loadout` | char:s, abilities:l | char | schreibend | default |
| `company.found` | char:s, capital:i | char | schreibend | default |
| `company.close` | actor:s, company:s | actor | schreibend | default |
| `company.hire` | actor:s, company:s, char:s, wage:i, share?:i | actor | schreibend | default |
| `company.fire` | actor:s, company:s, char:s | actor | schreibend | default |
| `company.resign` | char:s, company:s | char | schreibend | default |
| `company.set_contract` | actor:s, company:s, char:s, wage?:i, share?:i | actor | schreibend | default |
| `company.promote` | actor:s, company:s, char:s | actor | schreibend | default |
| `company.demote` | actor:s, company:s, char:s | actor | schreibend | default |
| `company.upgrade` | actor:s, company:s | actor | schreibend | default |
| `company.poach` | actor:s, company:s, char:s, wage:i | actor | schreibend | default |
| `company.offer_shares` | char:s, company:s, qty:i, price:i | char | schreibend | default |
| `company.preempt` | char:s, company:s, offer:s, qty:i | char | schreibend | default |
| `company.purchase` | char:s, company:s, offer:s, qty:i, ack:s | char | schreibend | default |
| `company.withdraw_offer` | char:s, company:s, offer:s | char | schreibend | default |
| `company.grant_equity` | actor:s, company:s, char:s, qty:i | actor | schreibend | default |
| `company.propose` | char:s, company:s, kind:s, candidate?:s | char | schreibend | default |
| `company.vote` | char:s, company:s, proposal:s, yes:b | char | schreibend | default |
| `production.stock_in` | actor:s, company:s, item_key:s, qty:i | actor | schreibend | default |
| `production.stock_out` | actor:s, company:s, item_key:s, qty:i | actor | schreibend | default |
| `production.start` | actor:s, company:s, worker:s, recipe:s, batches:i, grade:s | actor | schreibend | default |
| `production.cancel` | actor:s, company:s, job:s | actor | schreibend | default |
| `production.sell` | actor:s, company:s, item_key:s, qty:i | actor | schreibend | default |
| `query.quote` | item_key:s | – | lesend | query |
| `query.disclosure` | company:s | – | lesend | query |
| `query.inventory` | char:s | char | lesend | query |
| `query.economic_profile` | char:s | char | lesend | query |
| `query.offers` | char:s | char | lesend | query |
| `notify.fetch` | char:s, after?:i, limit?:i | char | lesend | query |
| `query.party` | char:s | char | lesend | query |
| `query.party_invites` | char:s | char | lesend | query |
| `query.abilities` | char:s | – | lesend | query |
| `query.character` | char:s | char | lesend | query |
| `character.choose_class` | char:s, base_class:s | char | schreibend | default |
| `essence.decide` | char:s, decision:s, choice:s | char | schreibend | default |
| `essence.trial` | char:s, form:s | char | schreibend | default |
| `essence.adopt` | char:s, form:s, ack:s | char | schreibend | default |
| `echo.activate` | char:s, echo:s | char | schreibend | default |
| `echo.release` | char:s, echo:s | char | schreibend | default |
| `echo.equip` | char:s, echo:s, role:s | char | schreibend | default |
| `echo.unequip` | char:s, echo:s | char | schreibend | default |
| `echo.upgrade` | char:s, echo:s, protect?:b, request_id?:s | char | schreibend | default |
| `echo.list` | char:s, echo:s, price:i | char | schreibend | default |
| `echo.cancel` | char:s, listing:s | char | schreibend | default |
| `echo.buy` | char:s, listing:s | char | schreibend | default |
| `query.settlements` | char:s | char | lesend | query |
| `settlement.found` | char:s, site:s, name:s | char | schreibend | default |
| `plot.buy` | char:s, site:s, n:i | char | schreibend | default |
| `plot.abandon` | char:s, site:s, n:i | char | schreibend | default |
| `plot.build` | char:s, site:s, n:i, building:s | char | schreibend | default |
| `plot.stash_in` | char:s, site:s, n:i, item_key:s, qty:i | char | schreibend | default |
| `plot.stash_out` | char:s, site:s, n:i, item_key:s, qty:i | char | schreibend | default |
| `project.contribute` | char:s, site:s, project:s, coins?:i, item_key?:s, qty?:i | char | schreibend | default |
| `query.research` | char:s | char | lesend | query |
| `research.start` | char:s, site:s, tech:s | char | schreibend | default |
| `research.license` | char:s, site:s, tech:s | char | schreibend | default |
| `research.contribute` | char:s, site:s, tech:s, coins?:i, item_key?:s, qty?:i | char | schreibend | default |
| `query.guild` | char:s | char | lesend | query |
| `guild.found` | char:s, name:s, tag:s | char | schreibend | default |
| `guild.invite` | char:s, target:s | char | schreibend | default |
| `guild.accept` | char:s, guild:s | char | schreibend | default |
| `guild.decline` | char:s, guild:s | char | schreibend | default |
| `guild.leave` | char:s | char | schreibend | default |
| `guild.kick` | char:s, target:s | char | schreibend | default |
| `guild.role` | char:s, target:s, role:s | char | schreibend | default |
| `guild.disband` | char:s | char | schreibend | default |
| `guild.stash` | char:s, item_key:s, qty:i | char | schreibend | default |
| `guild.take` | char:s, item_key:s, qty:i | char | schreibend | default |
| `guild.contribute` | char:s, coins?:i, item_key?:s, qty?:i | char | schreibend | default |
| `query.chronicle` | offset?:i, limit?:i, kind?:s | – | lesend | query |
| `query.prestige` | char:s | char | lesend | query |
| `query.echoes` | char:s | char | lesend | query |
| `equip.wear` | char:s, item_key:s | char | schreibend | default |
| `equip.remove` | char:s, slot:s | char | schreibend | default |
| `equip.look` | char:s, slot:s, item?:s | char | schreibend | default |
| `query.equipment` | char:s | char | lesend | query |
| `query.my_companies` | char:s | char | lesend | query |
| `query.market` | char:s | char | lesend | query |
| `query.market_quote` | item_key:s | – | lesend | query |
| `company.branch_open` | actor:s, company:s, region:s | actor | schreibend | default |
| `company.branch_close` | actor:s, company:s, branch:s | actor | schreibend | default |
| `company.branch_reopen` | actor:s, company:s, branch:s | actor | schreibend | default |
| `query.element_catalog` |  | – | lesend | query |
| `query.appearance` | char:s | – | lesend | query |

Argumentkürzel: `s` Zeichenkette, `i` Ganzzahl, `b` Wahrheitswert, `l` Liste von Zeichenketten (höchstens 16), `?` optional.

### Bewusst nur serverintern (nicht erreichbar)

- **cee_create/cee_record** – Charaktererstellung und Ereignisse kommen vom Server (Berichte, Kampf, Herstellung)
- **discovery.gather** – Beweise vergibt der Server aus Spielereignissen
- **trade (direkt, ohne Zustimmung)** – Der Handelsdienst selbst ist intern; Clients handeln nur über Orderbuch oder Angebot/Annahme (`trade.*`)
- **deposit/revenue** – Münzquellen sind serverintern
- **party.loot (Beuteverteilung) / party_expire** – Beute verteilt der Server nach dem Kampf an Teilnehmer mit Beitrag; Einladungsfristen räumt der Tagesschritt ab
- **advance_day/price_advance/market_expire** – Tagesschritte macht der Server nach seiner Uhr
- **price_shock/rules_upgrade/rules_migrate** – Weltereignisse und Betriebsaktionen
- **persistence (export/import/commit)** – Betrieb
<!-- KATALOG:END -->

### Benachrichtigungen (Push, ADR-0024)

Der Server legt für betroffene Figuren Benachrichtigungen in ein **Postfach** (Folgenummer `seq` je Figur) und kann sie live über den Transport schieben (`Gateway.on_push`); **zuverlässig wird es durch Abruf**: `notify.fetch(char, after, limit)` liefert alles nach `after` samt `latest` und `gap` (Lücke, falls das begrenzte Postfach Einträge verdrängt hat), `notify.ack(char, upto)` räumt auf, `notify.mute/unmute` schaltet Arten stumm. Zustellung mindestens einmal, der Client entdoppelt über `seq`. Benachrichtigungen tragen nur Kennungen und Konditionen (kein Inventar/Salden) und sind nicht maßgeblich: die Wahrheit liegt im Weltzustand.

Arten: `market.fill`, `market.expired`, `trade.offer_received/accepted/declined/cancelled/expired`, `company.hired/left/employee_left/promoted/demoted/warning/closed/shares_offered/proposal_opened/proposal_resolved`, `production.job_done`, `discovery.taught`.

## 6. Echtzeit-Kampf (Planung)

- Welche Befehle ein Spieler im Kampf nutzen darf, folgt aus seiner **Kampfausrüstung** (`combat.set_loadout`, ADR-0020): Grundbefehle plus die der ausgerüsteten Fähigkeiten; der Server ignoriert andere Eingaben.
- Eigener Kanal, 10 Server-Ticks/s (`mmo_sim`). Client sendet **Eingaben** mit Sequenznummer (`light heavy dodge block stun slow flee`),
  der Server entscheidet Treffer, Ausweichen, Block usw. und sendet Zustandsupdates (Schnappschüsse mit Delta).
- Gruppenkämpfe (ADR-0022): Der Server nennt die Teilnehmer, jeder sendet nur seine Eingaben; zusätzliche Befehle `heal`/`shield` (nur mit den Fähigkeiten `ally_mend`/`ally_ward`); jeder Teilnehmer erhält seinen eigenen Bericht.
- Am Ende erzeugt der Server den Begegnungsbericht für `combat.encounter_resolved`; die Begegnungs-ID vergibt der Server (Archivierung
  gewerteter IDs ist offen, siehe ADR-0014).
- Offene Fragen: Latenzausgleich (Rückspulen vs. Vorhersage am Client), Interessenverwaltung für Gruppen/Weltbosse, Raumgeometrie und
  Kollision (noch nicht in `mmo_sim`), Anti-Cheat-Signale (unmögliche Eingabefrequenz ist schon durch `max_actions_per_minute` begrenzt).

## 7. Sicherheit

- Eingaben sind feindlich: exakte Schemata, Größen- und Typgrenzen, keine Rückmeldung von Interna (`server_error` ohne Details).
- Berechtigung am Gateway (Besitz der Figur) **und** in den Weltdiensten (Rolle in der Firma, Eigentümer, Geschäftsführer).
- Keine Geheimnisse (Passwörter, Token, Schlüssel) in Protokoll, Audit, Snapshots oder Logs. Token werden nur an der Transportgrenze geprüft.
- Missbrauch über Mehrfachkonten (Scheinfirmen, Eigenhandel, Boosting) erkennt das Protokoll nicht; Signale dafür gehören in eine spätere
  Analyse (nur aus Spielverlauf, nie aus Daten realer Personen).
- Betrugsabwehr gegen Replay: Anfrage-IDs je Konto + TLS; gegen Mitschnitt/Fälschung der Sitzung: kurzlebige Token, Bindung an die Verbindung.

## 8. Versionierung und Betrieb

- `v` in jeder Nachricht; additive Änderungen (neue Befehle, optionale Felder) ohne neue Version, brechende mit neuer Version und
  Übergangszeit. Der Katalog ist maschinenlesbar (diese Tabelle wird aus dem Code erzeugt; ein Test erzwingt, dass jeder Befehl hier steht).
- Regelversionen der Figuren (ADR-0018): Clients melden ihre Protokollversion, der Server migriert Figuren zu festgelegten Zeitpunkten
  (Wartung/Login); nicht migrierte Figuren erhalten `rejected_by_rules`.
- Betrieb: Einzelschreiber je Weltscherbe (Shard), Persistenz-Speicherpunkte nach jeder Befehlsfolge oder zeitgesteuert (Transaktion über
  Logs, Inventar und Register, ADR-0014), Tagesschritte (`advance_day`, Preis- und Orderverfall) nach Serveruhr, Metriken (Codes,
  Latenz, Ratenbegrenzungen) und Audit-Auswertung.
- Skalierung (offen): Aufteilung nach Region/Stadt, Übergabe von Figuren zwischen Scherben, Konsistenz von Firmen und Markt über Scherben.

## 9. Offene Entscheidungen

1. Transport und Format im Detail (WebSocket+JSON für Befehle ist die Referenz; Binärformat und QUIC für den Kampf?).
2. Direkter Zwei-Parteien-Handel: Angebot/Annahme umgesetzt (ADR-0023); offen sind Gegenangebote und Tausch mehrerer Gegenstände.
3. Push-Nachrichten: Postfach mit Abruf/Quittung/Stummschaltung umgesetzt (ADR-0024); offen sind der Transport des Live-Push (Verbindung, Wiederaufbau), Benachrichtigung außerhalb des Spiels (Mobilgerät/E-Mail) und weitere Ereignisarten (Kampf; Gruppenereignisse `party.*` sind umgesetzt, ADR-0025).
4. Konten, Anmeldung, Token-Lebensdauer, Sperren, Jugendschutz/Rechtliches (nicht Teil der Referenz).
5. Reihenfolge und Fairness bei gleichzeitigen Befehlen vieler Spieler (Tick-Batching oder strikte Ankunftsreihenfolge).
6. Rückgängigmachen/Entschädigung bei Serverfehlern, Behandlung von `server_error` mit teilweise geänderter Welt.
