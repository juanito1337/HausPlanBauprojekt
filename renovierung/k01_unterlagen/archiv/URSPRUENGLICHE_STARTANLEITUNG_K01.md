# Keller-Renovierung K01 – eigenständige Konzept-Erweiterung

**Vorhandenes G02 nicht neu erzeugen.** Das neue Paket verändert keine Quelldateien und wird NICHT in G02 hineinkopiert.

## Start in NX
1. Das komplette K01-ZIP separat in einen kurzen beschreibbaren lokalen Ordner entpacken.
2. Eigene Änderungen bewusst speichern. Die erfolgreiche `PROJEKT_MASTER_G02_...prt` mit Haus und Umgebung als Anzeigeteil geöffnet lassen.
3. Zum ersten Schnittstellentest `01_NUR_RENOVIERUNG_BASIS_K01.py` starten. Es wird eine unabhängige Basis geklont; noch keine Grube erzeugt.
4. Nach dem Basis-Test wieder die ursprüngliche G02-Projekt-Masterdatei als Anzeigeteil aktivieren (die Kopie nicht löschen). Für Basis und alle vorbereiteten Zustände `00_RENOVIERUNG_K01_ERZEUGEN.py` aus demselben Paket starten. Keine alten G02-/Geländeerzeuger ausführen. Die vollständigen Kopien brauchen Speicherplatz und Zeit; der benötigte Platz wird vorher abgeschätzt.
5. `data/EINSTELLUNGEN_K01.json`: `stages: "ALL"` erzeugt alle Zustände. Alternativ eine Liste, z.B. `["BA05"]`, zum gezielten Gegencheck. Die auf einen späteren BA bezogenen fertiggestellten Vorbereiche sind aus derselben Studienfolge enthalten.

**Ein neuer Lauf legt einen neuen Ausgabeordner an.** Originaldateien werden weder gespeichert, geschlossen, überschrieben noch verknüpft als neue gemeinsam editierbare Bauteile übernommen. Pro Zustand entstehen eigene Partkopien. Beim Kopieren erkannte fremde Referenzen, ungespeicherte Änderungen oder Dateiabweichungen stoppen den Ablauf.

Die neue Basis enthält keine Maßnahmen. In Bauabschnittskopien wird nur das kopierte Gelände ausgeblendet; eine abgeleitete Geländeoberfläche mit dem aktuellen offenen Feld wird eingefügt. Zur Mengenkontrolle sind ausgeblendete Aushubkörper enthalten. Schicht-, Schutz- und Verbauhüllen sind Konzeptgeometrien und entsprechend bezeichnet.

**Alle Bauzustände bleiben fachlich gesperrt.** Ein erfolgreiches Journal ist keine Baustellenfreigabe. Die kleinen Prüffelder sind keine statisch bestätigten Öffnungslängen.

## Ausgabe
`ausgabe/K01_<Zeit>_<Kennung>/Renovierung_Basis/` und `Renovierung_BAxx/`.
Jeder Zustand besitzt eigene Komponenten; gespeicherte Zustände werden standardmäßig geschlossen, damit nicht alle großen Kopien zugleich in NX geladen bleiben.
`RENOVIERUNG_K01.json` enthält Kopier-/Dateinachweise, Schritte und Fehler. Eine Datei `STOP_K01.txt` im aktuellen Ausgabeordner fordert einen Stopp zwischen NX-Aufrufen an; kein harter Kernel-Timeout.

Bei Erfolg die jeweilige Renovierungs-Masterdatei direkt öffnen. Nicht den Erzeuger bei jedem Arbeiten neu starten. Die Kopieordner mitsamt Komponenten zusammenlassen. Bei Fehlern das neue Protokoll hochladen; Originaldateien nicht löschen.

## Prüfung und Grenzen
Kein eigener NX-Lauf. Neue Clone-Schnittstelle muss in der Installation bestätigt werden. Lokale Python-/CAD-Prüfungen sind im Prüfprotokoll ausgewiesen, nicht mit NX-Tests gleichgesetzt. Keine neue Statik, unbekannte Anbauplatte, Gründungs- und Leitungstiefen; keine automatische Grundwasserabsenkung.

Die unabhängigen Kopien brauchen absichtlich mehr Speicher als eine Baugruppe mit gemeinsam benutzten Originalteilen. Dies verhindert Rückwirkungen auf G02 und zwischen den Zuständen.
