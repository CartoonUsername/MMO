# ADR-0026: Kampf gegen mehrere Gegner und Flächenangriff

**Status:** akzeptiert als technische Grundlage. **Alle Zahlen in `sim_rules_v4.json` (Abschnitt `multi`) sind Platzhalter**, kein Balancing, keine bestätigten Spielinhalte.

**Kontext:** Der Gruppenkampf (ADR-0022) kennt nur einen Gegner. Ein Action-MMO braucht Rudel und gemischte Gegnergruppen sowie Zielwahl und Flächenangriffe. Raum und Winkel gibt es weiterhin nicht.

**Entscheidungen**
1. **Eigene Simulation** `mmo_sim/pack.py` (`simulate_pack`): 1..`multi.max_opponents` (Platzhalter 3) Gegner gegen 1..`group.max_party` Spieler. `group.py` bleibt unverändert (alle bisherigen Vektoren byteidentisch); mit genau einem Gegner und ohne die neuen Befehle ist das Ergebnis **bit-identisch zum Gruppenkampf** (Äquivalenztests über zufällige Eingaben und alle Gruppen-Vektoren).
2. **Gegnerzustand je Gegner:** Leben (wächst wie im Gruppenkampf mit der Gruppengröße), Betäubung, Verlangsamung, Taumeln, Angriffstakt und Ziel. Jeder Gegner wählt sein Ziel beim Beginn seines Angriffs nach Bedrohung (Gleichstand: kleinster Index); gefallene Gegner greifen nicht mehr an. Parade lässt nur den parierten Gegner taumeln.
3. **Fokus:** Jeder Spieler hat einen Fokusgegner (zu Beginn der erste); `target_1`..`target_3` wählen ihn (kostenlos, ohne Sperrzeit; ungültige oder gefallene Ziele zählen als ignoriert). Ist der Fokus gefallen, gilt der erste lebende. Leichter/schwerer Schlag, Betäubung und Verlangsamung wirken auf den Fokus (der schwere Schlag auf den bei Beginn gewählten, bei dessen Fall auf den ersten lebenden).
4. **Flächenangriff `sweep`:** festen Schaden (`multi.sweep.damage`) an **allen lebenden** Gegnern, mit Kosten, Sperrzeit und Abklingzeit; zählt für die CEE als **ein** `light_hit` (kein Vervielfachen von Entwicklungspunkten), erhöht die Bedrohung um den gesamten Schaden. Befehlsfreigabe: gehört zu den Basisbefehlen (`allowed` darf ihn führen); eine eigene Fähigkeit dafür steht aus.
5. **Sieg:** wenn alle Gegner gefallen sind; Schläge im Tick des letzten Todes zählen noch. `opponent_hp` ist die Summe, `opponents` die Lebenspunkte je Gegner (≤ 0: gefallen).
6. **Bericht und CEE:** Der Server (`EncounterServer.start_pack/finish_pack`) nennt im Bericht den **stärksten Gegner** (höchste Stufe, Gleichstand: der erste); weitere Gegner bringen **keine zusätzlichen Punkte** (Platzhalter, schützt vor Vervielfachung). Die CEE und ihre Regeln bleiben unverändert; alle Berichte laufen durch die CEE-Validierung (alles oder nichts).
7. **Golden Vectors:** `reference/golden_pack/sim_packs.json` (`mmo_sim.golden_pack`, Regeln `sim_rules_v4.json` per SHA-256 gebunden): Fokus, Flächenangriff, getrennte Takte, Parade, Betäubung/Verlangsamung, Zufallsfälle, Fehlerfälle.

**Absicherung:** `tests/test_pack.py` (Regeln, Äquivalenz, Validierung, Mechanik, Server), `tests/test_pack_golden.py`; Mutationstests (siehe Statusbericht).

**Offen / Grenzen**
- Kein Raum, keine Winkel, keine Reichweite: „Fläche" heißt hier „alle Gegner".
- Keine Gegnerarten mit besonderem Verhalten (Heiler, Beschwörer, Bosse mit Phasen), keine Gegnerführung zwischen Gegnern, kein Aggro-Wechsel außer über Bedrohung.
- Punkte für mehrere Gegner (mehr Erfahrung für Rudel) sind nicht entschieden; eigene Fähigkeit für `sweep` und Gegnerwahl im Protokoll (Begegnungsstart ist serverintern) fehlen.
