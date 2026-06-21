# FitFridge


## Ablauf (so benutzt man die App)

1. Registrieren / Einloggen: Jeder Nutzer hat seinen eigenen Kühlschrank.
2. Produkt hinzufügen: (`/fridge/add`): Barcode oder Name eingeben → Treffer aus
   Open Food Facts auswählen → landet mit Nährwerten im Kühlschrank.
3. Kühlschrank: (`/`): Bestände + hochgerechnete Nährwerte ansehen, bearbeiten,
   verbrauchen / auffüllen.
4.*Mahlzeiten-Tracker: (`/meal-tracker`): Tagesziel setzen und Mahlzeiten loggen
   (aus einem Kühlschrank-Item oder per Barcode) – die Tagesübersicht zeigt
   verbraucht vs. übrig.

## Starten und im Browser testen
> Die Datenbank wird bei **jedem** Serverstart frisch aus `schema.sql` aufgesetzt
> und automatisch mit Demo-Daten befüllt. **Login: demo / demo.**
> Daten überleben bewusst keinen Neustart, sind zur Laufzeit aber persistent.

### macOS
**Setup (einmalig):**

```bash
# 1. Ins Projektverzeichnis wechseln
cd /pfad/zum/FitFridge

# 2. Virtuelle Umgebung anlegen und aktivieren
python3 -m venv .venv
source .venv/bin/activate

# 3. Abhängigkeiten installieren
pip install -r requirements.txt
```

**Server starten:**

```bash
# Virtuelle Umgebung aktivieren (falls noch nicht aktiv)
source .venv/bin/activate

flask --app flaskr_new run --debug
```

Dann im Browser öffnen: **http://127.0.0.1:5000**

**Tests ausführen:**

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```

---

### Windows (PowerShell)

Im Projektordner ein Terminal öffnen.
```
powershell
# 1. Virtuelle Umgebung anlegen und aktivieren
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Abhängigkeiten installieren
pip install -r requirements.txt

# 3. Dev-Server starten
flask --app flaskr_new run --debug


Dann im Browser öffnen: **http://127.0.0.1:5000**
```

### Seiten
Kühlschrank (Dashboard) http://127.0.0.1:5000/ 
Produkt hinzufügen http://127.0.0.1:5000/fridge/add 
Mahlzeiten-Tracker http://127.0.0.1:5000/meal-tracker 

## Tests (Windows)

powershell
pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest tests/test_backend/test_meal_tracker.py

# Either activate it once per terminal session:
.\.venv\Scripts\Activate.ps1
python -m pytest tests/test_backend/test_meal_tracker.py

# Or call it directly without activating:
.\.venv\Scripts\python.exe -m pytest tests/test_backend/test_meal_tracker.py
