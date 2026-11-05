# ADR-0059: Client-Fenster für AP 16–19 (AP 20)

Status: angenommen

## Entscheidung
Der Browser-Testclient (`mmo_game/web/index.html`) zeigt die Serverfunktionen aus AP 16–19 an; alle Entscheidungen bleiben beim Server:
- **Elemente (AP 16):** Im Figurenfenster erscheint „Kampfzauber" (geprägtes Element → Zauber, Wechselzeit); die Skill-Leiste kennt Namen, Symbole und Effektfarben der acht neuen Elementzauber (`cast_*`), weitere Hotkeys (`r f g z x c v`, keine Kollision mit Bewegung, Sammeln, Ausweichen). Nach einer Prägung wird die Leiste neu geladen.
- **Echos (AP 17):** Das Echofenster zeigt „Wirkung im Kampf" (zusammengefasste Prozentwerte) und die freigeschalteten Fähigkeiten aus `query.echoes` (`combat`).
- **Gilde/Raid (AP 18/19):** Gildenfenster mit Forschungsliste (Kosten, Dauer, Status, „Erforschen" für Leitung/Offiziere über `guild.research`); der Dungeon-Knopf heißt bei Raids „Gildenraid betreten"; Ereignis `guild_chest` und Chronikart `raid_cleared` werden angezeigt.
- **Unity:** Das Gildenfenster bietet `guild.research` an (Fenster sind datengetrieben aus dem Katalog; `query.guild` liefert `research` mit).

## Prüfung und Grenzen
- Statische Tests (`tests/test_web_ap20.py`): gültiges JavaScript (Node), Beschriftung aller Elementzauber, Verdrahtung, Hotkey-Kollisionen. **Nicht** im echten Browser gespielt (Playwright fehlt auf dem VPS; der Rauchtest `tests/browser/smoke.js` bleibt übersprungen) und **nicht** in Unity.
- Offen: Echo-Fenster zeigt keine Vorschau „Wirkung nach Aufwertung"; Raid-Teilnehmerliste/Gruppenanzeige über 4 im Kampf-Overlay ungeprüft; Unity-Hotkeys nur 1–9.
