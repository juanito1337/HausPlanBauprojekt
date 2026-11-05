# M01.2 – Lagerstandort A als Darstellungskandidat

Stand **04.11.2026**. Der bisherige gemeinsame Lagerplatz bei **X = 13.000 / Y = −16.000 mm** überlagert modellierte Bestandshecken. Für die Darstellung wird **Kandidat A bei X = 14.500 / Y = −9.500 mm** bevorzugt. A hat gegenüber Kandidat B höhere Abstände zur Vegetationsprojektion, zum vorhandenen Leitungskorridor und zum Kartenrand. **Keine Ausführungsfreigabe.**

[Aktuelle maßstäbliche Ansicht von A](../../renovierung/planung/2026-11-04/M01_LAGERSTANDORT_A.png) · [Vektorfassung](../../renovierung/planung/2026-11-04/M01_LAGERSTANDORT_A.svg) · [kompakter Quellen-/Ergebnisnachweis](../../renovierung/planung/2026-11-04/M01_LAGERSTANDORTE_XY.json) · [CLI-Prüfung](../../tools/check_m01_lagerstandorte.py).

Die neue Ansicht verwendet die tatsächlich am Standort A neu berechneten Kontaktpolygone aus `piles_site_a.json`, keine starr verschobenen alten Haufen. Sie zeigt die Einzelfeldalternative PS01-F01 und die größte Reserve-Kontakthülle aller 22 Alternativen. Die frühere [Ansicht des alten Lagerorts](M01-2-PS01-F01-Lageplan.png) bleibt unverändert als Konfliktbeleg erhalten. Beide Bilder sind berechnete Draufsichten. Keine NX-Bildschirmaufnahmen.

## Konflikt des bisherigen Platzes mit dem modellierten Bestand

Alle 22 Hauptlager und alle 22 Reservelager liegen am bisherigen Zentrum. Die Flächen wurden aus ihren tatsächlichen, innen disjunkten Kontaktpolygonen mit den offenen Vegetationsrasterflächen geschnitten. Der Nachweis beruht auf den tatsächlichen Kontaktpolygonen.

| Modellierte Vegetationsgruppe | Hauptlager | Reserve, alternativ |
|---|---:|---:|
| V02, südliche Stellplatzhecke | 22/22 betroffen. 6,845–10,881 m² Überlagerung | 22/22 betroffen. 7,237–11,208 m² |
| V01, nördliche Stellplatzhecke | 18/22 betroffen. Höchstens 0,922 m² | 19/22 betroffen. Höchstens 1,698 m² |
| V03 / V05, vordere Gehölzgruppen | keine Projektionsüberlagerung | keine Projektionsüberlagerung |

Die Grundstücksprojektion wird dabei nicht verlassen. Der numerische Flächenrest liegt unter `4e-13 m²`. Auch EG-Projektion und die vorhandenen K02-Leitungskorridore werden am alten Ort nicht überlagert. Das macht den Heckenbereich nicht zu einem freien Lagerplatz. Dass Vegetationsgruppen in der Arbeitsansicht ausgeblendet werden, hebt ihren Bestandskonflikt nicht auf.

V01/V02/V03/V05 sind tatsächlich in der gültigen G02-Lieferung enthalten. Die CLI prüft ihre STEP-Hashes und zugehörigen Geometriereferenzen, affine XY-Knoten jeder Fläche sowie die Bytes der vier vorhandenen nativen G02-Parts. Die Projektionsflächen betragen für V01 26,96 m², für V02 18,60 m², für V03 6,08 m² und für V05 7,48 m². Die G02-Umgebung hat keine XY-Verschiebung. Ihr vorhandener Höhenanschluss ist ausschließlich Z = −31.362,49870845903 mm.

## Zwei geprüfte Alternativen

Die Abstände sind **konservative untere Schranken in der Horizontalprojektion**. Gemessen wurde die größte Fehlerhülle gegen alle 22 vorhandenen Grubenhüllen sowie gegen die jeweils gesamte aufgeführte Hinderniskategorie. Damit ist der Nachweis stärker als ein bloßer Vergleich eines Haufens mit seiner zugehörigen Einzelfeldgrube.

| Kriterium | A, bevorzugte Darstellung | B, Alternative |
|---|---:|---:|
| Zentrum X/Y, mm | **14.500 / −9.500** | 10.000 / −22.000 |
| Abstand zu allen Grubenhüllen | **≥2,360 m** | ≥15,286 m |
| Abstand V01/V02/V03/V05 | ≥0,339 m | ≥0,286 m |
| Abstand Haus/Überbau/Garage | ≥5,418 m | ≥18,404 m |
| Abstand vorhandener K02-Leitungskorridor | ≥3,962 m | ≥1,361 m |
| Abstand Kartenrand | ≥5,557 m | ≥1,927 m |
| Fläche größter Haufen auf örtlichem TIN | 52,632 m² | 51,991 m² |
| konservative obere Fehler-Kontaktfläche | 55,275 m² | 54,367 m² |

Bei A und B beträgt die berechnete Überlagerung mit Vegetation, Haus/Überbau, den vorhandenen Leitungskorridoren und Grubenhüllen jeweils **0 m²**. Außerhalb der Kartenkontur verbleibt nur numerisches Rundungsrauschen unter `1,5e-12 m²`. Das Prüfband beträgt `1e-8 m²`.

Der geforderte **mindestens 0,60 m freie horizontale Streifen zwischen Grubenkante und Lager** ist bei beiden Punkten bereits mit der größten gemeinsamen Hülle erfüllt. Diese rein geometrische Bedingung bestätigt weder einen sicheren Auflastabstand noch eine ausreichend breite oder tragfähige Zuwegung. Ein Abstand von 0,60 m zu allen anderen Hindernissen wird nicht behauptet. Insbesondere sind die Vegetationsabstände kleiner.

## Hüllenherleitung und Umfang

Die 44 Haupt-/Reservealternativen behalten ihre bisherigen Zielvolumen. Der größte Reserveansatz beträgt **31,3415321567 m³**. Am jeweiligen neuen Zentrum wird dieser Haufen auf dem dortigen DGM/TIN erneut berechnet. Die vorhandene einheitliche Dachneigung ist 0,5. Die größte Reserve umfasst am gleichen Zentrum sämtliche kleineren Haupt-/Reserveformen, weil ihre Dachfunktion `min(H ± k·x, H ± k·y)` mit H überall monoton steigt.

Das TIN verwendet vier Unterteilungen und einen globalen vertikalen Fehler ε = **20,78125 mm**. Für dieselbe Zielmenge auf einem Gelände innerhalb ±ε liegt die nötige Dachhöhe höchstens bei `H_nominal + ε`. Diese obere Dachhöhe wird gegen `TIN − ε` geschnitten. Die resultierende Kontaktmenge umschließt damit auch eine durch den Geländefehler erforderliche Volumen-Neulösung. Die konvexe Hülle dieser Kontaktmenge dient nur dem konservativen Abstandstest. Sie wird nicht als neuer Haufen oder neue Aushubmenge abgerechnet. Ein Erreichen des lokalen TIN-Rands wird ausdrücklich abgewiesen.

Geprüft werden die Grundstückskontur aus `haus.json`, KG/EG/Anbau/Garage aus `sektionen.json`, alle 22 vorhandenen Gruben-Unsicherheitshüllen, die aktiven Vegetationsflächen und die registrierten Leitungsplanprojektionen. Die Leitungskorridore behalten die bestehende K02-Studienannahme **1.000 mm Halbbreite**. Das ist kein georteter Leitungsquerschnitt und kein bestätigter Schutzabstand.

## Reproduktion und Integrität

Benötigt wird ein **vollständiger K02-Plan mit Kontakt-/Projektionspolygonen**, nicht die gekürzte Mengenübersicht oder ein kompakter BUILD-Plan. Der beim Nachweis verwendete Vollplan hat SHA-256:

```text
985c719f89586d1c8d3d311bf9c156e46b42d025b27797a367164711a343c279
```

Die Vollplanung lässt sich bei Bedarf aus dem vorhandenen `renovierung.k02.planning.create_plan` und `study_config.json` wiederherstellen. Das ist ein eigener reiner Python-Planungslauf. Er ist kein NX-Lauf. Ein Beispiel für einen frischen Checkout folgt.

```powershell
python -c "import json; from pathlib import Path; from renovierung.k02.planning import create_plan; from renovierung.k02.terrain import read_json; r=Path('.').resolve(); p=r/'reports/local/m02/PLAN.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(create_plan(r,read_json(r/'renovierung/k02/study_config.json')),ensure_ascii=False,indent=2),encoding='utf-8')"
```

Die Standortprüfung am 04.11.2026 wurde tatsächlich mit **Exit 0** ausgeführt.

```powershell
python -B tools/check_m01_lagerstandorte.py --plan reports/local/m02/PLAN.json --output renovierung/planung/2026-11-04/M01_LAGERSTANDORTE_XY.json --candidate A 14500 -9500 --candidate B 10000 -22000 --preferred A
```

In dieser Umgebung wurde dafür der vorhandene Interpreter unter `C:/Users/1337/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` verwendet. Die CLI führt keine Standortsuche durch. Sie prüft zuerst alle K02-Eingabe- und Generatorhashes samt vollständigem Generatorinventar, Quellenrollen und Konfiguration. Das Ergebnis enthält zusätzlich die Hashes von G02-Vegetationsauftrag/Auswahl/STEP, vorhandenen G02-Nachweisen/Vegetationsparts und Prüfwerkzeug. Alle Quellen werden nach der Rechnung erneut geprüft. Negative Prüfungen haben einen geänderten Eingabehash, einen fehlenden Generator und einen geänderten Generatorhash tatsächlich abgewiesen.

Für ein hartes Darstellungs-Gate sind unter anderem passendes Schema, `construction_release=false`, 22 Felder, 44 eindeutige ursprüngliche Alternativen, bevorzugter Kandidat A mit unverändertem Zentrum, `geometric_criterion_passed=true`, Grubenabstand ≥0,60 m, alle anderen Abstände positiv, sämtliche Überlappungssummen und Außenfläche unter `1e-8 m²` sowie weiterhin passende Quell-/Generatorhashes erforderlich. Das Gate ist eine Darstellungsprüfung, keine Bau-Freigabe.

Die aktuelle Ansicht wurde anschließend mit dem reinen [Grafikhelfer](../../tools/render_m01_lagerstandort_a.py) aus den vorhandenen echten A-Kontaktpolygonen erzeugt, **Exit 0**, und als PNG visuell geprüft.

```powershell
python -B tools/render_m01_lagerstandort_a.py --plan reports/local/m02/PLAN.json --piles reports/local/m02/piles_site_a.json --check renovierung/planung/2026-11-04/M01_LAGERSTANDORTE_XY.json --out renovierung/planung/2026-11-04/M01_LAGERSTANDORT_A
```

Dieser Helfer benötigt Pillow, berechnet keine neue Modellgeometrie und verändert keinen Plan. PNG und SVG tragen Hashes der verwendeten Kontakte, des Vollplans, des Standortnachweises und des Grafikhelfers. Beide verwenden A3 quer (420 × 297 mm). Bei 100 % Druck gilt links 1:250 und rechts 1:100. Bei veränderter Anzeigegröße gelten die eingezeichneten Maßstabsleisten. Die große violette Linie ist die konvexe **nominale** Kontakthülle der größten Reserve aus dem A-Plan. Die strengere Fehlerhülle der Abstandstabelle ist davon getrennt.

## Offene fachliche Grenzen

- Vegetationsoberflächen stammen aus bDOM vom **07.04.2023**, ihre Auswahlmaske aus dem Bildstand **12.05.2025**. Der Videoabgleich bestätigt nur plausible Bereichsidentität. Heutiger Heckenbestand, Stamm-/Wurzellagen und Schutzbereiche sind nicht vermessen. Ausgeschlossene V04/V06/V07/V08 dürfen nicht als beseitigt interpretiert werden.
- Leitungsprojekte sind Bestandsplanregistrierungen ohne bestätigte Tiefen. Im Quellenregister fehlen Trinkwasser-Hausanschluss, Schmutz-/Regenwasser, Drainage und gegebenenfalls Fernwärme. Auch ein positiver Projektionsabstand schließt unbekannte Leitungen nicht aus.
- Grundstücksrand bleibt Kartenreferenz. Gründung, Boden, Wasser, Lagerauflast, Böschungsstandsicherheit, Erreichbarkeit und Aufstell-/Transportflächen sind nicht freigegeben. Es werden weder Wege noch Tragfähigkeit erfunden.
- Keine neue NX-Erzeugung oder native Sichtprüfung durch diese Standortauswertung. Eine Übernahme von A in die Hauptbaugruppe benötigt die gesonderten M01-Erzeugungs-/Wiederöffnungsnachweise. Haupt- und Reservehaufen bleiben Einzelfeldalternativen am selben Platz.
