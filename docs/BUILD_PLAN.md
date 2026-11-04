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
| 9 | Welt: Regionen, Gegnervielfalt, Dungeon, Weltboss, Gefahrenstufen | §32–35, §60–61 | 2 | offen |
| 10 | Wirtschaft: NPC-Wirtschaft, Unternehmen (Filialen, Töchter, Offline-Betrieb mit Deckel) | §38–41, §75 | 3 | offen |
| 11 | Besitz: Grundstücke, Spielerstädte, Gemeinschaftsprojekte | §36–37 | 2/3 | offen |
| 12 | Forschung, Epochen, Entdecker | §42–44 | 3/5 | offen |
| 13 | Gilden, Prestige, Weltchronik (Stadtpolitik zurückgestellt) | §45, §47–49 | 3 | offen |
| 14 | Server: Regionen/Instanzen, Skalierung, Last- und Exploit-Tests | §50–55, §63 | 4 | offen |
| 15 | Engine-Client (Unity oder Unreal – Entscheidung des Nutzers, Frage 23) | §50, §77 | 1–2 | wartet auf Entscheidung |

## AP 1 im Detail (Teilschritte, Reihenfolge fest)
1. **Server:** Klassen-Kits (`game_rules_v2.json`), Kampfdaten je Figur (`game.kit`: Befehl, Kosten, Abklingzeit, Sperrzeit; im `fight_start`). Tests.
2. **Client:** Skill-Leiste (Tasten 1–9, Abklingzeit-Anzeige, Ausdauer-Sperre, auch außerhalb des Kampfes sichtbar).
3. **Client:** Kampfanzeige (Lebensbalken über Gegnern und Figuren, Zielwahl per Klick, Wirkleiste/Ankündigung, Treffer-/Block-/Ausweich-Effekte).
4. **Prüfung** im echten Browser, ADR-0039, Status, Commit, Bereitstellung nach Freigabe.
Nicht in AP 1 (kommt in späteren Paketen oder im 3D-Client): Kamera, Springen, Richtungsangriffe, aufgeladene/kanalisierte Fähigkeiten, Kombos, Waffen-/Rüstungsoptionen, PvP.
