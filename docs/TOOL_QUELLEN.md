# Externe Werkzeugdokumentation

Online geprüft am 31.10.2026. Diese Quellen betreffen ausschließlich Repository/Codex/Git-Workflow, keine zusätzliche Haus- oder Baugrundplanung.

- OpenAI: Custom instructions with AGENTS.md. https://developers.openai.com/codex/guides/agents-md (Weiterleitung zur offiziellen ChatGPT-Dokumentation). Repository-Regeln werden über AGENTS.md bereitgestellt.
- OpenAI: Iterating Development Workflows with Codex. https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex – AGENTS.md ist die erkannte Konvention; andere Übergabedateien sind Projektkonventionen, nicht automatisch spezielle Codex-Dateien.
- OpenAI: Using Codex Cloud. https://help.openai.com/en/articles/20001545-using-codex-cloud – Cloud-Aufgaben benötigen ihre bereitgestellte Umgebung; kein lokales NX impliziert.
- GitHub: About large files on GitHub. https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github – Browserlimit 25 MiB je Datei, reguläres Git-Limit 100 MiB je Datei; größere Objekte benötigen Git LFS.
- GitHub: Building and testing Python. https://docs.github.com/en/actions/tutorials/build-and-test-code/python – Python-Setup und Workflowbeispiele. Der beiliegende Workflow verwendet checkout@v6 und setup-python@v5 entsprechend dem abgerufenen Beispiel.

Keine API-Schlüssel, Abonnements, Modellnamen oder automatischen Schreibberechtigungen werden in diesem Repository konfiguriert. Ein lokaler `scripts/setup_codex.sh` ist nur ein bewusst auswählbarer Befehl; er wird nicht als automatisch vom Produkt erkannter Dateiname behauptet.
