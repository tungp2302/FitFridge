"""Rechnet die /100g-Naehrwerte eines Produkts auf eine konkrete Menge um."""


def convert_units(amount, from_unit, to_unit):
    """Rechnet eine Menge zwischen kompatiblen Einheiten um (Gewicht oder Volumen).

    Gewicht und Volumen lassen sich nicht ineinander umrechnen und loesen
    dann ein ValueError aus.
    """
    weight_units = {"mg": 0.001, "g": 1.0, "kg": 1000.0}
    volume_units = {"ml": 1.0, "cl": 10.0, "l": 1000.0}
    for units in (weight_units, volume_units):
        if from_unit in units and to_unit in units:
            return amount * units[from_unit] / units[to_unit]
    raise ValueError(f"Cannot convert from '{from_unit}' to '{to_unit}'.")


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
