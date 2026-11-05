# Balancing: Marktplatz-Rabatt (AP 29/30)

Rechnung mit den Platzhalterwerten (Börsengebühr 20 ‰ = 2 %, `market_square` Stufen 0/100/200 ‰ Rabatt). Nur Münzkosten; die Warenkosten (40 Holz bzw. 40 Balken) kommen obendrauf. Das Projekt ist ein Gemeinschaftsprojekt, die Kosten teilen sich die Beitragenden.

| Stufe | Münzkosten | Rabatt | gesparte Gebühr | Break-even (nur Münzen) |
|---|---|---|---|---|
| 1 | 800 | 100 ‰ | 0,2 % des Verkaufsumsatzes | 400 000 Münzen Umsatz |
| 2 | +2 000 | 200 ‰ | 0,4 % des Verkaufsumsatzes | 700 000 Münzen Umsatz (kumuliert 2 800) |

Zum Vergleich: Eine Order über 10 Eisenbarren bei Referenzpreis 20 sind 200 Münzen; höchstens 10 Orders sind gleichzeitig offen.

## Einschätzung (Vorschlag, nicht gemessen)
- Wirkung ist **zu schwach**: Auch ein sehr aktiver Händler spart in Wochen nur wenige Münzen. Der Marktplatz wäre ein reines Prestigeprojekt.
- Es fehlen Spieldaten zum echten Handelsumsatz; diese Zahlen sind Schätzungen aus den Regeln, keine Bot-Messung.
- Optionen (neue Regelversion `settlement_rules_v2` nötig, da neue Regelwirkung):
  1. Rabatt 0 / 250 / 500 ‰ (Gebühr 2 % → 1,5 % → 1 %).
  2. Kosten senken (z. B. 400 / 1 000 Münzen).
  3. Stattdessen mehr offene Orders (`max_open_orders` +2 je Stufe), was für Händler spürbarer ist.
- Empfehlung: Option 1 plus Messung per Bot, bevor weiter gedreht wird. Gebühren bleiben eine Münzsenke, daher kein Risiko für die Wirtschaft.

Status: Option 1 umgesetzt als settlement_rules_v2 (ADR-0067); keine Bot-Messung.
