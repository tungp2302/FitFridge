"""TheMealDB-Client für FitFridge ASaAI-Modul.

Dieses Modul kümmert sich um die Kommunikation mit TheMealDB
(https://www.themealdb.com), einer kostenlosen Rezept-API.

Funktionen:
- search_recipes_by_ingredient(ingredient): findet Rezepte mit einer Zutat
- get_recipe_details(recipe_id): holt vollständige Rezept-Daten
- parse_recipe(raw_recipe): wandelt API-Daten in sauberes Format um
"""

import requests


# Basis-URL der API. Der "1" am Ende ist der kostenlose API-Key.
BASE_URL = "https://www.themealdb.com/api/json/v1/1"


def search_recipes_by_ingredient(ingredient):
    """Sucht Rezepte, die eine bestimmte Zutat enthalten.

    Beispiel:
        recipes = search_recipes_by_ingredient("chicken")
        → Liste von Rezepten mit Hähnchen

    Parameter:
        ingredient (str): Name der Zutat (englisch, z.B. "tomato")

    Returns:
        list: Liste von Rezept-IDs und Namen, oder leere Liste bei Fehler.
              Format: [{"id": "52772", "name": "Teriyaki Chicken"}, ...]
    """
    # Edge Case: Leere Eingabe
    if not ingredient or not ingredient.strip():
        return []

    # API-Aufruf
    url = f"{BASE_URL}/filter.php?i={ingredient.strip()}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # wirft Fehler bei HTTP 4xx/5xx
        data = response.json()
    except requests.RequestException as e:
        # Netzwerk-Fehler, Timeout, etc.
        print(f"Fehler beim API-Aufruf: {e}")
        return []

    # API gibt {"meals": null} zurück wenn nichts gefunden
    if not data.get("meals"):
        return []

    # Vereinfachen: nur ID und Name extrahieren
    return [
        {"id": meal["idMeal"], "name": meal["strMeal"]}
        for meal in data["meals"]
    ]


def get_recipe_details(recipe_id):
    """Holt die vollständigen Details zu einem Rezept.

    Beispiel:
        recipe = get_recipe_details("52772")
        → kompletter Datensatz mit Zutaten, Anleitung, Bild

    Parameter:
        recipe_id (str): TheMealDB-ID des Rezepts

    Returns:
        dict: Aufbereitetes Rezept-Dictionary, oder None bei Fehler.
              Siehe parse_recipe() für das Format.
    """
    if not recipe_id:
        return None

    url = f"{BASE_URL}/lookup.php?i={recipe_id}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"Fehler beim API-Aufruf: {e}")
        return None

    if not data.get("meals"):
        return None

    # API gibt immer eine Liste zurück, auch bei einem Treffer
    raw_recipe = data["meals"][0]
    return parse_recipe(raw_recipe)


def parse_recipe(raw_recipe):
    """Wandelt die rohen API-Daten in ein sauberes Format um.

    TheMealDB gibt Zutaten als strIngredient1 bis strIngredient20 und
    Mengen als strMeasure1 bis strMeasure20 zurück. Diese Funktion
    sammelt sie in eine ordentliche Liste und filtert leere Slots raus.

    Parameter:
        raw_recipe (dict): Rohes Rezept-Dictionary von der API

    Returns:
        dict: Sauberes Format:
            {
                "id": str,
                "name": str,
                "category": str,
                "area": str (Herkunftsland),
                "instructions": str,
                "image_url": str,
                "ingredients": [
                    {"name": "Spaghetti", "measure": "200 g"},
                    ...
                ]
            }
    """
    # Zutaten und Mengen aus den 20 Slots zusammensammeln
    ingredients = []
    for i in range(1, 21):  # 1 bis 20 inklusiv
        name = raw_recipe.get(f"strIngredient{i}", "")
        measure = raw_recipe.get(f"strMeasure{i}", "")

        # Leere oder None-Werte überspringen
        if not name or not name.strip():
            continue

        ingredients.append({
            "name": name.strip(),
            "measure": measure.strip() if measure else "",
        })

    return {
        "id": raw_recipe.get("idMeal", ""),
        "name": raw_recipe.get("strMeal", ""),
        "category": raw_recipe.get("strCategory", ""),
        "area": raw_recipe.get("strArea", ""),
        "instructions": raw_recipe.get("strInstructions", ""),
        "image_url": raw_recipe.get("strMealThumb", ""),
        "ingredients": ingredients,
    }