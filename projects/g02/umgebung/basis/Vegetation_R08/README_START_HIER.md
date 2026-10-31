# Vegetationsreferenz R08 – für das NX-Hausprojekt

## Ergebnis und Grenzen

Separate Ergänzung zu Haus R06 und Gelände R07. **Kein neues vollständiges Hauspaket, keine fertigen NX-PRT-Dateien und keine parametrischen Einzelbäume.**

Die STEP-Dateien enthalten tatsächlich erzeugte CAD-Flächen. Das bDOM nennt den **07.04.2023**, das DOP den **12.05.2025** als Aktualität. Diese Zeitstände werden nicht gleichgesetzt. DGM: Jahreskennung 2023; genaues Erfassungsdatum und konkretes vertikales Metadatum bleiben unbekannt. bDOM-Metadaten werden NICHT auf das DGM übertragen.

**382 offene Vegetationsflächen in 8 räumlichen Prüfbereichen**, dazu 202 Bodenreferenzflächen für erkannten niedrigen Bewuchs. Das sind weder 8 gezählte Bäume noch eine vollständige Bestandserhebung. Die feine Zellaufteilung ist eine CAD-Darstellung, keine bewiesene biologische Einzelgliederung. Keine Unterseite, Stämme, Äste, Wurzeln, Arten oder Stammdurchmesser sind konstruiert.

## Direkt in NX ansehen

Das ZIP vollständig in einen neuen Ordner entpacken. Zunächst **die gemeinsame Datei**

`CAD/GELAENDE_UND_VEGETATION_R08.step`

über den vorhandenen STEP-Import in NX als **separates neues Teil** importieren. Einheit Millimeter; keine zusätzliche Skalierung. Die Datei enthält Gelände und Vegetation als benannte Gruppen. Keine Journaldatei erforderlich; die Python-Dateien unter `werkzeuge` sind ausschließlich Offline-Werkzeuge, nicht in NX ausführen.

Alternativen:

- `CAD/VEGETATION_OBERFLAECHEN_R08.step`: nur V01 bis V08, 382 offene Oberflächen.
- `CAD/GRUENFLAECHEN_NUR_BODENREFERENZ_R08.step`: nur die Bodenprojektion F01, keine tatsächliche Pflanzenhöhe.
- `CAD/GELAENDE_R07_UNVERAENDERT.step`: bytegleiches Gelände aus R07.

**Nicht die gemeinsame Datei UND die Einzeldaten zugleich einfügen:** Das würde Geometrie duplizieren. Erst die importierte Szene prüfen und bei Bedarf als eigenes `.prt` speichern. R06-Dateien unverändert behalten.

Offene Flächen sind beabsichtigt. Darstellung ohne Stämme oder Kronenunterseite ist kein gescheiterter Körperaufbau. Für diese nicht sichtbaren Teile fehlen Nachweise. An den Rändern kann die Auswahl löchrig aussehen, weil keine unbelegten Zellen ergänzt werden.

## Koordinaten und Höhen – entscheidend

X/Y entsprechen der vorhandenen R06/R07-Kartenbasis. Formel für Zeilenvektoren:

`local_m = (EN_m - origin_EN_m) @ basis.T`

`EN_m = local_m @ basis + origin_EN_m`

Die Matrixzeilen und der Ursprung sind in `data/BAUAUFTRAG_VEGETATION_R08.json` vollständig angegeben. Die Übernahme wurde gegen die R06-Grundstücks-/Hauspunkte und separat gegen sämtliche 8.466 R07-CSV-Stützpunkte geprüft; keine Scherung und keine Größenänderung.

**Z = 1.000 × Quellhöhe in Metern. Kein Haus-Höhenoffset abgezogen.** Die Daten liegen daher ungefähr auf 30.000 bis 34.000 mm, nicht auf EG ±0,00. Der bDOM-Höhenbezug ist EPSG:7837 / DHHN2016 laut `.pp`. Der konkrete DGM-Höhenbezug und die absolute Höhe unseres EG-Nullpunkts sind noch nicht bestätigt.

Die gemeinsame STEP ist eine Darstellung der übergebenen Quellhöhen. Sie ist noch kein vermessener Anschluss an das Haus. Zum späteren Einfügen in HAUS_MASTER ist der bestätigte Höhenanschluss zu verwenden, dann gleichartig für Gelände und Vegetation. **Nicht nur die Pflanzen nach unten verschieben und das Gelände unverändert lassen.**

## Inhalt und Nachvollziehbarkeit

`VORSCHAU_VEGETATION_R08.html` ist die offline nutzbare, drehbare Vorschau mit Gruppenschaltern und Luftbild. Sie zeichnet Dreiecke aus denselben Stützpunkten; zwischen vier Punkten kann sie von der bilinearen STEP-Fläche abweichen. Kein NX-Screenshot.

`PRUEFBERICHT_R08.pdf` erläutert Quellen, Auswahl, Teilabdeckung und Import. `data/VEGETATIONSREGISTER_R08.csv` und `data/AUSWAHL_R08.json` enthalten IDs, Zeitstände, Kriterien und vorläufige Höhendifferenzen. Die Höhen sind **keine bestätigten aktuellen Baumhöhen**.

Die betrachtete Vegetationszone reicht im Grenzbereich bis maximal 2 m über die bisherige Kartenkontur hinaus. Dadurch bleiben randnahe Kronen-/Heckenbereiche sichtbar. Stammposition, Eigentum und rechtlicher Grenzverlauf werden daraus nicht festgestellt. Kein Wurzel- oder Baumabstandsmodell.

Quellenzuschnitte als GeoTIFF, originale `.pp`-/`.tfw`-Begleitdateien und decodierte Metadaten sind enthalten. Die beiden vollständigen 1-km-Kacheln werden nicht nochmals dupliziert; ihre Hashwerte stehen im Quellenregister. Originaluploads bitte aufbewahren.

## Prüfung

25 tatsächliche Offline-Prüfungen bestanden: Raster, Transformation, Auswahlregeln und STEP-Rückimport mit Open CASCADE. Alle 585 Flächen der gemeinsamen Datei sind rechnerisch gültig; keine Volumenkörper. Rückimport: 3.504 Punkt-zu-Fläche-Vergleiche an den Vegetations-/Bodenreferenzflächen. Die numerische CAD-Toleranz ist KEIN Genauigkeitsnachweis der Luftbilder oder Pflanzen.

**Kein eigener NX-2406-Importtest.** Keine Aussage über vollständige Wiedergabe aller Pflanzen, heutige Vegetation, Hausgeometrie, Statik oder Leitungen. Haus R06, seine offenen Konflikte und die unbekannten Leitungstiefen werden durch diese Ergänzung nicht verändert.

Offline-Neuerzeugung (nicht in NX, benötigt externe Python-Pakete):

```text
python werkzeuge/ERZEUGE_STEP_OFFLINE.py --out NEUER_LEERER_ORDNER
python werkzeuge/PRUEFE_R08_OFFLINE.py
```

Der Erzeuger verarbeitet die bereits geprüfte Rasterauswahl; eine Änderung der Prüfpolygone allein berechnet keine neue Segmentierung. Neue Auswahl und neue Quelldaten müssen erneut fachlich geprüft und als passende Raster-/Bauauftragsdaten bereitgestellt werden.

© GeoBasis-DE/LVermGeo SH/CC BY 4.0. Für dieses Projekt wurden Ausschnitte, Masken, Abgrenzungen und CAD-Ableitungen erzeugt.
