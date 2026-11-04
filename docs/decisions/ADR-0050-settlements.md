# ADR-0050: Besitz – Grundstücke, Spielersiedlungen, Gemeinschaftsprojekte (AP 11)

Status: angenommen (Zahlen sind Entwürfe, siehe `settlement_rules_v1.json`; Blueprint Frage 18 bleibt offen)

## Entscheidung
- Weltdienst `SettlementService` (`mmo_world/settlements.py`), keine CEE-Ereignisse, keine Migration. Snapshot-Schlüssel `settlements` nur bei Aktivität.
- **Orte:** Hauptstadt von Anfang an; vier weitere Siedlungsgebiete gründet eine Figur gegen Münzen (Senke). Die Gründung gibt keine Sonderrechte (Stadtpolitik zurückgestellt, §46).
- **Grundstücke:** persönlich, klein/mittel, Obergrenze je Figur (Rathaus hebt sie an). Haus und Geschäft in Stufen; Gebäude geben ein Lager (Inventar des Grundstücks). Tägliche Steuer; nach 7 Tagen ohne Zahlung verfällt das Grundstück, das Lager geht zurück an die Figur (kein Itemverlust).
- **Gemeinschaftsprojekte:** Straße, Marktplatz, Lagerhaus, Mauer, Hafen (nur Küstenorte), Rathaus. Nur Grundstücksbesitzer des Ortes tragen Münzen und Material bei (Senke, nie mehr als nötig); volle Stufe wirkt für den ganzen Ort. Beiträge werden je Figur mitgezählt (Grundlage für Prestige/Chronik, AP 13).
- **Echte Wirkungen:** Straße erhöht die Bewegungsgeschwindigkeit in der Region des Ortes (`road_permille` im Spiel), Lagerhaus vergrößert alle Lager, Rathaus erhöht die Grundstücksgrenze. Marktplatz-Gebührenrabatt, Mauer-Verteidigung und Hafen-Handelsreichweite sind als Werte vorhanden, aber noch nicht an Markt/Überfälle/Handelsrouten angeschlossen.
- Client: Fenster „Siedlung“; Ereignis `plot_forfeit`. Befehle `query.settlements`, `settlement.found`, `plot.buy/abandon/build/stash_in/stash_out`, `project.contribute`.
- Offene Kante: Aktionen sind nicht an die Spielerposition gebunden (Weltschicht kennt keine Positionen).

## Offen
Grundstücksgrößen/Besitzgrenzen/Bauregeln (Frage 18), freie Platzierung/Raster im Ort, Verkauf von Grundstücken unter Spielern, Anschluss von Marktplatz/Mauer/Hafen, Sichtbarkeit der Gebäude in der Spielwelt.
