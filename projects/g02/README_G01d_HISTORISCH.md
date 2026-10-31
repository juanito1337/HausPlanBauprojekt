# NX-Gesamtprojekt G01d – Gelände mit explizitem Rasterrand

**Patch: `MAIN01-A01-G01d-EXAKTER-RASTERRAND`. Vollständiges Paket.**

Haus MAIN01-A01, vorhandene Höhenpunkte, Gelände-Trägerfläche und Vegetationsauswahl bleiben erhalten. Neu ist die **STEP-Randdarstellung des Geländes**: 366 gerade LINE-Abschnitte zwischen den vorhandenen Rand-Rasterpunkten statt vier langer stückweise linearer B-Spline-Randkurven. Die aktive STEP-Datei und ihre Prüfsumme haben sich damit geändert. Die Originaldatei bleibt unverändert im Paket.

**Kein eigener NX-/Parasolid-Lauf dieser Variante; keine fertigen hier erzeugten `.prt`-Dateien.**

## 1. Jetzt nur das Gelände prüfen – kein Hausneuaufbau

1. Das **gesamte ZIP in einen neuen Ordner** entpacken, beispielsweise `C:\NXHaus\G01d`. Nicht mit G01c mischen und keine einzelne Datei in ältere Pakete kopieren. Eigene NX-Arbeit sichern; bisherige Dateien behalten.
2. In NX über „Journal abspielen / Play Journal“ **`04_NUR_GELAENDE_MIT_PROTOKOLL.py` aus dem neuen Hauptordner** auswählen. Daneben müssen `gesamt`, `haus`, `umgebung`, `data` und `diagnose` liegen.
3. **Kein Teil anlegen, keine STEP-Datei suchen und kein separates CHECK-/Diagnosejournal starten.** Der Starter importiert die mitgelieferte neue Quelle, sichert den ungeprüften Importstand, prüft und speichert bei Erfolg das Ergebnis.

Der 04-Starter erzeugt ein neues Millimeter-Teil mit eindeutiger Laufkennung. Er verändert weder das vorhandene Haus noch andere geladene Nutzermodelle. Ein erfolgreicher Gelände-Einzeltest ist **noch keine vollständige Umgebung oder Gesamtbaugruppe**.

## 2. Was der neue Nutzerbericht tatsächlich nachweist

Quelle: `STARTFEHLER_G01c_20261012_121659_75b4ef58.json`.

- Alle **16.748** festgelegten Rasterknoten/Zellmittelpunkte wurden direkt über die importierte NX-Trägerfläche ausgewertet. Maximale numerische Abweichung: **7,0711 × 10⁻⁸ mm**. Das ist kein Genauigkeitsnachweis des realen Geländes.
- Die Endpunkte der **285** NX-Kanten sind vier Seiten zugeordnet: **82 / 1 / 101 / 101** Kanten. Eine Seite ist als einzelne, etwa 82 m lange Kante erhalten geblieben.
- Bei Randprobe **417** an Kante **64439**, Seite **R1**, liefert die Abfrage **0,2637268145 mm** bei einer Prüfgrenze von **0,25 mm**. Die Überschreitung beträgt **0,0137268145 mm**. Bis dahin wurden 418 von 1.591 Randproben abgefragt; der restliche Rand ist durch diesen Lauf nicht geprüft.

Die tatsächliche NX-Zielkoordinate liegt nach unabhängiger Quellenrechnung ca. **0,2634566 mm** neben der ursprünglichen exakten Randkurve. Der Bericht allein entscheidet nicht, ob die importierte 3D-Kante abweicht oder die Nahpunktsuche ungenau auswertet. **Weder ein allgemeiner NX-Fehler noch eine vollständige Korrektur durch G01d ist damit bereits bewiesen.**

## 3. Was geändert wird – und was gleich bleibt

Aktive neue Quelle:

```text
umgebung/CAD_IMPORT/GELAENDE_G01d_EXAKTER_SEGMENTRAND.step
```

Historische Originalquelle, weiterhin bytegleich:

```text
umgebung/CAD_IMPORT/GELAENDE_R07_UNVERAENDERT.step
```

Die neue Datei enthält dieselbe bilineare Fläche: gleiche Grade, Knoten, Vielfachheiten, Gewichte und **alle 8.466 Stützpunkte exakt unverändert**. Nur die Randkurven-/Kantenbeschreibung wird explizit in die vorhandenen linearen Rasterintervalle zerlegt. Es entsteht **kein Dreiecksnetz, keine Glättung, keine Geländeverschiebung und keine neue Rasterausdünnung**. Die Quelle besitzt weiterhin eine Face und eine geschlossene äußere Begrenzung.

**Die 0,25-mm-Prüfgrenze bleibt unverändert.** Es gibt keinen neuen NX-API-Aufruf und keinen Ersatz eines NX-Ergebnisses durch Quellkoordinaten. Der bestehende G01c-Kettenprüfer bleibt aktiv und muss alle tatsächlich importierten Kanten zuordnen. Die Anzahl allein ist kein Freigabekriterium.

Vorgesehen sind weiterhin **16.748 direkte Flächenpunktvergleiche** und **736 Originalrandproben plus drei Proben je tatsächlich importierter Kante**. Bei 366 Kanten sind das 1.834 Randabfragen. Falls NX anders segmentiert, zählt der Prüfer die tatsächlich importierten Kanten. Tatsächliche Abweichungen, Lücken oder nicht passende Trimmungen stoppen den Lauf weiterhin.

## 4. Protokolle und Sicherung

Ausgabe des Einzeltests unter `ausgabe/G01d_GELAENDE_<Zeit>_<Kennung>/`:

| Datei | Inhalt |
|---|---|
| `GELAENDE_PROTOKOLL_G01d.json` | Tatsächlicher Quellpfad und neue Prüfsumme; Import, Sicherung und Prüfstatus. |
| `DGM_FLAECHENPRUEFUNG_G01d.json` | Flächenpunkt- und Randprüfung getrennt; Kantenendpunkte, Zuordnung, Maximalabweichungen. |
| `DGM_FLAECHENPUNKTE_G01d.jsonl` | Tatsächliche NX-Flächenpositionen und Randabfragen, blockweise protokolliert. |
| `diagnose_ungeprueft/DGM_UNGEPRUEFTER_IMPORT_G01d.prt` | Ungeprüfter Importstand; keine automatische Verwendung als fertige Umgebung. |
| `01_GELAENDE_G01d_<Kennung>.prt` | Das neue Teil. Abschließenden Speicher-/Prüfstatus im Bericht beachten. |
| `manifest_G01.json`, `LAUFSTATUS_G01d.json` | Ablauf und Speicherstatus. |

Bei einem behandelten Abbruch entsteht **`STARTFEHLER_G01d_….json`** mit eingebetteter Geländediagnose. Diese Datei genügt zunächst für die nächste Auswertung. Ein einzelner laufender nativer NX-Aufruf hat weiterhin keinen garantierten Timeout. Die leere Datei `STOP_R11a.txt` im aktuellen Gelände-Ausgabeordner fordert einen Stopp zwischen den Aufrufen an.

## 5. Gesamtmodell und spätere Verwendung

Alle fünf Starter bleiben im Paket. `00_GESAMTPROJEKT_ERZEUGEN.py` erzeugt Haus und Umgebung; `01_NUR_HAUS_ERZEUGEN.py` nur das aktuelle Haus; `02_NUR_UMGEBUNG_ERZEUGEN.py` Umgebung ohne Hausneuaufbau; `03_GESPEICHERTE_TEILE_ZUSAMMENSTELLEN.py` die gespeicherten erfolgreichen Läufe dieses Pakets. **Auch 00 und 02 verwenden den neuen DGM-Importauftrag automatisch.**

Für den aktuellen Gegencheck genügt **04**. Ein alter Hauslauf muss nicht wiederholt werden. Keine vorhandenen Dateien werden gelöscht, alte manuelle Änderungen aber auch nicht automatisch auf einen Neuaufbau übertragen. Alte Ergebnisverweise nicht einfach aus anderen Paketordnern kopieren.

Ohne belegten Höhenanschluss bleiben Haus (EG ±0,00) und Umgebung (Quellhöhen) höhenmäßig getrennt. Fehlende Tragwerksangaben, zehn bekannte Haus-Anbau-Überschneidungspaare, zwei teilweise blockierte Innentüröffnungen und unbekannte Leitungstiefen bleiben offen. Die Änderung betrifft den Geländeexport, keine neue Bestands- oder Tragwerksfreigabe.

## 6. Prüfung und Nachvollziehbarkeit

**Alle 588 Offline-/Simulationstests bestehen, darunter 24 neue gezielte Prüfungen.** Die reale CAD-Prüfung vergleicht Original und neue STEP nach Rückimport in Open CASCADE, einschließlich aller Stützpunkte, Randlinien und der aktiven Prüfstrecke. Eine tatsächlich um 2 mm veränderte innere Stützstelle wird weiterhin zurückgewiesen. **Simulationen sind keine echten NX-Läufe.**

Aktuelle Nachweise: `PRUEFBERICHT_G01d.html`, `berichte/DGM_LINIENRAND_QUELLPRUEFUNG_G01d.json`, `berichte/NX_BEFUND_G01c_RAND417.json` und `berichte/TESTPROTOKOLL_G01d.txt`. G01–G01c-Berichte und ältere Dateien unter `umgebung` sind historische Nachweise, keine neue Prüfung dieser Revision.

Offline, nicht in NX:

```text
python werkzeuge/PRUEFE_GESAMTPAKET_G01.py --out NEUER_TESTORDNER --cad
```

Die optionalen Offline-CAD-Prüfungen benötigen OCP/cadquery. **Im NX-Journal keine zusätzlichen Python-Pakete installieren.** Der Offline-Exporter `werkzeuge/ERZEUGE_DGM_SEGMENTRAND_G01d.py` ist zur Reproduzierbarkeit beigelegt, nicht zur Ausführung in NX. Der Journallauf verwendet die fertige mitgelieferte STEP-Datei.

© GeoBasis-DE/LVermGeo SH/CC BY 4.0. Quelldatenstände und Geobasis-Lizenzhinweise bleiben erhalten.
