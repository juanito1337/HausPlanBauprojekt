# Nächste Arbeitspakete für Codex

## M0 – Bestand sichern (vor Maßnahmengeometrie)

G02-Import und Tests reproduzieren. Erfolgreichen Nutzer-Lauf als lokale Quelle inventarisieren, ohne Dateien zu verändern. Den vollständigen Baugruppenbaum, Komponentenpfade, Einheiten, Transformationen, Unterdrückungen, Referenzmengen, Materialien und Änderungszustände dokumentieren. Fehlende Quellen und manuelle Änderungen sichtbar melden. Abnahme: rein lesender Bericht, keine NX-/Dateiänderung durch Inventarisierung.

## M1 – Unabhängige Renovierungsbasis

Kleine Testbaugruppe mit Unterbaugruppe, gemeinsamem Prototyp und einer echten Fremdreferenz als Testfälle. Clone-Schnittstelle anhand der lokalen NX2406-Dokumentation prüfen. Eindeutigen neuen Zielordner verwenden, Namen/Referenzen auf neue Dateien umlenken, keine gemeinsamen bearbeitbaren Daten mit Originalen. Dateihashes und Zustand des Originals vor/nach, Einheiten und Positionen vergleichen; neue Basis speichern und erneut öffnen. Fehler nicht durch Deaktivierung des Kopierschutzes umgehen.

Abnahme in NX beim Nutzer: identischer Bestand, keine Maßnahmen, keine Originalverweise. Erst danach M2.

## M2 – Belastbare Eingabedaten und Sperrregister

Kelleraußenkontur und Platten-/Fundamentbezug getrennt ermitteln. Jeden Wert mit Quelle, Einheit und Status führen. Vorläufige Höhen und Kartengrenze markieren. Anbauten, Treppen, Lichtschächte, Leitungen, Zugänge und Auflager berücksichtigen. Keine pauschale Hauptkellertiefe an ungeklärte Anbauten übertragen. Ziel UK Platte −100 mm nur als Prüfziel.

## M3 – Geometrische Varianten und Volumen

Pro geometrisch sinnvoll abgegrenztem Prüffeld A/B als explizite Studienkonfiguration. Böschung quer zum Graben, Sicherungsbedarf auch an Enden/Ecken. Kein Winkel allein aus „Sand“. Arbeitsraum außerhalb der neuen Schichten und Sicherungskonstruktion messen. Alles einschließlich Sicherung/Lager/Wege innerhalb der Modellgrenze prüfen; Kartengenauigkeit gesondert begrenzen. Aushubvolumen direkt aus tatsächlich erzeugter Geometrie ableiten, Alternativrechnung und Abbruch bei Inkonsistenz.

## M4 – Abfolge und Bodenbilanz

Nur ein aktueller Abschnitt offen; alle vorangegangenen zulässigen Felder fertig und wiederverfüllt, spätere geschlossen. Ecken/Sperrstellen eigenständig. Auflockerung und Wiederverwendbarkeit als Annahmen führen. Haufenvolumen, Lagerfläche und Höhe stimmen mit laufender Bilanz; kein verschwundener Restboden. Transport- und Rettungszugang nicht blockieren. Belastungen und Wasser bleiben fachliche Prüfpunkte.

## M5 – Unabhängige Bauzustände und Darstellung

Jeder Zustand echte unabhängige Dateien, nicht geteilte veränderbare Basisteile. Kopiertes Gelände nur im eigenen Zustand ersetzen/ausblenden; Original bleibt unberührt. Abdichtung/Dämmung/Schutz getrennt, Quellenstatus visuell erkennbar. Grenzen, Schnitte und Sperrzonen eindeutig. Keine graphische Darstellung als sichere Bauausführung missverständlich freigeben.

## M6 – Abnahme und Lieferung

Daten-/Geometrietests, reale NX-Kopier-/Import-/Speicherprüfung und fachliche Freigabe strikt trennen. Frisches Liefer-ZIP tatsächlich entpacken, Hashes und START-Dateien prüfen. Kompakte Tabelle: Abschnitt, Seite, Reihenfolge, Variante, Maße, Mengen, Lager, offene Punkte. Nutzerdaten nicht überschreiben. Einen ersten kleinen Zustand liefern und prüfen, bevor alle vollständigen Kopien erzeugt werden.

Diese Roadmap ist Entwicklungsarbeit, kein Baustellenablaufplan. Die bindenden Nutzervorgaben stehen daneben unverändert in `ANFORDERUNGEN_RENOVIERUNG.md`.
