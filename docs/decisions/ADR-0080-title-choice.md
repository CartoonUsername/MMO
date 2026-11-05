# ADR-0080: Anzeigetitel wählen (AP 73–75)

Status: angenommen (Vorschlag, Claude, autorisiert)

## Entscheidung
- Befehl `title.choose {title?}`: wählt einen **selbst verdienten** Chronik-Titel als Anzeigetitel; ohne `title` wird er entfernt. Fremde, unbekannte oder falsch typisierte Titel werden abgelehnt. `query.prestige` liefert `chosen` und `display`.
- Speicherung in der Chronik (`chosen`), nur wenn jemand einen Titel gewählt hat (unveränderte Welten behalten ihren Zustand). Rein kosmetisch: keine Werte, keine Vorteile.
- Browser: Titelwahl im Chronikfenster; Unity-Fenster „Chronik“ kennt den Befehl.

## Offen
- Seit AP 76 zeigt die Zustandsmeldung den Titel bei Mitspielern. Offen: mehrere Anzeigeplätze, Darstellung in Unity.
