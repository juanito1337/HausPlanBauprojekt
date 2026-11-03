# HausPlan & Bauprojekt · NX / Codex

**Entwicklungsstand vom 03.11.2026.** Dieses Repository enthält den unveränderten G02-Quellbestand, die native K02-Böschungs-/Abraumstudie, die neue integrierte M01-Hauptbaugruppe, erhaltene K01-Unterlagen und den Außenrundgang.

**Aktuelle Hauptdatei:** [HAUSPROJEKT_MASTER_M01.prt](cad/nx/m01/20261103T005043Z_07d05f/HAUSPROJEKT_MASTER_M01.prt), dazu [Bedienung und Ladehinweise](cad/nx/m01/README.md). Die Hauptbaugruppe enthält Haus, Umgebung und die schaltbaren Bauabschnitte. Geschosse und Dach sind gegliedert; Zimmer bleiben ausdrücklich Raumregister ohne erfundene Wandzuordnung. Lauf `20261103T005043Z_07d05f`: 199 native Parts, tatsächlicher Neuaufbau sowie frisches und verschobenes Öffnen bestanden. [Prüfbericht und Grenzen](docs/entwicklungsstand/M01-pruefung-2026-11-03.md), [Entwurf und Prüfplan](docs/plans/2026-11-03-hauptbaugruppe.md).

**Aktueller CAD-Revisionsstand K02 / 31dba74:** [Revisionsübersicht mit allen 23 NX-Masterlinks](cad/nx/REVISION_K02_31dba74.md) oder [Renovierungsbasis BASE](cad/nx/k02/20261101T191747_4adeb5/BASE/BASE_21.prt). Der vollständige K02-Journalablauf wurde erneut mit Exit 0 ausgeführt: 689 Parts frisch gespeichert und je Zustand frisch sowie verschoben geöffnet. Der [Mengenbericht der geometrisch gleichen Erstlieferung](renovierung/planung/2026-11-01/K02_STUDIE.md) bleibt erhalten; seine Modelllinks zeigen den früheren Lauf. [Prüfnachweis und Grenzen](docs/entwicklungsstand/K02-native-2026-11-01.md). Grafische NX-Bedien-/Kameraprüfung bleibt offen; keine Bauausführungsfreigabe.

Native NX-Dateien werden unter [`cad/nx/`](cad/nx/README.md) mit Git LFS verwaltet. `tools/nx_project.py` prüft G02 und K02 getrennt; nur vollständige erfolgreiche Läufe schreiben ihre jeweiligen CURRENT-Verweise fort. Für K02 wird eine gültige G02-Basis wiederverwendet. Quell-/Generatoränderungen entwerten den zugehörigen Nachweis. Nach Checkout alle LFS-Dateien laden und die [Suchpfade des gewählten Zustands](cad/nx/README.md) verwenden.

> **Privates Repository verwenden.** Hauspläne, Grundstücksdaten, Bilder, lokale Pfade und teilweise personenbezogene Angaben sind enthalten. Dieses Verzeichnis ist nicht anonymisiert.

## Zuerst lesen

`AGENTS.md` → `docs/PROJEKTSTAND.md` → `docs/ARCHITEKTUR.md` → `CODEX_START.md`.

| Bereich | Verfügbarkeit / Status |
|---|---|
| `projects/g02/` | Vollständiger G02-Lieferbestand: **543 Dateien**, unverändert entpackt. Haus MAIN01-A01, Gelände, ausgewählte Vegetation, Leitungsreferenzen, Quellcode und Tests. |
| `renovierung/k02/` | Eigenständiger Studienerzeuger; 13 PS/72 Registerfelder, 22 native Einzelfeldvarianten, 5 Hinderniskonflikte, 45 ungeklärte/ausgenommene Felder ohne Mengen. Keine kumulative Baufolge oder Netto-Gesamtmenge. |
| `renovierung/k01_unterlagen/` | **8 erhaltene Dateien**: Konzeptbericht, Tabellen, Vorschau, Erläuterung und historische Nachweise. **Kein ausführbarer K01-Code und keine Maßnahmen-STEP-Dateien.** |
| `renovierung/recovered/` | Aus der erhaltenen HTML-Vorschau extrahierter JSON-Studienplan mit Herkunftsnachweis; keine neue CAD- oder Statikprüfung. |
| `sources/video/` | Originaler Außenrundgang, unveränderte Videodaten. |
| `historie/diagnosen/` | Frühere echte Fehlerberichte, nicht die aktuelle Fehlerliste. |
| `local_data/` | Platz für deine lokalen `.prt`-Ausgaben und ergänzende Originalarchive; standardmäßig nicht in Git. |
| `docs/` | Projektwissen, Anforderungen, Grenzen, Test- und Git-Anleitungen. |

**Der Nutzer hat G02 als erfolgreich ausgeführt bestätigt.** Die hier mitgelieferten Programmdateien wurden bei der Übergabe nicht verändert. Der erfolgreiche native NX-Ausgabeordner auf deinem Computer gehört nicht automatisch zu dieser ZIP: alle `.prt`-Komponenten und Laufmanifeste separat sichern.

## Offline prüfen – ohne NX

Python 3.10 oder neuer, keine Installation eines `NXOpen`-Pakets:

```sh
python tools/run_checks.py
python tools/run_checks.py --full
```

Der erste Befehl prüft Integrität, Syntax und Repository-Werkzeuge. Der zweite startet zusätzlich die vorhandenen G02-Tests und Simulationen. Logs entstehen ausschließlich unter `reports/local/`. Optionale unabhängige CAD-Prüfungen: `docs/TESTEN.md`.

**Erst echte NX-Läufe prüfen den NX-/Parasolid-Pfad.** Erfolgreiche Offline-Tests sind keine Bestands-, Höhen-, Baugrund- oder Tragwerksfreigabe.

## Mit Codex anfangen

Den entpackten Ordner als Git-Repository verwenden, nicht die ZIP als einzelne Datei hochladen. Danach Repository oder lokalen Ordner in Codex auswählen und den Auftrag aus `CODEX_START.md` verwenden. Codex braucht den bisherigen Chat nicht; die wesentlichen Entscheidungen und Grenzen sind hier dokumentiert.

Den aktuellen K02-Nachweis und die tatsächlich vorhandenen Zustände zuerst lesen; keine abgeschlossene Kopier-/Erzeugerintegration wegen historischer Starttexte erneut entwickeln. K01 bleibt eine fehlende historische Implementierung. Die vollständige Renovierungsanforderung steht in `docs/ANFORDERUNGEN_RENOVIERUNG.md`; die abgegrenzte K02-Studie erfüllt noch keine vollständige Ausführungsplanung.

## In NX arbeiten

G02 bleibt unter `projects/g02/` mit seinen bisherigen relativen Pfaden erhalten. Zum bloßen Weiterarbeiten die bereits erzeugte `PROJEKT_MASTER_G02_PLANBEZUG_…prt` öffnen. Nicht wegen des Git-Umzugs neu generieren.

Ein ausdrücklich gewünschter Neuaufbau erfolgt in NX über `projects/g02/00_GESAMTPROJEKT_G02_ERZEUGEN.py`; eigene Arbeit vorher sichern und die Originalanleitung lesen. **Keine Journale in Cloud-CI ausführen.** Native Ausgaben werden durch `.gitignore` nicht automatisch versioniert.

## Fachliche Grenzen

Höhenanschluss: vorläufiger Planansatz, **nicht vermessen**. Grundstücksgrenze: Kartenreferenz, kein Grenznachweis. Leitungen: historische Lageprojektionen ohne bestätigte Tiefen. Statik, Gründung und Wasserstand fehlen; zehn bekannte Überschneidungspaare und zwei teilweise blockierte Öffnungen bleiben offen. K01 ist ausschließlich eine historische Konzeptunterlage, keine ausführbare oder freigegebene Sanierungsplanung.

## Weiteres

- `docs/GIT_UND_CODEX.md`: Upload, privates Repository, Codex-Einrichtung.
- `docs/DATEN_UND_RECHTE.md`: Datenstatus, lokale Ergänzungen, Datenschutz.
- `docs/ENTWICKLUNGSPLAN.md`: abgegrenzte nächste Arbeitspakete.
- `reports/handoff/`: tatsächlich bei dieser Übergabe ausgeführte Prüfungen.
- `provenance/IMPORT_MANIFEST.json`: Herkunft und SHA-256 aller importierten G02-/K01-Dateien.

Der ursprüngliche Übergabestand wurde am 31.10.2026 in `juanito1337/HausPlanBauprojekt` hochgeladen. Neue lokale Commits sind erst nach einem tatsächlichen Push auf GitHub verfügbar. Lizenzdateien oder Zugangsdaten gehören nicht ins Repository; echte NX-Läufe benötigen die lokal verfügbare NX-Lizenz.
