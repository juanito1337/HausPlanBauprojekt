# R09 – verwendete Schnittstellen und Prüftiefe

**Keine eigene NX-2406-Laufzeit. Keine Freigabe sämtlicher Python-Bindings durch Offline-Doubles.**

## Übernommener NX-Teil

Der R06-NXAdapter bleibt unverändert unter `basis/Haus_R06/src/haus2406_r03` erhalten.
Die gemeldeten Pfad-, Enum- und Attributfehler aus den R03-Läufen werden nicht wiedereingeführt:
keine `Path.resolve()`-Abfrage in aktivem Journalcode, Einheitenprüfung mit `BasePart.Units`,
keine Metadaten auf Expressions und ausschließlich `HAUS_`-Attribute.

## Neuer STEP-Import

Die Klassenbezeichnungen und Bedeutungen sind im Siemens-NXOpen-C++-Referenztext, Version 2023,
für `NXOpen::Step214Importer` beschrieben. Verwendete Primärdokumentation, gespiegelt:
https://docs.tech-plm.ru/documentation/external/PL20230425447184281/en-US/custom_api/nx_open_c_plus_plus_ref/a74605.html
Copyright 2023 Siemens; Originalherkunft `Step214Importer.hxx`.

- Instanziierung über `DexManager.CreateStep214Importer()`.
- `ImportToOption.WorkPart`, `FileOpenFlag=false`: in das explizit neu angelegte Arbeitsteil importieren.
- `ProcessHoldFlag=true`: auf Übersetzung warten.
- `SewSurfaces`, `Optimize`, `SimplifyGeometry`, `SmoothBSurfaces` abgeschaltet.
- `Commit()` liefert laut Referenz NULL; daraus wird kein Erfolg/Fehler abgeleitet.
- Erfolgskontrolle über importierte NX-Bodies, Sheet-/Face-Zahlen und individuelle Begrenzungsboxen.

Die Python-Schreibweise dieser Bindings ist im R09-Code isoliert und wird beim Nutzer mit zwei
kleinen Originalflächen tatsächlich getestet, bevor die großen Flächen und das Haus gebaut werden.
Es wird kein alternativer API-Name auf Verdacht versucht und keine fehlende Importlizenz übersprungen.

## Baugruppenplatzierung

Siemens-generierter NXOpen-Referenztext, `Assemblies::ComponentAssembly::AddComponent`,
mit Datei, Referenzsatz, Namen, Punkt, Matrix, Layer und Ladestatus:
https://www.ugapi.com/doc/nxopen/a00564.html

R09 nutzt wie R06 die Identitätsrotation. Für eine später bestätigte Höhenverbindung wird nur die
Z-Translation der **Umgebungs-Unterbaugruppe** geändert, nicht die gespeicherte Geometrie.
`GetPosition()` und der geladene Prototyppfad werden zurückgelesen.

## Ansicht / Importdefinition

Siemens Community, ursprüngliche NX-Anwendungsfrage mit Journalzeile:
https://community.sw.siemens.com/s/question/0D54O000061xHJ8SAM/error-this-operation-can-only-be-done-on-the-display-part

R09 aktiviert ausdrücklich das Anzeigeteil, bevor `ShadedWithEdges`, isometrische Ansicht und Fit
angefordert werden. Ein Darstellungsfehler wird als Warnung protokolliert, nicht als Geometrieerfolg.

Siemens Community zur installationsseitigen Importdefinition:
https://community.sw.siemens.com/s/question/0D54O00006PpDqlSAF/step214ugdef

R09 prüft eine vorhandene lokale `step214ug.def`. Kein hartkodierter Siemens-Installationspfad.
Die Datei wird gelesen, nicht verändert. Die Programmlogik erzeugt keine eigenen Lizenz-/DEF-Dateien.

## Was die Prüfungen NICHT leisten

Offline-Doubles reproduzieren kontrollierte Antworten und bekannte Fehlerfälle. Sie sind kein
unabhängiger Signatur-, Translator- oder Parasolid-Nachweis. Selbst eine passende Körperbox
beweist nicht die Form jedes inneren Flächenpunkts. Der Runtime-Funktionstest und die erste
visuelle/technische Prüfung der erzeugten NX-Baugruppen bleiben erforderlich.
