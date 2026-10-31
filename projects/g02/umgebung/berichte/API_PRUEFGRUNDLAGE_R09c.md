# API-Prüfgrundlage R09c

Stand: 08.10.2026. Keine installierte NX-2406-API-Dokumentation und kein NX-Prozess in
dieser Arbeitsumgebung. Die tatsächliche Verfügbarkeit, Python-Überladungsauswahl,
Einheitenauflösung und Messrobustheit bleiben Laufzeitprüfpunkte.

## Direkte Beobachtung aus dem Nutzerbericht

Der bisherige `UF.Modeling.AskMassProps3d`-Aufruf wurde von NX angenommen, war aber bei
der zweiten Testfläche nicht erfolgreich (820001). Der Bericht gibt keine Beschreibung
der internen Fehlerursache. Es wird keine unbestätigte Fehlercodetabelle ergänzt.

## Quellen für den Ersatzweg – keine Bestätigung des Nutzerlaufs

- Originalbeitrag / eigener Beispielcode des Autors NXJournaling (18.12.2023):
  „Get the Area from the Face Created by Face from Curves“. Verwendet
  `MeasureManager.NewFaceProperties` mit Flächeneinheit, Längeneinheit,
  Genauigkeitsparameter und der gesamten `GetFaces`-Auswahl eines Körpers;
  Rückgabeeigenschaft `Area`. Sprache VB.NET, nicht der hier noch ungetestete Python-Aufruf.
  https://www.nxjournaling.com/content/get-area-face-created-face-curves
- Originale Python-Diskussion zur `AskMassProps3d`-Rückgabe:
  https://www.nxjournaling.com/content/using-askmassprops3d-method-python-nxopen
- Siemens-generierte Referenztexte in externen Spiegeln wurden ergänzend für Signaturen,
  Einheiten und Lebensdauer gelesen; keine Behauptung einer aktuellen offiziellen
  NX-2406-Installationshilfe:
  https://www.ugapi.com/doc/nxopen/a03996.html
  https://nxopencsdocumentation.thescriptingengineer.com/NX2022_1/NXOpen.MeasureFaces.html
  https://www.viewmold.com/ug_html_files/ugopen_doc/uf_modl/global.html

`MeasureFaces.Dispose()` gibt das vorübergehende Messobjekt frei; `CreateFeature()` wird
nicht verwendet. Die benannten Einheiten werden explizit abgefragt. Schlägt diese
Abfrage fehl, stoppt die Messung, statt eine Einheit stillschweigend anzunehmen.

UF-Ersatzweg: type=2 (dünne Schale), units=3 (g/cm), accuracy=1 (fester Parameter),
acc_value[0]=0.999 und 0.9999. Erster mass_props-Eintrag ist Fläche, hier cm² → mm².
Kein Material wird am Körper gesetzt. Der zusätzliche Stabilitätsvergleich und der
Referenzvergleich gehören zur Projektlogik, nicht zu einer zugesagten NX-Genauigkeit.

## Grenze der Tests

Die Tests mit simulierten NX-Antworten bestätigen Verzweigungen, Auswahl, Einheitenfaktoren,
Fehlerbehandlung und Berichtsausgabe. Sie beweisen weder das Verhalten des NX-Kernels
noch die Genauigkeit des NX-Messalgorithmus. Die zusätzlichen Open-CASCADE-Prüfungen
messen echte STEP-Geometrie mit einem anderen CAD-Kernel; auch das ist kein NX-Test.
