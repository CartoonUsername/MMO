# ÜBERGABE-PROMPT – MMORPG-Projekt, Stand der Engines (Referenzimplementierung)

Du übernimmst die technische Entwicklung eines langfristig geplanten Free-to-Play-3D-Action-MMORPGs (Windows-PC zuerst, realistische Fantasygrafik, Third-Person-Action-Kampf). Arbeite als Lead Developer/Architekt: bestehenden Code zuerst verstehen, dann in kleinen, getesteten Schritten erweitern. Antworte dem Benutzer auf Deutsch; Erklärungen jeweils in einem Satz.

## 1. Repository und Zustand (verifiziert)
- Repo `CartoonUsername/MMO`, Arbeitsbranch `claude/awesome-dirac-9k6p3n` (aktueller Stand: `git log -1`). Niemals direkt auf `main` arbeiten, kein Force-Push, keine Merges/PRs ohne Auftrag, kleine nachvollziehbare Commits (Co-Author-Zeilen laut Systemvorgabe).
- Alles liegt unter `reference/python/` (nur Python-Standardbibliothek, `unittest`, keine externen Abhängigkeiten). **723 Tests, alle grün.** Befehlsschicht des Server-Protokolls: `reference/python/mmo_server/`, Planung `docs/PROTOCOL.md`. Golden Vectors: `reference/golden` (24 CEE-Szenarien), `reference/golden_sim` (96 Fälle), `reference/golden_visual` (21 Fälle), `reference/golden_world` (14 Weltseiten-Szenarien inkl. Markt, Firmenproduktion, Preisdynamik und Regelversions-Migration, Welt-Hash je Schritt).
- Prüfen vor jeder Arbeit: `git status`, dann `cd reference/python && python -m unittest discover -s . -t . -v`, `python -m mmo_cee.golden check ../golden`, `python -m mmo_sim.golden check ../golden_sim`, `python -m mmo_cee.golden_visual check ../golden_visual`, `python -m mmo_world.golden check ../golden_world`.
- Dokumentation: `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/STATUS_REPORT.md`, `docs/decisions/ADR-0001…0012`, `reference/golden/README.md` (Format und Prüfverfahren für Portierungen), `Game/PRODUCTION_READINESS.md`, `Game/WINDOWS_SETUP_CHECKLIST.md`, `Game/ENGINE_COMPARISON_PROTOCOL.md`.
- Wichtige Commits: `ba3d1b0` Kern + Identity/Element/Profession/Essence · `062b52c` Combat Development · `c6c5069` Golden Vectors · `aed6ca6` Kampfsimulation `mmo_sim` · `4a2a156` Wesensbewertung · `2efc9c3` Visual Evolution · `ee32e2c` Discovery · `ad54492` Crafting · danach Economic Profile (siehe `git log`).

## 2. Bestätigte Spielentscheidungen (nicht eigenmächtig ändern)
- Jeder Spieler und NPC beginnt als Mensch. Entwicklung ausschließlich aus der Spielhistorie der Figur (keine Analyse realer Personen); Spieler und NPCs laufen durch dieselbe Pipeline; serverautoritativ, nachvollziehbar, versionierbar.
- Startklassen: Krieger, Schamane/Alchemist, Bogenschütze. Grundklasse bleibt Identität.
- Neun Elemente (Feuer, Wasser, Schatten, Licht, Wind, Erde, Elektro, Eis, Natur); freie Kombinationen ohne feste Paare; regulär 2, selten 3 (Endgame).
- Wesensform dauerhaft, per Prüfung und bewusster Entscheidung angenommen; Vor- und Nachteile; alle Pfade konkurrenzfähig.
- Berufe sind vollwertige Fortschrittssysteme; Spieler entdecken eigene Verfahren/Rezepte/Techniken. Erste Entdecker: Anerkennung + zeitlich begrenzter Vorsprung, nie dauerhafte Blockade, kein dauerhaftes Pay-to-win.
- Kein stumpfes Wiederholen: Diminishing Returns, Begegnungs-/Berichtsvalidierung, Limits. Deterministische, nachvollziehbare Regeln (kein unkontrollierter Zufall im Kampf).
- Kampfechos (Resonanz +0…+30, handelbar, Siegel, Schutz/Pity), Unternehmen/Wirtschaft, Spielerstädte, Technologieentwicklung: **bestätigt als Vision, noch nicht implementiert**. Stadtpolitik ausdrücklich vertagt.
- Alles in den Regeldateien (konkrete Formen, Entdeckungen, Rezepte, Zahlen, Optik) ist **Platzhalter/Vorschlag**, keine beschlossenen Spielinhalte – immer so kennzeichnen.

## 3. Architektur (Leitprinzipien)
1. **Event Sourcing mit Hash-Kette je Charakter** (`history.py`): Zustand ist nur Ableitung (Replay) aus append-only Ereignissen (Charakter-ID, seq, Typ, Payload, `rules_version`, `schema_version`, prev_hash, hash). Abgelehnte Ereignisse werden nicht aufgezeichnet und ändern nichts.
2. **Engines** (`engine.py`): je ein Teilzustand `state.parts[name]`, `validate` (wirft `RuleViolation`) und `apply`. Engines sind nur aktiv, wenn die Regeln den passenden Abschnitt enthalten (ältere Regelversionen bleiben bit-identisch lauffähig).
3. **Daten statt Code**: Regeln in versionierten JSON-Dateien (`mmo_cee/data/rules_v1…v7.json`, `visual_rules_v1.json`, `mmo_sim/data/sim_rules_v1.json`, `mmo_world/data/company_rules_v1.json`). Regelversionen sind **unveränderlich**; Erweiterung = neue Datei. Regeln werden beim Start auf Konsistenz geprüft.
4. **Ganzzahlen** (Promille, Floor-Division) für bit-identische Ergebnisse bei einer späteren Portierung (C++/C#/Rust). Keine Gleitkommazahlen in Regeln/Zuständen.
5. **Vertrauensgrenze**: Der Client sendet nie Fortschritt. Berichte (Kampf, Herstellung), Entscheidungen, Beweise, Prüfungen und Lehren kommen vom Spielserver; die Engines begrenzen Schaden (Eindeutigkeit, Raten, Limits, Reihenfolge), können Fälschungen mit plausiblem Inhalt aber nicht erkennen.
6. **Anti-Farming-Muster** (Kampf, Handwerk): serverseitig vergebene eindeutige IDs je Figur, strikte Payload-Felder, Plausibilitätsgrenzen, Wiederholungsabnahme je Gegner/Rezept und Tag, Tageslimits (voll → reduziert → hart). Mit den Standardwerten greift die Wiederholungsabnahme deutlich vor dem Tageslimit (Balancing-Hinweis).
7. **Replay-Schutz**: `RulesVersionMismatch`, wenn ein Log unter anderer Regelversion abgespielt/fortgesetzt wird (Migration zwischen Versionen ist offen).
8. **Referenz + Golden Vectors**: Python ist Regel-/Testorakel; produktive Engine muss alle Vektoren bit-identisch bestehen (Format: `reference/golden/README.md`). Keine parallelen, abweichenden Regelimplementierungen.

## 4. Stand der zehn CEE-Engines (alle als Referenz umgesetzt)
| # | Engine | Status | Kern |
|---|---|---|---|
| 1 | Identity | fertig | Spieler/NPC, Klasse (einmalig), XP/Level (max 50) |
| 2 | Essence (Wesen) | fertig | v1–v3 hartes Schema; **v4+ gewichtete Belege** (Elemente, Kampfrichtung, Beruf, Entscheidung, Entdeckung) mit Schwelle; kein Einzelsignal genügt; `essence.decision_made` (einmalig, endgültig); Vor-/Nachteile mit Bandbreitenprüfung; geheime Formen nur über Entdeckungen (`requires_discoveries`) |
| 3 | Combat Development | fertig | `combat.encounter_resolved`; sechs vorläufige Dimensionen (Kraft, Präzision, Mobilität, Kontrolle, Verteidigung, Unterstützung); Richtungen abgeleitet, nicht exklusiv, Punkte sinken nie |
| 4 | Element | fertig | 9 Elemente, Prägung ab Affinität, 2+1-Limit (3. ab Stufe 40) |
| 5 | Profession | fertig | Erfahrung → Meisterschaft 0–10 |
| 6 | Discovery | fertig | Beweise (eindeutig je Figur), Abschluss mit Anerkennung (Pionier/Entdecker), Lernen nur bei teilbaren; Wissensketten (azyklisch geprüft) |
| 7 | Crafting | fertig | `crafting.crafted`; Dimensionen Menge/Feinarbeit/Innovation/Infusion, Materialfamilien, Element-Infusion, Qualitäts-Plausibilität, nicht-exklusive Handwerksrichtungen |
| 8 | Economic Profile | fertig | `economy.trade_completed` (Referenzwert exakt aus Regeltabelle, Preisband, Wiederholungsabnahme je Handelspartner, Netzwerkbonus nur für qualifizierte Partner, kein Selbsthandel), `economy.career_changed` (Karriereleiter mit Meisterschaft/Dienstzeit/Punkten, Beförderung nur eine Stufe, Firmenwechsel nur nach Austritt), `economy.company_founded/closed` (Gate, Höchstzahl, IDs nie wiederverwendbar); Handelsrichtungen nicht-exklusiv. **Firmensimulation und Märkte fehlen noch.** |
| 9 | Character History | fertig | Log, Hash-Kette, Verifikation, Replay |
| 10 | Visual Evolution | fertig | reine Ableitung Zustand → Erscheinungsparameter (Skelett/Body-Set, Morphs, Materialien, VFX, Farben, Teile, Animations-Tags, Hash); freie Elementmischung der Aura; stabile individuelle Variation je Figur-ID; `appearance_diff` |

Regelversionen: v1 Basis ohne Kampf · v2 + `combat` · v3 + Wesensform mit Kampfrichtungs-Voraussetzung · v4 + Wesensbewertung/Entscheidungen · v5 + Entdeckungen (+ geheime Form) · v6 + Handwerk · **v7 + Wirtschaft (Standard)**. `visual_rules_v1` verlangt CEE-Regeln ≥ v4.

## 5. Serverseitige Weltlogik (Pakete neben der CEE)
- **`mmo_sim`** (Kampfkern): deterministische 1:1-Simulation, 10 Ticks/s, ganzzahlig, kein Zufall. Client sendet nur Befehle (`light, heavy, dodge, block, stun, slow, flee`); Treffer/Ausweichen/Parade/Betäubung entscheidet die Simulation. `EncounterServer` vergibt Begegnungs-IDs, bestimmt Gegner/Stufe/Tag, einmaliger Abschluss, Besitzerbindung. Verträglichkeit mit den CEE-Raten rechnerisch (`check_compatibility`) und per Spam-/Timing-Tests belegt.
- **`mmo_world.DiscoveryRegistry` + `DiscoveryService`**: Pionier, Halter, **endliches Lehrfenster** (nur der Pionier darf lehren; danach jeder Halter); unabhängige Forschung ist immer möglich; persönliche Entdeckungen nie lehrbar; transaktional mit der CEE (Rollback).
- **`mmo_world.Inventory` + `CraftingService`**: atomares Inventar (keine negativen Bestände), Herstellung deterministisch: Voraussetzungen → Qualität → Eingaben entnehmen → CEE-Bericht → Ausgaben; vollständiger Rollback; Berufserfahrung nur aus gedeckelten Punkten; ohne Material keine Produktion.
- **`mmo_world.TradeService`**: Handel zwischen zwei Figuren mit atomarer Übertragung von Ware und Münzen (`Inventory.apply_many`), beide CEE-Berichte vorab validiert, Rückbuchung bei Ausfall; Währung `coin@gold` entsteht nur serverintern; Ware und Münzen werden über viele Handel erhalten (Test).
- **`mmo_world.CompanyRegistry` + `CompanyService`** (Firmensimulation, ADR-0012): Kasse als Inventarkonto, Gebäudelevel (Kapazität) getrennt vom Unternehmenslevel (aus Umsatz), Mitarbeiter = Figuren (Spieler/NPC gleich) mit Gehalt, Gewinnbeteiligung, Zufriedenheit, Loyalität, persönlichem Ziel, Warnung → Kündigungsabsicht → Kündigung; Tagesabschluss (`advance_day`); **Abwerben** als transparente, zufallsfreie Entscheidung; **Anteile** mit Vorkaufsrecht (nur Gesellschafter in der Frist), Offenlegungsbestätigung vor dem Kauf, Mitarbeiterbeteiligung mit Obergrenze; **Gesellschafterbeschlüsse** (Stimmgewichte als Snapshot, Gründer-Veto, Geschäftsführer bestellen/abberufen → CEE-Beförderung); Eigentümer ≠ Geschäftsführer; Schließung mit anteiliger Liquidation. Laufbahn/Gründung laufen über die CEE-Ereignisse; ein Test prüft für jede Figur Register == CEE.

## 6. Qualitätsstandard (bitte beibehalten)
- Jede wichtige Funktion mit `unittest`-Tests (ungültige Eingaben, Duplikate, NPCs, Replay, Determinismus, Rollback), Regeländerungen nur als neue Regelversion, Architekturentscheidungen in ADRs, Doku im selben Commit.
- **Mutationstests** nach jedem Baustein (Schutzmechanismen testweise ausbauen; Tests müssen fehlschlagen). Überlebende Mutanten = Testlücke schließen. Nach Mutationsläufen `__pycache__` löschen (veraltete Bytecode-Caches täuschen).
- Doku-Skripte mit harten Assertions ausführen und erst nach Erfolg committen.
- Vor jedem Commit: gesamte Suite + alle Golden-Prüfungen grün; neue Verhaltensänderung = neue Regelversion + Vektoren neu erzeugen; bisherige Vektoren müssen byte-identisch bleiben.

## 7. Bekannte offene Punkte
- Aufträge/Kunden und Lieferketten der Firmen, Filialen/Töchter, Dividenden, regionale Märkte/Logistik/Weltereignisse als Preisauslöser, Spielerstädte, Technologie-Etablierung je Region, Kampfechos – nicht begonnen. Der Unternehmenslevel hat noch keine Wirkung; Golden Vectors der Weltseite sind vorhanden (ADR-0013).
- Kampf: nur 1:1, kein Raum/Winkel, keine Unterstützungsaktionen/Gruppen in der Simulation (die CEE kennt `ally_heal`/`ally_shield`). Fähigkeiten (Regeln v9, ADR-0020) sind freischalt- und ausrüstbar und geben Simulationsbefehle frei (`heavy`, `stun`, `slow`); ihre Wirkung als passive Modifikatoren steht in `sim_rules_v2.json` (ADR-0021: Schaden, Betäubung/Verlangsamung, Block, Parade, Ausweichen, Ausdauer, erlittener Schaden); eigene Fähigkeitsbefehle (Kosten/Abklingzeit/Zustände), Gruppen-/Unterstützungsfähigkeiten und Elementfähigkeiten fehlen noch.
- Handwerk: Werkzeuge/Werkstätten, Herstellungsdauer, Materialgewinnung, Experimentieren, Rezepte als Gegenstand fehlen.
- Wesen/Visual: Wirkung der Modifikatoren auf Kampf/Bewegung; echte Optik/Assets; Ausrüstung/Kosmetik; Übergangsanimationen; Handwerksrichtungen noch nicht an Wesen/Visual angebunden.
- Produktive Datenbank, Archivierung gewerteter Begegnungs-IDs, Betrieb der Regelversions-Migration (Mechanismus in ADR-0018; Snapshot-Referenz vorhanden), Besitzjournal für das Inventar, Server-Protokoll (Transport, Anmeldung, Push, Echtzeit-Kampfkanal; Befehlsschicht steht), Mehrfachaccounts/Boosting.
- Balancing-Hinweise: Wiederholungsabnahme dominiert Tageslimits; Ausdauer begrenzt in der Kampfsimulation kaum.

## 8. Engine- und Infrastrukturstand
- **Spiel-Engine nicht entschieden**: Unreal Engine 5.8.4 vs. Unity 6 URP. Kein Unreal-/Unity-Code existiert. Vergleichsprotokoll als Entwurf: `Game/ENGINE_COMPARISON_PROTOCOL.md` (Randbedingungen: Unity 6 Linux-Editor nur Ubuntu 22.04/24.04; Lizenzaktivierung ohne Fenster ungeklärt; Unreal 5.8 unter Linux riskant). Windows-Einrichtung und Unreal-MCP-Plugin-Recherche: `Game/PRODUCTION_READINESS.md`, `Game/WINDOWS_SETUP_CHECKLIST.md`. Keine irreversible Engine-Entscheidung ohne belastbare Messwerte.
- Der Benutzer hat keinen leistungsfähigen eigenen PC. RunPod-GPU-Pod (Kosten ca. 0,9–1,2 USD/h, Guthaben knapp; Container-Disk flüchtig) wurde getestet: Vulkan headless auf der GPU funktioniert, das Desktop-Template (Ubuntu 20.04, VNC) ist für Engine-Tests ungeeignet. Hilfsskript `Tools/runpod/pod_check.sh`. **Keine kostenpflichtigen Dienste ohne ausdrückliche Zustimmung starten; Pod nach Tests stoppen.** Budget für Cloud-Infrastruktur: 5–10 €/Monat.
- Diese Sandbox ist eine Cloud-Linux-Umgebung ohne GPU und ohne Zugang zu RunPod/SSH; niemals private Schlüssel, Passwörter oder Tokens anfordern oder im Repo/Chat speichern.

## 9. Vorgeschlagene nächste Schritte (Vorschläge, nicht beschlossen)
1. **Betriebsentscheidungen zur Migration** (wann/für wen: Wartung, Login, Schonfrist; Standard-Regeln auf v8?) und Besitzjournal für das Inventar; der Mechanismus (Migrationsereignis, Mehrversions-Replay, Welt-Upgrade) ist umgesetzt (ADR-0018); Persistenz-Referenz (Snapshots, Generationen, Ladeprüfung) und Golden Vectors der Weltseite sind erledigt (ADR-0013/0014).
2. Aufträge/Kunden und Lieferketten für Firmen; Orderbuch (ADR-0015), Firmenproduktion (ADR-0016) und Preisdynamik mit CEE-Regeln v8 und NPC-Händler (ADR-0017) sind erledigt. Weiter: regionale Preise, Weltereignisse als Schock-Auslöser, Logistik.
3. Snapshots/Archivierung und Regel-Migration.
4. Server-/Protokoll: Befehlsschicht ist umgesetzt (ADR-0019); offen sind Transport (WebSocket/TLS?), Anmeldung, Push-Ereignisse, direkter Zwei-Parteien-Handel, Echtzeit-Kampfkanal, Datenbank/Regionen und der Übergang zur Engine-Phase; Engine-Vergleich nur mit klarem Budget.
5. Kampf erweitern: eigene Fähigkeitsbefehle, Gruppen, Unterstützung, Raum; Kampfechos als eigenes System konzipieren. (Fähigkeiten/Ausrüstung: ADR-0020 erledigt.)

## 10. Arbeitsregeln
Keine unnötigen Rückfragen bei rein technischen Entscheidungen; Spielentscheidungen nicht eigenmächtig verändern; Vorschläge und Platzhalter deutlich markieren; nichts als fertig deklarieren, was nur Schnittstelle ist; ehrlich über Testergebnisse, Fehlschläge und Grenzen berichten; bestehende Module nicht überschreiben, sondern abwärtskompatibel erweitern.
