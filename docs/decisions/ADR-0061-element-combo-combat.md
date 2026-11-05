# ADR-0061: Kombinationszauber im Kampf (AP 22)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §22–26, §74)
- Wer zwei Elemente geprägt hat, bekommt im Kampf den **Paarzauber** (`combo_<a>_<b>`, alphabetisch); mit drei Prägungen (Endgame, Stufe 40) zusätzlich den **Dreierzauber** (`combo_<a>_<b>_<c>`). Entspricht `mmo_cee.combos.unlocked`: jedes Paar frei wählbar, Dreier nur mit drei Prägungen.
- Regeln: `sim_rules_v11.json` (= v10 + 36 Paar- und 84 Dreierzauber mit `elements` statt `element`), `game_rules_v14.json` (Standard; `combo_abilities`). v10/v13 und alle Golden Vectors bleiben. Keine CEE-Änderung, keine Weltmigration.
- Wirkung: Sofortschaden + Schaden über Zeit wie ein Einzelzauber, aber stärker (Paar 260/30, Dreier 380/45 gegenüber 180/20), dafür teurer (Ausdauer 45/60 statt 30) und längere Abklingzeit (120/160 statt 80). Elementfaktor gegen den Gegner = **bester** Faktor der beteiligten Elemente (Mischung ist nie schlechter als das beste Einzelelement).
- Kombinationszauber haben **keine Wechselzeit** (`switch_ticks` gilt nur für Einzelzauber, setzt sie auch nicht); das Gegengewicht sind Kosten und Abklingzeit.
- Validierung: `elements` = 2 oder 3 verschiedene, alphabetisch sortierte, bekannte Elemente, nicht zusammen mit `element`.
- Spielschicht: `game.kit` enthält die freigeschalteten Kombinationen, `game.elements` liefert zusätzlich `combos` (Befehl → Elemente).

## Nicht entschieden / offen
- Klassen- und Bereichswirkung der Kombination (Kontrolle, Schutz, Beschwörung … aus `combos.describe`); heute reiner Schaden mit Element-Bonus.
- Eigene Werte je Kombination; alle Paare/Dreier teilen eine Vorlage (Platzhalter).
- Darstellung im Client (Kit-Leiste zeigt sie datengetrieben, aber im Browser/Unity nicht geprüft); viele Kombinationen brauchen später eine Auswahl-UI.
