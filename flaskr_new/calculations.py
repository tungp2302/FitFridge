"""Einheiten-Umrechnung fuer Gewicht (mg, g, kg) und Volumen (ml, cl, l)."""


def convert_units(amount, from_unit, to_unit):
    """Rechnet eine Menge zwischen kompatiblen Einheiten um.

    Gewicht und Volumen lassen sich nicht ineinander umrechnen und loesen
    dann ein ValueError aus.
    """
    weight_units = {"mg": 0.001, "g": 1.0, "kg": 1000.0}
    volume_units = {"ml": 1.0, "cl": 10.0, "l": 1000.0}

    for units in (weight_units, volume_units):
        if from_unit in units and to_unit in units:
            return amount * units[from_unit] / units[to_unit]

    raise ValueError(f"Cannot convert from '{from_unit}' to '{to_unit}'.")
