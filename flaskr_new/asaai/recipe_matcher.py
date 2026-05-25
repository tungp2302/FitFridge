"""Recipe Matcher für FitFridge ASaAI-Modul.

Findet Rezepte, die zu den vorhandenen Kühlschrank-Items passen.
Nutzt TheMealDB-Client um Rezepte zu suchen und zu vergleichen.

Hauptfunktion:
- find_recipes_matching_fridge(fridge_items): Hauptlogik
"""

from .meal_db_client import (
    search_recipes_by_ingredient,
    get_recipe_details,
)


def find_recipes_matching_fridge(fridge_items, max_recipes_per_ingredient=5):
    """Findet Rezepte, die zu den vorhandenen Kühlschrank-Items passen.

    Logik:
    1. Für jedes Kühlschrank-Item: suche Rezepte mit dieser Zutat
    2. Für jedes gefundene Rezept: hole Details und prüfe Match
    3. Berechne Match-Score (Anteil verfügbarer Zutaten)
    4. Sortiere nach Score, beste zuerst

    Beispiel:
        fridge = [
            {"name": "chicken", "amount": 500, "unit": "g"},
            {"name": "rice", "amount": 1000, "unit": "g"},
        ]
        matches = find_recipes_matching_fridge(fridge)
        → [
            {
                "recipe": {...},
                "match_score": 0.6,
                "available": ["chicken", "rice"],
                "missing": ["soy sauce", "garlic", "ginger"],
            },
            ...
          ]

    Parameter:
        fridge_items (list): Liste von Items mit mind. "name"-Feld
        max_recipes_per_ingredient (int): Limit pro Zutat, um API-Calls
                                          und Wartezeit zu begrenzen.

    Returns:
        list: Liste von Match-Dictionaries, sortiert nach match_score
              (höchster zuerst). Leere Liste bei keinen Treffern.
    """
    # Edge Case: Leerer Kühlschrank
    if not fridge_items:
        return []

    # Schritt 1: Sammle Rezept-IDs aus allen Kühlschrank-Zutaten
    # Wir nutzen ein Set, um Duplikate zu vermeiden
    candidate_recipe_ids = set()

    for item in fridge_items:
        ingredient_name = item.get("name", "").strip()
        if not ingredient_name:
            continue

        recipes = search_recipes_by_ingredient(ingredient_name)

        # Limit pro Zutat (sonst dauert's ewig)
        for recipe in recipes[:max_recipes_per_ingredient]:
            candidate_recipe_ids.add(recipe["id"])

    # Edge Case: Keine Rezepte gefunden
    if not candidate_recipe_ids:
        return []

    # Schritt 2: Namen der Kühlschrank-Items (kleingeschrieben für Vergleich)
    fridge_names_lower = set()
    for item in fridge_items:
        name = item.get("name", "").strip().lower()
        if name:
            fridge_names_lower.add(name)

    # Schritt 3: Details holen und matchen
    matches = []
    for recipe_id in candidate_recipe_ids:
        recipe = get_recipe_details(recipe_id)
        if not recipe:
            continue

        match_info = calculate_match(recipe, fridge_names_lower)
        matches.append(match_info)

    # Schritt 4: Sortieren nach match_score (höchste zuerst)
    matches.sort(key=lambda m: m["match_score"], reverse=True)

    return matches


def calculate_match(recipe, fridge_names_lower):
    """Berechnet, wie gut ein Rezept zum Kühlschrank-Inhalt passt.

    Vergleicht die Rezept-Zutaten mit den Kühlschrank-Items.
    Match basiert auf Substring-Vergleich der Namen (kleingeschrieben).

    Beispiel:
        recipe hat ["chicken", "soy sauce", "rice", "garlic"]
        fridge hat {"chicken", "rice"}
        → 2 von 4 verfügbar = 0.5 Match-Score
        → missing: ["soy sauce", "garlic"]

    Parameter:
        recipe (dict): Rezept-Daten von parse_recipe()
        fridge_names_lower (set): Set der Kühlschrank-Zutaten (lowercase)

    Returns:
        dict: {
            "recipe": dict,
            "match_score": float (0.0 bis 1.0),
            "available": list,
            "missing": list,
        }
    """
    available = []
    missing = []

    for ingredient in recipe.get("ingredients", []):
        ing_name = ingredient["name"].lower()

        # Match-Logik: ist die Zutat in irgendeinem Kühlschrank-Item enthalten?
        # z.B. "chicken breasts" matched "chicken"
        found = False
        for fridge_name in fridge_names_lower:
            if fridge_name in ing_name or ing_name in fridge_name:
                found = True
                break

        if found:
            available.append(ingredient["name"])
        else:
            missing.append(ingredient["name"])

    total_ingredients = len(available) + len(missing)
    if total_ingredients == 0:
        match_score = 0.0
    else:
        match_score = len(available) / total_ingredients

    return {
        "recipe": recipe,
        "match_score": round(match_score, 2),
        "available": available,
        "missing": missing,
    }