# Aus HTML zurückgewonnene Referenzdaten

`RENOVIERUNGSPLAN_AUS_VORSCHAU.json` wurde aus dem literal eingebetteten `const P=...;` der unveränderten K01-HTML-Datei gelesen. **Kein JavaScript wurde ausgeführt**, keine Geometrie erzeugt und keine CAD-Volumina neu berechnet.

Die JSON enthält 62 Zustandsdatensätze, Konturen, Vergleichsgeometrien, Annahmen, historische Mengen und CAD-Dateiverweise. Sie erleichtert Codex die Weiterentwicklung. Die `assets`-Einträge sind nur Verweise; keine einzige der dort genannten STEP-Dateien ist im erhaltenen K01-Dokumentenpaket vorhanden. Das Verzeichnis `FEHLENDE_CAD_DATEIEN.json` listet die tatsächlich referenzierten Namen auf.

Reproduktion in eine neue Datei: `python tools/extract_k01_reference.py --output reports/local/plan_copy.json`. Der Befehl überschreibt keine bestehende Datei. Die vorhandene Extraktion und ihre Quelle sind per SHA-256 in `provenance/K01_JSON_EXTRACTION.json` dokumentiert.

Alle historischen Angaben behalten ihre ursprüngliche Bedeutung als Konzept. Ein Feld wie `CAD_files` ist ein damaliger Zähler, kein heutiger Verfügbarkeitsnachweis. Fehlende Geometrie muss später bewusst wiederhergestellt und erneut geprüft werden.
