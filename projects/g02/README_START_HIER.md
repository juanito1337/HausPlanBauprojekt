# G02 – Gesamtprojekt mit integrierter Höhenmontage

**Vollständiges Paket: Haus MAIN01-A01, Gelände, ausgewählte Vegetation und historische Leitungsreferenzen.**

**Gesamtstarter: `00_GESAMTPROJEKT_G02_ERZEUGEN.py`.** Er baut Haus und Umgebung auf und erzeugt anschließend unmittelbar eine höhenbezogene Projektbaugruppe. **Kein nachträgliches H01-/H01a-Journal erforderlich.**

Die gemeinsame Arbeitsmontage verwendet einen **vorläufigen Planbezug, keinen bestätigten heutigen Höhenmesspunkt**. Der sichtbare Versatz um etwa 31 m wird damit ausgeglichen; sämtliche realen Gelände-/Fassadenanschlüsse sind dadurch nicht vermessen.

## 1. Vollständig neu erstellen

1. Das **gesamte ZIP in einen neuen kurzen, beschreibbaren Ordner** entpacken, z. B. `C:\NXHaus\G02`. Nicht mit G01e, H01 oder H01a mischen. Alte Dateien behalten.
2. Eigene NX-Arbeit sichern. Für einen **Neuaufbau mit 00** gleichnamige alte Haus-/Umgebungsteile schließen; im Zweifel NX nach dem Sichern neu starten, ohne die alten Modelle zu öffnen. Das Journal schließt oder löscht keine alten Teile automatisch.
3. In NX über **Journal abspielen / Play Journal** ausdrücklich `00_GESAMTPROJEKT_G02_ERZEUGEN.py` aus dem neuen Hauptordner starten. Neben ihm liegen `g02`, `gesamt`, `haus`, `umgebung`, `data` und `diagnose`.
4. Den angezeigten **vorläufigen Höhenansatz** bewusst mit Ja bestätigen. Im anschließenden Hausdialog bedeutet Ja das Haus mit dokumentierten Näherungen; Nein erzeugt nur das Referenzgerüst. Für das gewünschte vollständige Arbeitsmodell Ja wählen. Keine weiteren Starter parallel und kein CHECK-/H01-Journal starten.
5. Nach Erfolg **`PROJEKT_MASTER_G02_PLANBEZUG_<Kennung>.prt`** aus dem neuen G02-Ausgabeordner öffnen/weiterbearbeiten. Die Datei wird am Ende angezeigt. Nicht die alte `…HOEHENBEZUG_OFFEN.prt` öffnen.

Die native Projektdatei entsteht **erst im NX-Lauf**. Das ZIP enthält die tatsächlichen Gelände-/Vegetations-STEPs, Quelldaten und NXOpen-Erzeuger, aber keine hier erzeugten nativen `.prt`-Dateien. Kein eigener NX-/Parasolid-Test dieser Revision.

## 2. Bereits fertiges G01e weiterverwenden – ohne neuen Haus-/Geländelauf

Für den zuletzt gezeigten Zustand mit bereits vorhandenen Haus- und Umgebungsteilen ist der kürzere Weg im selben Paket enthalten:

**`05_G02_VORHANDENES_PROJEKT_MONTIEREN.py`**

Die ursprüngliche **G01e-Gesamtbaugruppe angezeigt lassen**. Der Starter verwendet ihren Pfad ausschließlich zum Auffinden des daneben gespeicherten erfolgreichen `manifest_G01.json`; bei G02 entsprechend `manifest_G02.json`. Er liest daraus die gespeicherten Haus-/Umgebungskomponenten, prüft ihre Dateiprüfsummen und erstellt eine neue höhenbezogene Projektbaugruppe.

**Wesentliche Änderung gegenüber H01a:** Die alte äußere Projekt-Masterdatei wird nicht als Geometrie- oder Positionsquelle verwendet. Ihr Änderungskennzeichen blockiert diesen Weg deshalb nicht. Das Kennzeichen wird weder gelöscht noch als „sauber“ umgedeutet. Die alte Projektdatei wird nicht gespeichert, geschlossen oder überschrieben. **Nur in ihr vorhandene Montage-/Darstellungsänderungen werden nicht übernommen.** Das wird vor Ausführung ausdrücklich bestätigt.

Die eigentlichen **Haus-/Umgebungskomponenten bleiben geschützt**: nicht abgeschlossene Läufe, geänderte Dateien, unbekannte Unterteile und echte ungespeicherte Änderungen an Quellkomponenten werden weiterhin abgewiesen. Erforderliche Teile werden vor Lesezugriffen gezielt vollständig nachgeladen. Änderungen an alten Parts werden nicht durch irgendein automatisches Speichern/Verwerfen „behoben“.

05 erzeugt **kein neues Haus und importiert kein STEP**. Nur die neue Projektbaugruppe sowie neue, identische historische Leitungsplanreferenzen entstehen. Alle alten Komponentenordner bleiben erforderlich. 00 und 05 sind **Alternativen**, nicht nacheinander nötig.

## 3. Gemeinsamer Höhenbezug

| Größe | Vorbereiteter Wert |
|---|---:|
| Gebäude-Nullpunkt | EG-Fertigfußboden ±0,00 |
| Gewählter Außenanker, lokale Hauskoordinaten | X = 0 mm, Y = −500 mm |
| DGM-Quellhöhe am Anker | 31,062498708 m |
| Vorläufige Zielhöhe am Anker | −0,300 m relativ EG |
| Gemeinsamer Z-Versatz der gesamten Umgebung | −31.362,498708 mm |

**Quelle und Annahme sind getrennt:** Schnitt A–A / P13 vom 14.06.1995 zeigt die Außenkote −0,30 m. Die Übertragung auf den gewählten Punkt (0/−500 mm) ist eine **unbestätigte Modellannahme**, keine genau zugeordnete Messmarke im Plan. Die berechneten 31,362498708 m sind **keine bestätigte NHN-Höhe des EG**. Die vielen Nachkommastellen kommen nur aus der Rechnung.

Formel: **Z im Projekt = ursprüngliche Quellhöhe in mm − 31.362,498708 mm.**

Die Einstellung steht zentral in `data/HOEHENANSCHLUSS_G02.json`. Dort sind alternativ `AUFMASSPUNKT` oder `ABSOLUTE_EG_HOEHE` vorbereitet. Ein absoluter Höhenwert verlangt einen belegten gemeinsamen Höhenbezug und eine konkrete Quelle. In `data/EINSTELLUNGEN_GESAMT.json` bleibt die alte `height_connection` bewusst leer; zwei gleichzeitig aktive Höhendefinitionen werden abgewiesen.

Die **gesamte Umgebungsbaugruppe** wird einmal auf diesen Z-Versatz gesetzt: Gelände, V01, V02, V03, V05 und die darin enthaltenen Kartenreferenzen. Ihre gegenseitigen Höhen bleiben erhalten. Keine Einzelverschiebung der Pflanzen, keine Skalierung, kein Kippen, keine Verformung des Geländes. Wiederholte Montage addiert den Versatz nicht ein zweites Mal.

**Die Quelleinzelteile behalten bewusst ihre Originalhöhen.** Die korrigierte gemeinsame Lage siehst du in der neuen **G02-Projekt-Masterdatei**, nicht beim isolierten Öffnen des ursprünglichen Umgebungs-Quellteils.

## 4. Enthaltene Bereiche und Grenzen

Das Haus bleibt MAIN01-A01: 15 Komponenten mit 1.418 vorgesehenen Körpern, letzter Fenster-/Videostand, Balkon und Zugang, Dachfenster, Solarfeldhüllen und korrigierte Gaubenanschlüsse. Hauptdach 45°, ehemaliges Schwimmhallendach 28°; Gaubenwinkel, tatsächliche Konstruktion und weitere Maße teils geschätzt.

Die Umgebung enthält die DGM-Fläche und V01/V02/V03/V05: **115 offene Quellflächenkörper**, keine 115 Bäume. Die G01d-STEP mit expliziten Randsegmenten und der G01e-Prüfer für 8.282 mögliche Raster-Teilflächen sind unverändert enthalten. Die CAD-Vergleichsgrenze bleibt 0,25 mm; sie ist **keine Vermessungsgenauigkeit**. Die Vegetations-Basisprüfung bleibt eine Stichprobe, keine vollständige Oberflächenprüfung.

Die Grundstückskontur ist eine Kartenreferenz, kein neuer Grenzvermessungsnachweis. Die 25 historischen Leitungstrassen / 45 Liniensegmente bleiben in einer getrennten, ausgeblendeten Planbaugruppe auf Z = 0. **Die tatsächlichen Leitungstiefen sind nicht bekannt und werden durch die Höhenmontage nicht ergänzt.**

Das DGM wird innerhalb der Gebäudeprojektion **nicht ausgeschnitten**. Keller können dadurch in der Ansicht verdeckt sein; Gelände ausblenden oder Schnittansicht verwenden. Kein angeblich vermessener Baugrubenrand, keine neue Böschung, keine erfundenen Anschlüsse an Türen, Lichtschächte oder Terrassen. DGM-Jahreskennung 2023; konkrete vertikale Metadatenzuordnung weiterhin offen. bDOM und Luftbild haben unterschiedliche Datenstände 2023/2025.

**Zehn bekannte Haus-Anbau-Überschneidungspaare und zwei teilweise blockierte Innentüröffnungen bleiben offen. Statik, Dachtragwerk und Flachdachdetails sind nicht vollständig belegt.** G02 verbessert die Gesamtmontage, nicht den Nachweis des ausgeführten Bestands.

## 5. Speichern, Protokolle und Weiterentwicklung

Unter `ausgabe/G02_<Zeit>_<Kennung>/` liegen:

- `manifest_G02.json` und `LAUFSTATUS_G02.json`: Gesamtstatus und gespeicherte Teilergebnisse.
- `HOEHENANSCHLUSS_G02.json`: tatsächlich verwendeter Höhenansatz einschließlich der vier DGM-Stützpunkte.
- `MONTAGEPRUEFUNG_G02.json`: aus NX rückgelesene Positionen vor/nach dem Speichern, Nachladebefunde und Kontrollrechnung am Anker.
- `LADEVORGAENGE_G02.jsonl`: gezielte Nachladeereignisse.
- Haus-/Umgebungs-Unterordner: bestehende Detailprotokolle, z. B. `DGM_FLAECHENPRUEFUNG_G01e.json`.

Bei einem Fehler steht die neue `STARTFEHLER_G02_….json` unter `fehlerberichte`. Ein bereits erfolgreich gespeicherter Haus-/Umgebungslauf wird dadurch nicht gelöscht. Alle Bauteildateien mit sichern – nur eine Masterdatei zu kopieren ist keine unabhängige Projektkopie. Der 05-Weg referenziert bewusst die alten Komponenten und übernimmt keine manuellen Änderungen am alten äußeren Master.

Zum täglichen Arbeiten die gespeicherte `.prt` öffnen, nicht jedes Mal erneut erzeugen. Es gibt keinen garantierten Timeout eines blockierten nativen NX-Aufrufs. Die bekannten Stoppdateien der Haus-/Umgebungserzeuger wirken zwischen NX-Aufrufen, nicht mitten in einem laufenden Kernelaufruf.

## 6. Weitere Starter

`01_NUR_HAUS_G02_ERZEUGEN.py` und `02_NUR_UMGEBUNG_G02_ERZEUGEN.py` erzeugen getrennte Quellbereiche. Diese Einzelstarter erstellen noch keine gemeinsam montierte Gesamtbaugruppe. Danach kann `03_G02_GESPEICHERTE_TEILE_MONTIEREN.py` die erfolgreichen Teilläufe **dieses G02-Pakets** zusammenstellen; hierfür gespeicherte Quellteile schließen. Er liest keine geänderten alten Teile auf Verdacht ein.

Die gleichnamigen älteren 00-/01-/02-/03-Hauptstarter sind Kompatibilitätsnamen und leiten in diesem Paket ebenfalls zu G02. Die alten 04-G01e-Starter bleiben reine Geländetests und erledigen keine Höhenmontage. Historische Unterordner-Starter nicht für den Gesamtaufbau verwenden.

## 7. Tatsächlicher Prüfstand

Der neue Stand wird mit **680 Offline-/Simulationstests** geprüft (630 übernommene Prüfungen und 50 gezielte G02-Tests). Zusätzlich: vollständiger kombinierter Python-Ablauf mit synthetischen NX-Rückgaben, inklusive 8.282 Terrain-Teilflächen, anschließend Wiederverwendung ohne Neuimport, gezieltes Volladen und Schutz tatsächlich geänderter Quellkomponenten.

Unabhängige Open-CASCADE-Prüfungen umfassen alle 1.418 berechneten Hauskörper und elf STEP-Dateien. Der neue Höhentest liest die tatsächlichen fünf ausgewählten STEP-Quellen ein und prüft die reine Translation an allen 8.466 DGM-Knoten sowie weiteren Punkten aller 115 Quellflächen: insgesamt 9.271 Vergleiche. **Dies ist kein eigener NX-/Parasolid-Lauf und keine Vermessung.** Ergebnisse und Nachweise stehen im `PRUEFBERICHT_G02.html` und unter `berichte`.

`VORSCHAU_GESAMT_G02.html` zeigt eine lokale Browserdarstellung der Quelldaten mit demselben G02-Höhenansatz. Sie ist **kein NX-Screenshot**; Rasterzellen sind nur für die Vorschau trianguliert. Die alten Haus-/Umgebungsvorschauen zeigen dagegen bewusst ihre jeweiligen Quellen.

Offline außerhalb von NX: `python werkzeuge/PRUEFE_G02_OFFLINE.py --out NEUER_ORDNER --cad`. Für Offline-CAD-Tests werden OCP/cadquery benötigt. **In NX keine zusätzlichen Python-Pakete installieren.**

© GeoBasis-DE/LVermGeo SH/CC BY 4.0 für die übernommenen Geodaten. Quellen, Datenstände und historische Nachweise bleiben erhalten.
