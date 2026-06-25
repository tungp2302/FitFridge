"""Einheiten-Umrechnung und Nährwert-Berechnung."""

# Faktoren auf die Basiseinheit (g bzw. ml); Volumen wird als 1 ml = 1 g behandelt.
_TO_BASE = {"mg": 0.001, "g": 1.0, "kg": 1000.0, "ml": 1.0, "cl": 10.0, "l": 1000.0}


def calculate_for_amount(product, amount, unit):
    """Nährwerte für eine konkrete Menge (z.B. 30 g Nutella).

    Volumen wird vereinfachend als 1 ml = 1 g behandelt. Stückzahlen (``stk``)
    werden über ``grams_per_piece`` des Produkts in Gramm umgerechnet; fehlt der
    Wert, gibt es Nullen.
    """
    empty = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    if amount is None or amount <= 0:
        return empty
    if unit == "stk":
        per_piece = safe_float(product.get("grams_per_piece"))
        if not per_piece or per_piece <= 0:
            return empty
        amount_in_g = amount * per_piece
    elif unit in _TO_BASE:
        amount_in_g = amount * _TO_BASE[unit]
    else:
        return empty
    m = amount_in_g / 100.0
    return {
        "kcal": round(product["kcal_per_100g"] * m, 1),
        "protein": round(product["protein_per_100g"] * m, 1),
        "fat": round(product["fat_per_100g"] * m, 1),
        "carbs": round(product["carbs_per_100g"] * m, 1),
    }


def safe_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default
