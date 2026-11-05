# Balancing der Elementzauber und Kombinationen

(Handgeschrieben; `BALANCE_REPORT.md` ist generiert und wird von einem Test geprüft, deshalb steht diese Messung hier.)

## Elementzauber und Kombinationen (AP 22–26, sim_rules_v15; Messung 2026-11-05)

Methode: ein Spieler (Stufe 1) ohne Abwehr wirkt zu jedem zweiten Tick alle verfügbaren Zauber (nicht bereite werden von der Simulation ignoriert), gegen einen Gegner; gemessen werden Zeit bis zum Sieg und verbleibende Spieler-Lebenspunkte. Aussagekraft: Richtwert für das Verhältnis, kein Spielerverhalten.

| Gegner | 1 Element | 2 Elemente, nur Einzelzauber | 2 Elemente + Paarzauber | 3 Elemente, nur Einzelzauber | 3 Elemente + Paar/Dreier |
|---|---|---|---|---|---|
| Bär | Niederlage (478 Ticks) | Sieg 271 / 420 LP | Sieg 175 / 780 LP | Sieg 271 / 420 LP | Sieg 121 / 900 LP |
| Steinkoloss | Niederlage (373) | Sieg 241 / 420 LP | Sieg 175 / 620 LP | Sieg 241 / 420 LP | Sieg 121 / 820 LP |
| Alphawolf | Niederlage (638) | Sieg 441 / 442 LP | Sieg 315 / 717 LP | Sieg 401 / 512 LP | Sieg 231 / 867 LP |

Befunde:
- Kombinationen verkürzen den Kampf mit zwei Prägungen um ca. 30–35 %, mit drei um ca. 55 % (gegenüber nur Einzelzaubern). Der Schaden je Tick und je Ausdauer eines einzelnen Paar-/Dreierzaubers liegt dicht an dem eines Einzelzaubers (3,2 / 3,5 gegenüber 3,25 pro Tick); der Gewinn kommt aus den zusätzlichen Abklingzeit-Plätzen plus Zusatzwirkung.
- Das dritte Element bringt ohne Kombinationen fast nichts (nur ein weiterer Einzelzauber), mit Dreierzauber sehr viel. Das passt zu „Endgame“ (Stufe 40), ist aber die stärkste Stellschraube: **Vorschlag, noch nicht umgesetzt:** Dreier-Schaden 380 → 330 und Abklingzeit 160 → 180, falls echte Spieltests das als zu stark bestätigen. Das wäre eine neue Regelversion.
- Nur ein Element reicht gegen diese Gegner ohne Abwehr nicht zum Sieg; die Prägung eines zweiten Elements ist also ein spürbarer Schritt.
