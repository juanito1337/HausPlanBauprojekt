# Gesamtprojekt G01 — Haus MAIN01-A01, Gelände und Vegetation

**Ein vollständiges Lieferpaket. Hausstand: MAIN01-A01. Umgebung: unveränderte Quelldaten und Laufzeitkorrekturen aus R11a.**

Dieses Paket vereinigt die zuletzt getrennten Erzeugungswege. Es ersetzt weder die fehlende Statik noch ein Bestandsaufmaß. **Kein eigener NX-2406-/Parasolid-Lauf. Keine fertigen `.prt`-Dateien enthalten.** Die nativen NX-Dateien entstehen erst in deiner Installation.

## 1. Eindeutiger Gesamtstart

Das gesamte ZIP in einen **neuen, kurzen, beschreibbaren Ordner** entpacken, zum Beispiel `C:\NXHaus\Gesamt_G01`. Nicht mit alten Paketen mischen. Neben den vier Startern müssen `gesamt`, `haus`, `umgebung`, `data` und `diagnose` liegen. Die alten Dateien auf der Festplatte behalten.

Eigene NX-Arbeit speichern. Bereits geladene gleichnamige Haus-/Umgebungsteile nach dem Sichern manuell schließen; bei Unsicherheit NX neu starten. Ausblenden ersetzt Schließen nicht.

In NX über **Journal abspielen / Play Journal** im **Hauptordner** auswählen:

| Starter | Aufgabe |
|---|---|
| **`00_GESAMTPROJEKT_ERZEUGEN.py`** | Aktuelles Haus zuerst, anschließend Gelände und ausgewählte Vegetation; danach neue Projektbaugruppe mit separaten Leitungsplanreferenzen. |
| `01_NUR_HAUS_ERZEUGEN.py` | Nur Haus MAIN01-A01. **Kein STEP-Import und keine Geländeprüfung.** |
| `02_NUR_UMGEBUNG_ERZEUGEN.py` | Nur Gelände, Vegetation V01/V02/V03/V05 und Kartenreferenzen. Kein Haus-Neuaufbau. |
| `03_GESPEICHERTE_TEILE_ZUSAMMENSTELLEN.py` | Bereits erfolgreich erzeugte G01-Haus- und Umgebungsdateien erneut zusammenstellen. **Kein Haus-Neuaufbau, kein STEP-Import.** |

**Nicht die historischen Starter im Unterordner `umgebung` verwenden.** Sie sind nur als unveränderte, prüfbare Bestandteile der älteren Engine vorhanden. Der neue Gesamtstarter ruft ausschließlich MAIN01-A01 für das Haus und ausdrücklich `ENVIRONMENT`/`build_house=false` für die Umgebung auf. Dadurch wird der Hausstand nicht auf R11 zurückgesetzt.

Beim einzigen Haus-Freigabedialog bedeutet **Ja** das Modell mit dokumentierten Näherungen; **Nein** nur das Referenzgerüst ohne Hauskörper. Ein Referenzlauf ist kein vollständiges Hausmodell. Kein separates CHECK-Journal starten und keine Ergebnis-JSON selbst anlegen.

## 2. Was zusammenkommt

- **Haus MAIN01-A01:** 15 Komponenten, im unveränderten Näherungs-Datensatz 1.418 Körperaufträge. Fenster-/Videostand, Balkon rechts aus Straßensicht, Balkonzugang, Kellerabgang-Geländer, zwei Fallrohrreferenzen, Dachfenster und Solarfelder. Hauptdach 45°, ehemaliges Schwimmhallendach 28°; hintere Gaubenanschlüsse rechnerisch geschlossen. Die geschätzten Gaubenwinkel, Garagendachneigung, übrigen Näherungen und Quellen bleiben ausdrücklich gekennzeichnet.
- **Umgebung:** Terrainfläche aus dem DGM und die unveränderten Gruppen V01, V02, V03 und V05. Zusammen 115 offene Flächenkörper in fünf Quelldatenteilen; dazu ein eigenes Teil mit 601 Kartenliniensegmenten. Das sind keine 115 Bäume und kein Bodenvolumen. Andere frühere Vegetationsgruppen bleiben als STEP-Quellen erhalten, werden aber nicht automatisch importiert.
- **Leitungsplanreferenzen:** 25 historische Trassenstücke / 45 Liniensegmente in vier Sparten-Komponenten. Eigene Masterbaugruppe, im Gesamtprojekt zunächst ausgeblendet. Sie bleiben auf Z=0 als reine Zeichenprojektion, **keine tiefenrichtig eingebauten Leitungen**. Alle R09a-Tiefenhinweise werden als Attribute übernommen; weder Regelüberdeckungen noch DN werden in erfundene Isttiefe/Außendurchmesser umgerechnet.

Vorgesehener Baum nach erfolgreichem Gesamtstart ohne Höhenanschluss:

```text
PROJEKT_MASTER_G01_HOEHENBEZUG_OFFEN.prt
├── HAUS_MASTER.prt                         (MAIN01-A01)
├── UMGEBUNG_MASTER_R09.prt                  (DGM + V01/V02/V03/V05 + Kartenlinien)
└── LEITUNGSPLAN_MASTER_G01.prt              (zunächst ausgeblendet)
```

Die internen Dateinamen R09/MAIN01 sind aus Kompatibilitätsgründen erhalten. Maßgeblich ist der äußere Lieferstand **`MAIN01-A01-G01-GESAMT`**. Es werden weder neuere Hausdaten durch die alten Umgebungs-Hausdaten überschrieben noch alte Daten nachträglich als vermessener Bestand ausgegeben.

## 3. Die bekannte DGM-Punktabweichung ist NICHT nachweislich behoben

Der zuletzt gezeigte R10-Screenshot meldete für DGM-Punkt 85 einen Abstand von etwa **1.000,05 mm** bei einer CAD-Prüfgrenze von 0,25 mm. Die STEP-Quelle ist an dieser Stelle rechnerisch richtig; die Ursache im NX-Import beziehungsweise in der Abstandssuche ist noch nicht entschieden. Die angeforderte NX-Diagnose liegt nicht vor.

**G01 enthält alle bisher implementierten Fixes, aber keine behauptete Korrektur dieses offenen Fehlers.** Dieselbe Basis-Abstandsroutine wird aus R11a übernommen. Auch ein erfolgreicher Stichprobentest beweist nicht, dass eine zuvor beanstandete, nicht geprüfte Stelle richtig ist. Die Prüfung wurde weder durch Null-/Quellwerte ersetzt noch die Toleranz erhöht; keine Geländeverschiebung zur Kaschierung.

Die kleine Diagnose liegt unter `diagnose/DGM_Punkt85/DIAGNOSE_DGM_PUNKT85.py`. Sie ist nur für ein bereits importiertes, unverändertes Geländeteil vorgesehen. Sie startet keinen Haus-Neuaufbau und verändert/speichert keine Parts. Anleitung und ursprüngliche Quellenprüfung liegen daneben.

Scheitert die Umgebung, **bleibt das zuvor erfolgreich gespeicherte und dateigeprüfte Haus bestehen**. Die G01-Fehlermeldung nennt seinen Pfad. Es gibt dann keine Gesamterfolgsmeldung und noch keine vollständige Gesamtbaugruppe. Nicht anschließend blind alle Erzeuger erneut ausführen.

## 4. Höhenbezug — keine optisch passend geratene Montage

Das Haus verwendet EG-Fertigfußboden ±0,00. Die Umgebung bleibt bei **1.000 × Quellhöhe in Metern**. Im gemeinsamen Projektbaum liegen die Daten ohne bestätigten Anschluss daher weiterhin **ungefähr 30 m vertikal getrennt**. Sie sind enthalten, aber nicht physisch an das Haus montiert. Zum Bearbeiten das Haus oder die Umgebung einzeln anzeigen.

In `data/EINSTELLUNGEN_GESAMT.json` stehen deshalb unverändert:

```json
"height_connection": {
  "H_EG_zero_in_source_datum_m": null,
  "source": "",
  "common_vertical_datum_confirmed": false
}
```

Nur mit einer belegten absoluten Höhe des EG-Nullpunkts im gemeinsamen Höhensystem, einer Quellenangabe und ausdrücklicher Bestätigung werden daraus Zahlenwerte. Der Gesamtstarter versetzt dann **die gesamte Umgebung gemeinsam um −1.000 × H_EG**, ohne Rotation/Skalierung und ohne Veränderung der Quellkörper, und erstellt `PROJEKT_MASTER_G01.prt`. Das bleibt eine Nutzerangabe, kein durch das Programm erbrachter Vermessungsnachweis. Die Leitungsplanlinien erhalten dadurch keine physische Tiefenlage.

Beim DGM fehlt der konkrete vertikale Metadatenbeleg weiterhin; bDOM-Metadaten werden nicht ungeprüft darauf übertragen. Vegetationshöhen 2023 und Luftbildzuordnung 2025 bleiben unterschiedliche Datenstände.

## 5. Laufzeit und weitere Arbeit

Standard ist **BASIS** aus R11a: alle Körper nach Anzahl, Art und Begrenzungsbox; zusätzlich verteilte Quellpunkt-Stichproben mit unveränderter 0,25-mm-CAD-Prüfgrenze. 1.312 Abstände für die ausgewählte Umgebung plus 23 im Importtest. **Keine Flächeninhaltsintegration, keine Vollprüfung aller Quellpunkte.** Die Daten werden dabei nicht geglättet, ausgedünnt oder räumlich verschoben. BASIS ist weniger umfassend als INTENSIV.

In `data/EINSTELLUNGEN_GESAMT.json` kann `surface_validation` ausdrücklich auf `INTENSIV` gestellt werden; dann werden die teuren Flächen- und vollständigen Quellpunktprüfungen wieder angefordert. Das kann erneut sehr lange dauern und behebt den Punkt85-Fehler nicht automatisch. Der Pfad zu einer vorhandenen lokalen `step214ug.def` lässt sich bei Bedarf unter `step_settings_file` eintragen. Keine Installations- oder Lizenzdateien werden mitgeliefert/erfunden.

Der Umgebungs-Erzeuger wird ohne die mehrfach verschachtelten alten Projekt-Wrapper aufgerufen; seine Import-/Prüfalgorithmen bleiben unverändert. Das hält die Ausgabepfade kürzer. Die Laufzeitkorrekturen bleiben enthalten: verzögerte Attributaktualisierung, erforderliche Updates vor dem Speichern, reduzierte Informationsfenster-Ausgaben, keine zusätzlichen blockierenden OK-Zwischenmeldungen. Es gibt keinen Hintergrund-Thread mit NX-Zugriff und keinen garantierten Timeout eines laufenden Kernelaufrufs.

**Zum täglichen Weiterarbeiten die gespeicherten `.prt`-Masterdateien öffnen, nicht das Journal erneut starten.** Neue Läufe erstellen neue Ordner; manuelle Änderungen in älteren NX-Dateien werden nicht übernommen.

`03_GESPEICHERTE_TEILE_ZUSAMMENSTELLEN.py` verwendet nur die im aktuellen G01-Paket geschriebenen Verweise `LETZTES_HAUS_G01.json` und `LETZTE_UMGEBUNG_G01.json`. Beide müssen zu vollständig gespeicherten Läufen passen. Alle darin erfassten Dateien werden erneut gegen die Prüfsummen geprüft. Geänderte/manuell gespeicherte Modelle benötigen eine bewusst neu definierte Basis; sie werden nicht als unveränderter Ausgangsstand akzeptiert. Vor dieser Zusammenstellung die beteiligten gespeicherten Teile schließen, damit kein ungespeicherter Speicherstand statt der geprüften Datei verwendet wird. Die Zusammenstellung verändert/speichert die Quellkomponenten nicht.

Beispiel für getrennte Läufe: 01 ausführen, danach 02. Nach beiden Erfolgen beteiligte Teile schließen, dann 03 ausführen. Bei einem erfolgreichen 00-Gesamtstart ist 03 nicht zusätzlich nötig.

**Den gesamten Ausgabeordner und die abhängigen Komponenten sichern.** Nur eine Masterdatei zu kopieren erzeugt kein unabhängiges Modell. Die Ergebnisverweise enthalten absolute Pfade; bei späterem Umzug des Projekts müssen Dateireferenzen bewusst neu zugeordnet und geprüft werden. Nicht nur die Verweisdateien aus einer alten Version kopieren.

## 6. Ausgabe und Fehlerdiagnose

Unter `ausgabe/G01_<Zeit>_<Kennung>/` liegen die Teilläufe und die Projektdatei. Der Hauslauf verwendet eine unveränderte Quellkopie in `eingaben_haus`, lediglich der Ausgabeordner wird in der kopierten Konfiguration gesetzt.

- `manifest_G01.json` und `LAUFSTATUS_G01.json`: Gesamtphase, Pfade gespeicherter Ergebnisse, getrennter fachlicher Prüfstatus.
- `haus/HAUS_…/LAUFSTATUS_MAIN01.json` und `LAUFZEIT_MAIN01.jsonl`: detaillierter Hausfortschritt.
- `umgebung/LAUFSTATUS_R11a.json` und `LAUFZEITPROFIL_R11a.jsonl`: detaillierter Umgebungsfortschritt. Darunter liegen die jeweiligen Importberichte.

Ein leerer `STOP_MAIN01.txt` im konkreten Hauslaufordner beziehungsweise `STOP_R11a.txt` im konkreten Unterordner `umgebung` des G01-Laufs fordert einen Stopp **zwischen** NX-Aufrufen an. Ein bereits laufender Kernelaufruf muss zunächst zurückkehren.

Bei Abbruch: den neuen `STARTFEHLER_G01_…json` und `manifest_G01.json` aus demselben Lauf aufbewahren; bei einem DGM-Abbruch zusätzlich den Importbericht und gegebenenfalls die kleine Punktdiagnose. Ein unveränderter Status-Zeitstempel während eines einzelnen NX-Aufrufs ist kein sicherer Absturznachweis.

## 7. Was dieses Gesamtpaket nicht behauptet

**Keine neue Dachstatik und kein vollständig konstruiertes Dachtragwerk.** Die tatsächlichen Sparren-, Pfetten-, Binder- und Verbindungsdaten fehlen weiter. Zehn bekannte Haus-Anbau-Überschneidungspaare, zwei teilweise blockierte Innentüröffnungen, unbestätigte Flachdachdetails und weitere Bestandsannahmen bleiben offen. Der Benutzer muss keine dieser Lücken als gelöst akzeptieren, um die bekannten Teile weiterzubearbeiten.

Das Paket enthält keine bestätigten Leitungstiefen, keinen absteckbaren Grenznachweis, kein vollständiges Bauminventar und keine Ausführungs-/Tragwerksfreigabe. **„Komplettes Paket“ heißt: alle benötigten Erzeugungsdateien und vorhandenen Modellbereiche sind zusammen geliefert — nicht: jeder Befund am Haus ist abschließend bestätigt.**

## 8. Nachweise

`PRUEFBERICHT_G01.html` und `berichte/ERGEBNIS_G01.json` dokumentieren die aktuelle Prüfung. Die 87 Haus- und 291 übernommenen Integrationsprüfungen sowie 58 neue G01-Tests prüfen Python/Daten/Simulation, nicht den NX-Kern. Die vollständige kombinierte Simulation verwendet dieselben Engine-Aufrufe mit künstlichen NX-Antworten. Unabhängige Open-CASCADE-Prüfungen der realen Quelldateien sind gesondert ausgewiesen. Kein gemessener NX-Laufzeitgewinn und keine Garantie eines fehlerfreien NX-Imports.

Vorschauen: `haus/VORSCHAU_HAUS.html`, `umgebung/VORSCHAU_UMGEBUNG_R11.html`. Sie zeigen die berechneten Quelldaten, keinen eigenen NX-Lauf. Die im Unterordner `umgebung` verbliebenen Berichte und Haus-Helfer beziehen sich auf ältere Stände; sie steuern nicht das hier gelieferte aktuelle Haus.

© GeoBasis-DE/LVermGeo SH/CC BY 4.0 für die übernommenen Geobasisdaten; Ausschnitte und CAD-Ableitungen aus den Nutzerdaten. Weitere Quellen-/Zeitstandsangaben bleiben in den jeweiligen Bausteinen erhalten.
