"""Rechnet die /100g-Naehrwerte eines Produkts auf eine konkrete Menge um."""

from .calculations import convert_units


def calculate_for_amount(product, amount, unit):
    """Naehrwerte fuer ``amount`` ``unit`` eines Produkts.

    Volumen wird vereinfachend wie Gewicht behandelt (1 ml = 1 g). Bei
    ungueltiger Menge oder nicht umrechenbarer Einheit (z.B. "stk") sind
    alle Werte 0.0.
    """
    empty = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    if amount is None or amount <= 0:
        return empty

    base_unit = "ml" if unit in ("ml", "cl", "l") else "g"
    try:
        grams = convert_units(amount, unit, base_unit)
    except ValueError:
        return empty

    multiplier = grams / 100.0
    return {
        "kcal": round(product["kcal_per_100g"] * multiplier, 1),
        "protein": round(product["protein_per_100g"] * multiplier, 1),
        "fat": round(product["fat_per_100g"] * multiplier, 1),
        "carbs": round(product["carbs_per_100g"] * multiplier, 1),
    }
