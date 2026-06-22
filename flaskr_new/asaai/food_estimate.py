"""KI-Schaetzung der Naehrwerte pro 100g fuer einen Suchbegriff (Add Food).

Liefert ein Result-Dict im selben Format wie die OpenFoodFacts-Suche, damit es
als erster Treffer neben den OFF-Ergebnissen angezeigt werden kann.
"""
import json

from .ollama_client import generate_from_ollama


_PROMPT = (
    "Du bist ein Naehrwert-Schaetzer fuer FitFridge. "
    "Schaetze die Naehrwerte pro 100g fuer das genannte Lebensmittel moeglichst praezise. "
    "Nimm die unverarbeitete Primaerquelle an (z.B. 'Mango' = frische Mango, nicht Mango-Lassi). "
    "Bei Unsicherheit gib eine plausible Durchschnittsschaetzung statt 0. "
    "Antworte nur als JSON, ohne Markdown:\n"
    '{"name":"string","kcal":number,"protein":number,"fat":number,"carbs":number}\n\n'
    "Lebensmittel: "
)


def estimate_food(query, model=None):
    """Naehrwert-Schaetzung als Result-Dict, oder None bei Fehler/leerer Eingabe."""
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
        macros = {k: float(data[k]) for k in ("kcal", "protein", "fat", "carbs")}
    except Exception:
        return None  # ponytail: bei Ollama-/Parse-Fehler einfach keine KI-Zeile

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
