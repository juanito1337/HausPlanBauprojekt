# Prüfprotokoll Keller-Vorplanung V01

Datum: **01.11.2026**. Dokumentationsänderung, kein neuer NX-Erzeuger oder Modelleingang. Zugehöriger [Projektplan](../../../docs/plans/2026-11-01-keller-aushub-und-schachtplanung.md), [Katalog](sektionen.json), [Zeichnungsheft](../../../output/pdf/Keller_Vorplanung_V01.pdf).

## Tatsächlich durchgeführt

| Prüfung | Ergebnis und Grenze |
|---|---|
| Modell-/Quellprüfung | Haupt- und Anbaukeller, EG, Garage, Anschlusskonflikte, Höhen, Medien-/Schachthinweise aus aktivem G02 gelesen. Planwerte, keine Bestandsvermessung. |
| Unabhängiger Superpowers Builder Check | Vorplanungsdokument read-only geprüft; keine wesentlichen offenen Builder-Fragen außerhalb der ausdrücklich vorgesehenen Untersuchungsaufträge. Keine Standsicherheit geprüft/bestätigt. |
| Dokument-/Geometrieprüfung | 13 eindeutige Sektionen; alle 14 äußeren Quellkonturkanten vollständig ohne Lücke/Überlappung zugeordnet. Segmentkollinearität, Stationierung und Längen gegen die Polygone in `haus.json` geprüft. |
| Quellen und Sperren | Drei Quellhashes geprüft; sämtliche `construction_release=false`, keine existierenden neuen Baugruppen behauptet, Arbeitsfelder leer und unbekannte Bemessungswerte `null`. |
| PDF-Struktur | 21 Seiten, davon 13 Sektionsblätter mit A/B und Sperrvermerk; Status auf jeder Seite. Mit pypdf erneut geöffnet und Texte geprüft. |
| PDF-Sichtprüfung | Alle 21 finalen Seiten mit Poppler bei 90 dpi gerendert und visuell kontrolliert; keine abgeschnittenen Inhalte oder überlappenden Texte festgestellt. |
| `python tools/nx_project.py check` | Rückgabecode **0**, PASS: gespeicherter echter NX-Nachweis und native Dateien stimmen mit aktuellen Quellen überein. **Kein neuer NX-Lauf**; vorhandener G02-Lauf vom 31.10.2026 bleibt maßgeblich. |
| `python tools/run_checks.py` | Rückgabecode **0**, Gesamtstatus PASS: Repository-Integrität, Werkzeugtests und nativer Aktualitätsnachweis. 51 Testfälle: 50 bestanden, 1 vorhandener Windows-Symlinktest übersprungen. |
| `git diff --check` | Rückgabecode **0**, keine Whitespacefehler. |

Python: `C:/Users/1337/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

Lokale Rohberichte, nicht versioniert:

- `reports/local/20261101_023117_b375bed9/RESULT.json` und zugehörige `.txt`-Logs.
- `reports/local/20261101_planung/geometrie.json`, `document_check.json`, gerenderte Seiten und Sichtprüfungsbögen.
- Einmalige Dokumentwerkzeuge `author_plan.py` / `check_plan.py` im selben lokalen Ordner; keine Renovierungs-Engine und keine NX-Operationen.

## Lieferdateien

| Datei | SHA-256 |
|---|---|
| `output/pdf/Keller_Vorplanung_V01.pdf` | `ff34db3ff99cf3fd6aeb7950988f407ccba5fccbe450b098e8b6191ffaed7a98` |
| `renovierung/planung/2026-11-01/sektionen.json` (LF-Zeilenenden) | `61c05993677a7b01cdd1809251a68b30305752a159d6e88cf3ca05806ac09ddf` |

Bei Änderung dieser Dateien müssen Hashes und Prüfungen erneuert werden.

## Nicht nachgewiesen

- Keine tatsächliche Fundament-, Boden-, Wasser-, Leitungs- oder Grenzaufnahme. Nutzer bestätigt fehlende belastbare Grundlagen.
- Keine baustatische/geotechnische Bemessung, Ausführungsfreigabe, verbindlichen Aushubmaße, Mengen oder Kosten.
- Keine neu erstellten Renovierungs-Unterbaugruppen oder Schacht-.prt; deren Zielstruktur ist beschrieben. Der G02-Nachweis deckt keine geplanten K02-Funktionen ab.
- Historische vollständige G02-Suite diesmal nicht erneut ausgeführt. Der bereits dokumentierte Windows-Pfadtest `test_r09.CoreTests.test_path_traversal_rejected` bleibt offen; diese Dokumentationsarbeit korrigiert ihn nicht.
- Kein amtlicher Lageplan und keine bestätigte geografische Nordrichtung. Querschnitts-/Schachtschemata sind unbemessen, Lagepläne zeigen Modellkonturen.
