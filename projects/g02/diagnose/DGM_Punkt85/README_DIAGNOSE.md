# DGM-Punktdiagnose – kein Hausneuaufbau

## Der aktuelle Befund
Der Screenshot vom 09.10.2026 zeigt **R10**, DGM Sheet 1, Punkt 85:
`1000.049994 mm > 0.250 mm`. Er nennt das Haus als bereits gespeichert und
dateigeprüft. Die Original-JSON dieses neuen Abbruchs liegt hier noch nicht vor.
Der Screenshot ist nicht mit dem älteren R09d-Flächeninhaltsfehler zu verwechseln.

Die unveränderte STEP-Quelle wurde erneut mit Open CASCADE eingelesen. Der
Quellpunkt 85 liegt darin numerisch praktisch auf der Fläche (unter 0,000001 mm).
Auch acht ausgewählte Nachbar-/Randpunkte wurden geprüft. Dies sind keine Messungen
an der in deiner Sitzung importierten NX-Geometrie.

Auffällig: Der Abstand des Quellpunkts 85 zum benachbarten Rasterpunkt 84 beträgt
rechnerisch 1000,0499988 mm und stimmt damit fast mit der angezeigten Abweichung
überein. **Eine falsche Nahpunktsuche ist deshalb eine plausible Erklärung, kein
bewiesener Fehlergrund.** Eine Importänderung bleibt ebenfalls zu prüfen.

Die DGM-Quelldefinitionen in R10 und R11a sind identisch. Auch deren grundlegende
Methode `SceneAdapter.surface_distance_mm` in `r09/nx_adapter.py` (Zeilen 93–97)
ist unverändert. R11a reduziert den Prüfaufwand, ist aber keine bestätigte Korrektur
dieses Punktabstandsproblems. Das bloße Auslassen von Punkt 85 wäre kein Nachweis.

## Vorhandenes Modell behalten
Keine Modelldateien löschen oder den Gesamtstarter wiederholen. Dein erfolgreich
gespeichertes Haus bleibt verwendbar als bisheriges Prüfmodell. Die offene
Geländefrage bestätigt oder widerlegt nicht die Hauskonstruktion.

## Diagnose ausführen – nur bei bereits geladenem Geländeteil
1. Dieses kleine ZIP separat entpacken. **Keine Dateien des Hausprojekts ersetzen.**
2. In derselben NX-Sitzung das bereits importierte `01_GELAENDE_R09.prt` separat
   als Arbeits- **und** Anzeigeteil anzeigen. Nicht im Haus-Baugruppenkontext prüfen.
   Das Teil muss in Millimetern vorliegen und genau einen offenen Flächenkörper
   mit höchstens acht Einzelflächen enthalten. Andernfalls stoppt die Diagnose.
3. Über deinen bisherigen Journalstart `DIAGNOSE_DGM_PUNKT85.py` wählen.
   Das Journal erzeugt **keine Geometrie**, importiert nichts, verschiebt nichts,
   schaltet keine Teile um und speichert keine Parts.
4. Die neue Datei `DGM_PUNKTDIAGNOSE_<Zeit>_<Kennung>.json` hochladen.
   Sie steht neben dem Journal; falls dort keine Schreibrechte bestehen, im
   temporären Benutzerordner. Der vollständige Pfad erscheint im NX-Informationsfenster.
   Zusätzlich bitte den im Screenshot genannten Originalbericht hochladen:
   `STARTFEHLER_R09_20261009_155712_afeb149d.json`.

**Ist NX schon geschlossen und das Geländeteil nicht mehr geladen, dafür keinen
neuen vollständigen Hauslauf starten.** Zunächst nur den vorhandenen Startfehlerbericht
hochladen. Das Diagnosejournal enthält absichtlich keinen automatischen STEP-Import.

## Was gemessen wird
Vier unveränderte Quellpunkte (84, 85, 86, 168) werden geprüft. Bei einer einzelnen
DGM-Face erfolgen zwölf NX-Abfragen: bisheriger Körperabstand, Abstand zur tatsächlichen
Face ohne Startpunkt, Abstand zur tatsächlichen Face mit dem Quellpunkt als Startschätzung.
Alle Ergebnisabstände und zurückgegebenen Koordinaten stammen aus NX, nicht aus
den Sollwerten. Ausnahmen werden als solche protokolliert, nicht als Nullabstand.

Die Grenze bleibt 0,25 mm. Es findet **keine automatische Freigabe und keine
Korrektur** statt. Unterschiedliche Ergebnisse werden sichtbar gemacht, nicht
nachträglich durch den am besten passenden Wert ersetzt. Die Dateiausgabe wird
vor und nach jeder Messung aktualisiert. Auch dieser kleine Test kann auf einen
laufenden NX-Aufruf warten; keine garantierte Laufzeit und kein Abbruch-Thread.

## Prüfstatus
18 Offline-Tests für Ergebnisprüfung, Fehlerprotokollierung, begrenzte Aufrufzahl
und den Diagnoseablauf bestehen. Dabei wurden auch künstliche widersprüchliche
Abstände eingespeist. **Das sind keine tatsächlich beobachteten neuen NX-Messungen.**
Kein eigener NX-Lauf. Separat sind neun echte Punktabstände zur unveränderten
STEP-Quelldatei mit Open CASCADE geprüft; Ergebnis siehe Quellenprüfungs-JSON.

Die Originalkoordinaten beziehen sich auf die Quelldarstellung in Millimetern.
Eine zuvor manuell verschobene/umgebaute Geländegeometrie ist mit dieser Referenz
nicht direkt vergleichbar. Der geladene Part wird nicht als identisch zur STEP-Quelle
behauptet; seine echte Herkunft/Änderungshistorie ist nicht unabhängig geprüft.

Offline-Tests (nicht in NX): `python TESTE_DIAGNOSE_OFFLINE.py`.
