# ADR-0078: Gildenchat (AP 66–69)

Status: angenommen (Vorschlag, Claude, autorisiert; Platzhalterwerte)

## Entscheidung
- Befehl `guild.say` (nur Gildenmitglieder): Text 1–64 Zeichen (64 = Stringgrenze des Protokolls), ohne Steuerzeichen, Leerraum am Rand entfernt. Höchstens 30 Nachrichten je Figur und Spieltag; die Gilde behält die letzten 50, die Abfrage zeigt die letzten 30 (`mine.chat`).
- Speicherung nur in der Gilde (`chat`, `chat_n`), **erst bei der ersten Nachricht angelegt**: unveränderte Welten behalten ihren Zustand und ihre Hashes. Der Verlauf bleibt nach dem Austritt einer Figur erhalten, Außenstehende sehen ihn nicht.
- Browser: Chatliste und Eingabe im Gildenfenster; Unity-Fenster „Gilde“ kennt den Befehl (generische Anzeige).
- Kein Echtzeit-Push (Abfrage beim Aktualisieren), keine Moderation außer Längen-/Tageslimit.

## Offen
- Echtzeit-Zustellung (Benachrichtigung), Stummschalten/Moderation durch Offiziere, Weltchat, Flüstern.

## Ergänzung AP 82–84: Moderation
- `guild.mute {target, on?}`: Offiziere schalten Mitglieder stumm, der Leiter auch Offiziere; nie den Leiter oder sich selbst. Stummgeschaltete können nicht schreiben, aber lesen. Speicherung `muted` in der Gilde nur bei Bedarf; Austritt/Rauswurf hebt die Sperre auf (`check()` prüft, dass nur Mitglieder stumm sind). Browser: Knopf „Stummschalten“ in der Mitgliederliste, Anzeige „stumm“.
