# M01.2 – räumliche Machbarkeit der Kellerstudien

Stand 04.11.2026. Auftrag und Abgrenzung ergeben sich aus [Korrekturplan für sichtbare Bauzustände](../plans/2026-11-04-sichtbare-bauzustaende.md), [Renovierungsanforderungen](../ANFORDERUNGEN_RENOVIERUNG.md). **Die vorhandenen Aushub- und Lagerkörper können als anschauliche Einzelfeldstudien gezeigt werden. Ihre geometrische Darstellbarkeit ist keine Freigabe für Erdarbeiten.** Dieser Bericht enthält eine neue mathematische Abstandsauswertung der unveränderten K02-Eingaben. Er bestätigt keinen neuen NX-Lauf und keine geprüfte Standsicherheit.

## Was tatsächlich geplant und was nur registriert ist

Das Register umfasst 13 räumliche Sektionen und 72 Felder. 22 Felder besitzen unabhängige native Studiengeometrie aus der historischen K02-Lieferung. Fünf weitere Felder sind vollständige hypothetische Aushübe mit Gebäudekollisionen. 45 Felder bleiben wegen unbekannter Teilflächen, Anschlüsse oder Anbautiefen ohne Aushub-/Lagermengen. Unbekannt bedeutet `null`, niemals 0 m³. Die 50 Felder ohne native Studienkörper dürfen räumlich als gesperrtes Register sichtbar sein, aber nicht als bereits konstruierter oder ausführbarer Arbeitsgraben.

Als Belege dienen [K02-Studienübersicht](../../renovierung/planung/2026-11-01/K02_STUDIE.md), [Mengen und Warnungen](../../renovierung/planung/2026-11-01/K02_MENGEN.json), [K02-Planung](../../renovierung/k02/planning.py), [M01-Layout](../../renovierung/m01/layout.py). Das M01-Layout übernimmt Körperrollen nur für native Kandidaten. Die ursprüngliche Darstellung startet mit verborgenen Feldgruppen. Ein leerer Registerknoten und ein verborgener vorhandener Körper sind unterschiedliche Befunde. Die M01.2-Darstellung wird im Hauptauftrag getrennt korrigiert und nativ geprüft.

Alle 22 Varianten zeigen jeweils höchstens einen offenen Eingriff. Es gibt **keinen implementierten Verbauentwurf, keine bemessene Unterfangung und keine kumulative Baufolge**. 60 positive Projektionsüberschneidungen sind dokumentiert. Gemeinsame Aushubvolumen, Wiederfreilegung verfüllter Bereiche und Netto-Erstaushubmenge sind nicht berechnet. Die Feldvolumina dürfen nicht als Gesamtbaumenge addiert werden.

## Maßannahmen und ihre räumlichen Folgen

Die bestätigte Studie verwendet 0,80 m Arbeitsraum, höchstens 2,00 m Sohlenlänge sowie Seiten- und Endböschungen 1:1. Die modellierte Bodenplatten-UK des Hauptkellers beträgt −2,505 m, Prüfziel −2,605 m. Fundamentunterkante und tragende Aufstandsfläche sind unbekannt. Beim Anbau beträgt die FFB −1,860 m, Bodenplatten-UK und Zieltiefe unbekannt. Als Quellen dienen [Studienkonfiguration](../../renovierung/k02/study_config.json), [Sektionskatalog mit Höhen](../../renovierung/planung/2026-11-01/sektionen.json). Sämtliche `construction_release` bleiben `false`.

Die Felder werden durch gleichmäßige Teilung vorhandener Wandsegmente mit einer maximalen Sohlenlänge von 2 m gebildet. Diese Einteilung ist keine aus der Gründung abgeleitete zulässige Freilegungslänge. Endböschungen verlängern die Öffnung am Gelände deutlich. Bei beispielhaft 2,305 m Tiefe zwischen Gelände −0,300 m und Prüfsohle −2,605 m wird eine 1,853 m lange Sohle oben ungefähr 6,463 m lang. Die äußere Ausladung beträgt dann 0,800 + 2,305 = 3,105 m. Mit 0,600 m freiem Schutzstreifen werden mindestens 3,705 m benötigt. Diese ebene Beispielrechnung erklärt den Platzbedarf. Die tatsächlichen Feldprojektionen stammen aus dem unebenen Studien-TIN.

Der G02-Höhenanschluss bleibt die dokumentierte Planannahme mit einmaligem Z-Versatz −31362,49870845903 mm. Die Kartengrenze ist kein absteckbarer Grenznachweis. Die TIN-Abweichung von höchstens 20,78125 mm beschreibt die Approximation des vorhandenen bilinearen DGM, keine Vermessungsgenauigkeit oder heutige Oberflächengarantie.

## Bewertung der 13 Sektionen

Längen bezeichnen die nominalen Register-Sohlenlinien, nicht sanierte Wandflächen oder sichere Öffnungslängen. A = geböschte Studie. B = noch zu planender, bemessener Verbau. Auch positive A-Geometriekandidaten bleiben fachlich ungeprüft.

| Sektion / Lage im Grundriss | Länge m | Felder / nativ | Konkreter Befund | Nächster fachlicher Schritt |
|---|---:|---:|---|---|
| PS01 – untere Hauptkellerseite | 20,385 | 11 / 11 | Strom-, Gas- und Telefonprojektionen. Auffällige Geländesenke. F06 mit drei getrennten Aushubkörpern. | Medien orten, Gelände und Gründung aufnehmen. Feldgrenzen und A/B einschließlich Endböschungen prüfen. |
| PS02 – Balkon/Kellerabgang | 4,862 | 3 / 0 | Niedergangs-Teilfläche noch nicht abgegrenzt. Geländer ersetzt kein Schacht-/Stützenaufmaß. | Ausnahme räumlich festlegen. Übrige Fassade nicht pauschal streichen. B und separates Abdichtungskonzept untersuchen. |
| PS03 – Hauptbau/Anbau | 8,150 | 6 / 0 | Konturabstand örtlich nur ca. 57–69 mm. 0,80 m Arbeitsraum fehlt. Anschluss ungeklärt. | Kontakt, Lastabtrag und Zugänglichkeit aufnehmen. Standard-Außengraben gesperrt lassen. |
| PS04 – oberer Querbauabschnitt | 3,835 | 2 / 1 | F01 kollidiert mit Anbau. Örtlicher Konturabstand ca. 615 mm. F02 behält ungeklärte EG-Projektion. | Ecke, Anschluss und Gründung prüfen. F01 nicht zum Einpassen beschneiden. |
| PS05 – überbaute KG-/EG-Kontur | 13,305 | 8 / 0 | Erheblicher Überbau und ungeklärte Ausnahmemaske. | Überbau-/Lastabtrag aufnehmen, erreichbare Wandflächen und Anschlusskonzept festlegen. |
| PS06 – obere rechte Hauptkellerseite | 5,680 | 3 / 3 | Alle drei Kandidaten besitzen ungeklärte EG-Überbauprojektion. Fenster/Endanschlüsse. | Fassaden-/Gründungsaufmaß und Ecknachweise, A/B danach beurteilen. |
| PS07 – obere Hauptkellerseite | 7,930 | 4 / 2 | F03/F04 kollidieren mit Garage. F01/F02 behalten EG-Projektionswarnung. Historischer Lichtschacht ohne Maße. | Lichtschacht und Garagenecke aufnehmen. Freie Teilbereiche und Sicherung getrennt planen. |
| PS08 – Garagenanschluss | 6,430 | 4 / 0 | Garage außen unmittelbar anliegend. Ausnahmemaske ungeklärt. | Garagenfundament, Verbindung und Sanierungszugang klären. Gesperrtes Register erhalten. |
| PS09 – linke Hauptkellerseite | 12,500 | 7 / 5 | F01/F02 kollidieren mit Garage. Telefonprojektion in weiteren Feldern. | Garagenende und Medien gesondert behandeln, Feldfolge/Gründung prüfen. |
| PS10 – Anbauanschluss/untere Stirnseite | 8,730 | 5 / 0 | Anschluss und freie Teilfläche ungeklärt. Anbau-Zieltiefe fehlt. | Aufmaß mit Trennpunkt, Gründung und Bodenplatten-UK. Keine ersatzweise Hauptkellertiefe einsetzen. |
| PS11 – rechte Anbaulängsseite | 13,230 | 7 / 0 | Kartengrenzabstand örtlich nur ca. 2,088 m. Sohle unbekannt. | B vorrangig untersuchen, Einbauhülle/Aussteifung innerhalb Grundstück. Keine freien Rückanker voraussetzen. |
| PS12 – obere Anbaustirnseite | 8,730 | 5 / 0 | Grenzengpass an PS11-Ecke, etwa 2,088 m. Sohle unbekannt. | Tiefe und Grenze bestätigen, A/B und gesonderten Eckzustand prüfen. |
| PS13 – Anbauhofseite | 13,230 | 7 / 0 | Sohle unbekannt. Enger Anschluss unten und notwendiger Hofzugang. | Anbaugründung und Höhen aufnehmen, Durchgang und Sicherung gemeinsam planen. |

Die ca. 2,088 m sind modellierte Bestandsabstände aus dem Sektionskatalog, keine nachgerechnete Aushubprojektion des Anbaus. Ohne Anbausohle existiert dort bewusst kein vollständiger Aushubkörper. Mit 0,80 m Arbeitsraum und 0,60 m Schutzstreifen blieben an einem entsprechenden geraden Querschnitt nur 0,688 m für eine 1:1-Böschung. Das zeigt den Engpass, ersetzt wegen örtlicher Geometrie und unbekannter Tiefe aber keinen feldweisen Nachweis.

## Neue geometrische Abstandsauswertung

Die Standardkonfiguration wurde am 04.11.2026 mit `create_plan(repo_root, study_config)` frisch berechnet, ohne `source_paths`-Overrides und ohne Änderung der K02-Produktivmodule. Ausgewertet wurden die vollständigen XY-Projektionspolygone der Aushübe und beider Lageralternativen. Die minimale euklidische Entfernung wird über sämtliche geraden Polygonsegmente ermittelt. Segmentkreuzungen, Berührungen oder Enthaltensein ergeben bei gefüllten Projektionsmengen 0. Bei der Kartengrenze wird dagegen die Entfernung zur Grenzkurve gemessen und der Flächenaustritt separat geprüft. Innere TIN-/Formpartitionen bleiben enthalten. Sie verkleinern das Minimum gegenüber der gesamten gefüllten Menge nicht.

Alle 66 Projektionen (22 Aushübe und 44 Haufenalternativen) liegen innerhalb der numerischen Flächentoleranz von 0,001 mm² im Kartenpolygon. Der maximale rechnerische Flächenaustritt beträgt 3,65078 × 10⁻⁷ mm². Aushub und zugehöriger Haufen überlappen in keiner der 44 Kombinationen. Das besagt noch nichts über tatsächlichen Grenzverlauf, freie Laufwege, Leitungen oder Lastverträglichkeit. Die Zahlen sind auf 1 mm gerundete Modellabstände. Diese Stellenzahl ist keine Ortsgenauigkeit.

### Mengen der 22 darstellbaren Studien

Gewachsen = unabhängiger Erstaushubansatz des jeweiligen Feldes. Hauptlager = locker 1,05. Reserve = alternatives Szenario 1,25. Kontaktflächen sind Summen disjunkter mathematischer TIN-Kontaktprojektionen, keine native Flächenmessung. Alle Volumina sind frisch mathematisch nachgerechnet. Historische NX-Messungen stehen getrennt in der K02-Mengenquelle.

| Feld | Aushub m³ | Hauptlager m³ | Reserve m³ | Kontakt Haupt/Reserve m² |
|---|---:|---:|---:|---:|
| PS01-F01 | 20,255 | 21,268 | 25,319 | 41,622 / 46,630 |
| PS01-F02 | 20,371 | 21,390 | 25,464 | 41,777 / 46,805 |
| PS01-F03 | 19,601 | 20,581 | 24,501 | 40,744 / 45,642 |
| PS01-F04 | 15,082 | 15,836 | 18,852 | 34,392 / 38,491 |
| PS01-F05 | 9,040 | 9,492 | 11,300 | 24,757 / 27,678 |
| PS01-F06 | 4,505 | 4,730 | 5,631 | 15,794 / 17,679 |
| PS01-F07 | 10,474 | 10,997 | 13,092 | 27,200 / 30,424 |
| PS01-F08 | 16,007 | 16,808 | 20,009 | 35,739 / 40,005 |
| PS01-F09 | 19,721 | 20,707 | 24,651 | 40,905 / 45,823 |
| PS01-F10 | 20,107 | 21,112 | 25,133 | 41,423 / 46,406 |
| PS01-F11 | 20,682 | 21,716 | 25,853 | 42,190 / 47,270 |
| PS04-F02 | 25,073 | 26,327 | 31,342 | 47,834 / 53,631 |
| PS06-F01 | 24,543 | 25,770 | 30,678 | 47,171 / 52,881 |
| PS06-F02 | 24,612 | 25,842 | 30,765 | 47,257 / 52,979 |
| PS06-F03 | 24,148 | 25,355 | 30,185 | 46,674 / 52,320 |
| PS07-F01 | 23,070 | 24,224 | 28,838 | 45,304 / 50,773 |
| PS07-F02 | 23,258 | 24,421 | 29,073 | 45,544 / 51,044 |
| PS09-F03 | 22,379 | 23,498 | 27,974 | 44,413 / 49,768 |
| PS09-F04 | 21,840 | 22,932 | 27,300 | 43,714 / 48,980 |
| PS09-F05 | 21,374 | 22,443 | 26,718 | 43,104 / 48,296 |
| PS09-F06 | 20,874 | 21,918 | 26,093 | 42,445 / 47,556 |
| PS09-F07 | 20,420 | 21,441 | 25,525 | 41,842 / 46,878 |

### Tatsächliche Abstände der Studienprojektionen

E = Aushubprojektion, H = Hauptlager, R = Reservelager, G = Kartengrenzkurve. E–H/E–R vergleicht jeweils den aktiven Aushub mit seiner eigenen Lageralternative. **Der Vergleich mit 0,60 m ist ausschließlich ein geometrischer Platzcheck für einen Schutzstreifen zwischen diesen Projektionen bzw. zur Kartengrenze. Er ist keine Auflast-, Böschungs-, Verbau- oder Wegefreigabe.** Die vollständige Nutzung des Schutzstreifens und größere erforderliche Lastabstände sind gesondert zu planen. Ein Grundstücksabstand der Haufen selbst wird nicht als normativer 0,60-m-Grenzabstand ausgegeben.

| Feld | E–G m | H–G m | R–G m | E–H m | E–R m |
|---|---:|---:|---:|---:|---:|
| PS01-F01 | 6,141 | 6,556 | 6,343 | 11,692 | 11,420 |
| PS01-F02 | 7,980 | 6,549 | 6,336 | 10,845 | 10,586 |
| PS01-F03 | 9,817 | 6,596 | 6,384 | 10,583 | 10,335 |
| PS01-F04 | 11,712 | 6,907 | 6,702 | 10,916 | 10,699 |
| PS01-F05 | 13,517 | 7,453 | 7,276 | 11,441 | 11,290 |
| PS01-F06 | 12,048 | 8,063 | 7,921 | 11,255 | 11,153 |
| PS01-F07 | 10,163 | 7,304 | 7,119 | 10,546 | 10,402 |
| PS01-F08 | 8,356 | 6,838 | 6,630 | 10,179 | 10,010 |
| PS01-F09 | 6,541 | 6,588 | 6,376 | 9,977 | 9,798 |
| PS01-F10 | 4,524 | 6,564 | 6,352 | 9,957 | 9,778 |
| PS01-F11 | 2,733 | 6,531 | 6,317 | 9,986 | 9,794 |
| PS04-F02 | 11,374 | 6,294 | 6,068 | 20,756 | 20,562 |
| PS06-F01 | 8,000 | 6,321 | 6,097 | 23,667 | 23,486 |
| PS06-F02 | 6,114 | 6,318 | 6,093 | 25,534 | 25,352 |
| PS06-F03 | 4,361 | 6,341 | 6,118 | 27,439 | 27,249 |
| PS07-F01 | 3,367 | 6,398 | 6,178 | 31,898 | 31,705 |
| PS07-F02 | 3,347 | 6,388 | 6,168 | 31,926 | 31,725 |
| PS09-F03 | 5,232 | 6,435 | 6,217 | 20,411 | 20,145 |
| PS09-F04 | 5,257 | 6,464 | 6,248 | 18,920 | 18,649 |
| PS09-F05 | 5,278 | 6,491 | 6,276 | 17,465 | 17,189 |
| PS09-F06 | 5,306 | 6,519 | 6,306 | 16,108 | 15,827 |
| PS09-F07 | 5,315 | 6,546 | 6,333 | 14,815 | 14,533 |

- Der kleinste Abstand Aushub zur Kartengrenze beträgt **2,733 m bei PS01-F11**.
- Der kleinste Abstand Hauptlager zur Kartengrenze beträgt **6,294 m bei PS04-F02**.
- Der kleinste Abstand Reserve zur Kartengrenze beträgt **6,068 m bei PS04-F02**.
- Der kleinste Abstand Aushub zum Hauptlager beträgt **9,957 m bei PS01-F10**.
- Der kleinste Abstand Aushub zur Reserve beträgt **9,778 m bei PS01-F10**.

Im ausgewerteten 22-Felder-Umfang unterschreitet keiner der Schutzstreifen-Platzvergleiche E–G, E–H und E–R 0,60 m. Das ist ein positiver geometrischer Befund für die untersuchten Alternativen, keine Freigabe der Haufenlast oder des Bauzustands.

Zusätzlich wurden alle 231 Paare der 22 nativen Aushubprojektionen verglichen. 47 Paare berühren/überdecken sich (Abstand 0). Das nächste getrennte Paar PS01-F05/PS01-F08 hat 0,435 m Abstand. Diese Varianten sind nicht gleichzeitig offen. Der Paarvergleich zeigt die Notwendigkeit einer gesonderten Baufolge-/Wiederfreilegungsbilanz. Er ist keine Berechnung gemeinsamer Volumen. Die 60 bisherigen positiven Projektionsüberschneidungen betreffen den größeren Umfang einschließlich hypothetischer Konfliktfelder und sind eine andere Auswertung.


## Lager, Wiederverfüllung und Mengenbilanz

**Bestandskonflikt am bisherigen K02-Lagerplatz.** Die bei X = 13,00 m / Y = −16,00 m angesetzten Hauptlager überschneiden sich bei sämtlichen 22 Feldern im Grundriss mit der im G02-Modell vorhandenen Hecke V02: je nach Feld 6,845–10,881 m². Für die 22 alternativen Reservelager sind es 7,237–11,208 m². Zusätzlich berühren 18 Haupt- und 19 Reservelager den modellierten V01-Bereich mit positiver Überschneidungsfläche. Der oben ausgewiesene Abstand zur Kartengrenze macht diese Fläche nicht zu einem freien Lagerplatz. Das [Lageblatt PS01-F01](M01-2-PS01-F01-Lageplan.png) zeigt die Heckenprojektionen am bisherigen Standort. Ein Ausblenden der Hecken in einer CAD-Arbeitsansicht ist keine Beseitigung im Bestand.

Die Prüfung verwendet die tatsächlichen XY-Flächen der in G02 importierten Kronen-/Heckenoberflächen, die gegen ihre STEP- und nativen Quelldateien geprüft wurden. Stämme, Wurzeln oder heutige örtliche Verhältnisse sind daraus nicht ableitbar. V03/V05, registrierte EG-Projektion und angenommene Leitungskorridore haben am bisherigen Standort keine positive Überschneidungsfläche mit den Haufen. Nicht kartierte Leitungen, Bodenbelastbarkeit und Zugang bleiben offen.

Alle 22 nativen Felder nutzen alternativ dasselbe Lagerzentrum (13,000 m / −16,000 m) in lokalen Gebäudekoordinaten. Haupt- und Reservehaufen sind zwei Szenarien am gleichen Ort und dürfen nicht addiert oder gleichzeitig als vorhandener Boden gezeigt werden. Die Haufenform ist eine geschlossene quadratische Pyramide 1:2 mit Kontaktunterseite am Studien-TIN. Sie ist keine bemessene Böschungsform.

Die Platzsuche in `planning.py` prüft geometrische Überlappungen mit Kartengrenze, bekannten Hindernissen, Eingriffsprojektion und angenommenen Medienkorridoren. Sie enthält keine Mindestabstandsoptimierung, Lastbemessung oder Wegeprüfung. `load_clearance_mm=null` und `access_corridors_confirmed=false` bleiben richtig. Ein positiver Abstand oder ein Vergleich mit 0,60 m kann diese fehlenden Nachweise nicht ersetzen.

PS01-F01 benötigt 41,622 m² Kontaktfläche für den Haupthaufen bzw. 46,630 m² für die Reserve. Der größte Kandidat PS04-F02 47,834/53,631 m², PS01-F06 15,794/17,679 m². Die Bereiche liegen damit weit über einer bloß symbolischen Haufendarstellung. Die gespeicherte Apexhöhe ist eine EG-bezogene Kote, keine Haufenhöhe über lokalem Gelände.

Die Faktoren locker/gewachsen = 1,05 und verdichtet/gewachsen = 0,89 sind illustrative Volumenverhältnisse aus einem Sandbeispiel der [WSDOT, Chapter 10, Table 10-1](https://wsdot.wa.gov/publications/manuals/fulltext/m46-03/chapter10.pdf), keine örtlichen Kennwerte oder Trockenrohdichten. Die Szenarien 1,15/1,25 sind Sensitivitäten. Beispiel PS01-F01: gewachsen 20,255 m³, locker 21,268 m³, verdichtet verfügbar 18,027 m³. Für das transparente Szenario „gesamten Hohlraum verfüllen, unbekannte Dämmverdrängung nicht abgezogen“ fehlen 2,503 m³ Bank-Volumenäquivalent. Das ist keine Masse und keine Vorhersage des tatsächlichen Importbedarfs.

Eine künftige Baufolge benötigt je Zustand Anfangslager + Zugang − Abfuhr − Wiederverfüllung = Endlager mit konsistenter Materialbasis. Verfüllung und ggf. wieder ausgehobene verdichtete Bereiche müssen geometrisch bilanziert werden. Vorherige Felder fertig/verfüllt, aktuelles Feld offen, spätere unverändert. Keine gleichzeitige Eck-/Nachbaröffnung ohne Nachweis. Für den heutigen Studienstand darf weder ein kumulativer Haufen noch ein pauschaler Überschuss behauptet werden.

## Was vor einer realen Ausführung nachzuweisen ist

| Priorität / Prüfpunkt | Benötigte Grundlage und Entscheidung | Stand |
|---|---|---|
| P0 – Gründung und Zielsohle | Fundamentgeometrie/-UK, tragende Aufstandsfläche, Lastabtrag und Zustand aufnehmen. −100 mm unter Bodenplatte mit zulässiger Bodenaushubgrenze vergleichen. Ggf. gesonderte Unterfangung/Sicherung planen. | Offen an allen Feldern. Massive Kellerwände ersetzen keinen Nachweis. |
| P0 – Baugrund und Wasser | Schichtung, Lagerungsdichte/Kennwerte, vorhandene Verfüllungen, Wasserstände/-zufluss und Witterung für alle Bauzustände beurteilen. A-Böschung bzw. B-Verbau bemessen. | Sand und erwartetes Ausbleiben eines Grundwasserproblems sind Nutzerangaben, keine Untersuchungs-/Bemessungskoten. |
| P0 – Leitungen und Bestand | Betreiberunterlagen, örtliche Ortung/Suchstellen und Tiefenbezug. Anbau-, Garagen-, Treppen-, Lichtschacht- und Stützengeometrie. | Historische Z=0-Projektionen und ±1 m Darstellungskorridor sind keine Einbaulage oder Sicherheitsabstände. |
| P1 – Grenze und Platz | Tatsächliche Grenze, Höhen, Arbeitsraum, Seiten-/Stirnsicherung, Schutzstreifen, Verbaueinbau und ggf. Anker nachweisen. | Karten-/DGM-Studie allein reicht nicht. Konflikte bleiben erhalten. |
| P1 – Lager, Lasten und Zugang | Lagerhöhe/-auflast, Randabstand, Wege/Flucht-/Zugang, Maschinenstand-/Schwenk-/Transportflächen, Be-/Entladung und Schutz der Abdichtung planen. | Abstandstabelle prüft nur XY-Platz. Größere lastbedingte Abstände können nötig sein. |
| P1 – Felder, Ecken und Ablauf | Zulässige Öffnungslänge/-dauer, Endböschungen/Verbau, Reihenfolge, Wiederverfüllung und Überwachung fachlich festlegen. | 2-m-Sohlenraster und unabhängige Alternativen sind keine freigegebene Baufolge. |
| P2 – Abdichtung und Wiederherstellung | Wasserbeanspruchung, Untergrund, Wand-/Sohlen-/Ausnahmeanschlüsse, Dämmung/Schutz und geeignetes Verfüll-/Verdichtungskonzept festlegen. | Schichtenpaket und Verdrängung nicht belastbar bestimmt. Ausgenommene Flächen gelten nicht als saniert. |

Für die Darstellung zuerst vorhandene 22 Studien zuverlässig mit Grundstücks-/Gelände-/Lagerkontext zeigen. 50 Felder ohne native Körper räumlich und mit Sperrgrund kenntlich machen. Danach geometrische Randflächen/Wege und fachlich begründete Verbaualternativen ergänzen. Eine sichere, abschnittsweise Ausführung kann erst aus den abgestimmten Nachweisen und der verantwortlichen Bauleitung folgen.

## Rechnung wiederholen und Lageplan ansehen

Das [Lageplanblatt PS01-F01](M01-2-PS01-F01-Lageplan.png) zeigt die maßstäblichen Projektionen von Grundstück, Haus/Keller, Grube sowie Haupt- und alternativ gestricheltem Reservelager. Es ist eine berechnete Studiengrafik aus dem frischen K02-Plan, keine NX-Bildschirmaufnahme. Mengen, Kontaktflächen und Lagerposition sind auf dem Blatt angegeben. Wege werden nicht erfunden. Der [Lageplan-Erzeuger](../../tools/render_m01_lageplan.py) hält den Wiederholungsweg fest.

Die zuvor lokalen Rechenschritte stehen jetzt als eigenständiges, versionierbares [Abstandswerkzeug](../../tools/check_m01_clearances.py) mit [Rechentests](../../tests/test_m01_clearances.py) zur Verfügung. Das Werkzeug benötigt nur die Python-Standardbibliothek und die vorhandenen reinen K02-Module. Es importiert kein NXOpen. Die beschleunigte Fassung prüft die tatsächlichen Segmente der vollständigen Polygonmengen, ohne konvexe Hüllen als Ersatz einzusetzen. Räumliche Suchbäume verwerfen nur Kandidaten, deren umschließende Box bereits weiter entfernt ist als das bekannte Minimum.

Vom Repository-Verzeichnis aus erzeugt dieser Aufruf einen vollständigen neuen Standard-K02-Plan und misst ihn. Die Neuberechnung kann mehrere Minuten benötigen.

```text
python tools/check_m01_clearances.py --out-dir reports/local/m01-clearances
```

Ein vorhandener vollständiger, bereits frisch berechneter Plan kann stattdessen über seinen bekannten Dateihash übernommen werden. Für genau den diesem Bericht zugrunde liegenden Plan wurde folgender Aufruf am 04.11.2026 tatsächlich mit **Exit 0** ausgeführt.

```text
python tools/check_m01_clearances.py --plan reports/local/m02/PLAN.json --plan-sha256 985c719f89586d1c8d3d311bf9c156e46b42d025b27797a367164711a343c279 --out-dir reports/local/m02/repeatable_tool
```

Der Wiederverwendungsweg verweigert abweichende Planbytes, aktuelle Eingabe-/K02-Erzeugerhashes, unvollständige Feldregister, eine andere Konfiguration und abweichende Sollmengen für Aushub, Haupt- oder Reservelager. Er berechnet die Abstände erneut aus den Planpolygonen. Die Mengen-/Hashprüfung allein wäre keine neue Geometrieerzeugung. Der feste Dateihash ist der Bezug auf den zuvor tatsächlich frisch berechneten Plan. Fehlt dieser lokale Plan nach einem anderen Checkout, ist der erste Aufruf zu verwenden.

Die Ausgabe erfolgt ausschließlich im angegebenen Unterordner von `reports/local/`. Sie umfasst `CLEARANCES.json` mit Quellen-/Werkzeug-/Plan-/Sollmengenhashes, Punktpaaren, Flächenaustritt und 231 Aushubpaaren sowie `CLEARANCES.csv` mit den 22 Mengen-/Abstandszeilen. Bei einer frischen Planung zusätzlich `PLAN.json`. Die lokalen Dateinamen sind keine vorausgesetzten versionierten Lieferdateien. Die erfolgreiche Wiederholung ergibt dieselben fünf Mindestabstände wie oben, nämlich 2,733 / 6,294 / 6,068 / 9,957 / 9,778 m.

```text
python -m unittest discover -s tests -p test_m01_clearances.py -v
```

Dieser gezielte Testlauf bestand am 04.11.2026 mit Python 3.12.14 und **11 Tests, Exit 0**. Geprüft wurden die sieben ursprünglichen analytischen Prüffälle, die räumliche Suche über viele getrennte Polygonringe sowie das Zurückweisen ungültiger Projektionen, geänderter Planbytes, geänderter Quellen und falscher Sollmengen. Der aktuelle CLI-Wiederholungslauf bestätigte alle 22 Felder und 231 Paare. Ein separater Vergleich mit dem ersten lokalen Messlauf ergab identische numerische Ergebnisse. Diese Nachweise betreffen ausschließlich die Mathematik und Wiederholbarkeit, keine NX-Ausführung oder bautechnische Freigabe.

## Fachquellen und Grenzen ihrer Anwendung

Öffentlich zugängliche Primärquellen am 04.11.2026 geprüft. Keine vollständige Normenprüfung und keine ortsbezogene Fachfreigabe.

| Quelle | Für diese Bewertung maßgebliche Aussage |
|---|---|
| [DGUV – FAQ Baugruben und Gräben, Fragen 3/4 und 11](https://www.dguv.de/fb-bauwesen/sachgebiete/tiefbau/baugruben/faq_baugruben/index.jsp) | Nachweisfreie Winkel sind an Randbedingungen gebunden. Auflast, Gelände und Wasserzufluss können die Ausnahme ausschließen. Unterfangungen und Bauzustände benötigen passende Standsicherheitsnachweise. |
| [BG BAU C469, Geböschte Baugruben und Gräben, 07/2021](https://www.bgbau-medien.de/app/daten/bausteine/c_469/c_469.htm) | Mindestens 0,60 m Schutzstreifen am oberen Rand. Einflüsse und gefährdete Anlagen berücksichtigen. Unverbaute Gräben über 1,75 m von Sohle bis GOK böschen. Zugänge und Verkehrswege vorsehen. |
| [DGUV Information 201-052, Kapitel 4](https://www.bgbau-medien.de/handlungshilfen_gb/daten/dguv/201_052/4.htm) | 45° für nichtbindige/weiche bindige Böden im dort beschriebenen Rahmen bis 5 m. Schutzstreifen von Aushub/Gegenständen freihalten. Verbau, Stirnseite, Kontrolle und Rückbau beachten. Rohrleitungsbaukontext beachten. |
| [BG BAU C467, Ausschachtungen neben Gebäuden](https://www.bgbau-medien.de/app/daten/bausteine/c_467/c_467.htm) | Gründung, Baugrund und Kräfte erkunden. Bodenaushubgrenzen beachten. Bei deren Nichteinhaltung Verbau statisch und hinsichtlich Verformung sowie Auswirkungen auf Setzungen nachweisen. Ein Verbau allein sichert keine unbekannte Fundamentauflagerung. |
| [BG BAU C468, Gründungen neben Fundamenten/Unterfangungen](https://www.bgbau-medien.de/app/daten/bausteine/c_468/c_468.htm) | Erforderliche Fundamentfreilegung/Unterfangung gesondert und abschnittsweise planen. Keine pauschale Erlaubnis durch kurze Felder. |
| [BG BAU BauPortal 2/2025 – Planung von Baugruben und Gräben](https://bauportal.bgbau.de/bauportal-22025/anwendung-der-baustellenverordnung-bei-baugruben-und-graeben) | Auch 45° können bei gleichförmigem Sand und ungünstiger Witterung problematisch sein. Baugrund, alle Bauzustände, Randbebauung, Lager und Verkehrswege gemeinsam prüfen. Wasser-/Sandaustrag kann Verbau beeinträchtigen. |

Aus diesen Quellen folgt keine standortbezogene Genehmigung für 1:1. Die Böschung ist hier ausdrücklich ein gewünschtes Studienszenario. Wo sie räumlich oder fachlich nicht passt, bleiben alternative Sicherung und Ausnahmekonzept offen. Nachbar- oder öffentliche Flächen werden nicht vorausgesetzt.

## Tatsächlich durchgeführte Prüfung dieses Berichts

- Am 04.11.2026 ausgeführt mit Python 3.12.14 der Codex-Laufzeit. `measure_clearances.py` berechnete und speicherte den vollständigen frischen K02-Plan mit Standardquellen. Anschließend wurde ausschließlich seine langsame Abstandsauswertung beendet und mit `python reports/local/m02/measure_saved_plan.py` räumlich beschleunigt fortgesetzt. Dieser Messlauf endete mit Exit 0. Der gespeicherte Plan blieb unverändert, alle Eingabe-/K02-Erzeugerhashes wurden vor der Auswertung erneut verglichen. 22 native Kandidaten, vollständige Projektionspolygone und paarweise XY-Mindestabstände wurden ausgewertet. Die räumlichen Suchbäume überspringen nur Segmente, deren Abstand bereits nach ihrer umschließenden Box größer als das gefundene Minimum ist.
- Sieben analytische Kontrollfälle der Messmethode bestanden. Dazu gehören getrennte/enthaltene Quadrate, sich kreuzende/kollineare/degenerierte Segmente, Abstand einer innenliegenden Fläche zur Außenkurve sowie Punktprüfung an einer konkaven Grenze. Numerische Kontaktgrenze 10⁻⁷ mm, keine Vermessungstoleranz.
- Die 22 Feldkennungen und mathematischen Aushubmengen stimmen mit der historischen K02-Mengenquelle überein. Maximale Differenz 0 m³. Alle fünf Eingabehashes nach der Berechnung erneut unverändert geprüft. Kein neuer nativer Mengen- oder Sichtnachweis behauptet.
- Die lokalen Detailbelege sind bewusst nicht versioniert. Sie umfassen `reports/local/m02/PLAN.json`, `CLEARANCES.json` mit nächstgelegenen Punktpaaren und Paarabständen, `CLEARANCES.csv` sowie Mess-/Berichtsskripte. Der Messskript-SHA-256 lautet `71b0ca79cc9fcc88e453cfdaf71d90ccc43b9226cc48b4f1171f1120e3f84ef7`. Frischer Plan SHA-256: `985c719f89586d1c8d3d311bf9c156e46b42d025b27797a367164711a343c279`.
- Fachquellen BG BAU/DGUV öffentlich neu gelesen. Der erneute Abruf des historischen WSDOT-PDF lief in eine Zeitüberschreitung. Dessen Faktorzuordnung ist aus den erhaltenen K02-Unterlagen übernommen, nicht als neue Prüfung dieser Tabelle ausgegeben.
- Abschließende Dokumentprüfung am 04.11.2026, Exit 0: 13 Sektionszeilen, je 22 Mengen-/Abstandszeilen, 231 Detailpaare, alle relativen Dateilinks vorhanden, keine offenen Platzhalter oder Endleerzeichen.


Keine G02-/K02-Produktivmodule oder native Dateien wurden für diese Auswertung geändert. NX wurde durch diese Berichtsauswertung weder gestartet noch bedient. Historische native Nachweise sind von der neuen mathematischen Prüfung und der getrennten M01.2-Implementierung zu unterscheiden. Deren Abschluss-/Aktualitätschecks berichtet der Hauptauftrag.
