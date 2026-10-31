# Git-Übergabe – Entwurf

## Auftrag
Der Nutzer möchte das Haus-/Umgebungsprojekt in ein Git-Verzeichnis übernehmen und mit Codex weiterentwickeln. Keine neue Hausgeometrie, keine neue Kellerplanung und kein Upload in einen fremden Dienst sind Bestandteil dieser Übergabe.

## Entscheidung
Das vorhandene vollständige G02-Archiv wird unverändert unter `projects/g02/` entpackt. Eine komplette Neuordnung des alten NX-Codes würde zahlreiche relative Dateipfade und Prüfsummen verändern; sie ist für die Übergabe unnötig riskant. Ein bloßes Ablegen des ZIP würde Codex dagegen das Lesen/Bearbeiten erschweren. Deshalb: vollständig entpackter Bestand plus schlanke Repository-Werkzeuge.

Die erhaltenen K01-Unterlagen bleiben separat unter `renovierung/k01_unterlagen/`. Das nicht verfügbare K01-Programm und seine Maßnahmen-STEP-Dateien werden nicht nachgebildet oder als vorhanden ausgewiesen. Die Renovierungsanforderung wird als künftiger Implementierungsauftrag gesichert.

## Grenzen
Keine nativen .prt-Ausgaben vorhanden; Nutzer muss seinen erfolgreichen NX-Ausgabeordner lokal sichern. Keine NX-Lizenz, NXOpen-Bibliotheken oder vertraulichen Schlüssel beilegen. Privates Repository erforderlich, wenn die enthaltenen Hausunterlagen nicht veröffentlicht werden sollen. Die Versionierung ist keine bautechnische Freigabe.

## Abnahme
G02 vollständig und bytegleich; K01-Lücke sichtbar; offline ausführbare Prüfungen; AGENTS.md mit Betriebs- und Sicherheitsregeln; übertragbarer Git-Workflow; frisch entpacktes Lieferarchiv geprüft. Die aktuelle Python-/Simulationsprüfung ist ausdrücklich kein NX-/Parasolid-Lauf.
