# Renovierung Keller – ursprünglicher Nutzerauftrag

## Umfangsergänzung des Nutzers vom 01.11.2026

Überbaute Bereiche und Kellerniedergänge werden voraussichtlich ausgelassen; für Niedergänge wird alternativ ein gesondertes Abdichtungs-/Anschlusskonzept untersucht. Der Nutzer bezeichnet den Boden als Sandboden und kündigt weitere Leitungstiefenpläne an. Diese jüngere Umfangsvorgabe konkretisiert das nachfolgende ursprüngliche Ziel „rund um das gesamte Haus“; sie ist noch keine endgültige Teilflächenfestlegung. Details und Prüfung von `Tiefbau.zip`: [Ergänzung E01](plans/2026-11-01-keller-ergaenzung-umfang-leitungen.md). Ausgenommene Bereiche nicht löschen oder als saniert darstellen; angrenzende Gründungs-/Abdichtungsrisiken bleiben zu prüfen.

Die folgenden Anforderungen stammen aus dem Nutzerauftrag im bisherigen Gespräch. Sie werden für Codex erhalten. **Sie sind Zielanforderungen, kein Nachweis einer bereits vorhandenen Implementierung oder einer sicheren Bauausführung.**

---

Die letzte Ausführung ist erfolgreich durchgelaufen und hat die vorhandene Umgebung korrekt erstellt. Erweitere das bestehende Projekt jetzt um eine **Renovierungsmaßnahme zur äußeren Abdichtung und Wärmedämmung des Kellers rund um das gesamte Haus**.

Bearbeite die Aufgabe aus der Perspektive eines Bauingenieurs und Bauleiters. Berücksichtige insbesondere einen realistischen Bauablauf, die Grundstücksgrenzen, die Erdarbeiten in Sandboden sowie die Standsicherheit des Gebäudes und der Baugrube. Die erzeugten Umgebungen dienen der **konzeptionellen Planung und Visualisierung** und ersetzen keine geprüfte Ausführungs- oder Tragwerksplanung.

## 1. Bestehende Umgebung unverändert erhalten

Die vorhandene Umgebung muss vollständig unverändert bleiben. Überschreibe oder verändere keine bestehenden Objekte, Geometrien, Materialien, Einstellungen oder Funktionen.

Erstelle zunächst eine unabhängige Kopie der bestehenden Umgebung als neue **Renovierungs-Basisumgebung**. Achte darauf, dass Änderungen an kopierten Objekten oder gemeinsam genutzten Daten nicht auf die ursprüngliche Umgebung zurückwirken.

Lege anschließend für jeden Bauabschnitt eine eigene Umgebung an. Verwende eindeutige Bezeichnungen, beispielsweise `Renovierung_Basis`, `Renovierung_BA01`, `Renovierung_BA02` usw. Positionen, Maßstab und Grundstücksgrenzen müssen in allen Umgebungen übereinstimmen.

## 2. Vorhandene Geometrie und Planungsgrundlagen prüfen

Nutze die vorhandene Projektgeometrie als Grundlage. Prüfe insbesondere die Lage des Hauses auf dem Grundstück, die Abstände zu den Grundstücksgrenzen, die Geländeoberfläche, die Kellertiefe sowie die Lage von Bodenplatte und Fundamenten. Berücksichtige vorhandene Anbauten, Treppen, Lichtschächte, Leitungen, befestigte Flächen und Zugänge, soweit diese im Projekt enthalten sind.

Unterscheide klar zwischen bekannten Projektdaten, nachvollziehbar abgeleiteten Werten und noch ungeklärten Angaben. Erfinde keine Fundamentabmessungen, Bodenkennwerte, Grundwasserstände oder statischen Nachweise.

Fehlen sicherheitsrelevante Informationen, kennzeichne die davon betroffenen Bereiche als **vorläufig und fachlich zu prüfen**. Eine vorläufige Visualisierung darf nicht als nachgewiesen sichere Bauausführung dargestellt werden.

## 3. Renovierungsziel und Aushubtiefe

Das Haus soll abschnittsweise von außen freigelegt werden, damit die Kelleraußenwände abgedichtet und wärmegedämmt werden können. Berücksichtige hierfür den erforderlichen Arbeitsraum sowie die anschließende Schutzschicht, Wiederverfüllung und Wiederherstellung des Geländes.

Die gewünschte Freilegung reicht **bis 10 cm unter die Unterkante der Bodenplatte**. Behandle diese Tiefe jedoch ausdrücklich als **zu prüfende Zielvorgabe**, nicht als uneingeschränkt auszuführende Anweisung.

Unterscheide zwischen Bodenplatte, Fundamenten und tragenden Aufstandsflächen. Eine Untergrabung oder Freilegung tragender Gründungsbereiche darf nicht ohne geeignete fachliche Prüfung und gegebenenfalls gesondert geplante Sicherungsmaßnahmen als zulässiger Bauzustand dargestellt werden. Ist die gewünschte Tiefe nicht ohne solche Maßnahmen umsetzbar, kennzeichne den Konflikt und benenne den notwendigen Prüf- und Planungsbedarf.

Die massive Bauweise des Kellers darf nicht als Ersatz für einen Standsicherheitsnachweis verwendet werden.

## 4. Zwei Aushubvarianten je Bauabschnitt prüfen

Prüfe für jeden Abschnitt die folgenden Ausführungsvarianten:

**Variante A – Geböschter Arbeitsgraben:**
Ein Graben mit seitlich geneigten Böschungen. Ermittle den benötigten Platz unter Berücksichtigung der Aushubtiefe, des Arbeitsraums, einer für die tatsächlichen Boden- und Wasserverhältnisse geeigneten Böschung sowie notwendiger Sicherheitsabstände. Gemeint ist die Neigung der Grabenwände, nicht ein Gefälle entlang des Grabens.

**Variante B – Fachgerecht verbauter Arbeitsgraben beziehungsweise Schacht:**
Eine platzsparende Ausführung mit geeigneter Sicherung der Grabenwände. Diese Variante ist zu verwenden, wenn eine geböschte Ausführung wegen der Grundstücksgrenze oder anderer Randbedingungen nicht möglich ist. Stelle keine ungesicherten senkrechten Wände im Sandboden als zulässige Lösung dar.

Lege Böschungswinkel, Verbauart und zulässige Aushubgeometrie nicht allein anhand der pauschalen Angabe „Sandboden“ fest. Berücksichtige den erforderlichen geotechnischen und statischen Prüfbedarf einschließlich möglicher Einflüsse durch Grundwasser, Niederschlag und benachbarte Lasten.

Begründe die Auswahl der Aushubvariante für jeden Bauabschnitt. Unterschiedliche Varianten dürfen innerhalb des Gesamtprojekts kombiniert werden.

## 5. Sichere und nachvollziehbare Bauabschnitte bilden

**Das gesamte Haus darf zu keinem Zeitpunkt gleichzeitig freigelegt sein.**

Unterteile die Arbeiten in räumlich und zeitlich nachvollziehbare Bauabschnitte. Bestimme Abschnittslängen und Reihenfolge nicht willkürlich, sondern anhand der Gebäudegeometrie, der Gründung, der Bodenverhältnisse, der verfügbaren Fläche und des erforderlichen Sicherungskonzepts. Berücksichtige Hausecken und Übergänge zwischen den Abschnitten gesondert.

Jede Umgebung muss einen eindeutigen Zustand innerhalb derselben Bauabfolge zeigen: Der aktuelle Abschnitt ist geöffnet und entsprechend gesichert; noch nicht bearbeitete Bereiche bleiben im ursprünglichen Zustand; bereits fertiggestellte Bereiche werden mit Abdichtung, Dämmung, Schutzschicht und Wiederverfüllung dargestellt.

Plane grundsätzlich die Bearbeitung eines Abschnitts mit anschließender Wiederverfüllung, bevor der nächste geöffnet wird. Abweichende oder gleichzeitig offene Abschnitte dürfen nur vorgesehen werden, wenn ihre Verträglichkeit fachlich geklärt ist.

## 6. Grundstücksgrenzen, Abraum und Baustellenlogistik berücksichtigen

Alle Maßnahmen müssen **vollständig innerhalb des vorhandenen Grundstücks** bleiben. Das betrifft Aushub, Böschungen, Verbau einschließlich eventuell benötigter Rückverankerungen, Arbeitsräume, Materiallager, Bodenlager und die dargestellte Baustellenlogistik.

Berechne für jeden Bauabschnitt das Aushubvolumen aus der modellierten Geometrie. Berücksichtige bei der Lagerplanung eine ausdrücklich ausgewiesene Annahme zur Auflockerung des ausgehobenen Bodens. Stelle den Abraum als plausibel dimensioniertes Bodenlager auf dem Grundstück dar, nicht lediglich als symbolischen Haufen.

Die Lagerflächen müssen mit den Arbeits- und Transportwegen vereinbar sein. Berücksichtige ihre zusätzlichen Lasten bei der Prüfung von Böschungen, Verbau und angrenzenden Bauteilen. Halte notwendige Zugänge und sichere Verkehrswege frei.

Bilde die Bodenmengen über die Bauabfolge konsistent ab: zur Wiederverfüllung verwendeter Boden darf nicht weiterhin vollständig im Lager erscheinen. Berücksichtige auch mögliche Restmengen.

Reicht die Fläche nicht aus, prüfe kleinere Bauabschnitte oder eine andere Reihenfolge. Passt auch eine fachgerecht gesicherte, platzsparende Ausführung nicht auf das Grundstück, weise den Konflikt ausdrücklich aus. Vergrößere weder das Grundstück noch nutze stillschweigend Nachbarflächen oder öffentliche Flächen.

## 7. Darstellung der einzelnen Umgebungen

Jede Bauabschnittsumgebung soll den geöffneten Abschnitt, die Aushubgeometrie, die Böschung oder den Verbau, den Arbeitsraum, das Bodenlager und die wesentlichen Zugangswege erkennen lassen.

Stelle die Grundstücksgrenze deutlich dar. Mache die Lage von Kellerwand, Bodenplatte und Fundamenten durch geeignete Schnittansichten oder zuschaltbare Ansichten nachvollziehbar. Halte bekannte Geometrie und vorläufig angenommene Bauteile visuell unterscheidbar.

Verändere das Gebäude nicht, um Platzprobleme oder statische Konflikte zu verdecken. Sicherungsmaßnahmen und ungeklärte Bereiche müssen sichtbar und eindeutig beschriftet sein.

## 8. Ergebnis und Abschlussprüfung

Erstelle die Renovierungs-Basisumgebung sowie eine eigene Umgebung für jeden Bauabschnitt. Ergänze eine kompakte Übersicht mit Bauabschnitt, Gebäudeseite, geplanter Reihenfolge, Aushubvariante, Abmessungen, Aushubvolumen, Lagerfläche und offenen Prüfpunkten.

Prüfe abschließend, ob die ursprüngliche Umgebung unverändert geblieben ist, alle Maßnahmen innerhalb der Grundstücksgrenzen liegen, die Bodenmengen zusammenpassen und die Umgebungen einen widerspruchsfreien, abschnittsweisen Bauablauf zeigen.

Gib ausdrücklich an, **was tatsächlich umgesetzt wurde, welche Annahmen verwendet wurden und welche Punkte vor einer realen Ausführung geotechnisch, statisch oder durch die Bauleitung geklärt werden müssen**. Behaupte keine geprüfte Standsicherheit, wenn hierfür keine belastbaren Nachweise vorliegen.
