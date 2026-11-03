# ADR-0009: Discovery Engine – Beweise, Anerkennung, endlicher Pioniervorsprung

**Status:** akzeptiert als technische Grundlage. **Alle Entdeckungen, Beweise, Voraussetzungen, Fenster und Wirkungen in `rules_v5.json` sind Platzhalter**, keine bestätigten Spielinhalte.

**Kontext:** Bestätigt (Handover): Spieler und NPCs sollen Forschungen, Verfahren, Materialien und Techniken entdecken; erste Entdecker erhalten Anerkennung und einen *zeitlich begrenzten* wirtschaftlichen/spielerischen Vorsprung; Wissen darf nie dauerhaft von einer Person blockiert werden; einzigartige Entdeckungen müssen fair sein und dürfen nicht zu dauerhaftem Pay-to-win oder zur Blockade des Weltfortschritts führen; geheime Quests/Experimente können Entwicklungen (z. B. Wesensformen) freischalten.

**Entscheidungen**
1. **Zwei Ebenen.** *Charakterseite* in der CEE (`DiscoveryEngine`, Ereignisse `discovery.*`): was weiß diese Figur, aus welchem Weg, mit welcher Anerkennung. *Weltseite* außerhalb der Figurenhistorie (`mmo_world.DiscoveryRegistry`): wer war Erster, wer darf wann lehren. Beides wird durch `DiscoveryService` transaktional verbunden (Rollback, wenn das Log ablehnt).
2. **Beweise statt Grinden.** Eine Entdeckung braucht eine feste Menge eindeutiger Beweise (`evidence`, vom Server vergebene IDs, je Figur nur einmal). Dieselbe Handlung zu wiederholen bringt nichts; Fortschritt entsteht aus *verschiedenen* Erkenntnissen. Vorwissen (andere Entdeckungen) schaltet das Sammeln frei (Wissensketten, azyklisch geprüft).
3. **Abschluss** (`discovery.made`) nur mit allen Beweisen und erfüllten Voraussetzungen (Stufe, Berufsmeisterschaft, Prägung, Vorwissen). Die **Anerkennung** (`pioneer` / `discoverer`) bestimmt allein die Registry nach Reihenfolge der Serveraufrufe; die CEE speichert sie.
4. **Lernen** (`discovery.learned`) nur bei teilbaren Entdeckungen und erfüllten Voraussetzungen des Schülers; **persönliche** Entdeckungen (`shareable: false`, z. B. geheime Rituale) sind nie lehrbar.
5. **Endlicher Pioniervorsprung.** Im Fenster (`pioneer_window_days`, hart begrenzt durch `max_window_days`) darf nur der Pionier lehren. Danach darf jeder Halter lehren. **Unabhängige Forschung bleibt jederzeit möglich** – Fortschritt wird nie blockiert, nur die *Verbreitung durch Lehren* ist kurz exklusiv. Rechtsgrundlage dafür sind Regelprüfungen (Fenster > 0 und ≤ Maximum) und Tests.
6. **Verknüpfung mit dem Wesenssystem:** neues Signal `discovery:<id>` und das Gate `requires_discoveries` (geheime Formen). Punkte allein genügen für solche Formen nicht.
7. **Regelversion v5** (`rules_v5.json`, v1–v4 unverändert, Standard jetzt v5). Der Entdeckungsteil des Zustands existiert nur unter Regeln mit `discovery`-Abschnitt; alle älteren Golden Vectors bleiben byte-identisch.
8. **Schutz vor stillem Replay unter fremden Regeln:** `RulesVersionMismatch` – ein Ereignis, das unter einer anderen Regelversion aufgezeichnet wurde als die geladene, wird beim Replay (und beim Fortsetzen) abgelehnt statt still neu berechnet. Migration zwischen Versionen bleibt eine bewusste, noch offene Aktion.
9. **Golden Vectors:** `discovery_research` und `discovery_secret_form` (Regeln v5); `derived` enthält `known_discoveries` und `discovery_progress`.

**Vertrauensgrenze:** Beweise, Abschlüsse und Lehren sind serverseitige Ereignisse (Quest-/Welt-/Forschungssystem). Die Engine begrenzt Fehlverhalten (Eindeutigkeit, Voraussetzungen, Reihenfolge), kann aber nicht prüfen, ob der Spielserver einen Beweis zu Recht vergeben hat.

**Offen / Grenzen**
- Wirkung der Entdeckungen (`grants`: Rezepte, Techniken, Regionen, Technologien) ist nur Daten; die Crafting Engine, Wirtschaft und Stadtentwicklung greifen noch nicht darauf zu.
- Technologie-Etablierung je Stadt/Region (Infrastruktur, unterschiedlich schnelle Entwicklung) ist nicht abgebildet.
- Handelbares Wissen (Bücher/Schriftrollen als Gegenstände), Experimentier-Mechaniken (Kombinationen statt fester Beweisliste) und Vorsprungsvorteile im Markt (Preise, Lizenzen) sind offen.
- Persistenz der Registry ist als JSON-Snapshot vorbereitet, aber nicht an eine Datenbank angebunden; Registry und Logs müssen bei Wiederherstellung konsistent geprüft werden.
- Mehrfachaccounts können Pionierstatus/Fenster nicht verlässlich umgehen oder erzwingen; das ist Server-/Account-Aufgabe.
- Registry-Golden-Vectors (Weltzustand) fehlen noch.
