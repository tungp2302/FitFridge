"""Macro-Calculator für Rezepte.

Berechnet die Nährwerte (kcal, Protein, Fett, Carbs) für TheMealDB-Rezepte
und ranked sie nach dem verbleibenden Tagesziel des Nutzers.

Architektur:
- Nutzt Tungs openfoodfacts_client für Zutaten-Daten
- Nutzt Raams nutrition_service.calculate_for_amount für Mengen-Berechnung
- Cached Ergebnisse, um wiederholte API-Calls zu vermeiden

Hauptfunktionen:
- parse_measure_string(measure): "200 g" → (200.0, "g")
- calculate_ingredient_macros(name, measure): pro Zutat
- calculate_recipe_macros(recipe): pro Rezept
- rank_by_daily_goal(matches, daily_goal): sortiert Matches
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from ..openfoodfacts_client import lookup_product
from ..nutrition_service import calculate_for_amount
from .ingredient_macros import lookup_ingredient


# Cache für OpenFoodFacts-Lookups (vermeidet doppelte API-Calls)
_INGREDIENT_CACHE = {}


# Standard-Umrechnungen für US-Einheiten (in Gramm/Milliliter)
# Quelle: typische Kochbuch-Konventionen
UNIT_CONVERSIONS = {
    "cup": 240.0,        # 1 Cup ≈ 240ml
    "cups": 240.0,
    "tablespoon": 15.0,  # 1 EL ≈ 15ml
    "tablespoons": 15.0,
    "tbsp": 15.0,
    "teaspoon": 5.0,     # 1 TL ≈ 5ml
    "teaspoons": 5.0,
    "tsp": 5.0,
    "oz": 28.35,         # 1 Ounce ≈ 28.35g
    "ounce": 28.35,
    "ounces": 28.35,
    "lb": 453.59,        # 1 Pfund ≈ 453.59g
    "pound": 453.59,
    "pounds": 453.59,
}


def parse_measure_string(measure: str) -> Tuple[float, str]:
    """Parst einen TheMealDB-Mengen-String in (Wert, Einheit).

    Beispiele:
        "200 g" → (200.0, "g")
        "1 cup" → (240.0, "ml")
        "3/4 cup" → (180.0, "ml")
        "1/2 teaspoon" → (2.5, "ml")
        "2 chicken breasts" → (400.0, "g")  # Default: 200g pro Stück
        "to taste" → (0.0, "g")  # Wird ignoriert
        "" → (0.0, "g")

    Parameter:
        measure (str): Mengen-String wie von TheMealDB geliefert

    Returns:
        Tuple[float, str]: (Menge in Standard-Einheit, Einheit als "g" oder "ml")
    """
    if not measure or not measure.strip():
        return (0.0, "g")

    text = measure.strip().lower()

    # Edge Case: "to taste", "as needed", etc. → ignorieren
    if "taste" in text or "needed" in text or "optional" in text:
        return (0.0, "g")

    # Bruch-Pattern: "3/4 cup" → 0.75 cup
    fraction_match = re.match(r"^(\d+)/(\d+)\s+(.+)$", text)
    if fraction_match:
        numerator = float(fraction_match.group(1))
        denominator = float(fraction_match.group(2))
        rest = fraction_match.group(3)
        value = numerator / denominator
        return _convert_unit(value, rest)

    # Mixed-Number: "1 1/2 cup" → 1.5 cup
    mixed_match = re.match(r"^(\d+)\s+(\d+)/(\d+)\s+(.+)$", text)
    if mixed_match:
        whole = float(mixed_match.group(1))
        numerator = float(mixed_match.group(2))
        denominator = float(mixed_match.group(3))
        rest = mixed_match.group(4)
        value = whole + (numerator / denominator)
        return _convert_unit(value, rest)

    # Standard: "200 g", "1 cup", "2 chicken breasts"
    standard_match = re.match(r"^(\d+(?:\.\d+)?)\s*(.+)$", text)
    if standard_match:
        value = float(standard_match.group(1))
        rest = standard_match.group(2)
        return _convert_unit(value, rest)

    # Wenn nichts passt: 0
    return (0.0, "g")


def _convert_unit(value: float, unit_text: str) -> Tuple[float, str]:
    """Konvertiert eine Einheit zur Standard-Einheit (g oder ml).

    Interne Helper-Funktion. Erkennt:
    - Direkte Einheiten: g, kg, mg, ml, l, cl
    - US-Einheiten: cup, tablespoon, teaspoon, oz, lb
    - Zähleinheiten: piece, breasts, cloves → Default 200g pro Stück

    Parameter:
        value (float): Numerischer Wert
        unit_text (str): Einheit + ggf. Zutat-Name

    Returns:
        Tuple[float, str]: (Wert in g/ml, "g" oder "ml")
    """
    unit_text = unit_text.strip().lower()

    # Direkte Gewichts-Einheiten
    if unit_text.startswith("g ") or unit_text == "g" or "gram" in unit_text:
        return (value, "g")
    if unit_text.startswith("kg") or "kilogram" in unit_text:
        return (value * 1000.0, "g")
    if unit_text.startswith("mg") or "milligram" in unit_text:
        return (value / 1000.0, "g")

    # Direkte Volumen-Einheiten
    if unit_text.startswith("ml") or "millilit" in unit_text:
        return (value, "ml")
    if unit_text.startswith("l ") or unit_text == "l" or "liter" in unit_text or "litre" in unit_text:
        return (value * 1000.0, "ml")
    if unit_text.startswith("cl"):
        return (value * 10.0, "ml")

    # US-Einheiten
    for us_unit, conversion in UNIT_CONVERSIONS.items():
        if us_unit in unit_text:
            # Cup, Tablespoon, Teaspoon → Volumen (ml)
            if us_unit in ("cup", "cups", "tablespoon", "tablespoons", "tbsp",
                          "teaspoon", "teaspoons", "tsp"):
                return (value * conversion, "ml")
            # Oz, Pound → Gewicht (g)
            return (value * conversion, "g")

    # Zähleinheiten: "2 chicken breasts", "3 cloves"
    # Default: 200g pro Stück (grobe Schätzung)
    return (value * 200.0, "g")


def calculate_ingredient_macros(name: str, measure: str) -> dict:
    """Berechnet die Macros für eine einzelne Zutat.

    Beispiel:
        calculate_ingredient_macros("chicken breasts", "200 g")
        → {"kcal": 330.0, "protein": 62.0, "fat": 7.2, "carbs": 0.0}

    Parameter:
        name (str): Name der Zutat (englisch, wie von TheMealDB)
        measure (str): Mengen-String wie "200 g"

    Returns:
        dict: {"kcal": float, "protein": float, "fat": float, "carbs": float}
              Alle Werte 0.0 wenn Zutat nicht gefunden oder Menge unbekannt.
    """
    # Edge Case: Leere Eingaben
    if not name or not name.strip():
        return _empty_macros()

    # Schritt 1: Menge parsen
    amount, unit = parse_measure_string(measure)
    if amount <= 0:
        return _empty_macros()

    # Schritt 2: Zutat in OpenFoodFacts nachschlagen (mit Cache)
    # Schritt 2: Zutat nachschlagen
    name_lower = name.strip().lower()

    # 2a: Erst in kuratierter DB (genauer!)
    product_data = lookup_ingredient(name_lower)

    # 2b: Falls nicht gefunden, OpenFoodFacts als Fallback (mit Cache)
    if product_data is None:
        if name_lower in _INGREDIENT_CACHE:
            product_data = _INGREDIENT_CACHE[name_lower]
        else:
            try:
                product_data = lookup_product(name_lower)
            except Exception:
                product_data = None
            _INGREDIENT_CACHE[name_lower] = product_data

    # Edge Case: Zutat nicht gefunden
    if product_data is None:
        return _empty_macros()

    # Schritt 3: Macros mit Raams calculate_for_amount berechnen
    macros = calculate_for_amount(product_data, amount, unit)
    return macros


def calculate_recipe_macros(recipe: dict) -> dict:
    """Berechnet die Gesamt-Macros eines Rezepts.

    Geht alle Zutaten durch, berechnet pro Zutat die Macros mit
    calculate_ingredient_macros() und summiert auf.

    Beispiel:
        recipe = {
            "ingredients": [
                {"name": "chicken breasts", "measure": "2"},
                {"name": "rice", "measure": "200 g"},
                ...
            ]
        }
        calculate_recipe_macros(recipe)
        → {"kcal": 1450.0, "protein": 85.0, "fat": 45.0, "carbs": 120.0}

    Parameter:
        recipe (dict): Rezept-Dict wie von meal_db_client.parse_recipe()

    Returns:
        dict: Summe der Macros über alle Zutaten
    """
    total = _empty_macros()

    for ingredient in recipe.get("ingredients", []):
        name = ingredient.get("name", "")
        measure = ingredient.get("measure", "")

        macros = calculate_ingredient_macros(name, measure)
        total["kcal"] += macros["kcal"]
        total["protein"] += macros["protein"]
        total["fat"] += macros["fat"]
        total["carbs"] += macros["carbs"]

    # Auf 1 Nachkommastelle runden
    return {
        "kcal": round(total["kcal"], 1),
        "protein": round(total["protein"], 1),
        "fat": round(total["fat"], 1),
        "carbs": round(total["carbs"], 1),
    }


def rank_by_daily_goal(matches_with_macros: list, daily_goal: dict) -> list:
    """Sortiert Matches nach Passung zum Tagesziel.

    Logik: Ein Rezept ist "gut", wenn es die fehlenden Macros (besonders
    Protein) gut auffüllt, ohne kcal-Limit zu überschreiten.

    Score-Formel (vereinfacht):
        - Protein-Match: wie nah kommt das Rezept an das verbleibende Proteinziel?
        - kcal-Penalty: wenn Rezept > daily_goal["kcal"], Strafpunkte

    Beispiel:
        daily_goal = {"protein": 30, "kcal": 600}
        matches = [{"recipe": ..., "macros": {"protein": 28, "kcal": 550}}, ...]
        → sortiert nach Goal-Match-Score

    Parameter:
        matches_with_macros (list): Liste mit Recipe + Macros
        daily_goal (dict): Verbleibendes Tagesziel

    Returns:
        list: Gleiche Liste, sortiert nach goal_score (höchste zuerst)
    """
    if not daily_goal:
        return matches_with_macros

    target_protein = daily_goal.get("protein", 0)
    target_kcal = daily_goal.get("kcal", 0)

    for match in matches_with_macros:
        macros = match.get("macros", {})
        recipe_protein = macros.get("protein", 0)
        recipe_kcal = macros.get("kcal", 0)

        # Score-Logik: höher = besser
        score = 0.0

        # Protein-Match: Bonus wenn Rezept zwischen 80-120% des Ziels liegt
        if target_protein > 0:
            ratio = recipe_protein / target_protein
            if 0.8 <= ratio <= 1.2:
                score += 1.0  # perfect match
            elif 0.5 <= ratio < 0.8:
                score += 0.7  # underwhelming
            elif 1.2 < ratio <= 1.5:
                score += 0.5  # slightly over
            else:
                score += 0.2  # weit daneben

        # kcal-Penalty: wenn Rezept > target_kcal
        if target_kcal > 0 and recipe_kcal > target_kcal:
            penalty = (recipe_kcal - target_kcal) / target_kcal
            score -= min(penalty, 1.0)  # max 1.0 Penalty

        match["goal_score"] = round(score, 2)

    matches_with_macros.sort(key=lambda m: m.get("goal_score", 0), reverse=True)
    return matches_with_macros


def _empty_macros() -> dict:
    """Helper: gibt ein leeres Macro-Dict zurück."""
    return {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}