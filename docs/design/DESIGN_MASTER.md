# DESIGN MASTER – Gesamtübersicht der Spielvision

**Dokument A der Design-Reihe** · Stand 2026-11-05
Einstieg in alle Design-Dokumente. Dieses Dokument fasst zusammen, verweist und listet Lücken. Details stehen in den Fachdokumenten.

Statuslabels: **[BESTÄTIGT]** vom Projektinhaber entschieden · **[DESIGNRICHTUNG]** abgeleitet · **[VORSCHLAG]** Entwurf · **[OFFEN]** braucht Entscheidung · **[ZURÜCKGESTELLT]** bewusst später.

---

## 1. Dokumentenübersicht

| Kürzel | Datei | Inhalt |
|---|---|---|
| A | `DESIGN_MASTER.md` | dieses Dokument |
| B | `VISUAL_DIRECTION.md` | Bildanalyse, visuelle Identität, Farben, Licht, Qualitätsstufen |
| C | `WORLD_DESIGN.md` | Welt, zehn Biome, Hauptstadt, Städte, Dungeons, Reisen |
| D | `CHARACTER_DESIGN.md` | Menschen, drei Klassen, neun Elemente, Wesensformen, Ausrüstung |
| E | `COMBAT_DESIGN.md` | Third-Person-Kampf, Lesbarkeit, Kampfechos, Resonanz, Meisterschaft |
| F | `PROFESSIONS_AND_ECONOMY_DESIGN.md` | Berufe, Herstellung, Forschung, Wirtschaft, Unternehmen |
| G | `CREATURE_AND_BOSS_DESIGN.md` | Kreaturen, Elite, Bosse, Dungeons, Reittiere |
| H | `UI_UX_DESIGN.md` | HUD, Fenster, Bedienung, Barrierefreiheit |
| I | `DESIGN_DECISIONS.md` | Entscheidungsregister (bestätigt/Richtung/Vorschlag/offen/zurückgestellt) |

Konzeptbilder: `docs/design/konzeptbilder/` (zwei Tafeln, beide geöffnet und analysiert).

### Quellenlage
- `MMORPG_MASTER_BLUEPRINT.md` wurde gelesen (Hauptquelle).
- `docs/VISION_2026-11-03.md` **existiert nicht** im Repository; laut `CLAUDE.md` inhaltsgleich mit dem Blueprint.
- `workspace/Konzeptbild/` auf dem RunPod enthielt **genau zwei** PNG-Dateien; beide ließen sich öffnen.
- Zusätzlich ausgewertet: `DECISIONS_AND_OPEN_QUESTIONS.md`, `ENEMY_DESIGN.md`, ADR-0081, CEE-Regeln und Visual-Rules (Platzhalter).

---

## 2. Die Vision in einem Absatz

Ein **großes, gemalt-cineastisches Online-Rollenspiel** auf dem PC: Alle beginnen als Menschen, wählen eine von drei Klassen und werden durch Taten zu einzigartigen Wesen. Der Kampf ist Third-Person-Action mit lesbaren Gefahrenzeichen; **Kampfechos** mit **Resonanz bis +30** machen Kampfstil sichtbar und handelbar; **neun frei kombinierbare Elemente** geben jedem eine eigene Magie. Berufe, Forschung und Unternehmen sind **gleichwertige Lebenswege**; eine lebendige NPC-Wirtschaft und Spielerstädte formen die Welt. Alles wächst über **Epochen**. Das Spiel soll grafisch weit über Nostale und Metin2 hinausgehen.

---

## 3. Die sieben Säulen (Spielerperspektive)

| Säule | Was der Spieler **sieht** | **Tut** | **Fühlt** | **Entwickelt** | **Beeinflusst** | Langzeitantrieb |
|---|---|---|---|---|---|---|
| **Wandlung** (Wesensform) | Figur ändert sich in Kapiteln | lebt, kämpft, handwerkt, erkundet | Stolz, Endgültigkeit | Form, Prägung | Wahrnehmung durch andere | eigene, einmalige Gestalt |
| **Kampf** | Telegraphen, Manifestationen | weicht aus, kombiniert, spielt Rolle | Wucht, Fluss, Präzision | Fähigkeiten, Meisterschaft | Gruppenerfolg | Könnerschaft |
| **Echo** | Kristall mit Ringen, wachsende Gestalt | sammelt, verbessert, handelt | Spannung, Bindung | Resonanz +30 | Markt, Prestige | Sammlung und Verfeinerung |
| **Element** | Farben, Umweltreaktionen | kombiniert, entdeckt | Erfindergeist | Kombinationen (2–3) | Kampf, Gelände | Entdeckung seltener Kombinationen |
| **Handwerk** | Werkstatt, Meisterstücke | stellt her, forscht | Meisterstolz | Pfade, Verfahren | Ausrüstung aller | Vermächtnis |
| **Wirtschaft** | Märkte, Karren, Schiffe, Firmenzeichen | handelt, führt Betrieb | Verantwortung | Firma, Ruf | Preise, Arbeitsplätze | Aufbau einer Marke |
| **Welt** | Weite, Ruinen, Stadt | erkundet, baut | Staunen | Wissen, Siedlung | Landschaft, Chronik | eine bleibende Spur |

---

## 4. Die gemeinsame Bildsprache

Das Leitmotiv **„Nachhall“** [VORSCHLAG] verbindet alle Systeme: Die Welt behält, was in ihr geschieht. Drei Zeichen kehren wieder: **Ader** (Linie unter der Oberfläche), **Ring** (konzentrische Struktur um einen Kern), **Patina** (Gebrauchsspuren). Sie erscheinen in Wesensformen (Adern), Echos (Ringe), Gegenständen und Gebäuden (Patina), im HUD (Leuchtlinien). Siehe VISUAL_DIRECTION §2.

Stimmung: warm im Licht, kühl im Schatten, Magie als Lichtquelle, klare Silhouetten, sichtbare Geschichte.

---

## 5. Zusammenhänge zwischen den Systemen

```
 Klasse ───────► Bewegung, Rolle, Manifestationen
    │
 Elemente (2–3) ─► Magie, Umweltreaktion ─┐
    │                                      ├─► Kampfecho (Haupttradition + Fremdfähigkeiten)
 Meisterschaft ───► persönliche Handschrift┘          │
                                                   Resonanz +0..30 (sichtbare Entwicklung)
 Berufe/Forschung ► Ausrüstung, Verfahren, Echo-Fassungen, Siegel ─► Markt/Unternehmen
    │
 Gesamtleben ─────► Wesensform (irreversibel, 5 Stufen) ◄── Kampf, Berufe, Entdeckungen
 Welt/Hauptstadt ─► Treffpunkt, Dienste, Siedlungen, Chronik, Epochen
```

Regel: **Kein System darf ein anderes überflüssig machen.** Kämpfer brauchen Handwerker, Händler brauchen Beschützer, Forscher öffnen Wege für alle.

---

## 6. Status der Umsetzung (Ist-Stand, zur Orientierung)

Der Design-Auftrag ändert **keinen** Code. Zur Einordnung, was technisch schon existiert (siehe `docs/IMPLEMENTATION_STATUS.md`):

| Bereich | Stand |
|---|---|
| Server (Python-Referenz) | laufender Prototyp: Kampf, Gegner, CEE (Wesensentwicklung), Siedlungsregeln, Hauptstadt (AP 95, Repo, nicht ausgerollt) |
| Client | Web-Prototyp live; Godot-4-Vertical-Slice (Hauptstadt) rendert auf RunPod, mit einem KI-erzeugten Testgebäude |
| Content | Platzhalter (Regionen, Wesensformen, Gegnerfamilien) |
| Grafik | Konzeptstadium; Zielbild laut Konzepttafeln |

Nichts davon ist Produktionsqualität. Die Dokumente beschreiben die **Zielvision**, nicht den Ist-Zustand.

---

## 7. Empfohlene Reihenfolge der Weiterarbeit [VORSCHLAG]

1. **Stil festlegen** (O1): 3–5 verbindliche Referenzbilder, ein Farbpaletten- und Prompt-Katalog.
2. **Vertical-Slice-Entwurf**: Hauptstadt (fünf Viertel, drei Tore) + ein Dungeon + zwei Gegnerfamilien + ein Boss in Zielqualität.
3. **Charakterkern**: Charaktererstellung, ein Klassen-Set, Wesensform Stufe 1–2 in einer Familie.
4. **Echo-Prototyp** (Visualisierung der Meilensteine +0, +5, +10 zuerst), Telegraphensprache testen.
5. **Handwerk & Markt**: ein Berufspfad (Schmied) bis Meisterstück + Marktansicht.
6. **Erweiterung** nach Messungen (Bildrate, Lesbarkeit, Spielertests).

Jeder Schritt braucht eigene ADRs und Tests; Neues Regelverhalten = neue Regelversion (CLAUDE.md).

---

## 8. Wichtigste offene Entscheidungen (Top 10)

1. Grafikstil (gemalt-stilisiert vs. fotorealistisch) – O1
2. Stufenzählung und Namen der Wesensformen – O2
3. Anzahl und Mischlogik der Wesensformen – O3
4. Fähigkeiten-Slots und Hybridregeln – O6
5. Erfolgs- und Kostenmodell der Resonanz – O7
6. Todesstrafe – O9
7. PvP-Modi – O10
8. Weltgröße und Region-Zahl – O12
9. KI-Asset-Lizenzen und Produktionsweg – O17
10. Spieltitel und Marke – O19

Vollständige Liste: DESIGN_DECISIONS §4.

---

## 9. Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| **Grafikziel zu hoch** für das Team (AAA-Tafeln) | Stufenplan (VISUAL §6), Fokus auf Stil und Wiedererkennung statt Massendetail |
| **Zu viele Systeme gleichzeitig** | Vertical Slice zuerst; jede Säule einzeln validieren |
| **Elementkombinationen unbalancierbar** (36 + 84) | Rollenmodell + Regeln + Signaturkombinationen; Simulation und Telemetrie |
| **Resonanz als Glücksspiel wahrgenommen** | ehrliche Anzeige, Pechschutz, nie zerstören, kein Echtgeld-Boost |
| **Unlesbarer Kampf** durch Effekte | feste Telegraphensprache, Effekt-Ebenen, Gruppenreduktion |
| **Unumkehrbare Wesensform frustriert** | Vorschau, Wartezeit, Transmog, Erklärbarkeit |
| **Wirtschaft kippt** | Senken, kontrollierte Quellen, Telemetrie (BP §41) |
| **Politik schleicht sich ein** | Zurückgestellt, Rathaus nur Verwaltungs-/Archivdienst |
| **Markenähnlichkeit** | eigene Arten und Namen, keine Zitate von Figuren |
| **KI-Assets uneinheitlich** | Prompt-Katalog, Nachbearbeitung, Budgets, Lizenzprüfung |

---

## 10. Kurzcheck gegen die Auftragsvorgaben

| Vorgabe | Wo erfüllt |
|---|---|
| Alle starten als Menschen | D §2 |
| Drei Klassen mit Bewegung, Manifestationen, Endgame-Identität | D §3 |
| Wesensformen, 5 Stufen, irreversibel, individuell, auch aus Berufen | D §5 |
| Neun Elemente, freie Kombination, 2 normal/3 selten | D §4 |
| Third-Person-Kampf, Kampfechos, Resonanz +0..+30 sichtbar | E §2, §7, §8 |
| Große Welt, zehn Biome, Hauptstadt, Städte, Dungeons | C |
| Berufe, Crafting, Forschung, Wirtschaft, Unternehmen, NPC-Mitarbeiter | F |
| Kreaturen und Bosse ohne Recolors | G |
| Moderne UI | H |
| Epochen | C §6.5, F §10 |
| Stadtpolitik zurückgestellt | C §6.1, F §8, I Z1 |
| Labels und keine erfundenen Bestätigungen | alle, besonders I |
| Keine Änderungen an Code, Server, DB, Tests, Engine; kein Deploy | eingehalten, nur Dateien in `docs/design/` |
