# Testen ohne erfundene Erfolgsnachweise

## Integrierter M02 Nachweis ab 05.11.2026

Für den Gesamtstand `python tools/nx_anbau.py build --accept-model-assumptions` und anschließend `python tools/nx_anbau.py check` ausführen. Der Build erzeugt neue Parts und verlangt vollständige native Prüfungen des übernommenen M01-Baums, aller Anbaufelder, gespeicherten Zustände und separaten Einstiege. Ein explizites Paket bereits geprüfter nativer Eingaben kann über `--reuse-assets` verwendet werden. Die abschließenden Gesamtprüfungen bleiben dabei verpflichtend.

`tools/run_checks.py` führt Repository-, K02-, M01- und Anbautests sowie die nativen Aktualitätschecks für G02/K02 und M02 aus. Mit `--nx` werden G02/K02 und anschließend M02 nativ aufgebaut. Die M01-Basis muss dem aktuellen M01-Layoutgenerator exakt entsprechen. Bei einer Abweichung ist zuerst eine passende M01-Basis zu erzeugen. Ein reiner Aktualitätscheck führt keinen neuen NX-Lauf aus. Die grafische Menü-/Bildschirmabnahme bleibt ein eigener Prüfpunkt.

`tools/nx_master.py` behält seinen eigenständigen M01-Geltungsbereich. Der aktuelle gemeinsame Gesamtstand wird über `cad/nx/m02/CURRENT.json` bestimmt.

## Verbindlicher nativer Projektcheck ab 31.10.2026

Auf Nutzerwunsch werden neue native Ausgaben unter `cad/nx/` mit Git LFS verwaltet. Vor einem Abschluss `python tools/nx_project.py check` ausführen: Der gespeicherte echte NX-Nachweis muss zu aktuellen Quell-/Generatorhashes und allen nativen Dateien passen. Nach Erzeuger-/Geometrieänderungen ist ein neuer echter Lauf erforderlich:

```sh
python tools/nx_project.py build --nx-root C:/Siemens/NX2406 --accept-model-assumptions
python tools/nx_project.py check
```

Der Build enthält neue Erzeugung, Wiederöffnen in einem frischen NX-Prozess und Laden einer verschobenen Kopie. Ein separates Prüfjournal verweigert ungeladene Teile, fremde Komponentenpfade, falsche Einheiten und geänderte Dateien. Details: `cad/nx/README.md`. `python tools/run_checks.py` prüft den gespeicherten nativen Nachweis jetzt standardmäßig mit und scheitert bei fehlendem oder veraltetem Nachweis. `python tools/run_checks.py --full --nx --accept-model-assumptions` kombiniert alle Offline-Tests mit einem neuen echten NX-Lauf. Die gewöhnliche Cloud-CI lädt Git-LFS-Dateien, besitzt aber keine NX-Lizenz; dort kann nur der gespeicherte Nachweis geprüft werden, nicht ein neuer NX-Lauf behauptet werden.

Lokal ist Python 3.12.14 auch über die vorhandene Codex-Laufzeit verfügbar, obwohl `python` im PATH auf den Windows-Store-Alias zeigte. Für die folgenden Befehle einen tatsächlich verfügbaren Python-Interpreter verwenden; NX-Python bleibt unverändert.

## 1. Schneller Repository-Check

```sh
python tools/run_checks.py
```

Benötigt Python >=3.10 und ausgecheckte Git-LFS-Nativdateien. Prüft G02/K01-Importhashes, Python-3.10-Syntax, die Repository-Werkzeugtests und die Aktualität des gespeicherten nativen Nachweises. Kein NX-Import, keine neue Geometrie. Eine absichtlich geänderte Datei im importierten G02-Stand führt zu einer sichtbaren Abweichung; die historischen Importhashes werden nicht automatisch aktualisiert.

K02 ist ebenfalls enthalten: derzeit 45 reine Kern-/Runner-Tests für Geometrie, Terrain, Materialäquivalente, Konflikt-/Nullstatus, Provenienz und das vollständige native Manifestgate. Der Mengenvalidator verlangt nichtleere positive endliche Komponenten, passende Körperanzahlen und kohärente Gesamtvolumen; BUILD sowie beide VERIFY-Phasen werden geprüft. Diese Offline-Tests verwenden ausdrücklich Testfixtures und behaupten keine native Erzeugung. Fokussierter Aufruf: `python -m unittest discover -s renovierung/tests -p "test_k02*.py" -v`.

## 2. Vorhandener vollständiger Python-/Simulationsstand

```sh
python tools/run_checks.py --full
```

Startet zusätzlich `projects/g02/werkzeuge/PRUEFE_G02_OFFLINE.py` und dessen vorhandene Gruppen. Der bei dieser Übergabe ausgeführte Altbestand zählt 680 Tests; diese Zahl ist eine Beobachtung dieses Stands, kein auf ewig festes Erfolgskriterium. Testgruppen in getrennten Prozessen laufen lassen. Alle neuen Ausgaben unter `reports/local/` sind ignoriert.

Bekannte Windows-Grenze: `test_r09.CoreTests.test_path_traversal_rejected`, Teilfall `/tmp/x`, scheitert im unveränderten historischen G02. Der volle Lauf vom 03.11.2026 hat diesen einen Fehler erneut bestätigt. Das ist getrennt vom schnellen Check und echten nativen Gate zu lesen, keine Behauptung einer vollständig grünen historischen Suite. Aktuelle Befehle, Exitcodes und Nachweise: [M01-Projektprüfung](entwicklungsstand/M01-pruefung-2026-11-03.md), zuvor [K02-Entwicklungsnachweis](entwicklungsstand/K02-native-2026-11-01.md).

## 3. Optionale unabhängige CAD-Prüfung

Separaten Python-3.12-Environment verwenden, **nicht** die eingebettete NX-Python-Installation verändern. `requirements-cad-reference.txt` nennt die in der Übergabeumgebung vorhandenen direkten Paketversionen; es ist kein vollständig aufgelöster, plattformübergreifend getesteter Lockfile.

```sh
python -m venv .venv-cad
# Umgebung für dein Betriebssystem aktivieren.
python -m pip install -r requirements-cad-reference.txt
python tools/run_checks.py --full --cad
```

Die vorhandenen Prüfungen verwenden Open CASCADE/cadquery. Sie prüfen Quellkörper und Simulationen, **nicht** den realen NX-/Parasolid-Importer. Die Installation dieser Referenzliste wurde hier nicht in einer frischen Maschine getestet. Installationsprobleme nicht durch Änderungen an den NX-Libraries umgehen.

## 4. Echte NX-Prüfungen

NX 2406 mit der beim Nutzer vorhandenen Lizenz. Nur bewusst gestartete Journale ausführen. Vorher eigene Arbeit sichern; kein automatisches Schließen/Verwerfen fremder Parts. Neue Funktionen zuerst an einer kleinen Testkopie erproben. Für neue Renovierungskopien mindestens: Quelldateihashes unverändert; keine Original-/Fremdreferenzen; gleicher Maßstab und Transformationen; korrekte Unterdrückungen/Materialien; Speichern und erneutes Öffnen; dann erst Bauzustandsgeometrie.

Protokoll muss unterscheiden: tatsächlich ausgeführt / nur simuliert / nicht getestet. Ohne geotechnische und statische Unterlagen keine Standsicherheit behaupten.

K02 benötigt BASE plus alle 22 aktuellen nativen Kandidaten. Jeder Zustand wird mit unabhängigen Quellklonen gebaut und in zwei frischen eigenen NX-Prozessen geprüft: AsSaved am Lieferort, SearchDirectories nach vollständigem Verschieben. Alle drei echten Volumennachweise müssen einschließlich mehrteiliger Rollen zusammenpassen. Quellpart-Hashes werden vor/nach verglichen; eine Übertragungstoleranz ist keine Gelände- oder Vermessungsgenauigkeit. Die grafische Prüfung von Schnittsichtbarkeit, Böschung, Platzierung und Register bleibt ein eigener Nachweis; Batch-Messungen, gespeicherte Blankflags und aus NX exportierte Diagnosegeometrie dürfen nicht als NX-Bildschirmaufnahme ausgegeben werden.

## 5. GitHub Actions / Codex

`.github/workflows/offline.yml` führt den schnellen Test bei Push/PR aus. Der vollständige G02-Test kann über den manuellen Workflow-Start zusätzlich gewählt werden. Auf Cloud-Runners wird kein NX installiert. `scripts/setup_codex.sh` benötigt keine Zugangsdaten und lädt keine Pakete aus dem Netz; es prüft den vorhandenen Python-Stand.

## Paketregister bei zukünftigen Änderungen

`provenance/IMPORT_MANIFEST.json` ist ein historischer Vergleich. `projects/g02/PAKETDATEIEN_SHA256.json` und Unterregister sind Laufzeitschutz. Bei einer beauftragten Änderung bewusst eine neue Revision und überprüfbares Änderungsregister anlegen. Nicht einfach sämtliche Hashes neu schreiben, um unbekannte Änderungen zu akzeptieren. Die Renovierungsentwicklung kann außerhalb der G02-Basis erfolgen, ohne diese Register zu ändern.
