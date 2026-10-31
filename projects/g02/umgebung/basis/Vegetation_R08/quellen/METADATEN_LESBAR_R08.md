# Tatsächlich mitgelieferte Metadaten

## bDOM – Mehrfachdownload_UfZKh8_S7OWr5.zip
- Datei: bdom20nc_32_568_6003_1_sh_2023.tif
- Feld Aktualitaet: 07.04.2023
- Bildflugnummer: TK1_23
- Herstellungsdatum: 28.06.2023
- Aktualitaet_Kachelinformation: 06.06.2024
- Koordinatenreferenzsystem_Lage: 25832
- Koordinatenreferenzsystem_Hoehe: 7837
- Raster tatsächlich: 5000 x 5000, 0,2 m, 1 Band, float32.
- Die .pp nennt Farbtiefe 16 und Datentyp IEEE floating point data. Das tatsächliche Rasterformat float32 wird direkt gelesen, ohne angenommene 16-Bit-Höhenskalierung.
- Standardabweichung_Lage 20 / Standardabweichung_Hoehe 40 stehen ohne explizite Einheit im Begleittext. Keine daraus berechnete grundstücksspezifische Genauigkeitsgarantie.

## DOP – Mehrfachdownload_1Wgwca_N4MVgo.zip
- Datei: dop20rgbi_32_568_6003_1_sh_2025.tif
- Feld Aktualität: 12.05.2025
- Bildflugnummer: TK1_25
- Herstellung des DOP: 26.08.2025
- Spektralkanäle: RGBI
- Koordinatenreferenzsystem_Lage: 25832
- Koordinatenreferenzsystem_Höhe: 7837
- Bezugsfläche: bDOM. Diese Nennung macht das Bild selbst nicht zu einem Höhenraster.
- Raster tatsächlich: 5000 x 5000, 0,2 m, 4 Bänder, uint8. Band 4 wird entsprechend RGBI als NIR gelesen; kein Alpha-Kanal.

## DGM1 aus R07
Jahreskennung 2023, aber weiterhin keine eigenen Metadaten zum Erfassungsdatum oder konkreten Höhensystem. Die bDOM-Metadaten dürfen nicht dem DGM zugewiesen werden.

## Auswahl, keine vollständige Vegetationsinventur
Visuelle Prüfpolygone im DOP; Hilfsindex (NIR_DN-R_DN)/(NIR_DN+R_DN) >= 0,18; vorläufige Differenz bDOM-DGM >= 0,6 m. Mindestens 25 zusammenhängende Pixel. Index aus 8-Bit-Bildwerten, nicht kalibriertes Reflexions-NDVI; keine Aussage über Pflanzengesundheit. Dachbereiche werden ausgeschlossen. Keine künstliche Glättung oder räumliche Vergrößerung der Vegetationsauswahl.

Grenzsaum: höchstens 2 m außerhalb der grafischen Grundstückskontur werden mitbetrachtet, aber Eigentum und Stammstandort bleiben unbekannt. Niedriger Bewuchs F01 wird nur auf das DGM projiziert, ohne künstliche Pflanzenhöhe.

## Allgemeine externe Methoden-/Produktquellen (keine Daten für einzelne Pflanzen)
LVermGeo SH: ATKIS Digitale Geländemodelle (DGM und bDOM), Produktbeschreibung.
https://www.schleswig-holstein.de/DE/landesregierung/ministerien-behoerden/LVERMGEOSH/Service/serviceGeobasisdaten/geodatenService_Geobasisdaten_DGM
LVermGeo SH: Amtlicher Höhenbezug, DHHN2016/NHN.
https://www.schleswig-holstein.de/DE/landesregierung/ministerien-behoerden/LVERMGEOSH/Themen/themaRaumbez/themaRaumDhhn2016
USGS: NDVI, the Foundation for Remote Sensing Phenology – nur methodischer Hintergrund. Die verwendeten Orthophoto-DN sind kein kalibriertes Reflexionsprodukt.
https://www.usgs.gov/special-topics/remote-sensing-phenology/science/ndvi-foundation-remote-sensing-phenology
