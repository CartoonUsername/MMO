# ADR-0070: Aktiver Zweig gibt Zusatz-Berufserfahrung (AP 36)

Status: angenommen (Vorschlag, Claude, autorisiert; Platzhalterwert)

## Entscheidung
- `rules_v10.professions.specialization.focus_xp_permille` = 250: Wer ein Rezept herstellt, das zum aktiven Zweig des Berufs gehört, erhält 25 % mehr Berufserfahrung für diese Herstellung.
- Die Grundmenge bleibt die gedeckelte Erfahrung aus der Herstellung (Anti-Farming unverändert); der Bonus ist proportional und schafft keine neue Quelle. Keine Wirkung auf Güte, Menge oder Münzen.
- Umsetzung: `mmo_cee.branches.focus_xp_permille`, angewendet in `CraftingService.craft`. Regeln ohne Zweigwahl (v9 und älter) unverändert.
- `rules_v10` war noch nicht ausgeliefert, daher wurde sie erweitert und der Golden Vector `profession_specialization` neu erzeugt (nur dieser; alle anderen unverändert).

## Offen
- Balancing des Werts; weitere Zweigwirkungen (Güte, Techniken); Anzeige im Client.
