# Roadmap: G02-Bestand zur unabhängigen Keller-Renovierungsstudie

**Aktuelle Einordnung 01.11.2026:** Der nachfolgende Text und seine P00–P10-Statuszeilen dokumentieren den historischen Planungsstand. Inzwischen wird die gesonderte [K02-Einzelfeldstudie](2026-11-01-nx-boeschung-implementation.md) mit unabhängig gespeicherter NX-Basis und Feldvarianten umgesetzt; tatsächliche Liefer-/Prüfbelege und offene Grenzen stehen im [aktuellen K02-Nachweis](../entwicklungsstand/K02-native-2026-11-01.md), direkte Modelleinstiege im [Mengenbericht](../../renovierung/planung/2026-11-01/K02_STUDIE.md). Native Quellen und reale Kopier-/Öffnungsnachweise liegen vor. Dies ist keine pauschale Abnahme der P00–P10-Pakete: A/B-Vergleich, kumulative Baufolge und grafische NX-Prüfung bleiben offen. Die ursprüngliche Roadmap wird hier nicht nachträglich umgeschrieben.

Stand: 31.10.2026. Status: **Planung erstellt; Entwicklung noch nicht begonnen.**
Auftrag: Roadmap mit wiederverwendbaren Entwicklungsprompts; Superpowers für die Entwicklung einsetzen.

**Nachfolgender Nutzerauftrag:** Native NX-Dateien im Repository mit Git verwalten und fortlaufend echte NX-Erstellbarkeit prüfen. Umsetzung/Nachweise werden im [NX-Prüfplan](2026-10-31-nx-git-und-pruefung.md) und unter `cad/nx/` geführt. Die ursprüngliche reine-Lokaldaten-Regel gilt weiterhin für fremde Originale und Arbeitskopien; gezielt erzeugte native Lieferungen dürfen unter `cad/nx/` mit Git LFS versioniert werden. P00/P01 werden erst nach ihrer jeweiligen vollständigen Abnahme als erledigt markiert.

## Ziel und Ausgangslage

Aus dem vorhandenen G02-Bestand soll eine separat entwickelte Renovierungsstudie entstehen: unabhängige NX-Basis, nachvollziehbare Abschnitte, A/B-Aushubvarianten, Mengen-/Lagerbilanz und unabhängige gespeicherte Bauzustände. G02 und seine historischen Importnachweise bleiben unverändert. Softwareabnahme, echter NX-Nachweis und fachliche Freigabe sind getrennte Ergebnisse.

Gesichert ist der Git-Import auf `main`, Ausgangscommit `085b13a86e51c587122c93d80f1a8d057a2a1936`: 643 versionierte Dateien, darunter 543 G02-Dateien. Im aktuellen lokalen Arbeitslauf wurden 571 SHA-256-Prüfsummen bestätigt. Python war über die geprüften Befehle nicht verfügbar; neue Python-/NX-Prüfungen stehen aus. Die mitgelieferten Berichte über 680 G02- und 28 Repository-Tests stammen aus der vorherigen Übergabe und werden nicht als neuer Lauf gewertet.

K01 ist keine lauffähige Basis: acht historische Unterlagen, 62 extrahierte Studienzustände, fehlende Maßnahmen-CAD und fehlender Erzeuger. Der erfolgreiche native G02-Ausgabeordner ist im Repository nicht enthalten; sein tatsächlicher Ort muss beim Start der Inventarisierung ermittelt werden.

## Vorgehensentscheidung und Alternativen

Planungsvorschlag des Assistenten auf Basis der bestehenden Anforderungen: neue Erweiterung unter `renovierung/`, vorläufige Revisionsbezeichnung **K02**. Das ist keine Behauptung einer vorhandenen K02-Implementierung.

| Ansatz | Nutzen und Grenze | Entscheidung für diese Roadmap |
|---|---|---|
| Vollständiges K01 aus einer echten lokalen Quelle wiederherstellen | Könnte Entwicklung sparen, setzt tatsächlich vorhandene Originale voraus; danach trotzdem Integritäts-/NX-Prüfung nötig. | Bei P00 bekannte lokale Quellen prüfen. Falls gefunden, Bestand bewerten und Plan bewusst anpassen; nicht unbegrenzt auf fehlende Dateien warten. |
| Separate K02-Erweiterung auf G02 | Erhält funktionierende Basis; Offline-Logik kann vor NX-Schreibzugriffen geprüft werden. | Geplanter Hauptweg, bereits durch `renovierung/README.md` und M0–M6 vorgezeichnet. |
| G02 neu aufbauen oder groß refaktorieren | Würde bestehende Pfade, Geometrie und SHA-Register berühren, ohne die K01-Lücke direkt zu schließen. | Außerhalb des Auftrags. |

## Architektur und geplante Dateien

Alle nachfolgenden neuen Dateien sind **Zielpfade**, keine Bestandsbehauptungen. Architekturentscheidungen der späteren Geometrie- und NX-Adapter werden im jeweiligen Detailentwurf anhand lokaler APIs und echter Testfälle getroffen.

| Bereich | Zielpfade | Verantwortung |
|---|---|---|
| Reiner Python-Kern | `renovierung/src/renovierung_core/` | Dateiinventar, Datenstatus, Abhängigkeiten, Kopierplanung, Varianten, Zustandsfolge und Bilanz; kein NX-Import |
| Kommandozeilenwerkzeuge | `renovierung/tools/` | Explizite Ein-/Ausgabepfade, Validierung, lokale Berichte |
| NX-Integration | `renovierung/nx/` | Rein lesende Inventarisierung; getrennte, bewusst gestartete Kopier-/Geometriejournale |
| Tests | `renovierung/tests/` | Standardbibliothek-Tests, synthetische kleine Fixtures, spätere getrennte CAD-Adaptertests |
| Nachweise | `reports/local/`, `docs/entwicklungsstand/` | Rohberichte lokal und ignoriert; kompakte versionierte Zusammenfassungen ohne native Modelle |
| Große/native Daten | `local_data/` oder ausdrücklich gewählter externer Ordner | Native Quellmodelle und neue Kopien; getrennte Ordner, nicht automatisch hochladen |

Python-Kern: >=3.10, zunächst Standardbibliothek und `unittest`; keine neue Geometriebibliothek für das Dateiinventar. Für echte Boolesche Geometrie erst in P06 Kernel, Version, Einheiten und Toleranzen anhand eines kleinen Versuchs festlegen. Keine erfundenen NXOpen-Signaturen. Lokale NX2406-Dokumentation und ein echter Minimaltest bestimmen den Adapter.

## Reihenfolge und Abnahmepunkte

Die P-Nummern sind aufrufbare Entwicklungsprompts im [Promptkatalog](2026-10-31-entwicklungsprompts.md). M0–M6 bleiben die Meilensteine aus dem [bestehenden Entwicklungsplan](../ENTWICKLUNGSPLAN.md). Keine erfundenen Kalenderfristen: Aufwand und weitere Detailpläne werden nach P00/P03 und dem NX-Kopierversuch präzisiert.

| Prompt | Meilenstein | Ergebnis | Voraussetzung / nachweisbare Abnahme | Status |
|---|---|---|---|---|
| P00 | M0 | Aktuelle Testbasis und Quellenübersicht | Python-Version/Pfad, beide Offline-Befehle mit Rückgabecode; native Quelle vorhanden oder konkret als fehlend dokumentiert | Teilweise: Python und neue native NX-Basis vorhanden; historischer Windows-Pfadtest offen, siehe [Nachweis](../entwicklungsstand/NX-native-2026-10-31.md) |
| P01 | M0 | Rein lesendes Dateiinventar mit SHA-256 | P00 Testumgebung; deterministische Ausgabe, unveränderte Quelle, keine behaupteten NX-Referenzen | Offen |
| P02 | M0 | Reales NX-Baugruppeninventar | P01; explizit gewählte native Quelle und bewusst gestarteter NX-Leselauf, Status vor/nach unverändert | Wartet auf native Quelle/NX |
| P03 | M1 | Offline-Kopierplan mit Abhängigkeitsprüfung | P02 für echten Bestand; zuvor synthetische Entwicklung möglich; alle Prototypen/Fremdreferenzen zugeordnet oder gesperrt | Offen |
| P04 | M1 | Unabhängige gespeicherte Renovierungsbasis | P03; echter NX-Kopierversuch, speichern/erneut öffnen, keine Referenzen zu Originalen oder anderen Zuständen | Wartet auf NX |
| P05 | M2 | Eingabemodell, Quellenstatus und Sperrregister | Offline parallel zu P02–P04 möglich; reale Geometrie erst nach P04 anbinden | Offen |
| P06 | M3 | Geometrieprüfung, Varianten A/B, Volumen | P04/P05 für Projektgeometrie; synthetische Tests vorher; Grenzen, Arbeitsraum, Enden/Ecken und Bilanz geprüft | Offen |
| P07 | M4 | Konsistente Abschnittsfolge und Bodenlager | P05/P06; ein offener Abschnitt, Wiederverfüllung/Restmengen nachvollziehbar, Wege und Lagerkonflikte sichtbar | Offen |
| P08 | M5 | Erster unabhängiger Demonstrationszustand | P04/P06/P07; echter NX-Nachweis für BA01 und unveränderte Originale | Offen |
| P09 | M5 | Alle zulässigen Studienzustände plus Übersicht | P08 abgenommen; Zustände voneinander unabhängig, gesperrte Abschnitte bleiben sichtbar gesperrt | Offen |
| P10 | M6 | Reproduzierbare geprüfte Lieferung | P09; Offline-/CAD-/NX-Nachweise getrennt, frischer Paket-Roundtrip und native Referenzprüfung | Offen |

Abhängigkeiten: `P00 → P01 → P02 → P03 → P04`; `P05` kann nach P00 offline beginnen; anschließend `P04 + P05 → P06 → P07 → P08 → P09 → P10`. P03 darf vor P02 mit synthetischen Inventaren entwickelt werden, ist aber ohne P02 nicht für den realen Bestand abgenommen. Kein blockierter NX-Schritt sperrt automatisch unabhängige Offline-Arbeit. Dokumentierte Testblocker schließen P00 nicht ab: P01-Codeentwicklung benötigt einen nutzbaren Interpreter und bestandene aktuelle Ausgangsprüfungen; unabhängige Quellenrecherche und Entwurfsarbeit dürfen fortgesetzt werden. Ein fehlender nativer Quellordner blockiert den realen Inventarlauf, nicht synthetische Offline-Tests.

## Prüfregeln, die jede Etappe erbt

- Importdateien unter `projects/g02/`, `renovierung/k01_unterlagen/`, `historie/diagnosen/` und historische `provenance/`-Nachweise unverändert erhalten. Keine Hash-Neuberechnung zum Verdecken von Abweichungen.
- NX-Geometrie in **mm**. Höhenquelle ausschließlich `projects/g02/data/HOEHENANSCHLUSS_G02.json`; bestehende Umgebung einmalig auf Elternkomponentenebene um **−31362.49870845903 mm** versetzt, Haus bei EG ±0,00. Inventar/Kopie übernehmen den tatsächlichen Transformationsbaum ohne erneutes Absenken. Status **PLAN_ANNAHME**.
- Werte getrennt als belegt, abgeleitet, angenommen oder unbekannt führen. Ein abgeleiteter Wert behält die Einschränkungen seiner Eingaben. Unbekannt ist nicht Null.
- Bodenplatte, Fundament und tragende Aufstandsfläche unterscheiden. UK Bodenplatte minus **100 mm** bleibt ein Prüfziel. Keine pauschalen Boden-/Wasserwerte, Böschungen, Schichtdicken oder Abschnittslängen einsetzen.
- Grundstücksgrenze bleibt Kartenreferenz. Geometrische Einhaltung ist kein vermessener Grenznachweis. Aushub, Sicherung einschließlich Verankerungen, Lager und Wege vollständig prüfen.
- Ungeprüfte Sicherung oder Gründung sperrt die reale Ausführung. Eine ausdrücklich bezeichnete Studienvariante darf sichtbar sein; Sperrstatus und Gründe bleiben erhalten. Variante B wird nicht allein wegen Platzmangels zu einer freigegebenen Lösung.
- Grundfolge: ein Abschnitt offen, frühere zulässige Abschnitte fertig/wiederverfüllt, spätere geschlossen. Ecken und Übergänge separat prüfen. Kein gleichzeitiges Freilegen des ganzen Hauses.
- Inventar, Kopierplan, simulierte Kopie und real geprüfte unabhängige NX-Kopie sind unterschiedliche Nachweise.
- Reale Kopien erfordern einen ruhenden, gespeicherten Quellstand. Direkt vor der Kopie alle Quellhashes gegen das Inventar prüfen; ungespeicherte Quellparts oder laufende Änderungen führen zum Abbruch. Keine automatische Speicherung und kein Verwerfen von Nutzerarbeit. Quellhashes nach der Kopie erneut vergleichen.

## Superpowers-Arbeitsweise für jede Entwicklungsetappe

1. Aktuellen Git-Stand, `AGENTS.md`, Anforderungen und letzte Etappenberichte lesen; Iststand vor jeder Fortsetzung neu prüfen.
2. `superpowers:brainstorming`: offene Entwurfsentscheidungen am konkreten Etappenziel klären. Vor produktiver Implementierung den Etappenentwurf prüfen lassen; bestehende Entscheidungen nicht jedes Mal neu diskutieren.
3. `superpowers:writing-plans`: kleinen ausführbaren Detailplan unter `docs/plans/` mit Dateien, Schnittstellen, Tests und Abnahme erstellen. Für P01 liegt ein [erster Detailplan](2026-10-31-m0-dateiinventar-plan.md) vor.
4. `superpowers:using-git-worktrees`: vorhandene Isolation prüfen und nötigenfalls Entwicklungsbranch/Worktree anlegen. Keine fremden Arbeitsänderungen übernehmen oder verwerfen.
5. Vorgeschlagener Standard: `superpowers:executing-plans`, etappenweise in derselben Sitzung. `superpowers:subagent-driven-development` nur bei gewählter Delegation bzw. zutreffender Skill-Vorgabe; unabhängige Aufgaben dürfen nach Schnittstellenklärung parallel bearbeitet werden.
6. `superpowers:test-driven-development`: relevanten Fehlerfall zuerst rot zeigen, minimale Implementierung, grün prüfen. Bei Fehlern `superpowers:systematic-debugging`; keine ungeprüften Reparaturserien.
7. `superpowers:requesting-code-review` und `superpowers:verification-before-completion`: Diff gegen Anforderungen und tatsächliche Testausgaben prüfen. `superpowers:finishing-a-development-branch` für den Abschluss; kleine nachvollziehbare Commits. Veröffentlichung nach dem jeweils geltenden Nutzerauftrag, kein Force-Push.
8. Etappenbericht und Status pflegen; nur nach belegter Abnahme abhängige Etappen freigeben.

## Definition einer abgeschlossenen Etappe

Unter `docs/entwicklungsstand/Pxx-<kurzname>.md` festhalten: Datum/Zeitzone, Ausgangscommit, tatsächliche Dateien und Funktionen, ausgeführte Befehle, Python-/NX-/Kernel-Versionen, Rückgabecodes, Rohberichtpfade, Einschränkungen, Reviewbefunde, offene Punkte und nächster Prompt. Nur tatsächlich ausgeführte Prüfungen als bestanden markieren; G02-Integrität vor/nach vergleichen.

Für Codeetappen: fokussierte Tests und schneller Repository-Check; vollständige G02-Suite bei M0, Änderungen an Testintegration, Meilensteinabnahme und finaler Lieferung. Reine Dokumentationsänderungen: Links, Anforderungen, Diff und unveränderte Importdateien prüfen; keine künstlichen Code-Tests. Keine historischen Testzahlen als Sollwert fest einbauen.

## Abdeckung des ursprünglichen Auftrags

| Anforderungsabschnitt | Zuständige Etappen |
|---|---|
| 1. Originalschutz und unabhängige Umgebungen | P01–P04, P08–P10 |
| 2. Geometrie, Quellen und unbekannte Angaben | P02, P05, P06 |
| 3. Zielaushubtiefe und Gründung | P05, P06 |
| 4. Varianten A/B | P06 |
| 5. Abschnitte und eindeutige Reihenfolge | P07, P09 |
| 6. Grenzen, Bodenlager und Logistik | P06, P07, P09 |
| 7. Schnitte, Sichtbarkeit und Quellenstatus | P08, P09 |
| 8. Übersicht und Abschlussnachweise | P09, P10 |

## Nächster Einstieg

**P00 starten**, danach P01. Vor produktiven NX-Läufen wird der konkrete Quellordner benötigt; ohne ihn können Dateiinventar, Kopierplanung und Statusmodell mit ausdrücklich synthetischen Tests vorbereitet werden. Der Auftrag zur Roadmap startet noch keine NX-Journale und setzt keine Etappe auf erledigt.
