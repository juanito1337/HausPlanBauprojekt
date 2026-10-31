# Entwicklungsprompts für die Renovierungs-Roadmap

Stand: 31.10.2026. Geplante Arbeit; keine der Etappen ist durch dieses Dokument umgesetzt.
Zuordnung und Abnahmen: [Roadmap](2026-10-31-renovierung-roadmap.md).

## Verwendung

Pro Arbeitsauftrag den gemeinsamen Startblock und genau einen Pxx-Block verwenden. Kurzaufruf im Projektchat: **„Arbeite P00 aus docs/plans/2026-10-31-entwicklungsprompts.md mit dem gemeinsamen Startblock ab.“** Relative Pfade beziehen sich auf den Git-Repository-Stamm, derzeit den inneren Ordner `HausPlanBauprojekt/HausPlanBauprojekt`.

Kein Prompt behauptet, dass seine geplanten Dateien bereits existieren. Erledigte Vorgänger anhand ihrer Berichte und des aktuellen Git-Stands prüfen. Fehlende lokale NX-Modelle gezielt erfragen, sobald sie erforderlich sind; bis dahin unabhängige Offline-Arbeit fortsetzen. Keine automatische Kette bis P10 ohne Kontrolle der Abnahmepunkte.

## Gemeinsamer Startblock

```text
Arbeite am Projekt HausPlanBauprojekt auf Deutsch. Lies AGENTS.md,
docs/PROJEKTSTAND.md, docs/ARCHITEKTUR.md, docs/TESTEN.md,
docs/ANFORDERUNGEN_RENOVIERUNG.md und
docs/plans/2026-10-31-renovierung-roadmap.md sowie vorhandene Etappenberichte.
Prüfe den aktuellen Git-Stand und die tatsächlich verfügbaren Eingaben.

Nutze Superpowers für die Entwicklung: brainstorming für den Etappenentwurf,
writing-plans für einen konkreten Detailplan unter docs/plans/,
using-git-worktrees bei erforderlicher Isolation und executing-plans für
die Umsetzung. Nutze test-driven-development für Code und systematic-debugging
bei Fehlern. Schließe mit requesting-code-review und
verification-before-completion ab. Keine Etappe allein wegen historischer
Testberichte als erledigt behandeln.

G02 und die historischen Importnachweise unverändert erhalten. K01 ist nur
historisches Material. Neue Renovierungslogik unter renovierung/ entwickeln;
Repository-Testintegration und neue Dokumentation dürfen gezielt ergänzt werden.
Native Dateien nicht automatisch speichern, schließen, überschreiben oder
hochladen. NX-Schreibläufe brauchen einen konkreten, bewusst gestarteten Auftrag.
Kein NXOpen in gewöhnliches Python installieren. Keine fremden Änderungen verwerfen.

Alle globalen Prüfregeln der Roadmap gelten. Offline-Test, CAD-Kernelprüfung,
echter NX-Lauf und fachliche Freigabe getrennt ausweisen. Unbekannte Werte und
gesperrte Bereiche sichtbar erhalten. Keine Ausführungsfreigabe aus Tests ableiten.

Bearbeite nur die folgende Etappe. Liefere Code/Dateien, tatsächliche Tests
mit Datum und Rückgabecode, Reviewbefunde und einen kompakten Etappenbericht
unter docs/entwicklungsstand/. Aktualisiere den Status in der Roadmap und
verlinke den Nachweis. Nenne die nächste zulässige Etappe und konkrete Blocker.
```

## P00 — Testumgebung und Ausgangsstand

```text
Ziel: Eine reproduzierbare aktuelle Ausgangsbasis schaffen, ohne G02 zu ändern.
Prüfe Repository-Stamm, Branch, Ausgangscommit und vorhandene Python-Interpreter.
Nutze zuerst eine vorhandene geeignete Installation (>=3.10). Falls keine
verfügbar ist, bereite die konkrete Einrichtung passend zur lokalen Umgebung
vor; NX-Python und NX-Bibliotheken nicht verändern. Halte fest, was tatsächlich
eingerichtet und ausgeführt wurde. Keine pauschale Installation von CAD-Paketen.

Führe python tools/run_checks.py und python tools/run_checks.py --full mit
dem konkret ausgewählten Interpreter aus. Bei Abweichungen zuerst Ursache
reproduzieren; Hashregister niemals passend zum Fehler umschreiben.
Prüfe lokale bekannte Eingangsorte bzw. vorhandene Dateiverweise auf den
erfolgreichen G02-Ausgabeordner und vollständiges K01. Keine Vollplattensuche.
Fehlt ein benötigter Ort, frage gezielt nach dem Pfad; fehlendes K01 blockiert
die separate Neuentwicklung nicht.

Ergebnis: docs/entwicklungsstand/P00-ausgangsstand.md mit Interpreter,
Testbefehlen/-codes/-logs, Quellenübersicht, offenen Punkten und P01-Startstatus.
Abnahme der Testbasis: beide aktuellen Prüfungen bestanden. Bei reproduzierbaren
Blockern bleibt die Etappe offen oder teilweise erledigt; nur unabhängige Recherche
und Entwurfsarbeit fortsetzen. Fehlende native Quellen getrennt als Blocker für
den realen Inventarlauf führen; sie verhindern synthetische P01-Tests nicht.
Nicht vorhandene Quellen oder übersprungene Tests sind kein Erfolg.
```

## P01 — Rein lesendes Dateiinventar

```text
Ziel: Einen ausdrücklich ausgewählten lokalen Quellordner inventarisieren,
ohne NX zu öffnen oder Quelldateien zu ändern.
Nutze docs/plans/2026-10-31-m0-dateiinventar-plan.md als Detailentwurf.
Implementiere deterministische Dateiliste, Größen, SHA-256 und erkennbare
Fehler wie unlesbare Dateien, Verknüpfungen, Namenskollisionen oder Änderungen
während des Lesens. Referenzen innerhalb nativer .prt bleiben unbekannt.
Schreibe Berichte nur in neue, ausdrücklich gewählte Ausgabedateien außerhalb
der Quelle; verweigere Überschreiben und Ausgaben innerhalb der Quelle.

Zielpfade: renovierung/src/renovierung_core/inventory.py,
renovierung/tools/inventory.py, renovierung/tests/test_inventory.py.
Integriere die Tests gezielt in tools/run_checks.py; bestehende Tests erhalten.
Beweise Quellschutz an temporären Fixtures und teste Fehlerpfade tatsächlich.
Abnahme: Offline-Tests bestanden, Quellen unverändert, keine NX-Unabhängigkeit
aus einem bloßen Dateiscan behauptet. Ein synthetischer Test ersetzt keinen
Inventarlauf am echten G02-Ausgabeordner.
```

## P02 — NX-Baugruppeninventar ohne Schreibzugriffe

```text
Voraussetzung: P01 und ein explizit ausgewählter erfolgreicher G02-Ausgabeordner.
Ziel: Den tatsächlichen Baugruppen- und Referenzbestand rein lesend dokumentieren.
Prüfe die lokale NX2406-API-Dokumentation und vorhandene G02-Leselogik, ohne
G02 zu verändern. Definiere das Inventarformat zuerst und teste seine Validierung
offline. Implementiere den NX-Adapter getrennt unter renovierung/nx/.

Erfasse Vorkommen und Prototypen mit stabilen IDs, vollständigen lokalen Pfaden,
Parent-Kind-Beziehungen, Einheiten, lokalen und Welttransformationen, Unterdrückung,
Ladezustand, Referenzmengen, Materialien, Änderungszustand und externen Abhängigkeiten.
Unbekannte WAVE-/Interpart- oder sonstige Referenzen nicht als leer behandeln.
Keine vorhandenen Parts automatisch speichern, schließen oder verwerfen.
Vorher/Nachher-Zustand prüfen. Falls ein verlässlicher Leselauf in der aktuellen
Sitzung nicht möglich ist, konkrete Grenze dokumentieren und Testkopie vorsehen.

Abnahme: bewusst gestarteter echter NX-Minimaltest und anschließend echter
Inventarbericht; unveränderte Quelldateien und Sitzungszustände. Ohne NX bleibt
der Adapter als nicht integriert getestet markiert; Offline-Parser kann fertig sein.
```

## P03 — Offline-Kopierplan und Referenzprüfung

```text
Ziel: Aus einem validierten P02-Inventar einen deterministischen Kopierplan
erstellen; keine .prt kopieren oder NX starten.
Definiere renovierung/src/renovierung_core/clone_plan.py mit Tests für einen
Graphen aus Baugruppen, mehrfach verwendeten Prototypen und externen Referenzen.
Plane eindeutige neue Zielpfade je unabhängiger Umgebung. Ein Prototyp darf
innerhalb derselben Umgebung geteilt werden, zwischen Original/Basis/Bauzuständen
aber keine gemeinsam bearbeitbare Datei verbleiben.

Prüfe fehlende Dateien, unbekannte Referenzarten, Zyklen, externe Abhängigkeiten,
Windows-Groß-/Kleinschreibung, Zielkollisionen, Pfadlängen und vorhandene Ziele.
Unaufgelöste Abhängigkeit ergibt einen begründeten Sperreintrag. Vollständige
Quell-/Zielzuordnung, erwartete Quellhashes und unverändert übernommene
Transformationen ausgeben. Kopiervoraussetzung ist ein ruhender gespeicherter
Quellstand; vor realer Ausführung alle Hashes und NX-Änderungszustände erneut prüfen.
Abnahme: Offline-Gegenbeispiele bestanden; realer Plan erst mit P02-Inventar
bewertet. Ein gültiger Plan ist noch keine unabhängige NX-Kopie.
```

## P04 — Echte unabhängige Renovierungsbasis

```text
Voraussetzung: P03 und eine für den Kopierversuch verfügbare NX2406-Umgebung.
Ziel: Erst die Clone-Schnittstelle an einer kleinen Testbaugruppe nachweisen,
dann eine unabhängige Renovierung_Basis aus dem echten Bestand erzeugen.
Teste Unterbaugruppe, mehrfach genutzten Prototyp und eine echte Fremdreferenz.
NX-API anhand lokaler Dokumentation belegen; gewöhnliches Dateikopieren oder
eine neue Masterdatei mit Originalreferenzen erfüllen das Ziel nicht.

Bereite einen konkret prüfbaren Laufplan mit Quell-/Zielpfaden, erwarteten
Dateien und Abbruchregeln vor. Führe den Schreibtest nur bewusst beauftragt aus.
Nutze einen neuen Zielordner und verweigere vorhandene Ziele. Bei Abbruch
Teilergebnisse kennzeichnen, niemals Originale bereinigen. Speichern und erneutes
Öffnen ausschließlich an den neuen Test-/Zieldateien durchführen.
Vor Beginn ruhenden gespeicherten Quellstand sicherstellen: ungespeicherte
Quellparts, abweichende Quellhashes oder parallele Änderungen führen zum Abbruch,
nicht zum automatischen Speichern oder Verwerfen. Quelle während des Laufs
nicht bearbeiten; nach dem Lauf Hashes erneut gegen den Kopierplan vergleichen.
Prüfe Quellhashes und Änderungszustand vor/nach, alle Referenzen, Einheiten,
Positionen, Unterdrückungen, Referenzmengen und Materialien. Eine gezielte Änderung
an einer neuen Testkopie darf Quelle und andere Testkopien nicht beeinflussen.
Abnahme: echte Nachweise für Testbaugruppe und danach Renovierungsbasis.
```

## P05 — Planungsdaten, Herkunft und Sperrregister

```text
Ziel: Ein offline testbares Datenmodell mit nachvollziehbarer Herkunft erstellen.
Entwirf und implementiere unter renovierung/src/renovierung_core/ die Daten
für Kellerkontur, Gelände, Bodenplatte, Fundamente, tragende Aufstandsflächen,
Anbauten, Treppen, Lichtschächte, Leitungen, Zugänge und Grundstücksreferenz.
Jeder fachliche Wert benötigt Einheit, Quelle und Status: belegt, abgeleitet,
angenommen oder unbekannt. Abgeleitete Werte tragen Einschränkungen weiter.
Fehlende Angaben nicht als Null und Annahmen nicht als Messwerte behandeln.

Modelliere Ziel UK Bodenplatte minus 100 mm als Prüfziel. Keine historischen
K01-Maße oder Standardwerte unbemerkt übernehmen. Führe Sperrgründe und jeweils
benötigte Nachweise; Software darf fachliche Sperren nicht automatisch freigeben.
Teste insbesondere fehlende Gründung, unbekanntes Wasser, Einheitenverwechslung,
widersprüchliche Quellen und unbekannte Leitungstiefe. Bestehende zehn
Überschneidungspaare und zwei blockierte Öffnungen nicht pauschal schließen.
Abnahme: validiertes Statusmodell und nachvollziehbares Register; reale
Geometrieanbindung benötigt P04, synthetische Tests können vorher stattfinden.
```

## P06 — Varianten, räumliche Konflikte und Aushubvolumen

```text
Voraussetzung für reale Projektgeometrie: P04/P05.
Ziel: Varianten A (Böschung) und B (fachlich zu prüfender Verbau) für einzelne
Studienabschnitte geometrisch bewerten. Erstelle zuerst einen Etappenentwurf
für Kernel/Adapter, Datenvertrag, Toleranzen und einen kleinen CAD-Versuch.
Verwende echte Modellgeometrie für das Geländevolumen; begründe jede Näherung.

Arbeitsraum außerhalb von Abdichtung/Dämmung/Schutz und Sicherung messen.
Querböschung, Stirnseiten, Hausecken, wechselndes Gelände, Überlappungen und
Gründung separat berücksichtigen. Alle Flächen einschließlich Verankerungen,
Lager und Wegen gegen die unveränderte Grundstücksreferenz prüfen. Nichtkonvexe
Grenzen und Randfälle testen. Eine Bounding Box allein ist kein Geometrienachweis.
Böschungswinkel, Verbauabmessungen und Schichtdicken nur mit ausgewiesener Quelle
oder expliziter Studienannahme; fachliche Sperren bleiben bestehen.

Volumen aus tatsächlich erzeugter Aushubgeometrie in konsistenten Einheiten
berechnen; unabhängige Vergleichsfälle und numerische Bilanz prüfen. Teste
bekannte synthetische Volumen, mm³/m³, degenerierte Körper und Geometriefehler.
Abnahme: reproduzierbare Variantenberichte mit Auswahlbegründung/Konflikt und
separatem fachlichem Status. Kein Automatismus „passt geometrisch = sicher“.
```

## P07 — Baufolge, Wiederverfüllung und Lagerbilanz

```text
Voraussetzung: P05/P06 mit nachvollziehbaren Abschnittsgeometrien.
Ziel: Deterministische Zustandsfolge und vollständige Bodenbilanz entwickeln.
Leite Abschnitte aus Kontur, Hindernissen und Sperren ab; übernimm nicht
unbesehen die historische Anzahl 62 oder historische Feldlängen.
Standard: höchstens ein aktiver offener Abschnitt; vorherige zulässige Abschnitte
fertig/wiederverfüllt, nachfolgende geschlossen. Ecken und gesperrte Abschnitte
explizit behandeln. Gesperrte Schritte verhindern abhängige Ausführung und
bleiben als ungeklärter Teilumfang sichtbar.

Definiere Bilanzbasis eindeutig (Festboden, lockeres Lager, eingebauter Boden).
Faktoren für Auflockerung, Wiederverwendbarkeit und Einbau benötigen Quellenstatus;
Fremdmaterial, verdrängte Volumen und Restmengen gesondert buchen. Kein Boden
verschwindet nach Wiederverfüllung. Lagergeometrie muss Lagerbestand entsprechen.
Prüfe Flächen, Höhen, Zugänge, Transportwege und Konflikte mit Sicherungen;
Lagerlasten als fachlichen Prüfpunkt führen. Fehlender Platz ergibt Konflikt,
kleinere Studienabschnitte oder neue Reihenfolge, keine erfundene Nachbarfläche.
Abnahme: Tests über mehrere Zustände, Abbruch/Wiederaufnahme, Restboden,
fehlende Parameter und Platzmangel; Bilanz je Schritt und insgesamt stimmt.
```

## P08 — Ein vollständiger Demonstrationszustand in NX

```text
Voraussetzung: echte unabhängige P04-Basis sowie P06/P07-Ergebnisse.
Ziel: Einen ersten kleinen Studienzustand Renovierung_BA01 vollständig liefern.
Nutze P03/P04, um neue unabhängige native Dateien zu erzeugen. Änderungen nur
in dieser Umgebung. Zeige Aushub, Böschung/Verbau als gekennzeichnete Studie,
Arbeitsraum, getrennte Abdichtung/Dämmung/Schutz, Bodenlager, Wege und Grundstück.
Erzeuge nachvollziehbare Schnitte für Kellerwand, Platte und Fundamentstatus.
Unbekannte oder angenommene Geometrie deutlich unterscheiden und Sperrgründe
sichtbar beschriften. Keine Gebäudeänderung zum Kaschieren von Konflikten.

Prüfe nach bewusst gestartetem NX-Lauf Speichern/erneutes Öffnen, Referenzen,
Transformationen und unveränderte Original-/Basisdateien. Die Teständerung
in BA01 darf weder Original noch Renovierungsbasis beeinflussen.
Abnahme: prüfbarer BA01 mit lokalem Manifest und Darstellung, passende Mengen
und dokumentierte NX-Nachweise. Erst danach die Zustandsserie erzeugen.
```

## P09 — Zustandsserie und Gesamtübersicht

```text
Voraussetzung: P08 abgenommen.
Ziel: Alle nach aktuellem Studienplan zulässigen Zustände unabhängig erzeugen.
Plane Speicherbedarf vor dem Lauf. Verwende eindeutige neue Zielordner; kein
Wiederverwenden bearbeitbarer Dateien zwischen Zuständen. Wiederaufnahme nur
anhand verifizierter eigener Manifeste; vorhandene fremde Ziele nicht überschreiben.
Fehlerzustände sichtbar markieren, keine unvollständigen Kopien als fertig melden.

Prüfe für jeden Zustand: Referenzabschluss, gleiche Position/Einheiten/Grenzen,
genau definierter aktiver Abschnitt, frühere Wiederverfüllung, zukünftiger Bestand,
Schichten, Lager und Zugänge. Gesperrte Hausseiten bleiben im Gesamtumfang sichtbar;
keinen vollständigen Hausabschluss behaupten, wenn Bereiche ungeklärt bleiben.
Erzeuge eine kompakte CSV/HTML-Übersicht mit Abschnitt, Seite, Reihenfolge,
Variante, Maßen, Aushubvolumen, Lagerfläche, Restmengen, Quellenstatus und Sperren.
Abnahme: vollständige Zustands-/Dateiliste, Offline-Bilanz, echte NX-Referenzprüfung
und dokumentierte Sichtprüfung; Grundschutz über alle Originalhashes bestätigt.
```

## P10 — Prüfung und reproduzierbare Lieferung

```text
Voraussetzung: P09 und zuordenbare Nachweise aller Vorgänger.
Ziel: Eine nachvollziehbare Software- und Studienlieferung erstellen.
Führe fokussierte Renovierungstests, python tools/run_checks.py und --full aus;
optionale CAD-Prüfungen nur mit dokumentierter tatsächlicher Umgebung.
Prüfe die vollständige Anforderungsabdeckung und offene Reviewbefunde.

Nutze tools/package_repo.py für einen sauberen committed Quellstand, Ziel
außerhalb des Repositorys; frisch entpacken und Hashes/Einstiegspunkte prüfen.
Native NX-Lieferung separat planen: vollständige unabhängige Komponenten und
Referenzen, erneut öffnen, keine Lizenz-/Zugangsdaten und kein automatischer Upload.
Repository-ZIP und native Baugruppe sind unterschiedliche Lieferartefakte.

Liefere Release-Notizen mit Ausgangs-/Endstand, tatsächlich ausgeführten Tests,
NX-/Kernel-Versionen, unveränderten Quellen, Annahmen und offenen fachlichen
Punkten. Keine Ausführungsfreigabe behaupten. Veröffentlichung nur im geltenden
Nutzerauftrag und mit geprüfter Dateiliste; keine Historienumschreibung.
Abnahme: existierende geprüfte Artefakte, reproduzierbarer Start und getrennte
Nachweise für Software, CAD, NX und noch ausstehende fachliche Prüfung.
```

## Fortsetzung nach einer Unterbrechung

```text
Lies Roadmap, Promptkatalog und docs/entwicklungsstand/. Prüfe Git-Status und
die angegebenen Artefakte. Ermittle die erste noch nicht abgenommene Etappe;
wiederhole erledigte Entwicklung nicht ohne neue Befunde. Verwende den
gemeinsamen Startblock und den zugehörigen Pxx-Prompt. Bei fehlendem NX-Zugang
bearbeite zulässige unabhängige Offline-Arbeit und benenne den konkreten Blocker.
```
