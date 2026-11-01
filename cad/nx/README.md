# Versionierte native NX-Dateien

**Aktueller K02-Revisionsstand:** [K02 / Quellrevision 31dba74 mit allen 23 Masterlinks](REVISION_K02_31dba74.md). Erneuter vollständiger K02-Journalablauf mit Exit 0; 689 Dateien im Lauf `k02/20261101T191747_4adeb5/` gespeichert. G02 wurde als unveränderte gültige Basis wiederverwendet.

Dieser Bereich enthält ausschließlich tatsächlich erzeugte NX-Dateien und zugehörige Prüfnachweise. `.prt` werden mit Git LFS gespeichert. Arbeits-/Fehlerprotokolle und temporäre Quellkopien liegen unter `reports/local/nx/` und bleiben lokal.

`CURRENT.json` benennt den zuletzt vollständig geprüften Lauf und seinen Master. `LAST_ATTEMPT.json` zeigt den jüngsten Buildversuch; FAIL oder RUNNING darf nicht als Erfolg ausgegeben werden. Pro Lauf enthalten `BUILD.json` und `VERIFY.json` die Quellzuordnung, Part-Hashes, NX-Version und Ergebnisse des frischen Wiederöffnens sowie des Tests an einer verschobenen Kopie.

K02 hat darunter einen eigenen Bereich `k02/` mit eigenem `CURRENT.json`, `LAST_ATTEMPT.json` und vollständigen `BUILD.json`/`VERIFY.json`. Der G02-Einstieg bleibt die unveränderte Bestandsdarstellung. K02-CURRENT nennt die Renovierungsbasis `BASE` und jede separat gespeicherte Einzelfeldvariante; kein Feldmaster ist eine fortgeschriebene Ausführungsstufe des vorherigen Feldes. Der [K02-Mengenbericht](../../renovierung/planung/2026-11-01/K02_STUDIE.md) erklärt Mengen, Konflikte und ungeklärte Bereiche.

## Nach einem Checkout

```sh
git lfs install --local
git lfs pull
python tools/nx_project.py check
```

NX lädt die Baugruppe über Suchverzeichnisse: alle im Part-Manifest vorkommenden Unterordner des gewählten Laufs als Komponentensuchpfade eintragen, vollständig laden und den Master aus `CURRENT.json` öffnen. Eine `.prt`-Masterdatei allein ist keine vollständige Baugruppe. Der automatisierte Prüflauf verwendet genau dieses Ladeverfahren und verweigert Komponenten außerhalb des gewählten Laufordners. Absolute Speicherpfade in NX-Dateien werden nicht als portable Referenzgarantie ausgegeben.

Für K02 zuerst `k02/CURRENT.json` lesen: `directory` liegt relativ zu `cad/nx/k02/`, jeder Eintrag in `masters` wiederum relativ zu diesem Laufordner. Für einen Zustand ausschließlich dessen eigenen Unterordner als Suchverzeichnis verwenden und den dort genannten Master vollständig öffnen. Alle Komponenten haben zustandsspezifische Dateinamen. Keine Teile aus BASE, anderen Feldern oder dem G02-Original hinzufügen. Der automatisierte Test prüft neue K02-Dateien am Erstellort zusätzlich mit AsSaved; nach Checkout/Umzug ist SearchDirectories mit dem eigenen Zustandsordner maßgeblich.

Im Feldzustand ist der lokale Schnittboden auf Layer 101 sichtbar, der separate Aushub auf 102 ausgeblendet, das Hauptlager (locker 1.05) auf 103 sichtbar und das alternative Reservelager (1.25) auf 104 ausgeblendet. Haupt- und Reservelager sind Alternativen am gleichen Platz; beim Umschalten jeweils das andere Lager ausblenden. Das kopierte offene Originalgelände ist geblankt, damit es den echten Studienausschnitt nicht verdeckt. Registerlinien und Feldhinweise liegen auf einer ausdrücklich beschrifteten Referenzebene Z=0; sie zeigen keine bekannten Leitungstiefen. Gespeicherte Körper-/Layer-/Blankwerte ersetzen keine grafische Sichtprüfung.

## Aktuellen Quellstand neu erzeugen

```sh
python tools/nx_project.py build --nx-root C:/Siemens/NX2406 --accept-model-assumptions
```

Der Runner startet `NXBIN/run_journal.exe` in separaten Prozessen. Er verwendet die vorhandene G02-Engine einschließlich ihrer Geometrie-/Strukturprüfungen und erzeugt neue Dateinamen. Die beiden Bestätigungen für das bestehende Studienmodell werden über den ausdrücklichen Schalter erteilt. Keine Benutzer-Sitzung wird gespeichert oder geschlossen. Haus-/Umgebungskonflikte und fachliche Einschränkungen bleiben bestehen.

`check` prüft gespeicherte Nachweise und Dateien beider Bereiche, startet aber keinen neuen NX-Lauf. Bei Änderungen am Erzeuger oder an Modelleingaben wird der alte Nachweis ungültig. K02 ist in Build und Fingerprint integriert; ein unvollständiger Pilot besteht das Gesamtgate nicht. Der Build arbeitet seriell: gültige G02-Basis, frischer Gesamtplan, BASE und jedes modellierbare Feld jeweils Erzeugung/frisches Öffnen/verschobenes Öffnen. Rohnetze und große STEP-Zwischendateien werden nicht versioniert.

Die Dateien gehören zur konzeptionellen Modellierung; bestandene NX-Prüfungen sind keine Bau-, Bestands- oder Tragwerksfreigabe.
