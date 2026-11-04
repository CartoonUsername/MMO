# Protokoll der Spielschicht (Vertical Slice)

Transport: TCP, UTF-8, **eine JSON-Nachricht je Zeile**, höchstens 4096 Bytes. Verschlüsselung: optional TLS (Server mit `--cert`/`--key`), Pflicht außerhalb von 127.0.0.1. Alle Zahlen sind Platzhalter.

## Anmeldung
Erste Zeile des Clients (Server mit Konten, Standard):
- Neues Konto: `{"cmd":"register","account":"anna","password":"…"}`
- Anmeldung: `{"cmd":"hello","account":"anna","password":"…"}`
- Wiederanmeldung nach Verbindungsabbruch: `{"cmd":"hello","account":"anna","token":"…"}`

Antwort: `{"ev":"welcome","session":"sess-…","characters":["anna"],"tick":N,"token":"…"}`. Das `token` ist kurz gültig (Platzhalter: 1 Stunde), wird bei jeder Anmeldung erneuert und gilt nur einmal; es ersetzt das Passwort nur zum Wiederverbinden. Fehler: `{"ev":"error","code":…,"message":…}` und Verbindungsende. Codes: `bad_hello`, `bad_request` (Kontoname), `weak_password` (8–128 Zeichen), `account_exists`, `auth_failed` (gleiche Meldung für falsches Passwort, unbekanntes Konto und falsches Token), `locked` (zu viele Fehlversuche je Konto bzw. Adresse), `rate_limited` (zu viele Registrierungen von einer Adresse), `server_full` (zu viele Verbindungen insgesamt oder je Adresse).

Eine neue Anmeldung desselben Kontos verdrängt die alte Verbindung. Neue Konten erhalten eine Figur gleichen Namens (Mensch, 200 Münzen). Nur zum Testen kann der Server mit `--insecure-dev` ohne Konten laufen (`{"cmd":"hello","account":"anna"}`); das ist nur auf 127.0.0.1 erlaubt. Nicht-lokale Adressen verlangen Konten **und** TLS.

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
