# M0 / P01: Rein lesendes Dateiinventar – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task; superpowers:subagent-driven-development is an alternative when delegation is selected. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen explizit ausgewählten Quellordner rein lesend inventarisieren und einen neuen lokalen JSON-Bericht außerhalb der Quelle schreiben.

**Architecture:** Ein NX-freier Kern liefert ein deterministisches Inventar; ein schmales CLI validiert Ein-/Ausgabepfade und schreibt den Bericht exklusiv. Dateiinventar und spätere NX-Referenzinventarisierung sind getrennt. Die vorhandene Testorchestrierung erhält eine zusätzliche isolierte Testgruppe.

**Tech Stack:** Python >=3.10, Standardbibliothek, `unittest`, Windows und portable Offline-Tests. Kein `NXOpen`, keine CAD-Bibliothek.

**Spec:** [Roadmap und Architektur](2026-10-31-renovierung-roadmap.md), [P01 und gemeinsamer Startblock](2026-10-31-entwicklungsprompts.md), `AGENTS.md` und `docs/ANFORDERUNGEN_RENOVIERUNG.md`.

**Status:** Ausführbarer Planungsentwurf; keine der unten genannten neuen Code-Dateien wurde durch die Roadmap-Erstellung angelegt. P00 muss eine geeignete Python-Umgebung und nachvollziehbare aktuelle Testbasis liefern. Vor Codebeginn den Etappenentwurf nach Superpowers prüfen. Eine konkrete native Quelle ist nur für den abschließenden realen Inventarlauf nötig.

## Global Constraints

- G02 und historische Importdateien/-manifeste unverändert erhalten.
- Quelle nur lesen. Kein NX starten, kein Part speichern/schließen, keine Quellbereinigung.
- Native `.prt` sind undurchsichtige Dateien: aus Dateinamen keine Baugruppen-/Interpart-Referenzen ableiten.
- Python >=3.10; keine neuen Fremdpakete für P01.
- Berichte außerhalb der Quelle in einer neuen, ausdrücklich gewählten Datei; keine vorhandenen Ziele überschreiben.
- Lokale Quellenpfade und Berichte nicht automatisch veröffentlichen.
- Erfolgreiches Dateiinventar ist kein NX-/Referenz-/Kopiernachweis und keine atomare Momentaufnahme eines aktiv bearbeiteten Ordners.

## Review Focus

1. Windows-Junctions und Symlinks einschließlich Quell-/Zielvorfahren dürfen die erlaubten Pfade nicht umgehen: Aufgabe 1/2 mit realen Verknüpfungen, soweit lokal möglich; sonst ausdrücklich übersprungen und ergänzend Fehlerpfad simuliert.
2. Quelle verändert sich während des Hashens: Aufgabe 1 muss einen begründeten Fehler melden, keine unbemerkte Freigabe.
3. Unlesbare Datei oder Verzeichnis liefert ein unvollständiges Inventar: Aufgabe 1 muss einen Fehler und `status=FAIL` liefern, statt Einträge still zu überspringen.
4. Gleichnamige Dateien mit unterschiedlicher Großschreibung oder Unicode-Namen: Aufgabe 1 erhält Namen exakt, sortiert reproduzierbar und meldet Case-Kollisionen.
5. Vorhandenes Berichtsziel, Ziel in Quelle oder fehlgeschlagener Test-Unterprozess: Aufgaben 2/3 verweigern Überschreiben und propagieren Fehlercodes.

## Dateien und Schnittstellen

| Datei | Verantwortung |
|---|---|
| `renovierung/src/renovierung_core/__init__.py` | Importierbares Paket, keine Seiteneffekte |
| `renovierung/src/renovierung_core/inventory.py` | Inventarschema, sicherer Dateiscan und Hashes |
| `renovierung/tools/inventory.py` | CLI, Quell-/Ausgabepfadprüfung, exklusives Schreiben |
| `renovierung/tests/test_inventory.py` | Scan, Fehlerfälle und Quellschutz |
| `renovierung/tests/test_inventory_cli.py` | CLI-Integration und Ausgabegrenzen |
| `tests/test_check_runner.py` | Neue Testgruppe und Fehlerweitergabe des Runners |
| `tools/run_checks.py` | Gezielte Integration einer Renovierungstestgruppe |
| `renovierung/README.md` | Tatsächlich implementierte Benutzung und Grenzen |
| `docs/entwicklungsstand/P01-dateiinventar.md` | Nachweis, offene Punkte, nächste Etappe |

Synthetische Dateien per `tempfile.TemporaryDirectory()` erzeugen; keine realen Haus-/NX-Daten als neue Testfixtures einchecken. Testdateien fügen den absoluten Pfad `renovierung/src` zu ihrem Importpfad hinzu; keine Abhängigkeit vom aktuellen Arbeitsverzeichnis. Das CLI tut dies relativ zu seiner eigenen Datei.

## Aufgabe 1: Deterministischer Scan mit expliziten Fehlern

**Interface:** `scan_directory(source_root: pathlib.Path) -> dict[str, object]` in `inventory.py`.

Ergebnisformat Version `HAUSPLAN_FILE_INVENTORY_V1`:

```json
{
  "schema": "HAUSPLAN_FILE_INVENTORY_V1",
  "source_root": "<absoluter normalisierter Quellpfad>",
  "status": "PASS",
  "nx_references_examined": false,
  "files": [{"path": "teil.prt", "bytes": 3, "sha256": "<64 hex>"}],
  "issues": []
}
```

`files` und `issues` nach relativen POSIX-Pfaden sortieren; Groß-/Kleinschreibung erhalten. Jede Issue enthält `path`, `code` und `message`. Fehlercodes: `INVALID_ROOT`, `LINK_NOT_ALLOWED`, `UNREADABLE`, `CHANGED_DURING_SCAN`, `CASE_COLLISION`, `UNSUPPORTED_ENTRY`. Jeder Issue setzt `status=FAIL`; erfolgreich gelesene Dateien dürfen für die Diagnose enthalten bleiben. Verknüpfungen nicht verfolgen. Dateierweiterungen einschließlich `.prt` und versteckte Dateien nicht still ausfiltern. Keine Zeitstempel im deterministischen Kernresultat; Laufdatum/Version im Etappenbericht erfassen.

Vor und nach dem Hashen Dateikennung, Größe und Änderungszeit prüfen; am Scanende erfasste Verzeichniseinträge und Dateistatus erneut vergleichen, um übliche laufende Änderungen zu erkennen. Bei unlesbaren Verzeichnissen Fehler erfassen. Keine Garantie gegen beliebige gleichzeitige Manipulation behaupten: für spätere Kopien fordert P03/P04 eine ruhende Quelle und erneute Hashprüfung. Windows-Reparse-Points auch unter Python 3.10 erkennen; nicht auf neuere `Path.is_junction()`-Verfügbarkeit bauen. Quellvorfahren vor Pfadauflösung auf Links prüfen; tatsächliche Plattformsemantik berücksichtigen.

- [ ] Rot: `test_scan_hash_and_relative_path` für eine temporäre Datei `Unterordner/Teil ä.prt` mit Inhalt `b'abc'`; `bytes == 3`, SHA-256 gleich `hashlib.sha256(b'abc').hexdigest()`, `nx_references_examined is False`.
- [ ] Rot: `test_repeat_is_deterministic_and_source_unchanged`; zwei Resultate identisch, Byteinhalt und mtime der Quelle vor/nach gleich. Leerer gültiger Ordner liefert PASS mit leerer Liste, aber keinen Hinweis auf vorhandene NX-Basis.
- [ ] Rot: Fehlerfälle für fehlende Root, Root als Datei, unlesbare Datei/Verzeichnis, Symlink/Junction, Case-Kollision, Dateiänderung während des Lesens und neu auftauchende Datei vor Abschluss. Unlesbarkeit/Änderung kontrolliert mit `unittest.mock` auslösen, nicht von Administratorrechten abhängig machen. Plattformgrenzen von echten Linktests dokumentieren.
- [ ] Befehl ausführen: `python -m unittest discover -s renovierung/tests -p test_inventory.py -v`; die neuen fachlichen Assertions müssen vor Implementierung scheitern, Ursache dokumentieren.
- [ ] Paket und `scan_directory` minimal implementieren; Datei-Hashes blockweise berechnen, keine vollständigen großen CAD-Dateien in RAM laden.
- [ ] Denselben Testbefehl ausführen; Exit 0 und keine unerklärten Skips. Quellschutz prüfen und Diff reviewen.
- [ ] Nur zugehörige neue Paket-/Testdateien nach Prüfung in einen kleinen Commit aufnehmen; fremde Änderungen aussparen.

## Aufgabe 2: CLI und sichere Berichtsausgabe

**Interfaces:** Im CLI `main(argv: list[str] | None = None) -> int`; `write_report(report: dict[str, object], source_root: pathlib.Path, output: pathlib.Path) -> None`.
Konsumiert `scan_directory` aus Aufgabe 1.

Aufrufvertrag:

```text
python renovierung/tools/inventory.py --source <QUELLORDNER> --output <NEUE_JSON_DATEI>
```

Pfadwerte sind Laufparameter, keine voreingestellten echten Nutzerpfade. Quelle und Ziel auflösen/prüfen; vorhandene Vorfahren dürfen keine Symlinks/Junctions sein. Ziel innerhalb oder gleich Quelle verweigern. Ziel-Elternverzeichnis muss bereits existieren: keine automatische Verzeichniserzeugung durch dieses Werkzeug. Bericht UTF-8, eingerückt, abschließender Zeilenumbruch; Datei exklusiv mit Modus `x` öffnen. Existierendes Ziel inklusive bestehendem Link unverändert lassen. Report mit `status=FAIL` darf als Diagnose geschrieben werden; CLI liefert dann Exit 1. Exit 2 für ungültige Argumente/Pfade oder Schreibfehler. PASS nur bei komplettem Scan und erfolgreicher Ausgabe.

- [ ] Rot: CLI-Unterprozess an temporärer Quelle erzeugt externen Bericht, Exit 0 und erwartetes Schema; Aufruf aus anderem Arbeitsverzeichnis funktioniert.
- [ ] Rot: existierendes Ziel bleibt bytegleich; Ziel innerhalb Quelle, fehlender Ziel-Elternordner und Ziel über Link ergeben Exit 2 und keine neue Datei in Quelle.
- [ ] Rot: Fehler im Dateiscan ergibt Diagnosebericht mit FAIL und Exit 1; Hash-/mtime-Vergleich bestätigt unveränderte Quelle.
- [ ] `python -m unittest discover -s renovierung/tests -p test_inventory_cli.py -v` ausführen und erwartete neue Fehler dokumentieren.
- [ ] CLI und `write_report` implementieren; keine automatischen NX-Imports, Installationen oder Netzwerkzugriffe.
- [ ] `python -m unittest discover -s renovierung/tests -v` ausführen; Exit 0. Danach relevante Dateien reviewen und gezielt committen.

## Aufgabe 3: Testintegration und erste benutzbare Lieferung

**Interface:** Bestehendes `tools/run_checks.py:main()` behält Aufruf und Returncode-Vertrag. Ergänze Job `renovierung_tests` mit `sys.executable -m unittest discover -s <ROOT/renovierung/tests> -v` nach den Repository-Tests und vor der optionalen vollständigen G02-Suite. Jede Gruppe bleibt ein separater Prozess. Log und `RESULT.json` verwenden das vorhandene Format.

- [ ] Rot: `tests/test_check_runner.py` prüft mit kontrollierten Unterprozess-Ergebnissen, dass die neue Gruppe im schnellen und vollständigen Lauf enthalten ist und ihr Fehler einen FAIL-Bericht/Exit 1 erzeugt. Keine verschachtelte echte Komplettsuite im Unit-Test starten.
- [ ] `python -m unittest discover -s tests -p test_check_runner.py -v` ausführen und das relevante Scheitern belegen.
- [ ] Den Runner minimal ergänzen, ohne vorhandene Gruppen zu entfernen oder G02 zu bearbeiten.
- [ ] `python tools/run_checks.py` und `python tools/run_checks.py --full` ausführen; beide Exit 0 erforderlich. Jede Testart korrekt benennen, keine NX-Behauptung.
- [ ] Benutzung/Grenzen in `renovierung/README.md` ergänzen. Falls tatsächliche native Quelle bekannt und ausdrücklich ausgewählt: Inventarlauf ausführen, Bericht lokal außerhalb Quelle aufbewahren. Ansonsten reale Inventarisierung als offen benennen.
- [ ] `docs/entwicklungsstand/P01-dateiinventar.md` schreiben: Version, Datum, Befehle, Codes, Logs, Grenzen einschließlich nebenläufiger Änderungen, G02-Integrität, Quelle vorhanden/fehlend und P02-Voraussetzungen.
- [ ] Diff und Tests unabhängig reviewen lassen; relevante Fehler schließen und betroffene Prüfungen wiederholen. Nur überprüfte Dateien committen; Roadmap-Status mit Bericht verknüpfen.

## Abschluss und Übergabe

P01 hat zwei getrennte Ergebnisse: **Werkzeug offline abgenommen** und **echter Quellordner inventarisiert**. Ohne tatsächliche Quelle nur das erste als erledigt markieren. P02 übernimmt das Datei-Hashinventar, muss Baugruppenreferenzen aber selbst in einem echten NX-Lauf ermitteln. Keine Bauzustandsgeometrie, Kopie oder bautechnische Freigabe gehört zu P01.
