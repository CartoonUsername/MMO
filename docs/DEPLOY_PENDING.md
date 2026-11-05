# Bereitstellung ausstehend (Stand nach AP 80)

Auf dem VPS läuft Commit `ee249f9` (AP 16–21, 2026-11-05). **Nicht bereitgestellt:** AP 22–80 (Kombinationszauber, Marktplatz-Rabatt, Hafen, Grundstückshandel, Berufszweige, Meisterstück-Chronik u. a.; Einzelheiten in `CHANGELOG.md`). Bereitstellung nur nach ausdrücklicher Freigabe des Projektinhabers.

## Neue Regelversionen
`sim_rules_v11–v15`, `game_rules_v14–v19`, `settlement_rules_v2` (Marktrabatt, Hafen, Grundstückshandel), `community_rules_v3` (Chronikart Meisterstück), `research_rules_v2` (3 neue Techniken), `equipment_rules_v2` (Setboni), `rules_v10` (CEE). Alte Versionen und Golden Vectors bleiben.

**Wichtig:** `settlement_rules_*` und `community_rules_*` sind nicht an den Spielstand gebunden (anders als die CEE-Regeln); sie gelten sofort nach dem Neustart mit dem neuen Code. Neue Befehle: `guild.say`, `title.choose`, `profession.specialize`, `plot.sell` (auch ohne Käufer = offenes Angebot), `plot.cancel_sale`, `plot.accept_sale`.

## Ablauf (Vorschlag, bisher nicht auf dem Server ausgeführt)
1. Auf dem Server als root: `bash scripts/backup_mmo.sh` (geprüfte Sicherung; Hinweis zur externen Kopie beachten).
2. Code bereitstellen wie bisher: `git pull` im Klon, dann `bash deploy/setup.sh` (legt `/opt/mmo/python.prev` als Rückweg an).
3. **Der Spielstand bleibt zunächst auf CEE v9.** Das Spiel läuft, nur die Zweigwahl (`profession.specialize`) ist abgelehnt.
4. Zweigwahl aktivieren (bewusst, getrennt): `systemctl stop mmo`, dann `cd /opt/mmo/python && python3 -m mmo_game.upgrade --data /var/lib/mmo --to rules_v10.json`, dann `chown -R mmo:mmo /var/lib/mmo` und `systemctl start mmo`.
5. Rückweg: Dienst stoppen, `python.prev` zurück, Sicherung zurückspielen (`scripts/restore_mmo.sh`).

## Ungeprüft
- Browser-Anzeigen (Kombinationszauber, Zweigwahl, Marktrabatt) wurden nur statisch geprüft (Node-Syntax, Python-Tests), nicht im echten Browser.
- Unity-Client: Namen der Kombinationszauber ohne Unity-Editor kompiliert/geprüft; keine Anzeige der Zweigwahl.
- Alte Spielstände: `tests/test_old_state_compat.py` (AP 72) lädt einen unter den alten Regeldateien gespeicherten Stand unter den neuen Standards und prüft Konsistenz, Weiterspielen und erneutes Speichern; auf dem echten Spielstand nicht erprobt.
- Der Upgrade-Ablauf ist nur im Test mit einem Wegwerf-Spielstand gelaufen.
