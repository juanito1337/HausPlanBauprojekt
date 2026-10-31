# Erster Arbeitsauftrag für Codex

## Fortsetzung nach der Git-Übergabe

Die aktuelle [Roadmap](docs/plans/2026-10-31-renovierung-roadmap.md) konkretisiert M0–M6 mit Abnahmen. Für die Entwicklung den [Promptkatalog P00–P10](docs/plans/2026-10-31-entwicklungsprompts.md) verwenden und mit P00 samt gemeinsamem Superpowers-Startblock beginnen. Der folgende ursprüngliche Übernahmeauftrag bleibt als Kontext erhalten; spätere Etappen nicht ohne ihre Voraussetzungen starten.

Diesen Text nach dem Öffnen des Repositorys an Codex geben:

> Übernimm das Projekt HausPlan & Bauprojekt. Lies AGENTS.md, docs/PROJEKTSTAND.md, docs/ARCHITEKTUR.md, docs/TESTEN.md, renovierung/README.md und docs/ANFORDERUNGEN_RENOVIERUNG.md. Prüfe zuerst die tatsächlich vorhandenen Dateien und führe `python tools/run_checks.py` sowie `python tools/run_checks.py --full` aus. Verändere die funktionierende G02-Basis nicht. K01 ist nur als historische Dokumentation erhalten; behaupte keinen vorhandenen Renovierungserzeuger. Erstelle dann einen konkreten Implementierungsplan für eine unabhängige Renovierungsbasis und getrennte Bauzustände. Beginne anschließend mit einer kleinen, offline testbaren Inventar-/Kopierplanung ohne NX-Schreibzugriffe; die echte NX-Kopie ist ein gesonderter, bewusst gestarteter Integrationstest. Keine Maßnahmengeometrie oder Standsicherheit auf Basis unbestätigter Annahmen freigeben. Halte fehlende Informationen und Konflikte sichtbar und dokumentiere jeden tatsächlich ausgeführten Test.

## Arbeitsumgebung

Lokal: Codex im entpackten Repository öffnen. Der vorhandene NX-Ergebnisordner kann nach bewusster Freigabe lokal zugänglich gemacht werden; nicht automatisch verschieben.

Cloud: Repository anbinden und Python-Offlineprüfungen nutzen. Hier ist keine NX-/Parasolid-Lizenz vorgesehen. `scripts/setup_codex.sh` ist ein manuell auswählbarer Prüf-/Setupbefehl, kein automatisch erkannter Codex-Konfigurationsstandard. Zusätzliche lokale Dateien unter `local_data/` gelangen durch `.gitignore` nicht automatisch in eine Cloud-Sitzung.

## Nicht als ersten Schritt

Nicht das Haus neu modellieren. Nicht die Paketmanifeste blind aktualisieren. Keine Tausende vollständiger Renovierungskopien erzeugen. Keine historischen K01-Mengen als heute nachgerechnete Mengen ausgeben. Keine Abhängigkeit von den alten Chat-Links.
