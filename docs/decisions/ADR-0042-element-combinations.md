# ADR-0042: Elementkombinationen – Katalog, klassenabhängige Umsetzung, Grenzen (AP 4a)

**Status:** angenommen (Katalog und Ableitung; Kampfwirkung folgt in AP 4b)

## Kontext
Blueprint §22–26, §74: neun Elemente, freie ungeordnete Kombinationen (36 Paare, 84 Dreier, Dreier nur als seltene Endgame-Entwicklung), dieselbe Kombination wirkt je Klasse anders, Wirkungen nicht nur Schaden, mit Grenzen und Gegenspiel; Elementmanagement im Kampf ist **offen** (§26) und soll nur flexible Loadouts vorbereiten. Die CEE kannte bereits Affinität, Prägung (max. 2 regulär + 1 ab Stufe 40) und `combination_key`, aber weder Katalog noch Klassenunterschiede.

## Entscheidung
- Neue, von den CEE-Regeln getrennte Datei `mmo_cee/data/element_rules_v1.json` (Platzhalter, keine Migration, keine Änderung an Golden Vectors): je Element zwei **Wirkbereiche** (Entladung, Zerrung, Kontrolle, Bewegung, Schutz, Beistand, Beschwörung, Umgebung), je Bereich ein **Gegenspiel**, je Klasse und Bereich eine **Umsetzung** (3 × 8 authored Sätze), Grenzen (`max_same_domain_per_combination`, `triple_requires_attuned`).
- Modul `mmo_cee/combos.py`: `all_combinations` (36/84), `combo_key` (ungeordnet, keine Wiederholung), `describe` (vereinte Wirkbereiche, gleiche Bereiche verstärken nur bis zur Grenze), `catalog`, `unlocked` (aus den geprägten Elementen: jedes Paar frei wählbar, Dreier nur mit drei Prägungen). `CharacterService.element_combinations`.
- Gateway: `query.element_catalog` (ohne Figur) und `query.character → combinations`.
- Browserclient: Fenster „Elemente“ (zwei oder drei Elemente wählen → Wirkbereiche, Gegenspiel, Umsetzung je Klasse) und Abschnitt „Deine Kombinationen“ im Charakter-Fenster.
- Kein Element-Wechselmechanismus festgelegt (§26 offen).

## Folgen
- Alle Texte sind Entwürfe nach Blueprint §24, keine Mechanikwerte. Kombinationen sind derzeit **beschreibend**: im Kampf wirken nur die vorhandenen Fähigkeiten (z. B. Glutstoß). Die Kampfwirkung (Fähigkeiten je Wirkbereich, Elementarschaden/Widerstände, Interaktionen) ist AP 4b und braucht neue Simulationsregeln.
- Besondere Varianten über Geheimquests/Entdeckungen (§25) sind im Datenmodell noch nicht vorgesehen; eigener Schritt.
