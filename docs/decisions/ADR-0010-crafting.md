# ADR-0010: Crafting Engine – Herstellungsberichte, Handwerksprofil, Server-Herstellung

**Status:** akzeptiert als technische Grundlage. **Rezepte, Techniken, Materialien, Zahlen, Dimensionen und Spezialisierungen in `rules_v6.json` sind Platzhalter**, keine bestätigten Spielinhalte.

**Kontext:** Bestätigt (Handover Teil 8/9/11): Berufe sind vollwertige Fortschrittssysteme; gleiche Berufe entwickeln sich je nach Materialien, Elementen, Methoden, Werkzeugen, Forschung und Entscheidungen verschieden; Spieler entdecken eigene Verfahren, Rezepte und Techniken; wirtschaftliche Spieler sollen ohne starke Kampfklasse erfolgreich sein; keine unkontrollierte unendliche Produktion (Wirtschaft braucht Ressourcen, Zeit und Grenzen).

**Entscheidungen**
1. **Zwei Ebenen wie bei Kampf und Entdeckungen.** *CEE* (`CraftingEngine`, Ereignis `crafting.crafted`): serverbestätigter Herstellungsbericht → Handwerksprofil. *Weltseite* (`mmo_world`): atomares `Inventory` und `CraftingService`, der Herstellungen deterministisch auflöst und den Bericht erzeugt.
2. **Berichte statt Punkte.** Der Bericht nennt Rezept, Technik, Element, Menge, Qualitätsstufe, Tag. Punkte entstehen nur in der Engine. Eindeutige `craft_id` je Figur (vom Server vergeben), strikte Felder, Mengenobergrenze je Rezept, Tag monoton.
3. **Qualität ist deterministisch** (kein Zufall): `Basis + Meisterschaft × Faktor + Technikbonus + Materialgüte × Gewicht`, Stufen über Schwellen. Die CEE prüft die **Plausibilität** gegen die bestmögliche Qualität (bestes Material): ein Bericht über eine unerreichbare Stufe wird abgelehnt.
4. **Freischaltung über Meisterschaft und Entdeckungen.** Rezepte brauchen Berufsmeisterschaft und optional eine Entdeckung; Techniken gelten, sobald ihre Entdeckung bekannt ist (abgeleitet, kein eigener Zustand). Die Regelprüfung verlangt, dass die genannte Entdeckung das Rezept bzw. die Technik tatsächlich freischaltet (`grants`) und umgekehrt jede freigeschaltete Technik/jedes Rezept existiert.
5. **Spezialisierung aus dem Spielverlauf.** Dimensionen (Menge, Feinarbeit, Innovation, Infusion), Materialfamilien und Element-Infusionen werden aus Berichten gezählt; abgeleitete Spezialisierungen sind nicht exklusiv, nie rückgängig (Punkte sinken nie) und unabhängig von Kampfklasse.
6. **Anti-Farming wie im Kampf:** Wiederholungsabnahme je Rezept und Tag, Tageslimit je Dimension (voll → reduziert → hart), Erstherstellungsbonus nur einmal je Rezept. Wie im Kampf greift die Wiederholungsabnahme mit den Standardwerten deutlich vor dem Tageslimit (Balancing-Hinweis).
7. **Keine Produktion aus dem Nichts.** Der Dienst entnimmt Eingaben atomar aus dem Inventar (Technik kann sie senken, aufgerundet), erzeugt Ausgaben erst nach erfolgreichem Bericht und macht bei jedem Fehler alles rückgängig. Die CEE prüft den Bericht **vor** jeder Bestandsänderung. Berufserfahrung wird aus den *gedeckelten* Mengenpunkten abgeleitet (und nur bei > 0 vergeben), nicht frei gewählt.
8. **Regelversion v6** (v1–v5 unverändert, Standard jetzt v6; `discovery.grants` von `twilight_rite` in v6 um das Rezept ergänzt). Der Handwerksteil des Zustands existiert nur unter Regeln mit `crafting`-Abschnitt; alle älteren Golden Vectors bleiben byte-identisch.
9. **Golden Vectors:** `crafting_validation`, `crafting_antifarm`, `crafting_discovery_techniques`, `crafting_directions` (Regeln v6); `derived` enthält `known_recipes`, `known_techniques`, `craft_direction_scores`, `craft_directions`, `craft_profile`.

**Vertrauensgrenze:** Berichte stammen vom Spielserver (`CraftingService`); die Engine begrenzt Fehlverhalten, kann aber nicht prüfen, ob Material, Werkstatt oder Zeit tatsächlich vorhanden waren. Das Inventar ist ein minimaler Ersatz für die spätere Wirtschafts-/Lagerlogik.

**Offen / Grenzen**
- Werkzeuge und Werkstätten (Kapazität, Gebäudelevel), Herstellungsdauer, Offline-Produktion und Mitarbeiter sind nicht abgebildet.
- Materialgewinnung (Bergbau, Landwirtschaft …) und Märkte/Preise fehlen; Gütestufen sind ein Platzhalter für Materialeigenschaften.
- Die Wesenssystem- und Visual-Anbindung der Handwerksrichtungen ist nicht umgesetzt.
- Experimentieren (neue Kombinationen entdecken) und Rezeptweitergabe als Gegenstand sind offen; Rezepte werden derzeit nur über Entdeckungen/Lehren verbreitet.
- Weltweite Gegenstandsbilanz (Duplikationsschutz über Spieler hinweg, Handel) ist Aufgabe der späteren Wirtschaft; das Inventar garantiert nur nicht-negative Bestände je Besitzer und atomare Änderungen.
- Inventar-/Herstellungs-Golden-Vectors für die Weltseite fehlen noch.
