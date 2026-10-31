# HAUS MAIN01 – erste Haus-Arbeitsbasis

**Ein Starter: `00_HAUS_MAIN01_ERZEUGEN.py`. Nur Haus, kein STEP-Import, kein Gelände, keine Vegetation.**

MAIN01 ergänzt den rechts aus Straßensicht sichtbaren Balkon, einen angenäherten Zugang, das Geländer am Kellerabgang und zwei oberirdische Fallrohrabschnitte. Der Fenster-/Dachfensterstand R11 bleibt bis auf die dokumentierte Balkonzugang-Korrektur erhalten. MAIN01 ist eine versionierte Arbeitsbasis, KEIN vermessener oder statisch freigegebener Bestand.

## 1. In NX 2406 erzeugen

Das gesamte ZIP in einen neuen kurzen, beschreibbaren Ordner entpacken. Neben dem Starter müssen `src`, `data`, `quellen` und die übrigen Lieferdateien liegen. Nicht mit R11a/R10 oder anderen Revisionen mischen. Eigene NX-Arbeit speichern; bereits geöffnete gleichnamige HAUS-/Geschossdateien nach dem Sichern manuell schließen. Bei Unsicherheit NX nach dem Speichern neu starten und keine alten Hausdateien öffnen.

Über den bisherigen Befehl **Journal abspielen / Play Journal** nur `00_HAUS_MAIN01_ERZEUGEN.py` auswählen. Kein eigenes leeres Part vorbereiten. Nativer Dateimodus, keine Teamcenter-Automatisierung vorgesehen. NXOpen nicht per pip installieren.

**Ja** im Freigabedialog: Haus mit gekennzeichneten Näherungen erzeugen. **Nein**: nur Referenzgerüst ohne Hauskörper; kein vollständiges Main-Modell. Der Starter führt Funktionstest, Hausaufbau, Speichern und Datei-/Strukturprüfung aus. Kein zweites CHECK-Journal starten. Zwischenmeldungen werden protokolliert, nicht durch zusätzliche OK-Dialoge blockiert.

Erwartet im Ja-Modus: `HAUS_MASTER.prt`, **15 Komponenten und 1.425 Körperaufträge**. Alle nativen `.prt`-Dateien entstehen erst durch den Lauf in deiner NX-Sitzung. Im Paket sind keine hier erzeugten NX-Dateien enthalten. Das Haus bleibt in Millimetern und im bisherigen lokalen Koordinatensystem mit EG-Fertigfußboden ±0,00. Garten-/Leitungsdaten verbleiben nur als Archivinformationen im Datensatz, es entstehen keine Grundstücks-, Leitungs-, Gelände- oder Vegetationskomponenten.

## 2. Die neuen Teile

`10_BALKON_RECHTS_MAIN01.prt`: Boden-Einhüllende, drei Randhüllen, zwei angenäherte Rundstützen und horizontale Bekleidung mit vereinfachten Geländerstielen. **Kein Vollstahl-/Balkenplan, keine Fundamente oder Befestigungen.**

`11_BALKON_ZUGANG_MAIN01.prt`: geschätzte seitliche Anschlussflächen. Das lokale Dach der Nische liegt im Dachteil, die verschobene Tür im DG-Teil. Eine Änderung des Zugangs betrifft deshalb mehrere Dateien. Die alte interne Linie `DG_W_BALKON` wurde als Modellfehlinterpretation entfernt, nicht als real abzubrechende Wand behandelt.

`12_KELLERABGANG_GELAENDER_MAIN01.prt`: sichtbares Geländer als angenäherte Stab-/Handlaufhüllen; noch keine Rekonstruktion des Treppenlaufs oder seiner Unterkonstruktion.

`13_FALLROHR_REFERENZEN_MAIN01.prt`: zwei obere sichtbare Fallrohrabschnitte als polygonale Außenhüllen. Kein vollständiges Entwässerungsnetz und keine unterirdische Fortsetzung. Keine Rohrwandstärken-/Werkstoffmengen ableiten.

Die vorhandene Flachdach-Referenzhaut bleibt unbestätigt. Die neue Balkonplatte ist eine **35-mm-Darstellungshülle**, die Balkonrandhöhen, Stützendurchmesser, Bekleidungsmaße und alle neuen Anschlusslagen sind Annahmen, keine Bemessung. Alle neuen Anbauteile sind von belastbarer Mengenermittlung ausgeschlossen.

## 3. Main-Basis sichern und weiterentwickeln

Nach erfolgreichem Lauf liegt der vollständige Hausausgabeordner unter `ausgabe/HAUS_<Zeit>_<Kennung>/`. Darin stehen Parts, das verwendete Daten-Snapshot, Bauaufträge, Prüfprotokolle, `manifest_MAIN01.json` und `BASELINE_MAIN01.json`. Der Paketordner erhält `LETZTER_MAIN01_LAUF.json` als Verweis auf genau diesen Lauf.

**Den gesamten Ausgabeordner als ersten unveränderten Ausgangsstand sichern – nicht nur `HAUS_MASTER.prt`.** Die Masterdatei verweist auf die Geschoss-/Detaildateien. Beim Weiterarbeiten die gespeicherte Masterbaugruppe direkt in NX öffnen, nicht den Erzeuger jedes Mal neu starten. Die Parts bleiben bearbeitbar, besitzen aber keine vollständig durchgängige Architektur-/BIM-Parametrik.

`data/haus.json` ist die lesbare Gebäudedefinition. Ein neuer Lauf erstellt einen neuen Ausgabeordner; er übernimmt keine manuellen Änderungen aus vorherigen NX-Parts. Die Eingabedateien dürfen für eine dokumentierte neue Variante angepasst werden; der Starter protokolliert ihre Abweichung zum Lieferstand. Programm-/Quelldateien bleiben hashgeprüft. Mögliche Revisionsfolge: MAIN01 unverändert archivieren, MAIN01-A01/Änderungsliste mit Quellen und Messwerten führen. Vor Änderungen an einer Kopie sicherstellen, dass ihre Komponentenreferenzen tatsächlich auf die Kopie und nicht die archivierten Originalteile zeigen. Eine allein kopierte Masterdatei ist kein unabhängiges Projekt.

Wichtige Änderungen sind in NX nur teilweise assoziativ: insbesondere die X/Y-Positionen der neuen Außenteile und die Dachnische werden aus der JSON-Datei beim Neuaufbau berechnet. Eine lokale NX-Expression ändert nicht automatisch jeden anderen Part. Vor einer angenommenen globalen Maßänderung die betroffenen Teile und Abhängigkeiten prüfen.

## 4. Fortschritt, Laufzeit und Stopp

Es gibt keine teuren Gelände-Flächenmessungen oder STEP-Prüfungen. Die bewährten Körper-, Einheiten-, Attribut- und Speicherprüfungen bleiben aktiv. Attribute werden nach Möglichkeit verzögert geschrieben; erforderliche Geometrieupdates und das Update vor dem Speichern bleiben erhalten. Ein gemessener NX-Geschwindigkeitsgewinn wird nicht behauptet.

`LAUFSTATUS_MAIN01.json` zeigt Aktion, Zähler und Laufzeit; `LAUFZEIT_MAIN01.jsonl` enthält die Zeitereignisse. Während eines langen nativen NX-Aufrufs bleibt auch die Anzeige ggf. stehen. Die Summe geschachtelter Zeiten ist keine Gesamtlaufzeit.

Eine leere Datei `STOP_MAIN01.txt` im **aktuellen Ausgabeordner** fordert einen Stopp zwischen den Schritten an. Ein bereits laufender NX-Aufruf wird nicht hart unterbrochen. Bereits gespeicherte Teile bleiben erhalten, aber ein Teilmodell erhält keine Gesamterfolgsmeldung. Keine fremden Parts werden automatisch geschlossen oder gelöscht.

Bei Abbruch: `STARTFEHLER_MAIN01_....json` und `manifest_MAIN01.json` sowie `LAUFSTATUS_MAIN01.json` aus demselben Lauf sichern. Bei Geometriefehlern zusätzlich Screenshot, Bauteil-ID und `bauauftrag.json` aufbewahren. Nicht pauschal Prüfungen abschalten oder Grenzwerte erhöhen.

## 5. Fachliche Grenzen und Prüfstand

**57 fokussierte Offline-/Simulationstests bestehen. Zusätzlich wurden alle 1.425 berechneten Körper mit Open CASCADE geometrisch aufgebaut und auf Gültigkeit/Volumen geprüft.** Testdateien unter temporären Pfaden sind ausdrücklich keine NX-Dateien. Kein eigener Lauf in NX 2406/Parasolid; keine Garantie eines fehlerfreien NX-Laufs oder einer bestimmten Laufzeit.

**Offen bleiben zehn Haus-Anbau-Überschneidungspaare und zwei teilweise blockierte Innentüröffnungen.** Die neuen Details erzeugen in der numerischen Prüfung keine weiteren gezählten Überschneidungspaare. Das ist keine vollständige Anschluss-, Kollisions-, Tragwerks- oder Planfreigabe. Auflager, Befestigungen, tatsächlich vorhandene Balken und die Statik fehlen weiter. Kein Eingriff am Tragwerk aus dieser Näherungsgeometrie ableiten.

Das Video wurde über den gesamten Rundgang mit zeitlich verteilten Einzelbildern und zusätzlich verdichteten Balkonausschnitten geprüft; **keine Audioauswertung, keine automatische Photogrammetrie, keine vollständige Vermessung**. Videoexistenz, historische Planmaße und aktuelle Schätzmaße bleiben getrennt. Alle neuen Maße sind als Schätzwerte gekennzeichnet. Die Planflächenangabe 8,74 m² wurde nicht ungeprüft zur physischen Balkonfläche erklärt.

## 6. Lesen / Offline-Prüfen

`VORSCHAU_HAUS.html` enthält die aktuelle Rechengeometrie mit eigenen Balkonschaltern. Sie ist kein NX-Screenshot. `PRUEFBERICHT_MAIN01.pdf` (M01, fünf Seiten) zeigt die Belege; die HTML-Version enthält zusätzliche Ansichten. `data/BEOBACHTUNGEN_MAIN01.json` führt 12 Hausbefunde. `data/AUFMASS_MAIN01_VORLAGE.json` ist eine leere Erfassungshilfe und wird nicht automatisch importiert.

Außerhalb von NX: `python werkzeuge/PRUEFE_MAIN01_OFFLINE.py`. Mit `--cad` werden zusätzlich OCP/Open CASCADE benötigt. Im NX-Journal selbst sind keine externen Python-Pakete erforderlich. Historische Unterlagen unter `archiv`/`quellen` sind datierte Quellen, kein aktueller Istzustandsnachweis. Die Originalvideo-Datei ist nicht nochmals im ZIP enthalten; vollständiger Hash im Datensatz, ausgewählte Belegbilder unter `video/belege`.
