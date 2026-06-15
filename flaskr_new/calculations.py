"""Einheiten-Umrechnung (z.B. kg zu g, l zu ml)."""

def convert_units(amount, from_unit, to_unit):
    """Rechnet eine Menge innerhalb einer Kategorie um.

    Gewicht (mg, g, kg) und Volumen (ml, cl, l) lassen sich jeweils
    untereinander umrechnen. Gewicht <-> Volumen geht nicht (ValueError).
    """
    # Faktoren zur Basiseinheit (Gewicht -> g, Volumen -> ml)
    weight_units = {"mg": 0.001, "g": 1.0, "kg": 1000.0}
    volume_units = {"ml": 1.0, "cl": 10.0, "l": 1000.0}

    if from_unit in weight_units and to_unit in weight_units:
        return amount * weight_units[from_unit] / weight_units[to_unit]

    if from_unit in volume_units and to_unit in volume_units:
        return amount * volume_units[from_unit] / volume_units[to_unit]

    raise ValueError(
        f"Cannot convert from '{from_unit}' to '{to_unit}'. "
        f"Weight units: mg, g, kg, Volume units: ml, cl, l."
    )
