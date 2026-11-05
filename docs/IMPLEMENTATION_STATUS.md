# Bestandsabgleich: Master-Blueprint (03.11.2026) gegen den Code

Stand: 2026-11-04, Branch `claude/awesome-dirac-9k6p3n`, Commit-Basis `d32633d`. Quelle der Vorgaben: `docs/MASTER_BLUEPRINT.md` (Kopie von `VISION_2026-11-03.md` auf `main`). Geprüft durch Lesen des Dokuments, Stichwortsuche im Code und den Testlauf (1275 Tests, alle grün, 1 übersprungen). Zeilen mit „nicht im Detail geprüft“ sind Einschätzungen, keine Verifikation.

Legende: **vorhanden** (Code + Tests) · **teilweise** · **fehlt** · **Konflikt** (Blueprint und Repo widersprechen sich, Entscheidung beim Nutzer).

## Charakter und Entwicklung (Teil III–V)
| Blueprint | Stand | Beleg / Lücke |
|---|---|---|
| Alle starten als Mensch, 3 Startklassen | vorhanden | `mmo_cee/identity`, Regeln; Klassennamen sind Arbeitsbezeichnungen |
| Wesensmatrix aus validierter Historie, Hash-Kette, Replay | vorhanden | Character History, Golden Vectors |
| Charakter im Spiel sichtbar (Klasse wählen, Entwicklung ansehen) | vorhanden (neu) | ADR-0038, Fenster „Charakter“ |
| Wesensform dauerhaft, bewusste Annahme | vorhanden | `mmo_cee/essence.py` (Annahme nur einmal, Fehler „dauerhaft“); Vorschau, Prüfung und bestätigte Annahme im Client seit AP 6 (ADR-0045) |
| Drei Schichten: Lebensgeschichte / aktuelles Profil / Wesenidentität sauber getrennt | vorhanden (neu) | `mmo_cee/layers.py`, `docs/DOMAIN_MODEL.md`, ADR-0040; Meilensteine aus Erkundung/Sozialem brauchen AP 3 |
| Wesensformen nicht nur elementar (Beruf, Forschung, Erkundung) | teilweise | 5 Platzhalterformen (`ember_kin` …), Berufs-/Forschungspfade nicht im Detail geprüft |
| Berufe als eigene Domäne (Zweige, Techniken, Rezepte, Meisterstücke) | teilweise | Berufe, Meisterschaftsstufen, 7 Rezepte, Techniken (ADR-0010); Spezialisierungszweige und Meisterstücke seit AP 5 (ADR-0044, abgeleitet, 4 Berufe); Experimente/Respezialisierung fehlen |
| Entdeckungen, Pionier, Lehre | vorhanden | `mmo_cee/discovery`, `mmo_world` (ADR-0009) |
| Anti-Farming (kein sinnloses Wiederholen) | vorhanden | Tages-/Signaldeckel in den Regeln; Spielquellen mit Beutefaktor und Tageslimits (ADR-0041) |
| Spielgeschehen speist Profile (Erfahrung, Elemente, Berufe durch Sammeln, Erkundungshinweise, Prägung) | vorhanden (neu) | ADR-0041, `game_rules_v3.json`; nur 2 Hinweisorte, weitere Quellen offen |
| Klassenspezifische Bewegungsmechaniken, Manifestationen | fehlt | nur Parametermechanik der Visual Evolution (ADR-0008) |

## Kampfecho, Resonanz, Elemente, Kampf (Teil VI–VIII)
| Blueprint | Stand | Beleg / Lücke |
|---|---|---|
| Kampfecho (Haupttradition + Hybrid) | vorhanden (neu) | `mmo_world/echo.py`, ADR-0046; Kampfwirkung seit AP 17 (ADR-0056, Platzhalterwerte); elementare Wirkung und Optik im Kampf offen |
| Resonanz +0..+30, Rückschritt, Schutz, Pechschutz, atomar | vorhanden (neu), Raten/Kosten Platzhalter | Erfolgsraten/Kosten bewusst offen (Frage 8) → konfigurierbar bauen |
| Handelbarkeit: unaktiviert handelbar, aktiviert gebunden, Freigabe | vorhanden (neu) | direkter Handel (ADR-0023) und Markt (ADR-0015) existieren als Grundlage |
| Persönliche Meisterschaft getrennt vom Objekt | vorhanden (neu) | `grant_mastery` je Figur × Tradition, nicht am Objekt |
| 9 Elemente, Paare, Dreifach-Endgame | teilweise | `elements`: alle 9, max. 2 regulär + 1 Endgame-Element ab Stufe 40; **Interaktionen/Klassenabhängigkeit nur als 4 Beispiele** (ADR-0027) |
| Kombinationskatalog 36/84, klassenabhängige Umsetzung, Gegenspiel, Anzeige im Spiel | vorhanden (neu) | ADR-0042; nur beschreibend, Kampfwirkung = AP 4b |
| Elementschaden im Kampf (Stärke/Schwäche/gleich, Sofort- und Zeitschaden) | vorhanden (neu) | `sim_rules_v8` `elements`, ADR-0043; bisher nur `cast_ember` (Feuer); weitere Elementskills offen |
| Ausrüstung mit Wirkung (leicht/schwer) und Transmog getrennt von Werten | vorhanden (neu) | `mmo_world/equipment.py`, ADR-0047; Slots/Seltenheiten/Sets/Rezepte offen, Teile im Client noch nicht gezeichnet |
| Aktives Elementmanagement im Kampf | vorhanden (neu) | AP 16, ADR-0055: Zauber je geprägtem Element, Wechselzeit 40 Ticks; Platzhalterwerte, Dreier-/Domänenskills offen |
| Kombinationszauber (Paar, Dreier) im Kampf | vorhanden (neu) | AP 22, ADR-0061: 36 Paar- und 84 Dreierzauber, bester Elementfaktor, keine Wechselzeit; Domänen-/Klassenwirkung offen, Client ungeprüft |
| Bereichswirkung der Kombinationen | vorhanden (neu) | AP 23, ADR-0062: Kontrolle verlangsamt, Schutz mindert Schaden, Beistand gibt Ausdauer; Klassenumsetzung offen |
| Klassenwirkung der Kombinationen | vorhanden (neu) | AP 24, ADR-0063: Krieger stärkerer Schutz, Bogenschütze längere Verlangsamung, Schamane mehr Ausdauer |
| Bewegungswirkung der Kombinationen | vorhanden (neu) | AP 25, ADR-0064: Wind/Schatten-Kombinationen geben ein kurzes Ausweichfenster |
| Beschwörung und Umgebung der Kombinationen | vorhanden (neu) | AP 26, ADR-0065: Schaden über Zeit +50 %, Gegner taumelt 20 Ticks; ohne eigene Helferfigur |
| Skill-Leiste, Klassen-Kits, Kampfanzeige im Client | vorhanden (neu) | ADR-0039, `game_rules_v2.json`; Kits sind Platzhalter |
| Action-Kampf, Telegraphen, Zustände | teilweise | 1:1-, Gruppen-, Mehrgegner-Kampf, Gegnerfähigkeiten (sim_rules_v7); **Raumkampf/Trefferzonen/PvP fehlen** |
| Dungeons, Weltbosse, Raids | teilweise (neu) | 1 Dungeon (3 Etappen), 1 Gildenraid (AP 18, bis 8 Spieler seit AP 19), Weltboss mit Mitkämpfern/Kiste, ADR-0048/0057/0058; echte Instanzen fehlen |

## Welt, Wirtschaft, Gesellschaft (Teil IX–XIII)
| Blueprint | Stand | Beleg / Lücke |
|---|---|---|
| Gemeinsame Welt, serverautoritativ | vorhanden (Referenz) | Spielserver `mmo_game`, ein Prozess; Mehrregion-Betrieb **fehlt** |
| Gelände, Kollision, Wegfindung | vorhanden | ADR-0030/0031; eine Zone 6000×6000 cm |
| Regionen, Gefahrenstufen, Fortbewegung/Epochen | teilweise (neu) | 7 Regionen mit Gefahr 1–5, Zugangsbedingung, Bonus (ADR-0048); Fortbewegungsstufen fehlen; Weltepochen als Mechanik vorhanden (ADR-0051) |
| Dynamische NPC-Wirtschaft | teilweise | Markt, Preisdynamik (ADR-0015/0017), Weltereignisse mit Preisschocks, Markt-Fenster (ADR-0049); keine NPC-Lebensprofile |
| Spielerunternehmen: Gründung, Personal, Beteiligungen, Produktion | vorhanden (Referenz) | ADR-0012/0016, `company.*`, `production.*` |
| Filialen, Töchter, Offline-Betrieb mit Deckel | teilweise | Filialen + Offline-Deckel + Firmenfenster (ADR-0049); Töchter fehlen. Blueprint: Offline-Produktion im Blueprint ausdrücklich ohne unendliche Geldquelle |
| Forschung, Epochen, Entdecker (Siedlungsebene) | teilweise (neu) | Techniken, Epochensperre, Entdecker-Vorsprung, Lizenz, Übernahme, Fenster (ADR-0051); Epochen-Inhalte, Spezialisierung, Produktionsvorsprung offen |
| Spielerstädte, Grundstücke, Gemeinschaftsprojekte | teilweise | Orte, Grundstücke, Gebäude/Lager, Projekte mit Wirkung (Straße, Lagerhaus, Rathaus), Fenster (ADR-0050); Marktplatz/Mauer/Hafen-Wirkung, Grundstückshandel, Platzierung offen |
| Gilden | teilweise (neu) | Rollen, Kasse, Gildenhaus, Punkte, Fenster (ADR-0052); Gildenforschung und Gildenraid (bis 8 Spieler, ADR-0058) seit AP 18/19 (ADR-0057); Chat, Client-Fenster dafür offen |
| Direkter Handel, Benachrichtigungen | vorhanden | ADR-0023/0024 |
| Weltchronik, Prestige | teilweise (neu) | Chronik mit Erstleistungen, Titel, Ruhmpunkte, Fenster (ADR-0052); seltene Inhalte offen |
| Stadtpolitik | zurückgestellt | nicht bauen |

## Technik (Teil XIV–XVII)
| Blueprint | Stand | Beleg / Lücke |
|---|---|---|
| Lastmessung, Interessenverwaltung, Missbrauchstests | teilweise (neu) | `mmo_game.loadtest`, Sichtgrenze 60 Mitspieler, Fuzz-Invarianten (ADR-0053); echte Netz-/Mehrprozess-Last offen |
| Persistenz, Migration, Backup | vorhanden | ADR-0014/0018/0037, geprüftes Backup + Restore |
| Konten, TLS, Rate-Limits | vorhanden | ADR-0029 |
| Regelversionierung, Golden Vectors | vorhanden | v1–v9 (CEE), sim_rules bis v7 |
| Engine | Unity 6 (bestätigt) | Client mit WebSocket, Kit-Leiste, 12 datengetriebenen Fenstern (ADR-0054); in Unity ungetestet, Übersetzung gegen Nachbildung geprüft |
| Phase-1-Prototyp (Third-Person, Boss, Dedicated Server) | teilweise | Server ja; Third-Person-Client nur Browser (Top-down, Klick-Bewegung) |

## Vorschlag für die Reihenfolge (nach Blueprint §80: kleinster vertikaler Fortschritt zuerst)
1. `docs/DOMAIN_MODEL.md`: Lebensgeschichte / Profil / Wesenidentität explizit trennen (Dokumentation + Tests, ohne Regeländerung).
2. Kampfecho + Resonanz als **Datenmodell + atomare Upgrade-Transaktion** (neue Regelversion; Raten/Kosten als Platzhalter-Konfiguration; Schutz, Pechschutz, kein Zerstören; Duplikat-/Replay-/Race-Tests).
3. Handelbarkeit der Echos (unaktiviert/gebunden/Freigabe) auf Basis von `trade.*`.
4. Elementinteraktionen datengetrieben erweitern (Paare ungeordnet, 36/84 als Test).
5. Berufszweige und Meisterstücke.
6. Danach Welt-/Wirtschaftsausbau (Grundstücke, Stadt, Filialen, Gilden) – je eigene Etappe mit ADR.

## Offene Entscheidungen (Blueprint §57), die vor Bau geklärt sein müssen
Anzahl gleichzeitig ausrüstbarer Echos (Frage 7) · Resonanz-Raten/Kosten (8) · welche Echos serverexklusiv sind (9) · Berufswechsel (10) · Währung/Gebühren (17) · Grundstücksgrößen (18).
