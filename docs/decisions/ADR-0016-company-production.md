# ADR-0016: Firmenproduktion

**Status:** akzeptiert als technische Grundlage. **Alle Zahlen** (Linien, Dauer, Ausbeute, Betriebskosten, Abnehmer) in `production_rules_v1.json` sind **Platzhalter**, keine bestätigten Spielinhalte.

**Kontext:** Bestätigt: Unternehmen mit Gebäude/Infrastruktur und Mitarbeitern; **Offline-Produktion ist begrenzt**; kein sinnloses Wiederholen; Gebäudelevel (Kapazität) und Unternehmenslevel getrennt. Bisher stellten nur Figuren selbst her (ADR-0010); Firmen hatten Kasse, Mitarbeiter und Anteile, aber keine Waren (ADR-0012).

**Entscheidungen**
1. **Lager** = das Inventarkonto der Firma (`company:<id>`, neben den Münzen). Kapazität kommt vom Gebäude (`storage`, ADR-0012). Ware ein-/auslagern dürfen Geschäftsführer und Eigentümer.
2. **Produktionslinien:** Anzahl nach Gebäudestufe (`lines_by_building_level`). Ein **Auftrag** bindet eine Linie und einen angestellten Arbeiter, der das Rezept beherrscht (Meisterschaft, Entdeckung); ein Arbeiter höchstens ein Auftrag. Eine **Charge** verarbeitet `batch_size` Rezepteinheiten; alle Eingaben aller Chargen liegen ab dem Start im Auftragskonto `production:<id>`.
3. **Fortschritt nur im Tagesabschluss** (Haken in `CompanyService.advance_day`) und **nur an Tagen, an denen der Arbeiter angestellt ist und seinen Lohn erhalten hat** – entlassen, gekündigt oder unbezahlt = Stillstand. Dauer je Rezeptstufe in Tagen. Zum Abschluss einer Charge müssen Lagerplatz und Betriebskosten (Geldsenke) vorhanden sein, sonst wartet sie (Fortschritt läuft nicht über die Dauer hinaus).
4. **Begrenzung der Massenfertigung:** Ausbeute `output_permille` (Platzhalter 80 %) und Qualitätsgrenze `max_quality` (Platzhalter „fine“): Masterstücke bleiben Handarbeit. Qualität wird beim Start aus der Meisterschaft des Arbeiters und der Materialgüte nach der Formel der Herstellung berechnet.
5. **Keine CEE-Berichte:** Offline-Produktion erzeugt weder Herstellungsereignisse noch Berufsfortschritt – Spieler können sich nicht über eingestellte Arbeiter hochfarmen (Wash-/Farming-Schutz).
6. **Abnehmer:** Ein serverinterner NPC-Händler kauft Lagerware zu `npc_buyer.permille` des Referenzwerts mit **Tageslimit je Firma**; der Erlös ist Firmenumsatz (`record_revenue`, wirkt auf den abgeleiteten Unternehmenslevel). Weitere Absatzwege (Markt, Aufträge von Kunden) sind offen.
7. **Abbruch** erstattet die nicht begonnenen Chargen (soweit Lagerplatz da ist, Rest an den Verwalter), die angefangene Charge ist verloren. **Schließung** gibt Lagerware und Auftragskonten an den Gründer (Platzhalter-Regel) und beendet alle Aufträge.
8. **Persistenz und Vektoren:** Produktion ist Teil des Weltsnapshots (Schlüssel `production`, nur wenn je benutzt, damit ältere Snapshots unverändert bleiben), wird beim Laden gegen die Inventarkonten geprüft (`check`), Regeln sind per SHA-256 gebunden. Golden-Szenario `company_production`.

**Absicherung:** `tests/test_production.py` (29 Tests: Lager, Start-Ablehnungen, Linien/Arbeiter, Qualitätsdeckel, Dauer/Ausbeute/Betriebskosten, Stillstand durch Entlassung/Unterbezahlung/Lagerfülle/Kasse, Abbruch, Abnehmer inkl. Limit-Rand, Schließung, Invarianten, Zufallsfolgen, Persistenz) plus Golden-Szenario; Mutationstests (drei Überlebende sind gleichwertig, weil die Inventarschicht dieselbe Prüfung ohnehin leistet).

**Offen / Grenzen**
- Keine Weiterverarbeitung über mehrere Stufen mit Lieferketten, keine Rohstoffgewinnung, Werkzeuge/Werkstätten, Techniken und Elemente in der Produktion; keine Aufträge von Kunden/Kontrakte, kein Absatz über das Orderbuch (Firmen sind keine Marktteilnehmer, da der Handelsbericht Figuren braucht).
- Der Unternehmenslevel hat weiterhin keine Wirkung auf die Produktion; Mitarbeiterproduktivität, Arbeitszeit und Zufriedenheit beeinflussen die Produktion nicht.
- Missbrauch über Mehrfachaccounts (Scheinfirmen, Eigenanstellung zum Umgehen der Grenzen) erkennt das System nicht.
