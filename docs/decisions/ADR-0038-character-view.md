# ADR-0038: Lesende Charaktersicht und Klassenwahl über das Gateway

**Status:** angenommen (Anzeige und bereits vorhandene Regel; keine neue Regelwirkung)

## Kontext
Die Character Evolution Engine (Klasse, Elemente, Berufe, Wesen, Kampfentwicklung, Wissen) war nur als Bibliothek und in Tests sichtbar. Im Spiel konnte der Spieler weder seine Entwicklung sehen noch eine Grundklasse wählen (`identity.class_chosen` war nicht erreichbar). Das Master-Blueprint (§9, §12) verlangt eine nachvollziehbare Charakterentwicklung.

## Entscheidung
- `query.character(char)` (lesend): reine Ableitung aus dem Zustand – `identity`, `classes`, `elements` (Affinität, gebunden), `professions`, `essence` (Form, bestandene Prüfungen, Profil, erreichbare Formen, Bewertungen), `combat` (Richtungen, Fähigkeiten mit offenen Voraussetzungen, Plätze, Ausrüstung), `knowledge` (Entdeckungen, Rezepte, Techniken, Herstellungsprofil), `economy`, `appearance`. Teile, die eine ältere Regelversion nicht kennt, erscheinen leer statt als Fehler.
- `character.choose_class(char, base_class)` (schreibend): zeichnet `identity.class_chosen` auf; die vorhandene Regel macht die Wahl **dauerhaft** (zweite Wahl und unbekannte Klasse werden abgelehnt).
- Der Browserclient zeigt ein Fenster „Charakter“ (standardmäßig offen) mit Klassenwahl (Bestätigungsfrage), Elementen, Berufen, Kampfentwicklung, Fähigkeiten, Wesenspfad und Wissen. Namen und Texte sind Platzhalter.

## Folgen
- Keine neue Regelversion, keine Änderung der Golden Vectors: nur vorhandene Ereignisse und Abfragen werden erreichbar.
- Was noch nicht sichtbar wächst: Gegner-Kämpfe füllen die Kampfentwicklung; Berufe wachsen durch Herstellen; Elemente und Wesen hängen an Regeln, die der Spielserver heute noch nicht aus dem Spielgeschehen speist (z. B. Sammeln erzeugt keine Berufserfahrung). Das ist eine eigene Etappe mit neuer Spielregelversion.
- Offen: Vorschau/Bestätigung der Wesensannahme im Client (Blueprint §72).
