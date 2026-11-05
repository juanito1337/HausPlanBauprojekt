# Sichtbare NX-Bauzustände – Korrekturplan M01.2

> Ausführung mit Superpowers, gezielter Fehlerdiagnose und unabhängigen Reviews. Dieser Plan setzt den erneuten Auftrag um, vorhandene Abschnitte in einem gemeinsamen NX-Modell tatsächlich begutachten zu können.

Ein gemeinsamer Master zeigt beim Öffnen bereits einen verständlichen Studienzustand. Gespeicherte Zustände erlauben die direkte Begutachtung jedes verfügbaren Aushubs mit dem zugehörigen Sandlager auf dem Grundstück.

Bestehende eigene Haus-/Studienkopien bleiben Grundlage. Ergänzt werden gespeicherte NX-Arrangements, passende Kameras/Layer, räumlich erkennbare Register für gesperrte Felder und gemeinsam genutzte Geländeteile. Für jede Feldstudie wird nur der vom lokalen Schnittboden ersetzte Geländebereich ausgeblendet. Der übrige Grundstücksboden bleibt sichtbar, insbesondere unter dem Lager. Die technische Eignung verschachtelter Arrangements wird zuerst in einem kleinen echten NX-Probelauf geprüft.

Grundlage sind der Nutzerauftrag vom 04.11.2026, `docs/ANFORDERUNGEN_RENOVIERUNG.md` und die bisherige Strukturentscheidung M01. Keine neue Festlegung von Fundamentmaßen oder Ausführungsfreigaben.

## Befund und Entscheidungen

- Alle 72 Felder sind derzeit verborgen. Sektionen sind körperlose Baugruppen. Ihre Unterteile bleiben beim separaten Öffnen verborgen. Gewöhnliches Anklicken aktiviert keine Studie. Die bisherigen Nachweise prüften Blankzustände und Mengen, aber weder die Nutzerauswahl noch gespeicherte Kameras/Layer oder separat geöffnete Sektionen.
- 22 Felder besitzen Geometrie, 50 sind ausdrücklich ungeklärt/gesperrt. Leere Register dürfen nicht als fertige Aushubplanung erscheinen.
- Der bestehende Feldwechsel verbirgt den gesamten Bestandsboden. Der lokale Schnittboden zeigt zwar die Grube, aber nicht den separaten Lagerplatz.
- Gespeicherte NX-Zustände statt alleiniger Anweisung zum manuellen Einblenden. Eine zusätzliche gut bedienbare Auswahl bleibt möglich. Reine Dokumentationskorrektur löst den Bedienmangel nicht. Vollständige Hauskopien je Feld würden die bereits korrigierte gemeinsame Struktur wieder aufblähen.
- Gemeinsame Geländeflächen auf derselben TIN-Grundlage wie K02. Regionen werden anhand der vorhandenen lokalen Studienraster gruppiert und nur dort ausgeblendet, wo das aktive Feld den geschnittenen Boden liefert. Kein neues Aushubvolumen und keine Verkleinerung von Konflikten.
- Vorhandener eigener Feature-Checkout bleibt Arbeitsplatz. Keine weitere Kopie sämtlicher CAD-Dateien. Alte Lieferungen und G02/K02-Erzeuger bleiben unverändert.
- Die Windows-Bildaufnahme meldet weiterhin Zeitüberschreitungen. Native Sichtobjekt-/Layer-/Kameraprüfung und gegebenenfalls nativer Bildexport werden separat erprobt. Eine nicht erfolgte Bildschirmabnahme wird nicht behauptet.

## Aufgaben

- [x] Fehler in Master/Feld/Sektion anhand sichtbarer Körper, Layer, Kamera und Referenzsets nativ reproduzieren. Unabhängigen Code- und Machbarkeitsaudit durchführen.
- [x] Kleiner NX-Arrangements-Pilot mit verschachtelten Feldern, gespeichertem Startzustand und frischem Wiederöffnen. API vor breiter Umsetzung bestätigen.
- [x] Geländekontext aus belegtem DGM nach Studienrastern gruppieren. Flächen-/Mengen-/Überlappungs-Negativtests durchführen und getrennte Hilfsgeometrie ohne Abrechnung als Aushub verwenden.
- [x] Layout und Darstellung mit gespeicherten Studienzuständen, direkt sichtbarem Start, eindeutig benannten gesperrten Registern und Gelände-/Lagerkontext korrigieren. Separat geöffnete Sektionen/Felder sinnvoll anzeigen.
- [x] Prüfung um echte sichtbare Geometrie, Layer, Kamera, Zustandserhalt nach Öffnen, Kontextabdeckung und unveränderte Aushub-/Lagervolumen erweitern. Bedienweg mit dem tatsächlich verfügbaren NX-Zugang prüfen.
- [x] Machbarkeitsbericht pro Sektion mit Grundstücks-/Gebäudekonflikten, Lager-/Schutzstreifenprüfung und offenen Last-/Wege-/Gründungsnachweisen aktualisieren.
- [x] Neue native Lieferung vollständig erzeugen, frisch und verschoben öffnen, unabhängiges Review und Abschlusschecks.
- [x] CAD-Dateien und Bericht in Git sichern.

## Verbindliche Grenzen und Nachweise

Millimeter, bestehender Höhenversatz genau einmal. 1:1-Böschung, 0,80 m Arbeitsraum und höchstens 2,00 m Feldsohle bleiben ausdrücklich Studienannahmen. Die Endböschungen verbreitern die Öffnung an der Geländeoberkante erheblich. Die 22 Feldansichten sind Einzelfeldalternativen, keine kumulative Baufolge. Keine abgeschnittenen Konfliktmengen oder erfundenen Anbautiefen. Haupt- und Reservelager bleiben Alternativen am selben Ort.

Die Machbarkeit wird anhand der geometrischen Belege und aktuellen Primärquellen beurteilt. Schutzstreifen, Auflasten, Leitungen, Zugang und unbekannte Fundamentunterkanten sind ausdrücklich zu prüfen. Ein bestandener CAD-Lauf ersetzt keinen Standsicherheitsnachweis. Die endgültige Freigabe benötigt örtliche Erkundung und zuständige Fachplanung/Bauleitung.

## Fortsetzung M02 am 05.11.2026

Der Nutzer bestätigt vorläufig 1,50 m für den Anbau. Die erste Darstellungsannahme setzt die Plattenunterkante auf −1.500 mm gegenüber EG und die Zielsohle auf −1.600 mm. Der vorhandene Anbau-Fußbodenproxy liegt bei −1.860 mm. Am 05.11.2026 bestätigt der Nutzer ausdrücklich die Sohle bei −1.600 mm relativ EG als reine Schnittstudie. Der Unterschied zum Fußbodenproxy bleibt in den Modelldaten erhalten. Die rechnerische Hilfskote −1.500 mm liefert weiterhin keinen Bestands- oder Gründungsnachweis.

Alle 24 vorhandenen Anbaufelder PS10 bis PS13 erhalten native Darstellung. Die vollständige geometrische Berechnung ergibt 13 Kandidaten und 11 Konfliktfälle. Die zusätzliche Prüfung eines 600 mm breiten unbelasteten Randstreifens stuft PS11-F01, PS11-F04 und PS11-F05 ebenfalls als Konfliktdiagnose ein. Die integrierte Darstellung umfasst damit 10 Schachtstudien mit Bodenlager und 14 rote Konfliktansichten ohne effektive Aushubmenge. PS12-F01 besitzt rechnerisch nur rund 0,5 mm Reserve am Kartenrand. Seine örtliche Eignung bleibt ungeklärt.

- [x] Alle 24 Felder nativ erzeugen und in einem frischen NX-Prozess wieder öffnen.
- [x] Gemeinsamen Grundstücksboden nativ erzeugen, vermessen und frisch öffnen.
- [x] Alle Felder in eine unabhängige flache Gesamtlieferung integrieren und die bisherigen Studien erhalten.
- [x] Alle gespeicherten Zustände, Komponenten, Mengen und separaten Einstiegspunkte nativ prüfen.
- [x] Normalen Ladeweg nach Verschieben des gesamten Lieferordners prüfen.
- [x] Aktuellen CAD-Verweis, Mengenübersicht und Revisionsnachweise veröffentlichen.

Die neue Gesamtprüfung umfasst auch die übernommenen M01-Dateien. Ein vollständiger geometrischer Zwischenstand dient als explizit dokumentierte Eingabe. Die endgültige M02-Lieferung wird erst nach erfolgreicher Gesamtprüfung als aktuell gekennzeichnet.
