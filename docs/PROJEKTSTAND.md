# Projektstand und gesicherte Übergabe

Aktueller Studienstand: **03.11.2026**. Frühere Liefer- und Übergabestände bleiben nachfolgend als Historie erhalten.

## Aktuelle Hauptbaugruppe M01

**Eine Hauptdatei öffnen:** [HAUSPROJEKT_MASTER_M01.prt](../cad/nx/m01/20261103T005043Z_07d05f/HAUSPROJEKT_MASTER_M01.prt). Haus, Geschosse, Dach, Umgebung und alle 13 Bauabschnitte liegen gemeinsam im Baugruppenbaum. 72 Felder sind registriert; 22 besitzen separat schaltbare native Studiengeometrie. 50 Zimmer bleiben ausdrücklich Raumregister ohne erfundene Wand- oder Raumkörperzuordnung. Alle Komponenten im Lieferordner belassen; [Bedienung und Suchpfade](../cad/nx/m01/README.md).

Lauf `20261103T005043Z_07d05f`: **199 native Parts**, 265 Baumknoten, 405.483.415 Bytes. Mit NX 2406.6000 tatsächlich aufgebaut, frisch AsSaved und als verschobene Kopie mit SearchDirectories geöffnet; alle drei Phasen bestanden. Je Phase wurden alle 264 Komponenten und 23 Darstellungszustände geschaltet, Feld-/Rollenvolumen und Referenzen geprüft. G02/K02-Quellen und alte Lieferungen bleiben unverändert. [Projektanalyse, Fehlerkorrekturen und Prüfgrenzen](entwicklungsstand/M01-pruefung-2026-11-03.md).

Abschlusscheck `tools/run_checks.py`: Exit 0; 54 Repositorytests (ein bestehender Skip), 45 K02-Tests und 25 M01-Tests sowie beide nativen Aktualitätsnachweise bestanden. Die grafische Bildschirm-/Menüabnahme bleibt offen. Die erneut ausgeführte historische G02-Suite bestätigt weiterhin einen bekannten Windows-Pfadtestfehler. Fachliche Bestandslücken, Statik/Gründung und Leitungstiefen bleiben offen; keine Ausführungsfreigabe.

## Aktueller CAD-Revisionsstand K02 / 31dba74

Auf erneuten Prüf- und Speicherauftrag wurde der unveränderte K02-Journalablauf vollständig ausgeführt: **Exit 0**, Lauf `20261101T191747_4adeb5`, 23 Zustände und 689 frisch gespeicherte native Dateien. Alle Zustände wurden frisch AsSaved und als verschobene Kopie mit SearchDirectories geöffnet. Die gültige G02-Basis wurde wiederverwendet. Geometrie und Mengen stimmen mit der Erstlieferung überein; Code und Modelleingaben blieben unverändert. [Revisionsübersicht mit aktuellen Masterlinks und Prüfnachweisen](../cad/nx/REVISION_K02_31dba74.md). Grafische NX-Sichtprüfung und fachliche Freigaben bleiben offen.

## K02-Böschungs- und Abraumstudie: Erstlieferung

**Native Lieferung bestanden:** [Renovierungsbasis BASE direkt öffnen](../cad/nx/k02/20261101T133310_8b6d68/BASE/BASE_21.prt), oder ein Feld über die [Mengenübersicht mit direkten Masterlinks](../renovierung/planung/2026-11-01/K02_STUDIE.md) wählen. Vollständigen jeweiligen Komponentenordner beibehalten und nach Checkout die [NX-Suchpfadanleitung](../cad/nx/README.md) beachten. Ein Master allein ist keine vollständige Baugruppe.

Lauf `20261101T133310_8b6d68`: BASE plus alle 22 nativen Kandidaten, **689 unabhängige `.prt`-Dateien**, tatsächlich erzeugt und je Zustand frisch AsSaved sowie nach Verschieben SearchDirectories geöffnet. Alle Teile vollständig, mm, interne Referenzen, Quellhashes und Komponentenlagen passend; echte Rollen-/Einzelkomponentenvolumen kohärent. Der Gesamtplan wurde auf endgültigem Code und neuer gültiger G02-Basis frisch berechnet. Unveränderte historische Dateien bleiben erhalten. [Entwicklungs- und Prüfnachweis](entwicklungsstand/K02-native-2026-11-01.md).

Alle 13 PS/72 Felder bleiben registriert. 45 ungeklärte/vorläufig ausgenommene Felder erhalten keine erfundenen Mengen; fünf weitere Felder bleiben vollständige hypothetische Hinderniskonflikte. Sechs native Kandidaten behalten ungeklärte EG-Überbauprojektionen. PS01-F06 hat drei getrennte Aushubkörper, keinen nachgewiesenen durchgehenden Graben. Die 60 positiven Projektionsüberschneidungen sind keine berechnete Volumenunion. Keine kumulative Baufolge, Netto-Erstaushubmenge oder Ausführungsfreigabe; sämtliche `construction_release=false`.

Aktuell bestanden: Integrität von 543 G02-/8 K01-Importdateien, 51 Werkzeugtests (ein bestehender Skip), 45 K02-Tests und nativer Aktualitätscheck. Die historische vollständige G02-Suite behält ihren bekannten Windows-Pfadfehler; sie wurde ohne neuen Anlass nicht erneut gestartet. **Grafische NX-Sicht-/Bedien-/Kameraprüfung bleibt offen.** Eine ausdrücklich diagnostische Ansicht des finalen F01 aus echten NX-Körpern liegt im Nachweis, keine NX-Bildschirmaufnahme.

## Ergänzung 01.11.2026: Keller-Vorplanung

Weitere Nutzerangabe: Auf Kellertiefe wird kein Grundwasserproblem erwartet. In E01 als Standortangabe dokumentiert; kein gemessener oder bemessener Wasserstand angegeben. Keine automatische Ausführungsfreigabe daraus abgeleitet.

Aktuell zusätzlich [E01](plans/2026-11-01-keller-ergaenzung-umfang-leitungen.md) beachten: Nutzer plant voraussichtlich Ausnahmen für Überbau/Niedergänge; Sandboden als Nutzerangabe erfasst. `Tiefbau.zip` enthält neun bytegleiche bereits vorhandene PDF-Quellen; kein neuer belastbarer Leitungstiefennachweis gewonnen. Geometrischer V01-Stand und native NX-Dateien unverändert.

[Aushub- und Schachtplanung V01](plans/2026-11-01-keller-aushub-und-schachtplanung.md) erstellt: 13 aus den aktuellen Kellerkonturen abgeleitete Planungssektionen, 21-seitiges Zeichnungsheft, editierbarer Sektionskatalog, Untersuchungs-/Nachweisprogramm, Bauablauf mit Haltepunkten und Zielstruktur für NX-Unterbaugruppen. Keine neuen Renovierungs-.prt oder Maßnahmengeometrien erzeugt. Fachliche Grundlagen fehlen laut Nutzer; sichere Feldlängen, Tiefen und Mengen noch offen. Sämtliche Ausführungsfreigaben bleiben gesperrt. Prüfungen stehen im [V01-Protokoll](../renovierung/planung/2026-11-01/PRUEFUNG.md).

## Ergänzung: echte native NX-Lieferung

Am 31.10.2026 wurde der unveränderte G02-Erzeuger mit **NX 2406.6000** tatsächlich vollständig ausgeführt. Die neue Lieferung liegt unter `cad/nx/20261031T134924_e0fb72/`: **29 `.prt`-Dateien**, insgesamt 36.028.198 Bytes. Master: `PROJEKT_MASTER_G02_PLANBEZUG_1953e9e2.prt`. Haus: 1.418 Körperaufträge in 15 Komponenten. Umgebung und höhenbezogene Gesamtmontage wurden erzeugt und gespeichert.

Wiederöffnen in einem frischen NX-Prozess und Laden einer verschobenen Kopie bestanden; alle 29 Parts vollständig geladen, in mm und innerhalb des jeweils geprüften Ordners. `BUILD.json`/`VERIFY.json` und `CURRENT.json` ordnen die Lieferung zu. Versionierung über Git LFS. Diese neue Erzeugung übernimmt keine manuellen Änderungen aus früheren Nutzerdateien.

51 aktuelle Repository-/Werkzeugtests bestanden (ein bereits bestehender Windows-Symlinktest übersprungen). Die vollständige historische G02-Suite wurde ausgeführt, ist unter Windows aber nicht vollständig grün: nach UTF-8-Korrektur der Testumgebung bleibt der Pfadtest für `/tmp/x` offen. Einzelheiten und ausgeführte Befehle: [Entwicklungsnachweis](entwicklungsstand/NX-native-2026-10-31.md). Vor jedem Abschluss ist der native Aktualitätscheck verpflichtend; Erzeugeränderungen benötigen einen neuen echten NX-Lauf.

Die folgenden Angaben beschreiben den ursprünglichen importierten Lieferbestand; insbesondere bleiben K01-Lücken und fachliche Einschränkungen bestehen.

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
