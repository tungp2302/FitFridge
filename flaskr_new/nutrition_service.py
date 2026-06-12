"""Service für Nährwert-Berechnungen.

Rechnet die "pro 100g"-Nährwerte eines Produkts auf eine konkrete Menge um.
Nutzt calculations.py für die Einheiten-Umrechnung.
"""

from .calculations import convert_units


def calculate_for_amount(product, amount, unit):
    """
    Berechnet die Nährwerte für eine konkrete Menge eines Produkts.

    Die Nährwerte im Produkt sind "pro 100g" gespeichert. Diese Funktion
    rechnet sie auf die tatsächlich verbrauchte/vorhandene Menge um.

    Beispiel:
        nutella = {
            "kcal_per_100g": 539.0,
            "protein_per_100g": 6.3,
            "fat_per_100g": 30.9,
            "carbs_per_100g": 57.5,
        }
        calculate_for_amount(nutella, 30, "g")
        → {"kcal": 161.7, "protein": 1.9, "fat": 9.3, "carbs": 17.3}

    Parameter:
        product (dict): Produkt-Daten mit den Schlüsseln
                        kcal_per_100g, protein_per_100g,
                        fat_per_100g, carbs_per_100g
        amount (float): Menge des Produkts
        unit (str): Einheit der Menge (g, kg, mg, ml, cl, l, stk)

    Returns:
        dict: Dictionary mit den Schlüsseln kcal, protein, fat, carbs.
              Alle Werte auf 1 Nachkommastelle gerundet.
              Bei nicht-berechenbaren Einheiten (z.B. "stk") oder
              ungültiger Menge: alle Werte sind 0.0
    """
    # Leere Nährwerte als Standard-Rückgabe für Edge Cases
    empty_nutrition = {
        "kcal": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0,
    }

    # Edge Case 1: Ungültige Menge
    if amount is None or amount <= 0:
        return empty_nutrition

    # Edge Case 2: Stück-Einheit kann nicht in Gramm umgerechnet werden
    if unit == "stk":
        return empty_nutrition

    # Schritt 1: Menge zu Gramm konvertieren
    # Für Volumen nehmen wir die Vereinfachung 1ml = 1g
    weight_units = ["mg", "g", "kg"]
    volume_units = ["ml", "cl", "l"]

    if unit in weight_units:
        amount_in_g = convert_units(amount, unit, "g")
    elif unit in volume_units:
        # Erst zu ml konvertieren, dann ml als g behandeln (Vereinfachung)
        amount_in_ml = convert_units(amount, unit, "ml")
        amount_in_g = amount_in_ml
    else:
        # Unbekannte Einheit
        return empty_nutrition

    # Schritt 2: Multiplier berechnen (Anteil von 100g)
    multiplier = amount_in_g / 100.0

    # Schritt 3: Nährwerte multiplizieren und runden
    return {
        "kcal": round(product["kcal_per_100g"] * multiplier, 1),
        "protein": round(product["protein_per_100g"] * multiplier, 1),
        "fat": round(product["fat_per_100g"] * multiplier, 1),
        "carbs": round(product["carbs_per_100g"] * multiplier, 1),
    }