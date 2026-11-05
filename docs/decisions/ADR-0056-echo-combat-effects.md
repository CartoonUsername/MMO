# ADR-0056: Kampfwirkung der Kampfechos (AP 17)

Status: angenommen (Vorschlag, vom Projektinhaber am 2026-11-05 zur eigenständigen Entscheidung freigegeben; Platzhalterwerte)

## Entscheidung (Blueprint §17–21, §73)
- Ausgerüstete Echos wirken im Kampf über den bestehenden Ausrüstungskanal (`spec.gear` der Simulation); es gibt keine neue Simulationsregel und keine neue Simulationsversion.
- Neue Echo-Regeln `echo_rules_v2.json` (= v1 + Abschnitt `combat`); v1 bleibt erhalten. Keine CEE-Änderung, keine Weltmigration.
- **Stärke** = Resonanzstufe × (1000 + 40 × Meisterschaftsstufe der Tradition) / 1000; Hybrid-Echos wirken mit 50 %. Stufe 0 wirkt nicht.
- **Profile je Tradition** (Schritt je Stärkepunkt): Wolf: schwerer Schaden +0,6 %, Ausweichkosten −1 je 10; Glut: leichter Schaden +0,5 %, schwerer +0,3 %; Stein: erlittener Schaden −0,4 %, Blockschaden −0,6 %. Bei +30 z. B. Wolf ×1,18, Stein ×0,88 erlittener Schaden.
- Mehrere Echos kombinieren wie Ausrüstung (Faktoren multiplizieren, Blockwert Minimum, Kosten addieren); Ausrüstung und Echos werden im Spielserver zusammengeführt (`_sim_gear`).
- **Fähigkeiten:** Das Haupt-Echo schaltet die Fähigkeiten seiner Tradition im Kampf frei (wie das Klassen-Kit, ohne die CEE-Ausrüstung zu ändern); ein Hybrid-Echo erst ab Meisterschaftsstufe 1 dieser Tradition.
- Sicht: `echo.view()` liefert `combat.effects` und `combat.abilities`.

## Nicht entschieden / offen
- Elementare Wirkung der Echos (Feld `element` ist nur beschreibend), Bandwirkungen (Manifestationen/Optik im Kampf), weitere Traditionen und Wirkungsarten (nur Größen, die die Simulation kennt).
- Balancing der Platzhalterwerte; Anzeige im Client (Echo-Fenster zeigt die Wirkung noch nicht), in Browser und Unity nicht geprüft.
