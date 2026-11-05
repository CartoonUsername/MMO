#!/usr/bin/env bash
# Rauchtest des Browser-Clients mit echtem Chromium gegen einen frischen Wegwerf-Server (Startmünzen erhöht, damit Gilde/Plots möglich sind).
# Braucht Node >= 22 und eine Chromium-Datei: scripts/browser_smoke.sh [pfad-zu-chrome] [port]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="${1:-$(ls -d "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1)}"
PORT="${2:-17911}"
[ -x "${CHROME:-}" ] || { echo "FEHLER: Chromium nicht gefunden (Pfad als erstes Argument angeben)"; exit 2; }
cd "$ROOT/reference/python"
python3 - "$PORT" <<'PY' &
import asyncio, sys
from mmo_game import GameServer, load_game_rules
from mmo_game.auth import AccountStore
from mmo_game.net import NetServer

async def main(port):
    R = load_game_rules()
    R["start_coins"] = 20000
    srv = NetServer(GameServer(R), host="127.0.0.1", port=port, auth=AccountStore(None))
    await srv.start()
    await asyncio.sleep(300)          # Obergrenze, der Aufrufer beendet den Prozess
asyncio.run(main(int(sys.argv[1])))
PY
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 0.2; done
node "$ROOT/scripts/browser_smoke.mjs" "$CHROME" "$PORT"
