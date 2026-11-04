# ADR-0040: Drei Schichten der Charakteridentität (Lebensgeschichte, Profil, Wesenidentität)

**Status:** angenommen (reine Ableitung, keine Regeländerung)

## Kontext
Blueprint §12 verlangt drei getrennte Schichten: dauerhafte Lebensgeschichte, aktuelles Profil, Wesenidentität; wer nach Hunderten Stunden einen anderen Stil lernt, soll seine Geschichte nicht verlieren. Der Code hatte Ereignislog und Zustandsteile, aber keine ausdrückliche Dreiteilung (Blueprint §70.1–2).

## Entscheidung
- Neues Modul `mmo_cee/layers.py`: `life_story` (Meilensteine + Zähler aus dem Ereignislog), `current_profile` (Rohwerte je Bereich aus dem Zustand), `essence_identity` (Klasse, Form, geprägte Elemente, Entscheidungen). `CharacterService.layers(char)`; `query.character` liefert sie unter `layers`.
- **Keine neuen Ereignisse, keine neue Regelversion, keine Änderung an Golden Vectors.** Die Schichten sind eine Lesesicht; sie funktionieren für alle Regelversionen (fehlende Teile bleiben leer).
- Meilensteine werden aus vorhandenen Ereignissen abgeleitet (Stufen aus XP, „erster Sieg je Gegnerart“, „erste Herstellung je Rezept“); die Lebensgeschichte ist nur anhängend (Test: Präfix-Eigenschaft).
- Im Browserclient zeigt das Charakter-Fenster die letzten Meilensteine und Zähler.
- Dokumentation: `docs/DOMAIN_MODEL.md`.

## Folgen
- Neue Meilensteinarten (Erkundung, soziale Beiträge, Weltereignisse) brauchen zuerst Ereignisse aus dem Spielgeschehen (AP 3) und ggf. eine neue Regelversion.
- Das Profil enthält bewusst keine Gewichtung der Bereiche; diese ist Balancing und offen.
