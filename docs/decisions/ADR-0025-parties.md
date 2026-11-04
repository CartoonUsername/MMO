# ADR-0025: Gruppenbildung

**Status:** akzeptiert als technische Grundlage. **Alle Zahlen (Gruppengröße 4, Einladungsfrist 2 Tage, 5 offene Einladungen, Stufenabstand 20) sind Platzhalter.** Der Stufenabstand ist ein **vorläufiger Vorschlag gegen Boosting**; Mindestbeitrag, Regeln für Stufenunterschiede und Belohnungsabschläge sind **nicht entschieden** und brauchen eine Entscheidung des Produktverantwortlichen.

**Kontext:** Der Gruppenkampf (ADR-0022) nimmt bisher eine beliebige Liste von Figuren. Es fehlt, wie Spieler eine Gruppe bilden, wer sie führt und wie Beute verteilt wird, ohne dass Mitläufer ohne Beitrag profitieren.

**Entscheidungen**
1. **Gruppe:** `PartyService` (`mmo_world/party.py`, Regeln `party_rules_v1.json`). Eine Figur ist in höchstens einer Gruppe; bis zu `max_size` Mitglieder; Mitglieder in Beitrittsreihenfolge.
2. **Anführer:** Nur der Anführer lädt ein, wirft hinaus, gibt die Führung ab, setzt den Beutemodus und löst auf. Verlässt der Anführer die Gruppe, geht die Führung an das dienstälteste Mitglied. Bleibt nur eine Figur, löst sich die Gruppe auf (eine frisch gegründete Gruppe mit nur dem Anführer ist gültig).
3. **Einladung:** An genau eine Figur, mit Frist (`invite_days`); nur die Eingeladene nimmt an oder lehnt ab; Grenze für offene Einladungen je Ziel; Doppeleinladungen und Einladungen an Gruppenmitglieder scheitern. Größe und Stufenabstand werden bei Einladung **und** Annahme geprüft (der Zustand kann sich dazwischen ändern). Mit der Annahme erledigen sich alle anderen Einladungen der Figur.
4. **Beute (serverintern, `distribute_loot`):** Nur berechtigte Mitglieder, also Teilnehmer **mit Beitrag** im Kampf (der Server übergibt sie, z. B. alle mit Bericht), erhalten Beute. Modi: `round_robin` (reihum, Zeiger gespeichert und bei Austritten auf derselben Figur gehalten), `leader` (Anführer, sonst erster Berechtigter), `finder` (genannter Finder, der berechtigt sein muss). Ungültige Aufrufe ändern nichts. Clients erreichen die Verteilung nicht.
5. **Benachrichtigungen (ADR-0024):** `party.invited`, `invite_declined`, `joined`, `left`, `kicked`, `leader_changed`, `disbanded`, `loot`.
6. **Protokoll:** `party.form/invite/accept/decline/leave/kick/promote/set_loot/disband`, `query.party`, `query.party_invites` (eigene Figur). Einladungsfristen räumt der Tagesschritt ab (`expire`, serverintern).
7. **Persistenz:** Schlüssel `parties` im Weltzustand nur, wenn je eine Gruppe gegründet wurde (ältere Vektoren bleiben byteidentisch); `party_rules_v1.json` ist im Umschlag mit SHA-256 gebunden; `check()` prüft Mitgliederindex, Anführer, Zeiger und Einladungen beim Laden.
8. **Golden Vectors:** Szenario `parties` (Einladungen, Fristgrenzen, Größe, Stufenabstand, Anführerwechsel, alle Beutemodi, Auflösung, Fehlerfälle); Kopf enthält `party_rules_sha256`.

**Absicherung:** `tests/test_party.py` (Regeln, Einladungen, Mitglieder, Beute, Persistenz, Gateway); Mutationstests (siehe Statusbericht).

**Offen / Grenzen**
- Boosting-Regeln (Mindestbeitrag, Belohnungsabschlag bei großem Stufenabstand) sind Entscheidung offen; der feste Stufenabstand ist nur ein Platzhalter.
- Kein Gruppenchat, keine Raids/Schlachtzüge, keine Gruppenzusammenführung, keine Suche nach Mitspielern, keine Beuterechte für Gegenstände einzeln (Würfeln/Bieten).
- Die Auswahl der Berechtigten ist Sache des Kampfservers; ein Schwellenwert für „Beitrag" ist nicht festgelegt.
