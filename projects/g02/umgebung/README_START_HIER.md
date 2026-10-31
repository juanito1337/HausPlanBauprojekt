# NX-Haus R11a – Laufzeitüberarbeitung, Geometrie weiterhin R11

**Start: `00_NX_MODELL_ERZEUGEN_2406.py`. Vollständiges Paket, keine fertigen NX-`.prt`-Dateien. Kein hier ausgeführter NX-Lauf oder gemessener NX-Geschwindigkeitsgewinn.**

R11a ändert den Ablauf und den Umfang der automatischen Umgebungsprüfung. Fenster, Dach, sonstige Hausgeometrie, Gelände, Vegetationsauswahl und Leitungsdaten bleiben auf Stand R11. Es werden keine Punkte gelöscht, Oberflächen geglättet oder Fensterdetails reduziert.

## 1. Der wichtige Unterschied: BASIS statt Intensivprüfung

**Der normale Aufbau prüft die Umgebung jetzt bewusst weniger umfassend.** Er prüft weiterhin alle Flächenkörper hinsichtlich Anzahl, Art, Eigentümer-Part und Begrenzungsbox. Anschließend erfolgen räumlich verteilte Quellpunkt-Stichproben mit der bisherigen CAD-Abstandsgrenze von 0,25 mm. Das ist keine vermessungstechnische Genauigkeitsangabe.

Es wird im Modus **BASIS KEIN Flächeninhalt integriert** und **NICHT jeder definierte Quellpunkt** geprüft. Die bisherigen Flächenmessungen waren potenziell sehr teuer. Ein durchgelaufener BASIS-Aufbau ist kein gleichwertiger Ersatz für die frühere Intensivprüfung. Nicht erfasste Abweichungen zwischen den Stichproben sind möglich.

Das wird in den Part-Attributen `HAUS_IMPORTPRUEFUNG`, `HAUS_FLAECHENINHALT_GEPRUEFT`, `HAUS_ALLE_QUELLPUNKTE_GEPRUEFT` sowie in Manifest und Importberichten gekennzeichnet. Ein fehlender Messwert wird NICHT durch Null oder einen Quellflächenwert ersetzt.

| Umgebungsgruppe | Bisher definierte Punkte | Jetzt geprüfte Originalpunkte |
|---|---:|---:|
| Gelände DGM | 16.748 | 147 |
| V01 | 1.920 | 509 |
| V02 | 1.222 | 291 |
| V03 | 452 | 201 |
| V05 | 541 | 164 |
| **Umgebung zusammen** | **20.883** | **1.312** |
| Vorgeschalteter Importtest, zusätzlich | 58 | 23 |

Das sind rund **93,7 % weniger Punkt-Abstandsaufrufe** im eigentlichen Umgebungsaufbau. Das ist **keine Behauptung von 93,7 % kürzerer Gesamtlaufzeit**. STEP-Import, Darstellung, Dateizugriffe und der eigentliche Hausaufbau benötigen weiterhin Zeit.

## 2. Weitere Laufzeitänderungen

Projektattribute werden nach Möglichkeit mit `Update.Option.Later` geschrieben und bei den weiterhin vorhandenen Feature- beziehungsweise Speicheraktualisierungen verarbeitet. **Die geometrischen Feature-Updates und das zwingende DoUpdate vor dem Speichern bleiben aktiv.** Die Zusatzattribute werden weder weggelassen noch auf Expressions oder reservierte Attributnamen geschrieben. Fehlt `Later` in der Installation, bleibt der bisherige `Now`-Weg mit Hinweis erhalten.

Detaillierte Körper- und Einheitenmeldungen bleiben in den Textprotokollen, werden jedoch nicht mehr einzeln tausendfach ins Informationsfenster ausgegeben. Fortschrittsmeldungen erscheinen nach jeweils 25 Features oder mehreren Sekunden, soweit der aktuelle NX-Aufruf zurückgekehrt ist.

Zwischenmeldungen des Erzeugers blockieren nicht mehr mit zusätzlichen OK-Dialogen. **Die ausdrückliche Zustimmung zu Näherungen bleibt bestehen**. Nach Ende des Gesamtstarts erscheint eine Abschlussmeldung. Einzelne importierte Umgebungsteile werden nicht nochmals jeweils separat eingepasst; die Masterbaugruppe wird weiterhin angezeigt.

## 3. Ausführen

1. Das gesamte ZIP in einen **neuen lokalen, beschreibbaren Ordner** entpacken. Nicht mit R11 oder älteren Paketen mischen. Eigene Arbeit sichern und gleichnamige alte Projekt-Parts manuell schließen. Im Zweifel NX nach dem Speichern neu starten.
2. Über „Journal abspielen“ **einen** Starter aus dem neuen Hauptordner auswählen. `r09`, `basis`, `data` und `CAD_IMPORT` müssen daneben liegen.
3. Bei einem Hauslauf den Dialog zu Näherungen bewusst mit **Ja** beantworten, um das detaillierte Prüfmodell zu erzeugen. **Nein** erzeugt weiter nur das Haus-Referenzgerüst. Während eines laufenden Journals keinen zweiten Erzeugungslauf starten.

| Starter | Aufgabe |
|---|---|
| `00_NX_MODELL_ERZEUGEN_2406.py` | Haus zuerst, danach Gelände und V01/V02/V03/V05, anschließend Projektbaum. |
| `01_NUR_HAUS_ERZEUGEN_2406.py` | Nur Haus mit Grundstücks-/Leitungsplanreferenzen, **ohne STEP**, ohne Geländeaufbau. |
| `02_NUR_UMGEBUNG_ERZEUGEN_2406.py` | Nur Gelände und gewählte Vegetation, ohne erneuten Hausaufbau. |

Wenn das R11-Haus bereits erfolgreich gespeichert wurde, bleibt es inhaltlich derselbe Stand. Für den Gegencheck der Umgebung genügt `02_NUR_UMGEBUNG_ERZEUGEN_2406.py`. Dieser Einzelstart baut keine neue Verknüpfung zu alten Hausdateien auf. Ein vollständiger Projektbaum entsteht durch den Gesamtstart.

**Zum Weiterarbeiten gespeicherte `.prt`-Dateien öffnen, nicht die Starter erneut ausführen.** Es gibt keinen automatischen Cache oder Wiederaufnahmemechanismus. Neue Läufe benutzen neue Ordner, übernehmen aber auch keine manuellen Modelländerungen aus älteren Dateien.

## 4. Fortschritt, Zeiten und Stoppwunsch

Das Informationsfenster nennt den aktuellen R11a-Laufordner unter `ausgabe/R11a_<Datum>_<Kennung>/`. Dort stehen:

- `LAUFSTATUS_R11a.json`: letzter Aktualisierungszeitpunkt, aktuelle Aktion, Zähler und Laufzeiten.
- `LAUFZEITPROFIL_R11a.jsonl`: Zeiten abgeschlossener Arbeitsschritte. Einzelne sehr kurze Punktmessungen werden aggregiert; langsame oder fehlgeschlagene Messungen zusätzlich einzeln protokolliert.
- `manifest_R11a.json`: Ergebnis, Prüfmodus, gespeicherte Teilmodelle und gegebenenfalls Fehler.
- `LAUFZEITZUSAMMENFASSUNG_R11a.json`: Zusammenfassung nach Abschluss oder behandeltem Abbruch.

Die Messbereiche sind teilweise geschachtelt. Ihre Zeiten dürfen deshalb nicht unbesehen zu einer Gesamtlaufzeit addiert werden.

**Kein Hintergrund-Thread ruft NX auf.** Der Status wird zwischen Aufrufen aktualisiert. Während NX in einem langen STEP-, Feature- oder Messaufruf arbeitet, kann auch die Statusdatei unverändert bleiben. Das ist kein sicherer Nachweis eines Absturzes. Die neue Version verspricht keinen harten Timeout für einen blockierten nativen NX-Aufruf.

Für einen kontrollierten Stopp eine leere Datei **`STOP_R11a.txt` direkt im laufenden R11a-Ausgabeordner** anlegen. Sie wird zwischen den Arbeitsschritten geprüft; ein bereits laufender NX-Kernelaufruf muss erst zurückkehren. Der Lauf endet dann ohne Gesamterfolgsmeldung, bereits gespeicherte Parts bleiben erhalten. Nicht in den Paket-Hauptordner legen. Keine vorhandenen Nutzermodelle werden automatisch geschlossen oder gelöscht.

## 5. Intensivprüfung ausdrücklich einschalten

In `data/LAUFZEIT_R11a.json` kann vor einem neuen Lauf geändert werden:

```json
"surface_validation": "INTENSIV"
```

Dann gelten wieder der bisherige Flächeninhaltsvergleich, die adaptive Mehrfachmessung und alle definierten Quellpunktvergleiche. **Das kann erneut sehr lange dauern.** Die bisherige numerische Grenze wurde nicht gelockert. INTENSIV ist auch kein vollständiger mathematischer Formgleichheits- oder Bestandsnachweis.

Weitere bewusst änderbare Schalter: `defer_project_attributes`, `intermediate_dialogs`, `skip_individual_surface_fit`. Unbekannte Einstellungen und falsche Datentypen werden abgewiesen. Die Laufzeitdatei ist eine Benutzereinstellung; die übrigen Programm-/Quelldateien bleiben hashgeprüft.

## 6. Unveränderte Modellgrenzen

1.361 Hauskörper-Aufträge, 115 ausgewählte Umgebungsflächenkörper in fünf Quellgruppen plus Kartenreferenzen. Haus- und Umgebungshöhen sind weiterhin nicht verifiziert angeschlossen; die gemeinsame R11-Referenzbaugruppe enthält bewusst unterschiedliche Z-Bezüge. Keine automatische 30-m-Verschiebung.

Zehn bekannte Haus-Anbau-Überschneidungspaare, zwei teilweise blockierte Türöffnungen, fehlende Statik, ungeklärte Flachdachkonstruktion und unbekannte Isttiefen der Leitungen bleiben offen. Keine Bestands-, Tragwerks- oder Erdarbeitsfreigabe. Die Vegetation bleibt datierte Oberflächenreferenz, nicht ein Modell vermessener Einzelbäume.

## 7. Prüfen und Fehler eingrenzen

Der aktuelle Nachweis steht in `PRUEFBERICHT_R11a.html` und im mitgelieferten Testprotokoll. **Kein eigener NX-/Parasolid-Lauf; keine gemessene reale Laufzeitverbesserung.** Offlinetests prüfen Programmlogik und simulierte Antworten. CAD-Quellenprüfungen erfolgen mit Open CASCADE, nicht NX.

Bei weiterhin sehr langer Laufzeit sind **`LAUFSTATUS_R11a.json`, `manifest_R11a.json` und `LAUFZEITPROFIL_R11a.jsonl` aus demselben Lauf** entscheidend. Bei einem Abbruch zusätzlich den neuen Startfehlerbericht sichern. Alte R09/R11-Dateinamen in inneren Laufordnern sind für die Kompatibilität beibehalten; maßgeblich sind die äußere Patchkennung `R11a-LAUFZEIT` und das neue Manifest.

Historische Berichte R06–R11 gelten nur für ihre jeweiligen Stände. Die Vorschauen bleiben geometrisch unverändert und zeigen keinen neuen NX-Lauf.
