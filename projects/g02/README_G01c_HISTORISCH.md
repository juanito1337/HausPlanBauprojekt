# NX-Gesamtprojekt G01c – segmentierte Geländeränder prüfen

**Patch: `MAIN01-A01-G01c-SEGMENTIERTER-DGM-RAND`. Vollständiges Paket.**
Haus MAIN01-A01, DGM, ausgewählte Vegetation und Leitungsplanreferenzen sind gegenüber G01b geometrisch unverändert. Keine neuen nativen `.prt`-Dateien wurden hier erzeugt. Kein eigener NX-/Parasolid-Lauf.

## Jetzt nur das Gelände starten

1. **Das gesamte ZIP in einen neuen beschreibbaren Ordner entpacken**, z. B. `C:\NXHaus\G01c`. Nicht über G01b kopieren und keine einzelnen Programmdateien mischen. Eigene NX-Arbeit sichern; alte Dateien behalten.
2. In NX über **Journal abspielen / Play Journal** die Datei **`04_NUR_GELAENDE_MIT_PROTOKOLL.py`** im neuen Hauptordner auswählen. Dort liegen auch `gesamt`, `haus`, `umgebung`, `data` und `diagnose`.
3. **Kein Part vorbereiten, keine STEP-Datei manuell importieren, kein zusätzliches Diagnose-/CHECK-Journal starten.** Der Starter findet die mitgelieferte Quelle automatisch und verwendet einen eindeutigen neuen Teildateinamen.

Der 04-Starter baut KEIN Haus und KEINE Vegetation auf. Er schließt oder speichert keine fremden Nutzermodelle. Alte Geländeteile dürfen auf der Festplatte bleiben. Erzeugung: Import → ausdrücklich ungeprüfte Sicherung → Flächen- und Randprüfung → abschließendes Speichern. Das Ergebnis ist ein separates Geländeteil, noch keine vollständige Umgebung.

## Warum G01b abbrach

Der aktuelle Screenshot meldet: **„genau vier unterschiedliche Randkanten erforderlich; erhalten 285“**. Diese starre Anzahl war eine Annahme meines G01b-Prüfers, keine notwendige Zahl von CAD-Kanten eines geometrisch vierseitigen Randes.

285 Kanten können eine Unterteilung der vier Seiten sein. Die Anzahl allein beweist aber weder eine korrekte Unterteilung noch eine falsche Geländeform. **Von diesem G01b-Lauf liegt hier nur der Screenshot vor, nicht die darin genannte neue JSON oder die tatsächlich importierte NX-Datei.** Die genaue Verteilung seiner 285 Kanten ist daher noch nicht überprüft. Der alte Prüfer stoppte bereits vor dem direkten Vergleich der 16.748 Gelände-Referenzpunkte.

## Die Änderung: vier Seiten, nicht vier Kantenobjekte

Die neue Prüfung liest alle tatsächlichen Kantenkennungen und Endpunkte aus NX. Sie ordnet jede Kante genau einer der vier ursprünglichen Randseiten zu, sortiert die Teilstücke räumlich und prüft die Abdeckung. **Sie ersetzt 4 nicht durch die Zahl 285.** Auch andere Unterteilungen sind möglich, wenn die Geometrieprüfungen bestehen.

Erforderlich bleiben:

- Genau ein offener Geländekörper mit einer Einzelfläche, richtige Einheit/Part-Zuordnung und passende Begrenzungsbox.
- Eindeutige Ketten über alle vier Quellseiten; passende Eckanschlüsse, keine fehlenden Seiten, nicht zuordenbaren Innenkanten, doppelten Kantenkennungen, Lücken oder Überlappungen über der CAD-Toleranz. Kleine Lücken/Überlappungen dürfen sich je Seite nicht über insgesamt 0,25 mm aufsummieren.
- Der unveränderte direkte UV-Vergleich aller **16.748 Rasterknoten und Zellmittelpunkte**, einschließlich der früher beanstandeten Punkte 85 und 1089.
- **736 ursprüngliche Randknoten/-mittelpunkte sowie drei zusätzliche Prüfstellen je tatsächlicher NX-Kante.** Bei 285 Kanten sind das 1.591 Randabfragen. Die zu prüfende Kante wird vorher aus der Seitenposition fest zugeordnet, nicht hinterher nach dem günstigsten Abstand ausgewählt.
- **Maximal 0,25 mm CAD-Abweichung**, keine Lockerung. Keine Übernahme erwarteter Quellwerte als Ersatz für fehlgeschlagene NX-Rückgaben.

Die Zusatzpunkte je Kante liegen auf der Quelle bei einem Viertel, der Hälfte und drei Vierteln ihres zugeordneten Seitenabschnitts. Hier wird die tatsächliche Entfernung zur zugeordneten NX-Kante abgefragt. Es werden keine Kanten verschmolzen, entfernt oder neu konstruiert.

**Grenzen:** Endlicher Koordinaten-/Randvergleich, kein lückenloser mathematischer Formgleichheitsbeweis und keine Bestandsvermessung. Sehr kleine oder nicht eindeutig einer Seite zuordenbare Sonderkanten sowie unerwartete Flächenteilungen werden weiter gemeldet. Für den Arbeitsaufwand gilt eine Obergrenze von 4.096 Randkanten; Überschreiten löst eine gesonderte Prüfmeldung aus und wird nicht als festgestellter Geometrieschaden ausgegeben. Es werden keine zusätzlichen NX-API-Methoden gegenüber G01b eingeführt.

Im normalen Modus bleibt die aufwendige Flächeninhaltsintegration aus. `INTENSIV` schaltet sie weiterhin zusätzlich ein. Eine Laufzeit oder Beschleunigung in NX wurde hier nicht gemessen. Ein blockierter einzelner NX-Aufruf kann nicht garantiert unterbrochen werden.

## Protokollierung

Im neuen `ausgabe/G01c_GELAENDE_<Zeit>_<Kennung>/` entstehen:

| Datei | Zweck |
|---|---|
| `GELAENDE_PROTOKOLL_G01c.json` | Quelle, Prüfsumme, Import, ungeprüfte Sicherung, Prüfung und finaler Speicherstatus. |
| `DGM_FLAECHENPRUEFUNG_G01c.json` | Tatsächliche Kantenanzahl, Endpunkte, Zuordnung und sortierte Randketten, UV-Abbildung, Abweichungen und Abbruchstelle. |
| `DGM_FLAECHENPUNKTE_G01c.jsonl` | Tatsächlich gelesene Flächenkoordinaten und Kantenabstände; blockweise geschrieben. |
| `diagnose_ungeprueft/DGM_UNGEPRUEFTER_IMPORT_G01c.prt` | Gesicherter Rohimport, ausdrücklich ungeprüft und nicht als fertige Umgebung zu benutzen. |
| `01_GELAENDE_G01c_<Kennung>.prt` | Neues Einzelteil. Erst das finale Prüf-/Speicherergebnis kennzeichnet den abgeschlossenen Lauf. |

Bei einem behandelten Fehler entsteht **`fehlerberichte/STARTFEHLER_G01c_....json`** mit den eingebetteten Befunden. Neue Randdaten stehen unter `nx_terrain_boundary_g01c`; die früheren Felder `nx_terrain_uv_g01b` und `nx_terrain_audit_g01a` bleiben kompatibel erhalten und tragen innen die neue Patchkennung. Alte Dateinamen in historischen Unterlagen sind kein Hinweis auf einen Rückschritt des Hausstands.

Die Kennungen und Endpunkte werden vor der eigentlichen Kettenprüfung protokolliert. Beim nächsten Fehler ist somit sichtbar, welche Seite/Kante unpassend war. Die vollständige JSONL-Datei wird gepuffert; bei einem harten NX-Hänger kann die letzte noch ungepufferte Abfrage fehlen. Eine leere `STOP_R11a.txt` im konkreten Gelände-Laufordner fordert einen Stopp zwischen den Schritten an, keinen harten Kernelabbruch.

## Prüfung dieser Lieferung

**564 Offline-/Simulationstests bestehen**, einschließlich **42 neuer Tests** für segmentierte Ränder. Die 36 bisherigen G01b-UV-Tests wurden auf die zusätzlichen Randproben und die veränderte Topologieregel angepasst; ihre alten Dateinamen bleiben erhalten. Testdoppel sind keine tatsächlich gemessenen NX-Ergebnisse.

Zusätzlich: Original-STEP mit vier Kanten und eine **eigens konstruierte, geometrisch gültige CAD-Testfläche mit 285 Randkanten auf derselben Trägerfläche** wurden mit Open CASCADE geprüft. Beide bestehen die 16.748 Koordinatenvergleiche und ihre Randprüfungen. Eine zusätzliche innere Öffnung und eine um 2 mm angehobene innere Stützstelle werden zurückgewiesen. **Diese künstliche 285-Kanten-Kopie ist nicht deine importierte NX-Geometrie.** Sie ersetzt die Geländequelle im Lieferpaket nicht.

Auch die bestehenden unabhängigen Prüfungen aller 1.418 Hauskörper und der elf STEP-Quellen sind enthalten. Der ausgeführte Umfang steht in `berichte/ERGEBNIS_G01c.json` und `berichte/TESTPROTOKOLL_G01c.txt`. Alle Dateien unter `haus`, `umgebung`, `data` und `diagnose` sind gegenüber G01b bytegleich; Vergleich in `berichte/QUELLEN_UNVERAENDERT_G01c.json`.

**Kein eigener NX-2406-Lauf.** Die neue Prüfung muss die tatsächlichen 285 Kanten deiner nächsten NX-Ausführung erst geometrisch zuordnen und auswerten. Es gibt keine Zusicherung, dass jeder nachfolgende NX-Schritt fehlerfrei ist.

## Das Gesamtprojekt bleibt enthalten

`00_GESAMTPROJEKT_ERZEUGEN.py`: Haus MAIN01-A01 zuerst, dann Umgebung, danach Projektbaum.

`01_NUR_HAUS_ERZEUGEN.py`: ausschließlich aktuelles Haus, ohne STEP.

`02_NUR_UMGEBUNG_ERZEUGEN.py`: komplette ausgewählte Umgebung, ohne Haus-Neuaufbau.

`03_GESPEICHERTE_TEILE_ZUSAMMENSTELLEN.py`: unveränderte erfolgreiche Teilläufe dieses Pakets zusammenstellen.

`04_NUR_GELAENDE_MIT_PROTOKOLL.py`: der oben beschriebene kleine Gegencheck. Dieser schreibt keinen Verweis auf eine vollständige Umgebung.

Keine manuell bearbeiteten alten `.prt`-Dateien werden in einen Neuaufbau übernommen. Zum späteren Arbeiten gespeicherte Masterdateien direkt öffnen. Das Haus mit den 15 Komponenten und 1.418 Körperaufträgen, die Vegetationsauswahl und die historischen Leitungslagen bleiben unverändert. Der bestätigte Höhenanschluss zwischen Haus und Umgebung fehlt weiter; ohne ihn bleiben beide in ihren getrennten Quellhöhen. Zehn bekannte Haus-Anbau-Überschneidungspaare, zwei teilweise blockierte Türöffnungen, fehlende Statik und unbekannte Leitungstiefen sind nicht durch diese Randkorrektur gelöst.

Ältere Berichte/READMEs im Paket sind ausdrücklich historische Nachweise. **Aktuell sind dieser Text und `PRUEFBERICHT_G01c.html`.** Zum Offline-Nachprüfen (nicht in NX): `python werkzeuge/PRUEFE_GESAMTPAKET_G01.py --out NEUER_ORDNER --cad`. Zusätzliche Offline-CAD-Werkzeuge brauchen OCP/cadquery; innerhalb von NX sind keine neuen Python-Pakete erforderlich.
