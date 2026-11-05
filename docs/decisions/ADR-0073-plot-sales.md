# ADR-0073: Grundstückshandel zwischen Spielern (AP 43)

Status: angenommen (Vorschlag, Claude, autorisiert; Platzhalterwerte)

## Entscheidung
- Befehle `plot.sell` (Besitzer bietet einem bestimmten Käufer zum Preis an), `plot.cancel_sale`, `plot.accept_sale` (nur der genannte Käufer). Ein Angebot je Grundstück.
- Regeln in `settlement_rules_v2` (noch nicht ausgeliefert): `sale_days` 7 (Angebot verfällt danach), `sale_fee_permille` 50 (5 % vom Preis verschwinden als Münzsenke, der Verkäufer erhält 95 %), `max_sale_price` 1 000 000. Ohne diese Schlüssel (v1) gibt es keinen Grundstückshandel.
- Bedingungen: Verkäufer besitzt das Grundstück, keine offene Steuer, Lager leer (Waren werden nicht mitverkauft), Käufer existiert, ist nicht der Verkäufer und hat noch Platz im Grundstückslimit und genug Münzen. Das Gebäude geht mit. Zahlung und Besitzwechsel sind atomar.
- Aufgeben/Verfall des Grundstücks löscht das Angebot. Zustand `sales` wird nur gespeichert, wenn Angebote existieren (unveränderte Welten behalten ihren Zustands-Hash); `check()` prüft die Konsistenz.
- Ohne Preisband: Käufer und Verkäufer einigen sich frei. Wash-Trading-Risiko (Gebühr ist die Bremse) nicht gesondert untersucht.

## Offen
- Öffentlicher Grundstücksmarkt statt Einzelangebot; Chronik/Benachrichtigung bei Verkauf; Client-Fenster.

## Ergänzung AP 56–58: offene Angebote
- `plot.sell` ohne `buyer` erstellt ein **offenes Angebot**: jeder außer dem Verkäufer darf es annehmen (der Erste gewinnt, danach ist es weg). Die Abfrage `query.settlements` führt fremde offene Angebote in `sales_open` (höchstens 50). Bei offenen Angeboten gibt es keine Benachrichtigung an einen Käufer; der Verkäufer erfährt vom Verkauf (`plot.sold`) und vom Verfall (`plot.sale_expired`).
- Gebühr, Frist und Bedingungen unverändert. Ein Kaufmarkt mit Suche/Sortierung bleibt offen.
