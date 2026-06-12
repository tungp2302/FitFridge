Projekt FitFrdge für Strukturierte programmierung SoSe26 
https://flask.palletsprojects.com/en/stable/installation/
Run

flask --app flaskr run --debug
for testing

$ flask --app flaskr init-db
Initialize the database

//
Tutorial zum testen:
1. Im Projektordner das Terminal öffnen. (ist schon)
Umgebung erstellen:  python3 -m venv .venv
Umgebung aktivieren: source .venv/bin/activate   (Windows: .\.venv\Scripts\Activate.ps1)
Dependencies installieren: pip install -r requirements.txt
2. Befehle ausführen
Datenbank initialisieren (optional, fuer kompletten Reset): flask --app flaskr_new init-db
   Hinweis: Die App legt fehlende Tabellen beim Start automatisch an.
dev Server starten: flask --app flaskr_new run --debug

3. Im browser öffnen
http://127.0.0.1:5000

//


For tests nachdem in der Umgebung:
1: dependencies: pip install -r requirements-dev.txt
   (enthaelt requirements.txt + pytest)
2: Tests:
# single test file
python -m pytest tests/test_api_db/test_api_db.py -q

# all tests
python -m pytest -q


Flask import problem in VS Code:
Flask not available in the active interpreter.
Quick fix:
    create a virtual environment: python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install flask click werkzeug pytest requests
    In VS Code select the .venv interpreter:
        Command Palette -> Python: Select Interpreter -> .venv
    Reload Pylance:
        Command Palette -> Developer: Reload Window

Ollama local setup for kept AI features:
1. Install Ollama from https://ollama.com and start the local service.
2. Pull a model, for example:
    ollama pull qwen3.5:latest
    ollama pull qwen3:4b
    ollama pull gemma3:1b
3. Set environment variables before starting Flask:
    export OLLAMA_MODEL=qwen3.5:latest
    export OLLAMA_BASE_URL=http://127.0.0.1:11434
4. Start the app:
    flask --app flaskr_new run --debug
5. Open:
    Add Food with AI estimate:
        http://127.0.0.1:5000/fridge/add
    Freestyle recipe planner:
        http://127.0.0.1:5000/asaai/ui/planner

Model choice:
    Desktop default: qwen3.5:latest
    Laptop slower: qwen3:4b
    Laptop fast: gemma3:1b

    Browser choice:
        http://127.0.0.1:5000/settings

    Terminal / env fallback before starting Flask:
        export OLLAMA_MODEL=qwen3:4b
        export OLLAMA_MODEL=gemma3:1b

Ollama smoke test:
     curl http://127.0.0.1:11434/api/tags

FitFridge keeps only these local Ollama features for the current project scope:
    - Add Food with AI estimate
    - Freestyle recipe in the recipe planner

The active recipe LLM code is in:
    flaskr_new/asaai/freestyle_recipe.py

Demo data:
    python scripts/seed_demo.py
    Login: demo / demo
    Opens a repeatable fridge with sample products, meal entries, and forecast data.
