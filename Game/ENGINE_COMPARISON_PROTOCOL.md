# Engine-Vergleichsprotokoll (Unity 6 URP vs. Unreal Engine 5.8.4)

Status: **Entwurf, Vorschlag.** Die Engine-Entscheidung ist offen (Handover Teil 13). Dieses Protokoll legt nur fest, *wie* verglichen wird. Es entscheidet nichts.

## Randbedingungen (bestätigt durch Messung am 2026-11-03)

- RunPod-Pod: RTX 5090 (32 GB), Vulkan 1.4.329 headless funktioniert (`vulkaninfo` mit NVIDIA-ICD, ohne Display). Im VNC-Desktop nicht (kein Fenster-Rendering).
- Pod-System: Ubuntu 20.04, Python 3.10, Git 2.25, `sudo` verfügbar, 120 GB Container-Disk (flüchtig).
- Kosten: 1,21 USD/h (5090). Gesamtbudget für den Vergleich: **max. 5 GPU-Stunden** (≈ 6 USD), harte Grenze; danach Pod stoppen.
- Unity-Konto vorhanden, Sitz „Unity Personal“ **noch nicht aktiviert**.

## Voraussetzungen – Stand der Recherche (2026-11-03)

Quellen sind Suchauszüge; Epic-Seiten waren in der Sandbox nicht direkt lesbar. Vor dem Start gegen die Doku der exakten Version prüfen.

| # | Frage | Ergebnis | Status |
|---|---|---|---|
| V1 | Unity-6-Editor auf Ubuntu 20.04? | **Nein.** Unity 6 unterstützt auf Linux nur Ubuntu 22.04 und 24.04 (Unity-Doku „System requirements“). Der aktuelle Pod (20.04) ist ungeeignet. Neuer Pod mit Ubuntu 22.04 nötig, z. B. RunPod-PyTorch-Template mit CUDA 12.8 (laut RunPod-Doku-Beispiel `…cuda12.8.1-…-ubuntu22.04`; Template-Name in der Konsole bestätigen). Die RTX 5090 braucht ein Template mit passender CUDA-Version. | geklärt |
| V2 | Lizenzaktivierung ohne Fenster? | **Ungeklärt, größtes Risiko.** Möglich laut Suchauszügen: manuelle Aktivierung (`-createManualActivationFile` → .alf → .ulf → `-manualLicenseFile`) unter `xvfb-run`; Aktivierung per Benutzername/Passwort im Batchmodus scheitert häufig ohne Display; in Containern gab es Probleme mit der Machine-ID. Ob das für **Personal** geht, ist nicht belegt. Vermutung (nicht belegt): Eine Lizenz hängt an der Maschine, jeder neue Pod müsste neu aktiviert werden. | offen |
| V3 | Unreal 5.8 auf dem Pod? | **Nicht empfohlen für den ersten Test.** Epic empfiehlt für Linux Ubuntu 22.04; Foren melden Vulkan-Abstürze (`VK_ERROR_DEVICE_LOST`) mit 5.8 unter Linux (Einzelberichte, teils Preview). Download-/Plattenbedarf nicht belegt. | geklärt (Risiko hoch) |
| V4 | Ergebnisse vom Pod holen? | Container-Disk wird beim Stoppen geleert; `/workspace` bleibt, kostet aber weiter (RunPod-Doku). SCP/SFTP geht über `ssh.runpod.io` nicht. Einfachste Variante ohne Zugangsdaten: Messwerte als Text und Screenshots direkt in den Chat. Alternative: Push mit einem auf dieses Repo und einen Tag begrenzten GitHub-Token, nur auf dem Pod eingegeben (deine Entscheidung). | geklärt |

## Testszene (identisch in beiden Engines)

Ein Unity-Szenario, ein Unreal-Szenario, gleicher Inhalt:
1. Third-Person-Figur (Platzhalterfigur, gleiches Skelett/Humanoid), frei drehbare Kamera.
2. Kleine Fantasy-Landschaft (~100 × 100 m; Gelände, Bäume/Gras, Felsen, Wasserfläche), Tag- und Dämmerungslicht.
3. Ein NPC (stehend, einfache Idle-Animation).
4. Ein Gegner (läuft auf Spieler zu, greift an).
5. Bewegung: Laufen, Springen, Ausweichen.
6. Einfache 3er-Kombo.
7. Ein Elementareffekt (Partikel, z. B. Feuer), auslösbar.
8. Beleuchtung und Materialien (PBR, Terrain, Wasser, Vegetation).
9. Zwei Grafikprofile: **Niedrig** (Ziel 30 FPS, schwache Hardware) und **Hoch**.

Steuerung der Messung ohne Spieler: skriptgesteuerter Kamerapfad + Aktionsliste (gleiche Sequenz in beiden Engines), Ausführung headless (`-batchmode`/`-RenderOffScreen`).

## Messgrößen

| Kategorie | Messung | Quelle |
|---|---|---|
| Performance | Frame-Zeit Ø, p95, p99, 1 %-Low je Profil (Niedrig/Hoch), 5-Minuten-Fixpfad | engine-eigene Frame-Logs → CSV |
| GPU/VRAM | VRAM-Spitze, GPU-Auslastung | `nvidia-smi` Sampling (1 s) |
| RAM | Spitzen-RAM des Prozesses | `ps`/`/proc` Sampling |
| Bildqualität | Screenshots gleicher Kamerapunkte (Tag, Dämmerung, Effekt) Niedrig/Hoch | PNG, Blindvergleich durch dich |
| Aufwand | Arbeitszeit bis zur lauffähigen Szene, Zahl manueller Schritte, Probleme | Protokoll (ehrlich, inkl. Sackgassen) |
| Ressourcen | Build-/Importzeit, Plattenbedarf, GPU-Stunden verbraucht | Logs, Rechnung |

## Bewertung (Vorschlag, Gewichte von dir zu bestätigen)

| Kriterium | Gewicht (Vorschlag) |
|---|---|
| Bildqualität auf High | 25 % |
| Skalierbarkeit/Performance auf Niedrig | 25 % |
| Entwicklungsaufwand/Lernkurve (Solo + KI-Agenten) | 20 % |
| Eignung für MMO-Netzwerk (Server-Build, Replikation) | 15 % |
| Ressourcen-/Kostenbedarf | 15 % |

Zusatzregel: Eine Engine, deren Test nicht innerhalb des Budgets lauffähig wird, wird mit dem Grund dokumentiert und **nicht stillschweigend** abgewertet oder ausgeschlossen (es ist ein Ergebnis über Aufwand, nicht über Qualität).

## Ablauf

1. Offline: V1–V4 klären (kein GPU-Cost).
2. Unity-Test zuerst (geringerer Plattenbedarf, Konto bereit).
3. Nur bei offenem Bedarf: Unreal-Test (V3 muss vorher grün sein).
4. Ergebnisse als `Game/benchmarks/<datum>_<engine>.md` + CSV/PNG; Entscheidung erst nach beiden Messungen und mit deiner Freigabe.
