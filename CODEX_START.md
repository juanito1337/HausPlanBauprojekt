# Erster Arbeitsauftrag für Codex

## Aktueller Einstieg am 03.11.2026

Der jüngste Nutzerauftrag verlangt eine gemeinsame Hauptbaugruppe. [M01-Einstieg](cad/nx/m01/README.md) und [Umsetzungsplan](docs/plans/2026-11-03-hauptbaugruppe.md) zuerst lesen. `tools/nx_master.py` erzeugt/prüft M01 zusätzlich zum unveränderten G02/K02-Nachweis. Alte K02-Feldmaster sind die historischen unabhängigen Studienkopien; sie sind nicht die gemeinsame Hauptdatei. Zimmer sind vorerst nur Quellenregister. Die jeweils bestandene native Lieferung über M01-CURRENT bestimmen; einen Versuch mit FAIL nicht als geliefert ausgeben.

Zuerst [aktuellen CAD-Revisionsstand K02 / 31dba74](cad/nx/REVISION_K02_31dba74.md), [Projektstand](docs/PROJEKTSTAND.md), [K02-Nachweis](docs/entwicklungsstand/K02-native-2026-11-01.md) und [Mengenbericht der geometrisch gleichen Erstlieferung](renovierung/planung/2026-11-01/K02_STUDIE.md) lesen. Die Modelllinks des Mengenberichts gehören zur früheren Lieferung; aktuelle Master stehen in der Revisionsübersicht. Der getrennte K02-Studienerzeuger ist implementiert; vorhandene native Kopien und Nachweise nicht wegen des folgenden historischen Startauftrags erneut entwickeln. `python tools/run_checks.py` und `python tools/nx_project.py check` prüfen den aktuellen gelieferten Stand. Bekannter historischer Windows-Pfadtest und offene grafische/fachliche Prüfungen bleiben ausdrücklich im Nachweis getrennt ausgewiesen. Nächsten Auftrag am tatsächlichen Stand abgrenzen.

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
