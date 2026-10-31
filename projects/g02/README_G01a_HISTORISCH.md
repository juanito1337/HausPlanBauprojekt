# Gesamtprojekt G01a – automatische Gelände-Erzeugung mit Diagnose

**Patch: `MAIN01-A01-G01a-GELAENDEPROTOKOLL`. Vollständiges Paket.**
Hausstand MAIN01-A01 und alle STEP-Quelldaten aus G01 bleiben unverändert.
Keine fertigen NX-`.prt`-Dateien im Lieferpaket; diese entstehen in deiner NX-Sitzung.

## Für den jetzigen Geländefehler: genau einen Starter ausführen

Das gesamte ZIP in einen NEUEN, kurzen, beschreibbaren Ordner entpacken,
z. B. `C:\NXHaus\G01a`. Neben den Startern müssen `gesamt`, `haus`, `umgebung`,
`data` und `diagnose` liegen. Nicht mit G01 oder älteren Paketen mischen.
Eigene NX-Arbeit vorher sichern.

In NX über „Journal abspielen / Play Journal“ aus dem neuen Hauptordner starten:

**`04_NUR_GELAENDE_MIT_PROTOKOLL.py`**

Dieser Starter findet die im Paket enthaltene Geländequelle automatisch über den
Importauftrag, überprüft ihre Prüfsumme, ermittelt die lokale STEP-Importdefinition,
erstellt ein neues Millimeter-Teil, importiert das Gelände und protokolliert die
nachfolgende Prüfung. Du musst KEINE STEP-Datei manuell suchen/importieren und KEINE
vorhandene `01_GELAENDE_R09.prt` auswählen. Ein separates Diagnosejournal ist nicht nötig.
Der STEP-Importer wird weiterhin intern benutzt; dies ist keine STEP-freie Neuerzeugung.

Der Einzelstarter erzeugt NUR das Gelände: kein Haus, keine Vegetation, keine
Gesamtbaugruppe. Bereits gespeicherte Häuser und manuelle Änderungen bleiben unberührt.
Jeder Einzelstart verwendet eine neue, eindeutige Part-Kennung. Er speichert oder
schließt keine bereits vorhandenen Nutzermodelle. Alte Teile können dabei geladen
bleiben; sie werden nicht als neues Importziel benutzt. Nicht mehrere Journale
parallel ausführen. Eine harte Unterbrechung eines laufenden NX-Aufrufs ist nicht implementiert.

## Automatischer Ablauf

```text
Mitgelieferte Quelle und Prüfsumme kontrollieren
→ neues eigenes NX-Teil erzeugen und STEP importieren
→ importierten Stand als UNGEPRÜFT speichern und Diagnosekopie sichern
→ normale BASIS- oder INTENSIV-Prüfung mit Rohwertprotokoll durchführen
→ bei Fehler zusätzlich begrenzte Diagnose am gerade erzeugten Körper
→ Fehler mit allen Diagnosedaten melden ODER nach bestandener Prüfung fertig speichern
```

Die Quelldatei ist im vollständigen ZIP tatsächlich enthalten:
`umgebung/CAD_IMPORT/GELAENDE_R07_UNVERAENDERT.step`.
Ihr aufgelöster Absolutpfad und ihre SHA-256-Prüfsumme stehen im Laufprotokoll.
Die mitgelieferten Quellen werden nicht verändert, verschoben, skaliert oder geglättet.

## Welche Dateien der Gelände-Einzelstart erzeugt

Unter `ausgabe/G01a_GELAENDE_<Zeit>_<Kennung>/` entstehen:

| Datei | Bedeutung |
|---|---|
| `GELAENDE_PROTOKOLL_G01a.json` | Quelle, Einstellungen, tatsächliche NX-Körper-/Flächenanzahl, Speicherstatus, letzte Messungen und Zusatzdiagnose. Vor/nach nativen Punktabfragen aktualisiert. |
| `GELAENDE_PUNKTABFRAGEN_G01a.jsonl` | Alle regulären Punktabfragen in Reihenfolge: Original-Eingabe, Flags, rohe NX-Rückgabe, zurückgegebene Zielkoordinate, Laufzeit. |
| `diagnose_ungeprueft/DGM_UNGEPRUEFTER_IMPORT_G01a.prt` | Kopie des nach Import gespeicherten, noch UNGEPRÜFTEN Standes. Nur vorhanden, wenn NX den Import und Speichervorgang erfolgreich ausführt. Keine geprüfte Modellfreigabe. |
| `01_GELAENDE_G01a_<Kennung>.prt` | Neues Geländeteil. Nach Abbruch weiterhin als UNGEPRÜFTER_IMPORT gekennzeichnet; erst nach komplett bestandener Prüfung abschließend gespeichert. |
| `manifest_G01.json` | Ergebnis des Einzelablaufs. Kein Erfolgsverweis für ein komplettes Haus-/Umgebungsmodell. |
| `LAUFSTATUS_R11a.json` / `LAUFZEITPROFIL_R11a.jsonl` | Übernommene Ablauf-/Zeitmessung; die inneren Dateinamen sind kompatibel beibehalten. |

Bei einem normalen Python-/NX-Abbruch schreibt der Starter zusätzlich
`fehlerberichte/STARTFEHLER_G01a_....json`. Die Geländediagnose wird darin unter
`nested_diagnostics.nx_terrain_audit_g01a` eingebettet. **Zum Rückmelden genügt
zunächst diese eine neue Startfehler-JSON.** Falls NX in einem nativen Aufruf nicht
zurückkehrt, bleiben die vorher geschriebenen Status-/Protokolldateien relevant;
dann kann kein abschließender Python-Fehlerbericht garantiert werden.

Ein gespeicherter Diagnose-Part ist KEIN vollständig geprüftes Geländemodell.
Er darf nicht allein wegen seiner Dateiexistenz als erfolgreicher Umgebungsstand
verwendet werden. Die Gesamtbaugruppe und Ergebnisverweise nehmen ihn bei einem
Abbruch nicht als fertige Umgebung auf.

## Die Abstandsursache ist weiterhin offen

Die zuletzt gemeldeten Abstände bei DGM-Punkt 85 beziehungsweise Index 1089 sind
nicht durch einen tatsächlichen NX-Nachtest geklärt. G01a ändert NICHT die reguläre
Abstandsabfrage und erhöht NICHT die Grenze von 0,25 mm. Die neue Protokollierung
speichert nun auch die von NX zurückgegebenen Messpunkte sowie den zuvor abgefragten
Quellpunkt. Das erlaubt die Unterscheidung zwischen einem Importfehler und einer
möglicherweise fehlgeleiteten Nahpunktsuche; es beweist noch keine Ursache.

Wenn die normale Prüfung scheitert, folgt automatisch der bisher separate,
begrenzte Vergleich am selben Körper: Körperabstand, Abstand zu seinen tatsächlichen
Einzelflächen mit/ohne Startschätzung und eine Gegenprobe oberhalb der tatsächlichen
Begrenzungsbox. Bei einer Einzelfläche sind das 31 Zusatzabfragen. Es wird NICHT der
kleinste oder passendste Wert ausgewählt. Auch wenn eine Vergleichsmethode einen
kleinen Abstand liefert, bleibt der ursprüngliche Prüfabbruch bestehen.

Die normale BASIS-Auswahl bleibt erhalten: 147 DGM-Punkte, keine Flächenintegration.
INTENSIV bleibt konfigurierbar und kann lange dauern. Die zusätzliche Rohwert-
Protokollierung und Import-Speicherung benötigen ihrerseits etwas Laufzeit. Keine
NX-Laufzeitmessung oder garantierte Dauer wurde hier ermittelt.

## Auch im vollständigen Projekt integriert

| Starter | Aufgabe |
|---|---|
| `00_GESAMTPROJEKT_ERZEUGEN.py` | MAIN01-A01-Haus zuerst, danach Umgebung samt automatischer Geländediagnose und Gesamtbaugruppe. |
| `01_NUR_HAUS_ERZEUGEN.py` | Nur das aktuelle Haus. Kein STEP/Geländeaufbau. |
| `02_NUR_UMGEBUNG_ERZEUGEN.py` | Gelände, ausgewählte Vegetation und Kartenreferenzen; Diagnose ebenfalls integriert. |
| `03_GESPEICHERTE_TEILE_ZUSAMMENSTELLEN.py` | Nur vollständig gespeicherte Haus-/Umgebungsverweise aus genau diesem G01a-Paket zusammensetzen. Kein Neuaufbau. |
| `04_NUR_GELAENDE_MIT_PROTOKOLL.py` | Automatischer kurzer Gelände-Einzelablauf für den aktuellen Abbruch. |

Für 00/01/02/03 gleichnamige alte Projektteile nach dem Sichern schließen, wie bisher.
04 benutzt dagegen einen eigenen eindeutigen Partnamen. Beim Hausdialog bedeutet Ja
das dokumentierte Näherungsmodell; Nein nur das Referenzgerüst. Kein weiteres CHECK
starten. Alte Ergebnisverweise nicht in dieses Paket kopieren.

## Modellstand und Prüfung

Hausgeometrie MAIN01-A01, Höhen, Fenster, Balkon, Dächer, Gelände und Vegetations-
Quellen sind unverändert. Es wird kein neuer Dachstuhl nach einer nicht vorliegenden
Statik erzeugt. Zehn bekannte Haus-Anbau-Überschneidungspaare, zwei teilweise blockierte
Innentüröffnungen, fehlende bestätigte Leitungstiefen und der Höhenanschluss zwischen
Haus und Umgebung bleiben offen. Kein Bestands-, Bau- oder Tragwerksnachweis.

Es wurde hier kein NX-/Parasolid-Lauf ausgeführt. Offline-Simulationen sind keine
NX-Messungen; im Test erzeugte temporäre Textdateien sind keine nativen NX-Parts.
Aktuelle Prüfungen: `PRUEFBERICHT_G01a.html` und `berichte/TESTPROTOKOLL_G01a.txt`.
Der bisherige Bericht `PRUEFBERICHT_G01.html` und `README_G01_HISTORISCH.md` beschreiben
nur den Vorgängerstand. Die separaten alten Diagnosejournale unter `diagnose/` müssen
für G01a nicht gestartet werden.

Offline (nicht in NX):
`python werkzeuge/PRUEFE_GESAMTPAKET_G01.py --out NEUER_LEERER_TESTORDNER`
Optional `--cad` für die vorhandenen unabhängigen Open-CASCADE-Prüfungen.
Im NX-Journal keine zusätzlichen Python-Pakete installieren.

© GeoBasis-DE/LVermGeo SH/CC BY 4.0 für die übernommenen Geobasisdaten.
