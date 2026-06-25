"""KI-Schätzung der Nährwerte pro 100g für einen Suchbegriff (Add Food).

Liefert ein Result im selben Format wie die OpenFoodFacts-Suche, damit es
als erster Treffer neben den OFF-Ergebnissen angezeigt werden kann.
"""
import json

from ..calculations import safe_float
from .ollama_client import generate_from_ollama


_PROMPT = (
    "Du bist ein Lebensmittel Experte und Nährwert-Schätzer für FitFridge. "
    "Schätze die Nährwerte pro 100g für das genannte Lebensmittel möglichst präzise. "
    "Auf 100g immer die Protein-, Fett- und Kohlenhydratmenge sowie die Kalorien angeben. "
    "Bei Unsicherheit gib eine plausible Durchschnittsschätzung statt 0. "
    "Antworte nur als JSON, ohne Markdown:\n"
    '{"name":"string","kcal":number,"protein":number,"fat":number,"carbs":number}\n\n'
    "Lebensmittel: "
)


def estimate_food(query, model=None):
    """Nährwert-Schätzung als Result-Dict, oder None bei Fehler/leerer Eingabe."""
    query = (query or "").strip()
    if not query:
        return None
    try:
        raw = generate_from_ollama(
            prompt=_PROMPT + query,
            model=model,
            timeout=15,
            num_predict=200,
            format_json=True,
        )
        data = json.loads(raw)
        macros = {k: safe_float(data[k], 0.0) for k in ("kcal", "protein", "fat", "carbs")}
    except Exception:
        return None  

    return {
        "name": (data.get("name") or query).strip() or query,
        "brand": "KI-Schätzung",
        "barcode": "",
        "kcal_per_100g": round(macros["kcal"], 1),
        "protein_per_100g": round(macros["protein"], 1),
        "fat_per_100g": round(macros["fat"], 1),
        "carbs_per_100g": round(macros["carbs"], 1),
        "total_amount": None,
        "unit": "g",
    }
