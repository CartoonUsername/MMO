# Domänenmodell: Charakter, Historie, Profil, Wesenform, Beruf, Fähigkeit

Stand: AP 2 (ADR-0040). Alle Zahlen und Namen in den Regeldateien sind Platzhalter. Dieses Dokument beschreibt, was der Code **heute** tut (Blueprint §12, §70).

## Grundprinzip
Die einzige Wahrheit ist das **Ereignislog** je Figur (`mmo_cee/history.py`): anhängend, hash-verkettet, mit Regelversion je Ereignis. Der Zustand (`CharacterState`, Teile je Engine) entsteht ausschließlich durch Wiederholung (`rebuild`). Alles andere ist eine **Ableitung** und schreibt nichts.

## Drei Schichten (`mmo_cee/layers.py`, `CharacterService.layers`, `query.character → layers`)
| Schicht | Inhalt | Veränderlich? | Quelle |
|---|---|---|---|
| **Lebensgeschichte** (`life_story`) | Meilensteine: Geburt, Grundklasse, Stufen, Elementprägungen, bestandene Prüfungen, Wesensentscheidungen/-annahme, Entdeckungen, Firmengründung/-schließung, Laufbahn, erster Sieg je Gegnerart, erste Herstellung je Rezept; Zähler (Kämpfe, Herstellungen, Handel, Beweise, Arbeitseinheiten); Ereigniszahl und Kopfhash | **nur anhängend**; frühere Einträge ändern sich nie | Ereignislog |
| **Aktuelles Profil** (`current_profile`) | Stufe, Elementaffinitäten (führende drei), Berufe mit Erfahrung und Meisterstufe, Kampfpunkte und erreichte Richtungsstufen, Herstellungsprofil, Wirtschaftsprofil, Zahl der Entdeckungen – Rohwerte, **keine** Gewichtung | ja, verschiebt sich mit der Spielweise; verliert nie die Lebensgeschichte | Zustand |
| **Wesenidentität** (`essence_identity`) | Grundklasse, Wesensform mit Vor-/Nachteilen, Annahme-Ereignis (`adopted_at_seq`), Entscheidungen, bestandene Prüfungen, geprägte Elemente, `permanent` | Form und Annahme **dauerhaft** (Engine lehnt eine zweite Annahme ab) | Zustand |

Garantien (Tests in `tests/test_layers.py`): Lebensgeschichte wächst nur als Präfix; Profilwechsel löscht frühere Wege nicht; Identität bleibt nach der Annahme beim Weiterspielen unverändert; Ableitung ist rein und deterministisch (gleiche Ereignisse → gleiche Schichten); Kopfhash verweist auf die Hash-Kette; alle Regelversionen v1–v9 liefern Schichten; keine realen Personendaten.

## Engines und ihre Zustandsteile
| Teil | Engine | Wichtigste Ereignisse | Dauerhaft? |
|---|---|---|---|
| `identity` | Identity | `identity.created`, `identity.class_chosen`, `identity.xp_gained` | Klasse einmalig, XP wachsen |
| `element` | Element | `element.exposure`, `element.attuned` (max. 2 regulär + 1 Endgame ab Stufe 40) | Prägung dauerhaft |
| `profession` | Profession | `profession.work` | wächst |
| `essence` | Essence | `essence.trial_passed`, `essence.decision_made`, `essence.adopted` | Annahme dauerhaft |
| `combat` | Combat Development | `combat.encounter_resolved`, `combat.loadout_set` | Punkte wachsen, Ausrüstung wechselbar |
| `discovery` | Discovery | `discovery.evidence_gathered`, `discovery.made`, `discovery.learned` | dauerhaft |
| `crafting` | Crafting | `crafting.crafted` | wächst |
| `economy` | Economic Profile | `economy.trade_completed`, `economy.career_changed`, `economy.company_founded/closed` | wächst |

Spiel-/Weltzustand (Inventar, Firmen, Markt, Gruppen) liegt **nicht** in der Figur, sondern in `mmo_world` (siehe `ARCHITECTURE.md`).

## Beruf und Fähigkeit (Ist-Stand)
- **Beruf:** Erfahrung je Beruf (`profession.xp`), Meisterstufe aus Schwellen; Rezepte, Techniken und Entdeckungen setzen Meisterstufen voraus. Spezialisierungszweige und Meisterstücke: **fehlen** (AP 5).
- **Fähigkeit:** Katalog in den CEE-Regeln (`combat.abilities`: Art, Voraussetzung, Simulationsbefehl); Freischaltung nur aus Wachstumsgrößen (Richtungsstufe, Element, Stufe, Wesensform), Ausrüstung über `combat.set_loadout` (Plätze nach Stufe). Spielregeln v2 geben Grundklassen ein Kit nur für den Kampf (ADR-0039). Designer-authored Definitionen mit Counterplay-Hinweisen und Asset-Schlüsseln: **fehlen** (AP 6).

## Offen (nicht eigenmächtig entschieden)
Anzahl dauerhafter Wesensformen (Blueprint Frage 4/5) · Berufswechsel (Frage 10) · Gewichtung von Bereichen im Profil (Balancing) · Meilenstein-Katalog erweitern (z. B. Weltereignisse, soziale Beiträge – benötigt Ereignisse aus AP 3).
