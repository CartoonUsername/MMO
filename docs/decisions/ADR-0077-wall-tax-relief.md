# ADR-0077: Mauer senkt die Grundsteuer (AP 64/65)

Status: angenommen (**Vorschlag, Claude, autorisiert**; Platzhalter, ausdrücklich eine Notlösung)

## Entscheidung
- Das Siedlungsprojekt `wall` (Wirkungsschlüssel `raid_defence_permille`, 0/150/350 ‰) hatte keine Wirkung, weil es keine Angriffsmechanik auf Orte gibt. Statt eine zu erfinden, senkt die Mauer in `settlement_rules_v2` (`wall_tax_relief: true`) die **tägliche Grundsteuer** aller Grundstücke im Ort um diesen Promillesatz (Wachkosten entfallen). Abgerundet, mindestens die ganzzahlige Steuer minus Rabatt.
- `SettlementService.tax_of`; Abrechnung (`advance`) und Anzeige (`plot_view.tax`) nutzen sie. Regeln ohne den Schlüssel (v1) unverändert. Der Browser nennt die Wirkung „Mauer: Steuerrabatt“.
- Die Steuer ist eine Münzsenke; weniger Steuer = weniger Senke, die Beträge sind klein (5 und 12 Münzen am Tag, Rabatt höchstens 35 %).

## Offen
- Sobald es Angriffe/Weltereignisse auf Orte gibt, kann die Mauer deren Schutz übernehmen und der Schlüssel wieder seinen Namen verdienen.
