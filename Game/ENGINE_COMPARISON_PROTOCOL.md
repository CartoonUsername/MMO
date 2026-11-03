# Engine-Vergleichsprotokoll (Unity 6 URP vs. Unreal Engine 5.8.4)

Status: **Entwurf, Vorschlag.** Die Engine-Entscheidung ist offen (Handover Teil 13). Dieses Protokoll legt nur fest, *wie* verglichen wird. Es entscheidet nichts.

## Randbedingungen (bestätigt durch Messung am 2026-11-03)

- RunPod-Pod: RTX 5090 (32 GB), Vulkan 1.4.329 headless funktioniert (`vulkaninfo` mit NVIDIA-ICD, ohne Display). Im VNC-Desktop nicht (kein Fenster-Rendering).
- Pod-System: Ubuntu 20.04, Python 3.10, Git 2.25, `sudo` verfügbar, 120 GB Container-Disk (flüchtig).
- Kosten: 1,21 USD/h (5090). Gesamtbudget für den Vergleich: **max. 5 GPU-Stunden** (≈ 6 USD), harte Grenze; danach Pod stoppen.
- Unity-Konto vorhanden, Sitz „Unity Personal“ **noch nicht aktiviert**.

## Offene Voraussetzungen (vor GPU-Start klären, kosten sonst Wartezeit)

| # | Frage | Wie klären | Status |
|---|---|---|---|
| V1 | Läuft Unity-6-Editor auf Ubuntu 20.04? | Systemanforderungen der gewählten Unity-6-Version prüfen; sonst neuen Pod mit 22.04/24.04 | offen |
| V2 | Lizenzaktivierung headless möglich? | Unity-Doku „manual activation“ prüfen | offen |
| V3 | Unreal-Linux-Build erhältlich + Plattenbedarf (120 GB) ausreichend? | Epic-Doku/Download prüfen | offen |
| V4 | Wie kommen Ergebnisse vom Pod zu uns? | Screenshots/CSV in Git (kleine Dateien), Push nur mit Login auf dem Pod | offen |

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
