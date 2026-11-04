# ADR-0039: Skill-Leiste, Klassen-Kits und Kampfanzeige (AP 1)

**Status:** angenommen (Spielschicht `mmo_game`; Regeln `game_rules_v2.json`, Platzhalter)

## Kontext
Der Kampf war serverseitig vollständig (Befehle, Abklingzeiten, Ausdauer, Gegnerfähigkeiten), im Browserclient aber nur eine Knopfreihe ohne Rückmeldung. Fähigkeiten werden über Entwicklungsstufen freigeschaltet (Richtungsstufen ab 50 000 Punkten), sodass neue Spieler nur Hieb, Ausweichen, Blocken und Fliehen hatten. Blueprint §27–29: direkte Steuerung, schnelle und schwere Aktionen, Ausweichen, verständliche Oberfläche bei tiefer Systematik.

## Entscheidung
- **Spielregeln v2** (`class_kits`): Jede Grundklasse nutzt im Kampf von Anfang an einige Fähigkeiten (Platzhalter): Krieger `power_strike`, `disrupting_blow`; Bogenschütze `power_strike`, `flowing_step`, `hindering_mark`; Schamane/Alchemist `ember_strike`, `ally_mend`, `ally_ward`, `hindering_mark`. Die Kits gelten **nur im Kampf** (`EncounterServer.pack_specs(..., extra_equipped)`): erlaubte Befehle und Fähigkeitseffekte der Simulation; die CEE-Ausrüstung und ihre Plätze bleiben unverändert. Ohne Klasse gilt weiter nur die Grundausstattung. Bericht und Neuberechnung nutzen dieselben Spezifikationen (Test: Live-Ergebnis == Neuberechnung).
- **`game.kit`** (lesend) und `fight_start.kit`: Befehl, Ausdauerkosten, Sperrzeit, Abklingzeit und Art (Angriff/Verteidigung/Kontrolle/Unterstützung) je verfügbarem Befehl, `stamina_max`. `fight_start.enemy_ids` ordnet die Gegner der Anzeige zu.
- **Client:** Skill-Leiste (Tasten 1–9, 0, Q; Leertaste = Ausweichen; Klick), Anzeige von Abklingzeit, Sperrzeit und Ausdauermangel, Lebens-/Ausdauerleiste, Lebensbalken über Gegnern und Mitspielern, Zielwahl per Klick (`target_n`) mit Zielring, Wirkleiste und Warnring bei Gegnerfähigkeiten, einfache Effekte je Befehl, Klick-Bewegung bleibt außerhalb des Kampfes. Der Client sagt nur voraus (Sperre, Abklingzeit), der Server entscheidet; jede Serverantwort überschreibt die Anzeige.

## Folgen
- Bestehende Abfragen, Golden Vectors und Regelversionen CEE/sim sind unverändert; geändert wurde nur `game_rules_v2.json` (neue Datei, v1 bleibt) und der Standardname in `load_game_rules`.
- Offen (spätere Pakete bzw. 3D-Client): Kamera/Springen, Richtungsangriffe, aufgeladene und kanalisierte Fähigkeiten, Kombos, Waffen-/Rüstungsoptionen, Elementarfähigkeiten für alle Klassen (AP 4), Fähigkeiten-Ausrüstung im Client (`combat.set_loadout`), PvP.
- Kits sind Platzhalter, keine bestätigten Skilllisten (Blueprint §57 Frage 3).
