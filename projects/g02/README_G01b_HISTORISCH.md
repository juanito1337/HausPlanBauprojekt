# NX-Gesamtprojekt G01b – Geländeoberfläche direkt prüfen

**Patch: `MAIN01-A01-G01b-DGM-UVPRUEFUNG`. Vollständiges Paket mit unverändertem Haus MAIN01-A01, Gelände und ausgewählter Vegetation.**

Die neue G01b-Routine ersetzt ausschließlich für das DGM den problematischen Abstand zur gesamten Fläche durch eine direkte Auswertung der tatsächlich importierten Oberfläche. Die Referenzdaten werden weder verschoben noch geglättet. **Kein eigener NX-Lauf: Die neue API-Ausführung in NX 2406 ist noch nicht bestätigt.**

## 1. Für den nächsten Versuch: nur Gelände, automatisch

1. Das gesamte ZIP in einen **neuen beschreibbaren Ordner** entpacken, beispielsweise `C:\NXHaus\G01b`. Nicht mit G01a mischen und nicht nur einzelne Python-Dateien kopieren. Eigene NX-Arbeit sichern; vorhandene Dateien behalten.
2. In NX über den vorhandenen Journalstart **`04_NUR_GELAENDE_MIT_PROTOKOLL.py` im neuen Hauptordner** auswählen. Neben den Startern müssen `gesamt`, `haus`, `umgebung`, `data` und `diagnose` liegen.
3. **Kein Part vorbereiten, keine STEP-Datei suchen und kein separates Diagnosejournal starten.** Der 04-Starter findet die mitgelieferte Quelle, erzeugt ein neues Millimeter-Part mit eindeutiger Laufkennung, importiert, sichert den ungeprüften Stand, prüft und speichert das Ergebnis.

Der 04-Starter baut **kein Haus und keine Vegetation** auf und schließt/speichert keine fremden Nutzermodelle. Ein altes Geländeteil muss nicht gelöscht werden. Durch den eindeutigen neuen Dateinamen werden Namenskonflikte mit früheren DGM-Einzelversuchen vermieden. Ein aktiver Kernelaufruf hat keinen garantierten Timeout.

Nach einem erfolgreichen Gelände-Einzeltest ist das Ergebnis ein separat gespeichertes Geländeteil, noch keine vollständige Umgebungs- oder Projektbaugruppe. Nicht gleichzeitig einen zweiten Erzeuger starten.

## 2. Was die jetzige Diagnose tatsächlich zeigt

Quelle ist der hochgeladene Bericht `STARTFEHLER_G01a_20261011_124825_69a57d5d.json` aus NX 2406.0.0.8100. Die Quelle war vorhanden und hashgleich. Ein Flächenkörper mit einer Einzelfläche wurde importiert; die ungeprüfte Importkopie wurde erfolgreich gespeichert.

Die bisherige Routine meldet beim Innenpunkt 1089 **10.003,641060 mm** und bei 84/85 ungefähr **1.000,049994 mm**. Alle **23 numerischen Rückgaben** der Zusatzdiagnose stimmen rechnerisch mit dem Abstand zum **Außenrand der unveränderten Quellfläche** überein; die Zielkoordinaten liegen ebenfalls dort. Die acht Versuche mit Startschätzung liefern NX-Fehler **821014**.

Das widerlegt nicht die gesamte importierte Innenfläche und beweist keinen allgemeinen NX-Fehler. Es ist ein konkretes Muster dieses Aufrufs an dieser Quelle. Die frühere Vermutung eines lediglich wiederverwendeten Nachbarpunkts wird damit durch die präzisere Randzuordnung ersetzt. Die hochgeladenen Archive `diagnose.zip` und `berichte.zip` enthalten Code beziehungsweise frühere Prüfberichte, **keine native importierte .prt-Datei**.

[Nachrechnung mit Koordinaten](berichte/NX_RANDAUSWERTUNG_G01b.json) · [Inventar der Diagnosearchive](berichte/UPLOAD_INVENTAR_G01b.json)

## 3. Neue Prüfung – nicht nur Fehler unterdrücken

Die normale DGM-Innenprüfung ruft `AskMinimumDist` nicht mehr auf Körper oder Face auf. Stattdessen:

- Ein neuer offener Körper, genau eine rechteckige Face, vier Randkanten, richtiges Eigentümer-Part, Einheiten und Begrenzungsbox werden geprüft.
- Die tatsächlichen UV-Parametergrenzen und vier Eckpositionen werden aus NX gelesen. Nur eine Achsenvertauschung beziehungsweise Richtungsumkehr wird zugelassen. Es gibt keine Lage-/Skalierungsanpassung und keine Wahl einer anderen Abbildung je Prüfpunkt.
- **Alle 16.748 Originalknoten und Zellmittelpunkte** werden über `Modeling.EvaluateFace(..., 0, [u,v]).SrfPos` direkt ausgewertet. Die früher beanstandeten Punkte werden zuerst geprüft. Jede zurückgegebene Position muss innerhalb der unveränderten Grenze von **0,25 mm** zum Quellpunkt liegen.
- Damit die Trägerfläche nicht mit einer beliebig getrimmten Face verwechselt wird, folgen zusätzlich **736 Randproben an den vier tatsächlichen NX-Kanten**, deren Endpunkte eindeutig zugeordnet sein müssen. Nur hier wird `AskMinimumDist` verwendet, ausdrücklich auf **Edge-Tags**.
- Eine zusätzliche Gegenprobe oberhalb des Geländes darf nicht als passend akzeptiert werden.

Die Routine verarbeitet die ausdrücklich festgelegte Originalfläche mit **102 × 83 Stützstellen** und bilinearer Zwischenfläche. Unerwartete Teilung, zusätzliche Trimmung, unpassende Parametrisierung, API-Fehler oder abweichende Koordinaten stoppen den Lauf. Das ist ein endlicher Koordinaten-/Randvergleich, kein universeller Flächengleichheitsbeweis und keine Bestandsvermessung. Quelldaten ersetzen niemals eine fehlgeschlagene NX-Rückgabe.

**Keine Höhendaten, STEP-Flächen, Einheiten oder Toleranzen wurden passend gerechnet.** Die Prüfung verändert keine Geometrie. Weder ein Zehn-Meter-Versatz noch ein Grenzwert von zehn Metern wird verwendet.

Im Standard `BASIS` entfällt weiterhin die teure Flächenintegration. G01b prüft beim DGM trotzdem alle 16.748 festgelegten Referenzpunkte; für die Vegetationsflächen bleiben die bisherigen BASIS-Stichproben aktiv. `INTENSIV` fordert zusätzlich beim DGM die bisherige Flächenmessung an und kann wieder erheblich mehr Zeit benötigen. Die direkte Auswertung kann günstiger sein als eine iterative Nahpunktsuche; eine NX-Laufzeit oder Beschleunigung wurde hier nicht gemessen.

## 4. Protokolle und gespeicherte Dateien

Der neue Gelände-Einzelordner heißt `ausgabe/G01b_GELAENDE_<Zeit>_<Kennung>/`. Die wichtigsten Dateien:

| Datei | Inhalt |
|---|---|
| `GELAENDE_PROTOKOLL_G01b.json` | Quelle, Import, ungeprüfte Sicherung, Gesamtstatus und eingebettete direkte Flächenprüfung. |
| `DGM_FLAECHENPRUEFUNG_G01b.json` | Tatsächliche UV-Grenzen, Eckzuordnung, Zähler, Maximalabweichungen und gegebenenfalls genaue Abbruchstelle. |
| `DGM_FLAECHENPUNKTE_G01b.jsonl` | Tatsächliche von NX gelieferte Positionen und rohe Randabfragen. |
| `diagnose_ungeprueft/DGM_UNGEPRUEFTER_IMPORT_G01b.prt` | Importstand vor der Prüfung, ausdrücklich ungeprüft; kein fertiges Gesamtmodell. |
| `01_GELAENDE_G01b_<Kennung>.prt` | Neuer Teilpfad. Erst der finale Prüf-/Speicherstatus im Protokoll weist den abgeschlossenen Lauf aus. |
| `manifest_G01.json`, `LAUFSTATUS_G01b.json` | Übergeordneter Ablauf. Einige interne G01/R11a-Feldnamen bleiben aus Kompatibilitätsgründen erhalten. |

Die Punktprotokollierung ist gepuffert. Vor/nach Blöcken von höchstens 128 Abfragen werden Status und Puffer geschrieben, nicht Tausende vollständige JSON-Berichte einzeln über ein Netzlaufwerk. Bei einem harten Hängen/Prozessende ist der letzte abgeschlossene Block bekannt, aber nicht garantiert jede noch ungepufferte Einzelabfrage. Ein leerer `STOP_R11a.txt` im aktiven Gelände-Laufordner fordert einen Stopp zwischen den Blöcken beziehungsweise NX-Aufrufen an, keinen harten Kernelabbruch.

Bei einem behandelten Fehler entsteht `fehlerberichte/STARTFEHLER_G01b_….json` mit eingebetteten Befunden unter `nx_terrain_uv_g01b` und dem aus Kompatibilitätsgründen beibehaltenen Feld `nx_terrain_audit_g01a`. **Keine zusätzlichen 31 Wiederholungen der bereits ungeeigneten Methode nach einem UV-Fehler.**

## 5. Gesamtes Projekt bleibt enthalten

`00_GESAMTPROJEKT_ERZEUGEN.py`: aktuelles Haus zuerst, dann Umgebung, anschließend Projektbaum. `01_NUR_HAUS_ERZEUGEN.py`: Haus ohne STEP. `02_NUR_UMGEBUNG_ERZEUGEN.py`: vollständige Umgebung ohne Haus-Neuaufbau. `03_GESPEICHERTE_TEILE_ZUSAMMENSTELLEN.py`: bereits vollständig gespeicherte, unveränderte Läufe dieses Paketordners zusammenstellen. `04_NUR_GELAENDE_MIT_PROTOKOLL.py`: oben beschriebener Gegencheck.

Der 04-Test schreibt bewusst keinen Verweis auf eine vollständig erstellte Umgebung. Für deren Erzeugung ist danach der 02-Starter vorgesehen. Die Gesamt-/Umgebungsstarter haben weiterhin einen Namensschutz gegen gleichzeitig geladene gleichnamige Projektteile. Manuelle Änderungen früherer Parts werden bei einem Neuaufbau nicht übernommen. Das bereits gesicherte Haus behalten.

Haus MAIN01-A01 mit **15 Komponenten und 1.418 Körperaufträgen**, DGM und Vegetation V01/V02/V03/V05 sowie Leitungsplanreferenzen bleiben unverändert. Das Haus und die Umgebung bleiben ohne belegten Höhenanschluss im Quellbezug ungefähr 30 m getrennt. Zehn Haus-Anbau-Überschneidungspaare, zwei teilweise blockierte Innentüröffnungen, fehlende Statik und unbekannte Leitungstiefen bleiben offen. Die Geländeprüfung macht daraus keinen Bau-/Tragwerks- oder Bestandsnachweis.

## 6. Prüfstatus

**522 Offline-/Simulationstests bestanden: 486 bestehende plus 36 neue G01b-Prüfungen.** Den tatsächlich ausgeführten Stand zeigt `berichte/TESTPROTOKOLL_G01b.txt` beziehungsweise `berichte/ERGEBNIS_G01b.json`.

Zusätzlich wird der echte STEP-Import in Open CASCADE mit demselben neuen Python-Prüfpfad geprüft: 16.748 Referenzpunkte, 736 tatsächliche Kantenabstände und eine absichtlich um 2 mm veränderte Innenstützstelle, die korrekt zum Abbruch führen muss. Das testet die CAD-Quelle und den Vergleich, **nicht den NX-Importer oder die NX-Python-Bindings**. Die übrigen unabhängigen Haus-/STEP-Checks bleiben enthalten.

[Technischer Prüfbericht](PRUEFBERICHT_G01b.html) · [Unveränderte Quelldateien](berichte/QUELLGEOMETRIE_UNVERAENDERT_G01b.json)

Offline, nicht in NX: `python werkzeuge/PRUEFE_GESAMTPAKET_G01.py --out NEUER_ORDNER --cad`. Für diese zusätzlichen Offline-CAD-Checks werden OCP/cadquery benötigt. **Der NX-Journallauf benötigt keine nachzuinstallierenden Python-Pakete.**

Die älteren G01/G01a-Berichte und Diagnoseskripte bleiben historische Nachweise. Die neuen Implementierungsdateien liegen im Ordner `gesamt`; die Originale unter `haus` und `umgebung` sind bytegleich übernommen. Keine fertigen, hier neu erzeugten nativen NX-Dateien im Lieferpaket.
