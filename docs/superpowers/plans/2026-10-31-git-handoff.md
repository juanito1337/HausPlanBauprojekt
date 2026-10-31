# Git-Übergabe Implementation Plan

**Goal:** Ein vorhandenes, lesbares und prüfbares Git-Arbeitsverzeichnis für Codex liefern.

**Architecture:** G02 unter `projects/g02/` unverändert erhalten. Repository-spezifische Dokumentation und Standardbibliothek-Werkzeuge außerhalb des Altbestands ergänzen. K01 ausschließlich als historische Unterlagen und offener Entwicklungsauftrag kennzeichnen.

**Tech Stack:** Python >=3.10, Git, Markdown, JSON, unittest. NX 2406 nur beim Nutzer. Optionale Open-CASCADE-Prüfungen getrennt.

**Spec:** `docs/superpowers/specs/2026-10-31-git-handoff-design.md`

## Globale Grenzen
Kein Remote-Push, keine Änderung von Quellgeometrie oder G02-Programmen, keine erfundenen K01-Dateien, keine automatische NX-Ausführung.

## Aufgaben
- [x] G02/K01-Originalarchive einlesen, CRC prüfen, Dateihashes und Herkunft dokumentieren.
- [x] Repository-Werkzeuge zuerst mit Tests für fehlende/geänderte Dateien und Pfadausbruch absichern.
- [x] AGENTS.md, Projektstand, Architektur, Renovierungsauftrag und lokale/Cloud-Prüfwege schreiben.
- [x] Git-Ignore und Attribute gegen ungewollte Ausgaben und Zeilenendekonvertierung prüfen.
- [x] Unveränderte G02-Offline-Tests und Übergabe-Werkzeugtests ausführen.
- [x] Repository mit Git testweise initialisieren; alle vorgesehenen Dateien müssen versionierbar sein.
- [x] Liefer-ZIP bauen, frisch entpacken und Datei-/Syntax-/Werkzeugprüfungen wiederholen.

## Review-Fokus
Ungeprüfte Bauannahmen bleiben Annahmen. Historische K01-Testzahlen sind kein aktueller Nachweis. .gitignore darf benötigte Quellen nicht ausschließen. Git-Checkout darf Prüfsummen nicht durch CRLF verändern. Archiv darf weder .git noch lokale Ausgaben oder geheime Konfiguration enthalten.
