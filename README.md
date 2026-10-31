# HausPlan & Bauprojekt · NX / Codex

**Git-fähiger Entwicklungsstand vom 31.10.2026.** Dieses Repository enthält den tatsächlich verfügbaren G02-Quellcode mit seinen Plan-/Geometriequellen, die erhaltenen K01-Unterlagen, den Außenrundgang und eine eigenständige Übergabe an Codex.

> **Privates Repository verwenden.** Hauspläne, Grundstücksdaten, Bilder, lokale Pfade und teilweise personenbezogene Angaben sind enthalten. Dieses Verzeichnis ist nicht anonymisiert.

## Zuerst lesen

`AGENTS.md` → `docs/PROJEKTSTAND.md` → `docs/ARCHITEKTUR.md` → `CODEX_START.md`.

| Bereich | Verfügbarkeit / Status |
|---|---|
| `projects/g02/` | Vollständiger G02-Lieferbestand: **543 Dateien**, unverändert entpackt. Haus MAIN01-A01, Gelände, ausgewählte Vegetation, Leitungsreferenzen, Quellcode und Tests. |
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

Die erste Aufgabe ist **Bestand aufnehmen, Tests nachvollziehen und K01 als fehlende Implementierung behandeln**, nicht G02 neu schreiben. Die vollständige Renovierungsanforderung steht in `docs/ANFORDERUNGEN_RENOVIERUNG.md`.

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

Kein Repository wurde online angelegt oder veröffentlicht. Keine NX-Lizenzdateien oder Zugangsdaten sind für die Werkzeuge erforderlich.
