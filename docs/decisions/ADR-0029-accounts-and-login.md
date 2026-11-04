# ADR-0029: Konten, Anmeldung und Transportsicherheit

**Status:** akzeptiert als Grundlage für den Vertical Slice. Grenzen und Fristen sind Platzhalter. **Kein Ersatz für ein geprüftes Sicherheitskonzept vor einem öffentlichen Betrieb.**

**Kontext:** Die erste Fassung des Spielservers kannte nur einen Kontonamen (ADR-0028) und war deshalb nur lokal zulässig. Für Spiele mit zwei Spielern im Netz braucht es echte Anmeldung, ohne bezahlte Dienste.

**Entscheidungen**
1. **Konten (`mmo_game/auth.py`, nur Standardbibliothek):** Passwort 8–128 Zeichen; Speicherung nur als PBKDF2-HMAC-SHA256 mit zufälligem 16-Byte-Salz und konfigurierbarer Durchlaufzahl (Platzhalter 200 000); Vergleich in konstanter Zeit. Die Kontodatei (`accounts.json` im Datenverzeichnis) wird atomar mit Rechten 0600 geschrieben; beim Laden wird jedes Konto geprüft.
2. **Missbrauchsschutz:** Sperre je Konto nach 5 Fehlversuchen (60 s), Sperre je Adresse nach 20 Fehlversuchen in 5 Minuten, höchstens 5 Registrierungen je Adresse und Stunde, höchstens 4 gleichzeitige Verbindungen je Adresse, 16 insgesamt, 10 s Frist für die erste Nachricht. Falsches Passwort, unbekanntes Konto und falsches Token liefern dieselbe Antwort; für unbekannte Konten wird derselbe Hash-Aufwand betrieben.
3. **Sitzungs-Token:** Nach Anmeldung erhält der Client ein zufälliges Token (`secrets`, 256 Bit), das nur als SHA-256 im Speicher des Servers liegt, 1 Stunde gilt, nur einmal einlösbar ist (bei jeder Einlösung ersetzt) und nur ein Token je Konto zulässt. Es dient der Wiederanmeldung nach Verbindungsabbruch; es wird nicht in die Kontodatei geschrieben (Neustart des Servers macht es ungültig).
4. **Verdrängen:** Eine erfolgreiche Anmeldung desselben Kontos beendet die alte Verbindung (die Figur gilt wie bei einem Abbruch; im Kampf als Flucht).
5. **TLS:** Optional über `--cert`/`--key` (TLS ≥ 1.2, `ssl` der Standardbibliothek; ein selbst signiertes Zertifikat genügt für Tests). **Nicht-lokale Adressen werden ohne Konten und TLS abgelehnt** (der Server startet nicht). `--insecure-dev` schaltet die Konten nur für 127.0.0.1 ab.
6. **Figur = Konto:** Ein Konto besitzt genau eine Figur gleichen Namens; Mehrfachfiguren und Kontoverwaltung folgen später.

**Absicherung:** `tests/test_auth.py` (25 Tests: Hashing/Salz, Sperren mit simulierter Uhr, Token, Dateirechte und -beschädigung, Netzwerk mit Registrierung/Anmeldung/Wiederanmeldung/Verdrängen/Adresslimit, TLS mit selbst signiertem Zertifikat, Klartext gegen TLS, unbekanntes Zertifikat); Mutationstests (siehe Statusbericht).

**Offen / Grenzen**
- Kein Passwort-Zurücksetzen, keine E-Mail, keine Kontosperre durch Betreiber, kein Zwei-Faktor, keine Passwortregeln über die Länge hinaus; Tokens überleben keinen Serverneustart.
- Die Sperre je Adresse sieht hinter einem Proxy nur dessen Adresse; Betrieb hinter Lastverteiler braucht eine geprüfte Weitergabe der Client-Adresse.
- Der Unity-Client ist unverändert ungeprüft (Anmeldefelder ergänzt); TLS mit selbst signiertem Zertifikat erfordert Eintrag im System oder eine eigene Zertifikatsprüfung.
- Sicherheitsprüfung durch Dritte steht aus.
