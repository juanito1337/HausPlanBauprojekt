# Projektstand und gesicherte Übergabe

Stand dieser Übergabe: **31.10.2026**.

## Was tatsächlich verfügbar ist

G02 ist vollständig aus `NX_GESAMT_G02_HOEHENBEZUG.zip` übernommen: 543 Dateien unter `projects/g02/`. Das Quellarchiv, die einzelnen Dateihashes und ihre Zielorte sind im Importmanifest dokumentiert. Kein G02-Programm und keine Geometrie wurde für die Git-Übergabe verändert. Die internen Paketregister (542 Einträge im äußeren Register plus Registerdatei selbst) bleiben gültig.

Der Nutzer meldete: „Die letzte Ausführung ist erfolgreich durchgelaufen und hat die vorhandene Umgebung korrekt erstellt.“ Das ist ein **Nutzerbericht zum G02-Lauf**, kein hier nachträglich ausgeführter NX-Test und keine bautechnische Bestandsfreigabe. Seine nativen `.prt`-Dateien und das erfolgreiche lokale Laufmanifest sind in diesem Übergabeverzeichnis nicht enthalten.

K01: Das frühere vollständige Renovierungs-ZIP war in der anschließenden Bereitstellung nicht vorhanden. Erhalten blieb `K01_Unterlagen_NEU.zip`. Dessen 8 Dateien liegen unverändert in `renovierung/k01_unterlagen/`. Es fehlen insbesondere die K01-Journale, der Maßnahmen-Erzeuger, die separat ausgelieferte ursprüngliche Plan-JSON und die Maßnahmen-STEP-Geometrien. In der erhaltenen HTML-Vorschau wurde jedoch ein JSON-Studienplan gefunden und ohne Ausführung von JavaScript unter `renovierung/recovered/RENOVIERUNGSPLAN_AUS_VORSCHAU.json` extrahiert. Dieser enthält 62 Zustandsdatensätze und Verweise auf fehlende CAD-Dateien; er ist kein wiederhergestellter NX-Erzeuger. Frühere Berichte über Tests sind nur historische Dokumente; sie ersetzen die fehlenden Dateien nicht.

## Aktiver Hausstand

MAIN01-A01: 15 Komponenten, 1.418 Körperaufträge. Haus-/Fensterstand nach Videoabgleich; Balkon rechts aus Straßensicht, angenäherte Stützen/Bekleidung, Balkonzugang, Kellerabgang-Geländer, Fallrohrreferenzen, Dachfenster und Solarfeldhüllen. Hauptdach 45°, ehemaliges Schwimmhallendach 28°. Gaubenwinkel und tatsächliche Anschlüsse teilweise geschätzt. Kein vollständig auskonstruiertes Dachtragwerk nach Statik.

## Umgebung und Höhen

Gelände plus Vegetationsgruppen V01/V02/V03/V05 und Kartenlinien. Quellteile behalten ihre Quellhöhen. Die übergeordnete G02-Montage versetzt die gesamte Umgebung gemeinsam um **−31.362,49870845903 mm**; X/Y und Rotation unverändert. Das Haus bleibt bei EG-Fertigfußboden ±0,00.

Bezug: interpolierter DGM-Wert 31,062498708 m am lokalen Punkt (0,−500 mm), angenommene Außenhöhe −0,300 m. Die Übertragung der historischen Außenkote auf diesen konkreten Punkt ist **nicht vermessen**. Auch Datum und heutige einzelne Fassadenanschlüsse sind nicht bestätigt. Ein sichtbarer passender Anschluss ist nicht automatisch ein Vermessungsnachweis.

DGM: Jahreskennung 2023. bDOM: Aktualität 07.04.2023; Luftbild: Aktualität 12.05.2025. Unterschiedliche Datenstände nicht als identischen heutigen Bewuchs behandeln. Vegetationsflächen sind keine Vermessung von Stämmen/Wurzeln oder einzelne gezählte Bäume.

## Offene technische und fachliche Punkte

Zehn bekannte Haus-/Anbau-Überschneidungspaare und zwei teilweise blockierte Öffnungen. Statik/Gründung, heutiger Höhenanschluss, Leitungstiefen, Flachdachaufbau und diverse verdeckte Konstruktionen unbekannt. Die Grundstückskontur ist eine Kartenreferenz, kein absteckbarer Grenznachweis. Historische Leitungen sind auf Z=0 projiziert; keine bestätigte dreidimensionale Einbaulage.

## Aktueller Prüfstatus

Die Übergabeprüfungen liegen unter `reports/handoff/`. Dort werden die neu ausgeführten Python-/Simulationstests von den früheren CAD-Quellprüfungen in G02 getrennt. Das mitgelieferte G02-Prüfwerkzeug kann die optionalen CAD-Prüfungen erneut anfordern; diese wurden bei dieser Git-Übernahme nicht als neue NX-Tests ausgegeben.

## Rangfolge bei Widersprüchen

1. Konkreter aktueller Nutzerauftrag und zugehörige tatsächliche Dateien.
2. Aktive G02-Konfiguration und belegte Quellenzuordnung.
3. Erhaltene alte Konzeptunterlagen als historische Studienergebnisse.
4. Chat-Zusammenfassungen und alte Testbehauptungen ohne erhaltenes Artefakt: nicht als Umsetzungsnachweis verwenden.

Primäre lokale Belege: `projects/g02/README_START_HIER.md`, `projects/g02/data/HOEHENANSCHLUSS_G02.json`, `projects/g02/haus/data/haus.json`, `projects/g02/haus/data/planregister.json`, `provenance/IMPORT_MANIFEST.json`.
