#!/usr/bin/env bash
# Richtet den Spielserver auf einem frischen Ubuntu-24.04-VPS ein (als root ausführen):  bash deploy/setup.sh [domain]
# Ohne Domain wird <IP>.sslip.io verwendet (kostenloser Namensdienst, funktioniert sofort mit automatischem HTTPS).
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Bitte als root ausführen."; exit 1; }
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IP="$(curl -4 -fsS https://api.ipify.org || hostname -I | awk '{print $1}')"
DOMAIN="${1:-${IP}.sslip.io}"

apt-get update -y
apt-get install -y python3 curl ufw debian-keyring debian-archive-keyring apt-transport-https gpg
# Caddy (automatisches HTTPS) aus dem offiziellen Repository
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y && apt-get install -y caddy
fi

# Spielserver: eigener Benutzer, Code unter /opt/mmo, Spielstand unter /var/lib/mmo
id mmo >/dev/null 2>&1 || useradd --system --home /var/lib/mmo --shell /usr/sbin/nologin mmo
mkdir -p /opt/mmo /var/lib/mmo /var/backups/mmo
rm -rf /opt/mmo/python && cp -r "$REPO_DIR/reference/python" /opt/mmo/python
chown -R mmo:mmo /var/lib/mmo

cat > /etc/systemd/system/mmo.service <<'U'
[Unit]
Description=MMO Spielserver
After=network.target
[Service]
User=mmo
WorkingDirectory=/opt/mmo/python
ExecStart=/usr/bin/python3 -m mmo_game.net 7777 --data /var/lib/mmo --behind-proxy
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/lib/mmo
PrivateTmp=true
[Install]
WantedBy=multi-user.target
U

cat > /etc/caddy/Caddyfile <<C
${DOMAIN} {
    reverse_proxy 127.0.0.1:7777
}
C

# Tägliche Sicherung des Spielstands (14 Tage)
cat > /etc/cron.daily/mmo-backup <<'B'
#!/bin/sh
tar -czf /var/backups/mmo/spielstand-$(date +%F).tgz -C /var/lib mmo
find /var/backups/mmo -name 'spielstand-*.tgz' -mtime +14 -delete
B
chmod +x /etc/cron.daily/mmo-backup

# Firewall: nur SSH, HTTP, HTTPS
ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw --force enable >/dev/null

systemctl daemon-reload
systemctl enable --now mmo
systemctl restart caddy
sleep 2
systemctl is-active mmo caddy
echo
echo "Fertig. Spiel öffnen: https://${DOMAIN}/"
echo "Aktualisieren später: git pull && bash deploy/setup.sh ${DOMAIN}   (Spielstand bleibt erhalten)"
