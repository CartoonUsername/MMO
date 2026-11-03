# ADR-0023: Direkter Zwei-Parteien-Handel (Angebot und Annahme)

**Status:** akzeptiert als technische Grundlage. **Alle Zahlen** (Frist, Limits, Gebühr) in `trade_rules_v1.json` sind Platzhalter, keine bestätigten Spielinhalte.

**Kontext:** Der `TradeService` (ADR-0011) ist serverintern und setzt voraus, dass beide Seiten dem Handel zugestimmt haben; Clients konnten bisher nur über das Orderbuch (ADR-0015) handeln. Für gezielte Geschäfte zwischen zwei Spielern (Absprachen, Freunde, Auftragsarbeit) braucht es Zustimmung beider Seiten ohne Betrugsmöglichkeit.

**Entscheidungen**
1. **Angebot -> Annahme.** Ein Angebot richtet sich an genau eine andere Figur und ist **unveränderlich**: `sell` (Anbieter gibt Ware für einen Gesamtpreis) oder `buy` (Anbieter gibt Münzen für Ware). Nur die angesprochene Figur kann **annehmen oder ablehnen**, nur der Anbieter kann **zurücknehmen**; nach `offer_days` verfällt es (`expire(day)`, serverinterner Tagesschritt; gültig bis zum Vortag der Frist).
2. **Immer gedeckt:** Der Anbieter hinterlegt seine Leistung sofort im Treuhandkonto `trade:escrow` (Ware bzw. Münzen); es kann also kein Angebot ohne Deckung geben, und die Gegenseite kann nicht überrumpelt werden (die Bedingungen ändern sich nach dem Stellen nicht).
3. **Annahme = regulärer Handel:** Die Hinterlegung geht zurück an den Anbieter, dann läuft `TradeService.trade` (beide CEE-Berichte, Plausibilität, Wiederholungsabnahme je Partner, Referenzwert ab Regeln v8). **Scheitert** die Annahme (zu wenig Münzen/Ware der Gegenseite, CEE-Ablehnung, z. B. Figur nicht migriert), wird die Hinterlegung wiederhergestellt und das **Angebot bleibt bestehen**.
4. **Gebühr:** Anteil des Erlöses (`fee_permille`, abgerundet) vom Verkäufer an die Geldsenke – wie am Orderbuch, damit direkter Handel die Gebühr nicht umgeht.
5. **Freie Preise:** Es gibt kein Preisband (anders als im Orderbuch); die CEE wertet nur Preise nahe am Referenzwert, Scheinpreise zwischen eigenen Konten bringen also keine Punkte (Test).
6. **Limits gegen Spam:** höchstens `max_open_offers` ausgehende Angebote je Figur und `max_incoming_offers` eingehende je Figur; keine Angebote an sich selbst oder unbekannte Figuren.
7. **Protokoll:** Befehle `trade.offer`, `trade.accept`, `trade.decline`, `trade.cancel`, Abfrage `query.offers` (nur eigene Angebote, nur für die eigene Figur). Berechtigung am Gateway (handelnde Figur gehört zur Sitzung) und in der Welt (Adressat/Anbieter).
8. **Persistenz und Vektoren:** Die Angebote sind Teil des Weltsnapshots (`trade_offers`, nur wenn je benutzt), werden beim Laden gegen das Treuhandkonto geprüft; die Handelsregeln sind per SHA-256 an Snapshot und Golden Vectors gebunden. Golden-Szenario `direct_trade`.

**Absicherung:** `tests/test_direct_trade.py` (19 Tests: Hinterlegung, Ablehnungen ohne Wirkung, Limits, Rollen/Gebühr, Berechtigungen, Erstattung, fehlgeschlagene Annahme, Frist-Grenzen, Erhaltungssatz bei Zufallsfolgen, Persistenz/Manipulation, Gateway) plus Golden Vectors; Mutationstests (alle erkannt).

**Offen / Grenzen**
- Keine Gegenangebote, kein Tausch mehrerer Gegenstände, keine Mehr-Parteien-Geschäfte, kein Handel mit Firmenanteilen (dafür bleibt das Vorkaufsverfahren, ADR-0012).
- **Kein Push:** Die Gegenseite erfährt von einem Angebot nur durch Abfrage (`query.offers`); Benachrichtigungen sind Teil der noch offenen Push-Ereignisse.
- Scheinhandel und Geldwäsche über Mehrfachkonten werden nicht erkannt (die CEE wertet nur plausible Preise und dämpft Wiederholungen mit demselben Partner).
