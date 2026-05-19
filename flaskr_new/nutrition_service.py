"""Service für Nährwert-Berechnungen.

Dieses Modul kümmert sich um alle Berechnungen rund um Nährwerte:
- Wie viele Kalorien/Protein/Fett/Carbs hat eine konkrete Menge?
- Wie viel hat der gesamte Kühlschrank?
- Wie viel Prozent eines Tagesziels wurden erreicht?

Es nutzt calculations.py für allgemeine Hilfsberechnungen.
"""

from .calculations import to_percentage, convert_units


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

def calculate_total_for_fridge(items):
    """
    Berechnet die Gesamt-Nährwerte aller Produkte im Kühlschrank.

    Geht durch alle Items, berechnet pro Item die Nährwerte für die
    aktuelle Menge, und summiert alles auf.

    Beispiel:
        items = [
            {"name": "Nutella", "current_amount": 30, "unit": "g",
             "kcal_per_100g": 539.0, "protein_per_100g": 6.3, ...},
            {"name": "Butter", "current_amount": 200, "unit": "g",
             "kcal_per_100g": 717.0, "protein_per_100g": 0.9, ...},
        ]
        calculate_total_for_fridge(items)
        → {"kcal": 1595.7, "protein": 3.7, "fat": 171.3, "carbs": 17.5}

    Parameter:
        items (list): Liste von Fridge-Items (dicts mit current_amount,
                      unit und den Nährwert-Feldern pro 100g)

    Returns:
        dict: Summe der Nährwerte über alle Items.
              Bei leerer Liste: alle Werte 0.0
    """
    # Start: alle Summen auf 0
    total = {
        "kcal": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0,
    }

    # Edge Case: Leere Liste
    if not items:
        return total

    # Durch jedes Item gehen und die Nährwerte aufsummieren
    for item in items:
        nutrition = calculate_for_amount(
            product=item,
            amount=item["current_amount"],
            unit=item["unit"],
        )

        total["kcal"] += nutrition["kcal"]
        total["protein"] += nutrition["protein"]
        total["fat"] += nutrition["fat"]
        total["carbs"] += nutrition["carbs"]

    # Am Ende noch sauber runden
    return {
        "kcal": round(total["kcal"], 1),
        "protein": round(total["protein"], 1),
        "fat": round(total["fat"], 1),
        "carbs": round(total["carbs"], 1),
    }

def calculate_daily_percentage(consumed, daily_target):
    """
    Berechnet, wie viel Prozent des Tagesziels für jeden Nährwert
    erreicht wurden.

    Beispiel:
        consumed = {"kcal": 1200, "protein": 80, "fat": 50, "carbs": 150}
        target = {"kcal": 2000, "protein": 120, "fat": 70, "carbs": 250}
        calculate_daily_percentage(consumed, target)
        → {"kcal": 60.0, "protein": 66.7, "fat": 71.4, "carbs": 60.0}

    Parameter:
        consumed (dict): Bereits verbrauchte Nährwerte
                         mit Schlüsseln kcal, protein, fat, carbs
        daily_target (dict): Tagesziel für jeden Nährwert
                             mit denselben Schlüsseln

    Returns:
        dict: Prozentuale Anteile pro Nährwert (0 bis 100+).
              Auf 1 Nachkommastelle gerundet.
              Werte über 100% sind möglich (= Tagesziel überschritten).
    """
    return {
        "kcal": round(to_percentage(consumed["kcal"], daily_target["kcal"]), 1),
        "protein": round(to_percentage(consumed["protein"], daily_target["protein"]), 1),
        "fat": round(to_percentage(consumed["fat"], daily_target["fat"]), 1),
        "carbs": round(to_percentage(consumed["carbs"], daily_target["carbs"]), 1),
    }