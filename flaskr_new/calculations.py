"""Einheiten-Umrechnung und Naehrwert-Berechnung."""

# Faktoren auf die Basiseinheit (g bzw. ml); Volumen wird als 1 ml = 1 g behandelt.
_TO_BASE = {"mg": 0.001, "g": 1.0, "kg": 1000.0, "ml": 1.0, "cl": 10.0, "l": 1000.0}


def calculate_for_amount(product, amount, unit):
    """Naehrwerte fuer eine konkrete Menge (z.B. 30 g Nutella).

    Volumen wird vereinfachend als 1 ml = 1 g behandelt.
    Gibt bei ungueltiger Menge/Einheit Nullen zurueck.
    """
    empty = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    if amount is None or amount <= 0 or unit not in _TO_BASE:
        return empty
    amount_in_g = amount * _TO_BASE[unit]
    m = amount_in_g / 100.0
    return {
        "kcal": round(product["kcal_per_100g"] * m, 1),
        "protein": round(product["protein_per_100g"] * m, 1),
        "fat": round(product["fat_per_100g"] * m, 1),
        "carbs": round(product["carbs_per_100g"] * m, 1),
    }
