# ADR-0072: Hafen erhöht die Zahl offener Marktorders (AP 41)

Status: angenommen (Vorschlag, Claude, autorisiert; Platzhalterwert)

## Entscheidung
- Das Siedlungsprojekt `harbor` (Handelsreichweite 0/1/2) wirkt: jede Stufe erlaubt `orders_per_reach` = 3 zusätzliche offene Orders (Standard 10 aus `market_rules_v1`). Es gilt der beste Wert unter den offenen Orten, in denen die Figur ein Grundstück besitzt.
- `settlement_rules_v2` (noch nicht ausgeliefert) bekommt dafür `orders_per_reach`; `market_rules_v1` bleibt unverändert, daher keine Migration der Marktregeln. `SettlementService.order_bonus`, `Exchange.order_bonus` (Standard 0), von `World` verdrahtet; `query.settlements` liefert `order_bonus`.
- Keine neue Geldquelle: mehr Orders binden mehr Hinterlegtes.

## Offen
- Die Mauer (`raid_defence_permille`) hat weiterhin keine Wirkung (keine Angriffsmechanik auf Orte vorhanden, bewusst nicht erfunden).
