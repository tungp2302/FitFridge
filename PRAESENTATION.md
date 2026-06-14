

### Anhang — Schnellstart (Backup-Folie)

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app flaskr_new run --debug

# Tests
pip install -r requirements-dev.txt
python -m pytest -q
```

---

# Anhang — Code-Walkthrough (von Hand erklärt)

> Dieser Teil ist zum **Lernen und freien Erklären** gedacht. Er folgt dem Code
> von außen (Browser/Route) nach innen (DB) und erklärt pro Kernfunktion: **Was**
> macht sie, **warum** ist sie so gebaut, **wie** läuft sie ab. Am Ende jeder
> Schicht steht ein Satz, den man im Vortrag sagen kann.

## 0. Das Grundprinzip in einem Satz

Eine HTTP-Anfrage wandert immer durch dieselben Schichten:
**Route (`routes.py`) → Service (`*_service.py`) → Repository (`*_repo.py`) → DB**.
Die Route nimmt nur Eingaben entgegen und rendert die Antwort, die Fachlogik liegt
im Service, die SQL-Befehle stehen im Repository. Externe Daten (Open Food Facts)
kommen aus einer eigenen Datei (`openfoodfacts_client.py`), die nichts von der
Datenbank weiß.

> *So erkläre ich es:* „Jede Datei hat genau eine Aufgabe. Wenn ich eine Anfrage
> verfolge, gehe ich immer dieselbe Treppe hinunter — das macht den Code
> vorhersehbar und testbar."

---

## 1. Durchstich: „Produkt per Barcode hinzufügen"

Konkretes Beispiel quer durch alle Schichten — der rote Faden für die Demo.

1. **Browser** schickt das Formular von `/fridge/add` (Feld `query` = Barcode/Name,
   oder `selected_payload` = ein bereits angeklickter Treffer als JSON).
2. **Route** `add_product()` in [routes.py](flaskr_new/routes.py#L187):
   - prüft, ob überhaupt etwas eingegeben wurde,
   - bei direkter Eingabe → `create_dashboard_item(query, user_id)`,
   - bei Auswahl-Treffer → `create_dashboard_item_from_data(payload, user_id)`,
   - fängt `ValueError`/`RuntimeError`/`JSONDecodeError` ab und zeigt eine Flash-Meldung,
   - bei Erfolg → `redirect` aufs Dashboard.
3. **Service** [fridge_service.create_dashboard_item](flaskr_new/fridge_service.py#L44):
   - holt die Produktdaten über `lookup_product(query)`,
   - reicht sie an den internen Helfer `_add_item_from_product_data` weiter.
4. **OFF-Client** [lookup_product](flaskr_new/openfoodfacts_client.py#L186):
   - sind es nur Ziffern → `search_product(barcode)` (Barcode-API),
   - sonst → `search_products(query)` (Textsuche) und der beste Treffer.
5. **Service** `_resolve_or_create_product`: gibt es das Produkt (per Barcode) schon
   in der DB? → bestehende ID nehmen; sonst `product_repo.create_product(...)`.
6. **Repository** [fridge_repo.add_item](flaskr_new/fridge_repo.py#L38) legt das
   Kühlschrank-Item an (Produkt-ID + Menge + Einheit + `user_id`).
7. **Redirect** → das Dashboard lädt die Liste neu und zeigt das neue Produkt.

> *So erkläre ich es:* „Die Route entscheidet nur *welcher* Weg, der Service macht
> die eigentliche Arbeit, und Produkte werden nie doppelt angelegt — vorhandene
> Barcodes werden wiederverwendet."

---

## 2. Dashboard & Nährwert-Hochrechnung

**Route** [dashboard()](flaskr_new/routes.py#L73): lädt die Items des Nutzers
(`list_dashboard_items`), rechnet für jedes die Nährwerte auf die aktuelle Menge
hoch (`calculate_total_nutrition`) und bildet die Gesamtsummen für die obere
Übersicht.

**Die Rechnung selbst** steckt in zwei kleinen Funktionen:

- [nutrition_service.calculate_for_amount](flaskr_new/nutrition_service.py#L6):
  rechnet die Menge zuerst in Gramm um (Volumen vereinfacht: 1 ml = 1 g),
  bildet den Faktor `Menge / 100` und multipliziert die „pro 100 g"-Werte.
  Bei ungültiger Menge oder nicht umrechenbarer Einheit (`stk`) sind alle Werte 0.
- [calculations.convert_units](flaskr_new/calculations.py#L3): rechnet innerhalb
  einer Kategorie um — Gewicht (mg/g/kg) **oder** Volumen (ml/cl/l). Gewicht ↔
  Volumen wirft bewusst einen `ValueError`.

Beispiel: 30 g Nutella, 539 kcal/100 g → Faktor 0,3 → **161,7 kcal**.

> *So erkläre ich es:* „Nährwerte stehen in der DB immer pro 100 g. Für die echte
> Menge brauche ich nur einen Faktor. Die Umrechnung ist eine eigene Mini-Funktion,
> damit ich sie isoliert testen kann."

---

## 3. Verbrauchen & Auffüllen (Kern-Logik mit einer Funktion)

Beide Aktionen teilen sich eine private Funktion
[_change_amount](flaskr_new/fridge_service.py#L123) mit dem Schalter `consume`:

1. Menge validieren (`> 0`, sonst `success=False`).
2. Item laden — **user-scoped**, also nur eigene Items.
3. Neue Menge berechnen: beim Verbrauchen `max(0, bestand - menge)` (fällt nie unter
   0), beim Auffüllen `bestand + menge`.
4. `fridge_repo.update_amount(...)` schreibt den neuen Stand.
5. Ein Log-Eintrag (`log_consume`/`log_refill`) wird geschrieben — in einem
   `try/except`, damit die Hauptaktion auch dann erfolgreich bleibt, wenn das
   Logging mal scheitert.
6. Rückgabe `{"success", "new_amount", "message"}` → die Route zeigt die Meldung.

Die **Routen** [consume_product](flaskr_new/routes.py#L394) /
[refill_product](flaskr_new/routes.py#L401) sind absichtlich dünn: sie nutzen den
gemeinsamen Helfer `_handle_amount_change`, der die Eingabe mit
`_parse_amount_input` prüft (Komma erlaubt, max. 10000) und dann den Service aufruft.

> *So erkläre ich es:* „Verbrauchen und Auffüllen sind dieselbe Operation mit
> umgekehrtem Vorzeichen — deshalb eine Funktion mit einem Flag statt zweimal
> derselbe Code."

---

## 4. Mahlzeiten-Tracker

**Ein Endpunkt, mehrere Aktionen:** [meal_tracker()](flaskr_new/routes.py#L102)
liest das Formularfeld `action` und verteilt an den passenden Handler im Service
(`save_settings`, `delete_meal`, `edit_meal_amount`, `track_meal`). Danach baut die
Route immer den aktuellen Tagesstand zusammen und rendert die Seite.

Eine Mahlzeit loggen — [track_meal_from_form](flaskr_new/meal_tracker_service.py#L270):
- Quelle ist entweder ein **Fridge-Item** (Produktdaten kommen aus dem Kühlschrank)
  oder ein **Barcode** (`resolve_product_from_barcode` holt/legt das Produkt an).
- dann [log_meal_from_product](flaskr_new/meal_tracker_service.py#L116): rechnet die
  Nährwerte (`calculate_for_amount`), schreibt den Eintrag (`add_meal_entry`) und
  zieht bei einem Fridge-Item die Menge direkt vom Bestand ab.

Tagesziel & Empfehlung:
- [normalize_macro_percentages](flaskr_new/meal_tracker_service.py#L23) zwingt
  Protein/Carbs/Fett-Prozente auf Summe 100 (Rundungsrest landet bei Fett).
- [calculate_macro_targets](flaskr_new/meal_tracker_service.py#L37) rechnet kcal in
  Gramm um (Protein/Carbs = 4 kcal/g, Fett = 9 kcal/g).
- [build_daily_summary](flaskr_new/meal_tracker_service.py#L50) bildet
  Ziel − verbraucht = übrig und formuliert daraus eine kurze Empfehlung.

„Heute" heißt wirklich heute: [get_today_meals](flaskr_new/meal_tracker_repo.py)
filtert auf `eaten_at >= Tagesbeginn`, `get_today_totals` summiert daraus.

> *So erkläre ich es:* „Der Tracker schließt den Kreis: Kühlschrank → Mahlzeit →
> Tagesziel. Ein Formular mit `action`-Feld reicht, weil die ganze Logik in kleinen
> Service-Funktionen liegt."

---

## 5. Open-Food-Facts-Anbindung

Eigenständige Datei [openfoodfacts_client.py](flaskr_new/openfoodfacts_client.py),
ohne DB-Bezug — nur HTTP über die Standardbibliothek (`urllib`), kein API-Key.

- [search_product(barcode)](flaskr_new/openfoodfacts_client.py#L142): Barcode-API,
  normalisiert Name/Marke/Nährwerte; Energie wird bei Bedarf von kJ in kcal
  umgerechnet (`_kcal_from_nutriments`).
- `_parse_total_quantity`: liest die Packungsmenge aus Freitext per Regex, inkl.
  Multiplikator — **„4 x 100 g" → 400 g**, Einheiten werden vereinheitlicht.
- [search_products(query)](flaskr_new/openfoodfacts_client.py#L201): die Suche
  liefert nur Barcodes; für jeden Treffer werden die vollen Nährwerte nachgeladen.
  Fehler werden hier abgefangen → im Fehlerfall eine leere Liste.
- `_rank_off_products` / `_score_off_product`: sortiert Treffer nach Namens-
  Ähnlichkeit zur Eingabe (exakter Treffer > enthält > einzelnes Wort).

> *So erkläre ich es:* „Die OFF-Anbindung ist bewusst getrennt und kennt keine
> Datenbank. Im Test ersetze ich nur diese Funktionen (Mock) — es geht kein echter
> Netzaufruf raus."

---

## 6. Datenbank-Schicht & Sicherheit

- Pro Tabelle ein Repo: `product_repo`, `fridge_repo`, `meal_tracker_repo`,
  `consumption_log_repo` — reine SQL-Funktionen, sonst nichts.
- [db.py](flaskr_new/db.py): eine Verbindung pro Request (`get_db`), beim
  App-Start legt `ensure_core_schema()` die Kerntabellen an, falls sie fehlen;
  `schema.sql` bleibt das Werkzeug für einen kompletten Reset (`flask init-db`).
- **User-Scoping:** Lese-/Schreibzugriffe nehmen eine `user_id` und filtern danach
  (`WHERE f.user_id = ? ...`). So sieht und ändert niemand fremde Items, auch nicht
  über geratene IDs.

> *So erkläre ich es:* „Jede Tabelle hat ihr eigenes kleines Repo. Und jede Abfrage
> ist auf den eingeloggten Nutzer eingeschränkt — Datentrennung passiert direkt im SQL."

---

## 7. Warum es so geschnitten ist (für Rückfragen)

- **Dünne Routen:** leicht zu lesen, kein SQL/keine Rechnung im HTTP-Handler.
- **Fachlogik im Service:** ohne HTTP aufrufbar → direkt testbar (siehe `tests/`).
- **SQL nur im Repo:** ändert sich das Schema, ist nur eine Stelle betroffen.
- **OFF als eigene Datei:** ersetzbar/mockbar, kein Netz im Test.
- **Eine Funktion pro Aufgabe** und gemeinsame Helfer (`_change_amount`,
  `_handle_amount_change`) statt kopiertem Code.
