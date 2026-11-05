# CREATURE AND BOSS DESIGN – Kreaturen, Elite, Bosse, Dungeons, Reittiere

**Dokument G der Design-Reihe** · Stand 2026-11-05 · Labels: **[BESTÄTIGT] [DESIGNRICHTUNG] [VORSCHLAG] [OFFEN] [ZURÜCKGESTELLT]**.
Baut auf `docs/ENEMY_DESIGN.md` (Gegnerbausteine und Familien, vom Produktverantwortlichen bestätigt) auf; hier kommen Aussehen, Verhalten aus Spielersicht, Welt- und Bossdramaturgie dazu. Keine Werte.

---

## 1. Kurzfassung

Jedes Wesen der Welt hat **eine Absicht, eine Silhouette und eine Lektion**: Der Spieler soll beim ersten Blick wissen, was es will, und nach dem ersten Kampf, wie man es schlägt. Gegner sind keine Lebensbalken mit Fell, sondern **Begegnungen mit Regeln** [BESTÄTIGT: individuelle Monster- und Bossmodelle mit hochwertigen Animationen, Blueprint §5].

Harte Regel: **Keine reinen Recolors** [Auftrag]. Zwei Varianten einer Familie unterscheiden sich in mindestens **zwei** der Ebenen Silhouette, Bewegungsmuster, Angriffsform, Fähigkeit, Lebensraumverhalten.

---

## 2. Gestaltungsregeln für Kreaturen

### 2.1 Fünf Lesefragen [DESIGNRICHTUNG]
Jedes Wesen muss beantworten:
1. **Silhouette:** Erkenne ich es als Schattenriss? (Leitformen: Wolf = Keil, Bär = Block, Hexe = Dreieck/Schleier, Irrlicht = Tropfen, Golem = Quader.)
2. **Absicht:** Jagt, bewacht, lauert, heilt, ruft es? Zeigt Körperhaltung und Idle.
3. **Telegraph:** Welche Körperbewegung kündigt den gefährlichen Angriff an (Ausholen, Aufrichten, Glühen)?
4. **Schwachstelle:** Wo ist es verletzlich (Kern, Rücken, Wirkzeit, Schildbruch)?
5. **Lebensraum:** Wo gehört es hin, und was tut es dort, wenn niemand kommt (Ökologie)?

### 2.2 Lebendige Ökologie [VORSCHLAG]
- **Tagesabläufe:** Wölfe jagen nachts, Hirsche weiden morgens, Echsen sonnen sich.
- **Beziehungen:** Wölfe fressen Hirsche, Aasvögel kreisen über Kämpfen, Irrlichter locken Wanderer in Sümpfe.
- **Reaktion auf Spieler:** Scheue Tiere fliehen; Raubtiere schleichen; Wächter ignorieren Besucher, solange sie nichts berühren.
- **Spuren:** Fährten, Nester, Knochenhaufen, Kratzspuren markieren Revier – Hinweis auf Gefahr (siehe WORLD_DESIGN 5).

### 2.3 Elemente und Kreaturen [VORSCHLAG]
Elemente sind **Zustand und Lebensweise**, nicht nur Farbe: Ein Eiswolf hat Raureif im Fell und rutscht über Eis; ein Feuerwolf hinterlässt Brandspuren und scheut Wasser. Damit ergeben sich **neue Verhaltensweisen**, nicht nur neue Texturen.

---

## 3. Gegnerfamilien (Aussehen + Verhalten)

Die Familien kommen aus ENEMY_DESIGN §4 (bestätigt). Hier der Gestaltungsvorschlag:

| Familie | Silhouette und Material | Verhalten aus Spielersicht | Lektion | Variationen (nicht nur Farbe) |
|---|---|---|---|---|
| **Wolfsrudel** | Keil, drahtig, nasse Fellsträhnen | Heulen ruft Rudel, Flankieren, Alpha führt | Rudel trennen, Alpha-Heulen unterbrechen | Schneewolf: Sprungangriff aus Schneeverwehungen; Moorwolf: Fell mit Torf, Giftbiss; Glutwolf: Brandspur |
| **Höhlenbär** | Block, schwerer Kopf, Narben | langsam, Brüllen schwächt, Wuchtschlag mit langer Vorwarnung | Parade und Ausweichen | Gebirgsbär (klettert Wände), Eisbär (Bodeneis) |
| **Moorhexe** | Schleier, Stelzenschritt, Moosgewand | schwebt auf Abstand, Brandzauber (unterbrechbar), verlangsamt | Zauber unterbrechen | Nebelhexe (Täuschungsbilder), Torfhexe (Pflanzenwände) |
| **Steinwächter** | Quader, rissige Fugen, leuchtende Adern | Bodenschlag, Gesteinsschild | Schild brechen (Parade/Präzision) | Moosgolem (heilt Umgebung), Kristallwächter (reflektiert Zauber) |
| **Irrlicht-Heiler** | Tropfen aus Licht, schwebend | heilt Verbündete, flieht, bei Tod Wut der anderen | Heiler zuerst oder zuletzt? (Entscheidung) | Sumpflicht (lockt), Höhlenlicht (blendet) |
| **Schattenjäger** | schlanker Schleier mit Klauenhänden | Betäubungsstoß, flieht bei 25 % | Ausweichen auf Hörsignal | Dämmerjäger (Doppelgänger), Nachtbeißer (nur im Dunkeln stark) |
| **Totem-Beschwörer** | Holzpfahl, Federn, Knochenrasseln | beschwört Wellen, verwundbar zwischen den Wellen | Rhythmus lesen | Salztotem (Küste), Ascheschamane (Vulkan) |

### 3.1 Weitere Kreaturenarten (Vorschlag für Zielwelt) [VORSCHLAG]

| Gruppe | Beispiele (Arbeitsnamen) | Rolle |
|---|---|---|
| Wildtiere | Hirsch, Eber, Auerochse, Kranich, Fuchs | Ressourcen (Fell, Fleisch), harmlos oder wehrhaft |
| Scheue Wesen | Moosfüchse, Glaskrähen | Fund- und Forschungsziele |
| Raubtiere | Luchs, Säbelzahnkatze, Wüstenskorpion | Revierwächter |
| Wasserwesen | Riffkrabbe, Sturmrochen, Sumpfkroko | Küsten-/Seegefahr |
| Pflanzenwesen | Würgeranken, Sporenträger, Baumhirten | Natur-Biom, Heilung/Gift |
| Konstrukte | Ruinenwächter, Uhrwerkfiguren | alte Hinterlassenschaft |
| Geistwesen | Echo-Schemen, Irrlichter | Verbindung zu Kampfechos |
| Drachenartige | **Wyrmlinge, Glutechsen, Eisdrachen** | Weltboss-Material (Auftrag Tafel „Feuerdrache“) |

*Eigene Gestaltung statt Zitate:* Wir entwerfen **eigene Arten** (z. B. einen nicht-fliegenden Laufvogel „Dornschreiter“ als Reittier), ohne bekannte Figuren oder Marken nachzubauen.

---

## 4. Elite und Weltereignisse

### 4.1 Elite [BESTÄTIGT als Typ: Mini-Boss „Alpha des Nordtals“ in ENEMY_DESIGN]
Elite-Gegner sind benannte Wesen mit eigenem Namen, Narben, Revier und Muster. Sie **patrouillieren** und **reagieren auf Taten** der Spieler (jagt Spieler, der seine Brut tötete). Ihre Trophäe ist ein **Hinweis** (Rezept, Echo-Fragment).

### 4.2 Weltereignisse [BESTÄTIGT: Events, Weltboss-Siege in der Chronik §48]
- **Ankündigung:** Himmelsfärbung, Rauchsäule, Tierflucht, Wächter-NPCs warnen.
- **Teilnahme offen** für alle Spieler der Region; Beitrag zählt nach Rolle (Schaden, Heilung, Schutz, Handwerk/Versorgung).
- **Folgen:** zerstörte Straßen, Versorgungsengpässe (Wirtschaft), neue Rohstoffe, Chroniktext.
- Beispiele: Drachenanflug, Wolfsplage, Moorbrand, Golem-Erwachen, Schiffsangriff auf Hafen.

---

## 5. Bosse

### 5.1 Grundprinzipien [DESIGNRICHTUNG, ENEMY_DESIGN §3]
1. **Eine zentrale Idee pro Boss** („der Boss zwingt dich, X zu lernen“).
2. **Drei Phasen** als Regel (Idee → Eskalation → Wendepunkt), Übergänge sichtbar und hörbar.
3. **Lesbarkeit zuerst:** Gefahrenflächen, Schwachstellen (violette/orange Kerne), Phasenmarkierung.
4. **Rollen statt Zwang:** Rollen werden belohnt, aber nicht als einzige Lösung erzwungen.
5. **Arena erzählt:** Raum gehört zum Boss (Hitzeschächte, Fallbrücken, Kristallsäulen).
6. **Kein Recolor:** Jeder Boss hat eigenes Modell, eigene Animation, eigenes Soundthema.
7. **Wiederholbarkeit ohne Frust:** kurze Wege zurück, klare Checkpoints, Lerngewinn pro Versuch.

### 5.2 Beispielbosse (Arbeitsentwürfe) [VORSCHLAG]

#### Steinherz-Koloss (bestätigtes Konzept in ENEMY_DESIGN, Gestaltung neu)
| | |
|---|---|
| Ort | Ruinen im Gebirge |
| Silhouette | monumentaler Steinmensch, zerbrochene Schulter, offenes Brustfenster mit glühendem Kern |
| Idee | **Schild und Rhythmus** |
| Phase 1 | langsame Schläge, Bodenschlag; Kern verdeckt |
| Phase 2 | Schildphase (Gesteinsschild muss gebrochen werden), Wellen von Splittern |
| Phase 3 | Kern frei, Flächenschlag; Fenster für Fernkämpfer |
| Rollen | Front (Parade), Fern (Kern), Unterstützer (Schild/Heilung) |
| Belohnung | Kernsplitter (Echo-Material), Rezeptfragment, Chroniktitel „Herzbrecher“ |

#### Glutschwinge (Weltboss, Vulkanland)
| | |
|---|---|
| Silhouette | breiter, vierbeiniger Drache mit zerrissenen Flügelhäuten, lavaleuchtende Schuppenrisse |
| Idee | **Gelände ändert sich** |
| Phasen | Luftangriffe (Ausweichen, Deckung) → Bodenlava breitet sich aus → Erschöpfungsphase mit offenen Wunden |
| Besonderheit | Lavafelder bleiben Stunden bestehen; Spieler bauen/ernten dort anschließend Obsidian |
| Rollen | Mobilität, Eis/Wasser-Löschung, Gruppenschilde |

#### Der Lichtlose (Dungeon-Boss, Ruinenland)
| | |
|---|---|
| Silhouette | schmaler Mensch aus Schleier, verzerrte Schatten |
| Idee | **Licht als Waffe** |
| Mechanik | Räume sind dunkel; Spieler setzen Lichtquellen (Fackeln, Lichtzauber); der Boss meidet Licht, verdunkelt Quellen |
| Rollen | Licht-Träger, Wächter der Lichtinseln |

#### Mutter Moor (Weltboss, Sumpf)
| | |
|---|---|
| Silhouette | gewaltige Baumhexe mit Wurzelarmen und Moosschleier |
| Idee | **Raum wuchert** |
| Mechanik | Wurzeln versperren Pfade; Natur-/Feuer-Wechselwirkung; Heilkräuter wachsen auf besiegten Wurzeln |

#### Der Sturmbringer (Weltboss, Küste)
| | |
|---|---|
| Silhouette | wellenförmige Riesengestalt mit Schiffsmasten als Hörner |
| Idee | **Wetter ist Boss** |
| Mechanik | Blitzfelder (Elektro), Wasserwände, Schiffe als Gruppenkampfplattform |

### 5.3 Schwierigkeitsstufen [OFFEN]
Gruppengröße, Skalierung, Wiederholbarkeit, Wochenverriegelung sind offen. Gestalterisch gilt: **Schwierigkeit zeigt sich in neuen Mustern**, nicht in aufgeblähter Lebensenergie.

---

## 6. Dungeons und Raids [BESTÄTIGT: Dungeons, Ruinen, Raids]

| Typ | Gruppe | Länge | Wiederholung | Gestaltung |
|---|---|---|---|---|
| **Offene Ruinen** | Solo bis Gruppe | kurz | frei | in offener Welt, Rätsel und Funde |
| **Dungeon** | 3–5 [OFFEN] | 30–60 min | lohnend | lineare bis verzweigte Abfolge mit 1–2 Mini-Bossen, 1 Boss |
| **Raid** | große Gruppe [OFFEN] | mehrere Stunden | wöchentlich [OFFEN] | monumentale Räume, mehrere Bosse, Mechanikketten |
| **Prüfungen** | Solo | kurz | einmal | Wesensform-Schwellen, Meisterschaft; persönliche Orte |

Gestaltungsregeln:
- **Lichtinseln** führen; Magie als kalte Lichtquelle (Tafel 1).
- **Maßstab** durch Raumhöhe und menschliche Figuren.
- **Erzählung durch Umgebung** (Wandbilder, Spuren, Notizen).
- **Abkürzungen** und Checkpoints, damit Scheitern nicht lange Wege kostet.
- **Rätsel mit Ruinenwissen** koppeln an Forschung (PROFESSIONS 5).

---

## 7. Belohnung [DESIGNRICHTUNG]

Belohnungen sind **Material, Wissen, Echo-Fragmente, Aussehen**, nicht nur Zahlen [BESTÄTIGT §25, §20]:
- Bossmaterial → Handwerk (Rezepte/Veredelung).
- Echo-Fragmente → neue Traditionen.
- Titel, Chroniktexte, Trophäen für Haus/Gilde.
- Aussehen (Transmog) ohne Kampfvorteil.
- Seltenes und Einzigartiges ist **nicht duplizierbar** [BESTÄTIGT §20].
- Kein Pay-to-win, keine Echtgeld-Lotterie [BESTÄTIGT, CLAUDE.md].

---

## 8. Reittiere und Begleiter [BESTÄTIGT: Reittiere §35; Begleiter selten §49]

### 8.1 Reittiere
| Reittier (Arbeitsname) | Biom | Silhouette | Fähigkeit | Eigenheit |
|---|---|---|---|---|
| **Grauwolf** | Wald, Gebirge | Keil, Sattel mit Fellkragen | schnell, ausdauernd | Rudelbindung |
| **Dornschreiter** | Wiese, Wüste | zweibeiniger Laufvogel mit Stachelkamm | Sprint, Hindernisse überspringen | eigene Art, nicht an bekannte Vorbilder angelehnt |
| **Felsbock** | Gebirge | Ziege mit Hornbogen | klettert Steilwände | langsam in Ebene |
| **Sumpfmolch** | Moor | breites Amphib | trägt Last, schwimmt | schwerfällig |
| **Dünenläufer** | Wüste | langbeinig, Hitzeschutz | wenig Wasserbedarf | meidet Kälte |
| **Eisbock** | Schnee | Breite Hufe, Pelz | Rutschen auf Eis | hitzeempfindlich |
| **Kristallgolem** (selten) | Ruinen | kleiner Konstrukt-Läufer | Kristallsprünge | Fund durch Forschung |

Reittiere wirken **wie Lebewesen**: Pflege, Ausdauer, Gepäck, Scheuen bei großer Gefahr. Zucht/Berufbezug [VORSCHLAG]. Kampf vom Reittier ist [OFFEN].

### 8.2 Begleiter [BESTÄTIGT als seltene Möglichkeit §49; Eigenentwicklung OFFEN]
Seltene Begleiter (Falke, Fuchsgeist, Mini-Golem) sind **Charaktere** mit Gewohnheiten, nicht nur Pet-Buffs. Tafel zeigt „Begleiter mit eigener Entwicklung“: wir übernehmen das als [VORSCHLAG] mit klarer Grenze (keine Stat-Maschine).

---

## 9. Hybride und NPCs mit Wesensform

NPCs können wie Spieler Wesensformen tragen [BESTÄTIGT §11]. Dadurch begegnen Spieler **Menschen und Wesen**, die ihren Weg gegangen sind: ein einsamer Schmied mit Glutadern, eine Alchemistin mit Moosschultern. Diese NPCs sind Quellen von Quests, Techniken und Weltgeschichte und zeigen, was **aus dem eigenen Charakter werden kann**.

---

## 10. Offene Fragen

1. Gruppengrößen und Schwierigkeitsmodell für Dungeons/Raids; Wiederholbarkeit.
2. Wie viele Gegnerfamilien im Vertical Slice, wie viele in der Vollwelt?
3. Gegnermodelle: Handarbeit, KI-gestützt (Meshy) mit Nachbearbeitung oder Auftragsarbeit?
4. Boss-Loot: gebunden oder handelbar (Einzigartigkeit)?
5. Reitkampf, Begleiter-Entwicklung.
6. Weltboss-Rotation und Serverereignisse (zeitlich vs. getriggert durch Spieler).
7. Was passiert bei Weltboss-Niederlage (Folgen für Regionen)?
