# M01 – eine gemeinsame Hauptbaugruppe

Der aktuelle vollständig geprüfte Lauf steht in `CURRENT.json`. Sein Eintrag `master` ist relativ zu diesem Ordner. Die Hauptdatei heißt **HAUSPROJEKT_MASTER_M01.prt**. Nur eine Hauptdatei öffnen; alle zugehörigen Komponenten im Lieferordner belassen.

**Aktuelle Hauptdatei:** [HAUSPROJEKT_MASTER_M01.prt öffnen](20261103T005043Z_07d05f/HAUSPROJEKT_MASTER_M01.prt). Revision M01, Lauf `20261103T005043Z_07d05f`, 03.11.2026: 199 native Parts, 265 Baumknoten. Neuaufbau sowie frisches und verschobenes Wiederöffnen mit NX 2406.6000 bestanden. Je Lauf wurden 264 Komponentenschaltungen und 23 Zustände geprüft. [Prüfbericht und Grenzen](../../../docs/entwicklungsstand/M01-pruefung-2026-11-03.md).

## Bedienung

- Haus, Keller, Erdgeschoss, Dachgeschoss, Dach, Außenbauteile und Umgebung über den NX-Baugruppenbaum ein-/ausblenden.
- Unter `Bauzustaende_Einzelfeldstudien` liegen alle 13 Sektionen und 72 Feldregistereinträge. 22 besitzen eine native Geometriestudie. Übrige Felder behalten ihren ungeklärten/gesperrten Status in den Komponentenattributen, ohne erfundene Aushubkörper.
- Für eine vollständige Feldansicht im Baugruppenbaum genau die gewünschte native **Feld_...**-Komponente auswählen, anschließend [Auswahljournal](../../../renovierung/m01/select_state.py) über NX „Journal wiedergeben“ starten. Das blendet das Bestandsgelände und die anderen Feldstudien aus. Eine leere Auswahl stellt BASE wieder her. Das Journal speichert nicht. Der programmgesteuerte Schaltkern wird nativ geprüft; der interaktive Menü-/Auswahlablauf braucht eine gesonderte Sicht-/Bedienabnahme.
- Manuell: Bestandsgelände ausblenden, einen Feldknoten einblenden, anschließend dessen Rollen wählen. NX kann beim Einblenden eines Elternknotens auch vorher verborgene Kinder einblenden. Für dieselbe Ansicht wie im Auswahljournal `cut_soil` und `pile_main` einblenden, `excavation` und `pile_reserve` ausblenden. Haupt- und Reservelager nicht als zwei gleichzeitig vorhandene Lager deuten. Das Auswahljournal übernimmt diese Schritte gemeinsam.
- Räume stehen unter den Geschossen als **Raumregister**, ohne erfundene Raumkörper oder Wandzuordnung. Historische Wohnung A/B sind Quellenbezüge, keine bestätigte heutige Wohnungsaufteilung. Die Raumregister sind zunächst ausgeblendet; ihre Knoten und Attribute bleiben im Baum verfügbar.

Der lokale Schnittboden ersetzt in der Feldansicht nur einen Studienausschnitt; er ist kein vollständiges Grundstücksgelände. Mehrere gleichzeitig eingeblendete Felder sind ein geometrischer Vergleich, keine kumulative Baufolge oder Netto-Gesamtmenge. Keine Ausführungsfreigabe.

## Laden nach einem Umzug

`git lfs pull` ausführen. Alle Unterordner des gewählten M01-Laufs als NX-Komponentensuchverzeichnisse eintragen und vollständig laden. Frisches Öffnen am Erstellort sowie Öffnen einer verschobenen Kopie werden getrennt geprüft. Die Hauptdatei allein enthält nicht alle Bauteildaten.

## Erzeugen und prüfen

```sh
python tools/nx_master.py build --nx-root C:/Siemens/NX2406 --accept-model-assumptions
python tools/nx_master.py check
python tools/nx_project.py check
python tools/run_checks.py
```

Nur bestätigte aktuelle G02/K02-Lieferungen dienen als Quellen. M01 speichert eigene Kopien und einen eigenen Struktur-, Sichtbarkeits- und Mengenprüfnachweis. Der Erzeuger startet ausschließlich eigene frische NX-Prozesse. Ein belegter eigener Build-Lock führt zum Abbruch; auf ein fremdes laufendes `run_journal` wartet er vor jedem Teilschritt bis zu 30 Minuten. Keine fremde Sitzung wird beendet. Nicht beteiligte Programme können diese Sperre umgehen, daher ist sie kein allgemeines NX-Lizenzreservierungssystem.
