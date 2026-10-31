# Versionierte native NX-Dateien

Dieser Bereich enthält ausschließlich tatsächlich erzeugte NX-Dateien und zugehörige Prüfnachweise. `.prt` werden mit Git LFS gespeichert. Arbeits-/Fehlerprotokolle und temporäre Quellkopien liegen unter `reports/local/nx/` und bleiben lokal.

`CURRENT.json` benennt den zuletzt vollständig geprüften Lauf und seinen Master. `LAST_ATTEMPT.json` zeigt den jüngsten Buildversuch; FAIL oder RUNNING darf nicht als Erfolg ausgegeben werden. Pro Lauf enthalten `BUILD.json` und `VERIFY.json` die Quellzuordnung, Part-Hashes, NX-Version und Ergebnisse des frischen Wiederöffnens sowie des Tests an einer verschobenen Kopie.

## Nach einem Checkout

```sh
git lfs install --local
git lfs pull
python tools/nx_project.py check
```

NX lädt die Baugruppe über Suchverzeichnisse: alle im Part-Manifest vorkommenden Unterordner des gewählten Laufs als Komponentensuchpfade eintragen, vollständig laden und den Master aus `CURRENT.json` öffnen. Eine `.prt`-Masterdatei allein ist keine vollständige Baugruppe. Der automatisierte Prüflauf verwendet genau dieses Ladeverfahren und verweigert Komponenten außerhalb des gewählten Laufordners. Absolute Speicherpfade in NX-Dateien werden nicht als portable Referenzgarantie ausgegeben.

## Aktuellen Quellstand neu erzeugen

```sh
python tools/nx_project.py build --nx-root C:/Siemens/NX2406 --accept-model-assumptions
```

Der Runner startet `NXBIN/run_journal.exe` in separaten Prozessen. Er verwendet die vorhandene G02-Engine einschließlich ihrer Geometrie-/Strukturprüfungen und erzeugt neue Dateinamen. Die beiden Bestätigungen für das bestehende Studienmodell werden über den ausdrücklichen Schalter erteilt. Keine Benutzer-Sitzung wird gespeichert oder geschlossen. Haus-/Umgebungskonflikte und fachliche Einschränkungen bleiben bestehen.

`check` prüft gespeicherte Nachweise und Dateien, startet aber keinen neuen NX-Lauf. Bei Änderungen am Erzeuger oder an Modelleingaben wird der alte Nachweis ungültig. Neue Renovierungserzeuger müssen später ausdrücklich in Build und Fingerprint integriert werden.

Die Dateien gehören zur konzeptionellen Modellierung; bestandene NX-Prüfungen sind keine Bau-, Bestands- oder Tragwerksfreigabe.
