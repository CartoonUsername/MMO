# ADR-0066: Marktplatz senkt die Börsengebühr (AP 29)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint Siedlungen / Markt)
- Das Siedlungsprojekt `market_square` (settlement_rules_v1, Stufen 0/100/200 Promille) wirkt jetzt: Es senkt die Börsengebühr des **Verkäufers** um den besten Wert unter den offenen Orten, in denen die Figur ein Grundstück besitzt.
- Umsetzung: `SettlementService.fee_discount_permille(char)`, `Exchange.fee_discount` (Standard 0), von `World` verdrahtet. Der Rabatt wird auf die Gebühr (`fee_permille`) angewendet, auf 0–1000 Promille begrenzt.
- Die Gebühr bleibt eine Münzsenke (SINK); es entsteht keine neue Geldquelle. Käufer und Figuren ohne Grundstück zahlen unverändert.
- Ohne Marktplatz ist das Verhalten identisch zu vorher, daher bleiben alle Golden Vectors gültig.

## Offen
- Balancing der Stufen (100/200 ‰); Anzeige des Rabatts in den Clients; Deployment auf den VPS.
