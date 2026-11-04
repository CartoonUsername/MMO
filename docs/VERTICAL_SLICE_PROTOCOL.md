# Protokoll der Spielschicht (Vertical Slice)

Transport: TCP, UTF-8, **eine JSON-Nachricht je Zeile**, höchstens 4096 Bytes. Entwicklungsstufe: keine Verschlüsselung, Anmeldung nur per Kontoname (nur lokal binden!). Alle Zahlen sind Platzhalter.

## Anmeldung
Client → `{"cmd":"hello","account":"anna"}`; Server → `{"ev":"welcome","session":"sess-…","characters":["anna"],"tick":N}`. Ungültig: `{"ev":"error","code":"bad_hello"}` und Verbindungsende. Ein Konto kann nur einmal gleichzeitig verbunden sein; neue Konten erhalten eine Figur gleichen Namens (Mensch, 200 Münzen).

## Befehle (Client → Server)
Hülle wie `docs/PROTOCOL.md`: `{"v":1,"id":"<1-64 Zeichen>","cmd":"…","args":{"char":"anna",…}}`; Antwort `{"v":1,"id":…,"ok":true,"result":…}` oder `{"ok":false,"error":{"code","message"}}`. `args.char` muss zur Sitzung gehören (`forbidden`). Alle Befehle ohne Präfix `game.` laufen unverändert durch das Gateway (Handel, Markt, Gruppen, Herstellen, Abfragen).

| Befehl | Argumente | Wirkung |
|---|---|---|
| `game.join` | – | tritt der Welt am Startpunkt bei; Ergebnis: Zustand |
| `game.move` | `dx`, `dy` ∈ {−1,0,1} | setzt die Bewegungsrichtung (Tempo und Grenzen bestimmt der Server; im Kampf wirkungslos) |
| `game.gather` | `node` | sammelt am Sammelpunkt (Reichweite, Abklingzeit); Beute kommt ins Inventar |
| `game.fight` | `input` | Kampfbefehl; der Server vergibt den Tick; unbekannt oder nicht im Kampf: `rejected` |
| `game.state` | – | aktueller Zustand in Sichtweite |

Zu viele Befehle: `rate_limited` (Budget füllt sich ein Befehl je Tick).

## Ereignisse (Server → Client, ohne `id`)
- `state` (alle 2 Ticks): `{tick, day, you:{char,pos,fight}, players:[{char,pos,fight}], enemies:[{id,type,pos,alive,fight}], nodes:[{id,item,pos,ready}], zone}`; Positionen in Zentimetern.
- `fight_start`: `{fight, opponents:[Typ], party:[Figur], you:<Index>}`.
- `fight` (alle 2 Ticks): `{tick, opponents:[{type,hp,alive}], players:[{hp,max_hp,stamina,state,cooldowns,busy,focus}], stagger:[bool]}` – keine Bedrohung/Zielwahl.
- `fight_left`: `{fight, reason: defeat|fled}` – du bist raus.
- `fight_end`: `{fight, outcome, ticks, actions, report, loot}` – `report` ist der CEE-Bericht (oder `null`, wenn nichts bewertbar war), `loot` die erhaltene Beute.
- `notify`: Benachrichtigung aus dem Postfach (ADR-0024), z. B. Angebot erhalten.
