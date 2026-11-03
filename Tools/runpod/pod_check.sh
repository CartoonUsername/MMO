#!/usr/bin/env bash
# Schnellprüfung eines (RunPod-)Pods. Rein lesend, verändert nichts. Dauer: wenige Sekunden.
# Aufruf:  bash Tools/runpod/pod_check.sh
ok()   { printf '[ OK ] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*"; FAILED=1; }
warn() { printf '[WARN] %s\n' "$*"; }
FAILED=0

echo "== System"; . /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-unbekannt}"; echo "Benutzer: $(whoami)"
echo "RAM (frei/gesamt, GB): $(free -g | awk '/Mem:/{print $7"/"$2}')   Kerne: $(nproc)"
echo "Freier Speicher auf /: $(df -h / | awk 'NR==2{print $4}')"

echo "== GPU"
if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
  ok "nvidia-smi: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader)"
else
  fail "nvidia-smi nicht nutzbar -> Pod hat keinen GPU-Zugriff. SOFORT STOPPEN (Kosten!)."
fi
# Geräteknoten sind je nach Container unterschiedlich nummeriert; entscheidend ist, dass nvidia-smi läuft.
echo "Geräte: $(ls /dev/nvidia* 2>/dev/null | tr '\n' ' ')"

echo "== Grafik (für Engine-Tests)"
if command -v vulkaninfo >/dev/null; then
  vulkaninfo --summary 2>/dev/null | grep -i -E "deviceName|driverName" | head -4 || true
  vulkaninfo --summary 2>/dev/null | grep -qi nvidia && ok "Vulkan sieht NVIDIA" || warn "Vulkan sieht keine NVIDIA-GPU (nur Software-Rendering?)"
else
  warn "vulkaninfo nicht installiert (apt install vulkan-tools)"
fi
[ -d /dev/dri ] && ok "/dev/dri vorhanden" || warn "/dev/dri fehlt (kein direktes Rendering im Desktop)"

echo "Vulkan-ICD-Dateien: $(ls /usr/share/vulkan/icd.d /etc/vulkan/icd.d 2>/dev/null | tr '\n' ' ')"
echo "NVIDIA-Grafikbibliotheken: $(ldconfig -p 2>/dev/null | grep -c -i -E 'libGLX_nvidia|libnvidia-glcore|libnvidia-vulkan')"
sudo -n true 2>/dev/null && ok "sudo ohne Passwort verfügbar" || warn "kein sudo (apt install nicht möglich)"

echo "== Werkzeuge"
for t in git python3 gcc curl; do command -v "$t" >/dev/null && ok "$t $($t --version 2>&1 | head -1)" || warn "$t fehlt"; done

echo "== Projekt-Tests (CPU)"
if [ -d reference/python ]; then
  (cd reference/python && python3 -m unittest discover -s . -t . 2>&1 | tail -3)
else
  warn "Im Repo-Wurzelverzeichnis ausführen, um die Python-Tests mitzulaufen"
fi

echo; [ "$FAILED" = 0 ] && echo "ERGEBNIS: Pod brauchbar." || echo "ERGEBNIS: Pod NICHT brauchbar - stoppen und anderes Template wählen."
exit "$FAILED"
