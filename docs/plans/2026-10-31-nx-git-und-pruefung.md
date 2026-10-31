# Native NX-Dateien und wiederholbare NX-Prüfung

Auftrag vom 31.10.2026: native Dateien im Repository erzeugen und mit Git verwalten; bei weiteren Projektständen immer die tatsächliche Erstellbarkeit in NX prüfen.

## Umsetzung

Die bestehende G02-Engine bleibt bytegleich. Ein neuer Batch-Einstieg unter `tools/` arbeitet mit einer temporären vollständigen Quellkopie. NX erzeugt wegen der Windows-Pfadlängengrenze in einem kurzen neuen temporären Ordner; erst nach erfolgreichem Aufbau werden die zum Projekt gehörenden nativen Dateien unter `cad/nx/<Laufkennung>/` übernommen. Nur native `.prt`, relative Dateimanifeste und kompakte Prüfnachweise werden versioniert; große native Binärdateien über Git LFS. Originalmodelle und bestehende Ausgaben werden nicht überschrieben. Arbeitsbranch: `feature/nx-native-versioning` im vorhandenen Repository, damit die spätere NX-Ablage am gewünschten Ort liegt.

Ein echter NX-Batchprozess baut den vollständigen aktuellen G02-Stand mit seinen bereits dokumentierten Modellannahmen. Der ausdrückliche Aufruf mit `--accept-model-assumptions` ersetzt ausschließlich die zwei interaktiven Bestätigungsdialoge. Geometrie-, Hash-, Einheiten- und Strukturprüfungen bleiben aktiv. Ein zweiter frischer NX-Prozess öffnet die gespeicherte Baugruppe vollständig. Zusätzlich öffnet ein weiterer NX-Lauf eine verschobene Kopie mit ausdrücklich konfigurierten Suchpfaden; jede geladene Komponente muss aus dieser Kopie kommen. Keine manuelle Nutzer-NX-Sitzung wird verändert.

Der Nachweis enthält Quellfingerprint, Generatorfingerprint, NX-Version, Datum, Part-Dateien und SHA-256, Masterpfad, Build-Status und Wiederöffnungs-/Portabilitätsstatus. Eine Offline-Prüfung kann nur Aktualität und Dateiintegrität bestätigen; sie ersetzt keinen echten NX-Lauf. Fehlende NX-Lizenz, unvollständige Ergebnisse oder geänderte Eingaben führen zu einem sichtbaren Fehlerstatus.

## Schritte

- [x] Vorhandenes Python und NX ermitteln; Offline-Ausgangsprüfungen und echter NX-Minimaltest. Historischer Windows-Pfadtest bleibt dokumentiert offen.
- [x] Tests für veraltete/fehlende/außerhalb liegende Parts, fehlenden NX-Nachweis und Quelländerungen rot ausführen.
- [x] Batch-Runner, echte Build-/Prüfjournale und Nachweisvalidator implementieren.
- [x] Git-LFS-Attribute und gezielte Ignore-Ausnahmen für `cad/nx/` ergänzen.
- [x] Vollständigen echten G02-Aufbau ausführen; Fehler reproduzieren und begründet behandeln, keine Schutzprüfungen umgehen.
- [x] Gespeicherte Baugruppe in frischem NX öffnen; verschobene Kopie vollständig laden und alle Pfade/Hashes prüfen.
- [x] AGENTS.md, Testanleitung, Projektstand und Roadmap um verpflichtende NX-Prüfung ergänzen.
- [x] Offline-Tests, G02-Importhashes, LFS-Zuordnung, Native-Nachweis und Diff prüfen; unabhängiges Review; gezielt committen. Nativer Implementierungsstand: `a8b7f62`; `git lfs fsck` bestanden. Historischer Windows-Pfadtest bleibt ausdrücklich offen.

## Abnahme

Native Dateien existieren tatsächlich und sind mit LFS erfasst; Build und Wiederöffnen stammen aus NX 2406, nicht aus Simulation. Die vollständige Baugruppe ist mit dem dokumentierten Ladeverfahren nach einem Checkout ladbar. Alle Importdateien bleiben bytegleich. Fachlich offene Punkte von G02 bleiben offen.

## Entscheidungsprotokoll

- Der neue Nutzerauftrag erlaubt native Versionierung und einen echten Neuaufbau; frühere reine-Lokaldaten-Regeln werden dafür gezielt eingeschränkt.
- Python 3.12.14 aus der vorhandenen Codex-Laufzeit ist für Offline-Tests verfügbar. NX verwendet sein eigenes unverändertes Python 3.10.15. Es werden keine Pakete in NX installiert.
- NX 2406.6000 unter `C:/Siemens/NX2406` wurde ermittelt; ein separater echter Batch-Minimaltest meldete eine leere Sitzung und verfügbare NX-UI-API.
- Echter Fehler reproduziert: Der erste vollständige Versuch erreichte das gespeicherte Haus, scheiterte aber beim Umgebungs-Testprotokoll an einem zu langen temporären Windows-Dateipfad. Kurzen temporären Ausgabeordner eingeführt; Regression für kurze/eindeutige Pfade und Abweisung zu langer Temp-Wurzeln rot/grün nachgewiesen. Keine G02-Quelle geändert.
- Unabhängiges Review: Fehlgeschlagene Vorbereitung muss den jüngsten Versuch auf FAIL setzen; `repo_support.py` gehört in den Generatorfingerprint. Beide Befunde durch zunächst fehlgeschlagene und danach bestandene Regressionen abgesichert. Der Masterverweis in CURRENT wird ebenfalls geprüft, weil ein falscher Öffnungspfad trotz gültiger Dateien den Nutzer zum falschen Modell führen könnte.
- Offline-Tests starten mit `PYTHONUTF8=1`, damit historische UTF-8-Fixtures unter Windows nicht mit cp1252 gelesen/geschrieben werden. Plattformbedingte Pfadfehler bleiben sichtbar; keine Tests überspringen oder Hashregister zum Grünfärben ändern.
