# COMBAT DESIGN – Kampf, Kampfechos, Resonanz

**Dokument E der Design-Reihe** · Stand 2026-11-05 · Labels: **[BESTÄTIGT] [DESIGNRICHTUNG] [VORSCHLAG] [OFFEN] [ZURÜCKGESTELLT]**.
Reines Design: keine Formeln, keine Werte, keine Änderung am Server. Zahlen unten sind **Beispiele zur Veranschaulichung** und ausdrücklich nicht verbindlich.

---

## 1. Kurzfassung

Kampf ist **Third-Person-Action** [BESTÄTIGT]: Der Spieler bewegt, zielt, weicht aus und trifft selbst. Er gewinnt durch **Lesen** (Telegraphen, Positionen), **Timing** und **Entscheidungen** (Fähigkeiten, Elemente, Echo), nicht durch Zahlenvergleich im Hintergrund. Die systemische Tiefe ist groß, die Oberfläche bleibt lesbar [BESTÄTIGT §29].

Drei Kampfsäulen:
1. **Bewegung ist Verteidigung** (Ausweichen, Positionieren, klassenspezifische Mobilität).
2. **Fähigkeiten sind Aussagen** (jede Fähigkeit hat Form, Zeitfenster, Preis).
3. **Das Kampfecho ist Handschrift** (wie du kämpfst, wächst sichtbar mit der Resonanz).

---

## 2. Kampfgefühl [BESTÄTIGT §27, §28]

| Eigenschaft | Gestaltung |
|---|---|
| Perspektive | Third-Person hinter dem Charakter, frei drehbare Kamera, Schulterblick-Option, Zielerfassung (weich) |
| Steuerung | direkte Steuerung; kein Auto-Kampf; Springen/Ausweichen sind echte Mechaniken |
| Tempo | Mischung: schnelle Grundangriffe und Kombos **und** schwere, aufgeladene, taktische Aktionen |
| Richtung | richtungsabhängige Angriffe (Seiten, Rücken, Höhe) [BESTÄTIGT §28]; Server kennt bereits sechs Kampfrichtungen |
| Aktionen | Kombokette, aufgeladener Schlag, gehaltene/kanalisierte Fähigkeit, Ausweichen, Konter, Block/Parade je Klasse |
| Rückmeldung | Treffer-Stopp (kurzes Einfrieren), Kamerawackeln (regelbar), Klang, Trefferfunken, Gegnerreaktion (Taumeln, Rückstoß) |

### 2.1 Was der Spieler im Kampf fühlt
- **Wucht:** Treffer haben Gewicht (Krieger), **Fluss:** Zauber gehen ineinander über (Wandler), **Präzision:** der perfekte Schuss sitzt (Schütze).
- **Kontrolle:** Tode fühlen sich fair an („ich habe den roten Kreis gesehen und zu spät reagiert“).
- **Entdeckung:** Zwischen Fähigkeiten, Elementen und Umgebung entstehen überraschende, nachvollziehbare Wechselwirkungen [BESTÄTIGT §29].

---

## 3. Lesbarkeit: Die Sprache des Kampfes [DESIGNRICHTUNG]

Ohne feste Sprache ist ein Kampf voller Effekte unlesbar. Deshalb gilt:

| Signal | Bedeutung | Ausführung |
|---|---|---|
| **Roter/orangener Bodenkreis, Kegel, Linie** | Gefahrenfläche des Gegners | Füllanimation = Restzeit; Form sagt Art des Angriffs (Tafel 1 zeigt dies bereits) |
| **Gelbe Kante/Warnblitz** | Gegner holt zu unblockbarem/besonderem Schlag aus | zusätzlicher Ton |
| **Blau-türkise Zonen** | Verbündeten-Bereich (Heilung, Schild, Buff) | niemals rot |
| **Violette Kerne** | Schwachstelle/Unterbrechbar | bei Bossen als Leuchtpunkt |
| **Elementfarbe** | Herkunft des Zaubers | nie allein, immer mit Form/Bewegung gekoppelt |
| **Zahlen** | Schaden/Heilung | optional, in Größe und Menge regelbar |

Regeln:
1. **Gefahr vor Schönheit.** Die Gefahrenebene wird nie von Effekten verdeckt.
2. **Eigene Effekte kräftiger als fremde**, besonders in Gruppen.
3. **Gegner haben klare Anzeichen** (Ausholen, Aufrichten, Schnauben), bevor Gefahr kommt (Telegraphzeit).
4. **Farbfehlsichtigkeit:** Warnungen unterscheiden sich zusätzlich durch Form und Bewegung, Ton oder Symbol.

---

## 4. Klassen im Kampf [BESTÄTIGT: klassenspezifische Bewegung und Fähigkeiten]

| | Krieger | Schamane/Alchemist | Bogenschütze |
|---|---|---|---|
| Spielgefühl | Standhalten, Wucht | Mischen, Wandeln, Unterstützen | Distanz, Tempo, Präzision |
| Ausweichen | Ansturm/Schulterstoß, Block | gleitender Schritt, kurzer Blink | Rolle, Sprint, Rutschen, Wandsprung |
| Defensiv | Block, Parade, Haltung | Schilde, Heilwellen, Verwandlungen | Abstand, Fallen, Täuschung |
| Offensiv | Kombos, Schmetterschläge, Flächenwellen | Zauberketten, Totems, Tränke | Schüsse, Salven, Spurpfeile |
| Gruppenrolle | Frontlinie, Kontrolle | Unterstützer/Wandler | Fernkampf, Aufklärer |
| Schwäche (Mechanik, nicht Malus) | langsam, auf Raum angewiesen | verletzlich, Ressourcenbedarf | wenig Panzerung, Positionspflicht |

Waffen und Rüstung ändern tatsächliche Optionen [BESTÄTIGT §28/§31]: schwere Rüstung = Block und Standfestigkeit, leichte = Mobilität; Zweihand = Wucht und Reichweite, Einhand + Schild = Parade, Dolch = Rückenangriffe usw. [VORSCHLAG].

---

## 5. Fähigkeitsdesign [DESIGNRICHTUNG]

Jede Fähigkeit wird in sechs Fragen beschrieben (Vorlage für die späteren Fähigkeitsblätter):

1. Wie sieht sie aus (Form, Dauer, Klang)?
2. Wie wird sie ausgelöst (Taste, Halten, Ziel, Richtung)?
3. Was sagt sie dem Gegner/den Mitspielern (Telegraph, Signal)?
4. Was kostet sie (Zeit, Ausdauer, Fokus, Abkühlung)?
5. Womit wechselwirkt sie (Element, Umgebung, Zustand)?
6. Wie ändert sich ihr Ausdruck mit Echo, Element, Meisterschaft?

**Leiste:** Wenige aktive Fähigkeiten gleichzeitig (Zielwert z. B. 8–10, [OFFEN]), dazu kontextuelle Aktionen. Die Fähigkeitsleiste unten ist klassisch lesbar (Tafel 1) und modern gestaltet (siehe UI_UX_DESIGN).

### 5.1 Ressourcen [VORSCHLAG]
- **Ausdauer** für Ausweichen/Sprint/Block (zeitkritisch).
- **Fokus** für Fähigkeiten (baut sich aus Treffern/Zeit auf).
- **Haltung** (Gleichgewicht) als zweite Lebensleiste von Gegnern: Bei gebrochener Haltung sind sie verwundbar (Betäubung, Taumeln) [Blueprint §29 nennt Haltung, Gleichgewicht, Unterbrechungen].

### 5.2 Wechselwirkungen (Tiefe ohne Zufall) [BESTÄTIGT §29]
Ergebnisse sind **reproduzierbar und durch Können beeinflussbar**. Kein „Würfelglück“ entscheidet. Beispiele für regelbasierte Wechselwirkungen:
- Nasse Gegner leiten Elektro weiter; Eis auf Wasser erzeugt Rutschfläche; Feuer brennt Gras ab (Geländeveränderung); Wind trägt Gift und Funken; Licht blendet Schattenwesen; Erde blockiert Linien.
- Angriffswinkel: Rückenangriffe, Flankenbonus bei Position; Schildseiten.
- Gruppeninteraktion: Zustand durch A (nass, brennend, verlangsamt) wird von B ausgenutzt. Dies fördert Zusammenspiel.

---

## 6. Elemente im Kampf

Siehe CHARACTER_DESIGN §4 für Aussehen und Kombinationen. Kampfregeln [DESIGNRICHTUNG]:

1. **Zwei Elemente normal, drei als seltene Endgame-Entwicklung** [BESTÄTIGT].
2. **Klassenabhängige Wirkung** [BESTÄTIGT §24]: Schatten + Wind ist beim Krieger ein anderes Kampfverhalten als beim Schamanen oder Schützen (Beispiel Krieger: Schattenschritt-Ansturm mit Windschnitt; Schamane: Dämmergeist, der Gegner verwirrt; Schütze: Pfeile, die kurz durch Schatten teleportieren).
3. **Rollen der Elemente (Tendenz, keine Festlegung) [VORSCHLAG]:** Feuer = Druck/Schaden über Zeit; Wasser = Fluss/Regeneration/Kontrolle; Erde = Stabilität/Barriere; Wind = Tempo/Verschiebung; Elektro = Ketten/Überlastung; Eis = Verlangsamung/Einfrieren; Licht = Schutz/Reinigung/Blendung; Schatten = Täuschung/Teleport/Begleiter; Natur = Wurzeln/Gift/Heilung.
4. **Kein Element hat feste Gegen-Element-Zwangskette** (kein Schere-Stein-Papier); Resistenzen entstehen aus Kreaturentyp und Kontext.
5. **Stapelgrenzen:** Freie Kombination bedeutet nicht unendliches Stapeln [BESTÄTIGT §23].

---

## 7. Kampfechos [BESTÄTIGT: Arbeitsbegriff „Kampfecho“, Hybridsystem; DESIGNRICHTUNG vom Nutzer bestätigt]

### 7.1 Was ein Kampfecho ist (Spielerperspektive)
Ein Kampfecho ist ein **gefundener, geschmiedeter oder erkämpfter Kristall einer Kampftradition**. Man trägt ihn (z. B. in einem Fassungsring an Waffe oder Brust). Er verändert, **wie** man kämpft: Fähigkeiten, Animationen, Bewegungen, Manifestationen, Spielstil [BESTÄTIGT §17]. Er ist **kein 2D-Kärtchen und keine reine Verkleidung**.

| Frage | Antwort |
|---|---|
| Was sieht der Spieler? | Einen Kristall mit Rune und Ringen; im Kampf sichtbare Manifestation (Geist, Aura, Waffenform). |
| Was tut er? | Findet, aktiviert, verbessert (Resonanz), kombiniert (Haupttradition + ausgewählte Elemente anderer). |
| Wie fühlt es sich an? | Wie Zugang zu einer fremden Kampfkunst, die zu einem passt. |
| Wie entwickelt er sich? | Resonanz +0–30; Meisterschaft; Wesensprägung. |
| Wen beeinflusst er? | Gruppen (Rollen), Markt (handelbar), Prestige. |
| Langfristiger Antrieb? | Sammeln, Verfeinern, Handeln, „mein“ Echo ausbilden. |

### 7.2 Hybridsystem [BESTÄTIGT §18]
- **Haupttradition** bestimmt den Grundstil (Kombos, Bewegungsmuster, Hauptmanifestation).
- Aus **anderen freigeschalteten Traditionen** lassen sich **ausgewählte Fähigkeiten und Passive** integrieren (Slots begrenzt).
- Klassenspezifisch, selten klassenübergreifend. Wenn eine Klasse ein Echo nicht nutzen kann, gibt es **gleichwertig interessante Alternativen** [BESTÄTIGT].

### 7.3 Echo-Typen (Arbeitstitel) [VORSCHLAG]
Jedes Echo hat eine **Leitform** (Silhouette seiner Manifestation), damit man im Gruppenkampf erkennt, wer welches trägt.

| Tradition (Arbeitstitel) | Leitform | Klassenfeld | Gefühl |
|---|---|---|---|
| Wolfsrudel | Geisterwölfe, Sprung und Flankieren | Krieger, Schütze | Jagd, Rudeltaktik |
| Bergwall | Schildkristall, Steinwellen | Krieger | Standhaft |
| Sturmjäger | Bogen aus Blitz, Windbahn | Schütze | Tempo |
| Quellmutter | Wasserbänder, Heilkreise | Schamane | Fluss, Heilung |
| Aschenschmied | Hammerfunken, Glutklingen | Krieger, Alchemist | Wucht, Handwerk im Kampf |
| Dämmerseele | Doppelgänger, Schleier | Schütze, Schamane | Täuschung |
| Wurzelhüter | Ranken, Sporen, Begleitpflanzen | Schamane | Kontrolle, Zermürbung |
| Frostchor | Eisharfen, Kristallechos | Schamane, Krieger | Verlangsamung |
| Glaswandler (klassenübergreifend, selten) | zerbrechliche Spiegelgestalten | alle | Risiko/Belohnung |

### 7.4 Handelbarkeit [BESTÄTIGT §20]
1. Unaktivierte Echos sind handelbar.
2. Nach Aktivierung sind sie zunächst charaktergebunden.
3. Ein besonderer Gegenstand (Arbeitsname: **Resonanzsiegel**) macht sie wieder handelbar.
4. Beim Verkauf bleiben Resonanzstand und visuelle Stufe erhalten.
5. Die persönliche **Meisterschaft des Verkäufers geht nicht über**.
6. Einzigartige/serverexklusive Echos dürfen nicht vervielfältigt werden.
7. Resonanzsiegel nur über anspruchsvolle Inhalte oder seltene Herstellung, nicht als Echtgeld-Boost [BESTÄTIGT: kein Pay-to-win].

Designfolge: Ein Echo trägt eine **Biografie** (wer hat es gefunden, wie viele Kämpfe, welche Bosse, Vorbesitzer-Wappen). Handel überträgt diese Geschichte, nicht die Meisterschaft.

---

## 8. Resonanz +0 bis +30 [BESTÄTIGT §19]

### 8.1 Kernregeln
- Upgrade bis **+30**; mit steigender Stufe sinkt die Erfolgswahrscheinlichkeit.
- Fehlschlag verliert Material/Kosten; auf höheren Stufen kann die Stufe sinken; **Schutzgegenstände** verhindern Stufenverlust; **Pechschutz** steigert schrittweise die Chance nach Fehlschlägen; ein einzelner Fehlschlag **zerstört das Echo nie** [BESTÄTIGT §19.1].
- Echtgeld-Lotterie ist verboten (CLAUDE.md).
- Genaue Wahrscheinlichkeiten und Kosten sind [OFFEN].

### 8.2 Visuelle Entwicklung: **kein bloßes größeres Leuchten** [BESTÄTIGT §19.2: spürbare, sichtbare Entwicklung; DESIGNRICHTUNG zur Umsetzung]

Prinzip: Jede Meilenstein-Stufe verändert eine **andere Ebene**, damit Fortschritt wie Entwicklung wirkt und nicht wie Aufblasen.

Ebenen: **(A) Kristallkörper** · **(B) Ringe** · **(C) Manifestation (Gestalt)** · **(D) Waffen-/Körpereffekt** · **(E) Animation/Bewegung** · **(F) Umwelt-/Soundspur** · **(G) Fähigkeitszusatz**.

| Bereich | Name (Blueprint) | Kernänderung (neu in dieser Stufe) | Ebene | Beispiel Tradition „Wolfsrudel“ |
|---|---|---|---|---|
| **+0 bis +4** | Erweckung | Echo ist **eingestellt**: schwache Kontur, ein Ring | A, B | blasse Wolfsform bei jedem dritten Treffer |
| **+5 bis +9** | Manifestation | Gestalt wird **dauerhaft** sichtbar; zweiter Ring; erste Ausprägung (Variante) | B, C | Geisterwolf begleitet, folgt Wegen |
| **+10 bis +14** | Erweiterte Form | **Animation ändert sich**: Kombos erhalten neue Zwischenschritte; Waffe bekommt Material-Ausprägung | D, E | Wolf springt in Kombos mit, Krallenspuren auf der Klinge |
| **+15 bis +19** | Erhabene Form | **Aufwendigere Gestalt** (Details, Rüstung der Manifestation), besondere Fähigkeitsendungen | C, G | Wolf trägt Kristallrüstung, Heulen ruft Rudel auf Zeit |
| **+20 bis +24** | Legendäre Form | **Umwelt reagiert**: Bodenspuren, Lichtveränderung, eigene Soundspur; Spezialanimation | F, E | Rudelspuren im Schnee, dunklere Dämmerung beim Auftritt |
| **+25 bis +30** | Mythische Form | **Struktur verändert**: zweite Manifestation, Charakter-Aura passt sich an, einzigartige Signaturfähigkeit | alle | Wolfskönig erscheint kurz, Charakter bekommt Wolfsprägung (Wesensprägung) |

Innerhalb eines Bereichs wächst die Stufe über **Feinzeichen** (zusätzlicher Teilring, Rune füllt sich, kleine Details), nicht über neue Modelle. So sieht man +7 und +8 unterschiedlich, ohne dass für jede der 30 Stufen neue Modelle nötig sind [BESTÄTIGT §19.2: modulare Assets, Materialparameter, Animationslayer, Effektvarianten].

### 8.3 Grenzen der Optik [BESTÄTIGT §19.2]
1. Größere Effekte bedeuten **keine** größere Trefferfläche und keinen unverhältnismäßigen Schaden.
2. Effekte unterliegen dem Lesbarkeits- und Leistungsbudget (Telegraph-Ebene zuerst, siehe VISUAL_DIRECTION 3.4).
3. **Regelbare Effektdichte** (Spieler wählt) und **Gruppenreduktion** fremder Effekte.

### 8.4 Spielerwirkung
Mit Resonanz verändern sich nicht nur Optik, sondern **Fähigkeitsausprägung**: zusätzliche Varianten, neue Endungen, Synergien [Bildtafel: „Schaden, Effekte, Synergien, Individuelle Entwicklung“]. Wie viel davon Zahlen und wie viel neue Möglichkeiten sind, ist [OFFEN]; Leitlinie: **mehr Optionen statt nur mehr Schaden**.

### 8.5 Der Upgrade-Moment [DESIGNRICHTUNG]
Ein Upgrade ist ein Ereignis: Amboss/Resonanzaltar in Handwerksviertel oder Gildenhalle, Kristall in Fassung, Ringe laufen, Bild und Ton bauen Spannung auf. **Erfolg** zeigt klare Entladung (Ring rastet ein), **Fehlschlag** zeigt Rissbild (aber kein Zerstören), **Pechschutz** ist als Füllanzeige sichtbar. Wiederholte Spielerlebnisse werden überspringbar, damit viele Versuche nicht nerven. Verbot: Kasinomuster (Rotationsanimationen, die Sucht erzeugen sollen).

---

## 9. Meisterschaft [BESTÄTIGT §21]

Meisterschaft ist **persönliche Beherrschung** einer Tradition und von Resonanz getrennt:
- Schaltet Varianten, Timingoptionen, Kombos, individuelle Ausführungen frei.
- Wird durch **Üben und Leistung** gewonnen (Treffgenauigkeit, perfekte Ausweichmanöver, Bossfreischaltungen, Herausforderungen).
- Ist **nicht handelbar** und geht beim Verkauf nicht über.
- Sichtbar als **persönliche Handschrift**: Der Charakter führt Fähigkeiten leicht anders aus als ein Anfänger mit demselben Echo (Animationsvarianten, Zierlinien).

Dadurch kaufen Spieler kein Können: Ein hochresonantes Echo ohne Meisterschaft bleibt sichtbar „unvertraut“.

---

## 10. Gruppenkampf, Bosse, Dungeons

Siehe CREATURE_AND_BOSS_DESIGN für Bosse. Grundregeln [DESIGNRICHTUNG]:
- **Rollen ohne Zwang:** Frontlinie, Unterstützung, Distanz; keine feste Heiler-Tank-Dreiheit als einzig mögliche Form.
- **Positionspflicht und Kommunikation**: Telegraphen für Gruppen (Marken, Linien), Pingsystem.
- **Wiederbeleben und Retten** als Spielerfantasie: Einsatz von Ausweich-/Heilmanövern, die andere retten.
- **Skalierte Lesbarkeit:** Bei Gruppen wird Effektdichte automatisch reduziert.

---

## 11. PvE und PvP [BESTÄTIGT §30]

- Ein Charakter, eine Progression für beide [BESTÄTIGT].
- Kontextabhängige Anpassung statt getrennter Klassen; PvP-Modi/Arenen [OFFEN].
- Anti-Monokultur: viele konkurrenzfähige Builds; sichtbares Counterplay; Telemetrie [BESTÄTIGT als Ziel].
- **Gestalterisch:** PvP verwendet dieselbe Lesbarkeitssprache; Gegnerfarben/Teamfarben sind deutlich, Spezialeffekte werden stärker reduziert.

---

## 12. Tod, Strafe, Wiederkehr [OFFEN, Vorschlag]

Nicht im Blueprint bestätigt. Vorschlag: sanfte Strafe (Ausrüstungsabnutzung, Wegstrecke), keine Verluste von Echos oder Resonanz durch Tod [VORSCHLAG]. Wiederbelebung durch Mitspieler oder Rückkehrpunkte.

---

## 13. Offene Fragen

1. Anzahl aktiver Fähigkeiten, Slotzahl für Fremdtradition-Fähigkeiten im Hybridsystem.
2. Zielsystem: freie Zielung vs. weiche Zielerfassung; Verhältnis in PvP.
3. Konkrete Erfolgsraten, Kosten, Schutzstufen der Resonanz.
4. Ob Waffen und Echo getrennt oder gebunden sind (Echo in Waffe fassen?).
5. Tod und Strafe.
6. PvP-Modi, Arenen, Schlachten.
7. Verhältnis Meisterschaft ↔ Wesensform (prägt Meisterschaft die Form?).
