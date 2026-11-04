#!/usr/bin/env bash
# Wiederherstellung aus einer Sicherung (siehe docs/BACKUP_AND_RESTORE.md).
#   restore_mmo.sh list                    vorhandene Sicherungen
#   restore_mmo.sh test <archiv> [zielverz] Wiederherstellung in ein isoliertes Testverzeichnis (berührt Live-Daten nie)
#   restore_mmo.sh live <archiv>           echte Rückspielung nach $MMO_DATA; Dienst muss gestoppt sein; verlangt Bestätigungssatz
set -euo pipefail
DATA="${MMO_DATA:-/var/lib/mmo}"
OUT="${MMO_BACKUP_DIR:-/var/backups/mmo}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${MMO_PY:-}"
if [ -z "$PY" ]; then
  for c in /opt/mmo/python "$HERE/../reference/python"; do [ -d "$c/mmo_game" ] && PY="$c" && break; done
fi
[ -n "$PY" ] || { echo "FEHLER: mmo_game nicht gefunden (MMO_PY setzen)"; exit 1; }
cd "$PY"
cmd="${1:-}"; shift || true
case "$cmd" in
  list) python3 -m mmo_game.backup list --out "$OUT" ;;
  test)
    arc="${1:?Archiv angeben}"; target="${2:-$(mktemp -d /tmp/mmo-restore-test.XXXXXX)/data}"
    python3 -m mmo_game.backup verify "$arc" --full
    python3 -m mmo_game.backup restore "$arc" --target "$target"
    echo "Testwiederherstellung liegt in: $target  (Live-Daten unverändert; zum Aufräumen: rm -r $(dirname "$target"))" ;;
  live)
    arc="${1:?Archiv angeben}"
    if command -v systemctl >/dev/null && systemctl is-active --quiet mmo; then
      echo "ABBRUCH: Dienst mmo läuft. Erst stoppen:  systemctl stop mmo   (Spieler werden getrennt)"; exit 2
    fi
    python3 -m mmo_game.backup verify "$arc" --full
    phrase="$(python3 -m mmo_game.backup phrase "$arc")"
    echo "Die vorhandenen Daten in $DATA werden NICHT gelöscht, sondern als ${DATA}.before-restore-<Zeit> beiseitegestellt."
    read -r -p "Zur Bestätigung exakt eintippen: $phrase  > " answer
    [ "$answer" = "$phrase" ] || { echo "ABBRUCH: Bestätigung stimmt nicht."; exit 3; }
    python3 -m mmo_game.backup restore "$arc" --target "$DATA" --confirm "$answer"
    id mmo >/dev/null 2>&1 && chown -R mmo:mmo "$DATA"
    python3 -m mmo_game.backup verify "$arc" --full
    echo "Fertig. Dienst starten:  systemctl start mmo   und danach https-Seite prüfen." ;;
  *) sed -n '2,6p' "$0"; exit 1 ;;
esac
