# Keller-Renovierung – Entwicklungsbereich

## Vorplanung vom 01.11.2026

Der [Projektplan zu Aushub und Schächten](../docs/plans/2026-11-01-keller-aushub-und-schachtplanung.md) gliedert die aktuelle Kellergeometrie in 13 räumliche Sektionen mit geplanter NX-Unterbaugruppenstruktur. Dazu gehören ein [21-seitiges Zeichnungsheft](../output/pdf/Keller_Vorplanung_V01.pdf), der [editierbare Sektionskatalog](planung/2026-11-01/sektionen.json) und das [Prüfprotokoll](planung/2026-11-01/PRUEFUNG.md).

Der Nutzer bestätigt fehlende belastbare Baugrund-/Fundamentunterlagen. Sämtliche Aushubfelder bleiben bis zur fachlichen Prüfung gesperrt. Planungssektoren sind keine zulässigen offenen Grabenlängen. Der aktuelle Stand ergänzt Dokumentation; neue Renovierungs-.prt oder eine K02-Engine sind damit noch nicht implementiert.

**Status: K01-Implementierung fehlt.** Dieser Bereich enthält historische Unterlagen und den vollständigen Nutzerauftrag, noch keine lauffähige Renovierungserweiterung.

`recovered/RENOVIERUNGSPLAN_AUS_VORSCHAU.json` enthält den in der Vorschau eingebetteten JSON-Studienplan (62 Zustandsdatensätze). Er wurde ohne Ausführung des JavaScripts extrahiert. `provenance/K01_JSON_EXTRACTION.json` nennt Quell- und Ergebnisprüfsumme. Die darin genannten CAD-Dateien fehlen weiterhin; auch die geometrischen Mengen wurden hier nicht neu berechnet.

`k01_unterlagen/` ist eine unveränderte Übernahme des tatsächlich erhaltenen Unterlagen-ZIP. Darin sind unter `archiv/` alte Start- und Testtexte enthalten, deren referenzierte Programm-/CAD-Dateien hier fehlen. **Diese Startanweisungen nicht als ausführbar behandeln.**

Der nächste Stand soll getrennt von G02 entwickelt werden, zum Beispiel K02. Kein stiller Ersatz der fehlenden K01-Dateien durch Attrappen. Bestand und Ziel getrennt dokumentieren:

- Eingang: funktionierender, gespeicherter G02-Stand beim Nutzer.
- Ziel: unabhängig geklonte Basis und eigene Zustände; kein Rückwirken auf Original oder andere Zustände.
- Daten: belegte, abgeleitete, angenommene und unbekannte Werte explizit.
- Nachweis: räumliche Grenz-/Kollisionsprüfung und nachvollziehbare Volumen-/Lagerbilanz.
- Fachlicher Status: Konzept, keine geprüfte Standsicherheit oder Ausführungsplanung.

Die frühere Tabelle beschreibt 61 Prüffelder und BA62 als Teilabschluss. Die in den historischen Dokumenten angegebenen kleinen Feldlängen, Böschung, Arbeitsbreite und Schichten sind **nicht verbindliche neue Ausführungswerte**. Geometrie muss bei Wiederherstellung neu geprüft werden; gesperrte Bereiche nicht automatisch öffnen.

Verbindliche Anforderung: `docs/ANFORDERUNGEN_RENOVIERUNG.md`. Vorgehen: `docs/ENTWICKLUNGSPLAN.md`.
