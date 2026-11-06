# Auftrag: Handy-Version des MMORPG (Mega-Prompt für die Server-Sitzung)

Du bist der Lead Developer. Sprache: Deutsch, Erklärungen in einem Satz (Listen und Pläne dürfen länger sein). Dieses Dokument beschreibt, was der Nutzer als Handy-Spiel baut, wo es steht, und was bis zum Ziel getan werden muss. Lies zuerst `docs/VPS_SESSION_PROMPT.md`, `docs/STATUS_REPORT.md`, `docs/VERTICAL_SLICE.md`, `docs/VERTICAL_SLICE_PROTOCOL.md`, `docs/ENEMY_DESIGN.md`, `docs/BALANCE_REPORT.md` und `docs/decisions/`. Die ursprüngliche Ausarbeitung des Spiels („Projekt-Kickoff“) liegt nicht im Repository; frage den Nutzer danach (er kann sie einfügen), statt Inhalte zu erfinden.

## 0. Stand-Abgleich (zuerst, hat Vorrang vor allem Folgenden)
Dieses Dokument wurde in einer Cloud-Sitzung geschrieben, die das Repository nur bis zum Commit `40c72a7` kannte. Das Repo ist inzwischen weiter (z. B. `CLAUDE.md`, `MMORPG_MASTER_BLUEPRINT.md`, `docs/design/*`, `docs/DECISIONS_AND_OPEN_QUESTIONS.md`, `client/godot`, ADR bis 0081, `game_rules_v20`). **Wo dieses Dokument dem Repo widerspricht, gilt das Repo** – insbesondere: die Engine-Entscheidung ist laut `docs/design/DESIGN_DECISIONS.md` (B32, Nutzer 2026-11-05) **Godot 4** (Unity verworfen); überall unten, wo „Unity“ steht, ist der Godot-Client gemeint, es sei denn, das Handy-Projekt des Nutzers ist ein Unity-Projekt (klären). Die „Projekt-Kickoff“-Ausarbeitung steckt vermutlich in `MMORPG_MASTER_BLUEPRINT.md`/`docs/design/`; lies sie und gleiche ab, statt sie vom Nutzer neu zu verlangen. Melde Widersprüche als Fragen, ändere keine bestätigten Entscheidungen.

## 0a. Wichtig vorab
- Das Handy-Projekt liegt **nicht** in diesem Repository (Stand der Cloud-Sitzung: nur Server, Python-Referenz, Unity-Testclient und Browser-Testclient; inzwischen gibt es außerdem `client/godot` – prüfen, ob das Handy-Projekt damit zusammenhängt). **Frage den Nutzer als Allererstes, wo das Handy-Projekt liegt** (Repo/Ordner, Unity-Version, Render-Pipeline, Zielplattform), und arbeite nicht auf Verdacht. Bitte ihn, die drei Screenshots auch in dieser Sitzung hochzuladen.
- Du hast keine Engine-Installation (Godot/Unity) mit Grafik auf dem Server: Client-Code kann hier höchstens eingeschränkt geprüft werden (Godot headless ist ggf. möglich – prüfen). Der Nutzer testet Builds lokal und meldet Fehler. Alles, was serverseitig ist (Regeln, Protokoll, Tests), baust und prüfst du hier.
- Schutzregeln des Servers aus `docs/VPS_SESSION_PROMPT.md` gelten unverändert (kein Eingriff in `/var/lib/mmo`, `mmo.service`, `/opt/mmo` ohne Freigabe, keine kostenpflichtigen Dienste, keine Zugangsdaten im Repo/Chat, nur Branch `claude/awesome-dirac-9k6p3n`).

## 1. Was der Nutzer gerade gebaut hat (nach drei Screenshots)
Alle Beschriftungen sind Platzhalter, Zahlen ungeprüft. Hochformat (Handy), sichtbare schwarze Ränder links/rechts: läuft vermutlich im Editor/Browser mit Handy-Seitenverhältnis. Stil: stilisierte Low-Poly-3D-Grafik, vermutlich fertige Asset-Pakete (Lizenzen prüfen!), Hintergrundmusik/Sounds unbekannt.

**Bild 1 und 2 – Hub/Hauptmenü („Stadt“):**
- Oben: Münzen (292) und Diamanten (0), darunter „+56 / Min. (auch offline, max. 8 Std.)“.
- Dialog „Willkommen zurück! Deine Stadt hat 70 Münzen verdient.“ mit grünem OK-Knopf (Offline-Einkommen).
- 3D-Stadtansicht mit Gebäuden (Häuser, Turm, Holzhütte) und der Heldenfigur (Bogenschütze) davor.
- Großer grüner Knopf „SPIELEN“.
- „Helden“: drei Karten – **Krieger** (Wirbelschlag, Fähigkeit Erdstoß, „Wählen“), **Bogenschütze** (Durchschlagende Pfeile, Fähigkeit Pfeilhagel, „GEWÄHLT“), **Schamanin** (Magiekugeln, Fähigkeit Blitzsturm, gesperrt, 600 Münzen).
- „Stadt ausbauen“: **Schmiede** Stufe 10 („+8 % Schaden je Stufe“, Preis 3.201), **Gildenhalle** Stufe 4 („+10 % Leben je Stufe“, Preis 230); Liste scrollt, vermutlich weitere Gebäude.

**Bild 3 – Kampf/Arena („Spielen“):**
- Kamera von schräg oben auf eine grüne Gras-Arena, Heldenfigur (Bogenschütze) in der Mitte, Gegner/Spawner am Rand.
- HUD: Herz mit Lebensbalken „125 / 125“, darunter Erfahrungsbalken, „Stufe 1“; oben rechts Timer „3:16“, Totenkopf mit Kill-Zähler „16“; runder oranger Fähigkeitsknopf unten rechts „Pfeilhagel BEREIT“.
- Vermutlich Auto-Angriff und Joystick (nicht sichtbar) – im Projekt prüfen.
- Es ist eine zeitbegrenzte Runde („Survivor“-Art), keine persistente Welt.

## 2. Ziel
Ein **MMORPG fürs Handy** im Geist des Projekt-Kickoffs – aber **deutlich einfacher gestaltet**: persistente gemeinsame Welt, andere Spieler sichtbar, Kämpfe gegen Gegner mit Ankündigungen (Telegraphe), Charakterentwicklung aus der eigenen Historie, Berufe/Handwerk, einfache Wirtschaft, Gruppen. Die heutige Arena-Runde und die Stadt sind erste Bausteine; sie müssen an den **serverautoritativen Spielserver** (`mmo_game`) angebunden und inhaltlich zum MMORPG-Konzept umgebaut werden. Heutiger Zustand: „lange nicht das, was wir wollen“ – viel Arbeit; geh in kleinen, getesteten Etappen vor und zeige dem Nutzer nach jeder Etappe etwas Spielbares.

## 3. Bestätigte Spielentscheidungen (nicht ändern, nur dem Nutzer Konflikte melden)
Alle starten als Mensch; Entwicklung nur aus der Historie des Charakters (keine reinen Stufen/XP-Kauf); Spieler und NPCs gleiche Pipeline; Server autoritativ, deterministisch, versioniert; 3 Startklassen; 9 Elemente; Essenzformen; Berufe; kein sinnloses Wiederholen; kein Pay-to-win; alle Zahlen Platzhalter bis bestätigt.
**Konflikte, die du dem Nutzer zur Entscheidung vorlegst (nicht selbst entscheiden):**
1. „+56 Münzen/Min. auch offline, max. 8 Std.“ ist Wiederholungs-/Idle-Belohnung → widerspricht „kein sinnloses Wiederholen“. Vorschläge: abschaffen, oder an echte Aktivität koppeln (Handwerksaufträge/Berufe laufen offline weiter, begrenzt, mit Entscheidung des Spielers).
2. „Schamanin für 600 Münzen freischalten“: Klassen kaufen ist nicht bestätigt; die Entscheidung lautet „3 Startklassen“. Krieger/Bogenschütze/Schamanin sind Platzhalter für die drei Startklassen, deren Namen/Rollen der Nutzer festlegt.
3. „Schmiede +8 % Schaden je Stufe“ gegen Münzen: Machtgewinn über Spielwährung ist okay, solange Münzen nur durch Spielen/Handel entstehen und nie mit Echtgeld oder Diamanten gekauft werden. Diamanten: nur Kosmetik/Komfort ohne Machtvorteil – bestätigen lassen.
4. Wachstumskurve der Gebäudekosten (Stufe 10 = 3.201 Münzen) auf Spielzeit prüfen (Bots/Rechnung), kein „Grinden“.

## 4. Arbeitspakete (Reihenfolge = Priorität; jedes Paket: Ziel, Aufgaben, Abnahme)
### A. Bestandsaufnahme Handy-Projekt (zuerst)
Ort, Unity-Version, Render-Pipeline (URP?), Paketliste, Szenen, Skripte, Asset-Quellen **und deren Lizenzen** (Weitergabe/Veröffentlichung erlaubt? Store?), Build-Ziele, App-Größe, Bildraten. Ergebnis: kurzer Bericht + Abhängigkeitsplan. Abnahme: der Nutzer bestätigt den Bericht.
### B. Architektur: dünner Client, autoritativer Server
Client sendet nur Absichten (Bewegen, Fähigkeit, Ausweichen, Interaktion), Server entscheidet (siehe `docs/VERTICAL_SLICE_PROTOCOL.md`). Alles Wirtschaftliche (Münzen, Zeit, Offline-Gewinn, Beute) **serverseitig mit Serverzeit**, nie Gerätezeit/Gerätespeicher als Wahrheit. Transport: WebSocket über TLS (steht bereits unter `https://187.126.26.226.sslip.io/ws`), Reconnect mit Token, Netzwechsel/Hintergrund/Sperrbildschirm sauber behandeln. Konto-Anmeldung: Name+Passwort/Token (steht), später Geräteanmeldung. Abnahme: Handy-Client verbindet, meldet an, sieht einen zweiten Spieler.
### C. Touch-Steuerung und UX
Virtueller Joystick (links), Auto-Angriff auf nächstes Ziel, Fähigkeitsknöpfe (rechts; Pfeilhagel-Beispiel), Ausweichen per Knopf/Wisch, Zielwechsel per Tippen auf Gegner, Interaktion (Sammeln/Händler) per Tippen. Hochformat und Querformat, Safe Areas (Notch), Skalierung für Tablets, Haptik, Lesbarkeit (Textgrößen), keine Eingabe, die ein Finger verdeckt. Abnahme: Steuerung auf echtem Gerät flüssig, Eingaben werden als Serverbefehle (`game.move`, `game.fight` …) gesendet.
### D. Von der Zeit-Arena zur persistenten Welt
Aus „SPIELEN“ (Runde 3:16) wird „Welt betreten“: Zonen mit Gegnern, Sammelpunkten, anderen Spielern; Gegner leben weiter (Wiedererscheinen je Art, steht). Arena-Runde kann als optionale Instanz/Herausforderung bleiben, aber ohne eigene Regeln neben dem Server. Interessenverwaltung (nur Nahes senden), Bandbreite für Mobilfunk, maximale Spieler pro Zone. Abnahme: zwei Handys in einer Zone sehen sich und kämpfen gemeinsam.
### E. Kampf fürs Handy
Mapping der Serverbefehle (`light`, `heavy`, `dodge`, `block`, `stun`, `slow`, `sweep`, `heal`, `shield`, `flee`, Fähigkeiten) auf wenige Touch-Elemente. **Telegraphe als Bodenmarkierungen** (Kreis/Linie/Kegel mit Füllanimation passend zu `ticks`) und Text-Antworten (dodge/block/parry/interrupt); Statussymbole (betäubt, verlangsamt, brennend), Gegner-Schild/-Heilung/-Beschwörung sichtbar, Bossphasen mit Ansage. Server-Tickrate (10 Hz) ↔ 60-fps-Darstellung: Interpolation, kein Client-Vorhersagen von Ergebnissen. Abnahme: Kampf gegen Wolfsrudel, Irrlicht-Heiler, Boss „Steinherz-Koloss“ spielbar, Ankündigungen rechtzeitig erkennbar.
### F. Charakterentwicklung (CEE) sichtbar machen
Statt reiner „Stufe 1“-Anzeige: Fortschritt aus der Historie (Berichte `fight_end.report`), Fähigkeits-/Formwahl nach den Regeln der CEE (`reference/python/mmo_cee`), Anzeige „was hat mich geprägt“. Keine zweite Entwicklungslogik im Client. Abnahme: nach Kämpfen/Handwerk ändert sich der Charakterbildschirm nachvollziehbar.
### G. Stadt als sozialer Hub und Berufe
Die Stadt wird zum gemeinsamen Hub: Gebäude = Funktionen des MMORPG (Schmiede = Handwerk/`craft`, Markt = `market.*`/`maker.*`, Gildenhalle = Gruppen/`party.*`/später Gilden, Händler, Lager). Bonus-Gebäude („+8 % Schaden“) nur nach bestätigter Regel; falls Machtboni bleiben, im Server als Regelversion mit Golden Vectors. Abnahme: Handwerksauftrag und Handel zwischen zwei Handys funktionieren.
### H. Wirtschaft
Münzen (Spielwährung): Quellen (Beute, Verkauf) und Senken (Reparatur, Gebühren, Ausbau) bilanzieren (`mmo_world` Markt, Pricing); Diamanten: erst nach Entscheidung des Nutzers (kosmetisch). Offline-Einkommen nach Entscheidung aus Abschnitt 3. Kein Echtgeld-Shop ohne ausdrückliche Freigabe. Abnahme: Wirtschafts-Simulation (Bots) zeigt keine Inflation/Exploits in 1000 Spielstunden-Modell.
### I. Soziales und Sicherheit der Spieler
Gruppen (`party.*`, steht), Freundesliste, kurzer Chat mit Filter, Melden/Blockieren, Namensregeln, Rate-Limits, Moderationswerkzeuge für den Betreiber. Altersgerecht (Jugendschutz), keine Lootboxen. Abnahme: Chat/Meldefunktion getestet, Missbrauchsfälle als Tests.
### J. Oberfläche, Optik, Ton
Einheitlicher Stil (Farben, Schrift, Icons, Knopfformen wie auf den Screenshots), Deutsch + Englisch (Lokalisierung von Anfang an), Barrierefreiheit (Textgröße, Farbenblind-Modi, Screenreader nicht vorrangig), Sounds/Musik **nur lizenzfrei oder selbst erstellt** (Lizenzliste führen), Ladebildschirm, Fehlerdialoge in Klartext, Onboarding/Tutorial der ersten 5 Minuten (Bewegen → sammeln → erster Kampf → Gruppe), „Willkommen zurück“-Dialog nach der Offline-Entscheidung umbauen. Abnahme: ein neuer Tester kommt ohne Erklärung bis zum ersten Kampf.
### K. Mobile-Technik
Ziel: stabile 30 fps (besser 60) auf Mittelklasse-Android, Akku/Wärme, Speicher; Draw-Calls/Batching/Occlusion, LODs, Objekt-Pooling für Gegner/Pfeile/Effekte, Texturen mit ASTC, Atlanten, Shader-Varianten reduzieren, Partikel begrenzen, Audio komprimieren, App-Größe möglichst klein (Asset-Streaming für Zonen), Ladezeiten, Pause/Hintergrund, Telemetrie datensparsam. Build-Pipeline Android (AAB), iOS später. Abnahme: Profiler-Messungen auf zwei echten Geräten dokumentiert.
### L. Recht, Datenschutz, Stores
DSGVO (Datenminimierung, Löschung auf Anfrage, Datenschutzerklärung, Einwilligung), Altersfreigabe, Impressum, Google-Play-Richtlinien (keine Lootboxen ohne Wahrscheinlichkeitsangabe, Konto-Löschung in der App), Asset-Lizenzen, Passwörter nie im Klartext speichern (Token im sicheren Speicher des Geräts). Keine Dienste mit Kosten ohne Zustimmung. Abnahme: Checkliste im Repo (`docs/`), Lücken benannt.
### M. Server-Skalierung und Betrieb
Messen statt schätzen: Lasttest mit Bot-Clients (viele WebSocket-Verbindungen), CPU/Speicher/Tick-Dauer; der Server ist heute ein einzelner Python-Prozess (max. 16 Verbindungen im Code, `MAX_CONNECTIONS`) auf KVM 1. Danach: Zonen auf mehrere Prozesse, Gateway, Datenbank statt Dateispeicher, Überwachung (Dienstausfall, Plattenplatz, fehlgeschlagene Sicherung), externe Sicherungen. Erst nach Messung Servergröße entscheiden. Abnahme: dokumentierte Kapazität (Spieler/Zone) mit Messwerten.
### N. Qualitätssicherung
Python-Referenz bleibt Orakel (alle Tests, Golden Vectors, Replay/Determinismus, Mutationstests, doppelte Ereignisse, ungültige Eingaben). Zusätzlich: Client-Tests (Godot: GUT/headless; Unity: Edit-/Play-Mode) für Netzwerk-/UI-Logik, Manipulations-Tests (modifizierter Client sendet unmögliche Befehle), Gerätematrix (3–5 Geräte), Playtests mit Freunden mit festem Feedbackformular, Absturzberichte, Regressionstests vor jedem Deployment (Backup prüfen → Suite → Freigabe → Rollback-Weg).
### O. Meilensteine
- **M0** Bestandsaufnahme + Entscheidungen aus Abschnitt 3 (ohne Code).
- **M1** Handy-Client meldet an und läuft in der Serverwelt (Joystick, sehen, bewegen, sammeln).
- **M2** Kampf mit Telegraphen auf dem Handy, zwei Spieler zusammen.
- **M3** Hub-Stadt mit Handwerk/Handel/Gruppe, sichtbarer Charakterentwicklung.
- **M4** Onboarding, Lokalisierung, Performance-Ziele, Sicherheit/Recht-Checkliste.
- **M5** geschlossene Testphase (10–20 Spieler), Messung, Balancing.
- **M6** Store-Vorbereitung nach Entscheidung des Nutzers.

## 5. Arbeitsweise
- Jeder Schritt: kleine Etappe, Tests, Dokumentation/ADR im selben Commit, Commit + Push auf den Arbeitsbranch, kurzer Bericht (was getestet wurde, was nicht, was der Nutzer auf dem Handy prüfen soll).
- Beginne mit **A** (Bestandsaufnahme: frage den Nutzer nach dem Projektort) und lege ihm die vier Entscheidungen aus Abschnitt 3 vor, bevor du in B–H Code schreibst, der davon abhängt.
- Keine Konzeptdiskussionen ohne Not; Entscheidungen, die dem Nutzer gehören (Spielregeln, Geld, Live-Server, Store, Lizenzen), kurz und konkret fragen.
