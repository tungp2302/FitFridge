# FitFridge – Technischer Projektbericht (finaler Stand)

**Branch:** `ASaai_final` · **Stand:** 25.06.2026
**Stack:** Python 3.10+, Flask 3, SQLite (stdlib `sqlite3`), `certifi`. Frontend: Server-gerendertes Jinja2 + Vanilla-JS, keine Build-Tools, kein Framework. KI: lokales Ollama (`qwen3.5:latest`).
**Umfang:** ~2.500 Zeilen Python, ~870 Zeilen JS/CSS, ~640 Zeilen Templates, 39 Tests (alle grün).

Der Bericht ist in zwei Teile geteilt:
- **Teil A – SE (Software-Engineering-Kern):** Kühlschrank, Produkte, Mahlzeiten-Tracker, Auth, OpenFoodFacts, DB.
- **Teil B – ASAAI (KI-Rezeptplaner):** Ollama-Anbindung, Freestyle-Rezepte, Validierung/Makro-Reparatur, KI-Nährwertschätzung.

---

## Feature-Überblick (funktional)

### SE-Features (Software-Engineering-Kern)

**1. Konto & Login**
Registrieren, Anmelden, Abmelden. Passwörter werden gehasht (Werkzeug) gespeichert; jede Aktion ist auf den eigenen Account beschränkt (kein Zugriff auf fremde Daten). Demo-Zugang: `demo` / `demo`.

**2. Kühlschrank-Dashboard**
Übersicht aller Produkte im Kühlschrank mit Marke, Menge und **berechneten Nährwerten je Posten** sowie **Gesamtsummen** (kcal, Protein, Carbs, Fett, Anzahl). Live aus den hinterlegten /100g-Werten und der aktuellen Menge gerechnet.

**3. Produkt hinzufügen — drei Wege**
- **Barcode scannen (Kamera):** native `BarcodeDetector`-API, Fallback auf `zxing-wasm`; mit Kontrastverbesserung und Autofokus für zuverlässige Erkennung (Handy & Desktop).
- **Suche (Barcode oder Name):** kombiniert lokale DB **und** OpenFoodFacts-Online-Suche, nach Relevanz sortiert, dedupliziert.
- **KI-Nährwertschätzung:** zu einem Suchbegriff schätzt das lokale LLM die Nährwerte pro 100 g und bietet sie als ersten Treffer an (für Lebensmittel ohne Barcode/OFF-Eintrag).

**4. Mengenbearbeitung**
Aktuelle Menge eines Postens direkt ändern; unterstützte Einheiten **g, ml, kg, cl, l und Stück (stk)**. Bei Stück wird über **Gramm-pro-Stück** korrekt in Nährwerte umgerechnet (z. B. „1 Ei = 60 g"). Ungültige Eingaben sind ein No-op statt Fehler.

**5. Produkt löschen**
Posten aus dem Kühlschrank entfernen (nur eigene).

**6. Mahlzeiten-Tracker**
- **Tagesansicht:** Konsum des gewählten Tags gegen das **Tagesziel** (kcal + Makroverteilung), inkl. „noch übrig"-Werten.
- **Warenkorb-Logik:** Mahlzeiten werden zusammengestellt aus **Kühlschrank-Posten** (Bestand wird automatisch abgezogen) **oder** aus der **Produktsuche**; bei der Produktsuche kann ein **Rest** angegeben werden, der dann als neuer Kühlschrank-Eintrag landet. Sammeln, dann gemeinsam buchen.
- **Mahlzeit bearbeiten/löschen:** Menge ändern skaliert **alle Makros proportional**; Eintrag löschen.

**7. Kalender**
Monatsraster (Vor/Zurück blättern). Tage mit Einträgen sind **markiert**; ein Klick wählt den Tag aus und zeigt dessen Mahlzeiten und Tagesbilanz. So ist auch die Vergangenheit einsehbar.

**8. Einstellungen**
Tagesziel (kcal) und Makroverteilung (Protein/Carbs/Fett %, automatisch auf 100 % normalisiert); Auswahl des LLM-Modells inkl. „LLM testen"-Button.

### ASAAI-Features (KI-Rezeptplaner)

**1. Freestyle-Rezepte aus dem Kühlschrank**
Auf Knopfdruck erzeugt das lokale LLM mehrere realistisch kochbare Rezepte **nur aus den vorhandenen Zutaten** (plus erlaubte Basics wie Öl/Salz/Gewürze). Mehrere unterschiedliche Vorschläge pro Lauf.

**2. Zielwerte & Rezeptart**
Vorgabe von **kcal, Protein, Carbs, Fett** und **Rezeptart** (Frühstück, Hauptspeise, Abendessen, Nachspeise, Snack). Die Rezeptart steuert die Logik mit (z. B. süß ohne Fleisch/Fisch, herzhaft mit Protein+Stärke).

**3. Makro-genaue Rezepte (Kernstärke)**
Das Backend **vertraut den Modellzahlen nicht**: Nährwerte werden **selbst aus den Gramm-Mengen × /100g-Werten** berechnet. Liegt ein Rezept außerhalb der Zielbereiche, werden die **Mengen automatisch repariert** (Koordinatenabstieg pro Makro: dichteste Protein-/Carb-/Fettquelle wird angepasst, z. B. Low-Carb → Stärke runter, Fett rauf).

**4. Plausibilitäts-Validierung**
Unsinn wird abgelehnt: keine doppelten Protein-/Stärkequellen, kein Süß-Herzhaft-Mix, Supplement-/Whey-Regeln, Titel-Zutaten-Konsistenz, realistische Portionsgrößen, Mindest-Schrittzahl. Ungültiges wird mit konkretem Feedback **nachgefordert** (Retry-Schleife).

**5. Schnelles, gestaffeltes Laden**
Erst **ein** Vorschlag sofort, dann **zwei weitere** im Hintergrund — die UI bleibt reaktionsschnell.

**6. Rezepte speichern, umbenennen, löschen**
Vorschläge werden pro Nutzer gespeichert, umbenennbar (ohne den Rezept-Datensatz anzufassen) und löschbar.

**7. KI-Nährwertschätzung** *(auch im SE-Add genutzt)*
Schätzt Nährwerte für beliebige Lebensmittel ohne DB-/OFF-Eintrag.

**8. Modellwahl & Robustheit**
Mehrere Ollama-Modelle wählbar (Desktop 9B / Laptop 4B / schnell 1B), pro Modell eigene Token-/Zutaten-Profile. Sauberes Degradieren: leerer Kühlschrank, LLM offline oder „Makro-Kombination nicht erreichbar" liefern verständliche Hinweis-Karten statt Fehler.

---

## 0. Gesamtarchitektur & Ablauf

Schichtenmodell, konsequent durchgezogen:

```
Browser (Jinja2-Templates + Vanilla-JS)
   │  HTML-Forms (SE)            │  fetch/JSON (ASAAI)
   ▼                            ▼
routes.py (Frontend-Blueprint)   asaai/routes_asaai.py (asaai-Blueprint, /asaai/*)
   │                            │
   ▼                            ▼
*_service.py  (Fachlogik)        asaai/freestyle_recipe.py (Orchestrierung)
   │                            │
   ▼                            ▼
*_repo.py     (reines SQL)       asaai/freestyle_recipe_support.py (Parsing/Validierung/Makros)
   │                            │
   ▼                            ▼
db.py (sqlite3-Connection)       asaai/ollama_client.py (HTTP zu Ollama)
   │
schema.sql + seed.py
```

**Trennung:** `*_repo.py` = nur SQL, `*_service.py` = Geschäftslogik, `routes.py` = HTTP/Templating. Externe Dienste (OpenFoodFacts, Ollama) liegen in eigenen Client-Modulen mit reinem `urllib` (keine `requests`-Abhängigkeit).

**Wichtigste Eigenheit (Uni-Setup):** Die DB wird bei **jedem Serverstart** aus `schema.sql` neu aufgebaut (`DROP TABLE … CREATE TABLE …`) und über `seed.py` mit Demo-Daten gefüllt. Daten überleben bewusst **keinen** Neustart, sind zur Laufzeit aber persistent. Login: **demo / demo**.

### App-Bootstrap – `flaskr_new/__init__.py` (35 Z.)
`create_app(test_config=None)` ist die Application-Factory:
1. Konfiguriert `SECRET_KEY="dev"` (signiert Session-Cookies) und `DATABASE` (Pfad in `instance/`).
2. Lädt im Normalbetrieb `instance/config.py` (git-ignored, für Overrides); im Test `test_config`.
3. `db.init_app(app)` registriert `close_db` als Teardown.
4. **`db.init_db()` läuft beim Start** → Schema neu. Außerhalb von Tests zusätzlich `seed.seed_demo_data()`.
5. Registriert zwei Blueprints: `frontend` (SE) und `asaai` (KI, URL-Prefix `/asaai`).

---

# TEIL A — SE (Software-Engineering-Kern)

## A1. Datenbank & Infrastruktur

### `schema.sql` (80 Z.) — API/DB
7 Tabellen, alle mit `DROP TABLE IF EXISTS` am Anfang (Reset bei jedem Start):
- **`user`** — `id, username (UNIQUE), password` (Werkzeug-Hash).
- **`product`** — Stammdaten + Nährwerte pro 100 g: `name, brand, barcode (UNIQUE), kcal/protein/fat/carbs_per_100g, grams_per_piece` (für Stück-Einheiten), `created`.
- **`fridge_item`** — Kühlschrank-Posten: `user_id (FK), product_id (FK), current_amount, unit, created`. *Hinweis:* `user_id` ist **nullable** (für besitzerlose Alt-Items), alle anderen FKs nicht.
- **`meal_tracker_settings`** — Tagesziel pro Nutzer: `user_id (UNIQUE), daily_kcal, protein_pct, carbs_pct, fat_pct`.
- **`meal_tracker_entry`** — geloggte Mahlzeiten: `user_id, meal_name, amount, unit, kcal, protein_g, carbs_g, fat_g, eaten_at`.
- **`saved_recipe`** (ASAAI) — `user_id, title, data (JSON-Blob), created`.
- **`app_settings`** (ASAAI) — `user_id (UNIQUE), llm_model` (Default `qwen3.5:latest`).

### `db.py` (38 Z.) — API/DB
- `get_db()` — öffnet/cached eine `sqlite3`-Connection in Flask-`g`, `row_factory = sqlite3.Row` (Zugriff per Spaltenname), `PARSE_DECLTYPES`.
- `init_db()` — führt `schema.sql` per `executescript` aus.
- `close_db()` — Teardown, schließt die Connection.
- `_now()` — UTC-`datetime` ohne tzinfo (passt zu SQLite `CURRENT_TIMESTAMP`).
- `register_converter("timestamp", …)` — wandelt TIMESTAMP-Spalten zurück in `datetime`.

### `seed.py` (148 Z.)
- `_DEMO_PRODUCTS` — 24 Demo-Produkte, bewusst aufgeteilt in **herzhaft** (Hähnchen, Steak, Reis, Spaghetti, Kartoffeln, Gemüse, Öl) und **süß** (Haferflocken, Banane, Honig, Mandeln, Whey …). Diese Bandbreite ist die Test-Spielwiese für den Rezeptplaner.
- `_DEMO_MEALS` — 3 Beispiel-Mahlzeiten für „heute".
- `seed_demo_data()` — **idempotent** (bricht ab, wenn `demo`-User existiert; wichtig wegen Dev-Reloader). Legt `demo`/`demo` an, befüllt Produkte+Kühlschrank, setzt Tagesziel (2200 kcal, 30/40/30), schreibt heutige Mahlzeiten **und einen Tag vor 3 Tagen** (damit die Kalender-Historie testbar ist).

### `calculations.py` (41 Z.) — Backend-Kernhelfer
- `_TO_BASE` — Einheiten-Faktoren auf Basis g/ml (`mg, g, kg, ml, cl, l`); Volumen wird vereinfachend 1 ml = 1 g behandelt.
- `calculate_for_amount(product, amount, unit)` — rechnet die Nährwerte einer konkreten Menge aus. `stk` → über `grams_per_piece`; bekannte Einheit → über `_TO_BASE`; sonst Nullen. Robust gegen `None`/≤0.
- `safe_float(value, default=None)` — toleranter Float-Parser (akzeptiert Komma als Dezimaltrennzeichen, fängt `None`/`""`/Fehler ab). **Wird im ganzen Projekt als Schutz an Eingaberändern benutzt.**

## A2. Produkte & Kühlschrank (Backend)

### `product_repo.py` (39 Z.) — reines SQL
- `get_by_barcode(barcode)` — Produkt per Barcode (UNIQUE).
- `create_product(...)` — neues Produkt anlegen, gibt `lastrowid`.
- `update_grams_per_piece(product_id, gpp)` — Gramm-pro-Stück nachtragen.
- `search_by_name(query, limit=10)` — lokale Suche per `LIKE` über `name`/`brand`.

### `fridge_repo.py` (68 Z.) — reines SQL
- `_FRIDGE_ITEM_SELECT` — JOIN `fridge_item × product`, liefert Posten **mit** Produktdetails.
- `list_items(user_id)` — alle Kühlschrank-Posten eines Nutzers (neueste zuerst).
- `get_item(item_id, user_id=None)` — **sicherheitsrelevant:** mit `user_id` werden nur eigene oder besitzerlose (`user_id IS NULL`) Items gefunden, nie fremde.
- `add_item / update_amount / delete_item` — CRUD; `delete_item` ist optional user-gescoped.

### `fridge_service.py` (95 Z.) — Fachlogik
- `_resolve_or_create_product(data, fallback_barcode)` — findet Produkt per Barcode oder legt es an. Barcode-lose Items (z. B. KI-Schätzungen) werden **unter ihrem Namen als Barcode** gespeichert → erneutes Hinzufügen findet den Eintrag wieder statt an UNIQUE zu scheitern. Fängt zusätzlich `IntegrityError` ab (Race/Doppel-Insert).
- `create_dashboard_item(query, author_id)` — Query (Barcode/Name) → OpenFoodFacts-Lookup → Kühlschrank. Menge aus geparster Packungsgröße (`total_amount`/`unit`), Fallback 100 g.
- `create_dashboard_item_from_data(data, author_id)` — wenn der Nutzer im Frontend bereits einen Treffer ausgewählt hat (Payload).
- `update_dashboard_item(...)` — Menge/`grams_per_piece` ändern, **user-gescoped**; leere/ungültige Menge ist No-op statt 500er.
- `calculate_total_nutrition(item)` — `calculate_for_amount` auf `current_amount`, Keys mit `total_`-Präfix (für die Dashboard-Summen).

## A3. Mahlzeiten-Tracker (Backend)

### `meal_tracker_repo.py` (135 Z.) — SQL
- `DEFAULT_SETTINGS` — 2000 kcal, 30/40/30.
- `get_settings / save_settings` — `save_settings` nutzt **UPSERT** (`ON CONFLICT(user_id) DO UPDATE`).
- `add_meal_entry(...)` — Mahlzeit loggen.
- `update_meal_entry_amount(entry_id, user_id, new_amount)` — skaliert **alle Makros proportional** zur neuen Menge (`factor = new/old`), user-gescoped.
- `delete_meal_entry` — user-gescoped, gibt `bool`.
- `get_tracked_days(user_id, year, month)` — Tage mit ≥1 Mahlzeit (für Kalenderpunkte), via `strftime(..., 'localtime')`.
- `get_day_meals / get_day_totals` — Tagesliste bzw. `SUM`-Aggregat (mit `COALESCE`, damit leere Tage 0 liefern).

### `meal_tracker_service.py` (155 Z.) — Fachlogik
- `normalize_macro_percentages(p, c, f)` — skaliert Protein/Carbs/Fett-Prozente immer auf Summe **100 %** (Rundungsdifferenz landet auf Fett); fällt bei Unsinn auf Defaults zurück.
- `calculate_macro_targets(kcal, p%, c%, f%)` — rechnet kcal-Verteilung in **Gramm** um (Protein/Carbs ÷4, Fett ÷9 kcal/g).
- `build_daily_summary(settings, consumed)` — liefert `{targets, remaining}` für die Tagesansicht.
- `log_meal_from_product(user_id, product, amount, unit, fridge_item_id=None)` — loggt Mahlzeit **und zieht** bei Herkunft aus dem Kühlschrank die Menge vom Bestand ab.
- `save_settings_action(user_id, form)` — Formular → normalisierte Settings speichern.
- `commit_meal_cart(user_id, cart)` — verarbeitet den Session-Warenkorb: Fridge-Posten werden abgezogen, Produkt-**Reste** (`remaining_amount`) wandern als neuer Kühlschrank-Eintrag rein. Liefert eine Status-Meldung.

## A4. OpenFoodFacts-Client — `openfoodfacts_client.py` (221 Z.)

Reiner `urllib`-Client mit `certifi`-CA-Bundle (HTTPS auch auf macOS/Servern ohne System-Truststore).
- `_normalize_text` / `_score_off_product` / `_rank_off_products` — Text-Normalisierung (ASCII-Falten, Kleinschreibung) und **Relevanz-Ranking** (exakt 60, enthält 35, Teilwort 15; Tiebreak nach Protein/kcal).
- `_parse_total_quantity(product)` — extrahiert Packungsmenge aus Freitext: behandelt `"400 g"`, `"2 x 250 g"`, `"4x100g"` (Multiplikator), normalisiert Einheiten. Robuste Regex.
- `_kcal_from_nutriments(nutriments)` — kcal pro 100 g: bevorzugt `energy-kcal_*`, fällt sonst auf kJ → kcal (÷4,184) zurück. *(In der aktuellen Working-Copy zu einer Schleife vereinfacht.)*
- `search_product(barcode)` — GET `/api/v2/product/{barcode}.json`; `404`/`status!=1` → `None`, andere Fehler → `RuntimeError`. Mappt auf das interne Result-Dict.
- `lookup_product(query)` — Barcode (nur Ziffern) → `search_product`, sonst Textsuche + Ranking, bester Treffer.
- `search_products(query, limit=10)` — Textsuche liefert nur Barcodes → für jeden Treffer Detail nachladen; schluckt Netzfehler (loggt + leere Liste), Ergebnis gerankt.

## A5. Frontend (SE) — Routen, Templates, JS

### `routes.py` (405 Z.) — Frontend-Blueprint
- `login_required` (Decorator) + `load_logged_in_user` (`before_app_request`, setzt `g.user` aus der Session).
- `_form_value(name, cast)` — sicheres Form-Parsing.
- **`/` `dashboard`** (GET/POST) — POST aktualisiert eine Menge; GET listet Kühlschrank mit `calculate_total_nutrition` je Posten + Gesamtsummen (kcal/Protein/Carbs/Fett/Anzahl).
- **`/settings`** — LLM-Modell wählen + „LLM testen" (ruft `test_ollama_model`). Validiert gegen erlaubte Modelle.
- **`/meal-tracker`** (GET/POST) — größte Route. POST-Actions: `delete_meal`, `edit_meal_amount`, `save_settings`, `cart_commit`, `cart_add_fridge`, `cart_add_product`, `cart_remove` (Warenkorb in der Session). GET rendert **einen Tag** (Default heute) inkl. **stdlib-Kalender** (`calendar.monthrange`), Tagesübersicht, Such-/Add-Modal.
- **`/fridge/add`** — Suche (Barcode/Name) → Treffer auswählen → in den Kühlschrank.
- `unified_search(q)` — **vereint drei Quellen:** KI-Schätzung (`estimate_food`, ASAAI), lokale Produkte (`search_by_name`) und OpenFoodFacts (`search_products`), dedupliziert per Barcode. Vereinheitlicht über `_to_result` / `_RESULT_KEYS`.
- **`/fridge/<id>/delete`**, **`/auth/register`**, **`/auth/login`**, **`/auth/logout`** — CRUD/Auth mit Werkzeug-Passwort-Hashing.

### Templates (Jinja2)
- `base.html` — Layout: Sidebar-Navigation (Kühlschrank, Mahlzeiten, Rezeptplaner, Einstellungen), Login/Logout-Status, Flash-Messages, lädt `style.css` + `barcode_scan.js`.
- `fridge/dashboard.html` (80) — Kühlschrank-Tabelle, Mengen ändern/löschen, Nährwert-Summen.
- `fridge/add_product.html` (55) + `fridge/_add_modal.html` (121) — Such- & Auswahl-UI, gemeinsam mit dem Tracker genutzt.
- `fridge/meal_tracker.html` (118) — Tagesziel, Konsum vs. Rest, Mahlzeitenliste, Kalender, Add/Settings-Modal.
- `fridge/_settings_modal.html`, `settings.html` — Tagesziel-/LLM-Einstellungen.
- `auth/login.html`, `auth/register.html`, `auth/_form.html` — Auth-Formulare.

### `static/barcode_scan.js` (130 Z.) — Kamera-Barcode-Scanner
- Nutzt die native **`BarcodeDetector`-API** (Android/macOS) und fällt sonst auf **`zxing-wasm`** per ESM-Import zurück (Windows-Desktop, Firefox, iOS).
- `enhanceContrast` — Graustufen + Auto-Level-Kontrast (1 %-Clipping gegen Glanz) zur besseren Erkennung.
- `detectFrame` — analysiert nur das mittlere Bild-Band (1D-Codes sind breit).
- `startBarcodeScan(onResult)` — baut Overlay, öffnet Rückkamera in hoher Auflösung, erzwingt Autofokus, pollt Frames bis ein Code erkannt wird.

### `static/style.css` (508 Z.)
Komplettes handgeschriebenes Stylesheet (App-Shell, Sidebar, Karten, Modals, Planner-Layout, Scanner-Overlay). Keine CSS-Frameworks.

---

# TEIL B — ASAAI (KI-Rezeptplaner)

Eigener Blueprint unter `/asaai`, **JSON-API** (kein Server-Rendering außer der Planner-Seite). Kern: ein lokales LLM erzeugt Rezepte aus den Kühlschrank-Zutaten; das Backend **vertraut den Modellzahlen nicht**, sondern validiert hart und **rechnet die Nährwerte selbst** aus den Gramm-Mengen.

## B1. Ollama-Anbindung — `asaai/ollama_client.py` (143 Z.)

- `DEFAULT_OLLAMA_BASE_URL` = `http://127.0.0.1:11434`, `DEFAULT_OLLAMA_MODEL` = `qwen3.5:latest`.
- `OLLAMA_MODEL_CHOICES` — 3 wählbare Modelle (qwen3.5 9B / qwen3 4B / gemma3 1B).
- `resolve_ollama_model(model)` — Reihenfolge: expliziter Parameter → **gespeicherte User-Einstellung** → env `OLLAMA_MODEL` → `None`.
- `_stored_ollama_model()` — liest das Modell aus `app_settings` (nur bei App-Kontext + eingeloggtem User).
- `_http_json(url, payload, timeout)` — minimaler GET/POST-JSON-Helfer über `urllib`.
- `_local_model_names(endpoint)` — `GET /api/tags` → installierte Modelle.
- `test_ollama_model(...)` — prüft, ob das Modell **installiert** ist und im **JSON-Modus** brauchbar antwortet (für den „LLM testen"-Button in den Einstellungen).
- `generate_from_ollama(prompt, model, …, num_predict, format_json, temperature)` — Kernaufruf an `POST /api/generate` (`stream=False`, `think=False`, `format:"json"` optional). Modell-Fallback auf erstes installiertes, sonst Default.

## B2. KI-Nährwertschätzung — `asaai/food_estimate.py` (51 Z.)

- `estimate_food(query)` — schätzt Nährwerte pro 100 g für einen Suchbegriff via Ollama (JSON-Prompt) und liefert ein Result-Dict **im selben Format wie OpenFoodFacts** → erscheint als erster Treffer in `unified_search` (Brand `"KI-Schätzung"`, leerer Barcode). Schluckt jeden Fehler und gibt dann `None` (degradiert sauber).

## B3. App-Settings-Repo — `asaai/app_settings_repo.py` (29 Z.)

- `get_settings(user_id)` — gewähltes LLM-Modell (Default `qwen3.5:latest`).
- `save_settings(user_id, *, llm_model)` — UPSERT auf `app_settings`.

## B4. HTTP-API — `asaai/routes_asaai.py` (134 Z.)

- `require_user` (Decorator) — gibt bei fehlendem Login **401-JSON** statt Redirect (API-tauglich).
- `_current_fridge_items()` — Kühlschrank des Users als Dict-Liste (schluckt DB-Fehler → `[]`).
- `_selected_ollama_model(data)` — Modell aus Body oder Query.
- **`POST /asaai/recipes/freestyle`** — Hauptendpunkt. Liest `daily_goal`, `recipe_category`, `count` (1–5), `exclude` (bereits gezeigte Titel), reduziert Kühlschrank-Posten auf die nährwertrelevanten Felder und ruft `generate_freestyle_recipes(...)`.
- **`GET/POST /asaai/recipes/saved`** — eigene Rezepte listen / speichern (JSON-Blob + separate `title`-Spalte → Umbenennen ohne den Blob anzufassen).
- **`DELETE/PATCH /asaai/recipes/saved/<id>`** — löschen / umbenennen (user-gescoped).
- **`GET /asaai/ui/planner`** — rendert die Planner-Seite.

## B5. Orchestrierung — `asaai/freestyle_recipe.py` (313 Z.)

Baut den Prompt, ruft Ollama mit Retry-Schleife, lässt validieren/reparieren.

- `DEFAULT_PROFILE` / `MODEL_PROFILES` — pro Modell `num_predict` und `max_items` (kleinere Modelle bekommen weniger Tokens/Zutaten). `_profile(model)` wählt es aus.
- `_SCHEMA` — exakte JSON-Zielstruktur (title, ingredients, fridge_ingredients mit `id`/`amount_g`, instructions, estimated_macros, …).
- `_goal_hint` / `_exclude_hint` — bauen Zielwert- und Ausschluss-Hinweise in den Prompt.
- `_macro_strategy_hint(fridge_items, daily_goal, category)` — **das Herz der Prompt-Steuerung:** analysiert die echten Kühlschrank-Nährwerte und gibt konkrete Strategie-Hinweise (z. B. „bei Protein-Ziel ≥50 g eher 200–300 g Hauptprotein", „Low-Carb: Stärke runter, Fett rauf", süße Kategorien ohne Fleisch/Fisch, Whey nur in süßen Gerichten).
- `build_prompt(...)` — setzt alles zu einem langen, strikt regulierten deutschen Prompt zusammen (Rezeptlogik, Gerichtsart, Zutatenregeln, Mengen, Konsistenz, Qualität, Nährwerte, Ausgabeformat).
- `_run(...)` — **Ablauf:**
  1. Erster Ollama-Call (`temperature` 0.15 bei count=1, sonst 0.7).
  2. `valid_recipes(...)` validiert die Antwort.
  3. **Retry-Schleife** (bis `count+1` Versuche): fehlende/zu wenige valide Rezepte werden nachgefordert, bereits gefundene Titel ausgeschlossen, mit konkretem `validation_feedback` als Begründung.
- `generate_freestyle_recipes(...)` — Einstieg:
  - leerer Kühlschrank → Hinweis-Rezept,
  - LLM nicht erreichbar → Warn-Rezept,
  - keine treffergenauen Rezepte → unterscheidet „Makro-Kombination nicht erreichbar" vs. „kein valides Rezept".

## B6. Parsing/Validierung/Makros — `asaai/freestyle_recipe_support.py` (454 Z.)

Die komplexeste Datei. Hier wird die Modellantwort gegen Realität geprüft und korrigiert.

**Wissensbasen (Keyword-Listen):** `SUPPLEMENT, SWEET, VEG, STARCH, PROTEIN, MAIN_PROTEIN_GROUPS, MAIN_STARCH_GROUPS, SAVORY_CATS, SWEET_CATS, MEAT_FISH, SUPP_BLOCK/SUPP_OK, ALIASES …` — domänenspezifisch, der Teil, der mit neuen Modellen/Zutaten am ehesten nachjustiert werden muss.

**Helfer:** `normalize` (Umlaut-Falten), `has_term` (wort-/teilstring-genau), `is_supplement/is_savory_category/is_sweet_category`, `numbered_items` (Zutaten durchnummerieren), `item_label` (Label fürs Prompt inkl. `[Supplement]`/`[Nährwerte fehlen]`).

**Parsing:** `extract_recipes(response)` — robustes JSON-Parsing (auch eingebettetes Array/Objekt via Regex). `structured_fridge_ingredients` / `_structured_pantry` — zieht IDs+Gramm-Mengen heraus, baut saubere Labels.

**Makro-Berechnung (Ground Truth):**
- `computed_macros(recipe, fridge_items)` — rechnet kcal/Protein/Fett/Carbs **aus den Gramm-Mengen × /100g-Werten** der Kühlschrank-Produkte (plus Öl-Pauschale aus der Pantry). Das ist die Zahl, die im Frontend angezeigt wird (`macro_source: computed_from_fridge_amounts`).
- `macro_target_ranges(daily_goal)` / `MACRO_TOLERANCES` — leitet erlaubte Bereiche je Makro ab (kcal max +10 %, Protein nur Untergrenze, Fett/Carbs symmetrische Toleranz mit absoluten Floors). `format_ranges` für die Prompt-Anzeige.
- `macros_within_targets(macros, daily_goal)` — prüft die berechneten Makros gegen die Bereiche. *(In der Working-Copy vereinfacht: nutzt jetzt `macro_target_ranges` statt doppelter Toleranzlogik.)*

**Validierung:** `_ids_ok` (nur echte Kühlschrank-IDs), `_amounts_ok` (0 < g ≤ 1200, Supplements ≤ 80 g), `_pantry_amounts_ok` (Salz/Öl-Obergrenzen), `_recipe_conflicts` (kein Doppel-Protein/Doppel-Stärke, kein Süß-Herzhaft-Mix, Supplement-Regeln, Titel-Konsistenz), `_is_valid` bündelt alles + Mindest-Schrittzahl.

**Makro-Reparatur (zentrale Stärke):**
- `_fit_amounts(...)` — wählt pro Makro **eine Hebel-Zutat** (dichteste Protein-/Carb-/Fettquelle) und löst deren Menge per **Koordinatenabstieg** aufs Ziel. Fixt Verhältnisfehler, die reines kcal-Skalieren nicht kann (z. B. Low-Carb: Stärke runter, Fett rauf).
- `_scale_fridge_amounts` / `_set_fridge_amounts` — Mengen skalieren/setzen, Labels neu aufbauen.
- `_repair_macros(...)` — erst `_fit_amounts`, sonst Portion aufs kcal-Ziel skalieren; nur übernehmen, wenn danach valide.

**Ausgabe:** `clean_recipe(...)` — normiert das finale Rezept (Zutaten-Labels, Schritte ≤8, `estimated_macros` aus `computed_macros` oder LLM-Fallback, `macro_source`). `valid_recipes(...)` — Pipeline: extrahieren → reparieren → validieren → deduplizieren → bis `count`. `validation_feedback(...)` — formuliert konkretes Retry-Feedback. `warning_recipe/invalid_recipe_warning/empty_fridge_recipe` — Stub-Rezepte für Fehlerfälle.

## B7. Frontend (ASAAI) — Planner

### `templates/asaai/planner.html` (72 Z.)
Zwei-Spalten-Layout: links Zielwerte (Protein/kcal/Carbs/Fett, Rezeptart-Dropdown, „Freestyle-Rezept"-Button, Vorschlags-Rail, „Gespeichert"-Sektion), rechts Detailansicht + „Rezept speichern". Lädt `planner.js`.

### `static/planner.js` (236 Z.)
- `buildDailyGoal()` / `readGoalValue` — liest die Zielwerte (leere Felder = nicht gesetzt).
- `escHtml` — XSS-Schutz beim Rendern der Modell-Ausgabe.
- `renderDetail` / `cardHtml` / `renderRail` — zeichnet Detailspalte und beide Rails (Vorschläge + Gespeicherte als eine indizierbare Liste).
- **`loadFreestyleRecipe()` — zweistufiger Ablauf:** Phase 1 holt **einen** schnellen Vorschlag (`count:1`) und zeigt ihn sofort; Phase 2 lädt **zwei weitere** im Hintergrund nach (`count:2`, `exclude` der bereits gezeigten Titel), dedupliziert per Titel. `requestToken` verhindert Races bei schnellem Mehrfachklick.
- `loadSavedRecipes / saveCurrentRecipe / renameSaved / deleteSaved` — CRUD gegen `/asaai/recipes/saved` per `fetch`.

---

# Tests (`tests/`, 39 Tests, alle grün)

Aufgeteilt in **`test_backend/`** (Fachlogik) und **`test_api_db/`** (Client/DB). Kein Framework außer pytest, Ollama/OFF werden per `monkeypatch` ersetzt (Tests laufen **offline**). `conftest.py` legt das Repo-Root in `sys.path`, `pytest.ini` setzt `testpaths = tests`.

- **`test_api_db/test_api_db.py`** (4) — OpenFoodFacts: Parsing, Mengen-Multiplikatoren/Einheiten, kcal-aus-kJ-Fallback, Ranking-Stufen.
- **`test_backend/test_freestyle_recipe.py`** (14) — Kern des Rezeptplaners: valide Rezepte, Makros aus Mengen berechnet, zu kleine Portion wird hochskaliert, Doppel-Protein/Stärke wird abgelehnt, Low-Carb-Reparatur per `_fit_amounts`, mehrere Vorschläge aus Array, Top-Up per Retry, leerer Kühlschrank/LLM-Fehler/unbrauchbare Antwort → Warnungen; plus Saved-Recipe-CRUD-Roundtrip inkl. Login-Schutz.
- **`test_backend/test_meal_tracker.py`** (6) — Settings-Normalisierung, Tagessummen/Rest, Abzug vom Kühlschrank, User-Isolation, Mengen-Skalierung, Warenkorb-Reste in den Kühlschrank.
- **`test_backend/test_ollama_client.py`** (5) — Modell-Auflösung (Param/Env), Response-Parsing, kein lokaler Fallback bei explizitem Modell, `test_ollama_model` (Erfolg/Non-JSON).
- **`test_backend/test_app_settings.py`** (5) — Settings-Roundtrip, User-spezifisches Modell, Settings-Seite speichert/testet Modell.
- **`test_backend/test_nutrition_integration.py`** (3) — `calculate_for_amount` Einheiten/Fehlerfälle, `calculate_total_nutrition`.
- **`test_backend/test_product_repo.py`** (2) — Produkt per Barcode finden, Namens-/Brand-Suche.

---

# Live-Test (End-to-End, 25.06.2026)

| Check | Ergebnis |
|---|---|
| Ollama erreichbar, `qwen3.5:latest` installiert | ✅ |
| Flask-Start + `GET /` | ✅ 200 |
| Login `demo`/`demo` | ✅ 302 |
| Rezeptplaner-Seite | ✅ 200 |
| Rezeptgenerierung über echtes LLM | ✅ 200 in 33 s, `macro_source: computed_from_fridge_amounts`, keine Warnung |
| Test-Suite | ✅ 39 passed |

# Starten
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app flaskr_new run --debug
```
Ollama muss laufen, Modell ziehen: `ollama pull qwen3.5:latest`. Tests: `python -m pytest -q`.
