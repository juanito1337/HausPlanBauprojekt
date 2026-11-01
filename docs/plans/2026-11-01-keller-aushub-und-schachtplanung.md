# Keller: Sektionen, Aushub und Schächte

Stand **01.11.2026**, Revision **V01**. **Vorplanung; keine Bauausführung freigegeben.**

**Aktuelle Umfangsergänzung:** [E01: voraussichtliche Auslassung überbauter Bereiche und Kellerniedergänge, Sandboden und Tiefbau-Unterlagen](2026-11-01-keller-ergaenzung-umfang-leitungen.md). E01 ist beim Lesen des V01-Zeichnungshefts und Sektionskatalogs mitzuberücksichtigen; deren Geometrie bleibt unverändert. Teilflächen und endgültige Ausnahmen sind noch offen.

Der Nutzer bestätigt am 01.11.2026: Es liegen noch keine belastbaren Baugrund-, Fundament- oder Kellerstatikunterlagen vor. Deshalb sind die nachfolgenden 13 Sektionen räumliche Planungsbereiche, keine zulässigen offenen Grabenlängen. Alle tatsächlichen Aushubfelder bleiben gesperrt, bis ihre Nachweise vorliegen.

## 1. Ergebnis und Lesereihenfolge

- [Zeichnungsheft: Übersicht und 13 Aushub-/Schachtblätter](../../output/pdf/Keller_Vorplanung_V01.pdf).
- [Editierbarer Sektionskatalog](../../renovierung/planung/2026-11-01/sektionen.json): Modellkoordinaten, Quellen, Konflikte und offene Bemessungswerte. Planungsdaten, kein Eingang für einen ausführbaren NX-Erzeuger.
- Dieser Projektplan: Untersuchung, Sicherung, Abdichtung, Ablauf, Nachweise und anschließende NX-Entwicklung.

Die vorhandene native G02-Lieferung bleibt die geometrische Ausgangsbasis. Neue Renovierungs-Unterbaugruppen und ausführbare Schachtkörper sind **noch nicht erzeugt**. Die hier definierten Zielnamen sind deren geplante Struktur. Das entspricht dem aktuellen Auftrag zur Planung; die Umsetzung folgt nach Prüfung des Entwurfs und der jeweiligen Voraussetzungen.

## 2. Verfahrensentscheidung

Die bestehenden Anforderungen verlangen zwei Varianten je Sektion. Dieser Entwurf behält beide bei:

| Variante | Eignung / Vorteil | Ausschluss oder zusätzlicher Prüfbedarf |
|---|---|---|
| A: geböschter Arbeitsgraben | Weniger Verbauteile; Zugriff auf die Wand möglich, sofern ausreichend Platz und geeigneter Boden vorhanden sind. | Raumbedarf aus tatsächlichem Gelände, Tiefe, Arbeitsraum, Böschung, Stirnseiten und Lastabständen; auf engem Grundstück möglicherweise nicht darstellbar. |
| B: bemessener, möglichst verformungsarmer Verbau | Räumlich kompakter; vorrangig zu untersuchen an Grenze, Anschluss und Hindernissen. | Einbau, Rückbau, Einbindung, Aussteifung, Wasser und Gebäudeeinfluss nachweisen. Hauswand ist kein ungeprüftes Widerlager. Eine Grabenbox ist nicht automatisch geeignet. |
| Kein Außenaushub in der betroffenen Zone | Bleibt eine reale Entscheidung bei überbauten/angeschlossenen Flächen oder fehlender sicherer Lösung. | Erst Anschlussaufnahme; gegebenenfalls gesonderte Tragwerksmaßnahme oder alternatives Abdichtungskonzept. Keine versteckte Verkleinerung des Sanierungsziels. |

Planungsvorschlag: Varianten je Sektion bewerten, kein pauschaler Verbau- oder Böschungsentscheid für das ganze Haus. Bei nicht lösbarem Platz-/Gründungskonflikt bleibt die Sektion gesperrt. Unterfangung ist ein gesondertes Tragwerksprojekt und kein Standardbestandteil der Dämmarbeiten.

## 3. Modellbefund und Belastbarkeit

Quelle: `projects/g02/haus/data/haus.json`, aktiver G02-Erzeuger, Höhenanschluss und native Lieferung laut `cad/nx/CURRENT.json`. Quellhashes stehen im Sektionskatalog. Lokales X/Y/Z-System in **mm**, keine bestätigte Nordrichtung. Außenwandlinien sind äußere Materialkanten; Wandmaterial liegt links in Laufrichtung. Alle hier verwendeten Kellerumrisse sind geschätzte Planableitungen und am Bau nicht bestätigt.

| Befund | Bedeutung für die Planung |
|---|---|
| Hauptkeller: 10 Außenkanten, Konturlänge 83,077 m | Geometrische Summe einschließlich unzugänglicher Anschlussbereiche; keine abrechenbare Abdichtungsmenge. |
| Anbaukeller: 4 Außenkanten, Konturlänge 43,920 m | Eigenständige Höhen-/Gründungsuntersuchung. |
| Hauptkeller UK Bodenplatte −2505 mm; Prüfziel −2605 mm | Aus FFB −2325, Aufbau 30, Platte 150 mm abgeleitet. **Keine zulässige Aushubsohle.** Fundamentunterkante und tragende Aufstandsfläche fehlen. |
| Anbau FFB −1860 mm; keine modellierte Bodenplatte | Aushub-Prüfziel unbekannt; FFB oder Wandunterkante nicht ersatzweise verwenden. |
| Umwelt-Z-Versatz −31362,49870845903 mm | Bestehende PLAN_ANNAHME, einmal am Elternteil. Kein bestätigter NHN-Bezug. |
| Gelände entlang PS01 variiert deutlich | Keine umlaufend horizontale GOK −300 mm annehmen. DGM lokal vermessen/prüfen; einzelne Modellsenke ist auffällig. |
| Haupt-/Anbauanschluss: Außenlinien teilweise nur ca. 57–69 mm auseinander | Modellunstimmigkeit, kein Arbeitsraum. PS03/PS10 benötigen Anschlussaufmaß. |
| Abweichender EG-Umriss über PS05; Garage außen an PS08 | Keine frei erreichbaren Kelleraußenwände unterstellen; Tragkonstruktion fehlt. |
| Kleinster Abstand Anbaukontur zur Kartengrenze ca. 2088 mm | Engpass bei PS11/PS12. Abstand ist kein rechtlich/bautechnisch verfügbarer Arbeitsstreifen. |

Die 0,25-mm-CAD-Toleranz ist keine Aufmaßgenauigkeit. Grundstückslinie bleibt Kartenreferenz. Leitungen aus Plänen von 2021 haben unbekannte Tiefen; Z=0 ist nur Zeichenebene. Balkonstützen besitzen keine bestätigten Fundamente. Vom Kellerabgang ist nur ein geschätztes Geländer vorhanden, kein vollständiger Schacht. Ein Lichtschacht ist als Quellenhinweis bekannt, nicht als bemessenes Bauteil.

## 4. Räumliche Sektionen und Unterbaugruppen

Sektor-IDs bleiben dauerhaft. Die Nummer ist **keine Bauabfolge**. Die vollständigen Polylinien und Längen stehen im Katalog und auf den Einzelblättern. Kurze Abschnitte oder Ecken sind nicht automatisch standsicher.

| ID | Modellkante / Bereich | Vorrangige Untersuchung und Variantenentscheidung |
|---|---|---|
| PS01 | KG_AW_01 | Leitungsquerungen, Fenster, wechselnde GOK. A/B offen; Medien zuerst orten. |
| PS02 | KG_AW_02 | Kellerabgang, Balkonstützen und Anbauende. B vertieft untersuchen; Stützenlasten/Gründung und Zugang erhalten. |
| PS03 | KG_AW_03 + 04 | Anschluss Hauptbau/Anbau. Beide Standardvarianten gesperrt; Kontakt und Lastabtrag aufnehmen. |
| PS04 | KG_AW_05, X 15190 bis 11355 | Fassadenversatz und enge Anbauecke. A/B mit Eck- und Fundamentnachweis. |
| PS05 | Rest KG_AW_05 + KG_AW_06/07 | Abweichender EG-Umriss über Keller. Standard-Außenaushub gesperrt; Zugänglichkeit und Überbau klären. |
| PS06 | KG_AW_08 | Fenster, Anschluss PS05/PS07. A/B nach Grenz-, Wasser- und Bodenprüfung. |
| PS07 | KG_AW_09 | Lichtschachthinweis, Garagenecke. Schachtanschluss und Zugang gesondert, A/B offen. |
| PS08 | KG_AW_10, Y 18930 bis 12500 | Garage auf Außenseite. Standard-Außenaushub gesperrt; Garagenfundament/Anschluss prüfen. |
| PS09 | KG_AW_10, Y 12500 bis 0 | Garagenende, Fenster, Telefontrasse. A/B offen; Leitung und Ecklasten prüfen. |
| PS10 | AN_KG_AW_01 | Anschluss plus möglicherweise freier Endbereich. Trennung erst nach Aufmaß; A/B derzeit gesperrt. |
| PS11 | AN_KG_AW_02 | Grenzengpass. B vorrangig prüfen, A nur mit komplettem Platznachweis. Keine fremden Rückanker. |
| PS12 | AN_KG_AW_03 | Engpass an Ecke zu PS11. A/B und Ecklösung, keine gleichzeitige Eckfreilegung unterstellen. |
| PS13 | AN_KG_AW_04 | Hofseite und enger Anschluss unten. A/B, unterschiedliche Haupt-/Anbauhöhen und Durchgang prüfen. |

Geplante NX-Struktur, **noch keine vorhandenen Dateien**:

```text
RENOVIERUNG_BASIS/MASTER.prt             unabhängiger G02-Klon
RENOVIERUNG_BA000/MASTER.prt             eigener gespeicherter Ausgangszustand
RENOVIERUNG_BAxxx/MASTER.prt             jeweils unabhängiger Bauzustand
  BESTAND/                             nur Kopien innerhalb dieses Zustands
  SEKTIONEN/PS01 ... PS13/MASTER.prt
    BESTANDSBEZUG                       interne Referenz, keine Originalverknüpfung
    FELDER/F001 ...                     erst nach Bemessung: offene Arbeitsfelder
    AUSHUB_A / AUSHUB_B                  Varianten gegenseitig ausschließen
    SICHERUNG / ARBEITSRAUM / ZUGANG
    SCHAeCHTE / ECKEN / DURCHDRINGUNGEN
    ABDICHTUNG / DAEMMUNG / SCHUTZ
    VERFUELLUNG / SPERREN / SCHNITTE
  BAUSTELLE/LAGER / TRANSPORT / WASSER / MESSPUNKTE
```

Jeder BA bildet einen Zeitpunkt derselben Folge ab: vorherige Felder fertig/verfüllt, aktuelles Feld im eindeutig benannten Zustand, spätere unverändert. Räumliche Sektion PS, tatsächlich offenes Feld F und zeitlicher Zustand BA sind getrennte Objekte. Ein BA kann mehrere noch gesperrte PS enthalten; Sichtbarkeit ist keine Freigabe. Für Verbaueinbau, Aushub, Abdichtung, Verfüllung und Verbaurückbau sind bei Bedarf eigene Unterzustände nötig.

Geplante Attribute: `sector_id`, `field_id`, `state_id`, `source_sha256`, `geometry_status`, `design_revision`, `evidence_ids`, `execution_release`, `blocked_reasons`. Alle Ausführungsfreigaben initial `false`; unbekannte Maße `null`, niemals 0. Kein WAVE-/Interpart-Link zu G02 oder einem anderen BA. Lage, Einheiten, Teileabhängigkeiten und unveränderte Originalhashes nach Kopie und Wiederöffnen prüfen.

## 5. Untersuchungsprogramm vor Feldbemessung

Die Untersuchungen selbst benötigen ein sicheres, von Fachplanern festgelegtes Verfahren. Dieser Plan fordert **keine eigenständige Suchschachtung bis ans Fundament**.

| Paket | Beauftragte Funktion | Zu liefern / Abnahmekriterium |
|---|---|---|
| U01 Vermessung | Vermessungsfachperson | Aktuelle GOK entlang jeder Sektion, Sockel-/Plattenhöhen, Grenzbezug, Anschlüsse, Garagen- und Treppenlage. Modellabweichungen als Revision erhalten. |
| U02 Tragwerksbestand | Tragwerksplaner | Fundamentart, Breite, Unterkante und Lastabtrag je Baukörper; Wand-/Deckensystem, Risse, Bauzustandslasten. Untersuchungsstellen und Sicherung vor Freilegung festlegen. |
| U03 Baugrund/Wasser | Geotechnische Fachplanung | Schichten, Auffüllungen, Lagerung, Festigkeits-/Verformungswerte, Durchlässigkeit, Wasserstände und Bemessungswasser; saisonale Unsicherheit und örtliche Gültigkeit dokumentieren. |
| U04 Medien | Betreiber + Ortungsfachbetrieb | Aktuelle Auskünfte und örtliche Lage-/Tiefenprüfung; Strom/Gas/Telekom sowie bislang fehlendes Trink-, Schmutz-, Regenwasser. Querungen, Schutz und etwaige Umlegung festlegen. |
| U05 Feuchte/Abdichtung | Fachplanung Bauwerksabdichtung | Ursache, Feuchte-/Salzbild, Untergrund, vorhandene Schichten, Fugen und Anschlüsse; Innenraumnutzung und erreichbares Sanierungsziel. |
| U06 Logistik/Überwachung | Bauleitung + Fachplaner | Maschinenlasten/-wege, Lagerflächen, Rettung/Zugang, Niederschlagsvorsorge, Messkonzept, Zuständigkeiten und Stop-/Wiederanlaufregeln. |

Prioritäre Untersuchungszonen: Haupt-/Anbauübergang PS03/10, Überbau PS05, Garage PS08, Stützen/Kellerabgang PS02, Grenzengpass PS11/12 sowie ein repräsentativer Hauptkellerbereich und Lichtschacht PS07. Anzahl, genaue Lage und Tiefe von Aufschlüssen bestimmt U02/U03 anhand der Leitungen und Lasten; die Liste ist keine Anweisung zum Ausheben von sieben Löchern.

## 6. Statik und Bodenstabilität: erforderliche Nachweise

BG BAU C467 behandelt bei gebäudenahen Ausschachtungen ausdrücklich Bestands- und Gründungsuntersuchung, zulässige Bodenaushubgrenzen sowie Verformungen und Setzungen [Q01]. Daraus folgt für dieses Projekt: UK Bodenplatte −100 mm darf erst nach Vergleich mit der tatsächlichen Gründung als erreichbares Ziel bewertet werden. Ein Verbau sichert nicht allein die Fundamentauflagerung.

Die Fachplanung muss die folgenden Aufgaben für **jeden relevanten Zwischenzustand**, einschließlich Ein-/Rückbau und Arbeitsunterbrechung, beantworten:

| Nachweisgruppe | Projektbezogene Frage | Freigabeunterlage |
|---|---|---|
| Gebäude/Gründung | Bleiben Tragfähigkeit, Auflagerung und Gebrauchstauglichkeit erhalten? Was geschieht bei Entlastung/Freilegung und an Ecken, Garage, Stützen, Anbau? | Bauzustandsstatik mit Bodenaushubgrenze, zulässiger Feldlänge/Tiefe und Reihenfolge. |
| Boden/Böschung | Lokaler und gesamter Bruch, Abrutschen, Auflockerung, Schichtung, Verkehr und Lagerlasten? | Geotechnischer Nachweis mit räumlicher Gültigkeit, Wasser- und Lastannahmen. |
| Verbau | Erd-/Wasserdruck, Verformung, Einbindung, Tragglieder, Aussteifung, Einbau und abschnittsweiser Rückbau? | Bemessung, Ausführungszeichnung und Montagefolge; Reaktionen nicht ungeprüft gegen Kellerwand. |
| Wasser | Wasserzutritt, Erosion/Bodenaustrag, hydraulischer Grundbruch und Auswirkungen einer Wasserhaltung? | Wasserhaltungskonzept samt Ableitung und erforderlicher Abstimmung; Schutz von Bestandsgründungen. |
| Überwachung | Welche Bewegung/Änderung ist erwartbar, wann wird gestoppt, wer entscheidet? | Messpunkte, Ausgangsmessung, projektspezifische Grenzwerte, Messhäufigkeit und Eskalationsplan. |

Die pauschale Angabe Sand reicht nicht zur Wahl eines Winkels. BG BAU erläutert, dass auch 45° in gleichförmigem Sand bei ungünstiger Witterung problematisch sein können; ein wasserdurchlässiger Verbau kann bei Sand-/Wasseraustrag ebenfalls versagen [Q04]. Daher gibt es hier keinen vorgegebenen Winkel, keine freigegebene senkrechte Erdwand und keinen Standard-Verbauquerschnitt.

Die in C468 genannten schmalen Takte betreffen besondere Fundament-/Unterfangungsarbeiten mit Voraussetzungen und eigener Folge [Q02]. Sie sind **keine pauschale Erlaubnis für 1,25 m lange Dämmgräben**. Die offene Feldlänge L, zulässige Offenzeit und Abstand zu anderen Eingriffen bleiben objektbezogen zu bemessen. Gleiches gilt für Eckabstände und Endflächen.

## 7. Aushub- und Schachtplanung je Sektion

Jedes Einzelblatt im Zeichnungsheft liefert eine lagebezogene Polylinie und zwei ausdrücklich unbemessene Querschnittskonzepte. Die Feldstationen werden später entlang der dort gerichteten Außenkante angegeben, bei Knicken je Teilkante. An Ecken gelten getrennte Freigaben. Ein Feld darf nicht automatisch um eine Ecke laufen.

**Nachzutragende Maße je Feld:** Anfang/Ende, Länge L, aktuelle GOK(s), zulässige Sohle zS(s), Fundamentumriss/-UK, lichter Arbeitsraum b, Schichtenpaket, Böschung beta oder Verbauabmessungen/Einbindung, Stirnsicherung, Zugangsfläche, Schutzstreifen und Lastabstände. Hinzu kommen Wasserstand, Nachweis-IDs und Freigabe. Bei geneigtem Gelände sind Tiefe und Raumbedarf stationär zu prüfen.

Reine Geometriebeziehung für eine ebene, einseitig geböschte Querschnittsidealisierung: `h = zGOK - zS`, `r = h / tan(beta)`, Außenbedarf ab Wand = Schichten-/Geometriezuschläge + b + r + erforderliche Randflächen. Diese Gleichung bemisst keine Böschung. Stirnböschungen, Ecken, örtliche Fundamente und Gelände ändern das Volumen und die Fläche. Schutzstreifen sind keine ausreichenden Maschinenabstände. Die BG-BAU-Hinweise zu Schutzstreifen, Zugang und Leitungen müssen in die konkrete Ausführungsplanung eingehen [Q03].

**Schachtregister (Planobjekte, keine behaupteten vorhandenen Schächte):**

| Plan-ID | Ort / Typ | Benötigte Planung |
|---|---|---|
| SCH-PS01-MED | Historische Medien nahe PS01 | Leitungsquerungen lokalisieren; gesicherte Arbeitskammer nur bei Erfordernis und Betreiberabstimmung. Keine Tiefen aus Zeichenebene übernehmen. |
| SCH-PS02-ABG | Geschätzter Kellerabgang bei PS02 | Treppe, Wände, Sohle, Schwelle, Ablauf und Gründung vermessen; Flucht-/Zugangsführung und Abdichtungsanschluss. |
| SCH-PS07-LIC | Lichtschachthinweis an KG_AW_09 | Lagehinweis X 4730–5630 mm an Y 18930 mm; Breite 900 mm bezeichnet Fenster-/Quellenbezug, **nicht Schachtmaß**. Geometrie, Befestigung, Wasseranschluss und Rückstauschutz klären. |
| SCH-PS09-MED | Telefonhinweis am unteren Wandende | Ortung vor jedem Eingriff; Schutz und möglicher Kreuzungsschacht noch zu entscheiden. |
| SCH-PSxx-Fnn | Falls bemessene Arbeitsfelder als Schächte ausgeführt werden | Alle Erdseiten und Stirnseiten, Zugang, Rettung, Aussteifung und Ein-/Ausbaufolge planen. Keine ungesicherte Stirnseite im Sand. |

Entwässerungs-/Kontrollschächte werden **erst** nach einem Wasser-/Dränkonzept hinzugefügt. Lage und Anzahl sind derzeit offen; eine umlaufende Dränleitung oder ein Pumpensumpf wird nicht als Standard angenommen. Ableitung und gegebenenfalls erforderliche behördliche Zustimmung sind vor Festlegung zu klären.

## 8. Abdichtung, Wärmedämmung und Verfüllung

Die Bestandsabdichtung benötigt zuerst Diagnose und ein zusammenhängendes Anschlusskonzept. Die öffentlich verfügbare WTA-Kurzfassung 4-6, Ausgabe 12.2024, umfasst Voruntersuchung, nachträgliche Außen-/Innen-/Bodenabdichtung und Qualitätssicherung [Q08]. Materialwahl und Detailplanung müssen diese objektspezifische Grundlage nutzen.

DIN 18533-1 liegt aktuell in Ausgabe 2026-06 vor. Ihr öffentlich beschriebener Anwendungsbereich schließt nachträgliche Bauwerkserhaltung nicht allgemein ein, sondern nur soweit geregelte Verfahren anwendbar sind [Q07]. Deshalb nicht ungeprüft Neubau-Standarddetails übernehmen. Wassereinwirkungen unter Einbezug der aktuellen DIN 4095-1:2026-06 bestimmen [Q09]. Normvolltexte wurden hier nicht geprüft.

Auszuarbeiten sind: Untergrundvorbereitung/-instandsetzung; Anschluss Wand/Sohle bzw. Fundament; Übergänge zwischen Takten; Außen-/Innenecken; Fugen Hauptbau/Anbau; Sockel; Fenster, Lichtschacht und Leitungsdurchdringungen. Die Kontinuität muss nach jedem abgeschlossenen Feld und im Endzustand nachvollziehbar sein. Aufsteigende Feuchte kann zusätzliche Maßnahmen erfordern.

Perimeterdämmung nach Wasserbeanspruchung, Druck-/Langzeitbelastung, Wärmebrücken und Herstellerverwendbarkeit festlegen; Dicke und Dämmstoff derzeit unbekannt. Keine ungeprüfte Standardschicht von 120 mm. Schutz-/gegebenenfalls Dränschicht nicht mit der Abdichtung verwechseln. Erhärtungs-/Trocknungsbedingungen und Kontrollen vor Verfüllung dokumentieren; spätere Felder dürfen fertige Anschlüsse nicht beschädigen.

Verfüllstoff, lagenweiser Einbau und Verdichtung nach Konzept, Wandlasten und Schutz der Abdichtung wählen. Verbau nur in der geplanten Folge zurückbauen; die DGUV-Hinweise behandeln insbesondere Kontrollen, Stirnseiten und die Abhängigkeit des Rückbaus vom Verfüllen [Q10]. Kein pauschaler Verdichtungswert ohne Material-/Bemessungsgrundlage.

## 9. Projektablauf und Haltepunkte

Keine belastbaren Kalendertermine oder Baukosten ohne Untersuchungen und Mengen. Angebote sollen getrennt nach Untersuchung, Planung, Sicherung, Aushub, Abdichtung/Dämmung, Wasserhaltung, Entsorgung und Wiederherstellung eingeholt werden. Unbekannte Leistungen als Bedarfspositionen kennzeichnen.

| Phase | Arbeit / Ergebnis | Abhängigkeit und Haltepunkt |
|---|---|---|
| P0 Bestandsklärung | U01–U06 beauftragen; Quellen-/Riss-/Messregister aufsetzen. | H0: Fachplanung legt sichere Untersuchungsmethoden fest. |
| P1 Vorentwurf aktualisieren | Modell/13 PS mit Aufmaß abgleichen; A/B und Alternativen vergleichen. | H1: Gründung, Baugrund, Wasser, Leitungen, Grenzen hinreichend bekannt. |
| P2 Nachweise und Ausführung | Statik/Geotechnik, Abdichtung, Verbau, Logistik und Feldfolge koordinieren. | H2: Revisionsgleiche Fachfreigaben; Rand-/Last-/Raumprüfung für alle Zustände bestanden. |
| P3 Baustelle vorbereiten | Beweissicherung, Ausgangsmessung, Schutz/Zugang, Leitungen, Wasser- und Materiallogistik. | H3: Bauleitung bestätigt vorbereitete Randbedingungen. |
| P4 Erstes bemessenes Feld | Fachplaner wählt nach Ergebnissen ein repräsentatives, möglichst konfliktarmes Feld. Keine Vorab-Zuweisung PS01. | H4: Sicherung/Bestand nach erster Freilegung mit Annahmen abgleichen; bei Abweichung stoppen. |
| P5 Wiederholungszyklus | Gesicherten Aushub, Untergrund, Abdichtung, Dämmung/Schutz, Verfüllung und Wiederherstellung abnehmen. | H5: Verdeckte Leistungen vor Verfüllung prüfen. H6: Stützwirkung/Verfüllung/Anschlüsse fertig, bevor nächstes Feld startet. |
| P6 Sonderbereiche | Ecken, Anschlüsse, Garage, Stützen, Schächte nach gesonderter Freigabe einordnen. | Nicht pauschal zuletzt: Reihenfolge in P2 anhand Tragwerk, Abdichtungsanschlüssen und Zugang festlegen. |
| P7 Abschluss | As-built-Aufmaß, Fotodokumentation, Prüf-/Materialnachweise, Mengenbilanz, Restarbeiten. | H7: Bestandsdokumentation und vereinbarte Nachkontrollen vollständig. |

Grundregel dieser Planung: nur **ein offenes, bemessenes Arbeitsfeld**; vollständiger Abschluss einschließlich wiederhergestellter Stützung vor dem nächsten. Das ist eine organisatorische Begrenzung, kein Standsicherheitsnachweis. Zulässige Nachbarabstände, Eckeingriffe und Offenzeit legt die Fachplanung fest. Eine feste umlaufende Reihenfolge wäre jetzt erfunden.

Regelmäßige Kontrolle vor Arbeitsbeginn sowie nach Regen, Frost, Unterbrechung, Erschütterung oder Änderungen; Anforderungen aus Sicherungskonzept übernehmen [Q10]. Neue Risse, Bewegungen, ausrieselnder Boden, unerwartetes Wasser oder Leitungen lösen Arbeitsstopp, Räumung des Gefahrenbereichs und fachliche Neubewertung aus. Grenzwerte werden projektspezifisch vor Start festgelegt. Keine spontane Nachschachtung, Abstützung oder Wasserabsenkung als Reparaturmaßnahme vorgeben.

## 10. Flächen, Mengen und Bodenlager

Lager-, Maschinen-, Rettungs- und Verkehrsflächen liegen vollständig innerhalb bestätigter Grundstücksgrenzen. Der aktuelle Kartenabstand genügt nicht. Die zulässige Haufenform/-höhe und Auflast gehen in die geotechnische Planung ein. Passt das Lager nicht, zuerst Feldgröße, Sequenz und externe Entsorgungslogistik prüfen; keine Nutzung fremder Fläche unterstellen.

Mengen erst aus geprüften dreidimensionalen Feldkörpern bestimmen: Aushub = Schnitt von zulässigem Aushubkörper und vorhandenem Boden; bestehende Hohlräume/Bauteile nicht als Boden zählen. Überlappende Felder nicht doppelt summieren. Anbauhöhen, Gelände und Gründung fehlen derzeit für belastbare Zahlen. Es gibt deshalb **noch keine freigegebenen m³-Mengen, Lagerflächen oder Kosten**.

Bilanz pro BA getrennt für gewachsenen, gelockerten und eingebauten Zustand führen. Auflockerung und Verdichtung nicht gleichsetzen. Massenbilanz: Anfangslager + Aushubzufuhr + Anlieferung − Wiederverwendung − Abfuhr = Endlager, bei Volumina erst über nachgewiesene Zustandsfaktoren/Dichten umrechnen. Ungeeigneten und belasteten Boden getrennt behandeln. Nach Wiederverfüllung darf dieselbe Menge nicht weiterhin als vollständiger Haufen erscheinen.

## 11. Nächste Entwicklungsprompts mit Superpowers

Diese Arbeit ergänzt die vorhandene [Roadmap P00–P10](2026-10-31-entwicklungsprompts.md), ersetzt weder deren Kopiernachweis noch startet sie spätere Module. Gemeinsamer Auftrag für jeden Prompt: AGENTS lesen, passende Superpowers-Skills verwenden, G02 erhalten, Unbekanntes sperren; vor Abschluss `tools/nx_project.py check`, bei Erzeuger-/Geometrieänderung echter NX-Lauf samt frischem und verschobenem Wiederöffnen. Neue K02-Quellen in den Fingerprint aufnehmen. Software-PASS und fachliche Freigabe getrennt ausgeben.

**K-S01: Sektionsmodell.** „Überführe nach abgestimmtem Entwurf den V01-Katalog in ein validiertes Planungsmodell unter renovierung/. PS-, Feld- und BA-IDs trennen; Nullwerte blockieren Ausführungsgeometrie. Teste vollständige Konturabdeckung ohne Doppelzählung, Konfliktzonen und unveränderte Quellen. Keine Standardmaße ergänzen.“

**K-S02: Unabhängige NX-Unterbaugruppen.** „Erfülle erst Roadmap P01–P04. Erzeuge in einer kleinen echten NX-Testbaugruppe einen unabhängigen Klon mit einer PS-Unterbaugruppe, internen Referenzen und sichtbarem Sperrstatus. Wiederöffnen/Portabilität sowie unveränderte Originale nachweisen. Erst danach auf PS01–PS13 skalieren und `.prt` unter cad/nx mit Git LFS versionieren.“

**K-S03: Nachweise und Aufmaß.** „Implementiere danach Datenherkunft und Freigaberegister je Feld: Geometrie, Gründung, Boden, Wasser, Leitungen, Grenze, Lasten, Sicherung, Abdichtung. Revisionen verknüpfen; Änderungen entwerten abhängige Freigaben. Fehlende oder veraltete Belege führen zur Sperre.“

**K-S04: A/B und Schachtkörper.** „Nur mit dokumentierten Eingaben erzeugen: Gelände-Schnitt, zulässige Sohle, Arbeitsraum, seitliche und stirnseitige Sicherung, Verbau-Einbauhülle, Zugang und Randflächen. Keine Normbemessung simulieren. Grenz-/Bauteilkollisionen erhalten und anzeigen. Eine unbemessene Studie klar von freigegebenem Feld trennen; echte NX-Boolesche Operationen minimal testen.“

**K-S05: Baufolge und Mengen.** „Führe unabhängige BA mit Einbau/Aushub/Abdichtung/Verfüllung/Rückbau-Zuständen ein. Default höchstens ein offenes Feld; Ecken und Anschlussabhängigkeiten explizit. Prüfe Materialzustände, konservative Massenbilanz, Lagerlasten/-flächen und Entwertung nach Planänderung. Volumina aus aktuellen Körpern, nicht historischen K01-Tabellen.“

**K-S06: Planableitung.** „Erzeuge revisionsgleiche Lage-, Quer-/Längsschnitt- und Schachtpläne aus freigegebenem Feldmodell. Jede Zeichnung zeigt Status, Bezugsmaße, Quelle, Sicherung, Bauzustand, Lasten/Wasser und Haltepunkte. In NX erzeugen und öffnen; PDF visuell prüfen. V01 erst ersetzen, wenn seine offenen Angaben nachvollziehbar geklärt sind.“

## 12. Quellen und Grenzen der Recherche

Abruf 01.11.2026. Primärquellen; Zusammenfassungen sind keine vollständige Normprüfung. BG-/DGUV-Texte wurden öffentlich gelesen; bei DIN nur Produktbeschreibung/Metadaten, bei WTA Kurzfassung/Verzeichnis. Normenbeschaffung, örtliche Anwendbarkeit und konkrete Nachweise gehören in P2. Keine privaten Gutachten vorhanden.

| ID | Quelle | Verwendung |
|---|---|---|
| Q01 | [BG BAU C467, 07/2021](https://www.bgbau-medien.de/app/daten/bausteine/c_467/c_467.htm) | Ausschachtungen am Bestand, Bodenaushubgrenze, Setzungen. |
| Q02 | [BG BAU C468, 07/2017](https://www.bgbau-medien.de/app/daten/bausteine/c_468/c_468.htm) | Abgrenzung von Fundamentfreilegung/Unterfangung und ihren Voraussetzungen. |
| Q03 | [BG BAU C469, 07/2021](https://www.bgbau-medien.de/app/daten/bausteine/c_469/c_469.htm) | Böschung, Randflächen, Einflüsse, Zugang. |
| Q04 | [BG BAU BauPortal 2/2025](https://bauportal.bgbau.de/bauportal-22025/anwendung-der-baustellenverordnung-bei-baugruben-und-graeben) | Sand/Witterung, Wasser-Sand-Gemisch, alle Bauzustände. |
| Q05 | [DIN 4123:2013-04](https://www.dinmedia.de/de/norm/din-4123/170468164) | Normrahmen Arbeiten im Einfluss bestehender Gebäude, Metadaten. |
| Q06 | [DIN 4124:2012-01](https://www.dinmedia.de/de/norm/din-4124/147362129) | Normrahmen Böschungen, Verbau, Arbeitsräume, Metadaten. |
| Q07 | [DIN 18533-1:2026-06](https://www.dinmedia.de/de/norm/din-18533-1/399850897) | Aktuelle Abdichtungsnorm und Anwendungsgrenze im Bestand. |
| Q08 | [WTA 4-6, 12.2024, Kurzfassung](https://www.wta-international.org/fileadmin/user_upload/Geschaeftsstelle/Schriften/Kurzfassungen/4-6-24.pdf) | Nachträgliche Abdichtung und Qualitätssicherung. |
| Q09 | [DIN 4095-1:2026-06](https://www.dinmedia.de/de/norm/din-4095-1/397841413) | Aktuelle Begriffe/Wassereinwirkungen, Metadaten. |
| Q10 | [DGUV Information 201-052, Kapitel 4](https://www.bgbau-medien.de/handlungshilfen_gb/daten/dguv/201_052/4.htm) | Verbaukontrolle, Stirnseiten, Rückbau und Leitungen; Rohrleitungsbaukontext beachten. |

## 13. Abnahme dieses Planungsstands

V01 ist als vollständiger Vorplanungsauftrag nutzbar, aber nicht als Absteckungs-, Aushub- oder Unterfangungsfreigabe. Offen bleiben insbesondere Fundament- und Baugrunddaten, Wasser, aktuelle Leitungen, bestätigte Grenze, erreichbare Anschlüsse, endgültige Feldabmessungen, Reihenfolge, Mengen und Kosten. Die Begutachtung durch einen Software-/Planungsreviewer ersetzt keine fachliche Prüfung durch Tragwerks-/Geotechnikplaner.

Die tatsächlichen Datei-, Zeichnungs- und NX-Aktualitätsprüfungen werden im separaten [Prüfprotokoll](../../renovierung/planung/2026-11-01/PRUEFUNG.md) dokumentiert. Nur dort bestätigte Ergebnisse gelten als ausgeführt.
