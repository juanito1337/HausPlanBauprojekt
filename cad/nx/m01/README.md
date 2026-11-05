# Gemeinsame Hauptbaugruppe öffnen und Bauabschnitte ansehen

Aktueller Gesamtstand M02 vom 05.11.2026. [HAUSPROJEKT_MASTER_M01.prt](../m02/20261105T002134Z_6569c2/HAUSPROJEKT_MASTER_M01.prt) enthält Haus, Umgebung und sämtliche Bauabschnitte. Zum Wechsel die ältere Projektbaugruppe schließen. Alle 367 Parts im neuen Revisionsordner belassen.

## Einzelne Bauabschnitte

Die gespeicherten NX-Arrangements enthalten BASE, 13 Abschnittsansichten und 46 Feldansichten. Die 32 Schachtstudien zeigen den geöffneten Boden und das zugehörige Sandlager. 14 weitere Anbaufelder zeigen rote Konfliktgeometrie.

Einzelne Abschnitte lassen sich direkt über PS01.prt bis PS13.prt öffnen. Für ein bestimmtes Feld die Datei mit der bloßen Feldkennung wählen, beispielsweise [PS12-F01.prt](../m02/20261105T002134Z_6569c2/PS12-F01.prt). Diese Einstiege zeigen den jeweiligen Zustand im Gesamthaus. Die Dateien mit `_STUDY`, `_CONFLICT`, `FIELD_` oder `CONTEXT_` im Namen dienen als Komponentenquellen beziehungsweise Unterbaugruppen.

Im minimalen NX-Ladeprofil wurden alte Registerlinien in 11 Ansichten nicht beobachtet. Nur die 4 reinen Register-SECTIONs `SECTION_PS02`, `SECTION_PS03`, `SECTION_PS05`, `SECTION_PS08` zeigten eine leere Minimalansicht. In gemischten SECTIONs fehlten lediglich einzelne alte Begleitregistermarker. Ausgewählte Studienmarker und Studienkörper blieben vorhanden. Die betroffenen Abschnitts-Wrapper zeigten Haus und Gelände, alle 26 zugehörigen direkten FIELD-Einstiege ihre Feldmarkierung. Für sämtliche Registerlinien im SECTION-Teil ist vollständiges Laden der belegte Weg. Die 26 betroffenen alten Registerfelder besitzen keinen aktiven Aushubkörper und keinen nativen Aushubvolumennachweis. Historische K02-Rechenwerte einzelner Konfliktfelder sind keine aktuellen nativen Aushubmengen. Alle 24 neuen Anbaufeld-Wrapper und die zugehörigen 24 direkten FIELD-Einstiege wurden ohne Registerausnahme geprüft. Diese Anbaufelder besitzen echte Studien- oder Diagnosekörper. Rote Diagnosen erhalten weiterhin keine effektiven Aushub- oder Lagermengen.

Im geöffneten Master kann alternativ ein Feld oder Abschnitt im Baugruppenbaum ausgewählt und das [Auswahljournal](../../../renovierung/m01/select_state.py) über Werkzeuge → Journal → Abspielen ausgeführt werden. Ohne Auswahl wird BASE aktiviert. Ein einzelner Mausklick im Baum wählt zunächst nur den Knoten aus.

## Struktur und Annahmen

Das Haus ist nach Geschossen und Bauteilgruppen gegliedert. 50 Zimmer sind als Raumregister gekennzeichnet. Alle 72 Felder bleiben auffindbar. Die zusätzlichen Anbaufelder PS10 bis PS13 umfassen 10 Schachtstudien und 14 rote Konfliktansichten. Haupt- und Reservelager sind alternative Mengenansätze. Ausführungsfreigaben bleiben offen.

Die Anbausohle ist vom Nutzer mit −1,60 m gegenüber EG als reine Schnittstudie bestätigt. UK −1,50 m bleibt eine rechnerische Hilfsannahme. Tatsächliche Platten- und Fundamenthöhen sind ungeklärt. [Prüfbericht und Mengen](../../../docs/entwicklungsstand/M01-2-pruefung-2026-11-04.md).

## Reproduzieren und prüfen

```sh
python tools/nx_anbau.py build --accept-model-assumptions
python tools/nx_anbau.py check
python tools/run_checks.py
```

Der Build erzeugt neue versionierte Parts und prüft sie in eigenen NX-Prozessen. CURRENT wird erst nach erfolgreicher Gesamtprüfung aktualisiert. Der aktuelle Lauf verwendete zusätzlich ein explizites lokales Paket bereits frisch geprüfter Feld- und Geländeteile. Die vollständige Prüfung der daraus aufgebauten Hauptbaugruppe erfolgte anschließend erneut.
