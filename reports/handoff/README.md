# Bei der Git-Übergabe tatsächlich geprüft

Die Dateien `g02_offline/` stammen aus einem neuen Lauf des unveränderten G02-Prüfers in diesem Repository. 680 Python-/Simulationstests bestanden. Kein eigener NX-/Parasolid-Lauf, keine neue reale CAD-Kernelprüfung bei dieser Übergabe.

`REPO_TESTS_GREEN.txt`: 28 aktuelle Tests für Repository-Werkzeuge, sichere Pfade, ZIP-Ausgabe und JSON-Extraktion. `REPO_TESTS_RED.txt` und `EXTRACT_TESTS_RED.txt` sind absichtliche Vor-Implementierungsbefunde; keine offenen aktuellen Fehler.

`GIT_CHECKOUT_PRUEFUNG.json`: Testweises Git-Staging und erneuter Checkout mit `core.autocrlf=true`; die 543 G02-Dateien und 8 historischen K01-Dateien behalten alle Originalhashes. Die initiale Dateizahl dieses Zwischenschritts ist nicht zwingend die spätere finale Archivdateizahl.

`REPOSITORY_PRUEFUNG.json` / `UEBERGABEPRUEFUNG.json`: aktuelle Integritäts-, Syntax- und Eingangsarchivprüfungen. `ORIGINALQUELLEN_ARCHIVE.json`: echte zusätzliche ZIP-Dateien mit CRC und Payload-Hash-Prüfung.

Diese Tests verleihen keine Ausführungs-/Baugrund-/Tragwerksfreigabe und stellen die fehlende K01-Implementierung nicht wieder her. Das abschließende ZIP-Prüfprotokoll wird als separate Datei neben dem Liefer-ZIP ausgegeben, damit das geprüfte Archiv danach nicht mehr verändert werden muss.
