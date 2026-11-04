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

# Sicherung: geprüfte, datierte Archive (ADR-0037); Skripte liegen unter /opt/mmo/scripts, Aufbewahrung 14 Tage + 8 Wochen
mkdir -p /opt/mmo/scripts && cp "$REPO_DIR"/scripts/*.sh /opt/mmo/scripts/ && chmod 755 /opt/mmo/scripts/*.sh
printf 'commit=%s\ndeployed=%s\n' "$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || echo unbekannt)" "$(date -u +%FT%TZ)" > /opt/mmo/DEPLOY_INFO
rm -f /etc/cron.daily/mmo-backup
cat > /etc/cron.d/mmo-backup <<'B'
17 3 * * * root /opt/mmo/scripts/backup_mmo.sh >> /var/log/mmo-backup.log 2>&1
B
chmod 644 /etc/cron.d/mmo-backup

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
