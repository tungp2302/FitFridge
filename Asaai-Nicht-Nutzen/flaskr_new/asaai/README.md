# ASaAI-Modul

KI-Features für die FitFridge-App. Hybrid-Architektur aus
**deterministischen Algorithmen** und **lokalem LLM** (Ollama).

## Übersicht der Features

| Feature | Endpoint | Modul |
|---|---|---|
| Recipe Matcher | `GET /asaai/recipes/match-only` | `recipe_matcher.py` |
| Volle KI-Pipeline | `POST /asaai/recipes/suggest` | `llm_enricher.py` |
| Nutrition Insights | `GET/POST /asaai/insights/nutrition` | `nutrition_insights.py` |

## Architektur

HTTP-Request
↓
routes_asaai.py (Blueprint, URL-Prefix: /asaai)
↓
Service-Layer:

recipe_matcher.py    (TheMealDB-Integration)
llm_enricher.py      (LLM-basiertes Re-Ranking)
nutrition_insights.py (LLM-basierte Bericht-Generierung)
↓
Helper-Layer:
meal_db_client.py    (TheMealDB API)
macro_calculator.py  (Nährwert-Berechnung)
ollama_client.py     (Lokales LLM via Ollama)
↓
Externe Quellen:
TheMealDB (kostenlos, kein API-Key)
OpenFoodFacts (kostenlos, kein API-Key)
Ollama lokal (qwen3.5:latest)

## Hybrid-Design-Prinzip

ASaAI kombiniert deterministische Logik mit KI:

1. **Deterministisch (schnell, vorhersehbar):**
   - Recipe Matcher findet Kandidaten basierend auf Zutaten-Match
   - Macro Calculator rechnet Nährwerte mit Mengen-Parser
   - Goal-Ranking sortiert nach Tagesziel-Passung

2. **KI-basiert (kreativ, kontextuell):**
   - LLM re-rankt finale Empfehlungen
   - LLM erklärt Vorschläge in natürlicher Sprache
   - LLM schlägt Zutaten-Substitutionen vor
   - LLM generiert Ernährungs-Insights

## Setup

### 1. Ollama installieren
```bash
# Mac: https://ollama.com Download
# Linux: curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Modell laden
```bash
ollama pull qwen3.5:latest
```

### 3. Python-Abhängigkeiten
```bash
pip install requests
```

(Tungs `ollama_client.py` ist bereits im Modul enthalten und wird wiederverwendet.)

## Verwendung der API

### Schnelle Rezept-Suche (~30 Sek)
```bash
curl http://localhost:5000/asaai/recipes/match-only
```

### Volle KI-Pipeline mit Tagesziel (~3-4 Min)
```bash
curl -X POST http://localhost:5000/asaai/recipes/suggest \
  -H "Content-Type: application/json" \
  -d '{"daily_goal": {"protein": 30, "kcal": 800}}'
```

### Nutrition Insights (~1 Min)
```bash
curl -X POST http://localhost:5000/asaai/insights/nutrition \
  -H "Content-Type: application/json" \
  -d '{"daily_goal": {"protein": 120, "kcal": 2000}}'
```

## Verwendung im Python-Code

```python
from flaskr_new.asaai.recipe_matcher import find_recipes_matching_fridge
from flaskr_new.asaai.llm_enricher import enrich_with_full_pipeline

fridge = [{"name": "chicken"}, {"name": "rice"}]
matches = find_recipes_matching_fridge(fridge)
result = enrich_with_full_pipeline(
    matches=matches,
    fridge_items=fridge,
    daily_goal={"protein": 30, "kcal": 800},
)
print(result["llm_recommendation"])
```

## Tests

27 Pytest-Tests in `tests/test_asaai/`:
```bash
pytest tests/test_asaai/ -v
```

Alle externen Calls (LLM, APIs) werden in Tests gemockt für Geschwindigkeit.

## Bekannte Limitationen

1. **OpenFoodFacts-Treffer:** Generische Zutaten ("chicken") liefern
   manchmal Generic-Produkte mit ungenauen Makros. Für finale Version
   geplant: kuratierte Zutaten-Mapping-Tabelle.

2. **TheMealDB-Sprache:** API ist englisch. Suchen mit deutschen
   Zutaten-Namen funktionieren nicht.

3. **Mengen-Parser:** Zähleinheiten wie "2 chicken breasts" werden
   mit Default 200g/Stück geschätzt.

4. **LLM-Latenz:** qwen3.5 lokal braucht 30-90 Sek pro Aufruf.
   Für Frontend empfohlen: async/Loading-State.

## Performance

| Operation | Dauer |
|---|---|
| Recipe Matcher (8 Rezepte) | ~30 Sek |
| Macro Calculator (5 Rezepte) | ~2 Min |
| LLM Re-Ranking | ~60 Sek |
| Volle Pipeline | ~3-4 Min |
| Nutrition Insights | ~60 Sek |

Caching für API-Calls ist eingebaut (ingredient lookups).