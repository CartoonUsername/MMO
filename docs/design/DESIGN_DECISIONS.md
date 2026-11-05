# DESIGN DECISIONS – Entscheidungsregister der Design-Reihe

**Dokument I der Design-Reihe** · Stand 2026-11-05
Dieses Register trennt sauber, was **entschieden** ist, was **Designrichtung** ist, was nur **Vorschlag** ist und was **offen** oder **zurückgestellt** bleibt. Es erfindet keine bestätigten Entscheidungen. Quellen: `MMORPG_MASTER_BLUEPRINT.md` (kurz: BP §), `docs/DECISIONS_AND_OPEN_QUESTIONS.md`, `docs/ENEMY_DESIGN.md`, `CLAUDE.md`, ADRs in `docs/decisions/`, Konzepttafeln.

Hinweis zur Quellenlage: `docs/VISION_2026-11-03.md` existiert im Repository **nicht**; laut `CLAUDE.md` ist sie inhaltsgleich mit dem Master-Blueprint auf `main`. Die Analyse stützt sich daher auf den Blueprint und die zwei Konzepttafeln (siehe VISUAL_DIRECTION).

Hinweis zu „Vorschlag (Claude, autorisiert)“: `CLAUDE.md` erlaubt, offene Designfragen (§57) ohne Rückfrage zu entscheiden; solche Entscheidungen sind **Vorschläge**, änderbar. Dieses Register markiert sie nicht als bestätigt.

---

## 1. BESTÄTIGT (Projektinhaber)

| Nr. | Entscheidung | Quelle |
|---|---|---|
| B1 | Alle Spieler (und NPCs) beginnen als Menschen. | BP §6, §11 |
| B2 | Drei Grundklassen: Krieger, Schamane/Alchemist, Bogenschütze (Namen Arbeitsbezeichnungen). | BP §7 |
| B3 | Klassenspezifische Bewegung und Fähigkeiten. | BP §8, §28 |
| B4 | Wesensform ist dauerhaft, nicht umkehrbar, nicht ersetzbar; Weiterentwicklung im Pfad möglich; Annahme der großen Verwandlung ist bewusste Entscheidung. | BP §11 |
| B5 | Keine willkürlichen globalen Mali pro Form; Stärken/Schwächen aus Pfad und Mechanik. | BP §11.1 |
| B6 | Formen sind nicht nur elementar (auch Berufe, Forschung, Erkundung). | BP §11.2 (Designrichtung, bestätigt als Ziel) |
| B7 | Berufe sind vollwertige Progressionspfade; individuelle Entwicklung; Techniken von Designern entworfen, nicht frei generiert. | BP §14–16 |
| B8 | Kampfecho (Arbeitsbegriff), Hybridsystem aus Haupttradition + ausgewählten Fremdfähigkeiten. | BP §17–18 |
| B9 | Resonanz +0 bis +30; sinkende Erfolgschance; Fehlschlag verliert Material; Stufenverlust höher möglich; Schutz und Pechschutz; Echo wird nie durch einen Fehlschlag zerstört. | BP §19, §19.1 |
| B10 | Handelbarkeit: unaktiviert handelbar, nach Aktivierung gebunden, Resonanzsiegel macht wieder handelbar, Resonanzstand bleibt, Meisterschaft nicht. | BP §20 |
| B11 | Meisterschaft getrennt von Resonanz. | BP §21 |
| B12 | Neun Elemente: Feuer, Wasser, Schatten, Licht, Wind, Erde, Elektro/Strom, Eis, Natur; Blitz ist Erscheinungsform von Elektro. | BP §22 |
| B13 | Freie Kombination (36 Zweier, 84 Dreier); zwei normal, drei als seltenes Endgame. | BP §23 |
| B14 | Wirkung ist klassenabhängig. | BP §24 |
| B15 | Third-Person-Action-Kampf, frei drehbare Kamera, kein Auto-Kampf. | BP §27 |
| B16 | Mischung aus schnellen Kombos und schweren taktischen Aktionen; Richtung, Aufladen, Konter, Ausweichen. | BP §28 |
| B17 | Hohe systemische Tiefe, verständliche UI, reproduzierbare Ergebnisse. | BP §29 |
| B18 | Ein Charakter, eine Progression für PvE und PvP; Anti-Monokultur. | BP §30 |
| B19 | Transmog/Kleiderschrank getrennt von Werten; Ausrüstung ändert Optionen. | BP §31 |
| B20 | Große Welt: Hauptkontinent, Inselgruppen, später weitere Kontinente; frei erkundbar ohne starre Levelschranken. | BP §32–34 |
| B21 | Reittiere und Schiffe; später weitere Fahrzeuge. | BP §35 |
| B22 | Zentrale Hauptstadt mit Diensten + Spielersiedlungen; persönlicher Besitz + Gemeinschaftsprojekte. | BP §36–37; ADR-0081 |
| B23 | Dynamische NPC-Wirtschaft + Spielermarkt; keine unbegrenzten Quellen. | BP §38, §41 |
| B24 | Spielerunternehmen mit Gebäude- und Unternehmenslevel, begrenzte NPC-Mitarbeiter, Spezialisten, Loyalität, Abwerbung, eingeschränkter Offlinebetrieb. | BP §39 |
| B25 | Erste Entdecker erhalten Anerkennung; keine dauerhafte Blockade von Grundtechnologien. | BP §44 |
| B26 | Start in klassischer Fantasy-Epoche, langfristige technologische Entwicklung. | BP §42–43 |
| B27 | Stadtpolitik bewusst zurückgestellt. | BP §46 |
| B28 | Windows-PC zuerst; realistische, cineastische Fantasy; keine stark veraltete MMORPG-Optik. | BP §5 |
| B29 | Serverautoritative Architektur, gemeinsame logische Welt. | BP §50–52 |
| B30 | Verboten: Pay-to-win, Echtgeld-Upgrade-Lotterie, unendliche passive Geldquellen, frei generierte Skills/Wesensformen ohne Designerregeln. | CLAUDE.md |
| B31 | Gegnerdesign: Muster mit Vorwarnung, Phasenwechsel, Familien (Wolfsrudel, Höhlenbär, Moorhexe, Steinwächter, Irrlicht-Heiler, Schattenjäger, Totem-Beschwörer, Mini-Boss, Boss „Steinherz-Koloss“). | ENEMY_DESIGN §0, §4 |
| B32 | Grafik-Client mit **Godot 4** (Unity verworfen). | Entscheidung Nutzer 2026-11-05 |
| B33 | Das Ziel ist ein grafisch herausragendes MMORPG, besser als Nostale/Metin2. | Nutzer 2026-11-05 |

---

## 2. DESIGNRICHTUNG (aus Entscheidungen abgeleitet, noch nicht im Detail bestätigt)

| Nr. | Richtung | Herleitung |
|---|---|---|
| D1 | Visuelle Klammer „gemalter Realismus“ mit goldener Stunde, Volumenlicht, Magie als Lichtquelle. | BP §5.3 + Tafeln |
| D2 | Fünf visuelle Wesensform-Stufen (Erwachen, Prägung, Hybridform, Wesensform, Gipfelform), Schichtmodell (Adern, Augen/Haar, Silhouettenteile, Oberfläche, Aura, Haltung). | Auftrag + BP §11 (Zahl nicht im BP) |
| D3 | Resonanz-Optik pro Meilenstein auf **verschiedenen Ebenen** (nicht nur größeres Leuchten). | BP §19.2 |
| D4 | Telegraphensprache (Form = Art, Farbe = Gefahr, Füllung = Zeit, Ton). | BP §29 + Tafel |
| D5 | Zehn Biomtypen mit Gefahr jenseits des Kampfes. | Auftrag; BP §32 |
| D6 | Hauptstadt-Viertel (Markt, Handwerk, Gilden, Rathaus, Kontor) mit Diensten. | ADR-0081 |
| D7 | Spielerstädte mit Geisterbild-Platzierung und Funktionsansicht. | BP §37 + Tafel |
| D8 | Berufe prägen Aussehen (Wesensprägung durch Handwerk). | BP §11.2 |
| D9 | Zusammenspiel Kampf ↔ Handwerk ↔ Handel (gegenseitige Abhängigkeit). | BP §14, §38 |
| D10 | Moderne HUD-Sprache (dunkel, Gold, Leuchtlinien), anpassbar, barrierefrei. | BP §5.3 |
| D11 | Weltereignisse mit Fernsichtbarkeit; Chronik als Ergebnis. | BP §48 (Vorschlag) |
| D12 | Fachwerk-/Steinfantasy als Startarchitektur, Epochen über Baustoffe sichtbar. | BP §42 |

---

## 3. VORSCHLAG (Entwurf, nicht beschlossen)

| Nr. | Vorschlag | Dokument |
|---|---|---|
| V1 | Leitmotiv „Nachhall“ (Ader, Ring, Patina) als gemeinsame Bildsprache. | VISUAL_DIRECTION |
| V2 | Wesensformfamilien als Richtungen: glutgeprägt, gezeitengeprägt, steingeprägt, hainbewachsen, dämmergeprägt, sturmgeprägt. | CHARACTER |
| V3 | Signaturkombinationen (12 Beispiele Elemente). | CHARACTER |
| V4 | Echo-Traditionen (Wolfsrudel, Bergwall, Sturmjäger, Quellmutter, Aschenschmied, Dämmerseele, Wurzelhüter, Frostchor, Glaswandler). | COMBAT |
| V5 | Ressourcen Ausdauer/Fokus/Haltung. | COMBAT |
| V6 | Berufe „Verzauberung/Resonanzhandwerk“ und „Reittierzucht“. | PROFESSIONS |
| V7 | Firmenidentität (Wappen, Hausfarben, Qualitätssiegel). | PROFESSIONS |
| V8 | Beispielbosse: Glutschwinge, Der Lichtlose, Mutter Moor, Der Sturmbringer (Steinherz-Koloss ist bestätigtes Konzept, Gestaltung hier Vorschlag). | CREATURE |
| V9 | Reittiere: Grauwolf, Dornschreiter, Felsbock, Sumpfmolch, Dünenläufer, Eisbock, Kristallgolem. | CREATURE |
| V10 | Tod: sanfte Strafe, kein Verlust von Echos/Resonanz. | COMBAT |
| V11 | Tastenbelegung und Fensterliste. | UI |
| V12 | Stufenweise Produktion der Grafik (Stil → Vertical Slice → Pipeline → Politur). | VISUAL |
| V13 | Spezialisierte Jäger-Ausprägung des Bogenschützen. | VISUAL, CHARACTER |
| V14 | Hybridregeln für Wesensprägung (mehrere Gewichte). | CHARACTER |
| V15 | Kamera- und Telegraphstandards (Gruppenreduktion der Effekte). | VISUAL, COMBAT |

---

## 4. OFFEN (braucht Entscheidung des Projektinhabers)

| Nr. | Frage | Folge für |
|---|---|---|
| O1 | Genauer Grafikstil: gemalt-stilisiert oder fotorealistisch? | Aufwand, Bildrate, Asset-Pipeline |
| O2 | Ist „Mensch“ eine Stufe der Wesensform (0–5) oder zählt man 1–5? Wie heißen die Stufen? | Charakterdesign, UI |
| O3 | Zahl der Wesensformen und Mischregeln (Gewichte vs. Wahl). | Content-Planung |
| O4 | Spezialisierungen/Mischklassen? | Klassendesign |
| O5 | Ob ein zehntes Element („Äther“ aus Tafel 2) später kommt. | Elementsystem |
| O6 | Zahl aktiver Fähigkeiten; Slots für Fremdfähigkeiten im Hybridsystem. | Kampf |
| O7 | Erfolgsraten, Kosten, Schutzstufen der Resonanz. | Wirtschaft/Balance |
| O8 | Ob Echo an Waffe gebunden ist. | Handel/Handwerk |
| O9 | Todesstrafe. | Kampf |
| O10 | PvP-Modi, Arenen, Schlachten. | Kampf |
| O11 | Gruppengrößen für Dungeons/Raids, Wiederholbarkeit. | Inhalte |
| O12 | Weltgröße, Zahl der Regionen, Inselzahl. | Welt, Server |
| O13 | Berufsgrenze pro Charakter; Start-Roster. | Berufe |
| O14 | Währungsmodell, Bank. | Wirtschaft |
| O15 | Reitkampf, Seekampf, Begleiterentwicklung. | Welt/Kampf |
| O16 | Welche Epochenübergänge wann (Zeit- oder Ereignisbasis). | Langzeit |
| O17 | KI-Dienste (Meshy, Mixamo, ElevenLabs, Midjourney) für Assets: Lizenzen prüfen. | Produktion |
| O18 | Altersfreigabe, Gewaltgrad. | Gesamtstil |
| O19 | Spieltitel (Arbeitsbegriff „Nachhall“ ist nur Gestaltungsmotiv). | Marke |
| O20 | Lokalisierung und Vertonung. | UI |

---

## 5. ZURÜCKGESTELLT (bewusst nicht jetzt)

| Nr. | Thema | Grund |
|---|---|---|
| Z1 | Stadtpolitik (Wahlen, Gesetze, Regierung, Steuerhoheit der Spieler) | BP §46; in Hauptstadt keine politischen Gebäude |
| Z2 | Luftschiffe, Eisenbahn, Fahrzeuge, Hochtechnologie-Epoche | spätere Epochen (BP §35, §42) |
| Z3 | Bank, Kredit, Versicherung | Geldsystem offen |
| Z4 | Weitere Kontinente | nach Hauptkontinent und Inselgruppen |
| Z5 | Jahreszeiten | langfristig |
| Z6 | Konkreter Zehntelement „Äther“ | siehe O5 |
| Z7 | Steinzeit-Startepoche (Tafel 2) | widerspricht BP §42 |

---

## 6. Abweichungen zwischen Konzepttafeln und Blueprint (Zusammenfassung)

| Thema | Tafel | Entscheidung hier |
|---|---|---|
| Zweite Klasse „Schurke/Jäger“ | Tafel 1/2 | Blueprint: Bogenschütze; Jäger nur als Ausprägung (V13) |
| Magier | Tafel | Blueprint: Schamane/Alchemist |
| Elementnamen „Luft“, „Blitz“ | Tafel | Blueprint: Wind, Elektro |
| Zehn Symbole unter „9 Elemente“ | Tafel 2 | neun gültig; Äther offen (O5) |
| Politik in Hauptstadt | Tafel | zurückgestellt (Z1) |
| Steinzeitstart | Tafel 2 | verworfen (Z7) |
| Wesensformen elfisch/Bestie | Tafel 2 | Richtungen, keine festen Formen |
| Laufvogel-Reittier | Tafel 2 | eigene Art „Dornschreiter“ (V9) |

---

## 7. Änderungsprotokoll

| Datum | Änderung |
|---|---|
| 2026-11-05 | Erstfassung der Design-Reihe (A–I). Keine Code-, Server-, DB-, Test- oder Engine-Änderung. |

Neue Entscheidungen werden hier als eigene Zeile mit Quelle (Datum, Person) eingetragen und in den betroffenen Dokumenten nachgezogen. Technische Folgen laufen weiter über ADRs in `docs/decisions/`.
