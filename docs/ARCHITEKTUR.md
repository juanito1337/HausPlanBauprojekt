# Architektur und Einstiegspunkte

## Bestehende G02-Engine

| Pfad ab `projects/g02/` | Verantwortung |
|---|---|
| `00_GESAMTPROJEKT_G02_ERZEUGEN.py` | NX-Journal, Modus ALL; lädt die projektlokalen Pakete kontrolliert. |
| `g02/start.py`, `g02/workflow.py` | Start, Vorprüfung, Moduswahl, Manifeste, Wiederverwendung, Höhenmontage. |
| `g02/nx_backend.py`, `g02/loading.py` | NX-Zugriffe, gezieltes Nachladen, Quellenzustand und neue übergeordnete Montage. |
| `g02/height.py`, `g02/height_model.py` | Rasterbezug, bilineare Höheninterpolation, einmaliger Z-Versatz und Rückleseprüfung. |
| `gesamt/core.py`, `gesamt/nx_backend.py` | Gemeinsame Orchestrierung, Daten-/Dateiprüfung, Verbindung zur Haus-/Umgebungsengine. |
| `gesamt/terrain_audit.py`, `terrain_uv.py`, `terrain_patches.py`, `terrain_boundary.py` | DGM-Sicherung, direkte Oberflächen- und Randkontrollen, gegebenenfalls unterteilte Rasterflächen. |
| `haus/src/haus2406_r03/` | Vorhandener Hauscompiler und NX-Adapter. Der historische Paketname ist beabsichtigt. |
| `haus/src/main01/` | Aktuelle MAIN01-Ausführung und Herkunfts-/Paketprüfung. |
| `haus/data/haus.json` | Parameter, Geometrie, Bauteile, Öffnungen, Quellenstatus. |
| `haus/data/planregister*.json`, `haus/quellen/` | Dokument-IDs und Originalquellen des übernommenen Pakets. |
| `umgebung/r09/` | STEP-Import, Basis-/Intensivprüfungen und Laufzeitprotokolle. Historischer Name bleibt bestehen. |
| `umgebung/data/IMPORTAUFTRAG_R09.json`, `umgebung/CAD_IMPORT/` | Aktive STEP-Auswahl, Referenzpunkte, Prüfsummen und Quelldateien. |
| `data/HOEHENANSCHLUSS_G02.json` | Einzige aktive Höheneinstellung. |
| `data/EINSTELLUNGEN_GESAMT.json` | Ausgabeordner/Prüfmodus; alter `height_connection` bleibt leer. |
| `tests`, `tests_g02`, `haus/tests`, `umgebung/tests` | Unterschiedliche isoliert gestartete Testgruppen. |
| `werkzeuge/PRUEFE_G02_OFFLINE.py` | Aggregierter vorhandener Testlauf; `--cad` für optionale unabhängige CAD-Prüfung. |

Vor einer Änderung die konkreten Importpfade und Modulaufrufe lesen.

## Die Übergabe-Schicht

`tools/repo_support.py` enthält Standardbibliothek-Helfer für Dateihashes, sichere relative Pfade, Syntaxprüfung und ZIP-Ausgabe. `verify_repo.py` prüft die importierten Snapshots und Repository-Dateien. `run_checks.py` startet Tests in getrennten Prozessen, damit historische Paketnamen und Fake-NX-Module sich nicht vermischen. `package_repo.py` exportiert nur einen sauberen, in Git erfassten Arbeitsstand. `extract_k01_reference.py` liest das literal eingebettete JSON der historischen Vorschau ohne JavaScript-Ausführung aus.

## Neue Renovierungsentwicklung

`renovierung/src/` ist **noch kein vorhandener Erzeuger**. Zuerst klare Schnittstellen für Eingangsinventar, unabhängige Kopie, Studienkonfiguration, räumliche Konfliktprüfung, Mengenbilanz und NX-Adapter entwerfen. Geometrische Berechnung möglichst unabhängig von NX halten; NX-Schreibzugriffe getrennt kapseln. Frühere K01-CSV/HTML/PDF dienen als historische Vergleichsdaten, nicht als Ersatz für nachvollziehbare Geometriequellen.

## Warum kein großes Refactoring bei der Übergabe

Die bestehende Engine verwendet relative Dateipfade und mehrere SHA-Register. Eine scheinbar kosmetische Umbenennung kann Startdateien, Quellenzuordnung und Prüfung zugleich brechen. Die Übergabe erhält deshalb den Altbestand einschließlich älterer Unterordner. Deren frühere Starter sind keine Aufforderung, alte Hausstände aufzubauen. Nur die in der aktuellen G02-Anleitung benannten Starter verwenden.
