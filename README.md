# FitFridge

Projekt für Software Engineering (SoSe 2026).

FitFridge ist ein digitaler Kühlschrank mit Mahlzeiten-Tracker. 
Man legt
Lebensmittel per **Barcode oder Name** an – die Nährwerte kommen automatisch von
**Open Food Facts**. Der Bestand lässt sich verbrauchen/auffüllen, und Mahlzeiten
werden gegen ein selbst gesetztes **Tagesziel** (Kalorien + Makros) geloggt.

Technik: Python + Flask, SQLite, Jinja2-Templates (HTML/CSS/JS, kein Frontend-
Framework). Open Food Facts wird über die Standardbibliothek (`urllib`) angesprochen
– kein API-Key nötig.

> SE-Version: nur die Core-Funktionalität. Die KI-Teile (AI-Schätzung, Rezeptplaner,
> LLM-Einstellungen) gehören zur ASaai-Version und sind hier **nicht** enthalten.

## Ablauf (so benutzt man die App)

1. **Registrieren / Einloggen** – jeder Nutzer hat seinen eigenen Kühlschrank.
2. **Produkt hinzufügen** (`/fridge/add`): Barcode oder Name eingeben → Treffer aus
   Open Food Facts auswählen → landet mit Nährwerten im Kühlschrank.
3. **Kühlschrank** (`/`): Bestände + hochgerechnete Nährwerte ansehen, bearbeiten,
   **verbrauchen / auffüllen**.
4. **Mahlzeiten-Tracker** (`/meal-tracker`): Tagesziel setzen und Mahlzeiten loggen
   (aus einem Kühlschrank-Item oder per Barcode) – die Tagesübersicht zeigt
   verbraucht vs. übrig.

## Starten und im Browser testen

Im Projektordner ein Terminal öffnen.

```powershell
# 1. Virtuelle Umgebung anlegen und aktivieren
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Linux/macOS: source .venv/bin/activate

# 2. Abhängigkeiten installieren
pip install -r requirements.txt

# 3. Dev-Server starten
flask --app flaskr_new run --debug
```

Dann im Browser öffnen: **http://127.0.0.1:5000**

> Die Datenbank wird beim ersten Start automatisch angelegt (fehlende Tabellen).
> Ein kompletter Reset geht mit `flask --app flaskr_new init-db`.

### Wichtige Seiten

| Seite | URL |
|---|---|
| Kühlschrank (Dashboard) | http://127.0.0.1:5000/ |
| Produkt hinzufügen | http://127.0.0.1:5000/fridge/add |
| Mahlzeiten-Tracker | http://127.0.0.1:5000/meal-tracker |

### Demo-Daten (optional)

Legt einen gefüllten Kühlschrank mit Beispiel-Produkten und Mahlzeiten an:

```powershell
python scripts/seed_demo.py
# Login: demo / demo
```

## Tests

```powershell
pip install -r requirements-dev.txt   # enthält requirements.txt + pytest
python -m pytest -q                    # alle Tests
```

## Flask-Import-Problem in VS Code

Wenn „Flask not available in the active interpreter" erscheint: die `.venv` als
Interpreter wählen – Command Palette → *Python: Select Interpreter* → `.venv`,
danach *Developer: Reload Window*.
