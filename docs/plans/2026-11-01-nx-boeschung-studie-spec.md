# K02: Native NX-Studie Böschung und Abraum

Nutzerfreigabe 01.11.2026: Umsetzung des zuvor besprochenen Ansatzes mit Superpowers und Subagent-Prüfung. Keine Bauausführung freigegeben. G02 und alle Originalteile bleiben unverändert. Dieses Dokument konkretisiert den aktuellen Studienauftrag; vollständige Sanierungsdetails folgen später.

## Ergebnis

Native unabhängig kopierte Renovierungsbasis und pro modellierbarem Arbeitsfeld eine eigene NX-Baugruppe mit Bestand, sichtbar eingeschnittenem Studiengelände, separat zuschaltbarem Aushubkörper, Böschungsflächen und volumenrichtigem Abraumhaufen. Alle 13 PS bleiben im Register; ausgeschlossen/ungeklärt wird ausdrücklich dargestellt, nicht gelöscht. Jeder Arbeitszustand zeigt höchstens ein geöffnetes Feld. Mengenbericht je Feld mit gewachsenem/erneut ausgehobenem Material, lockerem Lager und verdichtetem Wiedereinbau; keine unbereinigte Summe als Netto-Erstaushub ausgeben.

## Verbindliche Grundlagen

- mm in NX; unveränderte Höhenquelle `projects/g02/data/HOEHENANSCHLUSS_G02.json`; Umgebung einmal auf Elternteilebene verschoben.
- V01-Katalog plus `UMFANG_E01.json` lesen; PS05/08 vorläufig ausgenommen, PS02-Niedergang nicht automatisch gesamte Fassade ausnehmen. PS03/10 Anschluss ungeklärt. Anbau ohne Bodenplatten-UK: keine erfundene Sohle oder m³-Angabe.
- Hauptkeller-Sohle in Studie: -2605 mm, ausdrücklich Prüfziel, keine Bodenaushubfreigabe. 1:1-Seiten- und Endböschungen = Nutzerannahme; keine ungesicherte senkrechte Erd-Stirnseite.
- Arbeitsraum 800 mm und Sohlenlänge bis 2000 mm sind vorläufige Darstellungsannahmen des Assistenten (optionale Nutzerfrage gestellt). Enden/Ecken/Konflikte begrenzen modellierbare Felder; unerreichbare Restbereiche im Bericht erhalten.
- Keine neuen geotechnischen Kennwerte behaupten. `construction_release=false` für sämtliche Felder. Grundwassererwartung als Nutzerangabe, keine Messkote.

## Geometrie

G02-DGM besteht aus bilinearen Zellen, nicht aus einem TIN. Studien-TIN lokal verfeinern; maximale vertikale Abweichung zur bilinearen Zelle über `abs(z00-z10-z01+z11)/(4*N*N)` begrenzen. Ziel höchstens 25 mm, unabhängig von CAD-Übertragungstoleranz. Darstellung/Volumen stammen aus diesem ausdrücklich approximierten Studienboden; Eingangsgelände bleibt als kopierte Referenz erhalten. Eingriff, Lager und Grundstücksprüfung beziehen sich auf dasselbe Höhenmodell. Volumenband für TIN-Unsicherheit und Differenz zum nativen gemessenen Körper berichten.

Lokal entlang Wand s, außen n, Sohlenlänge L, Arbeitsraum w: Unterfläche des Eingriffs ist `max(z0,z0+n-w,z0-s,z0+s-L)`, mit n>=0 und Obergrenze GOK(s,n). Diese miterförmige 1:1-Hülle enthält beide Endböschungen. Nur positive Schnittmenge mit Boden zählt. Haus, Garage, überbaute/exkludierte Bereiche, Kartengrenze und bekannte Hindernisse prüfen. Bei Kollision Feld als geometrischen Konflikt führen; nicht durch steilere Böschung oder beschnittene Sicherung passend machen. Bodeneinfluss/Fundamente und Leitungstiefen bleiben fachlich ungeprüft, auch wenn 2D-Geometrie passt.

Sohlenfelder zunächst entlang geeigneter gerader Hauptkellerkanten teilen; eindeutige PS/F-IDs. Eingriffsüberlappungen wegen Endböschungen explizit ermitteln. Wenn eine sichere technische CSG-/Sequenzbilanz nicht gelingt, unabhängige Einzelfeldvarianten eindeutig kennzeichnen und keine kumulative Baufolge oder Netto-Gesamtmenge behaupten; diese Einschränkung muss sichtbar im Modell und Bericht stehen. Das ist eine Studiengrenze, kein erledigter vollständiger Bauablauf.

## Material und Haufen

Referenz: WSDOT Geotechnical Design Manual M46-03.08, Chapter10, Table10-1 (S.10-12, 10/2013), https://wsdot.wa.gov/publications/manuals/fulltext/m46-03/chapter10.pdf, Abruf01.11.2026. Beispiel Sand: +5% locker, -11% verdichtet gegenüber in situ. Die Tabelle enthält feuchte Raumgewichte; diese nicht als Trockenrohdichten ausgeben. Rechenannahmen: `loose/bank=1.05`, `compacted/bank=0.89`; Sensitivität locker1.15/1.25 als bewusst erhöhte Szenarien, keine belegte örtliche Bandbreite. Kein tatsächlicher Bodenmassenwert ohne Dichtedaten.

Zustandsrechnung bei gleichem Material: `Vloose=Vbank*fl`, `Vcompacted=Vbank*fc`, `Vloose_needed=Vfill*fl/fc`. Wiederverdichtung erzeugt ggf. Fehlmenge, nicht automatisch Überschuss. Echte Trockenrohdichten können später eine alternative Massenerhaltungsrechnung liefern; keine Vermischung mit feuchten Tabellenwerten. Bereits verfülltes Material darf bei erneutem Aushub nicht erneut als gewachsen gezählt werden.

Haufen als geschlossener Bodenaufschüttungskörper mit echtem Kontakt zum Studiengelände, zunächst quadratischer Pyramidenform 1:2 (26,565°) als reine Formannahme, keine Standsicherheitsfreigabe. Höhe durch Volumenziel lösen. Grundstück, Haus, Eingriff und bekannte Medienkorridore nicht belegen; Lagerlasten/Wege bleiben ungeprüfte Logistik. Bei Platzkonflikt keine scheinbar zulässige Haufenposition erzwingen. Auch Reservevolumen1.25 auf Platzbedarf prüfen. Keine frei schwebende ebene Haufensohle auf schrägem Gelände.

## Native Lieferung und Verifikation

Kopieren aller referenzierten Parts mit eindeutigen Namen und explizit umgestellten Komponentenpfaden; keine Original-/Cross-State-Referenzen. Vorher/nachher Quellhashes und Komponentenlagen prüfen. Neuer API-Pfad zuerst an kleinem Würfel und dreiteiliger Baugruppe in echtem NX erproben. Kein NXOpen unter gewöhnlichem Python simulieren.

Ausgabe unter `cad/nx/` mit Git LFS. Studienmanifest nennt Eingabe-/Generatorhashes, Annahmen, Fach-/Geometrie-/Native-Status, alle Dateien, Feldmengen, echte NX-Volumenmessungen. Jede Lieferung frisch und nach Verschieben erneut öffnen, vollständig geladene Parts/mm/interne Pfade/gespeicherte Ansichten und Volumina prüfen. NX-Bilder als Sichtprüfung aus realem Modell erzeugen, keine gerenderte Webvorschau als NX-Beleg.

`tools/nx_project.py build --accept-model-assumptions` muss neue K02-Quellen berücksichtigen und vorhandenen G02-Stand wiederverwenden können; G02-Erzeugung nur bei tatsächlich geänderten G02-Eingaben, nicht wegen jedes Studienfeldes. `check` prüft Basis und Studie, sobald aktiviert. Alte G02-Nachweise nicht als K02-Erfolg umetikettieren.
