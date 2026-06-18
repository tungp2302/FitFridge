# FitFridge

Projekt für Software Engineering / ASAAI SoSe26.

Eine Flask-App zum Tracken von Kühlschrank-Inhalten und Mahlzeiten, mit
optionalen lokalen LLM-Funktionen (KI-Nährwertschätzung + Freestyle-
Rezeptplaner) über Ollama.

---

## 1. App starten

### Windows (PowerShell)

```powershell
# im Projektordner
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

flask --app flaskr_new run --debug
```

### macOS / Linux (bash/zsh)

```bash
# im Projektordner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

flask --app flaskr_new run --debug
```

Dann im Browser öffnen: http://127.0.0.1:5000

Die App legt fehlende Datenbank-Tabellen beim Start automatisch an, ein
Init-Schritt ist für den normalen Betrieb nicht nötig.

---

## 2. Demo-Konto

Legt einen wiederholbaren Kühlschrank mit Beispielprodukten und
Mahlzeiten-Einträgen an:

```bash
python scripts/seed_demo.py
```

Login: **demo / demo**

---

## 3. Datenbank zurücksetzen (optional)

Löscht alle Daten und legt alle Tabellen neu an:

```bash
flask --app flaskr_new init-db
```

---

## 4. Ollama (lokale LLM-Funktionen)

Diese beiden Funktionen brauchen eine laufende Ollama-Instanz:

- **Lebensmittel hinzufügen → KI-Schätzung** — http://127.0.0.1:5000/fridge/add
- **Freestyle-Rezeptplaner** — http://127.0.0.1:5000/asaai/ui/planner

### Installieren & Modell laden

1. Ollama von https://ollama.com installieren (startet einen lokalen Dienst
   auf `127.0.0.1:11434`).
2. Mindestens ein Modell laden:

   ```bash
   ollama pull qwen3.5:latest   # Desktop-Standard
   ollama pull qwen3:4b         # Laptop, langsamer
   ollama pull gemma3:1b        # Laptop, schnell
   ```

3. Smoke-Test, ob der Dienst antwortet:

   ```bash
   curl http://127.0.0.1:11434/api/tags
   ```

### Flask auf Ollama zeigen lassen (optional — Standardwerte passen direkt)

Die App nutzt standardmäßig `http://127.0.0.1:11434` und `qwen3.5:latest`
und fällt sonst auf das erste lokal installierte Modell zurück. Mit
Umgebungsvariablen vor dem Start von Flask überschreiben:

**Windows (PowerShell)**

```powershell
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL    = "qwen3:4b"
flask --app flaskr_new run --debug
```

**macOS / Linux**

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen3:4b
flask --app flaskr_new run --debug
```

### Modell im Browser wählen

http://127.0.0.1:5000/settings — Modell auswählen und mit **Test LLM**
prüfen, ob es antwortet. Auswahl: `qwen3.5:latest` (Desktop), `qwen3:4b`
(Laptop), `gemma3:1b` (schnell).

Der aktive Rezept-LLM-Code liegt in `flaskr_new/asaai/freestyle_recipe.py`.

---

## 5. Tests

```bash
pip install -r requirements-dev.txt   # requirements.txt + pytest

python -m pytest -q                                   # alle Tests
python -m pytest tests/test_api_db/test_api_db.py -q  # einzelne Datei
```

---

## Fehlerbehebung

**VS Code: "Flask not available in the active interpreter"** — den
`.venv`-Interpreter auswählen: Command Palette → *Python: Select
Interpreter* → `.venv` wählen, danach *Developer: Reload Window*.

**KI-Funktionen hängen oder geben Fehler** — prüfen, ob Ollama läuft
(`curl http://127.0.0.1:11434/api/tags`) und ob das gewählte Modell geladen
ist (`ollama list`).
