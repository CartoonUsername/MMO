#!/usr/bin/env bash
# Prüft die UnityEngine-freien Teile des Unity-Clients (Netz, Katalog, Fenster, Formulare) gegen einen frisch gestarteten Testserver.
# Braucht dotnet (SDK 8+). Unity selbst wird dafür nicht benötigt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-17877}"
DATA="$(mktemp -d)"
cd "$ROOT/reference/python"
python3 -m mmo_game.net "$PORT" --data "$DATA" >"$DATA/server.log" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true; rm -rf "$DATA"' EXIT
for _ in $(seq 1 50); do curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 0.2; done
cd "$ROOT/client/unity/Tests~/CoreCheck"
dotnet run --nologo -- "ws://127.0.0.1:$PORT/ws"
# Übersetzungsprüfung der Unity-Skripte gegen Nachbildungen der UnityEngine-Schnittstellen (nur Tippfehler/Typfehler, kein Ersatz für Unity)
cd "$ROOT/client/unity/Tests~/CompileCheck"
dotnet build --nologo -v q
echo "Übersetzungsprüfung ok"
