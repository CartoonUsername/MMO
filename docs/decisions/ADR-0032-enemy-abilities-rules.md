# ADR-0032: Gegnerfähigkeiten – Regeln und reproduzierbarer Baukasten

**Status:** akzeptiert als Grundlage (Schritt 1 des Gegnerdesigns, `docs/ENEMY_DESIGN.md`). **Alle Zahlen, Namen und Fähigkeiten in `sim_rules_v6.json` sind Platzhalter.** Die Wirkung im Kampf ist noch nicht umgesetzt (Schritt 2, ADR-0033); bisherige Kämpfe verhalten sich unverändert.

**Kontext:** Entschieden wurden: erste Familien (Wolfsrudel mit Alpha, Höhlenbär, Irrlicht-Heiler, Moorhexe) plus viele weitere Gegner mit „zufälligen" Fähigkeiten; Zufall nur reproduzierbar, je Spawn-Punkt neu und pro Tag fest; feste Muster mit sichtbarer Ankündigung; keine neuen Entwicklungspunkte.

**Entscheidungen**
1. **Regeldatei `sim_rules_v6.json`** (unveränderliche Version, Superset von v5): Abschnitt `enemy_abilities` mit Antwortenkatalog und zehn Fähigkeiten in acht Arten (Wuchtschlag `slam`, Flächenschlag `area`, Zustand auf Spieler `state` mit Betäubung/Verlangsamung, unterbrechbarer Brandzauber `cast`, Gegnerschild `shield`, Heilen `heal_ally`, Verstärkung `buff_allies`, Beschwören `summon`). Sechs neue Vorlagen (Alpha, Irrlicht-Heiler, Moorhexe, Steinwächter, Schattenjäger, Totem-Beschwörer), eine Beschworene (Steinimp) und ein Boss (Steinherz-Koloss mit drei Phasen); die vier alten Vorlagen behalten ihre Basiswerte.
2. **Pflichten, beim Laden geprüft:** jede Fähigkeit hat Vorwarnzeit ≥ 1 Tick und mindestens eine bekannte Antwort der Spieler; unterbrechbare Fähigkeiten haben die Antwort `interrupt`/`kill_caster`; Schilde nennen die brechenden Aktionen und die Antwort `break_shield`; Beschwörungen nennen Art, Anzahl und Obergrenze; Beschworene dürfen nicht selbst beschwören; Bosse werden nicht gewürfelt; feste Fähigkeiten dürfen die Gefahrengrenze der Vorlage nicht überschreiten; Phasen mit absteigenden Schwellen und ohne doppelte Fähigkeiten.
3. **Takt-Boden:** `min_attack_cycle` (Platzhalter 40 Ticks für Angriffstakt + Vorwarnzeit) gilt für alle Vorlagen und für jede Beschleunigung durch Phasen oder Verstärkung (`effective_interval`). Das hält die möglichen Aktionsraten unter den Plausibilitätslimits der CEE (`check_compatibility`); ein erster Entwurf des Schattenjägers (Zyklus 34) verletzte sie und wurde angepasst.
4. **Baukasten (`roll_abilities`):** Zusatzfähigkeiten einer Vorlage ergeben sich nur aus (Gegnerart, Spawn-Punkt, Tag): Zufallsstrom = SHA-256 über `"<Art>|<Spawn>|<Tag>|<i>"`, 64-Bit-Zahlen big-endian; Anzahl = `lo + z mod (hi − lo + 1)`; je Zug gewichtete Wahl unter den noch erlaubten Einträgen (Gefahrengrenze, höchstens eine Fähigkeit je Gruppe, Dateireihenfolge). Gleiche Eingaben liefern in jeder Sprache dieselbe Auswahl; Golden Vectors `reference/golden_enemies/enemy_rolls.json` (alle Vorlagen × 5 Spawn-Punkte × 6 Tage, Phasenfälle, Fehlerfälle).
5. **Phasen (`abilities_at`):** ab Lebensanteil unter der Schwelle (Promille) kommen Fähigkeiten hinzu und der Takt-Faktor ändert sich; Phasen addieren sich.
6. **Verzicht:** Elementzuordnung der Vorlagen nutzt die neun CEE-Elemente, aber ohne feste Schwächen/Paare.

**Absicherung:** `tests/test_enemies.py` (Regelprüfung je Regel, Grenzwerte, alter Kampf unverändert, Auswahl: Determinismus, Festwerte, exakte Stromdefinition, Gewichte, Gefahrengrenze, Gruppen, Phasen, Takt-Boden), `tests/test_enemies_golden.py`; Mutationstests (siehe Statusbericht).

**Offen / Grenzen**
- Die Wirkung der Fähigkeiten, Ankündigungsereignisse für den Client und die Anbindung an Spawn-Punkte und Tage des Spielservers folgen (ADR-0033).
- Die Raten-Obergrenze berücksichtigt nur einen Angreifer; mehrere gleichzeitig angreifende Gegner auf dasselbe Ziel sind eine bekannte Lücke der Verträglichkeitsprüfung (gilt schon seit dem Mehrgegnerkampf).
- Balancing (Schaden, Leben, Gefahrenwerte) ist ungeprüft; Gegner-Beute und Beutetabellen je Familie fehlen noch.
