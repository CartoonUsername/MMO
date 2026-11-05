# WORLD DESIGN – Welt, Regionen, Hauptstadt, Städte

**Dokument C der Design-Reihe** · Stand 2026-11-05 · Labels: **[BESTÄTIGT] [DESIGNRICHTUNG] [VORSCHLAG] [OFFEN] [ZURÜCKGESTELLT]** (Bedeutung siehe VISUAL_DIRECTION.md).
Alle Ortsnamen unten sind **Arbeitsnamen [VORSCHLAG]**, soweit sie nicht schon im Code als Regionen stehen (Sunmeadow, Fangvale, Moor, Crossing sind technische Platzhalter der Referenzwelt).

---

## 1. Kurzfassung

Die Welt ist **groß, begehbar und nicht in Instanzschläuche zerlegt** [BESTÄTIGT: große Welt, Hauptkontinent, Inselgruppen, später weitere Kontinente]. Sie wächst über Epochen. Jede Region hat eine eigene Aufgabe im Spiel: Rohstoffe, Gefahr, Forschung, Handel oder Rückzug. Die Hauptstadt ist der gemeinsame Treffpunkt, nicht der Mittelpunkt aller Wege.

Die Welt soll sich lohnen zu **erkunden**, auch ohne Karte voller Marker: Sichtachsen, Lichter in der Ferne, Geräusche und Spuren führen den Blick.

---

## 2. Aufbau der Welt

| Ebene | Inhalt | Status |
|---|---|---|
| Hauptkontinent | Startgebiet, Hauptstadt, Kernregionen, erste Dungeons | [BESTÄTIGT] |
| Inselgruppen | per Schiff erreichbar, eigene Ressourcen und Kreaturen | [BESTÄTIGT] |
| Weitere Kontinente | spätere Erweiterung, an Epochen gekoppelt | [BESTÄTIGT als Ziel], Umfang [OFFEN] |
| Tiefenräume | Höhlen, Ruinen, Untergründe, Dungeons | [BESTÄTIGT] |
| Luft und See | Reittiere, Schiffe, später Luftfahrzeuge | [BESTÄTIGT: Reittiere, Schiffe], Luftfahrzeuge und Fahrzeuge [ZURÜCKGESTELLT auf spätere Epochen] |

**Grundsatz Weltstreaming [DESIGNRICHTUNG]:** Die Welt ist in Zellen geteilt. Spieler sehen nur, was nahe ist. Das ist eine technische Folge der Größe, aber auch Gestaltungsregel: Weite Sicht (Berge, Türme, Rauchsäulen) trägt die Orientierung, Details laden mit der Nähe.

---

## 3. Die zehn Biomtypen [BESTÄTIGT: zehn Biomtypen; Namen und Zuordnung VORSCHLAG]

Jedes Biom bekommt: Leitlicht, Leitform, Leitgeräusch, Wetter, Rohstoffe, typische Kreaturen, Besonderheit für Spielsysteme.

| # | Biom | Leitlicht und Farbe | Leitform | Wetter | Rohstoffe (Beispiele) | Besonderheit |
|---|---|---|---|---|---|---|
| 1 | **Wiesenland und Hügel** | goldenes Streiflicht, sattes Grün | sanfte Linien, Steinzäune | Regen, Frühnebel | Getreide, Flachs, Kupfer | Startnahe Landwirtschaft, ruhige Siedlungen |
| 2 | **Laubwald und Magiewald** | gefiltertes Grün, im Magiewald blaue Sporen | hohe Stämme, Lichtschächte | Dunst, Nieselregen | Holz, Pilze, Kräuter | Natur-Element stark, Portale und Ruinen |
| 3 | **Gebirge** | kaltes Blau, scharfes Licht | Grate, Pässe, Seilbrücken | Wind, Schneesturm | Eisenerz, Edelstein | Minen, Festungen, Höhenwege |
| 4 | **Schneeland und Gletscher** | Blauweiß, lange Dämmerung | Eisspalten, Windkanten | Schnee, Eisnebel | Eisklar, Pelze | Eis-Element, Überlebensdruck |
| 5 | **Wüste und Trockenland** | gleißendes Weiß-Gelb, Hitzeflimmern | Dünen, Felsbögen | Sandsturm | Glas-Sand, Salz, Harze | Wasser ist knapp, Karawanen |
| 6 | **Dschungel und Wasserfälle** | feuchtes Grün-Gold, dichte Schatten | Lianen, Terrassen | Dauerregen, Dampf | Heilkräuter, Gifte, Hartholz | Vertikale Wege, Giftpflanzen |
| 7 | **Sumpf und Moor** | grünliches Zwielicht | Stege, Baumstümpfe | Nebel, Fäulnis | Torf, Moorerz, Pilze | Schatten- und Natur-Kreaturen, schlechte Sicht |
| 8 | **Vulkanland** | glühendes Rot-Orange gegen Schwarz | Lavaflüsse, Obsidiangrate | Asche, Hitzewellen | Obsidian, Schwefel, Feuerkristall | Feuer-Element, Boden verändert sich |
| 9 | **Küste, Inseln und Meer** | Türkis, Salzdunst | Klippen, Häfen, Riffe | Sturm, Flaute | Fisch, Perlen, Salz | Schifffahrt, Handel |
| 10 | **Ruinenland und Tiefe** | kaltes Blau-Weiß aus Kristallen, Fackelwärme | zerbrochene Bögen, Treppen | Staub, Zugluft | Relikte, Echo-Kristalle | Dungeons, Forschung, Geschichte |

Jedes Biom hat **mindestens eine Gefahr, die nicht Kampf ist** (Hitze, Kälte, Sicht, Gift, Absturz), damit Berufe und Ausrüstung wichtig werden [VORSCHLAG].

---

## 4. Die Referenzwelt des Servers (Ist-Stand)

Der technische Prototyp kennt vier Regionen: **Sunmeadow** (Wiesen), **Fangvale** (Gegnertal), **Moor** (Sumpf) und **Crossing** (Kreuzung am Fluss, hier liegt die Hauptstadt). Der Fluss trennt die Regionen, Brücken verbinden sie. Das ist ein **Testlayout** (ca. 6000 x 4000 Einheiten) und kein endgültiger Weltplan [DESIGNRICHTUNG]. Die Zielwelt wird um ein Vielfaches größer.

---

## 5. Regionsprinzipien [VORSCHLAG]

1. **Region = Geschichte.** Jede Region hat eine Frage, die man beim Erkunden beantwortet („Wer baute die Brücke?“, „Warum glüht der Berg?“).
2. **Stufen ohne Zwangswege.** Es gibt Empfehlungsbereiche, aber keine unsichtbaren Wände. Gefährliche Zonen **zeigen** ihre Gefahr (Knochen, Rauch, Lärm, rote Dämmerung).
3. **Drei Nutzungen pro Region:** Sammeln/Handwerk, Kämpfen/Entdecken, Wohnen/Bauen. Keine Region ist nur Durchgang.
4. **Weg ist Wert.** Reisewege haben Rastplätze, Aussichtspunkte und Händler, damit Reise nicht leere Zeit ist.
5. **Schnellreise ist Ergänzung.** Es gibt freigeschaltete Wegpunkte, aber teure Rückreise mit Ware lohnt Reittiere und Karawanen.

---

## 6. Die Hauptstadt

### 6.1 Rolle [BESTÄTIGT: zentrale Hauptstadt mit Diensten; Stadtpolitik ZURÜCKGESTELLT]

Die Hauptstadt ist der **gemeinsame Treffpunkt** und Dienstleistungsort: Handel, Herstellung, Gruppensuche, Gilden, Archiv. Sie ist sicher (keine Gegner greifen an) [BESTÄTIGT, ADR-0081, im Server umgesetzt]. Sie ist **keine politische Bühne**; Wahlen, Räte und Regierung sind zurückgestellt.

### 6.2 Standort und Silhouette [DESIGNRICHTUNG]

Die Stadt liegt an der Kreuzung des Flusses mit den drei Hauptwegen und hat **drei Tore** (West, Ost, Süd), jedes nach einer Region ausgerichtet (Server: Westtor → Sunmeadow, Osttor → Fangvale, Südtor → Moor). Aus der Ferne erkennt man sie an:

- einem **Uhrenturm** im Rathausviertel (Wahrzeichen und Orientierung),
- einer **Rauchfahne** des Handwerksviertels,
- **Fackel- und Fensterlicht** nachts, das die Tore markiert,
- Bannern in Türkis und Rot.

### 6.3 Fünf Viertel (Ist-Stand im Server, Gestaltung hier)

| Viertel | Funktion für den Spieler | Aussehen | Klang und Leben |
|---|---|---|---|
| **Marktplatz** (Mitte) | Handel, Treffpunkt, Brunnen als Startpunkt | großer Kopfsteinplatz, Brunnen, Marktstände mit gestreiften Markisen | Rufe, Lauten, Taubenflug |
| **Handwerksviertel** | Herstellen, Werkbänke, Berufslehrer | Schlote, Wasserrad, Werkstätten mit Auslage, Funken | Hämmern, Zischen |
| **Gildenhalle** | Gruppe/Gilde, Aufträge, Übungsplatz | breite Halle mit Bannerwand, Übungsplatz davor | Schwerter, Anfeuern |
| **Rathaus** | Archiv, Chronik, Forschung, Bürgerdienste | Fachwerk, türkises Ziegeldach, runder Uhrenturm (Meshy-Testmodell) | Glocke zur Stunde |
| **Handelskontor** | Firmen, Verträge, Fernhandel, Lagerhaus | Lagerhallen, Kran, Waagen, Firmenzeichen | Karren, Schreiber |

Dienste der Viertel sind im Server bereits verknüpft (Figur, Ausrüstung, Echos, Markt, Herstellen, Gruppe, Handel, Firma, Siedlung, Forschung, Gilde, Chronik).

### 6.4 Raumgefühl

- **Zentrum offen, Ränder dicht.** Der Marktplatz ist weit und hell, Gassen darum eng und warm.
- **Höhenstaffel:** Hauptstadtburg/Uhrenturm überragen; Plattformen und Treppen geben Höhenebenen, ohne Wege zu verwirren.
- **Zugangsregel:** Von jedem Tor führt eine **Sichtachse** zum Platz. Neue Spieler finden den Brunnen ohne Karte.
- **Beleben ohne Lärm:** NPC-Routinen (Händler öffnen morgens, Wachen wechseln, Laternenanzünder abends). Zielgröße und Technik [OFFEN].

### 6.5 Entwicklung der Hauptstadt über Epochen [DESIGNRICHTUNG]

| Epoche | Veränderung am Stadtbild |
|---|---|
| Klassisch (Start) | Holz, Fachwerk, Stein, Wasserrad |
| Frühindustrie | Ziegelschlote, Krane, Eisenbrücken, Gaslaternen |
| Hochindustrie | Dampf- und Schienenanlagen, Glashallen |
| Später | technologische Viertel; **nur wenn und wie die Epochen freigeschaltet werden** [OFFEN] |

Alte Viertel bleiben sichtbar als „Altstadt“. Die Stadt zeigt ihre Geschichte (Patina-Prinzip).

---

## 7. Städte und Siedlungen

### 7.1 Stufen [BESTÄTIGT Grundidee, Namen VORSCHLAG]

| Stufe | Wer baut | Charakter |
|---|---|---|
| Lager / Außenposten | Spielergruppe | Zelte, Feuerstelle, Lager; schnell, verwundbar |
| Weiler / Dorf | Spielergruppe oder Gilde | erste Häuser, Brunnen, kleine Dienste |
| Stadt | große Gemeinschaft, Firmen | Straßen, Handwerksbetriebe, Markt |
| Große Stadt | langfristig | eigene Viertel, Hafen, Spezialisierung |
| NPC-Städte | Spielwelt | Ankerpunkte pro Region, feste Dienste |

Siedlungsregeln im Server (Settlement Rules v2, gemeinsames Platzieren, Förderung/Limit) bestehen bereits; hier steht nur die Gestaltung.

### 7.2 Gestaltungsregeln für Spielerstädte [DESIGNRICHTUNG]

1. **Platzierung mit Geisterbild.** Beim Bauen zeigt ein blau transparentes Vorschaumodell Position, Ausrichtung und Anschlüsse; grün = gültig, rot = verboten, mit Grund im Text (Tafel „Spielerstädte“).
2. **Modularer Baukasten.** Wände, Dächer, Türen, Fenster, Schilder; regionale Bauweise nach Biom (Gebirge: Stein/Schiefer, Wüste: Lehm/Zelt, Wald: Stamm/Moos).
3. **Funktion sichtbar.** Eine Schmiede sieht aus wie eine Schmiede (Schlot, Amboss). Fremde erkennen Dienste aus der Entfernung.
4. **Stufen sichtbar.** Rohbau → Gerüst → Fertig → Meisterhaus; Verfall bei Vernachlässigung (Patina).
5. **Individuelles Zeichen.** Jede Siedlung und Firma hat Wappen und Farbe; Banner, Schilder und Fahnen tragen sie [VORSCHLAG].
6. **Stadtbild entsteht aus Spielerentscheidungen**, nicht aus Zufall: Straßenführung, Marktplatz, Hafen, Mauern.
7. **Schutz und Gefahr:** Eigene Siedlungen haben Wachen/Mauern/Türme; Ereignisse (Angriffe, Wetter) sind an Verteidigungsbauten gebunden. Genaue Regeln [OFFEN].
8. **Keine Politik** (Wahlen, Gesetze, Steuern der Spieler) [ZURÜCKGESTELLT]; Verwaltung beschränkt sich auf Eigentum, Rechte, Rollen nach den bestehenden Siedlungsregeln.

### 7.3 Was der Spieler tut, sieht, fühlt (Beispiel Siedlungsbau)

- **Sieht:** Ein leeres Feld, ein Banner, ein Geisterbild. Nach Tagen: Fundament, Gerüste, rauchende Schornsteine, Besucher.
- **Tut:** Plätze wählen, Material herbeischaffen, mit anderen bauen, Betriebe ansiedeln.
- **Fühlt:** Eigentümerstolz und Verantwortung; Wiedersehen mit Nachbarn.
- **Entwickelt:** Einrichtungen, Berufsbetriebe, Anbindung an Straßen/Häfen.
- **Beeinflusst:** Handel der Region, Preise, Wege anderer Spieler.
- **Langfristig:** Die Stadt überdauert Epochenwechsel und trägt Spuren früherer Zeiten.

---

## 8. Dungeons, Ruinen, Erkundung

### 8.1 Orte und Zweck [BESTÄTIGT: Dungeons, Ruinen, Raids, Events]

| Typ | Spielerfantasie | Gestaltung |
|---|---|---|
| **Offene Ruinen** | Erkunden, Rätsel, Geschichte | ohne Ladeschirm in der offenen Welt, Leuchtadern führen zu Geheimnissen |
| **Dungeons (Gruppe)** | taktischer Gruppenkampf, Bosse | gestaffelte Räume mit klaren Lichtinseln, Raumhöhen für Maßstab |
| **Raids** | große Koordination | monumentale Räume, Phasen, siehe CREATURE_AND_BOSS_DESIGN |
| **Weltereignisse** | gemeinsam reagieren | sichtbar in der Ferne (Rauchsäule, Himmelsfarbe) |
| **Verborgene Orte** | Entdeckerlohn | Hinweise im Gelände, keine Marker nötig |

### 8.2 Entdeckungsdesign [DESIGNRICHTUNG]

- **Hinweise vor Marker.** Pfade, Tiere, Farbwechsel, Geräusche, Notizen von NPCs.
- **Lohn für Neugier:** seltene Rohstoffe, Rezeptfragmente, Echo-Kristalle, Aussichtspunkte, Chronik-Einträge.
- **Karte füllt sich durch Gehen** (Nebel des Unbekannten), Zeichnungen und Notizen sind Spielerwerk.
- **Forschung** (Berufspfad): Ruinen enthalten Wissen, das Forscher entschlüsseln; Funde können Zugang und Rezepte öffnen.

---

## 9. Reisen: Reittiere, Schiffe, später mehr

| Mittel | Status | Rolle | Gestaltung |
|---|---|---|---|
| Zu Fuß | [BESTÄTIGT] | Basis, nie langweilig | Klettern, Springen, Schwimmen als Ergänzung [VORSCHLAG] |
| Reittiere | [BESTÄTIGT] | Geschwindigkeit, Lastenträger, Identität | Reittiere haben Sattel/Geschirr, Pflege; Arten je Biom (Wolf, Laufechse, Hirsch, Bergziege); Kampf vom Reittier ist [OFFEN] |
| Schiffe | [BESTÄTIGT] | Inseln, Fernhandel, Gruppenreisen | Segelschiffe, Hafen als Ereignisort; Seeschlachten [OFFEN] |
| Karawanen/Wagen | [VORSCHLAG] | Handelsware befördern | Spielerfirmen betreiben sie |
| Luftschiff, Eisenbahn, Fahrzeuge | [ZURÜCKGESTELLT] | spätere Epochen | siehe Epochen |

Reittiere sind keine reinen Geschwindigkeitsbuffs: ein mitgebrachtes Reittier hat Ausdauer, Gepäck und wird bei Gefahr scheu [VORSCHLAG].

---

## 10. Tageszeit, Wetter, Jahreszeit [DESIGNRICHTUNG, §5.3 Licht/Wetter]

- Tag/Nacht mit eigenem Gameplayeffekt (Nachtgegner, Händlerzeiten, Sicht).
- Wetter pro Biom, mit Wirkung auf Kampf (Nässe verstärkt Elektro, Regen löscht Feuer) und Beruf (Ernte, Segeln).
- Jahreszeiten **langfristig** [VORSCHLAG]; Auswirkung auf Ernte und Pässe.

---

## 11. Offene Fragen

1. Weltgröße, Zahl der Regionen und Reisezeit Hauptstadt – Rand (Zielwert).
2. Wie viele Inseln und welche Epochen schalten Kontinente frei?
3. Seekampf und Reitkampf: Ja/Nein, in welcher Stufe?
4. Schnellreisemodell (Wegpunkte, Kosten, Kampfbeschränkung).
5. Welche NPC-Städte außer der Hauptstadt, wie viele Fraktionen (ohne Politik)?
6. Wie weit darf Spielerbau die Landschaft verändern (Terraforming, Rodung)?
7. Wer verteidigt Siedlungen: NPC-Wachen, Spieler, beides?
