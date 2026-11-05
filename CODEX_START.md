# Erster Arbeitsauftrag für Codex

## Aktueller Einstieg am 05.11.2026

Der aktuelle Gesamtstand ist die gemeinsame Hauptbaugruppe M02 mit allen 24 Anbaufeldern. [CAD-Einstieg](cad/nx/m01/README.md), [Projektstand](docs/PROJEKTSTAND.md) und [Prüfbericht](docs/entwicklungsstand/M01-2-pruefung-2026-11-04.md) zuerst lesen. `tools/nx_anbau.py` erzeugt und prüft den Gesamtstand zusätzlich zum G02/K02-Nachweis. Die bestandene Lieferung über `cad/nx/m02/CURRENT.json` bestimmen. Haus und Gelände sind gemeinsam organisiert, Zimmer bleiben Raumregister. Die Anbausohle −1,60 m gegenüber EG ist ausdrücklich eine Schnittstudie. Ausführungs- und Gründungsnachweise bleiben offen.

G02 und K02 bleiben die bestätigte historische Basis. [K02-Revisionsübersicht](cad/nx/REVISION_K02_31dba74.md), [K02-Nachweis](docs/entwicklungsstand/K02-native-2026-11-01.md) und [historischer Mengenbericht](renovierung/planung/2026-11-01/K02_STUDIE.md) erhalten ihre eigenen Lieferstände. Die darin verlinkten Feldmaster sind unabhängige historische Studien, nicht die aktuelle gemeinsame M02-Hauptdatei. Den aktuellen Gesamtstand über den oben genannten M02-Einstieg öffnen. `python tools/run_checks.py` prüft die geltenden nativen G02/K02- und M02-Nachweise. Ein Aktualitätscheck ist kein neuer NX-Lauf. Grafische Bildschirmabnahme und fachliche Ausführungsfreigabe bleiben offen.

## Historischer Startauftrag nach der Git-Übergabe

Für den aktuellen Maßnahmenumfang zusätzlich [Ergänzung E01](docs/plans/2026-11-01-keller-ergaenzung-umfang-leitungen.md) lesen: mögliche Ausnahmen für Überbau/Niedergänge, Sandboden als Nutzerangabe und Prüfung von Tiefbau.zip. V01-PDF/Katalog enthalten diese jüngere Umfangsvorgabe noch nicht; E01 muss mitgelesen werden.

Aktueller fachlicher Entwurf: [Keller-Aushub und Schachtplanung V01 vom 01.11.2026](docs/plans/2026-11-01-keller-aushub-und-schachtplanung.md), 13 Planungssektionen, A/B-Prüfung, Untersuchungsprogramm und geplante Unterbaugruppen. Nutzer bestätigt fehlende belastbare Baugrund-/Fundamentunterlagen. Der Entwurf ersetzt keine Ausführungsfreigabe; die Entwicklungsprompts K-S01–K-S06 ergänzen die folgende Roadmap.

Die historische [Roadmap](docs/plans/2026-10-31-renovierung-roadmap.md) konkretisiert M0–M6 mit Abnahmen. Ihr [Promptkatalog P00–P10](docs/plans/2026-10-31-entwicklungsprompts.md) bleibt als Planungskontext erhalten; keine pauschale Etappenabnahme und kein automatischer Neustart bei P00. Der folgende ursprüngliche Übernahmeauftrag ist historischer Kontext; spätere Etappen nicht ohne ihre Voraussetzungen starten.

Diesen Text nach dem Öffnen des Repositorys an Codex geben:

> Übernimm das Projekt HausPlan & Bauprojekt. Lies AGENTS.md, docs/PROJEKTSTAND.md, docs/ARCHITEKTUR.md, docs/TESTEN.md, renovierung/README.md und docs/ANFORDERUNGEN_RENOVIERUNG.md. Prüfe zuerst die tatsächlich vorhandenen Dateien und führe `python tools/run_checks.py` sowie `python tools/run_checks.py --full` aus. Verändere die funktionierende G02-Basis nicht. K01 ist nur als historische Dokumentation erhalten; behaupte keinen vorhandenen Renovierungserzeuger. Erstelle dann einen konkreten Implementierungsplan für eine unabhängige Renovierungsbasis und getrennte Bauzustände. Beginne anschließend mit einer kleinen, offline testbaren Inventar-/Kopierplanung ohne NX-Schreibzugriffe; die echte NX-Kopie ist ein gesonderter, bewusst gestarteter Integrationstest. Keine Maßnahmengeometrie oder Standsicherheit auf Basis unbestätigter Annahmen freigeben. Halte fehlende Informationen und Konflikte sichtbar und dokumentiere jeden tatsächlich ausgeführten Test.

## Arbeitsumgebung

Lokal: Codex im entpackten Repository öffnen. Der vorhandene NX-Ergebnisordner kann nach bewusster Freigabe lokal zugänglich gemacht werden; nicht automatisch verschieben.

Cloud: Repository anbinden und Python-Offlineprüfungen nutzen. Hier ist keine NX-/Parasolid-Lizenz vorgesehen. `scripts/setup_codex.sh` ist ein manuell auswählbarer Prüf-/Setupbefehl, kein automatisch erkannter Codex-Konfigurationsstandard. Zusätzliche lokale Dateien unter `local_data/` gelangen durch `.gitignore` nicht automatisch in eine Cloud-Sitzung.

## Nicht als ersten Schritt

Nicht das Haus neu modellieren. Nicht die Paketmanifeste blind aktualisieren. Keine Tausende vollständiger Renovierungskopien erzeugen. Keine historischen K01-Mengen als heute nachgerechnete Mengen ausgeben. Keine Abhängigkeit von den alten Chat-Links.
