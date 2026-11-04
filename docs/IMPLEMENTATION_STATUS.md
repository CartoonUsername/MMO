# Bestandsabgleich: Master-Blueprint (03.11.2026) gegen den Code

Stand: 2026-11-04, Branch `claude/awesome-dirac-9k6p3n`, Commit-Basis `d32633d`. Quelle der Vorgaben: `docs/MASTER_BLUEPRINT.md` (Kopie von `VISION_2026-11-03.md` auf `main`). Geprüft durch Lesen des Dokuments, Stichwortsuche im Code und den Testlauf (1275 Tests, alle grün, 1 übersprungen). Zeilen mit „nicht im Detail geprüft“ sind Einschätzungen, keine Verifikation.

Legende: **vorhanden** (Code + Tests) · **teilweise** · **fehlt** · **Konflikt** (Blueprint und Repo widersprechen sich, Entscheidung beim Nutzer).

## Charakter und Entwicklung (Teil III–V)
| Blueprint | Stand | Beleg / Lücke |
|---|---|---|
| Alle starten als Mensch, 3 Startklassen | vorhanden | `mmo_cee/identity`, Regeln; Klassennamen sind Arbeitsbezeichnungen |
| Wesensmatrix aus validierter Historie, Hash-Kette, Replay | vorhanden | Character History, Golden Vectors |
| Charakter im Spiel sichtbar (Klasse wählen, Entwicklung ansehen) | vorhanden (neu) | ADR-0038, Fenster „Charakter“ |
| Wesensform dauerhaft, bewusste Annahme | vorhanden | `mmo_cee/essence.py` (Annahme nur einmal, Fehler „dauerhaft“); Vorschau der Folgen im Client **fehlt** |
| Drei Schichten: Lebensgeschichte / aktuelles Profil / Wesenidentität sauber getrennt | vorhanden (neu) | `mmo_cee/layers.py`, `docs/DOMAIN_MODEL.md`, ADR-0040; Meilensteine aus Erkundung/Sozialem brauchen AP 3 |
| Wesensformen nicht nur elementar (Beruf, Forschung, Erkundung) | teilweise | 5 Platzhalterformen (`ember_kin` …), Berufs-/Forschungspfade nicht im Detail geprüft |
| Berufe als eigene Domäne (Zweige, Techniken, Rezepte, Meisterstücke) | teilweise | Berufe, Meisterschaftsstufen, 7 Rezepte, Techniken (ADR-0010); **Spezialisierungszweige und Meisterstücke fehlen** |
| Entdeckungen, Pionier, Lehre | vorhanden | `mmo_cee/discovery`, `mmo_world` (ADR-0009) |
| Anti-Farming (kein sinnloses Wiederholen) | vorhanden | Tages-/Signaldeckel in den Regeln; Spielquellen mit Beutefaktor und Tageslimits (ADR-0041) |
| Spielgeschehen speist Profile (Erfahrung, Elemente, Berufe durch Sammeln, Erkundungshinweise, Prägung) | vorhanden (neu) | ADR-0041, `game_rules_v3.json`; nur 2 Hinweisorte, weitere Quellen offen |
| Klassenspezifische Bewegungsmechaniken, Manifestationen | fehlt | nur Parametermechanik der Visual Evolution (ADR-0008) |

## Kampfecho, Resonanz, Elemente, Kampf (Teil VI–VIII)
| Blueprint | Stand | Beleg / Lücke |
|---|---|---|
| Kampfecho (Haupttradition + Hybrid) | **fehlt** | keine Treffer im Code |
| Resonanz +0..+30, Rückschritt, Schutz, Pechschutz, atomar | **fehlt** | Erfolgsraten/Kosten bewusst offen (Frage 8) → konfigurierbar bauen |
| Handelbarkeit: unaktiviert handelbar, aktiviert gebunden, Freigabe | **fehlt** | direkter Handel (ADR-0023) und Markt (ADR-0015) existieren als Grundlage |
| Persönliche Meisterschaft getrennt vom Objekt | fehlt | – |
| 9 Elemente, Paare, Dreifach-Endgame | teilweise | `elements`: alle 9, max. 2 regulär + 1 Endgame-Element ab Stufe 40; **Interaktionen/Klassenabhängigkeit nur als 4 Beispiele** (ADR-0027) |
| Kombinationskatalog 36/84, klassenabhängige Umsetzung, Gegenspiel, Anzeige im Spiel | vorhanden (neu) | ADR-0042; nur beschreibend, Kampfwirkung = AP 4b |
| Aktives Elementmanagement im Kampf | fehlt | offen (Frage 6) |
| Skill-Leiste, Klassen-Kits, Kampfanzeige im Client | vorhanden (neu) | ADR-0039, `game_rules_v2.json`; Kits sind Platzhalter |
| Action-Kampf, Telegraphen, Zustände | teilweise | 1:1-, Gruppen-, Mehrgegner-Kampf, Gegnerfähigkeiten (sim_rules_v7); **Raumkampf/Trefferzonen/PvP fehlen** |
| Dungeons, Weltbosse, Raids | fehlt | ein Boss-Typ (Steinherz-Koloss) als Gegnervorlage |

## Welt, Wirtschaft, Gesellschaft (Teil IX–XIII)
| Blueprint | Stand | Beleg / Lücke |
|---|---|---|
| Gemeinsame Welt, serverautoritativ | vorhanden (Referenz) | Spielserver `mmo_game`, ein Prozess; Mehrregion-Betrieb **fehlt** |
| Gelände, Kollision, Wegfindung | vorhanden | ADR-0030/0031; eine Zone 6000×6000 cm |
| Regionen, Gefahrenstufen, Fortbewegung/Epochen | fehlt | – |
| Dynamische NPC-Wirtschaft | teilweise | Markt, Preisdynamik (ADR-0015/0017); NPC-Händler minimal, keine NPC-Lebensprofile |
| Spielerunternehmen: Gründung, Personal, Beteiligungen, Produktion | vorhanden (Referenz) | ADR-0012/0016, `company.*`, `production.*` |
| Filialen, Töchter, Offline-Betrieb mit Deckel | fehlt | Offline-Produktion im Blueprint ausdrücklich ohne unendliche Geldquelle |
| Spielerstädte, Grundstücke, Gemeinschaftsprojekte | fehlt | keine Treffer |
| Gilden | fehlt | Gruppen (Party, ADR-0025) existieren |
| Direkter Handel, Benachrichtigungen | vorhanden | ADR-0023/0024 |
| Weltchronik, Prestige | fehlt | – |
| Stadtpolitik | zurückgestellt | nicht bauen |

## Technik (Teil XIV–XVII)
| Blueprint | Stand | Beleg / Lücke |
|---|---|---|
| Persistenz, Migration, Backup | vorhanden | ADR-0014/0018/0037, geprüftes Backup + Restore |
| Konten, TLS, Rate-Limits | vorhanden | ADR-0029 |
| Regelversionierung, Golden Vectors | vorhanden | v1–v9 (CEE), sim_rules bis v7 |
| Engine | **Konflikt** | Blueprint: Unreal „bevorzugte Kandidatin“ (VORSCHLAG, Frage 23 offen). Repo: Unity 6 Client (`client/unity`, in Unity ungetestet) + Browser-Testclient. Entscheidung beim Nutzer |
| Phase-1-Prototyp (Third-Person, Boss, Dedicated Server) | teilweise | Server ja; Third-Person-Client nur Browser (Top-down, Klick-Bewegung) |

## Vorschlag für die Reihenfolge (nach Blueprint §80: kleinster vertikaler Fortschritt zuerst)
1. `docs/DOMAIN_MODEL.md`: Lebensgeschichte / Profil / Wesenidentität explizit trennen (Dokumentation + Tests, ohne Regeländerung).
2. Kampfecho + Resonanz als **Datenmodell + atomare Upgrade-Transaktion** (neue Regelversion; Raten/Kosten als Platzhalter-Konfiguration; Schutz, Pechschutz, kein Zerstören; Duplikat-/Replay-/Race-Tests).
3. Handelbarkeit der Echos (unaktiviert/gebunden/Freigabe) auf Basis von `trade.*`.
4. Elementinteraktionen datengetrieben erweitern (Paare ungeordnet, 36/84 als Test).
5. Berufszweige und Meisterstücke.
6. Danach Welt-/Wirtschaftsausbau (Grundstücke, Stadt, Filialen, Gilden) – je eigene Etappe mit ADR.

## Offene Entscheidungen (Blueprint §57), die vor Bau geklärt sein müssen
Engine (Unreal oder Unity) · Anzahl gleichzeitig ausrüstbarer Echos (Frage 7) · Resonanz-Raten/Kosten (8) · welche Echos serverexklusiv sind (9) · Berufswechsel (10) · Währung/Gebühren (17) · Grundstücksgrößen (18).
