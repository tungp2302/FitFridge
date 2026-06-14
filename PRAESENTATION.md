# FitFridge – Zwischenpräsentation (SE)

> Foliensatz zum Übernehmen in PowerPoint. Jede `## Folie` = eine Slide.
> Bullets = Folieninhalt. *Sprechnotiz* = was man dazu sagt (Notizenbereich).

---

## Folie 1 — Titel

**FitFridge**
Digitaler Kühlschrank & Mahlzeiten-Tracker

- Strukturierte Programmierung / Software Engineering – SoSe 2026
- Zwischenpräsentation, 15.06.2026
- [Name(n) / Gruppe]

*Sprechnotiz:* Kurz vorstellen, worum es geht: ein kleines Web-Projekt mit Flask, das Lebensmittel verwaltet und Mahlzeiten trackt.

---

## Folie 2 — Was ist FitFridge?

- Lebensmittel per **Barcode oder Name** anlegen → Nährwerte automatisch von **Open Food Facts**
- **Kühlschrank**: Bestände anzeigen, bearbeiten, verbrauchen, auffüllen
- **Mahlzeiten-Tracker**: Mahlzeiten gegen ein Tagesziel (Kalorien + Makros) loggen

**Abgrenzung SE vs. ASaai**
- Diese Version = **nur Core** (Frontend + Backend + Open Food Facts)
- KI-Teile (AI-Schätzung, Rezeptplaner, LLM-Einstellungen) = ASaai → hier **entfernt**

*Sprechnotiz:* Betonen, dass für SE bewusst nur die Kernfunktionalität ohne KI gezeigt wird.

---

## Folie 3 — Aktueller Stand

| Bereich | Status |
|---|---|
| Kühlschrank (anzeigen/anlegen/bearbeiten/löschen) | ✅ |
| Produktsuche über Open Food Facts (Barcode + Text) | ✅ |
| Verbrauchen / Auffüllen mit Validierung + Log | ✅ |
| Mahlzeiten-Tracker (Tagesziel, Makros, Logging) | ✅ |
| Nährwert-/Einheiten-Berechnung | ✅ |
| Login / Registrierung (Daten pro Nutzer) | ✅ |
| Automatisierte Tests | ✅ 35 grün |

*Sprechnotiz:* Kernfunktionen laufen end-to-end, abgesichert durch Tests.

---

## Folie 4 — Technik-Stack

- **Python + Flask** (Web-Framework)
- **SQLite** als Datenbank
- **Jinja2**-Templates, reines **HTML / CSS / JS** (kein Frontend-Framework)
- Open Food Facts über die Standardbibliothek (`urllib`) – kein API-Key nötig
- Tests mit **pytest**

*Sprechnotiz:* Bewusst schlanker Stack, gut überschaubar für ein Uni-Projekt.

---

## Folie 5 — Core-Funktion 1: Produktsuche (Open Food Facts)

- Seite **„New Food"** (`/fridge/add`)
- Eingabe = **Barcode** (nur Ziffern) → direkter Barcode-Lookup
- Eingabe = **Name** → Textsuche, Trefferliste zur Auswahl
- Klick legt Produkt inkl. Nährwerten + Packungsmenge im Kühlschrank an
- Kein Treffer? → **„Create anyway"**

*Sprechnotiz:* Hier live ein Produkt suchen und hinzufügen (z. B. Nutella oder einen Barcode).

---

## Folie 6 — Core-Funktion 2: Kühlschrank verwalten

- **Dashboard** (`/`): alle Produkte + hochgerechnete Nährwerte + Gesamt-Übersicht
- **Detailseite**: Name, Marke, Menge, Einheit ändern
- **Verbrauchen / Auffüllen**: Menge eingeben → Bestand wird angepasst
  - Verbrauch endet bei 0, jede Änderung landet im Verbrauchs-Log

*Sprechnotiz:* Zeigen, wie sich Menge und Nährwerte aktualisieren.

---

## Folie 7 — Core-Funktion 3: Mahlzeiten-Tracker

- **Tagesziel** setzen: Zielkalorien + Makro-Verteilung (P/C/F automatisch auf 100 %)
- **Mahlzeit loggen**: aus Kühlschrank-Item oder per Barcode-Suche
  - Optional: Bestand im Kühlschrank wird direkt reduziert
- **Tagesübersicht**: verbraucht vs. übrig + kurze Empfehlung
- Einträge nachträglich ändern oder löschen

*Sprechnotiz:* Den Kreislauf Kühlschrank → Mahlzeit → Tagesziel deutlich machen.

---

## Folie 8 — Architektur: Schichtenmodell

```
Browser (HTML/CSS/JS, Jinja2)
        │  HTTP
        ▼
routes.py        → Flask-Routen (dünn, keine Fachlogik)
        ▼
*_service.py     → Fachlogik (verbrauchen, loggen, rechnen)
        ▼
*_repo.py        → Datenbankzugriff (reine SQL-Funktionen)
        ▼
db.py / SQLite

openfoodfacts_client.py → externe API, eigenständig
```

- **Eine Aufgabe pro Datei** → testbar, übersichtlich

*Sprechnotiz:* Roter Faden der ganzen Code-Erklärung: Anfrage wandert von oben nach unten durch die Schichten.

---

## Folie 9 — Code-Durchstich: „Produkt hinzufügen"

1. **Route** `add_product()` nimmt Eingabe / ausgewählten Treffer entgegen
2. **Service** `create_dashboard_item()` holt Daten via `lookup_product()`
3. **OFF-Client** liefert Name + Nährwerte + Menge
4. **Repo** `product_repo` / `fridge_repo` schreiben Produkt + Kühlschrank-Item
5. Redirect zurück aufs Dashboard

*Sprechnotiz:* Ein konkretes Beispiel quer durch alle Schichten – verständlicher als jede Datei einzeln.

---

## Folie 10 — Code: Routen-Schicht (`routes.py`)

- `dashboard()` – Items laden, Nährwerte hochrechnen, Summen bilden
- `add_product()` – Produkt anlegen (Treffer oder Direkteingabe)
- `api_products_search()` – JSON-Suche fürs Frontend (Barcode bzw. lokal + OFF)
- `product_detail()` / `consume` / `refill` – bearbeiten & Menge ändern
- `meal_tracker()` – ein Endpunkt, mehrere Aktionen (Feld `action`)
- `register` / `login` / `logout` – Auth mit gehashten Passwörtern

*Sprechnotiz:* Routen sind absichtlich kurz: lesen, Service rufen, Antwort rendern.

---

## Folie 11 — Code: Service- & Rechen-Schicht

**fridge_service.py**
- `create_dashboard_item…`, `consume_amount` / `refill_amount`, `calculate_total_nutrition`

**meal_tracker_service.py**
- Tagesziele berechnen, Makros normalisieren, Mahlzeiten loggen

**nutrition_service.py + calculations.py**
- `convert_units` (mg/g/kg, ml/cl/l)
- `calculate_for_amount`: „pro 100 g" → echte Menge (Faktor = Menge / 100)

*Sprechnotiz:* Hier steckt die eigentliche Logik – ohne HTTP, daher gut testbar.

---

## Folie 12 — Code: Repository- & DB-Schicht

- **product_repo** – Produkte anlegen / suchen (Barcode, ID, Name)
- **fridge_repo** – Kühlschrank-Items (Liste mit Produkt-Join, Menge ändern, löschen)
- **meal_tracker_repo** – Tagesziele + Mahlzeiten-Einträge + Tagessummen
- **consumption_log_repo** – protokolliert jedes Verbrauchen / Auffüllen
- **db.py** – Verbindung pro Request + Tabellen anlegen

- Zugriffe sind **auf den Nutzer gescoped** → niemand sieht fremde Items

*Sprechnotiz:* Reine SQL-Funktionen, ein Repo pro Tabelle.

---

## Folie 13 — Open-Food-Facts-Anbindung

- `search_product(barcode)` – Produkt per Barcode, Nährwerte normalisieren (auch kJ → kcal)
- `_parse_total_quantity` – Packungsmenge parsen (z. B. „4 x 100 g" → 400 g)
- `search_products(query)` – Textsuche, dann Nährwerte nachladen, nach Ähnlichkeit sortiert
- `lookup_product(query)` – Fassade: Ziffern → Barcode, sonst Textsuche

*Sprechnotiz:* Eigene Datei, hängt an keiner Datenbank – klar getrennt.

---

## Folie 14 — Tests

- **35 Tests, alle grün** (`python -m pytest -q`)
- Abgedeckt:
  - DB-Schema + Produkt-/Kühlschrank-CRUD
  - Open-Food-Facts-Parsing (gemockt, **ohne echten Netzaufruf**)
  - Nährwert-/Einheiten-Berechnung inkl. Sonderfälle
  - Verbrauchen / Auffüllen
  - Mahlzeiten-Tracker (loggen, Restmenge in den Kühlschrank)

*Sprechnotiz:* Schichtentrennung macht das möglich – Logik direkt aufrufen, externe Aufrufe ersetzen.

---

## Folie 15 — Live-Demo

1. Produkt über Open Food Facts suchen & hinzufügen
2. Kühlschrank: Menge verbrauchen / auffüllen
3. Mahlzeit tracken + Tagesziel anschauen

```
flask --app flaskr_new run --debug   →  http://127.0.0.1:5000
```

*Sprechnotiz:* Server vorab starten; Demo-Daten optional via `scripts/seed_demo.py` (Login demo/demo).

---

## Folie 16 — Nächste Schritte

- UI-Feinschliff (einheitliche Sprache, Mobil-Ansicht)
- Mehr Tests für die Frontend-Routen (Mahlzeit-Flows end-to-end)
- Separat (ASaai-Strang): KI-Schätzung & Rezeptplaner

*Sprechnotiz:* Klar trennen, was noch SE ist und was bewusst in den ASaai-Teil gehört.

---

## Folie 17 — Abschluss

**Danke! Fragen?**

- Core läuft: Open Food Facts, Kühlschrank, Mahlzeiten-Tracker
- Saubere Schichten, durch Tests abgesichert

*Sprechnotiz:* Kurzes Fazit, dann Fragen.

---

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
