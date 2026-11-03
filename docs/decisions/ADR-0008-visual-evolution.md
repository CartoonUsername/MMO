# ADR-0008: Visual Evolution – deterministische Ableitung Zustand → Erscheinungsparameter

**Status:** akzeptiert als technische Grundlage. **Die gesamte Optik in `visual_rules_v1.json` ist Platzhalter** (Parameternamen, Gewichte, Paletten, Teile, Wesens-Schichten): Belegt wird die Mechanik, nicht die Gestaltung.

**Kontext:** Bestätigt (Handover Teil 3): Millionen Kombinationen entstehen nicht durch einzeln modellierte Charaktere, sondern über gemeinsame Skelette, modulare Teile, Morph Targets, Materialparameter, visuelle Zustandsparameter und datengetriebene, versionierte Regeln – serverseitig nachvollziehbar.

**Entscheidungen**
1. **Reine Ableitung, kein eigener Zustand, keine eigenen Ereignisse.** `VisualEvolution.appearance(state)` ist eine Funktion des Charakterzustands. Der Server berechnet, Clients erhalten schreibgeschützt; die Erscheinung ist damit nicht fälschbar und aus der Historie jederzeit rekonstruierbar (Replay).
2. **Engine-neutrale Ausgabe**: `skeleton`, `body_set` (aus der Grundklasse, bleibt Identität), `morphs`, `materials`, `vfx` (Promille 0..1000), `colors` (Aura, Hautton), `parts` (Slot → Teile-ID), `animation_tags`, `element_signature`, `essence_form`, `identity_seed`, `appearance_sha256`. Rein ganzzahlig (ADR-0004); typisch unter 1 KB.
3. **Quellen**: Kampfstil (Anteil × Zuversicht, damit eine winzige Historie keine Extremform erzeugt), Elementprägung und -affinität, Berufsmeisterschaft, Kampfrichtungen, Wesensform, Entscheidungen. Lineare Regeln mit Floor-Division, nur Gewichte ≥ 0 (negative Wirkung ausschließlich als Delta der Wesens-Schicht).
4. **Freie Elementkombinationen ohne Paarliste**: Aura-Farbe ist ein gewichteter ganzzahliger Mischwert der Elementpaletten (Gewicht nach Affinität, reihenfolgeunabhängig); jede Kombination (36 Paare, 84 Dreier) hat eine Signatur zum Auflösen von Manifestations-Assets. Welche Manifestationen existieren, bleibt Content/offen.
5. **Wesens-Schichten** (`essence_layers`) addieren Deltas, Teile (z. B. `head_ornament`), Animations-Tags und Hautton-Delta; die Grundklasse bestimmt weiter das Basis-Set.
6. **Individualität**: stabile, deterministische Variation je Figur aus `sha256(character_id|parameter)` (nur für ausgewählte Morphs, begrenzt). Das ist Figur-Identität, **keine Analyse realer Personen**.
7. **Quantisierung** (Schritt 10 Promille) macht kleine Zustandsänderungen unsichtbar für die Replikation; `appearance_diff` liefert die minimale Änderungsmenge.
8. **Regeln versioniert und validiert** (`visual_rules_v1.json`, `requires_cee_rules_min`): Quellen, Bereiche, Paletten, Teile-Stufen und Schichten werden beim Start geprüft.
9. **Golden Vectors** (`reference/golden_visual/`): 21 Fälle Zustand → Erscheinung, inkl. Hash.

**Grenzen / offen**
- Keine Ausrüstung/Kosmetik und kein Charaktereditor (kosmetisches Aussehen vom Stat-Equipment zu trennen ist bestätigt, aber nicht umgesetzt).
- Keine Zeitverläufe/Übergangsanimationen (Blend-Dauern sind Client-/Content-Thema).
- Kampfwirkung der Modifikatoren und Bewegungsweisen je Form sind nicht Teil dieser Engine.
- Ob die Ausgabe 1:1 auf Unreal- oder Unity-Parameter abgebildet wird, hängt von der offenen Engine-Entscheidung ab.
