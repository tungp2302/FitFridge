"""Einheiten-Umrechnung und Naehrwert-Berechnung."""

_WEIGHT = {"mg": 0.001, "g": 1.0, "kg": 1000.0}
_VOLUME = {"ml": 1.0, "cl": 10.0, "l": 1000.0}


def convert_units(amount, from_unit, to_unit):
    """Rechnet eine Menge innerhalb einer Kategorie um (Gewicht oder Volumen)."""
    for table in (_WEIGHT, _VOLUME):
        if from_unit in table and to_unit in table:
            return amount * table[from_unit] / table[to_unit]
    raise ValueError(f"Cannot convert from '{from_unit}' to '{to_unit}'.")


def calculate_for_amount(product, amount, unit):
    """Naehrwerte fuer eine konkrete Menge (z.B. 30 g Nutella).

    Volumen wird vereinfachend als 1 ml = 1 g behandelt.
    Gibt bei ungueltiger Menge/Einheit Nullen zurueck.
    """
    empty = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    if amount is None or amount <= 0:
        return empty
    if unit in _WEIGHT:
        amount_in_g = convert_units(amount, unit, "g")
    elif unit in _VOLUME:
        amount_in_g = convert_units(amount, unit, "ml")
    else:
        return empty
    m = amount_in_g / 100.0
    return {
        "kcal": round(product["kcal_per_100g"] * m, 1),
        "protein": round(product["protein_per_100g"] * m, 1),
        "fat": round(product["fat_per_100g"] * m, 1),
        "carbs": round(product["carbs_per_100g"] * m, 1),
    }
