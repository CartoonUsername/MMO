# Changelog

## [Unveröffentlicht] – 2026-11-05
- AP 22: Kombinationszauber (36 Paare, 84 Dreier) im Kampf (sim_rules_v11, game_rules_v14, ADR-0061); noch nicht deployt.
- AP 23: Bereichswirkung der Kombinationszauber (Verlangsamung, Schutz, Ausdauer; sim_rules_v12, game_rules_v15, ADR-0062); noch nicht deployt.
- AP 24: Klassenwirkung der Kombinationszauber (sim_rules_v13, game_rules_v16, ADR-0063); noch nicht deployt.
- AP 25: Bewegungswirkung der Kombinationen (Ausweichfenster; sim_rules_v14, game_rules_v17, ADR-0064); noch nicht deployt.
- AP 26: Beschwörung und Umgebung der Kombinationen (sim_rules_v15, game_rules_v18, ADR-0065); noch nicht deployt.
- AP 27: Browser-Client zeigt Kombinationszauber mit lesbaren Namen (Skill-Leiste, Elementfenster); Unity-Client nicht angepasst.
- AP 28: Unity-Client zeigt Kombinationszauber mit lesbaren Namen (Panels.SkillLabel, CoreCheck-Prüfung; in Unity selbst ungetestet).
- AP 29: Marktplatz senkt die Börsengebühr des Verkäufers (ADR-0066); noch nicht deployt.
- AP 30: Siedlungsabfrage liefert den eigenen Marktrabatt (`fee_discount_permille`); Browser-Client zeigt ihn und lesbare Ortswirkungen. Unity zeigt die Abfrage generisch; noch nicht deployt.
- Balancing-Rechnung zum Marktplatz-Rabatt (docs/BALANCE_MARKET_SQUARE.md): Wirkung vermutlich zu schwach, keine Regeländerung.
- AP 31: settlement_rules_v2, Marktplatz-Rabatt 250/500 ‰ (ADR-0067); noch nicht deployt.
- AP 32: `game.elements` liefert die Zusatzwirkungen der Kombinationszauber (`combo_riders`); Browser-Client zeigt sie als lesbaren Text. Unity nicht angepasst; noch nicht deployt.
- AP 33: Zweigwahl und Respezialisierung der Berufe (rules_v10, ADR-0068), Befehl `profession.specialize`; Spielschicht noch auf rules_v9, noch nicht deployt.
- AP 34: game_rules_v19 (Standard) läuft auf CEE rules_v10, Zweigwahl im Spiel aktiv (ADR-0069); noch nicht deployt.
- AP 35: Browser-Client zeigt den aktiven Berufszweig und bietet Wahl/Wechsel an (Befehl `profession.specialize`); im echten Browser ungetestet, Unity offen.
- AP 36: aktiver Berufszweig gibt +25 % Berufserfahrung für seine Rezepte (rules_v10, ADR-0070); noch nicht deployt.
- AP 37: `query.character` liefert die Regeln der Zweigwahl (`specialization`); Browser-Client zeigt Kosten, Sperrzeit und Bonus. Im echten Browser ungetestet.
- AP 38: Test: Welt von CEE v9 auf v10 heben, Zweig wählen, exportieren/importieren, Konsistenzprüfung (nur Tests, keine Regeländerung).
- AP 39: Missbrauchstests für `profession.specialize` (ungültige/fremde Eingaben, keine Nebenwirkungen).
- AP 40: `python -m mmo_game.upgrade` hebt einen Spielstand auf eine höhere CEE-Regelversion (ADR-0071); `docs/DEPLOY_PENDING.md` beschreibt die ausstehende Bereitstellung.
- AP 41: Hafen erhöht die Zahl offener Marktorders um 3 je Stufe (settlement_rules_v2, ADR-0072); noch nicht deployt.
- AP 42: Siedlungsabfrage liefert `orders_per_reach`; Browser zeigt Hafenwirkung als „+N offene Orders“ und die eigene Zusatzgrenze. Im echten Browser ungetestet.
- AP 43: Grundstückshandel zwischen Spielern (`plot.sell`, `plot.cancel_sale`, `plot.accept_sale`; settlement_rules_v2, ADR-0073); noch nicht deployt.
- AP 44: Browser-Client: Grundstück verkaufen, Angebot zurückziehen, Kaufangebote annehmen; Unity-Fenster „Siedlung“ kennt die Befehle. Im echten Browser ungetestet.
- AP 45: Missbrauchstests zum Grundstückshandel (falsche Argumente, Dritte, Doppelannahme, Münzbilanz, ungültig gewordene Angebote).
- AP 46/47: Erstes Meisterstück je Rezept in der Weltchronik (community_rules_v3, ADR-0074), Browser-Chronik zeigt es; noch nicht deployt.
- AP 48: Balancing-Rechnung zu Zweigbonus, Hafen und Grundstückshandel (docs/BALANCE_AP41_46.md), keine Regeländerung.
- AP 49: Statusdokumente (IMPLEMENTATION_STATUS, DEPLOY_PENDING) auf den Stand AP 50 gebracht.
- AP 50: Gesamtprüfung: 1519 Tests, Golden-Vectors-Prüfung, Unity-Kerncheck (dotnet) und Lasttest mit 20 Bots (p95 0,74 ms) ohne Befund.
- AP 51/52: Benachrichtigungen beim Grundstückshandel (`plot.sale_offered`, `plot.sold`, `plot.sale_cancelled`, `plot.sale_expired`), Browser zeigt sie lesbar; im echten Browser ungetestet.
- AP 53: aktiver Berufszweig gibt +50 Gütepunkte für seine Rezepte (rules_v10, ADR-0075); noch nicht deployt.
- AP 54: Browser-Hinweis nennt den Gütebonus. AP 55: echter Herstellungsweg bis zum Meisterwerk getestet, schließt die Lücke aus AP 46.
- Balancing der Kombinationen gemessen (docs/BALANCE_ELEMENTS.md), keine Regeländerung.
- Deployment auf den VPS: Commit ee249f9 (AP 16–21) um 2026-11-05T07:33Z; vorher Sicherung mmo-backup-20261105T073325Z, Rollback über /opt/mmo/python.prev.
- AP 21: Raid-Balancing (Mindestgröße 4, Etappen nach Gruppengröße, game_rules_v13, ADR-0060).
- AP 20: Client-Fenster für Elementzauber, Echo-Wirkung, Gildenforschung und Raid (ADR-0059).
- AP 19: Kampfgruppen bis 8 für Raids und Weltbosse (sim_rules_v10, game_rules_v12, ADR-0058).
- AP 18: Gildenforschung und Gilden-Raid (community_rules_v2, game_rules_v11, ADR-0057), Befehl `guild.research`.
- AP 17: Kampfwirkung der Echos (echo_rules_v2, ADR-0056).
- AP 16: Elementmanagement im Kampf (sim_rules_v9, game_rules_v10, ADR-0055), `game.elements`.
- Teil XIX (GitHub-Übernahme): `MMORPG_MASTER_BLUEPRINT.md` im Root, `CLAUDE.md`, `CHANGELOG.md`, `docs/DECISIONS_AND_OPEN_QUESTIONS.md`.

## Arbeitspakete bis 2026-11-04
AP 1 Kampfleiste/Klassen-Kits (ADR-0039) · AP 2 Identitätsschichten (0040) · AP 3 Spielgeschehen speist Profile (0041) · AP 4 Elemente (0042/0043) · AP 5 Berufszweige (0044) · AP 6 Wesensformen (0045) · AP 7 Kampfechos/Resonanz (0046) · AP 8 Ausrüstung/Transmog (0047) · AP 9 Regionen/Dungeon/Weltboss (0048) · AP 10 Filialen/Offline-Deckel (0049) · AP 11 Siedlungen (0050) · AP 12 Forschung/Epochen (0051) · AP 13 Gilden/Chronik/Prestige (0052) · AP 14 Last- und Missbrauchstests (0053) · AP 15 Unity-Client (0054). Deployment auf den VPS am 2026-11-04 (Commit 19e8307).
