# ADR-0051: Forschung, Epochen, Entdecker (AP 12)

Status: angenommen (Namen/Zahlen sind Entwürfe, siehe `research_rules_v1.json`; Epoche, Namen, Weltgeschichte bleiben offen, §42)

## Entscheidung
- Weltdienst `ResearchService` (`mmo_world/research.py`) auf Siedlungsebene, ergänzend zu den bestehenden Figuren-Entdeckungen (ADR-0009). Keine CEE-Ereignisse, keine Migration; Snapshot-Schlüssel `research` nur bei Aktivität.
- **Epochen:** Die Weltepoche setzt der Betrieb (`set_epoch`, absichtlich kein Spielerbefehl; nur vorwärts). Techniken späterer Epochen sind gesperrt.
- **Siedlungen entscheiden selbst (§43):** Bewohner zahlen Münzen/Material (Senke) in ein Forschungsprojekt, danach läuft die Forschungszeit. Voraussetzungen (ohne Kreise) werden geprüft.
- **Entdecker (§44):** Die erste Siedlung der Welt erhält den Entdecker-Titel (größter Beitragszahler), einen Chronikeintrag und `lead_days` Vorsprung. Im Vorsprung kostet unabhängige Forschung den vollen Preis oder man kauft vom Entdecker eine Lizenz (Preis geht an ihn; Überzahlung wird erstattet). Danach ist Übernahme für alle günstig (40 %, halbe Zeit). Niemand blockiert eine Technik dauerhaft.
- **Wirkung:** Siedlungsprojekt-Stufen können an Techniken gebunden sein (`requires_tech`): Mauer ab Stufe 1 braucht Mauerbau, Hafen Seefahrt, Straße Stufe 3 Pflasterstraßen.
- Client: Fenster „Forschung“, Ereignis `tech`. Befehle `query.research`, `research.start/license/contribute`.

## Offen
Echte Epochen-Inhalte und Weltgeschichte, Städte-Spezialisierung mit Wirkung (Fahrzeugbau, Energie …), Produktionsvorsprung und Baupläne als Entdeckerbelohnung, Anbindung an Rezepte/Herstellung, Wissensweitergabe durch Handel, Forschungsbeiträge in Gilden/Chronik (AP 13).
