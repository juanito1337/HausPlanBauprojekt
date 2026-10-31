# Git-Upload und Codex-Start

## 1. Lokalen Ordner vorbereiten

ZIP vollständig entpacken, z.B. nach `C:\Projekte\HausPlanBauprojekt`. Die Dateien `.gitignore`, `.gitattributes` und `.github/` gehören dazu; Windows kann solche Dateien versteckt anzeigen. Nicht den 100+-MB-ZIP-Download selbst ins Git-Repository hochladen, sondern die entpackten Dateien versionieren.

Der Ordner enthält keine vorgetäuschte alte Git-Historie und keine vorkonfigurierte Remote-Adresse. Der erste Commit wird unter deiner eigenen Git-Identität erstellt.

## 2. Prüfen und initialisieren

Im Terminal im Repository-Hauptordner:

```sh
python tools/run_checks.py
git init -b main
git add .
git status --short
git diff --cached --stat
git commit -m "Import G02 baseline and Codex handoff"
git tag baseline-g02-import
```

Falls Git noch keinen Namen/E-Mail kennt, deine eigene Identität konfigurieren. Keine fremden Zugangsdaten oder eine erfundene Identität übernehmen.

## 3. Privates Remote verbinden

Bei deinem Git-Anbieter ein **leeres privates Repository** anlegen. Nicht bereits ein anderes README als konkurrierenden ersten Commit erzeugen. Dann die vom Anbieter angegebene Clone-Adresse verwenden:

```sh
git remote add origin <DEINE-REPOSITORY-CLONE-ADRESSE>
git push -u origin main
git push origin baseline-g02-import
```

Die Platzhalter-Adresse bewusst ersetzen. Keine Tokens in Befehlen, Dateien oder Remote-URLs fest speichern. Alternativ GitHub Desktop: bestehendes lokales Repository hinzufügen und als privates Repository veröffentlichen; vor dem Publish die Dateiliste kontrollieren.

## 4. Codex

Lokal den Repository-Ordner in Codex öffnen. Für Cloud-Arbeit das private Repository mit der gewünschten Codex-Umgebung verbinden. Die verfügbaren Einstellungen können sich ändern; die aktuellen offiziellen Quellen stehen in `docs/TOOL_QUELLEN.md`.

Erster Auftrag: `CODEX_START.md`. Die repositoryweite `AGENTS.md` enthält Regeln für Tests, Quellschutz, Einheiten, Annahmen und die fehlende K01-Implementierung. Codex kann den Python-Code bearbeiten und Offline-Tests ausführen. Ein echter NX-Lauf benötigt weiterhin deine lizenzierte NX-Umgebung; das Repository verschafft keine NX-Lizenz.

Für die Kellererweiterung einen eigenen Branch verwenden:

```sh
git switch -c feature/keller-renovierung
```

## 5. Große Dateien

**Aktuelle Ausnahme auf Nutzerauftrag vom 31.10.2026:** Neue native Lieferungen unter `cad/nx/` werden jetzt bewusst mit Git LFS versioniert (`cad/nx/**/*.prt`). Nach einem Clone `git lfs install --local` und `git lfs pull` ausführen. Vor einem Push mit `git lfs ls-files` und `git lfs fsck` prüfen. Die initialen G02-Quellen bleiben unverändert; keine Migration oder Umschreibung alter Commits. Arbeitskopien unter `local_data/` bleiben ignoriert. Aktuelle Bedienung und NX-Ladeverfahren: `cad/nx/README.md`.

Die initial mitgelieferten versionierten Einzeldateien sind kleiner als 100 MiB; daher ist für diesen Stand kein Git LFS zwingend erforderlich. Das Gesamt-ZIP ist viel größer als einzelne Dateien. Die entpackten Dateien per Git push übertragen; den ZIP nicht als einzelne Repository-Datei ablegen.

Neue große `.prt`, Videos oder Roharchive zunächst außerhalb von Git unter `local_data/` lassen. Werden sie ausdrücklich zur Versionierung ausgewählt, vorher Git LFS und dessen Speicher-/Zugriffsregeln einrichten. Keine nachträgliche History-Umschreibung ohne bewusstes Vorgehen. `.gitignore` ist kein Datenschutzfilter für bereits eingecheckte Dateien.

## 6. Vorhandene native Modelle

Die auf deinem Rechner erzeugten `.prt` sind nicht Bestandteil dieses Downloads. Den gesamten erfolgreichen NX-Ausgabeordner inklusive aller Komponenten und Laufmanifeste sichern. Eine bloße Masterdatei ist keine vollständige Baugruppe. Ein Dateikopieren auf einen neuen Pfad passt gespeicherte NX-Komponentenreferenzen nicht automatisch an; die Verweise in NX überprüfen beziehungsweise eine bewusste Baugruppenkopie anlegen.

## 7. Neue ZIP-Ausgabe aus Git

Nach geprüftem Commit und sauberem Arbeitsbaum:

```sh
python tools/package_repo.py --output ../HausPlan_Release.zip
```

Nur in Git erfasste Dateien werden exportiert. `.git`, `local_data/`, lokale Tests und native Ausgaben werden nicht automatisch Teil des Releases. Der Befehl überschreibt kein vorhandenes Zielarchiv.
