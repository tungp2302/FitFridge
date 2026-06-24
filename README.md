# FitFridge

## Ablauf (so benutzt man die App)

1. Registrieren / Einloggen: Jeder Nutzer hat seinen eigenen Kühlschrank.
2. Produkt hinzufügen (`/fridge/add`): Barcode oder Name eingeben → Treffer aus
   Open Food Facts auswählen → landet mit Nährwerten im Kühlschrank.
3. Kühlschrank (`/`): Menge ändern und löschen.
4. Mahlzeiten-Tracker (`/meal-tracker`): Tagesziel setzen und Mahlzeiten loggen
   (aus einem Kühlschrank-Item oder per Barcode) – die Tagesübersicht zeigt
   verbraucht vs. übrig.

> Die Datenbank wird bei **jedem** Serverstart frisch aus `schema.sql` aufgesetzt
> und automatisch mit Demo-Daten befüllt. **Login: demo / demo.**
> Daten überleben bewusst keinen Neustart, sind zur Laufzeit aber persistent.

### Seiten

- Kühlschrank (Dashboard): http://127.0.0.1:5000/
- Produkt hinzufügen: http://127.0.0.1:5000/fridge/add
- Mahlzeiten-Tracker: http://127.0.0.1:5000/meal-tracker

## Starten

### macOS / Linux

```bash
cd /pfad/zum/FitFridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app flaskr_new run --debug
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app flaskr_new run --debug
```

Dann im Browser öffnen: http://127.0.0.1:5000

## Ollama 

Rezept-Planer und Nährwert-Schätzung laufen über eine **lokale Ollama-Instanz**.

1. **Installieren:** https://ollama.com/download (macOS, Windows, Linux). Nach der
   Installation läuft Ollama als Dienst unter `http://127.0.0.1:11434`.
2. **Mindestens ein Modell laden** (die App bietet diese drei in den Einstellungen an):

   ```bash
   ollama pull gemma3:1b        # klein/schnell – zum Testen empfohlen
   ollama pull qwen3:4b         # Mittelklasse (Laptop)
   ollama pull qwen3.5:latest   # Standard, beste Qualität (Desktop, ~9B)
   ```

3. **Prüfen, dass Ollama läuft:**

   ```bash
   ollama list                  # zeigt die installierten Modelle
   ```

4. In der App unter **Einstellungen** das gewünschte Modell wählen und mit
   "LLM testen" prüfen.

> Standardmodell ist `qwen3.5:latest`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Einzelne Datei:

```bash
python -m pytest tests/test_backend/test_meal_tracker.py
```

Ohne aktivierte venv direkt aufrufen:

```bash
# macOS / Linux
.venv/bin/python -m pytest -q
# Windows
.\.venv\Scripts\python.exe -m pytest -q
```
