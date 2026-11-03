# ADR-0007: Wesensbewertung – gewichtete Belege, Entscheidungen, Vor-/Nachteile

**Status:** akzeptiert als technische Grundlage. **Alle Formen, Namen, Gewichte, Schwellen, Vor-/Nachteile und Entscheidungen in `rules_v4.json` sind Platzhalter** zur Verifikation der Mechanik, keine bestätigten Spielinhalte.

**Kontext:** Bestätigt (Handover Teil 3): Wesensformen entstehen organisch aus der tatsächlichen Spielhistorie, werden durch Prüfungen und bewusste Entscheidungen angenommen, sind dauerhaft, haben logisch begründete Vor- und Nachteile und bleiben konkurrenzfähig; die Grundklasse bleibt die Identität. Harte Einzelvoraussetzungen (rules v1–v3) bilden das nur grob ab.

**Entscheidungen**
1. **Gewichtete Belege statt harter Schwellen.** Jede Form hat `signals` (Gewicht je Signal) und `threshold`. Punktzahl = Σ Gewicht × Signalwert (0..1000 Promille). Signale: `element_attuned:<e>`, `element_affinity:<e>`, `combat_direction:<d>`, `profession:<p>`, `decision:<id>:<choice>`. Signalwerte sind abgeleitete Sichten auf die Teilzustände der anderen Engines (inklusive deren Anti-Farming-Grenzen); `signal_caps` deckeln jeden Beitrag.
2. **Mehrere Wege zu derselben Form, kein Einzelgrind.** Kein einzelnes Signal darf die Schwelle allein erreichen (Regelprüfung beim Start). Verschiedene Historien (Beruf-lastig, Kampf-lastig, Entscheidungs-lastig) können dieselbe Form erreichen.
3. **Bewusste Entscheidungen** als eigenes Ereignis `essence.decision_made {decision_id, choice}`. Definition und Wirkung stehen ausschließlich in den Regeln; der Client kann weder Punkte noch Formen anhängen (strikte Felder). Jede Entscheidung ist einmalig und endgültig, ab Mindeststufe, nur solange die Figur Mensch ist. *Vertrauensgrenze wie bei Kampfberichten:* Entscheidungen und Prüfungen müssen vom Spielserver (Quest-/Story-System) ausgelöst werden, nicht vom Client.
4. **Ablauf unverändert zweistufig:** `essence.trial_passed` (nur bei erreichter Punktzahl und Stufe) → `essence.adopted` (bewusste Annahme). Dauerhaft; bei mehreren erfüllten Formen entscheidet die Figur; die Wahl schließt die übrigen aus.
5. **Vor- und Nachteile je Form** (`modifiers`) als Daten; abgeleitete Sicht `essence_profile`. Regelprüfung: je Form mindestens ein Vor- und ein Nachteil, Summen innerhalb einer Bandbreite (`balance.max_net_imbalance`). Das ist eine mechanische Leitplanke für „konkurrenzfähige Pfade“, **kein Balancing**.
6. **Abwärtskompatibel:** Das Legacy-Schema (v1–v3) bleibt gültig und unverändert (Zustand ohne `decisions`, alte Golden Vectors byte-identisch). Neue Regeln als `rules_v4.json`; Standardregeln zeigen jetzt auf v4.

**Folgen / Grenzen**
- Die Wirkung der Modifikatoren auf Kampf/Visualisierung ist noch nicht angebunden (nur Daten und Sicht).
- Visual Evolution, Fähigkeiten und Bewegungen je Form sind offen (Spielinhalte nicht beschlossen).
- Ob Prüfungen echte Spielinhalte (Bosskampf, Quest) sein sollen und wie sie das Ereignis auslösen, ist Server-/Content-Aufgabe.
- NPCs durchlaufen dieselbe Pipeline; ihre Entscheidungen müssen vom Simulationsserver kommen (offen).
- Seltene/„geheime“ Formen, die nur durch Entdeckungen freigeschaltet werden, brauchen die Discovery Engine (offen).
