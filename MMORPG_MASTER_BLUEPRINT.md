# MMORPG MASTER BLUEPRINT

**Konsolidiertes Game-Design-Dokument und Produktionsleitfaden**  
**Version:** 0.1 – Konzeptkonsolidierung  
**Stand:** 03. November 2026  
**Projektname:** Noch offen  
**Zielplattform zum Start:** Windows-PC  
**Status:** Lebendes Dokument – bestätigte Entscheidungen, Vorschläge und offene Punkte werden ausdrücklich getrennt.

---

# TEIL I – PROJEKTIDENTITÄT UND DESIGNGRUNDSÄTZE

## 1. Die Vision

Wir entwickeln ein eigenständiges, persistent angelegtes, grafisch hochwertiges 3D-Action-MMORPG. Es soll die langfristige Tiefe, Sammelmotivation, soziale Bindung und wirtschaftlichen Kreisläufe klassischer MMORPGs aufgreifen, aber eine eigene Welt, eigene Systeme und eine moderne technische und visuelle Identität besitzen.

Es ist **kein 2D-Spiel** und kein grafisch modernisierter Klon von NosTale, Metin2, 4Story oder Flyff. NosTale dient als Inspiration für einzelne Designqualitäten – insbesondere die langfristige Entwicklung von Spezialisten, handelbare Entwicklungsgegenstände, Sammeln, soziale Systeme und eine große Anzahl miteinander verbundener Progressionssysteme. Diese Inspiration darf nicht zu einer Kopie seiner konkreten Umsetzung führen.

Die Welt soll den Spielern nicht nur einen Charakter zum Leveln geben. Spieler sollen eine eigene Identität, Fähigkeiten, Berufe, Wissen, Besitz, Unternehmen, soziale Beziehungen und eine individuelle Geschichte aufbauen. Gleichzeitig sollen sie die Welt um sich herum sichtbar mitgestalten können.

### Zentrale Leitidee

> Die Klasse ist der Ursprung eines Charakters. Seine Geschichte, Entscheidungen, Fähigkeiten, Berufe, Entdeckungen und Erfahrungen formen seine Identität.

Ein Spieler muss nicht der stärkste Kämpfer sein, um im Spiel bedeutend zu werden. Er kann beispielsweise ein außergewöhnlicher Handwerker, Forscher, Händler, Unternehmer, Architekt, Entdecker oder Organisator werden.

## 2. Vier gleichwertige Säulen

1. **Kampf und Charakter:** Klassen, Action-Kampfsystem, Kampfechos, Resonanz, Elemente, Wesenentwicklung und Ausrüstung.
2. **Welt und Entdeckung:** Große Regionen, Erkundung, Geschichten, Monster, Dungeons, Weltbosse, Geheimnisse und langfristige technologische Entwicklung.
3. **Wirtschaft und Besitz:** Sammeln, Handwerk, Markt, Grundstücke, Gebäude, Unternehmen, NPC-Mitarbeiter, Spielerarbeitsplätze und Handelsnetzwerke.
4. **Gesellschaft und gemeinschaftliche Entwicklung:** Gilden, Kooperation, Spielerstädte, Gemeinschaftsprojekte, gemeinsame Forschung und eine sich verändernde Welt.

Diese Säulen dürfen nicht als voneinander isolierte Minispiele umgesetzt werden. Sie sollen sich gegenseitig beeinflussen.

## 3. Designprinzipien – verbindlich

- Hochwertiges, modernes 3D-Action-MMORPG mit Third-Person-Perspektive.
- Direkte Spielersteuerung; kein Auto-Kampf als Kernmechanik.
- Tiefe Systeme im Hintergrund, verständliche Benutzeroberfläche.
- Charakteridentität entsteht aus belegbarer Spielgeschichte, nicht aus einer einzigen Klassenwahl.
- Berufe sind vollwertige Progressionswege und keine nebensächlichen Minispiele.
- Jede Klasse, jede Kampftradition und jede Wesenform muss sinnvolle Stärken, Grenzen und Gegenmöglichkeiten besitzen.
- Vielfalt darf nicht zu einer dominanten Pflicht-Meta führen.
- Die Welt muss durch Spieleraktivitäten sichtbar verändert werden können.
- NPCs sind Teil der Weltwirtschaft und Weltgeschichte, nicht bloß statische Händler.
- Langfristige Fortschritte sollen bedeutsam sein, dürfen aber nicht auf undurchsichtigen, manipulativen Glücksspielmechaniken beruhen.
- Einzigartige Inhalte müssen technisch und spielerisch kontrolliert, dokumentiert und gegen Duplikation abgesichert sein.
- Die Charakterentwicklung soll viele Millionen sinnvolle Profilkombinationen ermöglichen. Eine mathematische Garantie, dass kein Charakter jemals dieselbe Kampfstärke oder denselben Build wie ein anderer haben kann, wird nicht versprochen.

## 4. Projektstatus und Begriffe

Das Projekt befindet sich in der Konzept- und frühen technischen Prototyping-Phase. Es existiert ein kleiner Python-Referenzprototyp `mmorpg_character_evolution_v0_1`. Dieser ist **kein spielbares MMORPG, kein Unreal-Plugin und keine produktionsreife Serverarchitektur**.

In diesem Dokument werden Statuslabels verwendet:

- **BESTÄTIGT:** Vom Nutzer ausdrücklich entschieden oder im Gespräch eindeutig festgelegt.
- **DESIGNRICHTUNG:** Aus mehreren Entscheidungen abgeleitete Leitlinie, die für weitere Ausarbeitung verwendet werden darf.
- **VORSCHLAG:** Sinnvoller Entwurf, aber noch nicht endgültig beschlossen.
- **OFFEN:** Benötigt spätere Designentscheidung oder technische Validierung.
- **ZURÜCKGESTELLT:** Wurde angesprochen, soll derzeit aber ausdrücklich nicht weiter ausgearbeitet werden.

Der Name des Spiels ist offen. „WANDERSTADT“ ist nicht der Name dieses Projekts und darf nicht als Projektname verwendet werden.

---

# TEIL II – BESTÄTIGTE PRODUKTRAHMENBEDINGUNGEN

## 5. Plattform, Grafik und Performance

### 5.1 Plattform

**BESTÄTIGT:** Der erste Release ist ausschließlich für Windows-PC vorgesehen.

- Primäre Steuerung: Tastatur und Maus.
- Komplexe Tastenkombinationen, gezielte Angriffe, Richtungsinputs und manuelle Bewegungssteuerung sind möglich.
- Konsolen und Mobile werden nicht für den ersten Release entwickelt.
- Eine spätere Portierung darf bei Architekturentscheidungen berücksichtigt werden, ist aber kein aktueller Produktionsumfang.

### 5.2 Hardware-Zielgruppe

**BESTÄTIGT:** Möglichst breite PC-Kompatibilität ist wichtig. Der grafische Anspruch soll trotzdem hoch sein. Auf schwächeren PCs sind reduzierte Einstellungen und gegebenenfalls 30 FPS akzeptabel; leistungsfähige PCs sollen eine deutlich höhere visuelle Qualität erhalten.

Das heißt nicht, dass 30 FPS für alle Systeme das Ziel sind. Konkrete Mindestanforderungen, Ziel-FPS, Auflösungen und Hardwareklassen müssen durch Prototypen und Messungen festgelegt werden.

### 5.3 Visuelle Richtung

**BESTÄTIGT:** Mischung aus realistischer und cineastischer Fantasy.

- Glaubwürdige 3D-Charaktere, Gesichter, Materialien, Rüstungen und Kleidungsstücke.
- Hochwertige Landschaften, Architektur und Innenräume.
- Eindrucksvolle, aber lesbare Magie- und Elementareffekte.
- Individuelle Monster- und Bossmodelle mit hochwertigen Animationen.
- Licht, Schatten, Wetter und Umgebungsgeräusche unterstützen die Atmosphäre.
- Die Welt darf sowohl wunderschöne, friedliche Regionen als auch düstere, gefährliche und geheimnisvolle Orte besitzen.

Keine 2D- oder stark veraltete MMORPG-Optik als Zielbild.

### 5.4 Visueller Qualitätsgrundsatz

Die Grafik soll skalierbar sein. Niedrige Einstellungen müssen auch ältere und mittelstarke PCs berücksichtigen; hohe und Ultra-Einstellungen dürfen High-End-Hardware ausnutzen. Effekte müssen hinsichtlich Sichtbarkeit, Lesbarkeit, Performance und Netzwerkdarstellung getestet werden.

---

# TEIL III – CHARAKTERE, KLASSEN UND IDENTITÄT

## 6. Charaktererstellung

**BESTÄTIGT:** Alle Spielercharaktere und NPCs beginnen als Menschen. Es gibt zu Beginn keine Auswahl zwischen klassischen Fantasy-Völkern wie Elfen, Zwergen oder Orks.

Der Charakter wird durch seine tatsächliche Entwicklung zu einem anderen Wesen beziehungsweise zu einer individuellen übernatürlichen Existenz geformt.

### 6.1 Startgestaltung

**VORSCHLAG:** Bei der Charaktererstellung werden zunächst grundlegende optische Merkmale bestimmt:

- Erscheinung, Gesicht, Körperbau und Körperproportionen.
- Frisuren, Haut- und Augenmerkmale sowie kosmetische Optionen.
- Eine anfängliche Grundklasse.
- Startausrüstung und Einstiegssituation.

Elementarprägung und endgültige Wesenform sollen nicht einfach im Charaktereditor gewählt werden. Sie entstehen durch das spätere Spiel.

Die genaue Bandbreite des Charaktereditors ist offen.

## 7. Die drei anfänglichen Grundklassen

**BESTÄTIGT als anfängliche Auswahl:**

1. **Krieger** – Nahkampf, Verteidigung, offensive Durchbrüche und unterschiedliche Waffenstile.
2. **Schamane/Alchemist** – eine kombinierte Grundklasse, nicht zwei getrennte Startklassen. Mögliche Richtungen umfassen Geister, Elemente, Alchemie, Unterstützung, Kontrolle und Beschwörung.
3. **Bogenschütze** – Fernkampf, Präzision, Mobilität, Fallen und unterschiedliche Schusstechniken.

Die Klassennamen sind Arbeitsbezeichnungen und dürfen später eigenständig gestaltet werden.

Weitere Startklassen sind derzeit nicht beschlossen. Die Architektur soll spätere Klassen aufnehmen können, ohne die gesamte Charakterentwicklungslogik neu zu schreiben.

## 8. Klassenidentität und Bewegungsmechaniken

**BESTÄTIGT:** Die Klassen sollen unterschiedliche Bewegungsmechaniken besitzen. Nicht alle Klassen verwenden dieselben Bewegungen nur mit anderen Animationen.

Mögliche Beispiele (noch nicht final):

- Krieger: Vorstöße, schwere Ausweichschritte, Sprünge, Blocks und Konterbewegungen.
- Schamane/Alchemist: magisch unterstützte Bewegung, Geisterbewegung, kontrollierte Luft- oder Elementarbewegung.
- Bogenschütze: schnelle Positionswechsel, Rückwärtssprünge, seitliche Ausweichbewegungen und Luftmanöver.

Diese Beispiele sind Entwicklungsrichtungen, keine endgültig beschlossenen Skilllisten.

Jede Klasse soll außerdem eine eigene, sich entwickelnde visuelle Manifestation erhalten. Nicht jeder Charakter soll dieselben Flügel besitzen. Eine Manifestation kann beispielsweise Rüstung, Energieerscheinung, Geisterstruktur, spirituelles Wesen, Waffe oder andere klassenspezifische Form annehmen.

---

# TEIL IV – WESENSMATRIX UND INDIVIDUELLE CHARAKTERENTWICKLUNG

## 9. Zentrales Charakterprinzip

**BESTÄTIGT:** Nicht nur die Klasse oder das Kampfsystem formt den Charakter. Berufliche Tätigkeiten, Forschung, Entdeckungen, Entscheidungen, wirtschaftliche Aktivitäten, Erkundung, soziale Zusammenarbeit und die gesamte Spielgeschichte sollen die Charakteridentität beeinflussen.

Ein Charakter soll sich als Kämpfer, Handwerker, Forscher, Händler, Unternehmer, Entdecker oder Kombination daraus entwickeln können.

Die Wesensentwicklung darf nicht ausschließlich durch eine feste Auswahl oder einen einzelnen Levelaufstieg bestimmt werden.

## 10. Wesensmatrix – Arbeitsbegriff

**DESIGNRICHTUNG:** Eine zentrale datengetriebene Wesensmatrix sammelt und interpretiert validierte Spielhistorie.

Sie soll folgende Dimensionen verbinden:

- Körperliche und übernatürliche Prägung.
- Kampfstil und Kampfmeisterschaft.
- Elementare Affinitäten und Kombinationen.
- Berufliche Meisterschaft.
- Handwerkliche Techniken und Herstellungswissen.
- Forschung und Entdeckungen.
- Erkundung und Überleben.
- Wirtschaftliche Tätigkeiten und Unternehmensentwicklung.
- Zusammenarbeit, Unterstützung und Gruppenleistungen.
- Wichtige Entscheidungen und besondere Ereignisse.
- Dauerhafte Wesenidentität.

Das System analysiert ausschließlich die belegbaren Handlungen der Spielfigur innerhalb des Spiels. Es darf nicht versuchen, die reale Persönlichkeit, psychische Eigenschaften oder privaten Daten des Spielers zu analysieren.

## 11. Dauerhafte Wesenentwicklung

**BESTÄTIGT:**

- Spieler und NPCs beginnen als Menschen.
- Ihre Entwicklung und Erfahrung kann sie zu anderen Wesenformen prägen.
- Eine Wesenform entsteht aus Fähigkeiten, Spielweise, Charaktergeschichte und weiteren Aktivitäten.
- Der Spieler entdeckt mögliche Entwicklungen durch Spielhandlungen, Prüfungen und besondere Ereignisse.
- Die Annahme der großen Wesenverwandlung ist eine bewusste Entscheidung.
- **Die angenommene Wesenform ist dauerhaft und kann nicht rückgängig gemacht oder durch eine andere Wesenform ersetzt werden.**
- Eine bereits angenommene Wesenform darf sich innerhalb ihres Entwicklungspfades weiterentwickeln.
- Wesenformen besitzen eigene Vorteile, Nachteile und Spielmöglichkeiten.

### 11.1 Keine willkürlichen Nachteile

Stärken und Schwächen sollen aus dem jeweiligen Entwicklungsweg und der Mechanik entstehen. Kein willkürlicher globaler Malus wie „alle Schattenwesen erhalten pauschal X Prozent mehr Lichtschaden“, sofern dafür keine nachvollziehbare Spielmechanik und Balancebegründung besteht.

Beispiele:

- Ein stark defensiv entwickeltes Wesen kann Schutz und Kontrolle besitzen, aber geringere Burst-Möglichkeiten.
- Ein aggressiv entwickeltes Wesen kann hohe Angriffskombinationen beherrschen, aber verwundbarer sein.
- Eine starke Handwerksprägung kann außergewöhnliche Herstellungsverfahren ermöglichen, ohne automatisch Kampfwerte zu erhöhen.

### 11.2 Wesenformen sind nicht nur Elementarformen

**DESIGNRICHTUNG:** Neben elementaren Prägungen sollen auch andere Wesenentwicklungen möglich sein, die aus Berufen, Handwerk, Forschung, Erkundung, Entscheidungen oder besonderen Lebenswegen entstehen.

Beispielrichtungen:

- Feuer-/Metallprägung durch Schmiedekunst und besondere Materialien.
- Naturprägung durch seltene Botanik, Alchemie und Wiederherstellung.
- Schattenprägung durch Täuschung, Mobilität oder spezielle Begegnungen.
- Andere besondere Wesenpfade, die erst durch Inhalte und Entdeckungen bekannt werden.

Die konkrete Anzahl, Namen und Voraussetzungen der Formen sind offen und müssen von Designern bewusst erstellt und balanciert werden.

## 12. Charakterhistorie, aktuelle Entwicklung und Identität

**DESIGNRICHTUNG:** Drei Schichten sollen getrennt sein:

1. **Lebensgeschichte:** Dauerhafte, validierte Ereignisse und wichtige Entscheidungen.
2. **Aktuelles Profil:** Gegenwärtige Schwerpunkte, Affinitäten, Meisterschaften und Fähigkeiten.
3. **Wesenidentität:** Dauerhaft angenommene Form und langfristige Eigenschaften.

Ein Spieler, der nach hunderten Stunden einen anderen Stil erlernt, soll seine gesamte Geschichte nicht verlieren. Die vorherige Entwicklung bleibt nachvollziehbar, auch wenn sich aktuelle Schwerpunkte verschieben.

## 13. Millionen mögliche Charakterprofile

**BESTÄTIGT als Ziel:** Das System soll extrem viele unterschiedliche Charaktere und Entwicklungsverläufe ermöglichen. Charaktere sollen in Fähigkeiten, Wesen, Beruf, Erscheinung, Wissen, wirtschaftlichen Möglichkeiten und Geschichte unterschiedlich sein.

**Technische Klarstellung:** Wir implementieren nicht Millionen separat programmierte Charaktertypen oder permanent laufende Berechnungen. Wir verwenden eine große, kontrollierte Kombination aus:

- Validierter Spielhistorie.
- Datengetriebenen Profilwerten und Merkmalen.
- Designer-authored Fähigkeiten und Wesenformen.
- Modulen für Elemente, Berufe, Kampf und Entdeckungen.
- Modularen Animationen und visuellen Variationen.
- Begrenzten, getesteten Interaktionsregeln.

Das Ziel sind Millionen sinnvolle Kombinationen, nicht mathematisch garantierte Einzigartigkeit jeder einzelnen Fähigkeit oder des Kampfausgangs. Zwei Charaktere können ähnliche Profile besitzen, sollen aber durch Geschichte und Kombinationen eine hohe Individualität erhalten.

---

# TEIL V – BERUFE, MEISTERSCHAFT UND HANDWERK

## 14. Berufe sind vollwertige Progressionspfade

**BESTÄTIGT:** Das berufliche System muss genauso bedeutend sein wie Kampf und Charakterentwicklung. Ein Spieler soll langfristig ein außergewöhnlicher Handwerker, Forscher, Händler, Unternehmer oder anderer Spezialist werden können.

Berufe sind keine kleinen Nebenmenüs oder bloße Balken, die man nebenbei füllt.

Mögliche Berufsgruppen (Roster noch offen):

- Bergbau und Erzgewinnung.
- Kräutersammeln und Botanik.
- Schmiedekunst und Metallverarbeitung.
- Alchemie und Elixierherstellung.
- Schneiderei und Lederverarbeitung.
- Holzverarbeitung und Tischlerei.
- Architektur und Baukunst.
- Kochen und Lebensmittelproduktion.
- Fischerei und Jagd.
- Forschung und Rezeptentwicklung.
- Handel und Marktanalyse.
- Transport und Logistik.
- Landwirtschaft und Viehzucht.
- Ingenieurwesen und später Maschinenbau.

Diese Liste ist eine Arbeitsliste, keine endgültige Berufsauswahl.

## 15. Individuelle berufliche Entwicklung

Zwei Spieler desselben Berufs sollen sich unterschiedlich entwickeln können.

Beispiel Schmied:

- Ein Spieler spezialisiert sich auf schwere Waffen und hitzebasierte Metallverarbeitung.
- Ein anderer spezialisiert sich auf leichte Rüstung, Schattenmaterialien und besondere Legierungen.

Beispiel Alchemist:

- Ein Spieler entwickelt Heilmittel und Elixiere.
- Ein anderer konzentriert sich auf Gifte, elementare Reaktionen oder seltene Reagenzien.

Das Ergebnis soll nicht durch frei erfundene, unkontrollierte Laufzeitgenerierung entstehen. Die Engine erkennt geeignete Muster und schaltet bewusst designte Techniken, Rezepte oder Prüfungen frei.

## 16. Herstellungsverfahren und Meisterstücke

**DESIGNRICHTUNG:** Erfahrene Spieler sollen nicht nur Rezepte freischalten, sondern durch Experimente, seltene Materialien und Wissen besondere Herstellungsverfahren entdecken können.

Mögliche Ergebnisse:

- Neue Legierungen.
- Spezielle Schmiedeverfahren.
- Seltene alchemistische Rezepturen.
- Besondere Koch- und Konservierungsmethoden.
- Architektur- und Bauvarianten.
- Neue Antriebstechniken in späteren Epochen.

Entdeckungen können zunächst exklusiv sein, später aber über Lizenzen, Baupläne, Lehre, Handel oder Forschung verbreitet werden. Welche Entdeckungen dauerhaft exklusiv bleiben, wird pro Inhalt bewusst definiert.

---

# TEIL VI – KAMPFECHOS, RESONANZ UND ELEMENTE

## 17. Kampfechos – Arbeitsbegriff

**DESIGNRICHTUNG, vom Nutzer grundsätzlich bestätigt:** Das Spiel soll den Reiz handelbarer Spezialisten-/Kampfobjekte aus klassischen MMORPGs aufgreifen, aber als eigenständiges modernes 3D-System umsetzen.

Der Arbeitsbegriff lautet **Kampfecho**. Der endgültige In-Game-Name ist offen.

Ein Kampfecho steht für eine Kampftradition oder spezielle Entwicklung. Es kann Fähigkeiten, Animationen, Bewegungen, Manifestationen und Spielstil beeinflussen.

Es ist nicht einfach ein 2D-Kärtchen und keine bloße kosmetische Verwandlung. Es muss im modernen 3D-Spiel eine sichtbare und spielerisch relevante Identität besitzen.

## 18. Haupttradition und Kombination

**BESTÄTIGT:** Hybridsystem.

- Eine aktive Haupttradition bestimmt den grundlegenden Kampfstil.
- Aus anderen freigeschalteten Traditionen können ausgewählte Fähigkeiten und passive Eigenschaften integriert werden.
- Der Charakter soll dadurch individuell werden, ohne dass jede beliebige Kombination möglich und dominant ist.
- Kampfechos können klassenspezifisch oder in seltenen Fällen klassenübergreifend sein.
- Wenn eine Klasse ein bestimmtes Kampfecho nicht nutzen kann, muss sie eigene gleichwertig interessante Entwicklungsalternativen besitzen.

## 19. Resonanz +0 bis +30

**BESTÄTIGT:** Das Upgrade-System geht bis **+30**. Mit steigender Stufe sinkt die Erfolgswahrscheinlichkeit. Die optische und spielerische Entwicklung soll deutlich sichtbar sein.

Vorgeschlagene visuelle Meilensteine:

| Bereich | Arbeitsname | Mögliche Veränderung |
|---|---|---|
| +0 bis +4 | Erweckung | Grundform und erste sichtbare Effekte |
| +5 bis +9 | Manifestation | Deutlichere Effekte und erste neue Ausprägungen |
| +10 bis +14 | Erweiterte Form | Fähigkeiten und Animationen entwickeln sich sichtbar |
| +15 bis +19 | Erhabene Form | Aufwendigere Manifestation und besondere Effekte |
| +20 bis +24 | Legendäre Form | Sehr auffällige Erscheinung und besondere Animationen |
| +25 bis +30 | Mythische Form | Höchste Entwicklungsstufen und außergewöhnliche Effekte |

Diese Stufenbereiche sind ein Konzeptvorschlag. Exakte Schwellen, Erfolgsraten, Materialkosten, Statuseffekte und Animationen sind offen.

### 19.1 Upgrade-Fehler und Schutz

**BESTÄTIGT:** Kombination aus Risiko und Schutz.

- Erfolgreiches Upgrade erhöht die Resonanzstufe.
- Bei Fehlschlag gehen die eingesetzten Materialien oder Kosten verloren.
- Bei höheren Stufen kann die Resonanzstufe sinken.
- Schutzgegenstände oder Sicherungsmechanismen können Stufenverlust verhindern.
- Ein Pechschutz soll nach Fehlschlägen die nächste Erfolgschance schrittweise verbessern.
- Das Kampfecho darf durch einen einzelnen Fehlversuch nicht vollständig zerstört werden.

Genaue Wahrscheinlichkeiten, Schutzstufen und Pechschutzkurven sind OFFEN.

### 19.2 Optische Qualität

Die Verbesserung muss in einer hochwertigen 3D-Umsetzung spürbar werden:

- Sichtbar veränderte Manifestationen.
- Neue oder erweiterte Animationen.
- Veränderte Waffen- und Angriffserscheinung.
- Elementare Partikel und Effekte.
- Besondere Bewegungs- oder Fähigkeitseffekte.

Nicht jede der 30 Stufen benötigt vollständig neue Modelle und Animationen. Das visuelle System soll modulare Assets, Materialparameter, Animationslayer, Effektvarianten und klar definierte Meilensteine kombinieren.

Optische Effekte dürfen die Gegnerlesbarkeit und Performance nicht zerstören. Größere VFX bedeuten nicht automatisch größere Trefferflächen oder unverhältnismäßig mehr Schaden.

## 20. Handelbarkeit von Kampfechos

**BESTÄTIGT:**

1. Unaktivierte Kampfechos sind handelbar.
2. Nach Aktivierung wird das Kampfecho zunächst charaktergebunden.
3. Ein besonderer Gegenstand (Arbeitsname: Resonanzsiegel) kann es wieder handelbar machen.
4. Beim Verkauf bleibt der vollständige Resonanzstand erhalten.
5. Freigeschaltete Resonanzfähigkeiten und visuelle Entwicklungsstufen bleiben am Gegenstand erhalten.
6. Die persönliche Meisterschaft des Verkäufers wird nicht auf den Käufer übertragen.
7. Der Käufer erhält den Gegenstand mit seiner bestehenden Resonanzstufe und kann ihn weiterentwickeln.

**VORSCHLAG:** Resonanzsiegel durch anspruchsvolle Spielinhalte und/oder seltene Herstellung verfügbar machen, nicht als unbegrenzten Echtgeldshop-Boost. Einzigartige oder serverexklusive Inhalte dürfen durch Handel nicht vervielfältigt werden.

## 21. Persönliche Meisterschaft

Resonanz und Meisterschaft sind getrennt:

- **Resonanz:** Fortschritt des Kampfechos von +0 bis +30.
- **Meisterschaft:** persönliche Erfahrung und Beherrschung des Spielers mit der jeweiligen Kampftradition.

Meisterschaft kann zusätzliche Kombos, Varianten, Timingoptionen, Techniken oder individuelle Ausführungen freischalten. Sie muss eigenständig balanciert werden und darf den Handel nicht zu einem Umweg machen, um persönliche Leistung zu kaufen.

---

# TEIL VII – ELEMENTARSYSTEM

## 22. Die neun aktuellen Elemente

**BESTÄTIGT:**

1. Feuer
2. Wasser
3. Schatten
4. Licht
5. Wind
6. Erde
7. Elektro/Strom
8. Eis
9. Natur

Blitz wird zunächst als mögliche Erscheinungs- oder Effektform von Elektro/Strom behandelt, nicht als separates zehntes Element.

## 23. Freie Elementarkombinationen

**BESTÄTIGT:** Es gibt keine fest vorgeschriebenen Elementarpaare. Jede freigeschaltete Elementarzuordnung kann grundsätzlich mit einer anderen kombiniert werden.

Bei neun Elementen gibt es 36 mögliche Zweifachkombinationen und 84 mögliche Dreifachkombinationen (jeweils ohne Reihenfolge und ohne Wiederholung).

- Zwei Elemente: reguläre erweiterte Kombination, sobald beide freigeschaltet sind.
- Drei Elemente: außergewöhnliche, seltene Endgame-Entwicklung.
- Freischaltung und besondere Erweiterungen können über Quests, Experimente, Forschung, Bosse und seltene Entdeckungen erfolgen.
- Eine freie Kombination darf nicht automatisch bedeuten, dass jede Fähigkeit beliebig und ohne Balancegrenzen stapelbar ist.

## 24. Klassenabhängige Elementarwirkung

Dasselbe Element oder dieselbe Kombination muss je nach Klasse anders funktionieren.

Beispiel: Schatten + Wind kann beim Krieger ein anderes Kampfverhalten, beim Schamanen einen anderen Geist oder eine andere Beschwörung und beim Bogenschützen eine andere Projektil- oder Bewegungsmechanik hervorbringen.

Beispielhafte Ideen, noch nicht final:

- Schatten: Schattenklone, Täuschung, Teleportation, kleine Dämonen als Begleiter.
- Wind: Luftkontrolle, Wirbel, Beschleunigung, Luftbewegung.
- Feuer: Verbrennung, Druck, Explosion, Hitzeeffekte.
- Wasser: Strömungen, Druck, Kontrolle und mögliche regenerative Effekte.
- Licht: Schutz, Reinigung, Verstärkung und Blendung.
- Erde: Stabilität, Gestein, Barrieren und Erschütterung.
- Elektro: Entladungen, Kettenreaktionen und Überlastung.
- Eis: Einfrieren, Verlangsamung und Barrieren.
- Natur: Wurzeln, Pflanzen, Sporen und Kreaturen.

Diese Effekte sind Ideen, keine endgültigen Mechanikwerte.

## 25. Entdeckung und verborgene Elementarentwicklungen

**DESIGNRICHTUNG:** Spieler können Kombinationen grundsätzlich selbst zusammenstellen, wenn die Elemente freigeschaltet sind. Bestimmte besondere Varianten, Manifestationen oder Fähigkeiten werden aber erst durch Geheimquests, Experimente, seltene Bosse, Forschungsprojekte oder Entdeckungen verfügbar.

Elementkombinationen dürfen nicht nur zusätzliche Schadensfarben sein. Sie können neue Fähigkeiten, Bewegung, Kontrolle, Beschwörungen, Verteidigungsreaktionen oder Umgebungsinteraktionen ermöglichen.

## 26. Aktives Elementmanagement

**OFFEN:** Es ist noch nicht festgelegt, wie viele Elemente im Kampf gleichzeitig aktiv sein können, wie Elementwechsel funktionieren oder ob manche Kombinationen vor dem Kampf vorbereitet werden müssen.

Bis zur finalen Entscheidung soll die Architektur flexible Loadouts unterstützen, ohne eine bestimmte Wechselmechanik fest einzubauen.

---

# TEIL VIII – ACTION-KAMPFSYSTEM

## 27. Perspektive und Steuerung

**BESTÄTIGT:**

- Third-Person-Kamera hinter dem Charakter.
- Frei drehbare Kamera.
- Direkte Steuerung des Charakters.
- Kein Auto-Kampf als Kernspielmechanik.
- Spieler steuern Bewegung und Angriffe selbst.
- Springen und echte Bewegungsmechaniken sind wichtig.

## 28. Kampfgefühl

**BESTÄTIGT:** Mischung aus schnellen, flüssigen Kombos und schwereren, taktischen Kampfaktionen.

- Schnelle Grundangriffe und Komboketten.
- Schwere und aufgeladene Angriffe.
- Ausweichmanöver und Konter.
- Richtungsabhängige Attacken.
- Gehaltene oder kanalisierte Fähigkeiten.
- Klassenabhängige Bewegung und Fähigkeiten.
- Waffen und Rüstungen verändern tatsächliche Bewegungs- und Kampfoptionen.

## 29. Kampfsystem mit hoher systemischer Tiefe

**BESTÄTIGT als Designziel:** Komplexe Hintergrundberechnung, aber verständliche UI. Das Kampfsystem soll sich im Laufe des Spiels immer tiefer erschließen. Es soll überraschende, aber regelbasierte Wechselwirkungen und Entdeckungen ermöglichen.

„Random“ bedeutet hier nicht, dass zufällige Würfelwürfe unfaire Kämpfe entscheiden. Gemeint ist eine vielfältige und nicht sofort vollständig vorhersehbare Interaktion vieler Systeme. Ergebnisse müssen reproduzierbar, testbar und durch Können beeinflussbar bleiben.

Mögliche Berechnungsebenen:

- Grund- und Waffenschaden.
- Elementarschaden und Widerstände.
- Rüstung und Durchdringung.
- Kritische Treffer.
- Statuswirkungen.
- Haltung, Gleichgewicht und Unterbrechungen.
- Angriffswinkel und Position.
- Bewegung und Timing.
- Temporäre Effekte.
- Fähigkeiten- und Elementarinteraktionen.
- Umgebungs- und Gruppeninteraktionen.

Die tatsächliche Formel ist noch nicht final.

## 30. PvE und PvP

**BESTÄTIGT:** Ein Charakter und eine grundlegende Progression sollen sowohl für PvE als auch PvP gelten. Es soll keine zwingende separate PvE-/PvP-Klassenentwicklung geben.

Die Balance muss verhindern, dass nach Patches eine Klasse oder ein Build die gesamte Spielerschaft dominiert. Der Nutzer hat ausdrücklich als Negativbeispiel genannt, dass nach Balanceänderungen ein Großteil des Servers dieselbe Klasse spielen könnte.

Mögliche Gegenmaßnahmen:

- Mehrere konkurrenzfähige Builds je Klasse.
- Unterschiedliche Gegenmechaniken und Counterplay.
- Stärken mit nachvollziehbaren Kosten und Schwächen.
- Kontextabhängige Koeffizienten, falls PvP-Anpassungen nötig sind.
- Telemetrie und regelmäßige Balanceauswertung.

Konkrete PvP-Modi, Arenen, Schlachten und Regeln sind OFFEN.

## 31. Ausrüstung und kosmetische Freiheit

**BESTÄTIGT:**

- Ausrüstung soll Spielstil, Fähigkeiten, Animationen und Bewegungsoptionen beeinflussen, nicht nur Zahlenwerte.
- Schwere und leichte Ausrüstung können unterschiedliche Vor- und Nachteile besitzen.
- Waffen können eigene Angriffsmuster und selten alternative Kampfstile ermöglichen.
- Optische Freiheit soll von Kampfwerten getrennt werden können (Transmog/Appearance-System).

Details zu Slots, Seltenheiten, Setboni und Herstellungsrezepten sind offen.

---

# TEIL IX – WELT, ERKUNDUNG UND FORTBEWEGUNG

## 32. Geografischer Aufbau

**BESTÄTIGT:** Ein großer Hauptkontinent bildet den Ausgangspunkt. Ergänzt wird er durch Inselgruppen und weitere Kontinente, die später über Erkundung und Updates erschlossen werden können.

## 33. Weltstruktur

**BESTÄTIGT:** Große, weitgehend zusammenhängende Welt mit unterschiedlichen Regionen. Einige Übergänge können nahtlos sein, andere über Reisepunkte, Schiffe, Tore oder besondere Übergänge erfolgen. Dungeons und einzelne Aktivitäten können eigene Instanzen besitzen.

## 34. Freie Erkundung und Gefahrenstufen

**BESTÄTIGT:** Die Welt ist grundsätzlich frei erkundbar. Normale Regionen sollen nicht durch starre Levelschranken abgesperrt werden.

- Regionen besitzen unterschiedliche Gefahrenstufen.
- Starke Gegner können unerfahrene Spieler besiegen.
- Besondere Bereiche dürfen spezielle Voraussetzungen verlangen.
- Erkundung, Vorbereitung, Ausrüstung und Wissen sind wichtig.
- Mutige Spieler können früh gefährliche Gebiete betreten und seltene Inhalte entdecken.

## 35. Fortbewegung und technologische Entwicklung

**BESTÄTIGT:** Kombination aus klassischer und später technisch weiterentwickelter Fortbewegung.

Mögliche Stufen:

- Zu Fuß und klassenspezifische Bewegungsfähigkeiten.
- Pferde, Reittiere und Kutschen.
- Schiffe und maritime Reisen.
- Gleiter und besondere Bewegungsformen.
- Später mechanische und dampfbetriebene Fahrzeuge.
- In späteren Epochen Motorräder und Autos, abhängig von der technologischen Entwicklung der Stadt.
- Langfristig weitere fortgeschrittene Fahrzeuge und Transportformen.

Die Spieler sollen Fahrzeuge nicht einfach als kosmetische Gegenstände erhalten. Straßen, Werkstätten, Ersatzteile, Energie/Treibstoff, Produktion und Wartung sollen in der jeweiligen Epoche sinnvoll eingebettet sein.

---

# TEIL X – NPCs, SPIELERSTÄDTE UND WIRTSCHAFT

## 36. Zentrale Hauptstadt und Spielersiedlungen

**BESTÄTIGT:** Es gibt eine zentrale Hauptstadt und zusätzlich mehrere Spielersiedlungen.

- Die Hauptstadt ist ein gemeinsamer Mittelpunkt mit wichtigen Dienstleistungen, NPCs, Handel und Weltzugängen.
- Neue Siedlungen entstehen in vorgesehenen Siedlungsgebieten.
- Innerhalb der Gebiete gestalten Spieler die Stadtstruktur weitgehend selbst.
- Persönliche Grundstücke und große Gemeinschaftsprojekte existieren parallel.
- Siedlungen können sich wirtschaftlich und gesellschaftlich unterschiedlich entwickeln.

## 37. Persönlicher Besitz und Gemeinschaftsprojekte

**BESTÄTIGT:** Zwei Ebenen des Städtebaus:

1. **Persönlicher Besitz:** Grundstücke, Häuser, Geschäfte und Unternehmen können erworben, bebaut, erweitert und wirtschaftlich genutzt werden.
2. **Gemeinschaftlicher Fortschritt:** Bewohner investieren Geld, Materialien und Arbeit in Straßen, Mauern, Marktplätze, Häfen, Lagerhäuser, öffentliche Gebäude und weitere Infrastruktur.

Gebäude und Infrastruktur sollen echte Auswirkungen haben. Ein Hafen eröffnet beispielsweise neue Handelsmöglichkeiten; Straßen können Logistik und Zugänglichkeit beeinflussen.

## 38. Dynamische NPC-Wirtschaft

**BESTÄTIGT:** Kombination aus Spielermarkt und dynamischer NPC-Weltwirtschaft.

NPCs sind Produzenten, Händler, Bewohner und Auftraggeber mit eigenem Bedarf. Regionen und Städte können Waren benötigen, produzieren oder durch Ereignisse beeinflusst werden.

Beispiele:

- Eine schlechte Ernte erhöht den Lebensmittelbedarf.
- Ein Krieg steigert den Bedarf an Waffen und Versorgung.
- Eine neue Mine bringt Erze in den Handel.
- Ein neuer Hafen öffnet Handelsrouten.
- Ein Monsterangriff beeinträchtigt Versorgung oder Transport.

NPC-Betriebe können mit Spielerunternehmen konkurrieren. Spieler können sie durch Qualität, Spezialisierung, bessere Organisation oder größere Produktionskapazität übertreffen.

NPCs dürfen keine unbegrenzten Waren oder unendliche Geldquellen erzeugen. Nachfrage und Angebot müssen nachvollziehbar simuliert werden.

## 39. Spielerunternehmen

**BESTÄTIGT:** Spieler können echte Unternehmen mit Gebäude, Ausstattung, Levelsystem, Mitarbeitern und wirtschaftlichen Prozessen besitzen.

Mögliche Betriebe:

- Schmiede und Waffenmanufaktur.
- Alchemielabor.
- Handelsgeschäft.
- Taverne und Gasthaus.
- Sägewerk und Steinbruch.
- Landwirtschaft.
- Lagerhaus.
- Werkstatt.
- Transport- und Logistikbetrieb.

### 39.1 Gebäude- und Unternehmenslevel

Gebäude und Unternehmen sind getrennte, aber verbundene Fortschrittssysteme:

- Gebäudestufe: Platz, Ausstattung, Arbeitsplätze, Lager und Produktionsmöglichkeiten.
- Unternehmensstufe: Ruf, Effizienz, Kundschaft, Qualität, Aufträge und wirtschaftliche Entwicklung.

Ein großes Gebäude garantiert nicht automatisch einen erfolgreichen Betrieb.

### 39.2 NPC-Mitarbeiter

Spieler können begrenzt NPC-Mitarbeiter einstellen.

Beispiele:

- Verkäufer.
- Schmiede und Produktionskräfte.
- Lagerverwalter.
- Köche und Servicepersonal.
- Buchhalter und Verwalter.
- Transport- und Lieferpersonal.

Die Mitarbeiterkapazität hängt von Gebäude, Unternehmensentwicklung und verfügbaren Arbeitsplätzen ab. Keine unbegrenzte Personalanstellung.

### 39.3 Normale Mitarbeiter und einzigartige Spezialisten

**BESTÄTIGT:** Es gibt gewöhnliche Mitarbeiter und besondere Spezialisten.

- Normale Mitarbeiter sind relativ einfach verfügbar, besitzen unterschiedliche Fähigkeiten und Gehaltsvorstellungen und können ausgebildet werden.
- Besondere Spezialisten besitzen Namen, Persönlichkeiten, Hintergrundgeschichten, seltene Fähigkeiten und eigene Ziele.
- Spezialisten können über Quests, Entdeckungen, Ereignisse und besondere Begegnungen gefunden werden.
- Sie können besondere Produktionsmöglichkeiten oder Techniken ermöglichen.

### 39.4 Loyalität und Abwerbung

**BESTÄTIGT:** Mitarbeiter besitzen individuelle Loyalität und Zufriedenheit. Gute Behandlung, Gehalt, Arbeitsbedingungen, Entwicklung und Unternehmensführung beeinflussen ihre Bindung.

Mitarbeiter können kündigen, aber nicht ohne nachvollziehbare Warnzeichen. Unzufriedenheit, Beschwerden, Kündigungsabsicht und Wechsel sollen als Prozess erkennbar sein.

Spielerunternehmen dürfen Mitarbeiter anderer Spieler abwerben. Der Mitarbeiter entscheidet jedoch anhand von Angebot, Loyalität, Arbeitsbedingungen und persönlichen Zielen.

### 39.5 Offline- und Online-Betrieb

**BESTÄTIGT:** Unternehmen laufen offline eingeschränkt weiter. Aktives Management durch den Spieler eröffnet zusätzliche Möglichkeiten.

Offline:
- Begrenzte Routineproduktion.
- Begrenzte Lager- und Produktionskapazität.
- Verbrauch von Materialien und Betriebskapital.
- NPC-Gehälter und Betriebskosten.

Online/aktiv:
- Besondere Aufträge.
- Produktionsoptimierung.
- Mitarbeitertraining.
- Höhere oder spezielle Produktionsmöglichkeiten.
- Neue Märkte und Lieferketten.

Keine unbegrenzte passive Geldmaschine.

### 39.6 Spieler als Mitarbeiter und Karriere

**BESTÄTIGT:** Spieler können bei anderen Spielern arbeiten und langfristige Karrieren machen.

Mögliche Rollen:

- Mitarbeiter.
- Spezialist.
- Abteilungsleiter.
- Betriebsleiter.
- Geschäftsführer.

Ein Spieler kann Führungsaufgaben übernehmen, ohne Eigentümer zu sein. Eigentum und Geschäftsführung müssen getrennt bleiben. Berechtigungen für Personal, Finanzen, Lager und Investitionen müssen präzise kontrolliert werden.

Vergütungsmodelle:

- Festgehalt.
- Auftragszahlung.
- Gewinnbeteiligung.
- Unternehmensanteile.

### 39.7 Unternehmensanteile und Verfassungen

**BESTÄTIGT:** Unternehmen können Anteilseigner haben. Bestehende Gesellschafter erhalten bei einem Anteilverkauf zunächst ein Vorkaufsrecht.

Jedes Unternehmen kann eine eigene Verfassung definieren, zum Beispiel:

- Stimmrechte.
- Geschäftsführung.
- Investitionsentscheidungen.
- Personalrechte.
- Gewinnverteilung.
- Verkaufs- und Übertragungsregeln.

Bestehende Rechte müssen vor einem Anteilskauf transparent sein. Änderungen dürfen Beteiligungsrechte nicht rückwirkend willkürlich entwerten.

Unternehmensanteile sind ausschließlich spielinterne Rechte. Eine Verbindung mit realen Finanzanlagen, NFTs oder externen Token ist nicht Teil des beschlossenen Grundkonzepts.

### 39.8 Unternehmensimperien

**BESTÄTIGT:** Unternehmen können sich zu größeren Gruppen entwickeln:

- Hauptunternehmen.
- Filialen und Niederlassungen.
- Tochterunternehmen.
- Unterschiedliche Geschäftsbereiche.
- Eigene Betriebsleiter und Geschäftsführer.
- Unternehmensübergreifende Lieferketten.

Größe soll Verantwortung und Risiko bringen: Personal, Versorgung, Ruf, Kapital, Verwaltung, Verträge und Betriebskosten.

## 40. Spielerhandel und Logistik

**DESIGNRICHTUNG:** Gemeinsamer Marktüberblick mit regionaler Warenlagerung und organisierbaren Lieferungen.

- Direkter Spielerhandel.
- Kauf- und Verkaufsangebote.
- Eigene Geschäfte und Verkaufsstände.
- Regionale Märkte und Lagerbestände.
- Lieferverträge und Transportaufträge.
- Handel mit Kampfechos und seltenen Gegenständen.

Gewöhnliche Einkäufe dürfen nicht unnötig erzwungene Transportarbeit verlangen. Logistik soll ein echter Beruf und eine echte Möglichkeit sein, aber keine lästige Pflicht für jeden Spieler.

## 41. Wirtschaftliche Stabilität

Erforderliche Schutzmaßnahmen:

- Geldsenken und laufende Kosten.
- Kontrolle von NPC-Geld- und Warenquellen.
- Manipulationsschutz im Markt.
- Serverseitige, atomare Transaktionen.
- Anti-Duplikationsmechanismen.
- Auditierbare Eigentumsübertragungen.
- Schutz gegen Bots und Exploits.
- Keine unbegrenzte passive Produktion.
- Wirtschaftliche Telemetrie und Inflationsmessung.

---

# TEIL XI – FORSCHUNG UND TECHNOLOGISCHE EPOCHEN

## 42. Technologischer Start und langfristige Entwicklung

**BESTÄTIGT:** Das Spiel beginnt in einer klassischen/historischen Fantasy-Epoche. Langfristig kann die Welt über Updates und Spielerentwicklung neue industrielle, moderne und futuristische Technologien erreichen.

Die genaue Epoche, Namen und Weltgeschichte sind noch offen.

## 43. Weltweiter und lokaler Fortschritt

**BESTÄTIGT:** Kombination aus gemeinsamem weltgeschichtlichem Fortschritt und individueller Stadtentwicklung.

- Entwickler bringen durch Weltgeschichte und Updates neue technologische Möglichkeiten in die Welt.
- Spieler müssen Technologien entdecken, erforschen, herstellen und etablieren.
- Jede Stadt entscheidet, wie schnell und in welche Richtung sie Technologien übernimmt.
- Eine Stadt kann traditionell bleiben, während eine andere industrialisiert wird.
- Städte können sich auf Fahrzeugbau, Energie, Forschung, Handel oder Produktion spezialisieren.

## 44. Entdecker und erste Erfinder

**BESTÄTIGT:** Erste Entdecker sollen besondere Anerkennung und einen zeitlichen technologischen Vorsprung erhalten. Wissen soll sich später durch Handel, Forschung, Zusammenarbeit oder Lizenzen verbreiten können.

Mögliche Belohnungen:

- Historische Erwähnung.
- Besondere Titel und sichtbare Auszeichnungen.
- Temporärer Produktionsvorsprung.
- Erste Herstellungsmöglichkeiten.
- Besondere Materialien oder Baupläne.

Dauerhafte Blockade grundlegender Welttechnologien durch einzelne Spieler soll verhindert werden.

---

# TEIL XII – SOZIALE SYSTEME UND ZURÜCKGESTELLTE POLITIK

## 45. Gilden und Gemeinschaft

Noch nicht vollständig ausgearbeitet. Erforderliche Themen:

- Gilden und gemeinschaftliche Projekte.
- Gildenhäuser und gemeinsame Gebäude.
- Gruppenabenteuer und Raids.
- Gemeinsame Forschung.
- Unternehmens- und Stadtkooperation.
- Neue soziale Treffpunkte und Veranstaltungen.
- Unterstützung für Einzelspieler ohne feste Gilde.

## 46. Stadtpolitik – bewusst zurückgestellt

Der Nutzer hat ausdrücklich entschieden, Politik vorerst nicht weiter auszuarbeiten. Die bereits besprochenen Grundgedanken werden nur als spätere Notiz bewahrt:

- Demokratie und Mitbestimmung sind wichtig.
- Kein dauerhaftes diktatorisches System.
- Bewohner haben gleichwertige Grundstimmen.
- Wirtschaftliche Interessengruppen können eine separate Interessenvertretung erhalten, aber keine zusätzlichen Bürgerstimmen kaufen.
- Gewählte Stadtführung und Stadtrat wurden als Konzept besprochen.
- 30-tägige Amtszeit und vorzeitige Abwahl durch Bürgerreferendum wurden als Richtung gewählt.
- Große grundlegende Stadtentscheidungen sollen direkte Bürgerbeteiligung erhalten.

**Nicht weiter ausarbeiten, solange der Nutzer das Thema nicht wieder aufnimmt.**

---

# TEIL XIII – LANGZEITMOTIVATION UND LIVE-WELT

## 47. Mehrere parallele Fortschrittsachsen

Ein Charakter soll nicht nur durch eine einzige Levelzahl definiert werden.

Mögliche Fortschrittsachsen:

- Grundklasse und Kampfmeisterschaft.
- Kampfechos und Resonanz +0 bis +30.
- Persönliche Meisterschaft je Kampftradition.
- Elementarfreischaltungen und Kombinationen.
- Wesenform und weitere Erhebungen.
- Berufe und berufliche Meisterschaft.
- Handwerksverfahren und Meisterstücke.
- Wissen, Forschung und Entdeckungen.
- Grundstücke, Gebäude und Unternehmen.
- Soziale Leistungen und Gildenaktivitäten.
- Sammlungen, Titel und Weltgeschichte.

Kein einzelner Fortschrittsbereich darf automatisch alle anderen entwerten.

## 48. Weltchronik

**VORSCHLAG:** Besondere Ereignisse, erste Entdeckungen, Stadtgründungen, Weltboss-Siege, technologische Meilensteine und außergewöhnliche Spielerleistungen werden dauerhaft in einer Weltchronik dokumentiert.

## 49. Prestige und seltene Inhalte

Seltene Dinge sollen Geschichten und Leistungen repräsentieren:

- Einzigartige Kampftraditionen.
- Besondere Wesenentwicklungen.
- Seltene Begleiter.
- Außergewöhnliche Herstellungsverfahren.
- Erste Technologieentwicklungen.
- Besondere Gebäude und Stadtprojekte.
- Weltgeschichtliche Erfolge.

Exklusivität muss fair gestaltet sein. Serverexklusive Fähigkeiten dürfen den Zugang zu grundlegenden Spielinhalten nicht für immer unfair blockieren. Ihre Bedingungen, Dauer und Gegenmöglichkeiten müssen pro Feature festgelegt werden.

---

# TEIL XIV – TECHNISCHE PRODUKTIONSRICHTUNG

## 50. Engine und technische Basis

**VORSCHLAG:** Unreal Engine ist die bevorzugte Kandidatin für den ersten 3D-Prototypen, weil das Projekt hohe Anforderungen an 3D-Grafik, Third-Person-Animationen, Umgebungen, VFX und Action-Gameplay stellt.

Die Engine-Version und finale Engine-Wahl müssen vor Produktionsbeginn anhand eines vertikalen Prototyps, Plattformanforderungen, Netzwerkfunktionen, Lizenzen, Teamkompetenzen und Langzeitwartbarkeit validiert werden. Nicht ungeprüft auf die neueste Version springen.

## 51. Serverautoritative Architektur

**DESIGNRICHTUNG:** Der Client ist nicht die vertrauenswürdige Quelle für Charakterfortschritt, Kampfresultate, Handel, Inventar, Besitz oder permanente Entscheidungen.

Der Server validiert:

- Bewegungs- und Kampfresultate.
- Treffer und Schaden.
- Loot und Inventaränderungen.
- Quest- und Entdeckungsabschlüsse.
- Crafting und Materialverbrauch.
- Markttransaktionen.
- Grundstücks- und Unternehmensbesitz.
- Mitarbeiterverträge und Gehaltszahlungen.
- Resonanz-Upgrades.
- Wesenform-Annahme.
- Technologische Entdeckungen.

## 52. Gemeinsame logische Welt statt isolierter Spielwelten

**BESTÄTIGTE DESIGNRICHTUNG:** Spieler sollen eine gemeinsame logische Welt mit zusammenhängender Wirtschaft, Märkten und sozialen Strukturen erleben.

Technisch darf und soll diese Welt auf mehrere Serverprozesse, Regionen, Instanzen und Backend-Dienste verteilt werden. Technische Skalierung darf nicht als getrennte, isolierte Weltökonomie beim Spieler ankommen.

## 53. Mögliche technische Module

Noch nicht endgültig entschieden; mögliche Architektur:

- Authentication / Account Service.
- Character Service.
- Character History / Evolution Service.
- Combat and Ability Service.
- World / Region Simulation.
- Inventory and Item Service.
- Market / Trading Service.
- Crafting / Profession Service.
- Housing / Plot / Building Service.
- Company / Employee Service.
- NPC Simulation Service.
- Research / Technology Service.
- Quest / Discovery Service.
- Social / Guild Service.
- Persistence / Audit / Telemetry.

Nicht vorschnell in viele Microservices zerschneiden. Zunächst klare Domänengrenzen und Module definieren; technische Verteilung erst nach messbarem Bedarf vornehmen.

## 54. Daten- und Ereignismodell

**DESIGNRICHTUNG:** Charakterhistorie als validierte Ereignisquelle und abgeleitete Profile als Snapshot.

Ein Produktionsereignis benötigt mindestens:

- Eindeutige Event-ID.
- Charakter-ID und Server-/Weltkontext.
- Zeitstempel.
- Aktivitätsdefinition.
- Validierte Tags und strukturierte Metadaten.
- Qualitäts-/Herausforderungsinformationen, falls relevant.
- Regelversion.
- Idempotenzschutz.

Die Datenbank muss Transaktionen, Wiederherstellung, Migration und Audits unterstützen.

## 55. Performance und skalierbare Simulation

- Keine vollständige Charakterneuberechnung pro Frame.
- Profilberechnung inkrementell oder bei relevanten Events.
- NPCs außerhalb aktiver Bereiche abstrakt simulieren.
- Sichtbare 3D-Manifestationen modular und mit LODs implementieren.
- Effekte mit Netzwerk-, GPU- und CPU-Budget versehen.
- Große Welt mit Streaming und Regionssimulation strukturieren.
- Große Stadtmengen mit messbaren Sicht- und Interaktionsbudgets entwickeln.

---

# TEIL XV – BEREITS EXISTIERENDER TECHNISCHER PROTOTYP

## 56. Character Evolution Engine 0.1

Im Projekt existiert bereits der Ordner `mmorpg_character_evolution_v0_1` mit einem Python-Referenzprototyp.

### Implementiert laut bestehendem Projektstand

- Charakter- und Ereignismodelle.
- Validierungsgrenze für Events im Referenzmodell.
- Abgeleitete Charaktermerkmale aus Gameplay-Tags.
- Neun Elementar-Affinitäten und Freischaltungen.
- Alle Zweierkombinationen freigeschalteter Elemente.
- Dreifachkombinationen hinter einem seltenen Meilenstein.
- Berufserfahrung, Berufsstufen und Branch-Mastery.
- Datengetriebene Bedingungen für neue Fähigkeiten.
- Datengetriebene Bedingungen für Wesenform-Kandidaten.
- Bewusste dauerhafte Annahme einer Wesenform ohne Rückkehrfunktion im Prototyp.
- Einfache abnehmende Belohnung für wiederholte identische Aktivitäten.
- Profil-Fingerprint zur Erkennung von Änderungen.
- Demo und automatisierte Tests.

### Noch nicht implementiert

- Unreal Engine C++ Integration.
- Datenbankpersistenz und Migrationen.
- Event Replay Storage.
- Authentifizierung und Anti-Cheat.
- Live-Server-Orchestrierung.
- Vollständiges Kampfsystem.
- GAS-/Animation-/VFX-Integration.
- Aktive Loadouts und Elementwechsel im Kampf.
- Professionelle Produktionssimulation und Rezeptentdeckung.
- Marktintegration.
- NPC-Wesenentwicklung.
- Produktionsreife Balance, Telemetrie und Lasttests.

### Lokale Tests

Aus dem Projektverzeichnis:
```bash
python -m unittest discover -s tests -v
```

Demo:

```bash
python -m evolution.demo
```

Der Referenzprototyp ist bewusst unabhängig von Unreal. Er ist ein prüfbares Modell der Regeln, nicht die fertige Laufzeitimplementierung.

---

# TEIL XVI – OFFENE ENTSCHEIDUNGEN UND DESIGNRISIKEN

## 57. Offene Designfragen

Diese Punkte sind noch nicht final entschieden. Claude Code soll sie nicht eigenmächtig als bestätigte Spielregeln behandeln:

1. Endgültiger Spielname und Lore.
2. Charaktereditor: genaue Körper- und Erscheinungsoptionen.
3. Finale Klassennamen, Waffen, Spezialisierungen und Skilllisten.
4. Wie viele dauerhafte Wesenformen ein Charakter annehmen kann; eine große Form ist die aktuelle Annahme, noch nicht final bestätigt.
5. Ob Wesenformen neben der ersten Erhebung später weitere irreversible Abzweigungen besitzen.
6. Wie Elemente im aktiven Kampf ausgerüstet und gewechselt werden.
7. Wie viele Kampfechos ein Charakter gleichzeitig ausrüsten kann.
8. Exakte Resonanz-Erfolgsraten, Kosten, Abstufungen und Pechschutzkurve.
9. Welche Kampfechos tatsächlich serverexklusiv sind und welche sich später verbreiten.
10. Wie Berufsrespezialisierung und Wechsel funktionieren.
11. Finale Berufsliste und Berufsbranches.
12. Exakte Fähigkeitserzeugung: Unlocks, Varianten, Meisterschaft und Loadouts.
13. Monsterverhalten, Bossmechaniken und Lootregeln.
14. Queststruktur, Hauptgeschichte, Weltgeschichte und Kulturen.
15. PvP-Modi, Schlachten und Balancekoeffizienten.
16. Gilden- und Gruppensystem.
17. Wirtschaftswährung, Marktgebühren, NPC-Preise und Inflationsregeln.
18. Grundstücksgrößen, Besitzgrenzen und Bauregeln.
19. Unternehmensgröße, Anteile, Rollen und Transaktionsregeln im Detail.
20. NPC-Simulation und Offline-Fortschritt in konkreten Zahlen.
21. Technologie- und Epochen-Roadmap.
22. Exakte Spielerzahl pro Region, Stadt, Instanz und logischer Welt.
23. Engine-Version, Netzwerkstack, Backend und Datenbanken.
24. Produktionsbudget, Teamgröße, Assetproduktion und Live-Service-Modell.
25. Monetarisierung. Kein Pay-to-win oder kaufbare unendliche Upgrade-Chancen als Standardannahme.

## 58. Wichtige Risiken

- **Feature-Explosion:** Zu viele Systeme ohne spielbaren Kern.
- **Unkontrollierter Skill-Kombinationsraum:** Jede Kombination einzeln zu produzieren wäre unmöglich.
- **Unbalancierte Individualität:** Ein Build darf nicht einzigartig, aber unbrauchbar oder unbesiegbar werden.
- **Serverlast:** Charakterprofile, NPCs, Städte und Wirtschaft dürfen nicht permanent unnötig neu berechnet werden.
- **Wirtschaftsexploits:** Duplikation, Botting, Inflation und Marktmanipulation.
- **Visueller Aufwand:** Jede Manifestation benötigt Asset-, Animations-, LOD- und Effektplanung.
- **Irreversible Entscheidungen:** Dauerhafte Wesenformen brauchen klare Voraussetzungen, verständliche Vorschau und bewusste Zustimmung.
- **Exklusivität:** Seltene Inhalte dürfen Prestige schaffen, aber nicht das gesamte Spiel für spätere Spieler unzugänglich machen.
- **Offline-Produktion:** Darf keine unendliche passive Geldquelle sein.
- **Technologische Epochen:** Müssen die ursprünglichen Fantasy-Spielstile weiter relevant halten.

---

# TEIL XVII – EMPFOHLENE PRODUKTIONSROADMAP

## 59. Phase 0 – Konzept und Architektur

- Master-GDD konsolidieren.
- Alle Regeln als bestätigt, vorgeschlagen oder offen markieren.
- Systemabhängigkeiten erfassen.
- Datenmodelle und Schnittstellen skizzieren.
- Technische Risiken identifizieren.
- Vertical-Slice-Ziel definieren.

## 60. Phase 1 – Technischer Action-Prototyp

Ziel: Eine kleine Testumgebung, in der sich das Spiel bereits gut anfühlt.

- Third-Person-Bewegung und Kamera.
- Ein spielbarer Krieger.
- Waffen, Grundangriffe, Kombos und Ausweichen.
- Ein einfacher Gegner und ein Boss.
- Ein Element und ein Kampfecho als Test.
- Multiplayer mit Dedicated Server.
- Servervalidierung für Treffer und Schaden.
- Debug-Werkzeuge für Profile und Fähigkeiten.

## 61. Phase 2 – Vertical Slice

- Eine hochwertige Region.
- Eine kleine Stadt/Siedlung.
- Alle drei Klassen in einem begrenzten, testbaren Umfang.
- Erste Berufssysteme.
- Erste Wesenprägung und eine permanente Formprüfung.
- Zwei bis drei Elemente im Kampf.
- Erste Kampfecho-Resonanzstufen.
- Ein Dungeon und ein Weltboss.
- Grundstücke, Gebäude und Gemeinschaftsprojekt.
- Ein einfacher Spielerhandel.

## 62. Phase 3 – MMORPG-Grundsysteme

- Erweiterte Charakterprogression.
- Alle neun Elemente.
- Freie Zweierkombinationen.
- Seltene Dreifachkombinationen.
- Mehrere Kampfechos und Resonanzprogression.
- Breitere Berufsliste.
- NPC-Mitarbeiter und Unternehmen.
- Persistente Spielerstadt.
- Dynamische NPC-Wirtschaft.
- Gilden und soziale Systeme.
- Mehrere Regionen, Dungeons, Raids und Weltbosse.

## 63. Phase 4 – Alpha und Belastungstests

- Serverlast und Regionenwechsel.
- Stadt- und NPC-Simulation.
- Markttransaktionen und Wirtschaftsexploits.
- Anti-Cheat und Sicherheitsprüfung.
- Combat- und PvP-Balance.
- GPU-/CPU- und Netzwerkmessungen.
- Persistenz, Wiederherstellung und Migration.

## 64. Phase 5 – Beta, Release und langfristige Erweiterung

- Weitere Kontinente und Regionen.
- Größere Weltgeschichte.
- Seltene Wesen- und Elementarentwicklungen.
- Unternehmensimperien.
- Technologie- und Epochenfortschritt.
- Neue Transportmittel.
- Neue Berufe, Bossmechaniken und soziale Aktivitäten.

Diese Roadmap ist eine Entwicklungsreihenfolge, kein Zeitversprechen. Termine, Teamgröße und Kosten können erst nach technischen Tests belastbar geschätzt werden.

---

# TEIL XVIII – CLAUDE CODE MASTERPROMPT

> **Diesen gesamten Abschnitt kann Claude Code als verbindlichen Projektauftrag verwenden.**

## 65. Rolle und Auftrag

Du bist der leitende technische Architekt und Senior Gameplay-/Backend-Engineer für ein langfristiges, eigenständiges 3D-Action-MMORPG. Du arbeitest in einem bestehenden GitHub-Repository. Dieses Masterdokument ist die konsolidierte Designgrundlage des Projekts.

Deine Aufgabe ist nicht, sofort blind alle beschriebenen Systeme zu implementieren. Deine Aufgabe ist, das Repository zu untersuchen, bestehende Implementierungen zu bewahren, die Architektur zu verstehen und das Projekt in kleinen, testbaren, produktionsorientierten Schritten weiterzuentwickeln.

Du arbeitest sorgfältig, selbstständig und proaktiv. Du stellst nicht für jede Kleinigkeit Rückfragen. Wenn eine Designfrage offen ist, dokumentierst du eine konservative Annahme, baust keine irreversible harte Abhängigkeit und arbeitest weiter an den Teilen, die eindeutig spezifiziert sind.

## 66. Verbindliche Quellenhierarchie

Verwende diese Priorität:

1. Explizit bestätigte Entscheidungen im Masterdokument.
2. Aktueller, getesteter Code und seine bestehenden Schnittstellen.
3. Als Designrichtung markierte Regeln.
4. Als Vorschlag markierte Ideen.
5. Deine eigenen technischen Vorschläge.

Erfinde keine Bestätigung für offene Punkte. Ändere keine bestätigte Designentscheidung stillschweigend. Falls ein technischer Konflikt existiert, dokumentiere ihn, erkläre Optionen und wähle bis zur Klärung die reversibelste Lösung.

## 67. Nicht verhandelbare Projektanforderungen

- Eigenständiges modernes 3D-Action-MMORPG, nicht 2D und keine Kopie bestehender MMORPGs.
- Windows-PC als erste Zielplattform.
- Realistische, cineastische Fantasy mit skalierbarer Grafik.
- Third-Person und direkte Spielersteuerung; kein Auto-Kampf als Kern.
- Drei anfängliche Klassen: Krieger, Schamane/Alchemist (eine kombinierte Klasse), Bogenschütze.
- Alle Spielercharaktere und NPCs beginnen als Menschen.
- Wesenentwicklung entsteht aus validierter Spielgeschichte und bewussten Prüfungen.
- Angenommene Hauptwesenform ist permanent und nicht reversibel.
- Charakteridentität wird durch Kampf, Berufe, Forschung, Erkundung, Wirtschaft, soziale Beiträge, Entscheidungen und Entdeckungen geprägt.
- Berufe sind vollwertige Entwicklungswege.
- Neun Elemente: Feuer, Wasser, Schatten, Licht, Wind, Erde, Elektro, Eis, Natur.
- Jede freigeschaltete Elementpaarung ist grundsätzlich möglich; Dreifachkombinationen sind seltenes Endgame.
- Element- und Klassenkombinationen brauchen Grenzen und Counterplay.
- Kampfechos sind moderne 3D-Kampftraditionen; Resonanz geht von +0 bis +30.
- Upgradefehlschläge können auf hohen Stufen Rückschritte verursachen, aber das Objekt darf nicht vollständig zerstört werden; Schutz und Pechschutz sind vorgesehen.
- Handelbarkeit: unaktiviert handelbar, aktiviertes Echo zunächst gebunden, besondere Freigabe ermöglicht Wiederhandelbarkeit; Resonanzstand bleibt beim Verkauf erhalten, persönliche Meisterschaft nicht.
- Ein logisches gemeinsames Welt-/Wirtschaftserlebnis, technisch skalierbar über Prozesse und Regionen.
- Spielerstädte, persönliche Grundstücke und Gemeinschaftsprojekte sind zentrale Systeme.
- Dynamische NPC-Wirtschaft und Spielerunternehmen.
- NPC-Mitarbeiter, Offline-Routinebetrieb und aktive Managementvorteile.
- Spieler können bei anderen Spielerunternehmen arbeiten und Karriere machen.
- Unternehmen können Beteiligungen, Filialen und Tochterunternehmen haben.
- Technologische Entwicklung von Fantasy in spätere Epochen ist eine langfristige Vision, nicht Startumfang.

## 68. Erste Aufgabe – Repository-Audit, nicht blind programmieren

Beginne mit einer vollständigen Bestandsaufnahme des Repositories:

1. Prüfe Branch, Git-Status, Projektstruktur und vorhandene Dokumentation.
2. Identifiziere die bereits vorhandene `mmorpg_character_evolution_v0_1`-Implementierung oder deren importierte Dateien.
3. Lies alle vorhandenen README-, Architektur-, Spezifikations- und Testdateien.
4. Führe vorhandene Tests aus, ohne vorher Code zu verändern.
5. Dokumentiere, was wirklich vorhanden ist, welche Tests bestehen und was fehlt.
6. Erstelle eine kurze Bestandsmatrix: vorhanden / teilweise vorhanden / fehlt / unklar.
7. Prüfe die vorhandene Engine- und Build-Umgebung. Behaupte nicht, dass Unreal installiert oder ein Projekt angelegt ist, bevor du es geprüft hast.
8. Erstelle keine neuen parallelen Implementierungen, wenn ein entsprechendes Modul bereits existiert.

Wenn der Repository-Status lokale Änderungen enthält, überschreibe oder lösche sie nicht. Bewahre sie. Arbeite in kleinen Änderungen und zeige am Ende die geänderten Dateien und Tests.

## 69. Architekturprinzipien

### 69.1 Modularer Monolith vor unnötigen Microservices

Definiere klare Domänengrenzen, aber zerlege das Projekt nicht ohne messbaren Grund in viele verteilte Services. Für den Prototyp sind gut abgegrenzte Module mit sauberen APIs sinnvoll. Spätere Dienste können bei Bedarf ausgelagert werden.

### 69.2 Serverautorität

Der Client darf niemals selbst die Quelle der Wahrheit sein für:

- Erfahrung und Progression.
- Charakterhistorie.
- Elementfreischaltungen.
- Berufserfahrung.
- Wesenform-Kandidaten und Annahme.
- Inventar und Währung.
- Loot und Drops.
- Crafting und Materialien.
- Markttransaktionen.
- Unternehmensanteile.
- Grundstücks- und Gebäudebesitz.
- Mitarbeiterverträge und Zahlungen.
- Resonanz-Upgrades.

Clientseitige Eingaben müssen serverseitig validiert werden.

### 69.3 Event History und abgeleitete Profile

Charakterhistorie ist die Quelle der Wahrheit. Profile, Affinitäten, Meisterschaften und Entwicklungskandidaten sind abgeleitete Zustände.

- Events benötigen eindeutige IDs und Idempotenz.
- Events müssen vertrauenswürdig vom Server erstellt oder validiert werden.
- Profiländerungen müssen nachvollziehbar sein.
- Regeln und Profile benötigen Versionierung.
- Rebuild/Replay aus Historie muss für Audit und Migration möglich sein.
- Keine vollständige Neuberechnung pro Frame.

### 69.4 Datengetriebenes Design

Klassen, Elemente, Berufe, Fähigkeiten, Formen, Rezepte und Freischaltbedingungen möglichst datengetrieben definieren. Nutze geeignete JSON-/YAML-/Data-Asset-Strukturen, Validierung und Schema-Versionierung.

Keine unkontrollierte freie Textgenerierung, die zur Laufzeit beliebige neue Skills, Zahlenwerte oder Formen erfindet. Neue Inhalte müssen authored, validiert, getestet und balanciert sein.

### 69.5 Erweiterbarkeit

Neue Klassen, Berufe, Elemente, Wesenformen und Epochen müssen hinzugefügt werden können, ohne den gesamten Charakterkern neu zu schreiben.

### 69.6 Reproduzierbarkeit

Gleiche gültige Events und gleiche Regelversion müssen reproduzierbare Profile ergeben. Zufallsmechaniken müssen kontrollierte Seeds, Telemetrie und testbare Grenzen besitzen.

## 70. Charakterentwicklung – Implementierungsauftrag

Prüfe und erweitere die vorhandene Character Evolution Engine in dieser Reihenfolge:

1. Vollständiges Datenmodell für Charakter, Klasse, Event-Historie und Profil.
2. Lebensgeschichte, aktuelles Profil und dauerhafte Wesenidentität sauber trennen.
3. Combat-, Profession-, Research-, Exploration-, Commerce-, Teamwork- und Leadership-Tendenzen als eigenständige Profile.
4. Neun Elementar-Affinitäten und Freischaltungen.
5. Freie Paar- und seltene Dreifachkombinationen.
6. Profession XP, Branches, Techniken, Rezepte und Meisterstücke.
7. Fähigkeitsemergenz über designer-authored Templates und nachvollziehbare Voraussetzungen.
8. Wesenform-Kandidaten, Prüfungen und irreversible Annahme.
9. Profilversionierung und Replay.
10. Anti-Farming und Missbrauchserkennung.

Jede Progressionsquelle muss einen klaren Grund haben, warum sie Profilwerte beeinflusst. Wiederholbare triviale Aktionen dürfen keine unbegrenzten Progressionsgewinne erzeugen.

## 71. Berufssystem – Implementierungsauftrag

Baue das Berufssystem als eigenständige Domäne, nicht als bloße Liste von XP-Werten.

Jeder Beruf braucht:

- Definition und erlaubte Aktionen.
- Berufserfahrung und Stufen.
- Spezialisierungszweige.
- Freischaltbedingungen.
- Qualitäts-/Herausforderungsbewertung von Tätigkeiten.
- Rezepte und Herstellungsverfahren.
- Entdeckungs- und Experimentiermöglichkeiten.
- Beziehungen zu Elementen und Wesenprägungen.
- Beziehungen zu Materialökonomie und Unternehmen.

Berufliche Fortschritte müssen aus validierten Tätigkeiten stammen. Ein Rezept darf nicht nur durch wiederholtes Spammen ohne Materialverbrauch und sinnvolle Herausforderung gemeistert werden.

## 72. Fähigkeiten und Wesenformen – Implementierungsauftrag

Fähigkeiten und Formen müssen designer-authored Definitionen besitzen.

Jede Definition soll mindestens enthalten:

- ID und versionierter Schlüssel.
- Klassenkompatibilität.
- Elementanforderungen.
- Wesens-/Trait-Anforderungen.
- Berufsanforderungen, falls relevant.
- Meilenstein-/Questanforderungen.
- Stärken und Tradeoffs.
- Counterplay-/Balancehinweise.
- Visual-/Animation-Referenzen oder Asset-Schlüssel.
- Freischalt- und Annahmeprozess.

Eine Form darf nicht automatisch angenommen werden. Für permanente Hauptformen muss es eine Vorschau/Erklärung der Folgen und einen ausdrücklichen Bestätigungsschritt geben. Die Annahme ist atomar, auditierbar und nicht reversibel.

## 73. Kampfecho und Resonanz – Implementierungsauftrag

Entwirf das Datenmodell so, dass folgende Zustände möglich sind:

- Unaktiviert und handelbar.
- Aktiviert und charaktergebunden.
- Durch zulässigen Freigabegegenstand wieder handelbar.
- Resonanzstufe +0 bis +30.
- Persönliche Meisterschaft getrennt vom Objekt.
- Resonanzgebundene visuelle und spielerische Freischaltungen.

Upgrade-Versuche müssen atomar Materialkosten, Ergebnis, Stufenänderung, Schutz und Pechschutz verarbeiten. Keine Cliententscheidung über Erfolg. Keine Objektzerstörung als Folge eines Fehlschlags. Exakte Wahrscheinlichkeiten bleiben bis zum Balance-Design konfigurierbar und werden nicht erfunden.

Die Handelsfunktion muss gegen Duplikation, Replay, Race Conditions und parallele Verkaufsversuche gesichert sein.

## 74. Elementarsystem – Implementierungsauftrag

Alle neun Elemente müssen datengetrieben registriert werden. Paare sind ungeordnet: Fire+Wind ist dasselbe Paar wie Wind+Fire. Keine doppelten oder selbstkombinierten Elemente, sofern das Design das nicht später ausdrücklich festlegt.

Die Anzahl der möglichen Paare bei neun Elementen ist 36. Dreifachkombinationen sind 84 und müssen hinter einem seltenen Freischalt-Meilenstein stehen.

Elementare Interaktionen müssen nicht nur Schadensboni sein. Sie können Kontrolle, Bewegung, Beschwörung, Verteidigung und Umgebungsinteraktionen verändern. Die konkreten Mechaniken müssen authored, begrenzt und testbar sein.

Klassenabhängige Definitionen sorgen dafür, dass gleiche Elemente bei Krieger, Schamane/Alchemist und Bogenschütze unterschiedliche Fähigkeiten erzeugen können.

## 75. NPCs und Wirtschaft – Architektur vorbereiten, nicht alles sofort bauen

Die langfristige Domäne muss folgende Systeme berücksichtigen:

- NPC-Lebens- und Entwicklungsprofile.
- NPC-Berufe, Fähigkeiten und Spezialisten.
- Personalverträge, Lohn, Loyalität, Zufriedenheit und Kündigung.
- Spielerjobs und Karrierepfade.
- Unternehmensstufen und Gebäudestufen.
- Offline-Routinebetrieb und aktive Managementinteraktion.
- Materialbestände, Produktion, Aufträge und Ausgaben.
- Markttransaktionen und Eigentumsrechte.
- Filialen, Tochterunternehmen und Gesellschafter.

Implementiere nicht alles im ersten Durchlauf. Definiere die Domänenmodelle, Schnittstellen und späteren Migrationspunkte. Vermeide eine Architektur, die diese Systeme später unmöglich macht.

## 76. Welt und Server – Architektur vorbereiten

Die logische Welt ist gemeinsam. Technische Prozesse dürfen Regionen, Instanzen und Simulationseinheiten aufteilen.

- Regionale Simulationen müssen persistente Daten sicher aktualisieren.
- Instanzen dürfen keine separaten Ökonomien oder Charaktere erzeugen.
- Markt und Eigentum müssen weltübergreifend konsistent sein.
- NPCs außerhalb aktiver Bereiche sollen abstrahiert und effizient simuliert werden.
- Städte benötigen Budgets für Gebäude, sichtbare NPCs, Interaktionen und Simulation.

## 77. Unreal Engine – Vorgehen

Unreal Engine ist bevorzugte Kandidatin, aber prüfe die tatsächliche Repository-Struktur und Engine-Version.

Wenn noch kein Unreal-Projekt existiert:

1. Erstelle nicht ungefragt ein vollständiges Großprojekt.
2. Dokumentiere erforderliche Engine-Version und Plugin-Abhängigkeiten.
3. Entwirf Module, Datenstrukturen und Integrationsplan.
4. Schlage eine minimale Vertical-Slice-Struktur vor.
5. Warte nicht auf Rückfragen, wenn eine Dokumentations- oder Referenzimplementierung unabhängig fortgesetzt werden kann.

Mögliche Unreal-Seite:

- CharacterHistoryComponent.
- CharacterEvolutionSubsystem.
- Data Assets für Klassen, Berufe, Elemente, Fähigkeiten und Formen.
- Gameplay Ability System für Fähigkeiten und Effekte, nach einem Proof-of-Concept.
- Serverautoritative Gameplay- und Progressionslogik.
- Profil-Snapshot für replizierte UI-Darstellung.

Nicht ungeprüft alle Berechnungen in den Client verlagern.

## 78. Produktionsregeln für Claude Code

Vor jeder größeren Änderung:

1. Betroffene Dokumente lesen.
2. Bestehende Architektur verstehen.
3. Confirmed versus Proposed versus Open unterscheiden.
4. Änderung in kleinen Schritten planen.
5. Tests zuerst oder zusammen mit Implementierung anlegen.
6. Tests ausführen.
7. Dokumentation und Changelog aktualisieren.
8. Auf Seiteneffekte und Migration achten.

Weitere Regeln:

- Keine Dateien blind überschreiben.
- Keine existierenden Module doppeln.
- Keine unnötigen Frameworks oder Dependencies hinzufügen.
- Keine Geheimnisse, Tokens oder Passwörter committen.
- Keine Performanceversprechen ohne Messung.
- Keine Behauptung, etwas sei implementiert, wenn nur eine TODO oder Spezifikation existiert.
- Keine Inhalte aus dem Masterdokument stillschweigend löschen.
- Keine Politiksysteme ausarbeiten, solange der Nutzer sie zurückgestellt hat.
- Kein Pay-to-win, keine Echtgeld-Upgrade-Lotterie und keine unendlichen passiven Geldquellen als Default.
- Keine frei generierten Skills oder Wesenformen ohne designer-authored Regeln.

## 79. Arbeitsmodus und Ergebnisformat

Arbeite selbstständig, aber kontrolliert. Stelle nicht bei jedem offenen Detail eine Rückfrage. Wenn eine Entscheidung nicht benötigt wird, markiere sie als offen und baue eine flexible, reversible Lösung.

Nach jeder Arbeitseinheit gib eine knappe, überprüfbare Zusammenfassung:

1. Was du im Repository gefunden hast.
2. Was geändert wurde.
3. Welche Dateien neu oder geändert sind.
4. Welche Tests ausgeführt wurden und deren tatsächliches Ergebnis.
5. Was noch nicht implementiert ist.
6. Bekannte Risiken und nächste sinnvolle Arbeitseinheit.

Beginne mit dem Repository-Audit. Danach priorisiere den nächsten kleinsten vertikalen Fortschritt für Character Evolution und dessen Integration. Implementiere nicht gleichzeitig das komplette MMORPG.

## 80. Erste konkrete Deliverables nach dem Audit

Wenn die vorhandene Codebasis dem erwarteten Python-Referenzprototyp entspricht, erstelle als ersten Folgeplan:

- `docs/MASTER_BLUEPRINT.md` oder verlinke diese zentrale Blueprint-Datei.
- Eine aktuelle `docs/IMPLEMENTATION_STATUS.md` mit echter Bestandsaufnahme.
- Eine `docs/DOMAIN_MODEL.md` für Charakter, Historie, Profil, Wesenform, Beruf und Fähigkeit.
- Eine `docs/DECISIONS_AND_OPEN_QUESTIONS.md`, die alle bestätigten und offenen Punkte sauber trennt.
- Tests für jede neu implementierte Regel.
- Eine versionierte Änderung an `CHANGELOG.md`.

Danach implementiere nur eine klar abgegrenzte, getestete Erweiterung. Bevorzuge die saubere Trennung von Lebensgeschichte, aktuellem Profil und dauerhafter Wesenidentität.

**Ende des Masterprompts.**

---

# TEIL XIX – GIT-HUB-ÜBERNAHME

## 81. Empfohlene Verwendung im Repository

Diese Datei soll im Root des GitHub-Repositories liegen, beispielsweise:

```text
/MMORPG_MASTER_BLUEPRINT.md
```

Den bisherigen Prototypen nicht löschen. Falls die Datei `MMORPG_MASTER_BLUEPRINT.md` im Root liegt, soll Claude Code diese vor jeder größeren Änderung lesen.

Empfohlene Projektstruktur nach und nach:

```text
/
├── MMORPG_MASTER_BLUEPRINT.md
├── README.md
├── CLAUDE.md
├── docs/
│   ├── IMPLEMENTATION_STATUS.md
│   ├── DOMAIN_MODEL.md
│   ├── ARCHITECTURE.md
│   ├── DECISIONS_AND_OPEN_QUESTIONS.md
│   └── ROADMAP.md
├── prototypes/
│   └── character_evolution/
└── unreal/
    └── (erst anlegen, wenn Engine-Projekt und Prototyp-Ansatz feststehen)
```

Diese Struktur ist eine Empfehlung. Bestehende Repository-Struktur hat Vorrang, sofern sie sauber funktioniert.

## 82. Wichtig für die weitere Zusammenarbeit

Dieses Dokument ist eine konsolidierte Konzeptfassung vom 03. November 2026. Es enthält bestätigte Entscheidungen, daraus abgeleitete Designrichtungen und klar markierte Vorschläge. Es ist kein fertiger vollständiger GDD-Abschluss und keine technische Produktionsfreigabe.

Neue Entscheidungen müssen versioniert in dieses Dokument oder in passende Unterdokumente übernommen werden. Widersprüche sind zu markieren und nicht stillschweigend aufzulösen.

**Unser Ziel ist eine große, langfristig erweiterbare MMORPG-Welt mit einem außergewöhnlich individuellen Charakterentwicklungssystem, einem tiefen Action-Kampfsystem, echten Spielerwirtschaften und einer Welt, die durch ihre Bewohner sichtbar wächst.**