# Windows-Einrichtung – Schritt für Schritt

Legende: ☐ = von dir auszuführen · ⚠ = bekannte Falle · `[PRÜFEN]` = Version/Verhalten konnte ich nicht gegen Epics Primärdokumentation verifizieren (siehe `PRODUCTION_READINESS.md`, Abschnitt 1).

Reihenfolge einhalten. Jeder Block endet mit einem **Abnahmetest**; erst dann weiter.

## Block 0 – Voraussetzungen prüfen

- ☐ Windows 11 (64 Bit), aktuelle Updates installiert.
- ☐ Freier Speicher auf einer **NVMe-SSD**: mind. 250 GB (Annahme: Engine + Visual Studio + DDC + Projekt + Shader-Caches; Epic nennt keinen festen Wert, den ich verifizieren konnte).
- ☐ 32 GB RAM, GPU mit mind. 8 GB VRAM (Epic-Empfehlung laut Suchauszug der Hardware-Seite, nicht 5.8-spezifisch).
- ☐ Aktueller GPU-Treiber (NVIDIA/AMD) direkt vom Hersteller.
- ☐ Kurzer Pfad ohne Leerzeichen/Umlaute, z. B. `D:\dev\MMO` (⚠ Windows-Pfadlängenlimit bei Unreal-Builds).
- ☐ Langpfade aktivieren (PowerShell **als Administrator**):
  ```powershell
  New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
  ```
  Danach `git config --system core.longpaths true` (nach Git-Installation, Block 1).

## Block 1 – Git, Git LFS, Python, Claude Code

- ☐ Git for Windows (enthält **Git Bash** – wird vom Epic-Claude-Plugin-Hook benötigt):
  ```powershell
  winget install --id Git.Git -e
  ```
- ☐ Git LFS:
  ```powershell
  winget install --id GitHub.GitLFS -e
  git lfs install
  ```
- ☐ Python 3.11 (nur für Referenz-CEE und Tools; Unreal bringt sein eigenes Python mit):
  ```powershell
  winget install --id Python.Python.3.11 -e
  ```
- ☐ Claude Code nach Anthropics aktueller Windows-Anleitung installieren (Installer-Befehl ändert sich; bitte der offiziellen Dokumentation folgen). Voraussetzung: Git for Windows.
- ☐ Repo klonen und Branch wählen:
  ```powershell
  git clone https://github.com/CartoonUsername/MMO.git D:\dev\MMO
  cd D:\dev\MMO
  git checkout claude/awesome-dirac-9k6p3n
  ```

**Abnahmetest 1**

```powershell
git --version; git lfs version; python --version
cd D:\dev\MMO\reference\python
python -m unittest discover -s . -t . -v
```
Erwartet: alle Tests (aktuell 140), `OK`.

## Block 2 – Visual Studio

Entscheidung offen (O-1): **VS 2022 17.14** (Empfehlung, längster Praxisnachweis) oder **VS 2026** (laut Epic-Seite „general development“, `[PRÜFEN]`; 5.8.1 hatte Buildprobleme, 5.8.4 behebt Integrationsfehler).

- ☐ Visual Studio **Community** installieren (Kostenlos für Einzelentwickler/kleine Teams – Lizenzbedingungen selbst prüfen):
  ```powershell
  winget install --id Microsoft.VisualStudio.2022.Community -e
  ```
- ☐ Im Visual Studio Installer → **Workload „Spieleentwicklung mit C++“** (Game development with C++).
- ☐ Rechts unter *Installationsdetails* zusätzlich:
  - ☐ „Unreal Engine installer“ (optionale Komponente der Workload)
  - ☐ MSVC v143 – C++-Buildtools x64/x86 (neueste)
  - ☐ **Windows-11-SDK 10.0.22621** **und** **10.0.26100** (beide ankreuzen; die Quellen widersprechen sich, welche Version 5.8 als Standard nutzt – mit beiden bist du abgesichert)
  - ☐ C++-Profilerstellungstools
  - ☐ „.NET-Desktopentwicklung“ (Workload) – Unreal-Build-Tools/Tools-Projekte
- ☐ Neustart.

**Abnahmetest 2**: Visual Studio Installer zeigt alle obigen Komponenten als installiert.

## Block 3 – Unreal Engine 5.8.4

- ☐ Epic Games Launcher installieren, anmelden.
- ☐ *Unreal Engine → Library → Engine-Version hinzufügen* → **5.8.4** wählen. (Falls nur 5.8.x angezeigt wird: Dropdown öffnen.)
- ☐ Optionen/Components: Editor-Symbole für Debugging (nur wenn Platz), **Windows-Target-Plattform**, Starter-Content **nicht** nötig. Keine anderen Plattformen.
- ☐ Installation abwarten, danach einmal Editor starten (Shader-Erstkompilierung, kann lange dauern).

**Abnahmetest 3**: Neues leeres C++-Projekt „Third Person“ (Templates → Games → Third Person → C++) in `D:\dev\scratch\` (NICHT im MMO-Repo) erstellen, mit *Tools → Visual Studio öffnen* kompilieren, *Play* drücken. Erwartet: Build ohne Fehler, Charakter steuerbar. ⚠ Scheitert das, ist die VS-/SDK-Kombination falsch (Entscheidung O-1 revidieren), nicht das MMO-Projekt.

## Block 4 – Unreal-MCP-Plugin (Editor-Seite)

- ☐ Im Scratch-Projekt: *Edit → Plugins* → aktivieren: **ModelContextProtocol** („Unreal MCP“) und **AllToolsets** („All Tool Sets“; ohne dieses Plugin stellt der Server laut Epic-README keine Tools bereit). Ein Webinar-Auszug nennt zusätzlich „Editor Tool Set“ – falls vorhanden, ebenfalls aktivieren. Editor neu starten. `[PRÜFEN]` genaue Anzeigenamen.
- ☐ *Edit → Editor Preferences* → Auto-Start für den MCP-Server aktivieren (oder in der Editor-Konsole `ModelContextProtocol.StartServer`). Standard: Port **8000**, Pfad **/mcp**. Belegt? → `ModelContextProtocol.StartServer 8001`.
- ☐ Client-Konfiguration für Claude Code erzeugen (Editor-Konsole, Cmd):
  ```
  ModelContextProtocol.GenerateClientConfig ClaudeCode
  ```
  Nach jeder Port-/URL-Änderung wiederholen.

## Block 5 – Epic-Claude-Plugin (Claude-Code-Seite)

- ☐ In Claude Code:
  ```
  /plugin marketplace add anthropics/claude-plugins-official
  /plugin install unreal-engine-skills-for-claude-code@claude-plugins-official
  ```
  (Marketplace-Zeile nur nötig, wenn er noch nicht vorhanden ist.)
- ☐ ⚠ Sicherheit: Claude Code **nicht** mit `--dangerously-skip-permissions` starten. `execute_tool_script` führt beliebiges Python im Editor aus; „localhost ist keine Vertrauensgrenze“ (Epic). Vor langen Sitzungen committen.
- ☐ Claude Code im Projektordner starten, Editor offen lassen, dann `/mcp` → Eintrag **unreal-mcp** muss verbunden sein.

**Abnahmetest 5**: Claude bitten, „liste die Actors im geöffneten Level auf“ (rein lesend). Erwartet: Antwort aus dem laufenden Editor. Erst danach schreibende Aufgaben.

## Block 6 – MMO-Projekt anlegen (erst nach Freigabe aller Tests)

- ☐ Mir melden: „Blöcke 0–5 bestanden“ + Ausgabe von `git lfs version`, VS-Version, SDK-Version, Ergebnis `/mcp`.
- ☐ Dann erstelle ich `Game/MMO.uproject` und das Modul-Skelett (Phase M0 in `PRODUCTION_READINESS.md`). Der Editor-Build erfolgt lokal bei dir (Rechtsklick `.uproject` → *Generate Visual Studio project files*, dann `Development Editor`/`Win64` bauen).
