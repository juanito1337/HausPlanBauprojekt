# Prüfung der Umfangsergänzung E01

Datum 01.11.2026. Reine Planungsdokumentation, keine Änderung an G02, V01-Katalog/PDF oder nativen NX-Dateien.

- `Tiefbau.zip`: CRC-Prüfung mit `zipfile.testzip()` ohne Fehler; 9 PDFs, 15 Seiten. Sichere lokale PDF-Extraktion unter `reports/local/tiefbau_20261101/`, keine Dokumentbefehle ausgeführt.
- SHA-256/Dateigröße aller 9 PDFs mit vorhandenen G02-Quellen verglichen: alle bytegleich; keine neue Quellkopie in G02 geschrieben. Zuordnung in `TIEFBAU_EINGANG.json`.
- Gas, Telefon, Strom (beide Seiten), Breitband und Legende mit Poppler gerendert und visuell gelesen. Anschreiben, Nutzungsbedingungen und relevante Abschnitte des Leitungsschutz-Merkblatts textlich geprüft. Allgemeine Überdeckungen nicht als Haus-Leitungstiefen eingetragen.
- Ergänzung `UMFANG_E01.json` wieder dem unveränderten V01-Katalog zugeordnet: SHA-256 `61c05993677a7b01cdd1809251a68b30305752a159d6e88cf3ca05806ac09ddf`. Vorläufige Ausnahmegrenzen unbekannt; PS02 nicht vollständig ausgeschlossen, PS07 nicht automatisch ausgeschlossen; Ausführungsfreigabe false.
- `python tools/nx_project.py check`: Rückgabecode **0**, PASS. Gespeicherter echter NX-Nachweis und native Dateien passen weiterhin zu aktuellen Quellen. **Kein neuer NX-Lauf und keine neuen Renovierungs-.prt.**
- `git diff --check`: Rückgabecode **0** vor Commit.

Ausgeführt mit `C:/Users/1337/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Kein neuer Produktcode; keine Wiederholung der vollständigen historischen G02-Suite. Der bekannte Windows-Pfadtest bleibt unverändert offen. Keine Fachfreigabe, Bemessung oder Bestandsvermessung aus diesen Prüfungen ableiten.
