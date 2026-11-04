# Spielserver auf einem VPS (Hostinger, Ubuntu 24.04)

Im Hostinger-Terminal (als root):
```bash
git clone -b claude/awesome-dirac-9k6p3n https://github.com/CartoonUsername/MMO.git
cd MMO
bash deploy/setup.sh
```
Das Skript installiert Caddy (automatisches HTTPS), legt den Spielserver als Systemdienst `mmo` an (Neustart bei Absturz, eigener Benutzer, Spielstand in `/var/lib/mmo`, tägliche Sicherung in `/var/backups/mmo`) und öffnet nur die Ports 22/80/443. Ohne Domain nutzt es `<IP>.sslip.io`; mit eigener Domain (A-Record auf die IP): `bash deploy/setup.sh spiel.beispiel.de`.

Der Spielserver lauscht nur auf 127.0.0.1; von außen erreichbar ist ausschließlich Caddy mit TLS. `--behind-proxy` liest die Spieleradresse aus `X-Forwarded-For` (nur von der eigenen Maschine akzeptiert), damit Verbindungs- und Sperrgrenzen je Spieler statt je Proxy gelten.

Nützlich: `systemctl status mmo`, `journalctl -u mmo -f`, Spielstand-Sicherung zurückspielen: Dienst stoppen, Archiv nach `/var/lib` entpacken, `chown -R mmo:mmo /var/lib/mmo`, Dienst starten.
Nicht enthalten: Mehrserverbetrieb, Überwachung, Datenbank (Platzhalter-Stand, ADR-0036).

Ubuntu 26.04: laut einer Drittquelle Python 3.14 und sudo-rs (als root irrelevant); der Server nutzt nur die Standardbibliothek und lief hier unter Python 3.13, 3.14 ist ungetestet. Caddy kommt aus dessen eigenem Paket-Repository, das nicht an die Ubuntu-Version gebunden ist.
