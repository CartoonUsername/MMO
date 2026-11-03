# ADR-0024: Push-Ereignisse (Benachrichtigungen)

**Status:** akzeptiert als technische Grundlage. Größen (Postfachlänge, Abrufmenge) sind Platzhalter; der Live-Transport ist nicht gebaut.

**Kontext:** Spieler müssen von Dingen erfahren, die ohne ihr Zutun passieren: eine wartende Order wird ausgeführt, ein Angebot trifft ein, eine Firma kündigt, ein Beschluss steht an. Bisher musste man alles abfragen (`query.*`). Gleichzeitig darf eine Benachrichtigung nie zur Wahrheitsquelle werden und keine Geheimnisse preisgeben.

**Entscheidungen**
1. **Postfach statt Fire-and-forget:** Jede Figur hat ein Postfach mit fortlaufender Folgenummer (`seq`). Live-Push (`Outbox.listeners`, `Gateway.on_push` je Sitzung) ist nur ein Wecksignal; **Zuverlässigkeit entsteht durch Abruf**: `notify.fetch(char, after, limit)` liefert alles nach `after`, `latest` und `gap`; `notify.ack(char, upto)` räumt auf. Zustellung mindestens einmal, der Client entdoppelt über `seq`. Offline aufgelaufene Nachrichten bleiben liegen.
2. **Begrenzt:** Das Postfach hält höchstens 200 Einträge; Verdrängtes meldet `gap` (der Client sieht, dass er etwas verpasst hat, und fragt den Zustand ab).
3. **Abgeleitet und nicht maßgeblich:** Benachrichtigungen tragen nur Kennungen und Konditionen (Angebot, Auftrag, Firma, Figur, Preis, Menge), nie Inventar, Salden oder Daten Dritter; sie sind **nicht Teil des Weltzustands** und ändern keinen Hash der Golden Vectors (die Vektoren pinnen Inhalte über die Abrufe als Schrittergebnisse). Sie werden aber mit der Welt gesichert (`outbox` im Snapshot-Umschlag, eigener Hash; fehlt der Schlüssel, ist das Postfach leer).
4. **Stummschaltung:** Der Spieler kann Arten stummschalten; stumme Arten werden gar nicht abgelegt und nicht geschoben.
5. **Erzeugung in den Weltdiensten, nicht im Gateway:** Auch Dinge, die der Server selbst auslöst (Tagesabschluss, Verfall, Ausführung wartender Orders), erzeugen Nachrichten. Abgelehnte Aktionen erzeugen keine. Empfänger: Orderbuch (Eigentümer der wartenden Order bei Ausführung/Verfall), Angebote (Adressat, Anbieter, bei Verfall beide), Firma (eingestellt/ausgeschieden/befördert/zurückgestuft, Verwarnung bei Statuswechsel, Verwalter bei Austritt, Gesellschafter bei Anteilsangebot/Antrag/Ergebnis, Mitarbeiter und Gesellschafter bei Schließung – nicht der Auslöser), Produktion (Gründer und Geschäftsführer bei fertigem Auftrag), Wissen (Schüler).
6. **Protokoll:** `notify.fetch` (lesend), `notify.ack`, `notify.mute`, `notify.unmute` (Berechtigung: eigene Figur).
7. **Golden Vectors:** Szenario `notifications` (Arten, Empfänger, Abruf mit `after`/`limit`, Quittung, Stummschaltung, Fehlerfälle).

**Absicherung:** `tests/test_notifications.py` (29 Tests: Postfach, Lücke, Quittung, Stummschaltung, Persistenz, jede Ereignisart mit Empfängern und Inhalt, Abgelehntes erzeugt nichts, Datenschutz der Inhalte, Gateway, Live-Push je Sitzung, Umschlag mit/ohne Postfach, Manipulation); Mutationstests (alle erkannt).

**Offen / Grenzen**
- Der Live-Transport (Verbindung, Wiederaufbau, Reihenfolgegarantie über mehrere Verbindungen) und Benachrichtigungen außerhalb des Spiels (Mobilgerät, E-Mail) sind nicht gebaut.
- Weitere Arten fehlen: Kampf (Gruppeneinladung, Begegnungsende), Weltereignisse, Preisalarme, Systemmitteilungen; Gruppeneinladungen setzen Gruppenbildung voraus.
- Kein Prioritäts- oder Bündelungskonzept (viele Ausführungen einer Order erzeugen viele Einträge) und keine Aufbewahrungsfrist außer der Postfachlänge.
