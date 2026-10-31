# Daten, Rechte und fehlende Bestandteile

## Enthalten

G02 ist eine vollständige Kopie des verfügbaren Lieferarchivs mit Code, Daten, Plan-PDFs, Belegbildern, zugeschnittenen Geodaten, STEP-Dateien, Tests und historischen Berichten. Der vollständige Außenrundgang wurde zusätzlich unter `sources/video/` übernommen. Die zusätzlichen Diagnoseberichte sind historische Originaldateien mit lokalen Pfadangaben.

Alle benötigten G02-Laufzeitquellen liegen bereits unter `projects/g02/`. Seine ursprünglichen relativen Pfade bleiben bestehen. Paketmanifeste und `provenance/IMPORT_MANIFEST.json` dokumentieren die übertragenen Dateien.

## Separat bereitgestellte Originalarchive

Das Hauptrepository enthält nicht nochmals die großen ursprünglichen ZIP-Downloads. Diese werden als zusätzliche Originalquellen-Pakete zur lokalen Ablage unter `local_data/originals/` angeboten: Planos, Umbau, DGM, bDOM und DOP. Ihre Größen und SHA-256 stehen in `provenance/RAW_SOURCE_ARCHIVES.json`.

Sie sind nicht für den G02-Journalstart erforderlich; die erforderlichen Ableitungen sind bereits im G02-Bestand enthalten. Sie helfen bei künftiger Quellenprüfung oder erneuter Geodatenauswertung. `local_data/` ist standardmäßig ignoriert: Codex Cloud erhält diese Dateien durch den Git-Push nicht. Für eine spätere gezielte Aufnahme zuerst Rechte, Datenschutz und Dateigröße prüfen.

## Nicht verfügbar / nicht übertragen

- K01-Journale, Maßnahmen-STEPs und der ursprüngliche ausführbare Maßnahmen-Erzeuger. Nur historische Unterlagen vorhanden.
- Native `.prt`-Ergebnisse aus der erfolgreichen NX-Sitzung des Nutzers. Diese liegen auf dessen Rechner.
- Fehlende Statik, Baugrund-/Grundwassernachweise, bestätigte Fundamentdaten, aktuelle Leitungsortung und vermessener EG-Höhenanschluss.
- Proprietäre NX-/Parasolid-Bibliotheken, Siemens-Lizenz-/Installationsdateien und Zugangsdaten.

## Rechte

Keine pauschale Open-Source-Lizenz über die privaten Planunterlagen legen. Eine spätere Lizenzentscheidung für eigens entwickelten Code ist vom Nutzer zu treffen; sie überträgt keine Rechte an fremden Plänen, Geodaten oder Bibliotheken.

Vorhandene Hinweise der Geodaten bleiben erhalten: **© GeoBasis-DE/LVermGeo SH/CC BY 4.0**, soweit im ursprünglichen Paket angegeben. Die mitgelieferte Quellenzuordnung und Datumsangaben beachten. Hier wurde keine neue Rechteklärung durchgeführt.

## Datenschutz

Privates Repository empfohlen. Pläne können Adresse, frühere Bauherren, Planverfasser, Unterschriften, Hausgeometrie und Versorgungsdaten enthalten. Diagnoseberichte enthalten lokale Windows-Pfade. Die Daten wurden zur Wahrung der Quellhashes nicht umfassend anonymisiert. Keine öffentlichen Screenshots oder Logs ohne Sichtprüfung teilen. Cloud-Codex erhält die Dateien, die du in seiner Umgebung zugänglich machst; dies bewusst entscheiden.
