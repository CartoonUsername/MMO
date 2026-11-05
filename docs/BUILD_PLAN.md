# Bauplan: Master-Blueprint in Arbeitspaketen

Quelle: `docs/MASTER_BLUEPRINT.md` (03.11.2026). Reihenfolge folgt den Phasen des Blueprints (§59–64) und der Vorgabe §80 „kleinster vertikaler Fortschritt zuerst“. **Immer nur ein Paket in Arbeit.** Jedes Paket endet mit: Tests, ADR, aktualisierter `docs/IMPLEMENTATION_STATUS.md`, Commit, danach Bereitstellung nach Freigabe. Neue Regelwirkungen → neue Regelversion, alte Golden Vectors bleiben. Alle Zahlen Platzhalter, offene Fragen (§57) werden nicht still entschieden.

| AP | Inhalt | Blueprint | Phase | Status |
|---|---|---|---|---|
| 1 | **Kampfsystem spielbar**: Skill-Leiste mit Tasten, Klassen-Kits, Abklingzeiten/Ausdauer sichtbar, Lebens-/Zielanzeige, Effekte, Zielwahl per Klick | §27–29, §60 | 1 | fertig, wartet auf Bereitstellung (ADR-0039) |
| 2 | Datenmodell Charakter: Lebensgeschichte / aktuelles Profil / Wesenidentität (`docs/DOMAIN_MODEL.md`, Tests) | §12, §70.1–2 | 0/1 | fertig, wartet auf Bereitstellung (ADR-0040) |
| 3 | Spielgeschehen füttert die Profile (Sammeln→Beruf, Erkundung, Elemente), Anti-Farming bleibt | §9, §10, §70.3 | 1/2 | fertig, wartet auf Bereitstellung (ADR-0041) |
| 4 | Elementarsystem: 36 Paare / 84 Dreier, Interaktionen, klassenabhängige Wirkung, Elementmanagement im Kampf | §22–26, §74 | 2/3 | **4a fertig** (Katalog, ADR-0042); **4b fertig** (Elementschaden, ADR-0043); Rest: Dreier-/Domänenskills und Elementmanagement (Frage 6 offen) |
| 5 | Berufe: Spezialisierungszweige, Techniken, Meisterstücke | §14–16, §71 | 2/3 | **fertig** (Zweige & Meisterstücke abgeleitet, ADR-0044); Experimente/Respezialisierung offen |
| 6 | Fähigkeiten und Wesensformen als Definitionen; Prüfung, Vorschau, irreversible Annahme im Client | §11, §72 | 2 | **fertig** (Definitionen, Vorschau, bestätigte Annahme, ADR-0045) |
| 7 | Kampfecho und Resonanz +0..+30 (atomar, Schutz, Pechschutz), Handelbarkeit, Meisterschaft | §17–21, §73 | 2/3 | **fertig** (Datenmodell, atomare Resonanz, Handel, Meisterschaft, Client; ADR-0046); Kampfwirkung der Echos offen |
| 8 | Ausrüstung und Transmog | §31 | 2/3 | **fertig** (Slots, Wirkung in Kampf/Bewegung, Transmog, Client; ADR-0047); Rezepte/Sets/Darstellung offen |
| 9 | Welt: Regionen, Gegnervielfalt, Dungeon, Weltboss, Gefahrenstufen | §32–35, §60–61 | 2 | **fertig** (Regionen/Gefahr, Zugangsbedingung, Dungeon, Weltboss; ADR-0048); echte Instanzen/Reisepunkte offen |
| 10 | Wirtschaft: NPC-Wirtschaft, Unternehmen (Filialen, Töchter, Offline-Betrieb mit Deckel) | §38–41, §75 | 3 | fertig (ADR-0049; Töchter offen) |
| 11 | Besitz: Grundstücke, Spielerstädte, Gemeinschaftsprojekte | §36–37 | 2/3 | fertig (ADR-0050; Teilwirkungen offen) |
| 12 | Forschung, Epochen, Entdecker | §42–44 | 3/5 | fertig (ADR-0051; Epochen-Inhalte offen) |
| 13 | Gilden, Prestige, Weltchronik (Stadtpolitik zurückgestellt) | §45, §47–49 | 3 | fertig (ADR-0052; Raids, Gildenforschung offen) |
| 14 | Server: Regionen/Instanzen, Skalierung, Last- und Exploit-Tests | §50–55, §63 | 4 | fertig (ADR-0053; Verteilung bewusst nicht gebaut) |
| 15 | Engine-Client (Unity 6, vom Nutzer bestätigt) | §50, §77 | 1–2 | Unity 6 gewählt; Code fertig, in Unity ungetestet (ADR-0054) |
| 16 | Aktives Elementmanagement im Kampf | §26, §74 | 2/3 | **fertig** (Zauber je Element, Wechselzeit; ADR-0055); Dreier-/Domänenskills offen |
| 17 | Kampfwirkung der Kampfechos (Resonanz, Meisterschaft, Fähigkeiten) | §17–21, §73 | 2/3 | **fertig** (echo_rules_v2, ADR-0056); Elementwirkung/Optik im Kampf offen |
| 18 | Gilden-Raids und Gildenforschung | §45, §47–49 | 3 | **fertig** (ADR-0057; Client-Fenster offen) |
| 19 | Größere Kampfgruppen (Raid/Weltboss bis 8) | §33–35, §45, §55 | 3/4 | **fertig** (sim_rules_v10, game_rules_v12, ADR-0058); Balancing und Client-Anzeige offen |
| 20 | Client-Fenster für AP 16–19 (Browser, Unity-Gildenfenster) | §26–29, §45 | 2/3 | **fertig, im Browser/Unity ungetestet** (ADR-0059; statische Tests) |
| 21 | Raid-Balancing nach Gruppengröße (Mindestgröße 4, Etappen nach Größe) | §45, §55 | 3/4 | **fertig** (game_rules_v13, ADR-0060); Richtwerte aus Bots, echte Spieltests offen |
| 22 | Kombinationszauber im Kampf (Paare, Dreier ab Endgame) | §22–26, §74 | 2/3 | **fertig** (sim_rules_v11, game_rules_v14, ADR-0061); Klassen-/Bereichswirkung, Client-Prüfung offen |
| 23 | Bereichswirkung der Kombinationen (Kontrolle, Schutz, Beistand) | §22–26, §74 | 2/3 | **fertig** (sim_rules_v12, game_rules_v15, ADR-0062); Klassenumsetzung, Bewegung/Beschwörung/Umgebung offen |
| 24 | Klassenwirkung der Kombinationen (Krieger/Bogenschütze/Schamane) | §24 | 2/3 | **fertig** (sim_rules_v13, game_rules_v16, ADR-0063); Bewegung/Beschwörung/Umgebung, Balancing offen |
| 25 | Bewegungswirkung der Kombinationen (Ausweichfenster) | §22–26 | 2/3 | **fertig** (sim_rules_v14, game_rules_v17, ADR-0064); Beschwörung/Umgebung, Balancing offen |
| 26 | Beschwörung und Umgebung der Kombinationen (alle 8 Wirkbereiche belegt) | §22–26 | 2/3 | **fertig** (sim_rules_v15, game_rules_v18, ADR-0065); echte Helferfigur, Balancing, Client offen |
| 29 | Marktplatz-Rabatt auf die Börsengebühr | Siedlungen | 2/3 | **fertig** (ADR-0066, Test in test_settlements); Balancing, Client-Anzeige, Deployment offen |
| 30 | Anzeige des Marktplatz-Rabatts (Abfrage + Browser-Client) | Siedlungen | 2/3 | **fertig** (Test in test_settlements); Unity nur generisch, in Unity ungetestet |
| 31 | settlement_rules_v2: Marktplatz-Rabatt 250/500 ‰ | Siedlungen | 2/3 | **fertig** (ADR-0067); nicht per Bot gemessen |
| 32 | Anzeige der Zusatzwirkungen der Kombinationszauber (Server + Browser) | §22–26 | 2/3 | **fertig, im echten Browser ungetestet** (Python-Test + Node-Prüfung des Textes); Unity offen |
| 33 | Zweigwahl / Respezialisierung der Berufe | §14–16 | 2/3 | **fertig** (rules_v10, ADR-0068, Golden Vector); Spielschicht (game_rules v19), Wirkung des Zweigs, Client offen |
| 34 | game_rules_v19: Spielschicht auf CEE v10, Zweigwahl im Spiel | §14–16 | 2/3 | **fertig** (ADR-0069); Wirkung des Zweigs, Client offen |
| 35 | Browser-Client: Zweig wählen/wechseln | §14–16 | 2/3 | **fertig, im echten Browser ungetestet** (Syntaxprüfung mit Node); Unity offen |
| 27 | Client: Namen der Kombinationszauber (Browser) | §26–29 | 2/3 | **fertig, im echten Browser ungetestet** (statische Tests + Node-Prüfung der Namenslogik); Unity-Client und Anzeige der Zusatzwirkungen offen |
| 28 | Unity-Client: Namen der Kombinationszauber | §26–29 | 2/3 | **fertig, in Unity ungetestet** (`Panels.SkillLabel`, CoreCheck + CompileCheck grün); Anzeige der Zusatzwirkungen offen |

## AP 1 im Detail (Teilschritte, Reihenfolge fest)
1. **Server:** Klassen-Kits (`game_rules_v2.json`), Kampfdaten je Figur (`game.kit`: Befehl, Kosten, Abklingzeit, Sperrzeit; im `fight_start`). Tests.
2. **Client:** Skill-Leiste (Tasten 1–9, Abklingzeit-Anzeige, Ausdauer-Sperre, auch außerhalb des Kampfes sichtbar).
3. **Client:** Kampfanzeige (Lebensbalken über Gegnern und Figuren, Zielwahl per Klick, Wirkleiste/Ankündigung, Treffer-/Block-/Ausweich-Effekte).
4. **Prüfung** im echten Browser, ADR-0039, Status, Commit, Bereitstellung nach Freigabe.
Nicht in AP 1 (kommt in späteren Paketen oder im 3D-Client): Kamera, Springen, Richtungsangriffe, aufgeladene/kanalisierte Fähigkeiten, Kombos, Waffen-/Rüstungsoptionen, PvP.
