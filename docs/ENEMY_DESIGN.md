# Gegnerdesign – Analyse und Vorschlag

**Status:** Vorschlag zur gemeinsamen Ausarbeitung; die Entscheidungen des Produktverantwortlichen stehen in Abschnitt 0. Nichts hier ist beschlossen; alle Zahlen, Namen und Fähigkeiten sind **Platzhalter**. Bestätigte Entscheidungen aus der Projektübergabe sind als solche gekennzeichnet.

## 0. Entscheidungen des Produktverantwortlichen (bestätigt)
1. **Erste Familien:** Wolfsrudel mit Alpha, Höhlenbär, Irrlicht-Heiler, Moorhexe – **und viele weitere Gegner mit „zufälligen" Fähigkeiten, ähnlich der Charaktererstellung.**
2. **Zufall nur reproduzierbar:** Fähigkeiten werden aus einem Baukasten **je Spawn-Punkt neu, aber pro Tag fest** bestimmt (aus Spawn-Punkt, Tag und Gegnerart, ganzzahlig und ohne unkontrollierten Zufall, nach dem Vorbild der stabilen Variation in der Visual Evolution). Im Kampf selbst gibt es keinen Zufall.
3. **Verhalten:** feste Muster mit sichtbarer Ankündigung (Vorwarnzeit) für alle Gegner.
4. **Entwicklungspunkte:** nur die bisherigen Aktionen (`perfect_dodge`, `parry`, `stun_applied`, …) mit ihren Raten- und Tageslimits; keine neuen Punktequellen.
5. **„Gegner mit Historie":** erst nach dem Basisspiel; die Architektur soll es später erlauben.
6. **Schwierigkeit:** normale Mobs solo schaffbar, Elite (Alpha) zu zweit, Boss ab 3–4 Spielern.

**Folgerungen:** Der Fähigkeiten-Baukasten (Abschnitt 3) wird zur Grundlage; Familien (Abschnitt 4) sind nur *Vorlagen* (Basiswerte, Element, Rolle), die der Baukasten je Spawn-Punkt und Tag mit 1–3 Zusatzfähigkeiten ausstattet. Die Zufallsauswahl braucht gewichtete, rollenverträgliche Regeln (keine unlösbaren Kombinationen, Bosse nicht zufällig). Ein Tageswechsel ändert die Fähigkeiten nur für Gegner, die gerade nicht kämpfen.

## 1. Was das Spiel ist (Analyse)

**Bestätigt:**
- Third-Person-Action-Kampf mit Ausweichen, Blocken, Parieren; Gruppenkampf mit Unterstützern; Free-to-Play ohne Pay-to-win.
- Charaktere entwickeln sich **nur aus ihrer Spielhistorie** (Combat Development mit sechs Dimensionen: Kraft, Präzision, Mobilität, Kontrolle, Verteidigung, Unterstützung; neun Elemente frei kombinierbar; Wesensformen; Berufe).
- **Spieler und NPCs laufen durch dieselbe Pipeline.** Kampf ist deterministisch (kein unkontrollierter Zufall), serverautoritativ, nachvollziehbar.
- Kein stumpfes Wiederholen: Diminishing Returns, Berichtsvalidierung, Limits. Wirtschaft und Handwerk sind vollwertige Systeme.

**Folgerungen für Gegner:**
1. **Gegner stellen Fragen an die Entwicklungsrichtungen.** Weil die CEE aus dem *Verhalten* entwickelt, sollte jeder Gegner Verhalten verlangen, das eine bestimmte Dimension belohnt (Ausweichen → Mobilität, Parieren/Blocken → Verteidigung, Unterbrechen/Betäuben → Kontrolle, Heilen/Schützen → Unterstützung, Schwachstellen treffen → Präzision, Durchbruchschaden → Kraft). So haben alle Pfade ihren Moment (Wesen und Richtungen sollen konkurrenzfähig sein).
2. **Kein Zufall, volle Lesbarkeit.** „Krass" heißt hier: Muster, Ankündigungen, Phasen, Zusammenspiel – nicht Würfelglück. Jede gefährliche Aktion hat eine Vorwarnzeit (Ticks), die der Server vorgibt und der Client anzeigt.
3. **Keine festen Elementpaare** (bestätigt: freie Kombinationen). Elemente geben Gegnern Charakter (Fähigkeiten, Aura, Beute), aber keine Schere-Stein-Papier-Zwänge.
4. **Gruppen zählen:** Leben wächst mit der Gruppengröße, Bedrohung steuert das Ziel – Gegner sollten Rollen *erzwingen* (Tank hält, Unterstützer heilt, Kontrolle unterbricht), ohne Solo unmöglich zu machen.
5. **Gegner sind Teil der Wirtschaft:** Beute speist Berufe (Materialien, Rezeptteile, Entdeckungsbeweise), nicht nur Münzen; gleiche Gegner wiederholt zu töten bringt weniger (Wiederholungsabnahme ist schon da).
6. **NPC = Figur:** Besondere Gegner können echte Figuren mit eigener Historie sein, die sich weiterentwickeln (siehe 5).

## 2. Heutiger Stand der Gegner (technisch)
Gegner haben Leben, Stufe, Angriffstakt, Vorwarnzeit, Schaden, Taumeln (`sim_rules`), bis zu drei gleichzeitig (ADR-0026), Bedrohung entscheidet das Ziel, Bewegung/Wegfindung/Leine stehen (ADR-0031). Sie haben **keine eigenen Fähigkeiten, Phasen oder Zustände auf Spielern.**

## 3. Neue Bausteine (Vorschlag, alle deterministisch)
| Baustein | Beschreibung | Antwort der Spieler → belohnte Dimension |
|---|---|---|
| **Angriffsmuster** | Folge von Aktionen mit Vorwarnzeit, die sich wiederholt oder nach Lebensanteil wechselt | – |
| **Wuchtschlag** (lange Vorwarnung) | hoher Schaden auf das Ziel | Ausweichen (Mobilität), Parieren (Verteidigung + Taumeln) |
| **Flächenschlag** | trifft alle Spieler, Zeitfenster zum Ausweichen | Mobilität; Schild (Unterstützung) |
| **Zustand auf Spieler** (Betäubung, Verlangsamung, Brand, Schwächung) | wirkt Ticks, wird durch Heilen/Reinigen/Warten beendet | Unterstützung, Verteidigung |
| **Zauber mit Unterbrechung** | Wirkzeit; wird er mit Betäubung/schwerem Treffer gestört, entfällt er und der Gegner taumelt | Kontrolle, Kraft |
| **Gegnerschild / Rüstung** | absorbiert Schaden, bricht durch Parade oder präzise Treffer | Präzision, Verteidigung |
| **Heilen/Stärken von Verbündeten** | Heiler stellt Leben her, solange er lebt | Fokus, Kontrolle |
| **Beschwörung / Verstärkung** | ruft Schwarmtiere in Wellen (Obergrenze, Vorwarnung) | Flächenangriff, Gruppenarbeit |
| **Phasenwechsel** | bei Lebensschwellen: neues Muster, Wut (schneller), Schildphase, Wellenphase | Anpassung |
| **Aggro-Regeln** | feste Bedrohungsfaktoren; Spott/Heilbedrohung existieren | Verteidigung, Unterstützung |

## 4. Gegnerfamilien (Vorschlag, passend zum Vertical Slice)
| Familie | Rolle | Kernmuster (Platzhalter) |
|---|---|---|
| **Wolfsrudel** (Wolf, Alpha) | Schwarm/Jäger | Wölfe greifen schnell an; der Alpha heult → alle Wölfe +Tempo für 30 Ticks, ein Zauber kann unterbrochen werden |
| **Höhlenbär** | Brecher | langsam, Wuchtschlag mit 12 Ticks Vorwarnung (Parade bringt viel Taumeln), Brüllen = Schwächung |
| **Moorhexe** | Caster/Zustände | Brand-Zauber (Unterbrechen!), verlangsamt Ziele, schwebt auf Abstand |
| **Steinwächter** | Wächter | Gesteinsschild (bricht nur durch präzise Treffer/Parade), Bodenschlag auf alle |
| **Irrlicht-Heiler** | Unterstützer | heilt Verbündete 40 % je 60 Ticks, schwach; bei Tod bricht der Rest in Wut aus |
| **Schattenjäger** | Kontrolleur | Betäubungsstoß auf das Ziel mit kurzer Vorwarnung (Ausweichen!), flieht bei 25 % Leben |
| **Totem-Beschwörer** | Beschwörer | ruft alle 150 Ticks zwei Schwarmtiere (max. 4), verwundbar nur zwischen den Wellen |
| **Mini-Boss „Alpha des Nordtals"** | Elite | Phase 1 Rudelführer (Heulen), Phase 2 bei 60 % Wut, Phase 3 bei 25 % ruft Verstärkung |
| **Boss „Steinherz-Koloss"** | Boss | drei Phasen mit Schildphase, Flächenschlag, Wellen; erzwingt Rollen in der Gruppe |

Jede Familie bekommt ein **Element** als Charakter (z. B. Moorhexe Natur/Schatten, Steinwächter Erde, Irrlicht Licht), das Fähigkeiten, Aura und Beute färbt – ohne feste Schwächen.

## 5. Was „krass" zusätzlich sein kann (Vision, nicht für den ersten Schritt)
- **Gegner mit Historie:** Benannte Elite-NPCs sind echte Figuren (gleiche Pipeline), die sich durch ihre Begegnungen weiterentwickeln (z. B. ein Alpha, der Spielerlager überlebt, bekommt andere Muster); alles aus protokollierter Historie, deterministisch, versioniert.
- **Weltereignisse:** Rudelwanderungen, Belagerungen als Preis-/Beuteschock (Schock-Auslöser existieren in der Preisdynamik).
- **Gegner reagieren auf Spielerbau:** Gruppen mit viel Unterstützung ziehen Kontrolleure an (nur über feste, sichtbare Regeln, nie versteckt).

## 6. Umsetzungsplan (Vorschlag)
1. **Regeln `sim_rules_v6`:** Abschnitt `enemy_abilities` (Kosten entfallen; Vorwarnung, Dauer, Ziel, Wirkung, Unterbrechbarkeit) und je Gegnerart `pattern` und `phases`; Prüfung beim Laden; neue Regelversion, alte Vektoren bleiben byteidentisch.
2. **Simulation (`mmo_sim.pack`):** Gegnerfähigkeiten, Zustände auf Spielern, Gegnerschild, Heilen/Beschwören, Phasenwechsel; weiterhin deterministisch und mit Eingabeprotokoll nachspielbar.
3. **Berichte/CEE:** Aktionen wie `perfect_dodge`, `parry`, `stun_applied` (Unterbrechen) laufen schon in die Entwicklung; neue Nachweise nur nach Entscheidung (siehe Fragen).
4. **Spielserver und Client:** Ereignis `telegraph` (Fähigkeit, Ziel, Ticks bis zur Wirkung) für die Anzeige; Beute je Familie.
5. **Golden Vectors, Mutationstests, Doku (ADR) je Schritt.**

## 7. Bisher offene Fragen (jetzt in Abschnitt 0 beantwortet)
1. Welche Familien/Rollen zuerst (Vorschlag: Wolfsrudel mit Alpha, Höhlenbär, Irrlicht-Heiler, Moorhexe als erste Welle)?
2. Feste Muster mit Ankündigung für alle, oder Bosse mit Prioritätsregeln?
3. Sollen Unterbrechen, perfektes Ausweichen und Parieren **eigene Entwicklungspunkte** bringen (wirkt auf die CEE und braucht Anti-Farming)?
4. Soll „Gegner mit Historie" (Abschnitt 5) früh als Ziel gesetzt werden oder erst nach dem spielbaren Basisspiel?
5. Schwierigkeit: Solo spielbar bis wohin, ab wann Gruppenpflicht?
