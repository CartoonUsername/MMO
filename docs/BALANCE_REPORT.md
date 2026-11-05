# Balancing-Bericht (erzeugt von `python -m mmo_sim.balance write`)

Regeln: `sim_rules_v7.json`. **Alle Zahlen sind Platzhalter**; die Testspieler (`mmo_sim.balance`) sind vereinfachte Modelle, kein Ersatz für echte Spieltests.

Testspieler: **novice** schlägt nur leicht zu; **average** reagiert ab 6 Ticks Vorwarnung mit einfachem Ausweichen und verfehlt jeden dritten Versuch; **good** reagiert ab 3 Ticks, pariert Wuchtschläge und normale Angriffe, weicht Flächenschlägen perfekt aus, unterbricht Zauber/Heiler/Beschwörer und verfehlt jeden fünften Versuch; in Gruppen heilen und schützen die Spieler 2 und 4. Alle Spieler haben die Stufe der Gegnerfamilie, Gegnerleben wächst mit der Gruppengröße. Je Zelle 6 verschiedene Spawn-Punkte (andere Zusatzfähigkeiten), Tag 1.

Zellen: `Sieg ‰ / Dauer / Verlust` (Anteil verlorener Lebenspunkte der Überlebenden in ‰).

## Wolf (Stufe 5)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 1000 ‰ / 16 s / 219 | 1000 ‰ / 16 s / 219 | 1000 ‰ / 16 s / 219 |
| 2 | 1000 ‰ / 12 s / 82 | 1000 ‰ / 12 s / 82 | 1000 ‰ / 13 s / 82 |
| 3 | 1000 ‰ / 12 s / 36 | 1000 ‰ / 12 s / 36 | 1000 ‰ / 12 s / 36 |
| 4 | 1000 ‰ / 11 s / 27 | 1000 ‰ / 11 s / 27 | 1000 ‰ / 12 s / 27 |

## Wolfsrudel (2) (Stufe 5)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 1000 ‰ / 36 s / 640 | 1000 ‰ / 36 s / 640 | 1000 ‰ / 36 s / 450 |
| 2 | 1000 ‰ / 27 s / 230 | 1000 ‰ / 27 s / 184 | 1000 ‰ / 28 s / 111 |
| 3 | 1000 ‰ / 25 s / 144 | 1000 ‰ / 25 s / 124 | 1000 ‰ / 25 s / 100 |
| 4 | 1000 ‰ / 23 s / 87 | 1000 ‰ / 23 s / 87 | 1000 ‰ / 24 s / 76 |

## Höhlenbär (Stufe 12)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 833 ‰ / 41 s / 674 | 1000 ‰ / 45 s / 352 | 1000 ‰ / 47 s / 137 |
| 2 | 1000 ‰ / 33 s / 307 | 1000 ‰ / 33 s / 171 | 1000 ‰ / 35 s / 8 |
| 3 | 1000 ‰ / 30 s / 173 | 1000 ‰ / 31 s / 87 | 1000 ‰ / 30 s / 24 |
| 4 | 1000 ‰ / 29 s / 129 | 1000 ‰ / 29 s / 60 | 1000 ‰ / 29 s / 18 |

## Irrlicht + Wolf (Stufe 6)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 1000 ‰ / 28 s / 334 | 1000 ‰ / 28 s / 334 | 1000 ‰ / 28 s / 246 |
| 2 | 1000 ‰ / 20 s / 109 | 1000 ‰ / 20 s / 109 | 1000 ‰ / 21 s / 71 |
| 3 | 1000 ‰ / 18 s / 64 | 1000 ‰ / 18 s / 64 | 1000 ‰ / 19 s / 53 |
| 4 | 1000 ‰ / 18 s / 48 | 1000 ‰ / 18 s / 48 | 1000 ‰ / 18 s / 40 |

## Moorhexe (Stufe 9)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 1000 ‰ / 35 s / 212 | 1000 ‰ / 36 s / 149 | 1000 ‰ / 36 s / 64 |
| 2 | 1000 ‰ / 26 s / 64 | 1000 ‰ / 27 s / 38 | 1000 ‰ / 27 s / 31 |
| 3 | 1000 ‰ / 24 s / 40 | 1000 ‰ / 24 s / 21 | 1000 ‰ / 25 s / 21 |
| 4 | 1000 ‰ / 23 s / 30 | 1000 ‰ / 23 s / 15 | 1000 ‰ / 23 s / 15 |

## Moorhexe + Irrlicht (Stufe 9)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 1000 ‰ / 75 s / 544 | 1000 ‰ / 78 s / 431 | 1000 ‰ / 47 s / 107 |
| 2 | 1000 ‰ / 46 s / 164 | 1000 ‰ / 47 s / 115 | 1000 ‰ / 35 s / 38 |
| 3 | 1000 ‰ / 41 s / 92 | 1000 ‰ / 41 s / 67 | 1000 ‰ / 32 s / 21 |
| 4 | 1000 ‰ / 35 s / 56 | 1000 ‰ / 35 s / 41 | 1000 ‰ / 30 s / 16 |

## Schattenjäger (Stufe 11)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 1000 ‰ / 36 s / 385 | 1000 ‰ / 36 s / 350 | 1000 ‰ / 35 s / 304 |
| 2 | 1000 ‰ / 27 s / 140 | 1000 ‰ / 27 s / 132 | 1000 ‰ / 28 s / 132 |
| 3 | 1000 ‰ / 25 s / 93 | 1000 ‰ / 25 s / 87 | 1000 ‰ / 25 s / 82 |
| 4 | 1000 ‰ / 23 s / 59 | 1000 ‰ / 23 s / 54 | 1000 ‰ / 24 s / 54 |

## Steinwächter (Stufe 14)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 1000 ‰ / 64 s / 708 | 1000 ‰ / 66 s / 277 | 1000 ‰ / 68 s / 80 |
| 2 | 1000 ‰ / 46 s / 335 | 1000 ‰ / 48 s / 116 | 1000 ‰ / 49 s / 0 |
| 3 | 1000 ‰ / 37 s / 282 | 1000 ‰ / 39 s / 63 | 1000 ‰ / 40 s / 0 |
| 4 | 1000 ‰ / 35 s / 266 | 1000 ‰ / 37 s / 47 | 1000 ‰ / 38 s / 0 |

## Totem-Beschwörer (Stufe 12)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 1000 ‰ / 34 s / 287 | 1000 ‰ / 34 s / 287 | 1000 ‰ / 25 s / 33 |
| 2 | 1000 ‰ / 26 s / 87 | 1000 ‰ / 26 s / 87 | 1000 ‰ / 19 s / 16 |
| 3 | 1000 ‰ / 24 s / 47 | 1000 ‰ / 24 s / 47 | 1000 ‰ / 17 s / 11 |
| 4 | 1000 ‰ / 23 s / 35 | 1000 ‰ / 23 s / 35 | 1000 ‰ / 16 s / 0 |

## Alpha + 2 Wölfe (Stufe 8)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 0 ‰ / 30 s / 1000 | 0 ‰ / 32 s / 1000 | 500 ‰ / 64 s / 908 |
| 2 | 1000 ‰ / 59 s / 700 | 1000 ‰ / 70 s / 622 | 1000 ‰ / 58 s / 304 |
| 3 | 1000 ‰ / 54 s / 469 | 1000 ‰ / 56 s / 302 | 1000 ‰ / 50 s / 233 |
| 4 | 1000 ‰ / 49 s / 315 | 1000 ‰ / 49 s / 131 | 1000 ‰ / 47 s / 143 |

## Steinherz-Koloss (Boss) (Stufe 25)

| Gruppe | novice | average | good |
|---|---|---|---|
| 1 | 0 ‰ / 20 s / 1000 | 0 ‰ / 73 s / 1000 | 0 ‰ / 114 s / 1000 |
| 2 | 0 ‰ / 41 s / 1000 | 0 ‰ / 108 s / 1000 | 0 ‰ / 124 s / 1000 |
| 3 | 0 ‰ / 60 s / 1000 | 0 ‰ / 95 s / 1000 | 1000 ‰ / 114 s / 240 |
| 4 | 0 ‰ / 72 s / 1000 | 1000 ‰ / 144 s / 932 | 1000 ‰ / 106 s / 240 |


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
