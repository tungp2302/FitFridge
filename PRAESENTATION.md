# FitFridge – Zwischenpräsentation (SE)

**Strukturierte Programmierung / Software Engineering – SoSe 2026**
Stand: Zwischenpräsentation am 15.06.2026

---

## 1. Worum geht es?

FitFridge ist ein digitaler Kühlschrank mit Mahlzeiten-Tracker. Der Nutzer

- legt Lebensmittel über einen **Barcode oder Produktnamen** an (Nährwerte kommen
  automatisch von der **Open-Food-Facts-API**),
- verwaltet die Bestände im **Kühlschrank** (bearbeiten, verbrauchen, auffüllen),
- **trackt seine Mahlzeiten** gegen ein selbst gesetztes Tagesziel (Kalorien + Makros).

> **Abgrenzung SE / ASaai:** Diese Version enthält **nur die Core-Funktionalität**
> (Frontend + Backend + Open-Food-Facts). Alle KI-Funktionen (AI-Schätzung in
> *Add Food*, der Rezeptplaner und die LLM-Einstellungsseite) gehören zur
> ASaai-Version und sind hier **bewusst entfernt**.

---

## 2. Aktueller Stand

| Bereich | Status | Kurz |
|---|---|---|
| Kühlschrank (Dashboard) | ✅ fertig | Produkte anzeigen, anlegen, bearbeiten, löschen |
| Produktsuche über Open Food Facts | ✅ fertig | Barcode-Lookup + Textsuche |
| Verbrauchen / Auffüllen | ✅ fertig | Mengenänderung mit Validierung + Log |
| Mahlzeiten-Tracker | ✅ fertig | Tagesziel, Makroverteilung, Mahlzeiten loggen |
| Nährwert-Berechnung | ✅ fertig | Einheiten-Umrechnung, "pro 100g" → echte Menge |
| Login / Registrierung | ✅ fertig | pro Nutzer getrennte Daten |
| Tests | ✅ 35 grün | `python -m pytest -q` |

Technik: **Python + Flask**, **SQLite** als Datenbank, **Jinja2**-Templates,
reines HTML/CSS/JS im Frontend (kein Framework). Zugriff auf Open Food Facts
über die Standardbibliothek (`urllib`), keine externen API-Keys nötig.

---

## 3. Core-Funktionen (Demo-Reihenfolge)

### a) Produkt über Open Food Facts suchen & hinzufügen
1. Seite **"New Food"** (`/fridge/add`).
2. Eingabe = **Barcode** (nur Ziffern) → direkter Barcode-Lookup,
   oder **Produktname** → Textsuche.
3. Die Treffer werden zur Auswahl angezeigt; ein Klick legt das Produkt
   inklusive Nährwerten und geparster Packungsmenge im Kühlschrank an.
4. Findet die Suche nichts, kann das Produkt per **"Create anyway"** trotzdem
   angelegt werden.

### b) Kühlschrank bearbeiten
- **Dashboard** (`/`): alle Produkte mit aktueller Menge und hochgerechneten
  Nährwerten, plus eine Gesamt-Übersicht (Summe kcal/Protein/Carbs/Fett).
- **Detailseite** (`/fridge/<id>`): Name, Marke, Menge und Einheit ändern.
- **Verbrauchen / Auffüllen**: Menge eingeben → Bestand wird angepasst
  (Verbrauch wird bei 0 abgefangen, jede Änderung landet im Verbrauchs-Log).

### c) Mahlzeiten tracken
- **Tagesziel** setzen: Zielkalorien + prozentuale Makroverteilung
  (Protein/Carbs/Fett werden automatisch auf 100 % normalisiert).
- **Mahlzeit loggen**: aus einem Kühlschrank-Item oder per Barcode-Suche;
  optional wird der Bestand im Kühlschrank direkt reduziert.
- **Tagesübersicht**: verbrauchte vs. verbleibende Kalorien/Makros + kurzer
  Empfehlungstext. Einträge lassen sich nachträglich in der Menge ändern oder löschen.

---

## 4. Architektur – das Schichtenmodell

Der Code ist bewusst in **klare Schichten** getrennt. Das ist der rote Faden
für die ganze Präsentation:

```
  Browser (HTML/CSS/JS, Jinja2-Templates)
        │  HTTP (Formulare + fetch)
        ▼
  routes.py            ← Flask-Routen: nimmt Request entgegen, ruft Service auf,
        │                gibt Template/JSON zurück. Enthält KEINE Fachlogik.
        ▼
  *_service.py         ← Fachlogik: was bedeutet "verbrauchen", "Mahlzeit loggen",
        │                "Nährwerte berechnen". Kennt keine HTTP-Details.
        ▼
  *_repo.py            ← Datenbankzugriff: reine SQL-Funktionen (CRUD).
        │
        ▼
  db.py / SQLite       ← Verbindung + Schema.

  openfoodfacts_client.py  ← externe API (Open Food Facts), eigenständig.
```

**Warum so?** Jede Datei hat *eine* Aufgabe. Routen sind dünn, Logik ist testbar
ohne Webserver, SQL ist an einer Stelle gebündelt. Genau das prüfen auch unsere Tests:
die Service-Funktionen werden direkt aufgerufen, ohne durch HTTP gehen zu müssen.

---

## 5. Die Dateien im Detail (Ablauf & Funktionsweise)

### Einstieg

**`flaskr_new/__init__.py` – `create_app()`**
Die *Application Factory*. Sie konfiguriert Flask, verbindet die Datenbank,
stellt sicher, dass alle Tabellen existieren (`ensure_*_schema`) und
registriert die Routen (Blueprint `frontend`). Beim Start ist die App ohne
manuelles `init-db` lauffähig, weil fehlende Tabellen automatisch angelegt werden.

**`flaskr_new/db.py`**
Verwaltet die SQLite-Verbindung pro Request (`get_db`, `close_db`) und legt mit
`ensure_core_schema()` die Kerntabellen `user`, `product`, `fridge_item` und
`consumption_log` an. `schema.sql` + der Befehl `init-db` dienen dem kompletten Reset.

### Routen (`flaskr_new/routes.py`)

Hier liegen alle URL-Endpunkte. Jede Route ist kurz: Eingaben lesen, passende
Service-Funktion aufrufen, Ergebnis rendern.

- **`dashboard()` (`/`)** – holt die Kühlschrank-Items des Nutzers, rechnet je
  Item die Nährwerte auf die aktuelle Menge hoch und bildet die Tagessumme.
- **`add_product()` (`/fridge/add`)** – legt ein Produkt an: entweder aus einem
  ausgewählten Suchtreffer (`selected_payload`) oder direkt aus der Eingabe.
- **`api_products_search()` (`/api/products/search`)** – die JSON-Suche, die das
  Frontend per `fetch` aufruft. Bei reinen Ziffern → Barcode-Lookup, sonst
  lokale DB-Treffer **plus** Open-Food-Facts-Textsuche, doppelte Barcodes werden
  herausgefiltert. Die kleine Hilfsfunktion `_to_result()` bringt jedes Produkt
  auf die immer gleichen Felder.
- **`product_detail()` (`/fridge/<id>`)** – Anzeige + Bearbeiten eines Items.
- **`consume_product()` / `refill_product()`** – nutzen einen gemeinsamen Helfer
  `_handle_amount_change()`. Die Eingabe-Validierung steckt in
  `_parse_amount_input()` (leer, keine Zahl, ≤ 0, unrealistisch groß → klare
  Fehlermeldung; Komma wird als Dezimaltrennzeichen akzeptiert).
- **`meal_tracker()` (`/meal-tracker`)** – ein Endpunkt für mehrere Aktionen
  (Tagesziel speichern, Mahlzeit loggen, Eintrag löschen/ändern). Die Aktion
  steht im versteckten Feld `action`; jede Aktion ist eine eigene Service-Funktion.
- **`register()` / `login()` / `logout()`** – Authentifizierung mit gehashten
  Passwörtern (`werkzeug.security`). `load_logged_in_user()` lädt vor jedem
  Request den eingeloggten Nutzer nach `g.user`; `@login_required` schützt die
  geschützten Seiten.

### Fachlogik (Services)

**`fridge_service.py`** – Logik rund um den Kühlschrank.
- `create_dashboard_item()` / `..._from_data()`: holt Produktdaten (per
  `lookup_product`) bzw. nimmt einen fertigen Treffer, legt bei Bedarf das
  Produkt an (`_resolve_or_create_product`) und fügt das Kühlschrank-Item hinzu.
- `consume_amount()` / `refill_amount()`: teilen sich `_change_amount()`.
  Edge-Cases (Menge ≤ 0, Item gehört anderem Nutzer, Bestand min. 0) werden hier
  sauber behandelt, jede Änderung wird geloggt, und es kommt eine fertige
  Erfolgs-/Fehlermeldung zurück.
- `calculate_total_nutrition()`: rechnet die "pro 100g"-Werte eines Items auf
  die aktuelle Menge hoch (delegiert an den Nutrition-Service).

**`meal_tracker_service.py`** – Logik des Mahlzeiten-Trackers.
- `calculate_macro_targets()` / `build_daily_summary()`: aus Tagesziel +
  Prozenten die Ziel-Gramm berechnen und mit dem heute Verbrauchten vergleichen.
- `normalize_macro_percentages()`: hält Protein/Carbs/Fett zusammen bei 100 %.
- `track_meal_from_form()` / `track_meals_from_payload()`: eine oder mehrere
  Mahlzeiten loggen; Restmengen können als "übrig" in den Kühlschrank wandern.
- `log_meal_from_product()`: schreibt den Eintrag und reduziert optional den
  Kühlschrank-Bestand.

**`nutrition_service.py` + `calculations.py`** – das Rechen-Herz.
- `convert_units()` rechnet zwischen kompatiblen Einheiten um
  (Gewicht: mg/g/kg, Volumen: ml/cl/l) und wirft bei unsinnigen Kombinationen
  einen Fehler.
- `calculate_for_amount()` rechnet Nährwerte von "pro 100g" auf die echte Menge:
  Menge → Gramm umrechnen, Faktor (`menge/100`) bilden, Werte multiplizieren.
  Nicht umrechenbare Einheiten ("stk") oder ungültige Mengen ergeben sauber 0.

### Datenbankzugriff (Repositories)

Reine SQL-Funktionen, ein Repository pro Tabelle:
- **`product_repo.py`** – Produkte anlegen/suchen (per Barcode, ID, Name).
- **`fridge_repo.py`** – Kühlschrank-Items (Liste mit Produkt-Join, anlegen,
  Menge ändern, löschen). Alle Lese-/Schreibzugriffe sind **auf den Nutzer
  gescoped**, damit niemand fremde Items sieht.
- **`meal_tracker_repo.py`** – Tagesziel-Settings + Mahlzeiten-Einträge,
  inklusive "heutige Summen".
- **`consumption_log_repo.py`** – protokolliert jedes Verbrauchen/Auffüllen.

### Externe API (`openfoodfacts_client.py`)

- `search_product(barcode)` – holt ein Produkt per Barcode von Open Food Facts,
  normalisiert die Nährwerte (auch kJ → kcal) und parst die Packungsmenge
  (`_parse_total_quantity`, z. B. „4 x 100 g" → 400 g).
- `search_products(query)` – Textsuche über die Such-API, dann je Treffer die
  vollen Nährwerte nachladen; Ergebnisse werden nach Namensähnlichkeit sortiert
  (`_rank_off_products`).
- `lookup_product(query)` – die einfache Fassade: Ziffern → Barcode, sonst
  Textsuche; gibt den besten Treffer oder `None` zurück.

### Frontend (`templates/` + `static/style.css`)

- `base.html` – gemeinsames Layout mit Seitenleiste (Navigation:
  **Kühlschrank** und **Mahlzeiten-Tracker**).
- `fridge/dashboard.html`, `fridge/add_product.html`, `fridge/product_detail.html`,
  `fridge/meal_tracker.html`, `auth/login.html`, `auth/register.html`.
- Das JavaScript ist klein und gezielt: in *Add Food* und im Tracker ruft es per
  `fetch` die Suchroute auf und zeigt die Treffer zur Auswahl an. Gerendert wird
  immer über `escHtml(...)`, damit Sonderzeichen in Produktnamen sauber bleiben.

---

## 6. Tests

35 Tests, alle grün (`python -m pytest -q`). Getestet werden u. a.:
- Datenbank-Schema und Produkt-/Kühlschrank-CRUD,
- Open-Food-Facts-Parsing (Mengen, Nährwerte) – mit gemockten Antworten,
  also **ohne echten Netzaufruf**,
- Nährwert-/Einheiten-Berechnung inkl. Edge-Cases,
- Verbrauchen/Auffüllen-Logik,
- Mahlzeiten-Tracker (loggen, Restmenge in den Kühlschrank).

Die Schichtentrennung macht das möglich: Logik wird direkt aufgerufen, externe
Aufrufe werden per Monkeypatch ersetzt.

---

## 7. Wie starte ich das Projekt?

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows
pip install -r requirements.txt

flask --app flaskr_new run --debug   # → http://127.0.0.1:5000
```

Optionale Demo-Daten: `python scripts/seed_demo.py` (Login: `demo` / `demo`).
Tests: `pip install -r requirements-dev.txt` und `python -m pytest -q`.

---

## 8. Nächste Schritte

- UI-Feinschliff (einheitliche Sprache DE/EN, Mobil-Ansicht).
- Mehr Tests für die Frontend-Routen (z. B. Mahlzeit-Flows end-to-end).
- (ASaai-Strang separat) KI-Schätzung und Rezeptplaner.
