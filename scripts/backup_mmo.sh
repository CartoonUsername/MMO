#!/usr/bin/env bash
# Datierte, geprüfte Sicherung des Spielstands (siehe docs/BACKUP_AND_RESTORE.md). Liest die Live-Daten nur, verändert sie nie.
set -euo pipefail
DATA="${MMO_DATA:-/var/lib/mmo}"
OUT="${MMO_BACKUP_DIR:-/var/backups/mmo}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${MMO_PY:-}"
if [ -z "$PY" ]; then
  for c in /opt/mmo/python "$HERE/../reference/python"; do [ -d "$c/mmo_game" ] && PY="$c" && break; done
fi
[ -n "$PY" ] || { echo "FEHLER: mmo_game nicht gefunden (MMO_PY setzen)"; exit 1; }
[ -d "$DATA" ] || { echo "FEHLER: Datenverzeichnis fehlt: $DATA"; exit 1; }
mkdir -p "$OUT"; chmod 700 "$OUT"
# Platzprüfung: mindestens das Doppelte der Datenmenge muss frei sein (Zwischenkopie + Archiv)
need=$(( $(du -sk "$DATA" | cut -f1) * 2 + 10240 ))
free=$(df -Pk "$OUT" | awk 'NR==2{print $4}')
[ "$free" -ge "$need" ] || { echo "FEHLER: zu wenig freier Platz in $OUT ($free KB frei, $need KB nötig)"; exit 1; }
extras=()
for f in /etc/systemd/system/mmo.service /etc/caddy/Caddyfile /opt/mmo/DEPLOY_INFO; do [ -f "$f" ] && extras+=(--extra "$f"); done
cd "$PY"
archive="$(python3 -m mmo_game.backup create --data "$DATA" --out "$OUT" "${extras[@]}" --note "${MMO_NOTE:-}")"
python3 -m mmo_game.backup verify "$archive" --full
python3 -m mmo_game.backup prune --out "$OUT" --daily "${MMO_KEEP_DAILY:-14}" --weekly "${MMO_KEEP_WEEKLY:-8}"
echo "Sicherung fertig: $archive"
echo "Hinweis: Das ist eine Kopie auf demselben Server. Für Schutz bei Serververlust das Archiv zusätzlich extern ablegen."
