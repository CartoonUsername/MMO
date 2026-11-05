# UI / UX DESIGN – Oberfläche, Bedienung, Rückmeldung

**Dokument H der Design-Reihe** · Stand 2026-11-05 · Labels: **[BESTÄTIGT] [DESIGNRICHTUNG] [VORSCHLAG] [OFFEN] [ZURÜCKGESTELLT]**.
Reines Design. Keine Implementierung. Der Godot-Prototyp (`client/godot`) hat nur ein Platzhalter-HUD und ist **kein** Vorbild für das Endlayout.

---

## 1. Kurzfassung

Die Oberfläche ist **modern, ruhig und diegetisch angehaucht**: dunkle Flächen mit feiner Goldkante und dünnen Leuchtlinien (wie die Konzepttafeln), viel Luft, große klare Symbole, wenig Dauerlärm. Sie darf nicht wie ein altes Tabellen-MMORPG oder ein Browsergame wirken [BESTÄTIGT §5.3: keine stark veraltete MMORPG-Optik].

Leitsätze:
1. **Die Welt bleibt sichtbar.** Das HUD nimmt im Kampf höchstens ein Viertel des Bildes.
2. **Eine Information, ein Ort.** Jede Zahl hat einen festen Platz.
3. **Tiefe auf Abruf.** Viel Systemtiefe (Kampf, Wirtschaft) wird durch Aufklappen erschlossen, nicht vorne gestapelt [BESTÄTIGT §29: komplex im Hintergrund, verständliche UI].
4. **Alles bedienbar mit Maus+Tastatur und Controller** [DESIGNRICHTUNG; Windows-PC zuerst, BESTÄTIGT §5].

---

## 2. Gestaltungssprache

### 2.1 Aussehen [DESIGNRICHTUNG, aus Konzepttafeln]
| Element | Gestaltung |
|---|---|
| Panels | Nachtblau-schwarz mit leichtem Papier-/Stoffrauschen, abgerundete Ecken, 1-px-Goldkante, weicher Schatten |
| Titel | Serifen-Versalien mit Weitenabstand (Fantasy-würdig, gut lesbar) |
| Fließtext | klare serifenlose Schrift, mind. 16 px bei 1080p, skalierbar |
| Akzent | Gold für Wichtiges, Türkis für Verbündete/Information, Rot-Orange für Gefahr |
| Rahmen von Items | Seltenheit: Grau, Grün, Blau, Violett, Gold (Tafel 1) |
| Symbole | linienbasiert, mit Elementfarbe, einheitliches Raster |
| Bewegung | sanft (150–250 ms), keine Sprunganimationen; Leuchtlinien laufen langsam |

### 2.2 Motiv „Ader, Ring, Patina“
Dieselbe Bildsprache wie die Welt (VISUAL_DIRECTION 2.2): Fortschrittsanzeigen sind feine Adern, die sich füllen; Echos erscheinen in Ringen; Alter und Nutzung zeigen sich als Patina auf Item-Karten. So wirkt die UI wie Teil der Welt, nicht wie darübergelegt.

---

## 3. HUD im Spiel (Spielansicht)

```
┌──────────────────────────────────────────────────────────────┐
│ [Ort/Wetter/Zeit]                     [Minikarte, rund]      │
│ [Gruppe: bis 5 Porträts]                                     │
│                                                              │
│                         (Spielwelt)                          │
│                                                              │
│ [Chat, einklappbar]            [Ziel / Boss-Leiste, mittig]  │
│                                                              │
│ [Figur: Leben/Ausdauer/Fokus]  [Fähigkeitsleiste]  [Echo]   │
└──────────────────────────────────────────────────────────────┘
```

### 3.1 Bestandteile

| Bereich | Inhalt | Verhalten |
|---|---|---|
| **Figurenanzeige (unten links)** | Porträt, Leben, Ausdauer, Fokus als dünne Leuchtleisten; Zustandssymbole | wird leiser außerhalb des Kampfs |
| **Fähigkeitsleiste (unten mittig)** | 8–10 Fähigkeiten, Abklingring um das Symbol, Element-Rand, Tastenhinweis | konfigurierbar; Controller-Radialmenü als Alternative |
| **Echo-Anzeige (unten rechts)** | Kristall mit Ringen; zeigt Haupttradition, Resonanzstufe, Aufladung | erscheint kompakt; Details im Echo-Fenster |
| **Zielanzeige (oben mittig)** | Name, Leben, **Haltung** (Gleichgewicht), Zustände | bei Boss groß mit Phasenmarken |
| **Gruppenleiste (links)** | Porträts, Leben, Rolle, Entfernung | Hervorhebung bei Gefahr (Markierung) |
| **Minikarte (oben rechts)** | rund, drehbar, Wegpunkte, Gefahrenhinweise | Nebel des Unbekannten |
| **Info-Streifen (oben links)** | Ortsname, Wetter, Zeit | blendet nach Ortswechsel aus |
| **Chat (unten links, einklappbar)** | Kanäle (Gruppe, Gilde, Region, Handel), Emotes | halbtransparent |
| **Benachrichtigungen (rechts mittig)** | Quests, Funde, Chronikmeldungen | kurze Karten, stapeln begrenzt |

### 3.2 Kampf-Zusatzebene [DESIGNRICHTUNG]
- **Bodentelegraphen** gehören zur Welt, nicht zur UI (siehe COMBAT_DESIGN 3).
- **Schwebende Zahlen** sind regelbar (Größe, Menge, aus).
- **Hit-Feedback** (Kameraschütteln, Treffer-Stopp) mit Intensitätsregler.
- **Kontextaktionen** (Ausweichen, Interaktion) erscheinen nahe dem Charakter als dezente Symbole.

### 3.3 Anpassbarkeit
Skalierung, Transparenz, freie Anordnung (Layoutmodus), Voreinstellungen **Minimal / Standard / Detail**, Controller-Layout, Linkshänder-Spiegelung [VORSCHLAG].

---

## 4. Fenster und Menüs

### 4.1 Hauptmenüstruktur [VORSCHLAG]

| Taste (Beispiel) | Fenster | Zweck |
|---|---|---|
| C | **Figur** | Aussehen, Wesensform, Eigenschaften, Chronik der Entwicklung |
| I | **Ausrüstung & Inventar** | Raster, Slots, Vergleich, Kleiderschrank |
| E | **Echos** | Echo-Sammlung, Haupttradition, Fremdfähigkeiten, Resonanz-Upgrade |
| K | **Fähigkeiten & Elemente** | Fähigkeitsbaum, Elementkombination, Meisterschaft |
| P | **Berufe** | Berufspfade, Verfahren, Aufträge |
| H | **Herstellen** | Rezepte, Werkbank, Qualität |
| M | **Karte** | Welt, Regionen, Wegpunkte, eigene Marker |
| B | **Markt** | Suchen, Angebote, Handelsverläufe |
| F | **Firma / Siedlung** | Unternehmen, Mitarbeiter, Bau, Gemeinschaft |
| G | **Gruppe / Gilde** | Gruppensuche, Gildenverwaltung |
| J | **Forschung / Journal** | Funde, Entdeckungen, Quests, Chronik |
| Esc | **System** | Optionen, Barrierefreiheit, Konto |

Die Dienste decken sich mit den **Fenstern**, die die Hauptstadt-Viertel im Server bereits benennen (Figur, Ausrüstung, Echos, Markt, Herstellen, Gruppe, Handel, Firma, Siedlung, Forschung, Gilde, Chronik).

### 4.2 Fensterprinzipien
- **Karte statt Liste:** Wo möglich, räumliche Darstellung (Weltkarte, Fähigkeitsnetz, Stadtplan).
- **Vergleich im Kontext:** Tooltips zeigen Unterschiede zum angelegten Teil (rot/grün, mit Text, nicht nur Farbe).
- **Rückgängig statt Bestätigen:** Wo möglich Undo; bei irreversiblen Handlungen **klare Bestätigung** (Wesensform, Verkauf von Meisterstück).
- **Kein verstecktes Tabellenwerk:** Zahlen mit Erklärung („Warum ist das so?“-Knopf) [BESTÄTIGT §29: verständliche UI].
- **Nur ein größeres Fenster gleichzeitig** außer Chat/Karte; Spielwelt schimmert durch.

---

## 5. Besondere Oberflächen

### 5.1 Echo-Fenster (Kampfecho & Resonanz)
- **Kristallkarte** groß: 3D-Vorschau der Manifestation (drehbar), Ringe zeigen Stufe; Meilensteinbereiche (Erweckung … Mythisch) als abgesetzte Segmente.
- **Entwicklungsleiste** mit den **sieben Ebenen** (Kristall, Ringe, Gestalt, Effekt, Animation, Umwelt, Zusatz): Der Spieler sieht, **was die nächste Stufe verändert**, nicht nur eine Zahl.
- **Upgrade-Bereich:** Chance, Kosten, Schutzgegenstand-Platz, Pechschutz-Füllstand; ehrliche Zahlen (keine versteckten Wahrscheinlichkeiten) [BESTÄTIGT §19.1 Prinzipien; Details OFFEN].
- **Hybridslots:** gewählte Fremdfähigkeiten verbunden mit Haupttradition; Hinweise auf Synergien.
- **Biografie:** Herkunft, Vorbesitzer, Kämpfe, Meisterschaft des aktuellen Trägers.
- **Handelsstatus:** aktiviert/gebunden/handelbar (Resonanzsiegel) deutlich sichtbar.

### 5.2 Wesensform-Fenster (Figur)
- **Zeitleiste der Prägung:** Stufen als Kapitel; kommende Stufen als **Schattenbild** (Vorschau).
- **Einflusswolke:** Was hat die Form geprägt (Kampf, Berufe, Entdeckungen)? Transparent, aber nicht als berechenbare Anleitung zum Ausreizen.
- **Warnung bei Schwelle:** irreversible Entscheidung mit Wartezeit, Zusammenfassung, Bestätigung.
- **Vergleichsfoto:** Mensch ↔ jetzt (Chronik).

### 5.3 Fähigkeits- und Elementfenster
- **Elementrad:** neun Medaillons, Freischaltstand, Markierung der gewählten zwei (bzw. drei im Endgame).
- **Kombinationsvorschau:** Vorschau von Form, Wirkung, Wechselwirkungen bei Auswahl; klassenabhängig (zeigt die eigene Klasse).
- **Anzeige der Wechselwirkungen** (Nass + Elektro) als lernbare Karten.

### 5.4 Berufsfenster und Herstellen
- **Pfad statt Balken:** Berufsbaum mit Spezialisierungen und Verfahren.
- **Werkbank:** Zutaten legen, Qualitätsvorschau, **aktiver Handwerksablauf** (kurze Interaktion).
- **Entdeckungsjournal:** unbekannte Kombinationen als „?“; Hinweise nach Experimenten.

### 5.5 Markt und Wirtschaft
- **Suche mit Filter** (Beruf, Qualität, Element, Seltenheit), Preisverlauf als kleine Kurve, Regionstabs.
- **Lieferverträge/Transport** als Auftragsliste mit Karte.
- **Unternehmensübersicht:** Gebäudestufe, Unternehmensstufe, Mitarbeiter (Stimmung als Gesicht+Farbe), Lager, Kosten, Ertrag; **Rückkehr-Zusammenfassung** nach Offlinezeit.
- **Mitarbeiterkarte:** Porträt, Fähigkeiten, Gehalt, Zufriedenheit, Ziele.

### 5.6 Siedlungs-/Baumodus
- **Platzierungsvorschau als Geisterbild** (Tafel „Spielerstädte“): blau transparent, grün gültig, rot ungültig + Grund als Text.
- **Draufsicht-Kamera**, Raster optional, Rotation, Anschlussmarker.
- **Kosten/Material** direkt sichtbar, Gemeinschaftsprojekt-Fortschritt als Balken am Gebäude.

### 5.7 Karte und Orientierung
- **Gezeichnete Karte** (Pergament-Look, dennoch klar), Nebel des Unbekannten, selbst gesetzte Marker, Fundnotizen, Gefahrenstufenhinweise.
- **Kompass-Leiste** oben (optional) mit Hinweisen statt Questpfeilen; Questmarker abschaltbar [DESIGNRICHTUNG: Entdeckung].

---

## 6. Erstkontakt: Einstieg und Führung [DESIGNRICHTUNG]

1. **Anmeldung/Charakter:** Wenige Schritte, Vorschau-Welt im Hintergrund, Charakterstudio mit Drehbühne.
2. **Erste 10 Minuten:** Der Spieler erwacht außerhalb der Hauptstadt, geht (mit sichtbarem Ziel am Horizont: Uhrenturm und Rauch) hinein, trifft einen Lehrer der Klasse und kämpft einen ersten Gegner. Kein Textblock vor dem Spielstart.
3. **Hinweise im Kontext:** Kurze Karten erscheinen **beim ersten Auftreten** einer Situation (Telegraph, Ausweichen, Handwerk) und lassen sich im Journal wiederfinden.
4. **Zurückhaltung:** Keine Tutorialpflicht für fortgeschrittene Systeme; Wirtschaft, Echo und Bau öffnen sich, wenn der Spieler sie berührt.

---

## 7. Rückmeldung (Feedback) und Ton

| Ereignis | Sichtbar | Hörbar |
|---|---|---|
| Treffer | Funken, Zahl (optional), Gegnerreaktion | Klang je Material |
| Gefahr | Bodenkreis, Gegnerhaltung | Warnton (richtungsbezogen) |
| Erfolg Resonanz | Ring rastet ein, Leuchtimpuls | tiefer Glockenton |
| Fehlschlag Resonanz | Haarriss im Kristall | dumpfer Klang, kein Hohn |
| Stufe Wesensform | kurzer, überspringbarer Ablauf | Orchester + Stille |
| Handel | Ware wechselt Besitzer (Animation), Münzen | Klingen |
| Chronikeintrag | goldene Zeile, Wappen | feierlicher Akkord |

Rückmeldung **informiert und feiert**, aber **verspottet nie**. Kein Kasinoeffekt bei Zufallsereignissen (keine suchtfördernden Dauer-Blinkeffekte).

---

## 8. Barrierefreiheit [DESIGNRICHTUNG]

- Skalierbare Schrift und UI, hoher Kontrast, Farbfehlsichtmodi (zusätzlich Form/Symbol).
- Untertitel und Sprecherkennung; visuelle Entsprechung für Warntöne.
- Umbelegbare Tasten, Hold-statt-Klick-Optionen, Zielhilfe.
- Reduzierte Bewegung/Kameraschütteln, Epilepsie-Schutz (Blitzdämpfung).
- Textsprache: Deutsch und Englisch als erste Lokalisierung [OFFEN].

---

## 9. Technische Leitplanken (Design-Sicht)

- UI als **eigene Ebene** mit festen Rastern, Skalierung 720p–4K.
- Alle Systeminhalte kommen **serverautoritativ** (UI zeigt, entscheidet nicht) [BESTÄTIGT §51].
- Latenzfreundlich: Optimistische Anzeigen nur für rein visuelle Aktionen; Handel/Upgrade erst nach Serverbestätigung.
- Ladezeiten: Vorschau-3D im Echo-Fenster nutzt dieselben Modelle wie das Spiel, kein zweiter Asset-Satz.

---

## 10. Gegenüberstellung mit Konzepttafeln

| Tafelelement | Übernahme |
|---|---|
| Fähigkeitsleiste unten | ja, modernisiert (Ringe, Elementränder) |
| Rasterinventar mit Seltenheitsrahmen | ja, mit Vergleichs-Tooltips |
| Kreisdiagramm der Resonanz | als Kristall-Ringe im Echo-Fenster |
| Hologramm-Platzierung | ja, als Baumodus |
| Listen („Berufe“, „Firmen“) | ja, aber als Pfad-/Kartenansichten |
| Pergament-/Banner-Look | nur als Akzent, nicht als Zwangs-Optik |
| Politik-Elemente | nicht übernommen (zurückgestellt) |

---

## 11. Offene Fragen

1. Controller-Support als Muss oder Ergänzung?
2. Mobile oder Tablet: nicht geplant (PC zuerst); Web-Variante (aktueller Prototyp) bleibt Vorschau.
3. Sprachausgabe/Synchronisation: Umfang, Dienste (z. B. ElevenLabs) [OFFEN].
4. Stufe der Hilfen (Questpfeile, Markierungen) als Standard oder Option?
5. Kameraverhalten bei Gruppenkämpfen (Bossübersicht) und PvP.
6. Wie viel Spielerlayout ist erlaubt, ohne Lesbarkeit zu zerstören?
