"""Rechnet die "pro 100g" eines Produkts auf eine Menge um."""

from .calculations import convert_units


def calculate_for_amount(product, amount, unit):
    """Naehrwerte fuer eine konkrete Menge (z.B. 30 g Nutella).

    Bei ungueltiger Menge oder nicht umrechenbarer Einheit ("stk") sind
    alle Werte 0. Volumen wird vereinfachend als 1 ml = 1 g behandelt.
    """
    empty = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}

    if amount is None or amount <= 0:
        return empty

    # Menge in Gramm umrechnen (Volumen: 1 ml = 1 g)
    if unit in ("mg", "g", "kg"):
        amount_in_g = convert_units(amount, unit, "g")
    elif unit in ("ml", "cl", "l"):
        amount_in_g = convert_units(amount, unit, "ml")
    else:
        return empty

    multiplier = amount_in_g / 100.0
    return {
        "kcal": round(product["kcal_per_100g"] * multiplier, 1),
        "protein": round(product["protein_per_100g"] * multiplier, 1),
        "fat": round(product["fat_per_100g"] * multiplier, 1),
        "carbs": round(product["carbs_per_100g"] * multiplier, 1),
    }