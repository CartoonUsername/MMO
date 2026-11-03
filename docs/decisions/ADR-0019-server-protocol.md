# ADR-0019: Server-Protokoll (Befehlsschicht)

**Status:** Vorschlag mit Referenzimplementierung der Befehlsschicht (`reference/python/mmo_server/`). Transport, Anmeldung, Echtzeit-Kampfkanal und Mehrserver-Betrieb sind in `docs/PROTOCOL.md` geplant, aber nicht gebaut. Alle Größen und Ratenlimits (`protocol_rules_v1.json`) sind Platzhalter.

**Kontext:** Die Weltdienste (`mmo_world`) und die Charakter-Engine setzen Berechtigungen zwar teilweise durch (Rolle in der Firma, Eigentümer), vertrauen aber dem Aufrufer, dass er die handelnde Figur wirklich vertritt – „wer rufen darf“ war bewusst offen (ADR-0012). Vor einer produktiven Server-Engine muss festgelegt sein, welche Aktionen Clients überhaupt auslösen können und wie Nachrichten geprüft werden.

**Entscheidungen**
1. **Clients senden Absichten.** Der Katalog (`COMMANDS`) nennt je Befehl Name, exakte Argumente samt Typ, die **handelnde Figur** und den Weltaufruf. Kein Befehl nimmt Zeit, Fortschritt, Punkte, Qualität, Wert oder Referenzwerte an (Test). Alles andere (Beweise, Tagesschritte, Münzquellen, Schocks, Regel-Upgrade, direkte Berichte) ist **serverintern** (`INTERNAL_ONLY`) und für Clients nicht erreichbar.
2. **JSON-Hülle Version 1:** `{v, id, cmd, args}` mit genau diesen Schlüsseln; Antwort `{v, id, ok, result | error{code, message}}`; nur der Code ist Vertrag. Zeichenketten 1–64 Zeichen, Ganzzahlen bis 10^12, keine Gleitkommazahlen, Größenlimit der Nachricht.
3. **Berechtigung am Gateway:** Das Argument „handelnde Figur“ muss zur Sitzung (Konto) gehören (`forbidden`), Zielfiguren dürfen fremd sein; die Fachprüfung (Rolle, Eigentum, Frist) bleibt in den Weltdiensten. Abfragen eigener Daten (Inventar, Profil) sind ebenfalls an die Figur gebunden, öffentliche (Kurs, Offenlegung, Erscheinung) nicht.
4. **Idempotenz:** Je Konto gilt eine Anfrage-ID im Fenster einmal; Wiederholung mit gleichem Inhalt liefert die gespeicherte Antwort ohne erneute Ausführung (auch Ablehnungen), anderer Inhalt = `duplicate_conflict`. Ungültige, verbotene und ratenbegrenzte Anfragen verbrauchen die ID nicht.
5. **Ratenbegrenzung:** Eimer je (Figur bzw. Konto, Gruppe), Nachfüllung je Server-Tick (Serveruhr, nie Clientzeit); Wiederholungen und ungültige Anfragen kosten nichts. Sie ergänzt die Deckel der Engines, ersetzt sie nicht.
6. **Fehlerabbildung:** `WorldError` -> `rejected`, CEE-Fehler (`RuleViolation`, auch „Figur nicht migriert“, ADR-0018) -> `rejected_by_rules`, Speicherfehler -> `server_error`; unerwartete Ausnahmen -> `server_error` ohne Details.
7. **Audit:** Hash-verkettetes, begrenztes Protokoll (Tick, Konto, ID, Befehl, Ergebniscode) **ohne Inhalte** und ohne Geheimnisse.
8. **Determinismus:** Gleiche Nachrichtenfolge + gleiche Serveruhr = gleiche Antworten, gleicher Weltzustand, gleiches Audit (Test).
9. **Dokument und Code bleiben deckungsgleich:** `docs/PROTOCOL.md` enthält die aus dem Katalog erzeugte Befehlstabelle; ein Test erzwingt, dass jeder Befehl dort steht.

**Absicherung:** `tests/test_server_gateway.py` (33 Tests: Hülle/Größen/Typen, Sitzungen, Berechtigung für jeden Befehl mit fremder Figur ohne Weltänderung, Idempotenz inkl. Fenster und Konten, Ratenlimits inkl. Wiederholungen, Fehlerabbildung, Audit, Determinismus, Ende-zu-Ende über Markt/Firma/Produktion); Mutationstests (ein verbleibender Mutant ist gleichwertig).

**Offen / Grenzen**
- Kein Transport, keine Anmeldung/Token-Prüfung, kein Push (Ereignisse an Clients), kein direkter Zwei-Parteien-Handel (Angebot/Annahme), keine Echtzeit-Eingaben für den Kampf (nur Planung), kein Mehrserver-/Scherben-Betrieb.
- Das Gateway ist ein Einzelschreiber; Parallelität und Fairness bei Gleichzeitigkeit sind offen. Bei `server_error` durch einen Programmfehler kann die Welt teilweise geändert sein (append-only Logs); der Betrieb muss dann den Zustand prüfen (Persistenzprüfung, ADR-0014).
- Missbrauch über Mehrfachkonten erkennt das Protokoll nicht.
