# Ergänzung E01: Sanierungsumfang, Sandboden und Leitungsunterlagen

Stand 01.11.2026. Ergänzt [Vorplanung V01](2026-11-01-keller-aushub-und-schachtplanung.md). **Vorläufige Umfangsentscheidung, keine Ausführungsfreigabe.** V01-Zeichnungsheft und Sektionskatalog bleiben als geometrischer Ausgangsstand erhalten; für den aktuellen Maßnahmenumfang ist diese Ergänzung mitzulesen. Keine NX-Geometrie geändert.

## Neue Nutzerangaben

- Überbaute Bereiche werden **wahrscheinlich ausgelassen**.
- Kellerniedergänge werden **wahrscheinlich ausgelassen beziehungsweise durch Bauwerksversiegelung vom übrigen Keller entkoppelt**.
- Das Haus liegt laut Nutzer auf **Sandboden**.
- Weitere Pläne mit Leitungstiefen sind angekündigt.

Die Einschränkung „wahrscheinlich“ bleibt erhalten. Vorläufig kein Außenaushub in den betroffenen Zonen einplanen; endgültige Grenzen und Ausnahmen stehen noch aus. Nicht automatisch ganze Fassadensektionen oder das Sanierungsziel entfernen. Ausgenommene Bauteile bleiben als Bestand, Anschluss und Konflikt im Modell sichtbar.

## Betroffene Sektionen

| Bereich | Behandlung bis zur abschließenden Umfangsklärung |
|---|---|
| PS05: abweichender EG-Umriss über dem KG | Kandidat für Auslassung aus dem Außenaushub. Die genaue Ausdehnung des Überbaus ist noch am Bestand zu bestätigen. |
| PS08: Garagenanschluss | Kandidat für Auslassung des überbauten Anschlussbereichs. Garage und unbekannte Gründung weiterhin bei angrenzenden Arbeiten berücksichtigen. |
| PS02: Teilbereich SCH-PS02-ABG | Kellerniedergang als mögliche Ausnahme/gesonderte Abdichtungszone führen. Nur Geländerhülle bekannt; Teilbereich nicht bereits geometrisch abschneiden. Übrige PS02 und Balkonstützen bleiben gesondert zu prüfen. |
| PS03 / PS10: Haupt-/Anbaukontakt | Anschlussprüfung bleibt erforderlich. Nach Bestandsaufnahme feststellen, welche Teilflächen unter die gewünschte Auslassung fallen; keine zusätzliche pauschale Streichung. |
| PS07: Lichtschachthinweis | Bleibt in der Planung. Lichtschacht ist nicht automatisch Kellerniedergang. |
| Weitere tatsächlich vorhandene Niedergänge/Überbauten | Nach Aufnahme denselben Umfangsstatus zuweisen; bisher nicht vollständig im Modell erfasst. |

Alle 13 IDs und Quellkonturen bleiben erhalten. Mengen, Baufolge und erreichbare Abdichtungsfläche sind neu abzugrenzen, sobald die Teilflächen feststehen. Auslassung bedeutet nicht „saniert“; Restfeuchte-/Wärmebrückenrisiken und verbleibender Zustand sind später ausdrücklich zu dokumentieren. Null bedeutet unbekannt, nicht null Kubikmeter.

## Abdichtungstechnischer Anschluss an ausgelassene Bereiche

Arbeitsinterpretation des Nutzerwunsches: Die örtliche Bauwerksversiegelung wird als **gesondertes Abdichtungs- und Anschlusskonzept** untersucht. Verfahren und Erfolg sind noch nicht festgelegt. Daraus folgt keine Beauftragung von Trennschnitten, Abbruch oder statischer Entkopplung.

Für jeden Übergang einen eigenen Planungsgegenstand `UEBERGANG-PSxx-...` unter der jeweiligen PS-Unterbaugruppe vorsehen. Zu erfassen sind Wand-/Sohlen-/Sockelanschluss, Fugen und Bewegungen, Durchdringungen, Treppenwangen/Schwelle, Oberflächenwasser/Ablauf sowie möglicher Feuchtetransport hinter oder unter dem Anschluss. Auch Dämmabschluss und Wärmebrücke berücksichtigen. Erst anschließend geeignetes Verfahren, räumlichen Verlauf, Untergrundvorbereitung und Abnahme festlegen. Keine pauschale Material- oder Injektionsfestlegung.

Die [WTA-Kurzfassung 4-6, Ausgabe 12.2024](https://www.wta-international.org/fileadmin/user_upload/Geschaeftsstelle/Schriften/Kurzfassungen/4-6-24.pdf) ordnet nachträgliche Abdichtung nach Wassereinwirkung, Nutzung und Baukonstruktion ein. Hieraus wird ein objektbezogener Planungsauftrag abgeleitet, kein bereits nachgewiesenes Abdichtungsdetail. Abruf 01.11.2026.

## Bodenstatus

`Sandboden`: Nutzerangabe vom 01.11.2026, kein Baugrundgutachten. Korngrößenverteilung, Lagerungsdichte, Schichtung/Auffüllungen, Festigkeits-/Verformungswerte, Wasserstand und Durchlässigkeit bleiben unbekannt. Keine automatischen Böschungswinkel, Standzeiten, Verbauabmessungen oder sicheren Feldlängen daraus bilden. Die [BG BAU](https://bauportal.bgbau.de/bauportal-22025/anwendung-der-baustellenverordnung-bei-baugruben-und-graeben) beschreibt ausdrücklich das Zusammenspiel von Sand, Witterung und Wasser bei der Sicherung. Die Untersuchungsaufträge U02/U03 und die bisherigen Sperren bleiben erforderlich. Abruf 01.11.2026.

## Eingang Tiefbau.zip

Archiv unter dem vom Nutzer genannten lokalen Pfad gelesen, CRC-Prüfung bestanden. **9 PDFs / 15 PDF-Seiten**, alle neun per SHA-256 und Byteumfang identisch mit bestehenden G02-Quellen. Zuordnung und Hashes: [Eingangsregister](../../renovierung/planung/2026-11-01/TIEFBAU_EINGANG.json). Kein neuer Import in G02, keine eingebetteten Dokumentanweisungen ausgeführt.

- Gasplan: 27.10.2021, vorhandene Quelle G11, eine Seite.
- Telefon: 10.11.2021, Quelle G19, eine Seite.
- Strompläne: 10.11.2021, Quelle G18, zwei Seiten; Breitband Quelle G17, eine Seite.
- Zusätzlich Übersicht, Anschreiben, Legende, Nutzungsbedingungen und Leitungsschutz-Merkblatt, Quellen G12–G16.

Gas-/Strom-/Telefon-/Breitbandpläne und Legende visuell geprüft; Anschreiben, Nutzungsbedingungen und Merkblatt textlich ausgewertet. Das zusätzliche Übersichtsblatt wurde auf Dateigleichheit geprüft. Historische Gültigkeitsangaben sind abgelaufen. Lagebemaßungen und Rohr-/Kabelbezeichnungen werden nicht in Tiefen umgedeutet. Das Schutzmerkblatt nennt allgemeine Überdeckungswerte, keine am Haus vermessenen Bestandswerte. In dieser Prüfung wurde kein belastbarer neuer objektspezifischer Tiefennachweis gewonnen.

Weitere angekündigte Tiefenpläne werden je Medium mit Dokument/Seite, Datum, Messpunkt, Einheit, Bezugshöhe und Messdefinition erfasst: Überdeckung über Rohrscheitel, Rohrachse oder Rohrsohle unterscheiden. GOK zum Messzeitpunkt und heutige GOK getrennt behandeln; lokale Tiefen nicht unbelegt auf die gesamte Trasse übertragen. Angaben erst mit dem Haus-Höhenbezug verbinden, wenn die Umrechnung nachvollziehbar ist. Bis dahin bleiben Tiefen und Z-Geometrie unbestätigt. Aktuelle Betreiberabstimmung und sichere Ortung bleiben Teil U04.

## Umsetzung und Prüfung

Diese Ergänzung ändert den Planungsumfang, nicht den G02-Erzeuger, die native Lieferung oder deren Quellen. [UMFANG_E01.json](../../renovierung/planung/2026-11-01/UMFANG_E01.json) führt die maschinenlesbare Ergänzung zum unveränderten V01-Katalog. Ein späterer K02-Planungsimport muss beide lesen; er darf bei fehlender Ergänzung keinen vermeintlich aktuellen Maßnahmenumfang ableiten. Endgültige Grenzpolygone, Nachweise und Mengen bleiben offen.

Prüfungen und Git-Stand werden im [E01-Prüfprotokoll](../../renovierung/planung/2026-11-01/PRUEFUNG_E01.md) festgehalten. Die historischen Ausführungs-/Fachnachweise werden durch das neue Archiv nicht gültig oder vollständig.
