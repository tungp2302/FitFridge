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

Scope (SE-Version):
    Diese Version enthaelt nur die Core-Funktionalitaet:
    - Kuehlschrank (Produkte ueber Open Food Facts suchen, anlegen, bearbeiten,
      verbrauchen/auffuellen)
    - Mahlzeiten-Tracker (Tagesziel, Makroverteilung, Mahlzeiten loggen)

    Die AI-Funktionen (AI-Schaetzung, Rezeptplaner, LLM-Einstellungen) gehoeren
    zur ASaai-Version und sind hier nicht enthalten.

Seiten:
    Kuehlschrank:        http://127.0.0.1:5000/
    Produkt hinzufuegen: http://127.0.0.1:5000/fridge/add
    Mahlzeiten-Tracker:  http://127.0.0.1:5000/meal-tracker

Demo data:
    python scripts/seed_demo.py
    Login: demo / demo
    Opens a repeatable fridge with sample products, meal entries, and forecast data.
