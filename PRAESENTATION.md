# FitFridge — Präsentation: Von der Vorlesung zur Produktion

---

## Folie 1 — Was ist FitFridge? (Motivation)

**Problem:** Du öffnest den Kühlschrank, siehst Hähnchenbrust, Reis, Paprika, Eier — und weißt trotzdem nicht, was du kochen sollst. Noch schwieriger: Du hast ein Fitnessziel — 2200 kcal, 160 g Protein — und weißt nicht, ob das Rezept das trifft.

**FitFridge löst genau das:**
- Digitaler Kühlschrank: du weißt immer, was du hast und wie viele Nährwerte noch drin sind
- KI-Rezeptplaner: ein lokales LLM generiert kochbare Rezepte **nur aus deinen echten Zutaten**, mit automatischer Makro-Anpassung auf dein Tagesziel
- Mahlzeiten-Tracker: was du gegessen hast, was noch übrig ist

**Relevanz für die Vorlesung:** Das Projekt verbindet alle fünf Themenblöcke — LLMs, RAG, Agentic Systems, Recommender Systems, Adaptive Systems — in einer einzigen Applikation, die wirklich läuft.

---

## Folie 2 — Tech-Stack auf einen Blick

| Schicht | Technologie | Warum |
|---|---|---|
| Backend | Python 3.10+, Flask 3 | Minimal, kein Overhead |
| Datenbank | SQLite (stdlib) | Kein Server nötig, ideal für Uni-Setup |
| Frontend | Jinja2-Templates + Vanilla-JS | Kein Build-Tool, kein Framework |
| KI | Ollama lokal (`qwen3.5:latest`) | Läuft offline, keine API-Kosten |
| Externe Daten | OpenFoodFacts API (urllib) | Freie Produktdatenbank |
| Auth | Werkzeug Password-Hashing | Standardbibliothek |

**Wichtig:** Die Datenbank wird bei jedem Serverstart neu aufgebaut (`schema.sql` → `DROP TABLE / CREATE TABLE`) und per `seed.py` mit Demo-Daten gefüllt. Login: `demo` / `demo`. Das ist bewusst — so ist jeder Demo-Lauf sauber reproduzierbar.

---

## Folie 3 — Systemarchitektur (Schichtenmodell)

```
Browser (Jinja2-Templates + Vanilla-JS)
   │  HTML-Forms (SE)            │  fetch/JSON (ASAAI)
   ▼                            ▼
routes.py (Frontend-Blueprint)   asaai/routes_asaai.py  (/asaai/*)
   │                            │
   ▼                            ▼
*_service.py  (Fachlogik)        asaai/freestyle_recipe.py
   │                            │
   ▼                            ▼
*_repo.py     (reines SQL)       asaai/freestyle_recipe_support.py
   │                            │
   ▼                            ▼
db.py (sqlite3)                  asaai/ollama_client.py
   │
schema.sql + seed.py
```

**Zwei Blueprints, eine Trennung:**
- `routes.py` (SE-Blueprint): klassisches Request/Response, HTML-Formulare, serverseitiges Rendering
- `asaai/routes_asaai.py` (ASAAI-Blueprint): JSON-API, wird per `fetch` vom Browser aufgerufen

**Warum diese Trennung wichtig ist:** Der ASAAI-Teil hat andere Anforderungen — er braucht async-ähnliche Verhalten im Browser (zweistufiges Laden), gibt JSON zurück, und schützt Endpunkte mit `401 JSON` statt HTML-Redirect. Beides in einer Datei zu mischen wäre chaotisch.

---

## Folie 4 — Teil A: Software Engineering Kern

Das ist die **SE-Leistung** des Projekts — solide, sauber, durchgezogen.

### Datenbank-Schema (7 Tabellen)

```
user            → id, username, password (Werkzeug-Hash)
product         → name, brand, barcode (UNIQUE), kcal/protein/fat/carbs_per_100g, grams_per_piece
fridge_item     → user_id, product_id, current_amount, unit
meal_tracker_settings → user_id (UNIQUE), daily_kcal, protein_pct, carbs_pct, fat_pct
meal_tracker_entry    → user_id, meal_name, amount, kcal, protein_g, carbs_g, fat_g, eaten_at
saved_recipe    → user_id, title, data (JSON-Blob)
app_settings    → user_id (UNIQUE), llm_model
```

**Schlüsselentwurfsentscheidungen:**
- `fridge_item.user_id` nullable → für barcode-lose Items (KI-Schätzungen) funktioniert das `ON CONFLICT` korrekt
- `saved_recipe` speichert `title` separat vom JSON-Blob → Umbenennen braucht keinen Blob-Parse
- `app_settings` nutzt **UPSERT** (`ON CONFLICT(user_id) DO UPDATE`) → kein separates INSERT/UPDATE

### Schichtenreinheit

```
product_repo.py   → nur SQL, kein Business-Logic
fridge_service.py → Geschäftslogik (Produkt finden oder anlegen, Menge abziehen)
routes.py         → nur HTTP: Form parsen, Service aufrufen, Template rendern
```

`_repo.py`-Dateien enthalten kein `if`, keine Berechnungen — nur Queries. `_service.py`-Dateien kennen kein `request`-Objekt. Diese Disziplin ist der Grund, warum 39 Tests ohne einen laufenden Webserver funktionieren.

### User-Isolation als Sicherheitsprinzip

Jede datenbanknahe Funktion ist `user_id`-gescoped:
```python
# fridge_repo.py
def get_item(item_id, user_id=None):
    # WHERE id = ? AND (user_id = ? OR user_id IS NULL)
```
Kein Nutzer sieht Daten eines anderen, nicht durch URL-Manipulation, nicht durch direkten DB-Zugriff.

---

## Folie 5 — Produkte hinzufügen: drei Wege

Das ist die **Eingangspforte** des Systems — wie kommen Lebensmittel in die App?

### Weg 1: Barcode-Scanner

```javascript
// barcode_scan.js
startBarcodeScan(onResult)
  → BarcodeDetector API (nativ: Android, macOS)
  → Fallback: zxing-wasm (WASM-Bibliothek, Firefox/Windows/iOS)
  → enhanceContrast() → Graustufen + 1%-Clipping gegen Überbelichtung
  → detectFrame() → nur mittleres Bildband (1D-Codes sind breit)
```

**Warum zwei APIs?** `BarcodeDetector` ist modern aber nicht überall verfügbar. `zxing-wasm` ist eine bewährte Bibliothek als WebAssembly-Modul — kein Server, läuft im Browser. Das ist defensive Programmierung: erst native API probieren, dann Fallback.

### Weg 2: Suche (Name oder Barcode)

`unified_search(q)` in `routes.py` verbindet drei Quellen parallel:
1. **KI-Schätzung** (ASAAI) — sofort, ohne Netzwerk
2. **Lokale DB** — eigene bereits eingescannte Produkte
3. **OpenFoodFacts** — Millionen realer Produkte

Dedupliziert per Barcode, nach Relevanz sortiert. `openfoodfacts_client.py` nutzt reines `urllib` — keine externe Bibliothek, kein `requests`. Das Relevanz-Ranking: exakte Namensübereinstimmung = 60 Punkte, "enthält" = 35, Teilwort = 15; Tiebreak nach Proteingehalt.

### Weg 3: KI-Nährwertschätzung (Brücke zu LLMs)

```python
# food_estimate.py
estimate_food("Schwarzwälder Kirschtorte")
  → Ollama JSON-Prompt → { kcal: 350, protein: 5, fat: 18, carbs: 42 }
  → Ausgabe im gleichen Format wie OpenFoodFacts
  → erscheint als "KI-Schätzung" ganz oben in den Suchergebnissen
```

**Vorlesungs-Brücke (LLMs / In-Context-Learning):** Das LLM wird hier als **Wissensdatenbank** benutzt — es kennt aus seinem Training die ungefähren Nährwerte von Lebensmitteln. Ein strukturierter JSON-Prompt zwingt es, sein implizites Wissen in ein maschinenlesbares Format zu verpacken. Das ist In-Context Learning in Reinform: kein Fine-Tuning, nur ein präzise formulierter Prompt.

---

## Folie 6 — Mahlzeiten-Tracker

Der Tracker ist komplexer als er aussieht.

### Warenkorb-Logik (Session-basiert)

Mahlzeiten werden nicht sofort geloggt. Der Nutzer sammelt zuerst im **Session-Warenkorb**:
- Item aus dem Kühlschrank → Menge abziehen, loggen
- Item aus der Suche → loggen, Rest als **neuer Kühlschrank-Eintrag** anlegen

`commit_meal_cart()` in `meal_tracker_service.py` macht das atomar — entweder alles oder nichts.

### Proportionale Skalierung

```python
# meal_tracker_repo.py
def update_meal_entry_amount(entry_id, user_id, new_amount):
    factor = new_amount / old_amount
    UPDATE ... SET
        kcal = kcal * factor,
        protein_g = protein_g * factor,
        ...
```

Wenn du sagst "ich habe doch nur 150 g gegessen statt 200 g", skalieren alle Makros mit. Keine Neuberechnung aus der Produktdatenbank nötig — mathematisch korrekt, weil Nährwerte linear sind.

### Kalender-Integration

`calendar.monthrange` (Python stdlib) liefert das Monatsraster. `get_tracked_days()` via SQLite `strftime(..., 'localtime')` markiert Tage mit Einträgen. Ein Klick springt in die Vergangenheit — wichtig für Langzeitbeobachtung.

---

## Folie 7 — Teil B: ASAAI — Die KI-Schicht beginnt hier

Ab hier verlassen wir klassisches Web-Engineering und betreten das Terrain der Vorlesung.

### Was der ASAAI-Teil macht

1. Nutzer klickt "Freestyle-Rezept generieren"
2. Browser sendet: `{ daily_goal: {kcal: 700, protein: 50, ...}, recipe_category: "Hauptspeise", count: 1 }`
3. Backend liest Kühlschrank-Inhalt aus der DB
4. LLM (Ollama) generiert Rezept als JSON
5. Backend **validiert und repariert** das Ergebnis
6. Browser zeigt fertiges Rezept an

Das klingt einfach. Es ist es nicht. Warum — das zeigen Folien 8–12.

---

## Folie 8 — RAG: Retrieval-Augmented Generation in FitFridge

**Vorlesungs-Definition:** RAG = Retrieval + Augmentation + Generation. Statt dem LLM alles aus dem Training-Gedächtnis abzufragen, wird **externer Kontext abgerufen** und **in den Prompt injiziert**. Das LLM generiert dann basierend auf diesem Kontext.

**FitFridge-Implementierung:**

```
Retrieval:    Kühlschrank-DB → alle fridge_items des Users → mit Produktdetails (JOIN)
Augmentation: Diese Zutaten + Nährwerte werden in den Prompt eingebettet
Generation:   Ollama generiert ein Rezept ausschließlich aus diesen Zutaten
```

Konkret sieht der injizierte Kontext so aus (aus `build_prompt()`):

```
Verfügbare Kühlschrank-Zutaten:
1. Hähnchenbrust (id=3): 300g verfügbar | 165 kcal, 31g P, 0g C, 4g F je 100g
2. Reis, weiß (id=7): 500g verfügbar | 130 kcal, 2g P, 28g C, 0g F je 100g
3. Paprika, rot (id=12): 200g verfügbar | 31 kcal, 1g P, 6g C, 0g F je 100g
...
```

Das LLM "weiß" so zur Laufzeit, was im Kühlschrank ist — obwohl dieser Kontext natürlich nicht in seinen Trainings-Gewichten steckt. Das ist exakt der RAG-Mechanismus aus der Vorlesung.

**Warum RAG hier notwendig ist:** Ein LLM ohne Kühlschrank-Kontext würde Rezepte vorschlagen, die Zutaten erfordern, die nicht vorhanden sind. Mit RAG ist das Modell **auf den tatsächlichen Bestand beschränkt** — ein Grundprinzip des kontextualisierten Schließens.

---

## Folie 9 — Agentic Systems: Die Retry-Schleife

**Vorlesungs-Definition:** Agentic Systems gehen über einfaches Prompt → Response hinaus. Sie haben: Tool Calling, Chain of Thought, Retry-Mechanismen, Stop-Conditions.

**FitFridge implementiert eine vollständige Agentic Loop:**

```python
# freestyle_recipe.py — _run()
for attempt in range(count + 1):          # Retry-Schleife
    response = generate_from_ollama(prompt, ...)

    recipes = valid_recipes(               # Validierung
        response,
        fridge_items=fridge_items,
        daily_goal=daily_goal,
        count=count
    )

    if len(recipes) >= count:
        break                             # Stop-Condition: genug valide Rezepte

    # Feedback für nächsten Versuch
    feedback = validation_feedback(recipes_so_far, needed=count)
    exclude = [r["title"] for r in recipes_so_far]
    # Nächste Iteration: Prompt mit feedback + exclude
```

**Die drei Agentic-Elemente:**

1. **Tool Calling analog:** `valid_recipes()` ist ein "Tool" das der Agent aufruft — es gibt strukturiertes Feedback zurück, nicht nur True/False

2. **Feedback-Loop:** `validation_feedback()` formuliert konkreten Text, der in den nächsten Prompt eingeht:
   ```
   "Das Rezept 'Hähnchen-Bowl' wurde abgelehnt wegen:
    Doppelte Proteinquelle (Hähnchen + Thunfisch).
    Bitte nur eine Hauptproteinquelle verwenden."
   ```

3. **Stop-Condition:** Schleife endet wenn genug valide Rezepte vorhanden sind oder `count+1` Versuche überschritten

**Unterschied zum einfachen LLM-Call:** Ein einzelner Prompt würde ~30% der Zeit invalide Rezepte produzieren (falsche Zutaten-IDs, unrealistische Mengen, verbotene Kombinationen). Die Retry-Schleife bringt die Erfolgsquote auf >95%.

---

## Folie 10 — Recommender Systems: Wie FitFridge Zutaten auswählt

**Vorlesungs-Definition:** Recommender Systems empfehlen Inhalte basierend auf Nutzerprofil (User Tower) und Item-Eigenschaften (Item Tower). Content-Based Filtering nutzt Eigenschaften der Items, nicht andere Nutzer-Daten.

**FitFridge nutzt implizites Content-Based Filtering auf zwei Ebenen:**

### Ebene 1: Ingredient Selection im Prompt

`_macro_strategy_hint()` in `freestyle_recipe.py` analysiert die echten Nährwerte der Kühlschrank-Items und gibt dem LLM konkrete Empfehlungen:

```python
# Wenn Protein-Ziel ≥ 50g:
hint += "Verwende 200–300g der Hauptproteinquelle (Hähnchenbrust: 31g P/100g)."

# Wenn Low-Carb (Carbs-Ziel < 50g):
hint += "Stärke (Reis, Nudeln) stark reduzieren. Fett erhöhen (Öl, Nüsse)."

# Wenn süße Kategorie:
hint += "Kein Fleisch/Fisch. Süßungsmittel, Obst, Milchprodukte bevorzugen."
```

Das ist **Content-Based Filtering**: Zutaten werden nach ihren Nährstoffprofilen bewertet und entsprechend dem Nutzerziel gefiltert.

### Ebene 2: Two-Tower Analogie

| Vorlesung | FitFridge |
|---|---|
| User Tower | Nutzer-Tagesziel: `{daily_kcal: 2200, protein_pct: 30, ...}` |
| Item Tower | Rezept-Makros: `{kcal: 650, protein: 48, carbs: 60, fat: 20}` |
| Matching | `macros_within_targets(recipe_macros, daily_goal)` |

Das "Matching" ist kein neuronales Netz, sondern eine arithmetische Toleranz-Funktion — aber die **konzeptuelle Struktur** (nutze Profil × Item-Properties → Score → Filter) ist identisch.

### OpenFoodFacts Relevanz-Ranking als Recommender

```python
# openfoodfacts_client.py
def _score_off_product(product, query_terms):
    score = 0
    if name == query: score += 60      # exakte Übereinstimmung
    elif query in name: score += 35    # enthält Suchbegriff
    else: score += 15                  # Teilwort
    # Tiebreak: mehr Protein = relevanter für Fitness-App
    score += min(protein_per_100g, 10)
    return score
```

Das ist klassisches **Content-Based Filtering** über Produkt-Eigenschaften: kein Nutzerverhalten, nur Produkt-Features.

---

## Folie 11 — Adaptive Systems & MAPE-K: Die Makro-Reparatur

Das ist die **technisch anspruchsvollste** Komponente — und sie ist direkt aus dem MAPE-K-Modell der Vorlesung ableitbar.

**Vorlesungs-Definition MAPE-K:**
- **M**onitor: Systemzustand beobachten
- **A**nalyze: Ist-Zustand vs. Soll-Zustand vergleichen
- **P**lan: Anpassungsstrategie entwickeln
- **E**xecute: Änderung durchführen
- **K**nowledge Base: domänenspezifisches Wissen

**FitFridge MAPE-K Mapping:**

```
Monitor  →  computed_macros(recipe, fridge_items)
            Berechnet kcal/Protein/Fett/Carbs aus
            Gramm-Mengen × /100g-Werten der echten Produkte
            (NICHT dem, was das LLM behauptet)

Analyze  →  macros_within_targets(computed, daily_goal)
            Vergleicht jeden Makro gegen erlaubten Bereich:
            kcal: max +10%, Protein: nur Untergrenze,
            Fett/Carbs: symmetrische Toleranz

Plan     →  _fit_amounts() — Koordinatenabstieg
            Wählt pro Makro eine Hebel-Zutat:
            dichteste Proteinquelle, Hauptkohlenhydratquelle, Hauptfettquelle

Execute  →  _set_fridge_amounts() / _scale_fridge_amounts()
            Passt die Gramm-Mengen an, baut Labels neu

Knowledge →  MACRO_TOLERANCES, PROTEIN/STARCH/SWEET/SAVORY Listen
             Domain-Wissen über Nährstoffdichte, Lebensmittelkategorien
```

### Koordinatenabstieg — der Algorithmus

```python
# freestyle_recipe_support.py — _fit_amounts()
def _fit_amounts(recipe, fridge_items, daily_goal):
    # Schritt 1: Finde Hebel-Zutaten
    protein_lever = max(fridge_ingredients, key=lambda i: i['protein_per_100g'])
    carb_lever    = max(fridge_ingredients, key=lambda i: i['carbs_per_100g'])
    fat_lever     = max(fridge_ingredients, key=lambda i: i['fat_per_100g'])

    # Schritt 2: Berechne benötigte Grammzahl pro Hebel
    protein_needed_g = (target_protein_g - other_protein) / (lever['protein'] / 100)

    # Schritt 3: Klemme auf valide Grenzen (0–1200g, Supplements ≤80g)
    # Schritt 4: Setze neue Menge, recompute alle Makros
    # Schritt 5: Prüfe ob Ergebnis valide → sonst Gesamt-Skalierung als Fallback
```

**Warum Koordinatenabstieg?** Ein einfaches kcal-Skalieren (alle Mengen × Faktor) fixiert proportionale Fehler, aber nicht strukturelle. Beispiel: Das Modell generiert ein Rezept mit 400g Reis und 100g Hähnchen. Wenn das Protein-Ziel 60g ist (Hähnchen hat 31g/100g → braucht 193g), reicht Skalieren nicht — du musst selektiv den Protein-Lever hochdrehen und den Stärke-Lever runter. Das ist das, was `_fit_amounts()` tut.

### Adaptive Systems: Drei Adaptivitätstypen der Vorlesung

| Typ | FitFridge |
|---|---|
| **Kontextbasiert** | LLM-Prompt ändert sich je nach Kühlschrank-Inhalt (RAG), Rezeptart, Tageszeit-Ziel |
| **Nutzerbasiert** | Makro-Reparatur zielt auf das individuelle Tagesziel des Users |
| **Systemzentrisch** | Retry-Schleife + Validierung = selbst-korrigierendes Verhalten ohne Nutzereingriff |

Das System adaptiert auf **allen drei Ebenen gleichzeitig**.

---

## Folie 12 — Die Validierungs-Pipeline

Bevor ein Rezept angezeigt wird, durchläuft es 8 Checks. Das ist **kein nice-to-have** — ohne Validierung liefert das LLM ~30% Unsinn.

```python
# freestyle_recipe_support.py — _is_valid()

def _is_valid(recipe, fridge_items, daily_goal, category):

    # 1. Nur echte Kühlschrank-IDs
    if not _ids_ok(recipe, fridge_items): return False, "Ungültige Zutaten-IDs"

    # 2. Reale Portionsgrößen (0 < g ≤ 1200, Supplements ≤ 80g)
    if not _amounts_ok(recipe): return False, "Unrealistische Mengen"

    # 3. Pantry-Limits (Öl ≤ 50g, Salz ≤ 10g)
    if not _pantry_amounts_ok(recipe): return False, "Öl/Salz überdosiert"

    # 4. Kein Doppel-Protein (Hähnchen + Thunfisch im gleichen Gericht)
    # 5. Kein Doppel-Stärke (Reis + Nudeln)
    # 6. Kein Süß-Herzhaft-Mix (Honig + Hähnchen)
    # 7. Whey-Protein nur in süßen Gerichten
    # 8. Titel muss Hauptzutat enthalten
    if conflicts := _recipe_conflicts(recipe, category): return False, conflicts

    # 9. Mindestens 3 Kochschritte (kein "Alles in eine Schüssel")
    if len(recipe["instructions"]) < 3: return False, "Zu wenig Schritte"

    # 10. Makros im Zielbereich (nach Reparatur)
    if not macros_within_targets(computed_macros(recipe), daily_goal):
        return False, "Makros außerhalb Zielbereich"
```

**Vorlesungs-Brücke:** Die Keyword-Listen (`PROTEIN, STARCH, SWEET, SAVORY_CATS, SUPPLEMENT...`) sind die **Knowledge Base** des MAPE-K-Modells. Domänenspezifisches Wissen, hart kodiert — der Teil, der gepflegt werden muss, wenn neue Zutaten oder Modelle hinzukommen.

---

## Folie 13 — Zweistufiges Laden: UX meets KI-Latenz

**Problem:** Ein Ollama-Call dauert 10–35 Sekunden. Drei Rezepte nacheinander = 45–105 Sekunden Wartezeit. Inakzeptabel.

**Lösung in `planner.js`:**

```javascript
async function loadFreestyleRecipe() {
    // Phase 1: SOFORT einen Vorschlag holen (count=1)
    const first = await fetch('/asaai/recipes/freestyle',
        { body: JSON.stringify({...goal, count: 1}) }
    );
    renderDetail(first);          // User sieht sofort etwas

    // Phase 2: Zwei weitere IM HINTERGRUND (count=2, exclude=[first.title])
    const more = await fetch('/asaai/recipes/freestyle',
        { body: JSON.stringify({...goal, count: 2, exclude: [first.title]}) }
    );
    // deduplizieren, in Rail einfügen
}
```

`requestToken` verhindert Race-Conditions bei schnellem Mehrfachklick.

**Warum das wichtig ist:** KI-Systeme haben andere Latenz-Profile als klassische Web-Backends. Progressive Loading ist hier kein Luxus, sondern Grundvoraussetzung für benutzbare UX.

---

## Folie 14 — Das Wichtigste: Vertraue dem Modell nicht

Das ist das **zentrale Architektur-Prinzip** des ASAAI-Teils:

> Das Backend vertraut den Modellzahlen nicht.

Das LLM schätzt Nährwerte in `estimated_macros`. Diese Zahlen werden **komplett ignoriert**. Stattdessen:

```python
# computed_macros() — die Wahrheit
def computed_macros(recipe, fridge_items):
    kcal = 0
    for ingredient in recipe["fridge_ingredients"]:
        product = fridge_items[ingredient["id"]]
        gram_factor = ingredient["amount_g"] / 100
        kcal    += product["kcal_per_100g"]    * gram_factor
        protein += product["protein_per_100g"] * gram_factor
        # ...
    return { "kcal": kcal, "protein": protein, ... }
```

**Nährwerte werden aus Gramm-Mengen × /100g-Werten der echten Produkte berechnet.**

Das hat zwei Konsequenzen:
1. Das Frontend zeigt immer korrekte Nährwerte (nicht LLM-Halluzinationen)
2. Die Validierung kann Rezepte ablehnen und reparieren, weil sie die echten Zahlen kennt

Das ist ein Beispiel für **hybride Systeme**: LLM für kreative Aufgaben (Rezeptideen, Schritte, Namen), deterministischer Code für präzise Aufgaben (Nährwert-Mathematik).

---

## Folie 15 — Testabdeckung: 39 Tests, alle grün

```
test_api_db/
  test_api_db.py (4)            → OpenFoodFacts: Parsing, Multiplikatoren, Ranking

test_backend/
  test_freestyle_recipe.py (14) → Kern: valide Rezepte, Makro-Berechnung,
                                   Low-Carb-Reparatur, Retry, Warnungen
  test_meal_tracker.py (6)      → Settings, Tagessummen, User-Isolation
  test_ollama_client.py (5)     → Modell-Auflösung, Response-Parsing
  test_app_settings.py (5)      → Settings-Roundtrip, User-spezifisch
  test_nutrition_integration.py (3) → Einheitenrechnung
  test_product_repo.py (2)      → Barcode/Name-Suche
```

Ollama und OpenFoodFacts werden per `monkeypatch` ersetzt — **alle Tests laufen offline**. Das ist kein Zufall: wer externe Dienste direkt testet, hat keine reproduzierbaren Tests.

**Live-Test-Ergebnis (25.06.2026):**

| Check | Ergebnis |
|---|---|
| Ollama erreichbar, `qwen3.5:latest` installiert | ✅ |
| Flask-Start + `GET /` | ✅ 200 |
| Login `demo`/`demo` | ✅ 302 |
| Rezeptplaner-Seite | ✅ 200 |
| Rezeptgenerierung über echtes LLM | ✅ 200 in 33s, `macro_source: computed_from_fridge_amounts` |
| Test-Suite | ✅ 39 passed |

---

## Folie 16 — Zusammenfassung: Vorlesung → Produktion

| Vorlesungsthema | FitFridge-Umsetzung | Datei |
|---|---|---|
| **LLMs / In-Context Learning** | JSON-Prompt-Modus, KI-Nährwertschätzung | `ollama_client.py`, `food_estimate.py` |
| **RAG** | Kühlschrank-Kontext in Prompt injiziert | `freestyle_recipe.py:build_prompt()` |
| **Agentic Systems** | Retry-Schleife + Validierungs-Feedback | `freestyle_recipe.py:_run()` |
| **Recommender Systems** | Content-Based Filtering (Makro-Match), Relevanz-Ranking | `freestyle_recipe_support.py`, `openfoodfacts_client.py` |
| **Adaptive Systems / MAPE-K** | Koordinatenabstieg zur Makro-Reparatur | `freestyle_recipe_support.py:_fit_amounts()` |
| **Kontextbasierte Adaptivität** | Prompt variiert je nach Kühlschrank, Ziel, Kategorie | `_macro_strategy_hint()` |
| **Nutzerbasierte Adaptivität** | Makro-Reparatur auf individuelles Tagesziel | `macros_within_targets()` |
| **Systemzentrische Adaptivität** | Selbst-heilende Retry-Schleife ohne Nutzereingriff | `_run()` |

---

## Folie 17 — Projektstatistik & Takeaway

**Umfang:**
- ~2.500 Zeilen Python
- ~870 Zeilen JS/CSS
- ~640 Zeilen Templates
- 39 Tests, alle grün

**Was dieses Projekt zeigt:**

1. Die Konzepte der Vorlesung — RAG, Agentic Systems, MAPE-K — sind keine akademischen Abstraktionen. Sie sind **praktische Lösungsmuster** für reale Probleme.

2. LLMs sind mächtig, aber **nicht zuverlässig genug für Präzisionsaufgaben**. Das richtige Design: LLM für Kreativität, Algebra für Korrektheit.

3. Ein gut durchdachtes Schichtenmodell (`repo → service → route`) ist die Voraussetzung dafür, dass KI-Komponenten testbar und wartbar bleiben.

4. **Degradation ist kein Fehler, sondern ein Feature:** Leerer Kühlschrank, LLM offline, unerreichbare Makro-Kombination — alle Fälle liefern verständliche Hinweis-Karten statt Crashes.

---

## Starten

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen3.5:latest
flask --app flaskr_new run --debug
# Login: demo / demo
# Tests: python -m pytest -q
```
