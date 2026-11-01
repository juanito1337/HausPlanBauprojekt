# K02 / 31dba74 – erneut geprüfter CAD-Revisionsstand

**Journalablauf: PASS, Exit 0.** Der unveränderte Quellstand `31dba74270dc87a76beb6618699dfc1df6624bad` wurde erneut vollständig für K02 ausgeführt. Die gültige G02-Basis wurde wiederverwendet; sämtliche K02-Zustände wurden frisch erzeugt und gespeichert.

Speicherordner: `k02/20261101T191747_4adeb5/`. Modellrevision **K02**, Quellrevision **31dba74**, Lauf **20261101T191747_4adeb5**. Die Quellrevision bezeichnet den geprüften Code-/Eingabestand, nicht den späteren Commit dieser neuen Ausgabedateien.

**23 Zustände / 689 native NX-Dateien:** Renovierungsbasis und 22 unabhängige Feldvarianten. Jeder Zustand hat Erzeugung, frisches AsSaved-Öffnen und Öffnen einer verschobenen Kopie mit SearchDirectories bestanden. Der neue Gesamtplan wurde frisch berechnet. Mengen, Status und native Körpermessungen stimmen mit der vorherigen Lieferung derselben Modellrevision überein.

[Revisionsnachweis](k02/20261101T191747_4adeb5/REVISION_K02_31dba74.json) · [Bauergebnis](k02/20261101T191747_4adeb5/BUILD.json) · [Wiederöffnungsnachweis](k02/20261101T191747_4adeb5/VERIFY.json)

## Modelle öffnen

In einer frischen NX-Sitzung öffnen, wie im Prüflauf. Die komplette jeweilige Baugruppe mit allen Komponenten im Zustandsordner beibehalten. [NX-Ladeanleitung](README.md). Die neuen Dateien wurden direkt im Hauptprojektordner gespeichert; nach einem Umzug gelten die dokumentierten Suchpfade.

| Zustand | NX-Master |
|---|---|
| BASE | [BASE_21.prt](k02/20261101T191747_4adeb5/BASE/BASE_21.prt) |
| PS01-F01 | [PS01-F01_21.prt](k02/20261101T191747_4adeb5/PS01-F01/PS01-F01_21.prt) |
| PS01-F02 | [PS01-F02_21.prt](k02/20261101T191747_4adeb5/PS01-F02/PS01-F02_21.prt) |
| PS01-F03 | [PS01-F03_21.prt](k02/20261101T191747_4adeb5/PS01-F03/PS01-F03_21.prt) |
| PS01-F04 | [PS01-F04_21.prt](k02/20261101T191747_4adeb5/PS01-F04/PS01-F04_21.prt) |
| PS01-F05 | [PS01-F05_21.prt](k02/20261101T191747_4adeb5/PS01-F05/PS01-F05_21.prt) |
| PS01-F06 | [PS01-F06_21.prt](k02/20261101T191747_4adeb5/PS01-F06/PS01-F06_21.prt) |
| PS01-F07 | [PS01-F07_21.prt](k02/20261101T191747_4adeb5/PS01-F07/PS01-F07_21.prt) |
| PS01-F08 | [PS01-F08_21.prt](k02/20261101T191747_4adeb5/PS01-F08/PS01-F08_21.prt) |
| PS01-F09 | [PS01-F09_21.prt](k02/20261101T191747_4adeb5/PS01-F09/PS01-F09_21.prt) |
| PS01-F10 | [PS01-F10_21.prt](k02/20261101T191747_4adeb5/PS01-F10/PS01-F10_21.prt) |
| PS01-F11 | [PS01-F11_21.prt](k02/20261101T191747_4adeb5/PS01-F11/PS01-F11_21.prt) |
| PS04-F02 | [PS04-F02_21.prt](k02/20261101T191747_4adeb5/PS04-F02/PS04-F02_21.prt) |
| PS06-F01 | [PS06-F01_21.prt](k02/20261101T191747_4adeb5/PS06-F01/PS06-F01_21.prt) |
| PS06-F02 | [PS06-F02_21.prt](k02/20261101T191747_4adeb5/PS06-F02/PS06-F02_21.prt) |
| PS06-F03 | [PS06-F03_21.prt](k02/20261101T191747_4adeb5/PS06-F03/PS06-F03_21.prt) |
| PS07-F01 | [PS07-F01_21.prt](k02/20261101T191747_4adeb5/PS07-F01/PS07-F01_21.prt) |
| PS07-F02 | [PS07-F02_21.prt](k02/20261101T191747_4adeb5/PS07-F02/PS07-F02_21.prt) |
| PS09-F03 | [PS09-F03_21.prt](k02/20261101T191747_4adeb5/PS09-F03/PS09-F03_21.prt) |
| PS09-F04 | [PS09-F04_21.prt](k02/20261101T191747_4adeb5/PS09-F04/PS09-F04_21.prt) |
| PS09-F05 | [PS09-F05_21.prt](k02/20261101T191747_4adeb5/PS09-F05/PS09-F05_21.prt) |
| PS09-F06 | [PS09-F06_21.prt](k02/20261101T191747_4adeb5/PS09-F06/PS09-F06_21.prt) |
| PS09-F07 | [PS09-F07_21.prt](k02/20261101T191747_4adeb5/PS09-F07/PS09-F07_21.prt) |

## Umfang der Prüfung

Start über `python tools/nx_project.py build --nx-root C:/Siemens/NX2406 --accept-model-assumptions`; dieser Starter führt die NX-Journale mit den erforderlichen Auftragsdateien über `run_journal.exe` aus. `renovierung/k02/nx_build.py` ist kein selbstständiges Journal zum Start ohne Auftragsdaten.

Die bestehende [Mengenübersicht](../../renovierung/planung/2026-11-01/K02_STUDIE.md) bleibt der Mengen-/Annahmenbericht der geometrisch gleichen Erstlieferung; ihre Modelllinks führen zum dort ausdrücklich genannten früheren Lauf. Die Tabelle oben führt ausschließlich zur neuen Speicherung.

**Offen:** grafische NX-Sicht-/Bedien-/Kameraprüfung. Dieser Lauf bestätigt die native Erzeugung und das Wiederöffnen, keine grafische Abnahme oder Bauausführungsfreigabe. Bestehende fachliche Grenzen und der historische G02-Windows-Testfehler bleiben unverändert.
