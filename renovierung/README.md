# Keller-Renovierung – Entwicklungsbereich

## Aktueller K02-Einstieg vom 01.11.2026

`k02/` enthält den eigenständigen Studienerzeuger für Böschung und Abraum. Der erneut geprüfte und gespeicherte Stand ist über die [Revisionsübersicht K02 / 31dba74](../cad/nx/REVISION_K02_31dba74.md) und die [Renovierungsbasis BASE](../cad/nx/k02/20261101T191747_4adeb5/BASE/BASE_21.prt) erreichbar. Der [Mengenbericht der geometrisch gleichen Erstlieferung](planung/2026-11-01/K02_STUDIE.md) behält seine früheren Modelllinks. Prüfungen und noch offene grafische NX-Prüfung stehen im [K02-Nachweis](../docs/entwicklungsstand/K02-native-2026-11-01.md). Komponentenordner vollständig beibehalten, [NX-Ladeanleitung](../cad/nx/README.md) beachten. Alle 13 PS/72 Felder bleiben registriert, auch gesperrte/ungeklärte Bereiche. Keine kumulative Baufolge oder Ausführungsfreigabe.

## Vorplanung vom 01.11.2026

**Aktueller Maßnahmenumfang:** [Ergänzung E01](../docs/plans/2026-11-01-keller-ergaenzung-umfang-leitungen.md) zusammen mit V01 lesen: mögliche Ausnahmen für Überbau/Niedergänge, Sandboden und Eingang der Tiefbau-Unterlagen. Maschinenlesbare Ergänzung: [UMFANG_E01.json](planung/2026-11-01/UMFANG_E01.json). Die V01-PDF allein bildet diese jüngere Umfangsvorgabe noch nicht ab.

Der [Projektplan zu Aushub und Schächten](../docs/plans/2026-11-01-keller-aushub-und-schachtplanung.md) gliedert die aktuelle Kellergeometrie in 13 räumliche Sektionen mit geplanter NX-Unterbaugruppenstruktur. Dazu gehören ein [21-seitiges Zeichnungsheft](../output/pdf/Keller_Vorplanung_V01.pdf), der [editierbare Sektionskatalog](planung/2026-11-01/sektionen.json) und das [Prüfprotokoll](planung/2026-11-01/PRUEFUNG.md).

Der Nutzer bestätigt fehlende belastbare Baugrund-/Fundamentunterlagen. Sämtliche Aushubfelder bleiben bis zur fachlichen Prüfung gesperrt. Planungssektoren sind keine zulässigen offenen Grabenlängen. V01 allein war eine Dokumentationsvorplanung; die anschließende getrennte K02-Implementierung ist oben eingeordnet.

**Status: K01-Implementierung fehlt weiterhin.** Die folgenden K01-Unterlagen sind historisch; der neue eigenständige K02-Erzeuger ersetzt die fehlenden K01-Originaldateien nicht.

`recovered/RENOVIERUNGSPLAN_AUS_VORSCHAU.json` enthält den in der Vorschau eingebetteten JSON-Studienplan (62 Zustandsdatensätze). Er wurde ohne Ausführung des JavaScripts extrahiert. `provenance/K01_JSON_EXTRACTION.json` nennt Quell- und Ergebnisprüfsumme. Die darin genannten CAD-Dateien fehlen weiterhin; auch die geometrischen Mengen wurden hier nicht neu berechnet.

`k01_unterlagen/` ist eine unveränderte Übernahme des tatsächlich erhaltenen Unterlagen-ZIP. Darin sind unter `archiv/` alte Start- und Testtexte enthalten, deren referenzierte Programm-/CAD-Dateien hier fehlen. **Diese Startanweisungen nicht als ausführbar behandeln.**

Die ursprüngliche Zielsetzung für eine getrennte Renovierungserweiterung bleibt maßgeblich; K02 setzt einen abgegrenzten Studienumfang um. Kein stiller Ersatz der fehlenden K01-Dateien durch Attrappen. Bestand und Ziel getrennt dokumentieren:

- Eingang: funktionierender, gespeicherter G02-Stand beim Nutzer.
- Ziel: unabhängig geklonte Basis und eigene Zustände; kein Rückwirken auf Original oder andere Zustände.
- Daten: belegte, abgeleitete, angenommene und unbekannte Werte explizit.
- Nachweis: räumliche Grenz-/Kollisionsprüfung und nachvollziehbare Volumen-/Lagerbilanz.
- Fachlicher Status: Konzept, keine geprüfte Standsicherheit oder Ausführungsplanung.

Die frühere Tabelle beschreibt 61 Prüffelder und BA62 als Teilabschluss. Die in den historischen Dokumenten angegebenen kleinen Feldlängen, Böschung, Arbeitsbreite und Schichten sind **nicht verbindliche neue Ausführungswerte**. Geometrie muss bei Wiederherstellung neu geprüft werden; gesperrte Bereiche nicht automatisch öffnen.

Verbindliche Anforderung: `docs/ANFORDERUNGEN_RENOVIERUNG.md`. Vorgehen: `docs/ENTWICKLUNGSPLAN.md`.
