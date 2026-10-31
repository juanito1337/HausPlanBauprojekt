# HAUS MAIN01-A01 – Dachneigungen und Gaubenanschlüsse

**Haus allein, kein STEP-Import, kein Gelände und keine Vegetation.**
Der Starter heißt weiterhin `00_HAUS_MAIN01_ERZEUGEN.py`. Die Patchkennung lautet jetzt **MAIN01-A01-DACHANSCHLUSS**.

## Was geändert wurde

Die zwei in den Schnitten numerisch beschrifteten Hauptneigungen bleiben unverändert: **45° am Hauptdach (P13, Seite 1)** und **28° am Dach der ehemaligen Schwimmhalle (P18, Seite 1)**. Diese waren bereits in MAIN01 enthalten.

Die drei flacheren Gaubendächer endeten bisher mit festen Hinterkanten rund 255/265/255 mm über der dortigen Hauptdachfläche. Sie werden jetzt bis zum berechneten Schnitt mit der Wirtsdachfläche verlängert. Vorderkanten, Dachvorderhöhe, Fensterdaten und die bisherigen geschätzten Gaubenneigungen bleiben erhalten. Gaubenwangen werden bis zum selben Anschluss verlängert; künstliche hintere Verschlusswände entfallen. Keine neue Dachhaut über die vorhandene gelegt.

**Kein neuer Winkel wurde aus dem Video gemessen.** Die Gaubenwinkel von rund 12,7° / 15,7° / 12,9° sind aus den alten Modellpunkten berechnete Näherungen, keine Planwerte. Sie sind jetzt als eigene Schätzparameter `GAUBE_…_WINKEL_MODELL` ausdrücklich geführt. Die 28° aus Schnitt B–B gelten nicht automatisch für die Gauben. Der bisherige 35°-Garagenwinkel bleibt ebenfalls unbestätigt. Die flache Balkonzugangshaube und das vorläufige Flachdach sind unverändert.

## In NX starten

1. Das ganze ZIP in einen neuen Ordner entpacken, z. B. `C:\NXHaus\MAIN01_A01`. Nicht über MAIN01 kopieren. Eigene Arbeit sichern und gleichnamige alte Projektteile manuell schließen. Alte Dateien auf der Festplatte behalten.
2. Im nativen NX-Dateimodus über „Journal abspielen / Play Journal“ ausdrücklich `00_HAUS_MAIN01_ERZEUGEN.py` **aus diesem neuen A01-Ordner** auswählen. Neben dem Starter liegen `src`, `data` und `quellen`.
3. „Ja“ erzeugt das Haus mit dokumentierten Näherungen; „Nein“ nur das Referenzgerüst. Kein separates CHECK-Journal starten. Die Teile werden in einem neuen Ausgabeordner gespeichert und geprüft.

Erwarteter Modellumfang: **15 Komponenten und 1.418 Körperaufträge**. Der alte Stand hatte 1.425 Körper; die sieben entfallenen Teilkörper hängen mit der Gaubenwangen-/Rückabschlusszerlegung zusammen, nicht mit gelöschten Fenstern oder Balkondetails. Konstruktionsparameter sind weiterhin nur teilweise partübergreifend assoziativ. Änderungen der Gaubenwinkel im Datensatz steuern einen **Neuaufbau**, nicht automatisch jede nachträgliche Änderung in NX.

## Als neuen Main-Stand sichern

Nach erfolgreichem NX-Lauf den **gesamten** Ausgabeordner sichern, nicht nur `HAUS_MASTER.prt`. Die vertrauten Dateinamen `BASELINE_MAIN01.json`, `manifest_MAIN01.json` und `LETZTER_MAIN01_LAUF.json` bleiben bestehen; Inhalt und Part-Attribut `HAUS_MAIN_REVISION` kennzeichnen MAIN01-A01. Zum Weiterarbeiten gespeicherte `.prt`-Dateien öffnen, nicht das Journal wiederholt starten. Manuelle Änderungen älterer Parts werden nicht automatisch übernommen.

`LAUFSTATUS_MAIN01.json` und `LAUFZEIT_MAIN01.jsonl` dokumentieren den Lauf. Eine leere `STOP_MAIN01.txt` im laufenden Ausgabeordner fordert einen Stopp zwischen den NX-Aufrufen an, keinen harten Abbruch eines laufenden Kernelaufrufs.

## Prüfergebnis und Grenzen

**87 Offline-/Simulationstests (57 aktualisierte Basistests + 30 neue Dachtests)** sowie unabhängiger Aufbau aller **1.418 Körper mit Open CASCADE**. Testdoppel sind keine echten NX-Parts. **Kein eigener NX-/Parasolid-Lauf**, keine fertigen `.prt`-Dateien im ZIP und keine Laufzeitgarantie.

Alle drei hinteren Gaubennähte treffen im Rechenmodell das Hauptdach. Die Rückkante wird an allen Schnitten mit den stückweise ebenen Wirtsdachgebieten geprüft. Das ist kein Nachweis von Blechen, Abdichtungen, Lastabtrag oder tatsächlichen Bestandsmaßen.

Zehn bekannte Haus-Anbau-Überschneidungspaare und zwei teilweise blockierte Innentüröffnungen bleiben offen. Keine neuen gezählten Paare. Der schräge Verlauf der Frontwangen, reale Traufen, Aufschieblinge, Dachschichten, Dachstuhl und Befestigungen sind nicht vollständig rekonstruiert. MAIN01-A01 ist eine verbesserte Arbeitsbasis, keine Bau- oder Tragwerksfreigabe.

## Nachweise

- `PRUEFBERICHT_DACH_A01.pdf` / `.html`: Winkelquellen, Videobilder, Modellkorrektur und Grenzen.
- `VORSCHAU_HAUS.html`: aktualisierte Rechengeometrie, kein NX-Screenshot; Schalter „Dach / Gauben“.
- `berichte/DACHPRUEFUNG_MAIN01_A01.json`: reproduzierbare Vorher-/Nachher-Werte.
- `data/DACHWINKEL_UND_GAUBEN_A01.csv`: Winkelregister (keine Vermessungstabelle).
- `archiv/HAUS_MAIN01_VOR_DACHPRUEFUNG.json`: unveränderte Ausgangsdaten; alte Berichte sind historische Nachweise.
- `quellen/P13.pdf`, `quellen/P18.pdf`, `quellen/P05.pdf`, `quellen/P19.pdf`: Originalpläne.

Offline außerhalb von NX: `python werkzeuge/PRUEFE_MAIN01_OFFLINE.py`; optional `--cad` mit lokal verfügbarem OCP/Open CASCADE. In NX selbst keine zusätzlichen Python-Pakete nachinstallieren.
