# Production Readiness – Unreal-Engine-Vorbereitung

Stand: 2026-11-03 · Branch `claude/awesome-dirac-9k6p3n` · Basis: Commit `ba3d1b0`

**Kennzeichnung durchgehend:**
- ✅ **Fakt** – mit Quelle belegt (und wie belegt).
- 🟡 **Annahme** – plausibel, aber nicht verifiziert; wird in der genannten Phase geprüft.
- ❓ **Offen** – Entscheidung des Projekts; ohne dich nicht festzulegen.
- 💡 **Vorschlag** – meine Empfehlung, noch nicht bestätigt.

Installationsschritte: `Game/WINDOWS_SETUP_CHECKLIST.md`.

---

## 0. Repository-Stand (verifiziert)

| Punkt | Befund |
|---|---|
| Inhalt | `docs/` (Zustandsbericht, Architektur, Roadmap, 2 ADRs), `reference/python/mmo_cee/` (Event-Log, Identity/Element/Profession/Essence-Engine), `README.md` |
| Tests | 477 `unittest`-Tests (Stand Combat Engine), alle grün |
| Unreal-Projekt | **nicht vorhanden** (`.uproject`, C++-Module, Content fehlen) |
| Neu in diesem Schritt | `Game/` (diese Doku + Checkliste, `Game/.gitignore`) und `.gitattributes` (Git-LFS-Regeln). Kein bestehender Code geändert. |
| Branches | `main` unverändert; Arbeit nur auf `claude/awesome-dirac-9k6p3n`; kein Merge |

## 1. Unreal Engine 5.8.4 und das Epic-MCP-Plugin

### Recherchegrenzen (wichtig)
In dieser Session sind `dev.epicgames.com`, `forums.unrealengine.com` und Drittseiten nicht erreichbar (nur GitHub). Belegt sind daher: Suchergebnis-Auszüge (Epic-Forum, Epic-Doku) und das README des Epic-GitHub-Repos in Zusammenfassung. **Nicht** belegt ist die Aussage „5.8.4 + MCP-Plugin getestet kompatibel“ – dafür gibt es keine Quelle; der Test steht in Phase M0 (Abnahmetest 5 der Checkliste).

### ✅ Fakten
| # | Aussage | Quelle / Art |
|---|---|---|
| F1 | UE **5.8.4** existiert als Hotfix (Forum-Ankündigung). Enthalten u. a.: Editor öffnet nicht mehr bei jeder Quelldatei eine neue VS-2026-Instanz; `.slnx`-Lösungen werden erkannt (bevorzugt vor `.sln`); Sequencer-Absturz beim Schließen behoben. | Suchauszug zu forums.unrealengine.com/t/5-8-4-hotfix-released, unvollständig |
| F2 | UE 5.8 enthält ein **experimentelles MCP-Plugin von Epic**; es betreibt einen MCP-Server im Editor, den MCP-fähige Agenten (u. a. Claude Code) über lokales HTTP ansprechen. Kein eingebautes Claude-Feature. | Epic-Forum-Staff-Antwort (Suchauszug) + Webinar-Zusammenfassung |
| F3 | Erforderliche Plugins laut Epic-README: **ModelContextProtocol** und **AllToolsets**; ohne AllToolsets stellt der Server keine Tools bereit. | github.com/EpicGames/unreal-engine-skills-for-claude-code-plugin |
| F4 | Standard: Port **8000**, Pfad **/mcp**, gebunden an localhost mit Origin-Validierung. Start: `ModelContextProtocol.StartServer [port]`. Client-Config: `ModelContextProtocol.GenerateClientConfig ClaudeCode` (keine statische `.mcp.json` im Plugin). | selbes README |
| F5 | Claude-Code-Plugin: `/plugin install unreal-engine-skills-for-claude-code@claude-plugins-official` (ggf. zuvor `/plugin marketplace add anthropics/claude-plugins-official`); Prüfung mit `/mcp` → `unreal-mcp`. Teamweit via `enabledPlugins` in `.claude/settings.json`. | selbes README |
| F6 | Sicherheit: „Localhost is not a trust boundary“; `execute_tool_script` führt beliebigen Python-Code im Editor aus; `--dangerously-skip-permissions` vermeiden; vor langen Sitzungen committen/shelven. | selbes README |
| F7 | Unter Windows braucht der SessionStart-Hook `bash` (Git Bash/WSL); die MCP-Tools laufen auch ohne. | selbes README |
| F8 | Der MCP-Server läuft nur bei laufendem Editor (kein Headless-Betrieb dokumentiert). | selbes README |
| F9 | Epic-Hardwareempfehlung (allgemeine UE-Seite, nicht 5.8-spezifisch): Windows 11, Quad-Core ≥ 2,5 GHz, 32 GB RAM, ≥ 8 GB VRAM. | Suchauszug dev.epicgames.com |
| F10 | Visual Studio: Epics englische Seite nennt **VS 2026** für allgemeine Entwicklung (VS 2022 für Nintendo und ältere AGDE). | Suchauszug dev.epicgames.com |

### 🟡 Annahmen
- A1: Das 5.8-MCP-Plugin funktioniert unverändert in 5.8.4 (Hotfixes ändern üblicherweise keine API-Verträge). Prüfung: M0.
- A2: Plugin-Anzeigenamen im Editor: „Unreal MCP“, „All Tool Sets“ (ggf. „Editor Tool Set“) laut Webinar-Zusammenfassung; maßgeblich ist der Plugin-Manager.
- A3: Das Editor-Python in 5.8 ist ≥ 3.11, kompatibel mit `requires-python >=3.11` der Referenz-CEE. Prüfung: in M0 `py` im Editor ausführen.
- A4: Speicherbedarf Windows-Entwicklungsrechner: ≥ 250 GB frei.
- A5: Launcher-Build der Engine genügt; Quell-Build der Engine nicht nötig. Anlass für Quell-Build wären Engine-Patches oder dedizierte Server-Targets (siehe O-4).

### ❓ Offene Entscheidungen
- **O-1 Visual Studio:** Quellen widersprechen sich (Epic-EN: VS 2026; andere Epic-Sprachfassungen und Drittquelle: VS 2022 17.14; Forum: 5.8.1-Buildfehler mit VS 2026, in 5.8.4 Integrationsfixes). 💡 Empfehlung: **VS 2022 17.14** als risikoärmster Startpunkt; Wechsel auf 2026 nur, wenn Abnahmetest 3 scheitert oder Epic es fordert.
- **O-2 Windows SDK:** Release Notes laut Forum: 10.0.26100.0; `Windows_SDK.json` laut Forum: 10.0.22621.0. 💡 Beide installieren (kostet nur Platz).
- **O-3 Versionskontrolle für Assets:** Git + LFS + Locking (Empfehlung für Start, `.gitattributes` liegt bereit) vs. Perforce (üblich bei großen Teams/vielen Binärassets). Entscheidung vor ~20 GB Assets.
- **O-4 Dedicated-Server-Build:** Erfordert in der Regel Quell-Engine-Build (Server-Target). Zeitpunkt der Umstellung vor M3 klären.
- **O-5 Referenz-Hardware** des Teams (CPU/GPU) – bestimmt die Zielwerte aus Abschnitt 6.

## 2. Benötigte Werkzeuge (Zusammenfassung)

| Werkzeug | Soll | Status |
|---|---|---|
| Windows 11 x64, NVMe-SSD | ja | prüfen |
| Visual Studio Community, Workload „Spieleentwicklung mit C++“, MSVC v143, Windows SDK 22621 + 26100, .NET-Desktop-Workload | ja (O-1/O-2) | zu installieren |
| Unreal Engine 5.8.4 (Epic Launcher) | ja | zu installieren |
| Git for Windows (inkl. Git Bash), Git LFS | ja | zu installieren |
| Python 3.11 | für Referenz-CEE/Tools | zu installieren |
| Claude Code + Epic-Plugin | ja | zu installieren |
| JetBrains Rider | optional | ❓ |

Details und Befehle: Checkliste.

## 3. C++-Architektur (💡 Vorschlag)

Projektwurzel: `Game/` (`Game/MMO.uproject`). Erst in M0 angelegt, nicht jetzt.

```
Game/
  MMO.uproject
  Source/
    MMO/                     (Runtime-Modul: GameMode, Character, PlayerController, Basisklassen)
    MMOCharacterEvolution/   (Runtime, UE-unabhängiger Kern + dünne UE-Hülle)
    MMOCombat/               (später)
    MMOEditor/               (Editor-Tools, Validatoren, Import-Prüfungen)
    MMO.Target.cs, MMOEditor.Target.cs, MMOServer.Target.cs (O-4), MMOClient.Target.cs
  Config/  Content/  Plugins/
```

Regeln:
1. **Server-Autorität.** Spielzustand der CEE entsteht nur auf dem Server. Clients erhalten ein abgeleitetes, schreibgeschütztes `FMMOCharacterProfile` (repliziert; später Fast-Array/Delta). Kein Client-RPC schreibt ein CEE-Ereignis.
2. **Kern ohne UE-Abhängigkeit.** `MMOCharacterEvolution/Private/Core` nutzt nur C++20-Standardbibliothek (Event, Hash-Kette, Engines, Regeln). Die UE-Hülle (`UMMOCharacterEvolutionSubsystem`) übersetzt Gameplay-Delegates in Ereignisse. Vorteil: schnell testbar, später auch außerhalb Unreal (Backend-Dienst) einsetzbar.
3. **Gameplay-Tags** für Ereignistypen und Wesen/Berufe-IDs im Editor; die Regel-JSON bleibt maßgeblich (kein Doppelpflegen: Import-Tool erzeugt Tag-Listen aus `rules_vN.json`).
4. **Data Assets/Data Tables** nur für Präsentationsdaten (Icons, VFX-Zuordnung), nie für Regelwerte.

### Integration der Python-Referenz-CEE – Optionen
| Option | Beschreibung | Bewertung |
|---|---|---|
| **A (💡 Empfehlung)** | **C++-Portierung** des Kerns als Runtime; Python bleibt **Referenz und Test-Orakel**. Gemeinsame **Golden Vectors** (JSON: Rules + Event-Log + erwarteter State + erwartete Hashes; **vorhanden** in `reference/golden/`). Python exportiert, C++-Automation-Test spielt nach und vergleicht. | Im Spiel-Build gibt es keine Python-Abhängigkeit; Hot-Path performant; Regel-Drift wird von Tests erkannt. |
| B | Python-Sidecar-Dienst (gRPC/HTTP) | Gut für spätere Backend-Dienste (Persistenz/Analytik), nicht im Spielthread; zusätzlicher Betriebsaufwand. |
| C | Editor-Python (Unreal-Python) für Tools: Regel-Validierung, Golden-Vector-Export, Datenimport | 🟡 Editor-only: Unreal-Python ist ein Editor-Plugin und wird nicht ins Spiel-Build geliefert (Allgemeinwissen, in M0 bestätigen). Nur für Tooling. |

Beschlossen werden müssen vor Umsetzung: **Kanonisches JSON** für Hashes (aktuell: sortierte Schlüssel, kompakt, UTF-8 ohne ASCII-Escaping; C++ muss byte-identisch erzeugen → Golden Vectors prüfen das) und **SHA-256-Bibliothek** (UE hat eigene Hash-Utilities; ❓ O-6: nutzen oder eigene Implementierung).

Persistenz (❓ O-7): Event-Store-Datenbank, Snapshot-Intervall, Regelmigration (`rules_version`) – gehört in Roadmap-Prio 9, nicht in den Vertical Slice (dort: Speicherung in Datei).

## 4. Asset-Pipeline (💡 Vorschlag, Tools größtenteils 🟡)

**Grundsatz:** Quelle (DCC) → Import (Interchange) → Validierung (MMOEditor-Checks) → Content. Jede Stufe automatisiert prüfbar.

**Namenskonvention (Epic-Stil):** `SK_` Skeletal Mesh, `SM_` Static Mesh, `M_`/`MI_` Material/Instanz, `T_..._BC/N/ORM` Texturen, `ABP_` Anim-BP, `AM_` Montage, `NS_` Niagara System, `NE_` Emitter, `DA_` Data Asset. Ordner nach Feature: `Content/MMO/Characters/…`, `…/Environment/…`, `…/VFX/…`.

| Bereich | Plan | Offen |
|---|---|---|
| **Charaktere** | Ein gemeinsames Skelett für humanoide Körper; modulare Teile (Kopf, Rüstungsslots, Haare) + Morph Targets + Material-Parameter. Das Evolution-System liefert nur *Parameter* (z. B. Haut-/Glühintensität, Partikelaura, Morph-Gewichte), nie neue Meshes pro Spieler → skaliert auf Millionen Profile. | ❓ O-8: Eigene Charaktere vs. MetaHuman als Basis (Lizenz/Stil/Performance); ❓ O-9: Mutable/Customizable Objects für Massen-Variation (🟡 Reife in 5.8 prüfen) |
| **Animation** | IK-Rig + IK-Retargeter für Klassen-/Körpervarianten; Motion Matching (Pose Search) für Locomotion; Control Rig für Prozedurales; Kampf-Montagen mit Notify-Fenstern (Hit, Dodge-I-Frames) für Action-Combat. Mocap vs. Keyframe: ❓ | ❓ O-10 Animationsquelle (Mocap-Kauf, Marketplace/Fab, selbst) |
| **Materialien** | Wenige Master-Materialien (Charakter, Haut, Stoff, Metall, Terrain), alles weitere über Material Instances; Material Parameter Collections für globale Welt-/Wetterwerte. Texel-Dichte-Standard festlegen. | ❓ O-11 Substrate-Materialsystem ja/nein (🟡 Stand in 5.8 prüfen) |
| **Niagara** | Je Element (9) ein parametrisiertes Basissystem + Skalierungsparameter (Stärke, Kombination mit 2. Element); Budget pro System (siehe 6); GPU-Sim nur wo nötig; Scalability-Stufen (Low/Med/High/Epic). | – |
| **Umgebungen** | World Partition + One File Per Actor, Nanite für Fels/Gebäude, Lumen als Basis, Virtual Shadow Maps, PCG/Foliage-Scatter; HLODs; Landscape-Tiles. Modulare Bau-Kits (Städtebau-Vorbereitung). | ❓ O-12 Lumen+Nanite-Vorgaben auf Foliage; Hardware-RT |
| **Quelldaten** | `Source_Art/` (außerhalb `Content/`, LFS); Blender/Maya/Substance sind ❓ O-13 (Toolchain-Wahl). | |

Automatische Importprüfungen (MMOEditor, M1): Namenskonvention, Tri-Budget, Textur-Größen (Zweierpotenz, max. Auflösung je Typ), Nanite-Flag, LOD-Anzahl, Skelett-Kompatibilität, Kollision.

## 5. Erster hochwertiger 3D-Vertical-Slice (💡)

**Ziel:** Beweisen, dass Look, Gefühl und die Kern-Alleinstellung (Entwicklung durch Spielhistorie) zusammen funktionieren – klein, aber produktionsnah.

**Umfang (bewusst klein):**
- 1 Zone (~300 × 300 m, Wald-/Siedlungsrand, Tag/Dämmerung), 1 Dorfplatz mit 3–4 modularen Gebäuden.
- 1 Klasse: **Krieger** (Third-Person-Action: Bewegen, Springen, Ausweichen, 3-Hit-Kombo, Richtungsangriff).
- 2 Gegnertypen + 1 Mini-Boss, einfache KI.
- 2 Elemente als Niagara-Prägung (z. B. Feuer + Eis – Auswahl ❓ O-14).
- 1 Beruf-Mini-Loop (Bergbau → Schmieden) nur als Ereignisquelle.
- **CEE live:** Spielhandlungen → Server-Ereignisse → `FMMOCharacterProfile` → sichtbare Änderung (Aura/Material) + einfache Profilanzeige.
- 2 Clients gegen 1 Server (Netzwerkbeweis); Speichern/Laden der Historie aus Datei.

**Nicht enthalten:** Kampfechos, Städtebau, Wirtschaft, Welt-Streaming-Großraum, Charaktereditor.

| Phase | Inhalt | Abnahmekriterium |
|---|---|---|
| **M0 Walking Skeleton** | `Game/MMO.uproject`, Modulgerüst, Third-Person-Charakter, Map, MCP-Verbindung getestet, Python im Editor geprüft | Projekt baut auf Windows (Development Editor); Charakter läuft; MCP liest Level aus; CI-fähiger Befehl zum Bauen dokumentiert |
| **M1 CEE-Kern in C++** | Portierung Event/Hash/Identity/Element/Profession/Essence; Golden Vectors; Automation-Tests | Alle Golden Vectors bit-identisch (Hashes, State); Tests grün in UE-Automation und Standalone |
| **M2 Kampf-Prototyp** | Bewegung, Ausweichen, Kombo, Hit-Detection, 1 Gegner, Placeholder-Assets | Spielbar; Combat-Zahlen server-validiert |
| **M3 Netzwerk** | Dedicated-Server-Build (O-4), 2 Clients, Replikation Profil | 2 Clients sehen sich + Profil; Verbindung stabil 30 Min |
| **M4 Grafik-Pass** | Charakter-, Umgebungs-, Material-, Niagara-Qualität, Beleuchtung | Review gegen Zielbild; Benchmarks Abschnitt 6 erfüllt |
| **M5 Evolution sichtbar** | Prägung/Beruf → Visual Parameter → VFX/Material | Zwei Spielstile ergeben sichtbar unterschiedliche Figuren |
| **M6 Politur & Messung** | Audio-Platzhalter, UI, Performance-Run, Videocapture | Alle Benchmarks grün; Demo-Build lauffähig |

## 6. Performance-Benchmarks (💡 Zielwerte, alle ❓ bis Referenz-Hardware O-5 bestätigt)

**Referenzsystem (Annahme, an Epic-Empfehlung F9 angelehnt):** 6-Kern-CPU (Ryzen 5 5600 / i5-12400-Klasse), 32 GB RAM, GPU mit 8 GB VRAM (RTX 3070-Klasse), NVMe-SSD, Windows 11.

| Metrik | Ziel Referenzsystem | Messung |
|---|---|---|
| Framerate | 1440p mit TSR-Upscaling von ~67 %: **60 FPS**, p95-Frametime ≤ 16,6 ms, 1 %-Low ≥ 50 FPS | CSV Profiler / Insights, 5-Minuten-Fixpfad |
| Game Thread | ≤ 6 ms | `stat unit` |
| Render Thread | ≤ 8 ms | `stat unit` |
| GPU | ≤ 14 ms | `stat gpu`, Insights |
| VRAM | ≤ 7 GB (bei 8-GB-Karte) | `stat rhi` / Task-Manager |
| RAM (Client) | ≤ 12 GB | Insights |
| Hitches | keine > 50 ms beim Durchlaufen des Testpfads | Insights Hitch-Analyse |
| Ladezeit Zone | ≤ 20 s von NVMe | Stoppuhr/Log |
| Niagara | ≤ 1,0 ms GPU für typische Kampfszene (4 Spieler-VFX + 4 Gegner), Einzelsystem ≤ 0,3 ms | `stat niagara`, GPU-Profiler |
| Charaktere sichtbar | 20 Charaktere gleichzeitig im Slice ohne Verletzung obiger Werte | Szenentest |
| Server | 30 Hz stabil, Server-Frame ≤ 20 ms, mit 100 Bot-Clients (Skalenvorschau, nicht Pflicht in M3) | Server-Insights |
| Netzwerk | ≤ 30 KB/s pro Client im Kampf | Net Profiler |
| **CEE** (C++) | Validate + Apply ≤ 50 µs p99 pro Ereignis; Replay von 10 000 Ereignissen ≤ 50 ms; Zustand pro Charakter ≤ 4 KB (ohne Log) | Automation-Benchmark |
| Entwicklungsiteration | Inkrementeller C++-Build ≤ 60 s; Editor-Start ≤ 90 s | Stoppuhr |

Regeln: Jede Zahl wird nach der ersten echten Messung (M0 leeres Level, M2, M4) angepasst – Änderungen werden hier mit Datum dokumentiert, nicht still verschoben. Mindest-Spec (1080p/30 FPS auf schwächerer Hardware) wird erst nach M4 definiert.

## 7. Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| MCP-Plugin experimentell (API-Änderungen, Lücken) | Früh testen (M0); Workflow nie davon abhängig machen; alle Änderungen über Git |
| Arbitrary-Python über MCP | Berechtigungsabfragen an lassen, vor Sitzungen committen, nur lokal |
| Regel-Drift Python ↔ C++ | Golden Vectors als Pflichttest in CI |
| Asset-Repo wächst schnell | LFS + Locking jetzt; O-3 vor 20 GB entscheiden |
| VS/SDK-Inkompatibilität | Abnahmetest 3 vor Projektstart |
| Zu großer Scope des Slice | Umfangsliste oben ist fix; Neues nur gegen Streichung |

## 8. Nächster Schritt

1. Du: Checkliste Blöcke 0–5 abarbeiten, Ergebnisse melden.
2. Ich (M0): `Game/MMO.uproject` + Modulgerüst `MMO` und `MMOCharacterEvolution` (leer baubar), Golden-Vector-Exporter im Python-Referenzprojekt.
3. Danach M1.
