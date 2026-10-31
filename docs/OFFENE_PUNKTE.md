# Offene Punkte – keine automatische Freigabe

| ID | Befund / Aufgabe | Status |
|---|---|---|
| DATA-01 | Vollständiger K01-Code und Maßnahmen-CAD fehlen. | Neu implementieren oder aus echter lokaler Quelle wiederherstellen; Dokumente allein sind keine Implementierung. |
| NX-01 | Tatsächliche erfolgreiche G02-`.prt` und Laufmanifeste liegen nur beim Nutzer. | Separat sichern, Referenzen prüfen; nicht neu erzeugen, nur um Git anzulegen. |
| HEIGHT-01 | G02-Höhe basiert auf übertragener historischer Außenkote. | Planannahme, kein vermessener heutiger Anschluss. |
| SITE-01 | Grundstückslinie ist Kartenreferenz. | Grenzlage für reale Erdarbeiten fachlich klären. |
| STRUCT-01 | Fundamentunterkanten, Abmessungen, Baugrund/Wasser fehlen. | Keine Aushub-/Unterfangungs-/Verbau-Freigabe. |
| GEOM-01 | Zehn bekannte Haus-Anbau-Überschneidungspaare. | Bestehend; keine neue Konfliktbehebung in der Übergabe. |
| GEOM-02 | Zwei teilweise blockierte Innentüröffnungen. | Bestehend; getrennt von Renovierung prüfen. |
| ROOF-01 | Dachtragwerk/Gaubenanschlüsse teils Näherungen. | Keine Dachstatik hinzugefügt. |
| UTIL-01 | Historische Leitungslagen, Tiefen unbekannt. | Projektion Z=0 nicht als Isttiefe verwenden. |
| REN-01 | UK Bodenplatte minus 100 mm. | Nutzer-Prüfziel, nicht zulässige Grubensohle. |
| REN-02 | Unabhängige Kopie von Basis und jedem Bauzustand. | Neu zu implementieren; echte NX-Integrationsprüfung erforderlich. |
| REN-03 | K01-Studienmengen/-takte. | Historische Vergleichswerte; neue Geometrie muss neu bilanziert und auf Konflikte geprüft werden. |
| PACK-01 | Historische ZIP-/Testbehauptungen ohne Artefakt. | Nicht übernehmen; neue Releases aus tatsächlichen Dateien bauen und frisch entpackt prüfen. |

Aktive Entwicklung: `docs/ENTWICKLUNGSPLAN.md`. Änderungen an diesem Register benötigen einen konkreten Nachweis. „Tests grün“ allein schließt keinen der fachlichen Punkte.
