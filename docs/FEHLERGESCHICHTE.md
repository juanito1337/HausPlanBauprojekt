# Fehlergeschichte für Regressionen

Historische Berichte unter `historie/diagnosen/` bleiben Daten früherer Stände. Die nachfolgenden Lösungen sind im G02-Bestand dokumentiert; sie sind keine Behauptung, dass jeder denkbare Fall behoben wurde.

| Phase | Beobachtung | Übergaberegel |
|---|---|---|
| R03 | Netzwerkpfad `Path.resolve`, Einheitenerkennung, Ausdrucksattribute/reserviertes `MATERIAL`. | Bestehende Pfad-, Einheiten- und Attributlösungen nicht unbemerkt zurückbauen. |
| R09a/b | 49 erwartete Flächen vs. 56 importierte Unterflächen. | Topologie-Unterteilung allein ist kein Geometrienachweis. Körperlage und Form prüfen. |
| R09b–e | Flächenmessung 820001 und instabile Integration. | Kein Quellenflächenwert als falsches NX-Messergebnis einsetzen; Normalmodus vermeidet teure Integration. |
| R10/G01 | Abstandsabfrage liefert scheinbare Meterfehler im DGM; Diagnosepunkte liegen am Rand. | Direkte Parameterprüfung des tatsächlichen Geländes erhalten; Toleranzen nicht zum Kaschieren erhöhen. |
| G01b/c | Vier gedachte Randseiten wurden in 285 tatsächliche Kanten zerlegt. | Seitenketten statt starrer Kantenanzahl. |
| G01c | 0,263727 mm an langer Randkante überschritt 0,25 mm. | In G01d alternative exakte Randrepräsentation; keine nachträgliche Grenzwerterhöhung. |
| G01d/e | Import: ein Körper mit 8.282 Einzelflächen. | G01e ordnet Rasterpatches, Abdeckung, Nähte, Flächenpunkte und Rand zu. |
| H01/H01a | Teilbeladung und ungespeicherte äußere Masterdatei. | G02 verwendet gespeicherte Komponenten aus Manifesten, lädt gezielt nach, schützt tatsächliche geänderte Quellteile. |
| G02 | Nutzer meldet erfolgreichen Gesamtaufbau. | Diesen Ausgangsstand sichern; Höhenbezug bleibt Planannahme. |
| K01 | Vollständiges angekündigtes ZIP nicht verfügbar. | Erhaltene 8 Dokumente als solche kennzeichnen, Implementierung nicht vortäuschen. |

Konkrete Beispiele: `STARTFEHLER_G01a_20261011_124825_69a57d5d.json`, `STARTFEHLER_G01c_20261012_121659_75b4ef58.json`, `STARTFEHLER_G01d_20261012_231858_556c0280.json`. Bei Tests synthetische Daten und echte Nutzerbefunde klar trennen.
