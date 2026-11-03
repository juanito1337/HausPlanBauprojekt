# Zentrale NX-Hauptbaugruppe M01 – Entwurf und Umsetzungsplan

> Ausführung mit Superpowers und unabhängiger Prüfung. Nutzerauftrag vom 03.11.2026: vorgeschlagene Hauptstruktur prüfen, Fehler korrigieren und tatsächlich in NX testen.

## Ziel und Entscheidungen

Ein Einstieg `HAUSPROJEKT_MASTER_M01.prt` enthält Haus, Gelände, alle Planungssektionen und sämtliche Feldregistereinträge. Bestandshaus und Gelände kommen nur einmal vor. Die 22 vorhandenen Geometriestudien werden als separat schaltbare Feldbaugruppen aufgenommen. Die früheren unabhängigen K02-Lieferungen bleiben unverändert erhalten.

Die Alternative, alle 23 Vollkopien unter einen neuen Master zu hängen, wird verworfen: sie vervielfacht Haus/Gelände und löst die Bedienprobleme nicht. Die neue Lieferung kopiert nur benötigte Quellteile in ihren eigenen Ordner, ordnet sie neu und erhält ihren eigenen Quellfingerprint und echte NX-Nachweise. Kein Neuaufbau der unveränderten Hausgeometrie.

Haus: Keller (Hauptbau/Anbau), Erdgeschoss (Hauptbau/Anbau), Dachgeschoss, Garage, Dach (inkl. Dachfenster/Solar/Flachdachreferenz), Außenbauteile, Steuerungsreferenz. Neue Zwischenbaugruppen besitzen Identitätstransformationen. Die Umgebung erhält genau einmal den dokumentierten Höhenversatz. Leitungsreferenzen bleiben ausdrücklich ohne bekannte Tiefe.

50 Räume werden als Raumregister geführt, keine erfundenen Raumkörper oder automatische Wandzuordnung. Historisch belegte Wohnung A/B werden als Quellenzuordnung beschriftet; übrige Planbereiche bleiben Zuordnung offen. Die geschossübergreifende Wohnung A erhält denselben Registerbezug an KG und EG. Gemeinsame Wände/Decken verbleiben einmal in den Geschossteilen. Ein Registerraum enthält ausschließlich Metadaten; sein Ausblenden verändert keine Gebäudegeometrie. Diese Festlegung ersetzt keine bestätigte heutige Wohnungsaufteilung.

Alle 13 Sektionen/72 Felder bleiben sichtbar im Baugruppenbaum. Ungeklärte/gesperrte Felder erhalten Metadaten statt erfundener Eingriffe. Ein nativer Feldzustand enthält Rollen Schnittboden/Böschung, Aushub, Hauptlager und alternatives Reservelager. Rollen werden über Referenzsets auf der eigenen Kopie des Studienparts getrennt. Keine Studiengeometrie mehrfach physisch erzeugen.

Gespeicherter Startzustand: Haus und Bestandsgelände sichtbar, Feldstudien und Raumregister ausgeblendet. Ein Auswahljournal aktiviert genau ein Feld und blendet das Bestandsgelände aus; BASE stellt den Bestand wieder her. Das ist eine unabhängige Feldstudie, keine kumulative Baufolge. Mehrere manuell eingeblendete Felder sind nur Vergleichsdarstellungen, keine gemeinsame Mengenbilanz.

## Grenzen und Schutz

- Alle bisherigen Quellmodelle, 543 G02-Dateien und historischen Prüfnachweise bleiben bytegleich.
- Neue Module ausschließlich `renovierung/m01/`, neue CAD-Lieferung `cad/nx/m01/<Lauf>/`.
- Additiver Prüf-/Erzeugereinstieg `tools/nx_master.py`; bestehender `tools/nx_project.py` und dessen Fingerprints unverändert. `tools/run_checks.py` prüft zusätzlich M01. Diese Aufteilung vermeidet sachlich unnötige 718 Neubauten des unveränderten Bestands.
- Millimeter; Umfeld Z = -31362.49870845903 mm einmal. Keine neue Statik, Mengenannahme oder Baufreigabe.
- Keine fremden NX-Fenster bedienen/speichern/schließen. Eigene frische `run_journal.exe`-Prozesse, eigener Arbeitsordner und eigene Anfragen. Laufbelegung prüfen; keine fremden Locks löschen oder Prozesse beenden.
- Visuelle Bildschirmabnahme wird nur behauptet, wenn tatsächlich erfolgt. Native Struktur-/Sichtbarkeitsprüfung getrennt berichten.

## Aufgaben und überprüfbare Schnittstellen

### 1. Quellenanalyse, Layout und Negativtests

Dateien: `renovierung/m01/layout.py`, `renovierung/tests/test_m01_layout.py`.

`create_layout(root: Path) -> dict` liest aktuelle gültige G02/K02-Nachweise und Hausregister. Ausgabe: `schema`, `master`, `nodes`, `sources`, `fields`, `rooms`, `construction_release=false`. Jeder Knoten hat eindeutige `id`, `parent` (Root null), `file` relativ zum Lieferordner, `name`, `kind` (`assembly`, `source`, `role`, `room`, `field`), `translation_mm`, `rotation`, `blank`, `reference_set`.

`sources`: pro kopiertem Quellpart `source` relativ Repo, `file` relativ Lieferung, `sha256`, `bytes`; Quelldateien nur bestätigte Blattparts oder STUDY-Parts. `role`-Knoten referenzieren denselben Feldpart mit Referenzset gemäß Rolle (`cut_soil`, `excavation`, `pile_main`, `pile_reserve`). `fields` enthalten `id`, `node_id`, `native`, `status`, `measurements` und Quellenmetadaten. `rooms` erhalten alle Originalregisterdaten, ohne unbestätigte Geometrie abzuleiten.

- [x] Tests zuerst: fehlende/duplizierte Quellen, alle 72 Felder/22 native/50 Räume, keine doppelten Haus-/Geländevorkommen, Höhenversatz nur einmal, sichere Dateinamen und eindeutige IDs.
- [x] Layout implementieren; Negativtests und reale Quellenprüfung ausführen.
- [x] Unabhängige Prüfung der Zuordnungen.

### 2. Native Erzeugung und prüfbare Darstellung

Dateien: `renovierung/m01/nx_journal.py`, `renovierung/m01/display.py`, `renovierung/m01/select_state.py`.

Vorab minimaler echter NX-Test der neuen Referenzset-/Schaltfunktionen im lokalen Testordner. Produktivjournal liest `M01_NX_REQUEST`, unterstützt `build` und `verify`. Builder kopiert Quellen in frischen Lieferordner, erzeugt neue Zwischenbaugruppen und Registerteile, fügt Rollenreferenzsets hinzu. Verifier öffnet vollständig, prüft Pfade/Einheiten/Abhängigkeiten/Hashwerte, erwartete Hierarchie, Komponentennamen, Transformationen, Referenzset-Mitglieder und gespeicherte Sichtbarkeit. Messungen pro Feld und Rolle statt globaler Rollennamen. Jede Feldumschaltung sowie Haus-/Geschoss-/Raumgruppen werden im eigenen Prozess getestet; Ausgangszustand wird wiederhergestellt. Kein Verifier speichert.

- [x] Echten NX-Pilot erfolgreich durchführen.
- [x] Native Erstellung/erneutes Öffnen implementieren; Fehler erzwingen und sichtbar scheitern lassen.
- [x] Unabhängige Prüfung des nativen Codes.

### 3. Runner, Integration und Auslieferung

Dateien: `renovierung/m01/runner.py`, `tools/nx_master.py`, `renovierung/tests/test_m01_runner.py`, `tools/run_checks.py`, Dokumentation und CAD-Metadaten.

`source_fingerprint()` umfasst sämtliche neuen Generator-/Displaymodule, neue CLI, Layoutquellen, bestätigte native Quellen und deren Nachweise. `check_master()` prüft CURRENT/LAST_ATTEMPT, vollständige Manifest-/Sichtbarkeits-/Messnachweise und aktuellen Fingerprint. Nur Build plus frisches und verschobenes Wiederöffnen erlauben PASS/CURRENT. Nicht erfolgreiche Läufe bleiben sichtbar FAIL. Maschinenweiter eigener Build-Lock mit exklusiver Anlage; bestehender Lock wird nie übernommen. Vor jedem Journal wird auf fremde laufende Journale bis zu 30 Minuten gewartet, danach Abbruch ohne Prozessübernahme.

- [x] Negative Evidenztests zuerst (fehlender Part, falscher Fingerprint, fehlende Felder, falsche Darstellung/Messung).
- [x] Runner/CLI implementieren und in schnelle Checks integrieren.
- [x] Vollständiges natives M01-Journal, frisches Öffnen und verschobenes Öffnen tatsächlich ausführen.
- [x] Regressionsprüfung bestehender Quellen und K02/G02-Nachweise.
- [x] Abschließende unabhängige Prüfung, konkrete Fehler beheben, Nachweis aktualisieren.
- [x] Aktuelle Hauptdatei dokumentieren, LFS-Dateien/Belege prüfen und versionierbare Lieferung vorbereiten.

Lieferlauf `20261103T005043Z_07d05f`; [Abschlussnachweis](../entwicklungsstand/M01-pruefung-2026-11-03.md). Commit und autorisierter Push erfolgen auf dem bestehenden Zweig `feature/nx-native-versioning`; keine automatische Übernahme in den Hauptzweig.

## Review-Schwerpunkte

1. Doppelte Haus-/Geländevorkommen und doppelter Höhenversatz.
2. Überdeckte Aushubdarstellung durch Bestandsgelände oder gleichzeitig sichtbare Alternativlager.
3. Fehlende/ungeklärte Registereinträge als scheinbar bestätigte Räume/Wohnungen/Felder.
4. Referenzen auf Quellordner und übersehene Komponenten beim verschobenen Wiederöffnen.
5. Fehlende native Evidenz, global vermischte Rollenvolumen oder ungetestete gespeicherte Sichtbarkeit.
