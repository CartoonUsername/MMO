# ADR-0065: Beschwörung und Umgebung der Kombinationszauber (AP 26)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §22–26)
- **Beschwörung** (Schatten, Natur): Schaden über Zeit der Kombination +50 % (`dot_permille: 1500`, ein Helfer ohne eigene Figur).
- **Umgebung** (Erde): Gegner 20 Ticks taumelnd (`stagger_ticks: 20`, danach sind leichte Treffer präzise); das Fenster ist länger als die Wirkzeit des Zaubers (14), sonst wäre es nie nutzbar.
- Damit hat jeder der acht Wirkbereiche eine Wirkung (Entladung, Zerrung im Schaden; Kontrolle, Schutz, Beistand AP 23; Bewegung AP 25).
- Regeln: `sim_rules_v15.json`, `game_rules_v18.json` (Standard). Ältere Versionen und Golden Vectors bleiben.

## Offen
- Echte Beschwörung (eigene Helferfigur), Umgebungseffekte mit Ort; Balancing per Bots; Client zeigt Riders nicht an.
