# ADR-0015: Markt und Preisbildung

**Status:** akzeptiert als technische Grundlage. **Alle Zahlen** (Gebühr, Preisband, Fristen, Limits) in `market_rules_v1.json` sind **Platzhalter**, keine bestätigten Spielinhalte.

**Kontext:** Bisher handeln zwei Figuren direkt (`TradeService`, ADR-0011). Eine Spielwirtschaft braucht einen Markt, auf dem Angebot und Nachfrage Preise bilden, ohne dass Clients Preise, Mengen oder Fortschritt behaupten können. Bestätigt sind: serverautoritativ, deterministisch, kein sinnloses Wiederholen (Wash-Trading-Schutz der CEE), keine dauerhaften Vorteile durch Bezahlen.

**Entscheidungen**
1. **Orderbuch je Gegenstand+Güteklasse** (`Exchange`, `mmo_world/exchange.py`), Limit-Orders mit ganzzahligem Stückpreis. Kauf und Verkauf; optional `ioc` (sofort ausführen, Rest verfällt).
2. **Immer gedeckt:** Ware (Verkauf) bzw. Münzen (Kauf, Menge × Limit) liegen im Treuhandkonto `market:escrow`. Invariante `check()`: Treuhand == Summe der offenen Orders (auch beim Laden und in `check_consistency` der Persistenz geprüft).
3. **Ausführung:** Preis-Zeit-Priorität, es gilt der Preis der **wartenden** Order (kein Vorteil für schnelles Überbieten ohne Gegenpartei), Teilausführung, **keine Selbstausführung** (eigene Orders werden übersprungen). Jede Ausführung läuft durch den bestehenden `TradeService`: beide CEE-Handelsberichte, Plausibilität und Wash-Trading-Schutz gelten unverändert. Die Differenz zwischen Limit und Ausführungspreis geht an den Käufer zurück.
4. **Preisbildung:** Preise entstehen im Buch, aber nur innerhalb eines **Bandes** (`band_permille`, Platzhalter ±250 ‰) um den Referenzwert der Regeltabelle der CEE; so lässt sich der Markt nicht auf absurde Preise treiben. Der **Preisindex** je Gut (letzter Preis, gleitender Durchschnitt `ema_milli` mit ganzzahliger Glättung, Tageshoch/-tief/-volumen, Tagesabschlüsse der letzten `history_days`) ist reine Information – er verändert den CEE-Referenzwert nicht.
5. **Gebühr:** Anteil des Erlöses (`fee_permille`, abgerundet) vom Verkäufer an die Geldsenke `world:sink` (Münzen bleiben bilanziert). **Verfall:** Orders laufen nach `order_days` ab (`expire(day)`, serverinterner Tagesschritt); höchstens `max_open_orders` wartende Orders je Figur (IOC zählt nicht).
6. **Fehlerverhalten:** Ungültige Eingaben ändern nichts. Scheitert eine Ausführung unerwartet (z. B. interner Ausfall), wird die laufende Order zurückgenommen und erstattet, bisherige Ausführungen bleiben (append-only Logs); wartende Orders bleiben unberührt.
7. **Persistenz und Vektoren:** Der Markt ist Teil des Weltsnapshots (Schlüssel `exchange`, nur wenn je eine Order gestellt wurde, damit ältere Snapshots/Vektoren unverändert bleiben); Marktregeln sind per SHA-256 an Snapshot und Golden Vectors gebunden. Neue Golden-Szenarien: `market_orderbook` und `random_market_3`.

**Absicherung:** `tests/test_exchange.py` (28 Tests: Treuhand, Preis-Zeit-Priorität, Teil-/IOC-Ausführung, Selbstausführung, Band-Ränder, Limits, Verfall, Preisindex, Ausfall-Rollback, Invarianten, zufällige Märkte mit Erhaltung von Münzen/Ware und ohne gekreuztes Buch, Persistenz); Mutationstests über alle Prüf- und Rechenschritte.

**Offen / Grenzen**
- Der CEE-Referenzwert bleibt statisch (Regeltabelle). Echte Preisdynamik über die Zeit (Angebots-/Nachfrageschocks, Inflation, regionale Preise) braucht eine Regelversion, die den Referenzwert an den Index koppelt – bewusst noch nicht entschieden.
- Keine NPC-Marktteilnehmer/Marktmacher, keine regionalen Märkte, Transport/Logistik, Steuern, Auktionen, Aufträge/Kontrakte; kein Handel mit Firmenanteilen über das Buch (dafür bleibt das Vorkaufsverfahren, ADR-0012).
- Manipulationsschutz ist begrenzt auf Band, Selbstausführung und CEE-Wiederholungsabnahme; Absprachen mehrerer Accounts erkennt das System nicht.
- Firmen können noch nicht über den Markt handeln und haben keine Produktion (nächster Schritt: Firmenproduktion/Aufträge).
