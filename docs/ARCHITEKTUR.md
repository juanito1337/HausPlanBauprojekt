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

`renovierung/m01/` ist der zusätzliche Erzeuger der gemeinsamen Hauptbaugruppe. `layout.py` leitet den Baum aus den gültigen G02/K02-Quellen ab und erhält alle Feld-/Raumregister. `nx_journal.py` erzeugt eigene Kopien der benötigten Blattteile, neue Zwischenbaugruppen und rollenbezogene Referenzsets auf den eigenen Studienparts. Haus und Umgebung werden jeweils einmal montiert. `display.py` behandelt Sichtzustände im vollständigen Masterkontext, `select_state.py` bietet die Feldauswahl im geöffneten Modell ohne Speichern. `runner.py` fordert native Struktur-, Sichtbarkeits-, Quellen- und Volumennachweise pro Feld/Rolle sowie frisches und verschobenes Wiederöffnen. `tools/nx_master.py` ist der öffentliche M01-Einstieg; der getrennte Fingerprint erhält die unveränderten G02/K02-Nachweise. `tools/run_checks.py` verlangt beide Bereiche. M01 ist eine gemeinsame Darstellung der unabhängigen Feldstudien, keine kumulative Baufolge.

`renovierung/k02/` enthält den getrennten K02-Studienerzeuger. `terrain.py` liest das bilineare G02-DGM und erzeugt ein lokal verfeinertes Studien-TIN; `geometry.py` berechnet geschlossene Eingriffs-/Haufenkörper, `materials.py` Volumenäquivalente und `planning.py` das vollständige Feldregister einschließlich gesperrter Bereiche. `mesh_step.py` überträgt die geschlossenen Netze als STEP. Diese Mathematik benötigt kein NXOpen; ihre Tests belegen keine NX-Ausführung.

`runner.py` verbindet den frischen Gesamtplan mit seriellen echten NX-Prozessen. `nx_build.py` klont alle Quellparts mit UFClone in jeden eigenen Zustand, stellt sämtliche Komponentenreferenzen um und erzeugt die Studiengeometrie. `nx_verify.py` öffnet jeden gespeicherten Zustand frisch (AsSaved) und als verschobene Kopie (SearchDirectories); geprüft werden Hashes, vollständiges Laden, mm, interne Pfade, Interpart-Abhängigkeiten, Komponentenlagen und native Körpervolumen. BASE und die unabhängigen Einzelfeldvarianten teilen keine bearbeitbaren Parts. Ein Feld mit mehreren getrennten geschlossenen Aushubkomponenten bleibt mehrteilig.

`tools/nx_project.py build` verwendet eine nach aktuellem G02-Fingerprint gültige Basis wieder oder erzeugt sie einmal neu; anschließend plant und erzeugt es K02 vollständig. Der eigene K02-Fingerprint umfasst Eingaben, Konfiguration, sämtliche K02-Pythonmodule, Integrationstools und den tatsächlichen G02-Nativbestand samt Nachweisen. `check` verlangt gültige G02- und vollständige K02-Nachweise. Ein Pilot oder Fehler darf K02-CURRENT nicht fortschreiben. Historische Nachweise werden nicht umgeschrieben.

Die Felder sind unabhängige Studienalternativen mit höchstens einem offenen Eingriff, keine kumulative Baufolge. `construction_release=false`; bei unbekannten Tiefen oder Umfangsgrenzen bleiben Mengen null. Quellgelände bleibt als geblankte Kopie erhalten, während der lokale geschlossene Studienboden einen künstlichen unteren Abschluss besitzt. Alle 72 Registerverweise liegen ausdrücklich auf Z=0, ohne erfundene Leitungstiefen. Frühere K01-CSV/HTML/PDF bleiben historische Vergleichsdaten. Lieferstand, Mengen und noch offene Sichtprüfung stehen im [K02-Nachweis](entwicklungsstand/K02-native-2026-11-01.md).

## Warum kein großes Refactoring bei der Übergabe

Die bestehende Engine verwendet relative Dateipfade und mehrere SHA-Register. Eine scheinbar kosmetische Umbenennung kann Startdateien, Quellenzuordnung und Prüfung zugleich brechen. Die Übergabe erhält deshalb den Altbestand einschließlich älterer Unterordner. Deren frühere Starter sind keine Aufforderung, alte Hausstände aufzubauen. Nur die in der aktuellen G02-Anleitung benannten Starter verwenden.
