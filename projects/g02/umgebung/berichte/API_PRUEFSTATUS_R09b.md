# R09b – Messschnittstellen und tatsächliche Prüftiefe

Stand 08.10.2026. Keine eigene Siemens NX-/Parasolid-Laufzeit; API-Signaturen/Verfügbarkeit werden im Lauf zusätzlich geprüft.

## Quellen zur Implementierung

- Originaler Python-Beispielcode des Autors NXJournaling, `Using the AskMassProps3d Method in Python for NXOpen`, 13.03.2017: `UFSession.Modeling.AskMassProps3d` liefert ein Tupel (Eigenschaften, Statistik); Oberfläche ist Eigenschaft 0. Das Beispiel verwendet Einheiten 1 = pound/inch.
  https://www.nxjournaling.com/content/using-askmassprops3d-method-python-nxopen
- Originaler Sheet-Messcode desselben Autors, `weight calculations journal`, 11.04.2018: Sheet-Körper werden mit Analyseart 2 gemessen; Flächeninhalt in Quadratzoll. Das Beispiel ist .NET, keine Bestätigung des Python-2406-Bindings.
  https://www.nxjournaling.com/content/weight-calculations-journal
- Siemens-generierter UF-Funktionsreferenztext (Spiegel, `UF_MODL_ask_mass_props_3d` und `UF_MODL_ask_minimum_dist`): Analyseart 2 = dünne Schale, Genauigkeitsmodus 2 = relative Toleranzen; beim Minimalabstand erlaubt NULL_TAG einen durch guess1 vorgegebenen Punkt. Original-Siemens-Endpunkt war beim Abruf nicht erreichbar; kein behaupteter Zugriff auf die installierte 2406-Hilfe.
  https://www.viewmold.com/ug_html_files/ugopen_doc/uf_modl/global.html
- Primärer Programmierbeitrag in Siemens Community zum Minimalabstand und NXOpen.UF.Modeling:
  https://community.sw.siemens.com/s/question/0D54O000061xORjSAM/check-if-point-lies-within-closed-curve-loop
- Primäres veröffentlichtes NXOpen-Projekt des Autors Plus-1000 mit Punkt-zu-Fläche-Messung über Modeling.AskMinimumDist:
  https://github.com/Plus-1000/Create-point-set-on-face-with-NX-Open

R09b verwendet ausdrücklich die Python-Eigenschaft `UFSession.Modeling`, nicht den anders benannten .NET-Zugriff `Modl`. Die beiden numerischen Messroutinen sind in `r09/nx_adapter.py` isoliert. Keine Installation zusätzlicher Pakete in NX, keine geratenen Fallback-API-Namen.

## Details

`AskMassProps3d([body.Tag], 1, 2, 1, 1.0, 2, [1e-7] + [0.0]*10)` misst jeweils EINEN Sheet-Körper. `props[0]` wird mit 25.4² von in² in mm² umgerechnet. Keine Material-/Dichtezuweisung am Part. Nur Fläche wird verwendet, keine WCS-abhängigen Schwerpunktkoordinaten. Geforderte Integrationstoleranz ist kein allgemeiner Nachweis der numerischen Genauigkeit.

`AskMinimumDist(0, body.Tag, 1, xyz, 0, [0,0,0])` verwendet einen über Koordinaten beschriebenen Messpunkt (UF NULL_TAG = 0). Eine .NET-artige NXOpen.Tag.Null-Eigenschaft wird im Python-Modul nicht vorausgesetzt. Der Python-Rückgabevertrag wird auf drei Felder, endliche Zahlen und konsistente Messpunkte geprüft. Kein persistierendes NX-Punktobjekt. Abstände werden ausschließlich im Millimeter-Part an dessen eigenen Body-Tags gemessen, nicht an Baugruppenkomponenten.

R09b behandelt einen API-/Messfehler als Abbruch mit Diagnose, nicht als bestandene Prüfung. Die automatische Importprobe verwendet zwei echte Quellflächen, an denen Inhalt und 58 Quellpunkte gemessen werden. Das ist der erste Test der neuen Aufrufe in der tatsächlichen Installation.

## Aussagegrenze

Ein endlicher, gerichteter Quellpunktvergleich + Körperboxen + Flächeninhalte beweist keine vollständige Hausdorff-Gleichheit, keine in jeder Größe lückenfreie Topologie und keinen vermessenen Bewuchs. Die Prüfung soll insbesondere verlorene Körper, größere Form-/Skalierungsänderungen und doppelte/fehlende Teilflächen erkennen, ohne eine bloße zusätzliche Face-Unterteilung als Fehler zu werten.

Das R09a-Protokoll des Nutzers enthält 49 erwartete und 56 gezählte Faces, jedoch keine gemessenen Abstände oder Flächen. Die Erklärung „reine Flächenteilung“ ist daher eine Arbeitshypothese, kein bestätigter Befund zur konkreten importierten NX-Geometrie.
