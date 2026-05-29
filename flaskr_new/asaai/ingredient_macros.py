"""Kuratierte Nährwert-Datenbank für häufige Rezept-Zutaten.

Werte pro 100g, aus verlässlichen Quellen (USDA FoodData Central,
Nährwerttabellen). Dient als genauere Alternative zu OpenFoodFacts
für generische Zutaten-Namen.

Verwendung:
    from .ingredient_macros import lookup_ingredient
    macros = lookup_ingredient("chicken")
    # → {"kcal_per_100g": 165, "protein_per_100g": 31, ...}

Wenn eine Zutat nicht in dieser Tabelle ist, fällt macro_calculator
auf OpenFoodFacts zurück.
"""

from __future__ import annotations


# Nährwerte pro 100g (roh/ungekocht wo nicht anders angegeben)
# Format: kcal, protein, fat, carbs
INGREDIENT_DB = {
    # === Fleisch & Geflügel ===
    "chicken": {"kcal_per_100g": 165, "protein_per_100g": 31.0, "fat_per_100g": 3.6, "carbs_per_100g": 0.0},
    "chicken breast": {"kcal_per_100g": 165, "protein_per_100g": 31.0, "fat_per_100g": 3.6, "carbs_per_100g": 0.0},
    "chicken thigh": {"kcal_per_100g": 209, "protein_per_100g": 26.0, "fat_per_100g": 11.0, "carbs_per_100g": 0.0},
    "beef": {"kcal_per_100g": 250, "protein_per_100g": 26.0, "fat_per_100g": 15.0, "carbs_per_100g": 0.0},
    "ground beef": {"kcal_per_100g": 254, "protein_per_100g": 26.0, "fat_per_100g": 15.0, "carbs_per_100g": 0.0},
    "minced beef": {"kcal_per_100g": 254, "protein_per_100g": 26.0, "fat_per_100g": 15.0, "carbs_per_100g": 0.0},
    "pork": {"kcal_per_100g": 242, "protein_per_100g": 27.0, "fat_per_100g": 14.0, "carbs_per_100g": 0.0},
    "bacon": {"kcal_per_100g": 541, "protein_per_100g": 37.0, "fat_per_100g": 42.0, "carbs_per_100g": 1.4},
    "sausage": {"kcal_per_100g": 301, "protein_per_100g": 12.0, "fat_per_100g": 27.0, "carbs_per_100g": 2.0},
    "chorizo": {"kcal_per_100g": 455, "protein_per_100g": 24.0, "fat_per_100g": 38.0, "carbs_per_100g": 2.0},
    "lamb": {"kcal_per_100g": 294, "protein_per_100g": 25.0, "fat_per_100g": 21.0, "carbs_per_100g": 0.0},
    "turkey": {"kcal_per_100g": 135, "protein_per_100g": 29.0, "fat_per_100g": 1.7, "carbs_per_100g": 0.0},

    # === Fisch & Meeresfrüchte ===
    "salmon": {"kcal_per_100g": 208, "protein_per_100g": 20.0, "fat_per_100g": 13.0, "carbs_per_100g": 0.0},
    "tuna": {"kcal_per_100g": 144, "protein_per_100g": 30.0, "fat_per_100g": 1.0, "carbs_per_100g": 0.0},
    "cod": {"kcal_per_100g": 82, "protein_per_100g": 18.0, "fat_per_100g": 0.7, "carbs_per_100g": 0.0},
    "shrimp": {"kcal_per_100g": 99, "protein_per_100g": 24.0, "fat_per_100g": 0.3, "carbs_per_100g": 0.2},
    "prawns": {"kcal_per_100g": 99, "protein_per_100g": 24.0, "fat_per_100g": 0.3, "carbs_per_100g": 0.2},

    # === Kohlenhydrate & Getreide ===
    "rice": {"kcal_per_100g": 130, "protein_per_100g": 2.7, "fat_per_100g": 0.3, "carbs_per_100g": 28.0},
    "white rice": {"kcal_per_100g": 130, "protein_per_100g": 2.7, "fat_per_100g": 0.3, "carbs_per_100g": 28.0},
    "brown rice": {"kcal_per_100g": 111, "protein_per_100g": 2.6, "fat_per_100g": 0.9, "carbs_per_100g": 23.0},
    "pasta": {"kcal_per_100g": 131, "protein_per_100g": 5.0, "fat_per_100g": 1.1, "carbs_per_100g": 25.0},
    "spaghetti": {"kcal_per_100g": 131, "protein_per_100g": 5.0, "fat_per_100g": 1.1, "carbs_per_100g": 25.0},
    "noodles": {"kcal_per_100g": 138, "protein_per_100g": 4.5, "fat_per_100g": 2.1, "carbs_per_100g": 25.0},
    "bread": {"kcal_per_100g": 265, "protein_per_100g": 9.0, "fat_per_100g": 3.2, "carbs_per_100g": 49.0},
    "flour": {"kcal_per_100g": 364, "protein_per_100g": 10.0, "fat_per_100g": 1.0, "carbs_per_100g": 76.0},
    "potato": {"kcal_per_100g": 77, "protein_per_100g": 2.0, "fat_per_100g": 0.1, "carbs_per_100g": 17.0},
    "potatoes": {"kcal_per_100g": 77, "protein_per_100g": 2.0, "fat_per_100g": 0.1, "carbs_per_100g": 17.0},
    "oats": {"kcal_per_100g": 389, "protein_per_100g": 17.0, "fat_per_100g": 7.0, "carbs_per_100g": 66.0},
    "couscous": {"kcal_per_100g": 112, "protein_per_100g": 3.8, "fat_per_100g": 0.2, "carbs_per_100g": 23.0},
    "quinoa": {"kcal_per_100g": 120, "protein_per_100g": 4.4, "fat_per_100g": 1.9, "carbs_per_100g": 21.0},

    # === Milchprodukte & Eier ===
    "milk": {"kcal_per_100g": 47, "protein_per_100g": 3.4, "fat_per_100g": 1.6, "carbs_per_100g": 4.7},
    "butter": {"kcal_per_100g": 717, "protein_per_100g": 0.9, "fat_per_100g": 81.0, "carbs_per_100g": 0.1},
    "cheese": {"kcal_per_100g": 402, "protein_per_100g": 25.0, "fat_per_100g": 33.0, "carbs_per_100g": 1.3},
    "cheddar": {"kcal_per_100g": 402, "protein_per_100g": 25.0, "fat_per_100g": 33.0, "carbs_per_100g": 1.3},
    "parmesan": {"kcal_per_100g": 431, "protein_per_100g": 38.0, "fat_per_100g": 29.0, "carbs_per_100g": 4.1},
    "mozzarella": {"kcal_per_100g": 280, "protein_per_100g": 28.0, "fat_per_100g": 17.0, "carbs_per_100g": 3.1},
    "cream": {"kcal_per_100g": 340, "protein_per_100g": 2.1, "fat_per_100g": 36.0, "carbs_per_100g": 2.8},
    "yogurt": {"kcal_per_100g": 59, "protein_per_100g": 10.0, "fat_per_100g": 0.4, "carbs_per_100g": 3.6},
    "egg": {"kcal_per_100g": 155, "protein_per_100g": 13.0, "fat_per_100g": 11.0, "carbs_per_100g": 1.1},
    "eggs": {"kcal_per_100g": 155, "protein_per_100g": 13.0, "fat_per_100g": 11.0, "carbs_per_100g": 1.1},

    # === Gemüse ===
    "onion": {"kcal_per_100g": 40, "protein_per_100g": 1.1, "fat_per_100g": 0.1, "carbs_per_100g": 9.3},
    "onions": {"kcal_per_100g": 40, "protein_per_100g": 1.1, "fat_per_100g": 0.1, "carbs_per_100g": 9.3},
    "garlic": {"kcal_per_100g": 149, "protein_per_100g": 6.4, "fat_per_100g": 0.5, "carbs_per_100g": 33.0},
    "tomato": {"kcal_per_100g": 18, "protein_per_100g": 0.9, "fat_per_100g": 0.2, "carbs_per_100g": 3.9},
    "tomatoes": {"kcal_per_100g": 18, "protein_per_100g": 0.9, "fat_per_100g": 0.2, "carbs_per_100g": 3.9},
    "carrot": {"kcal_per_100g": 41, "protein_per_100g": 0.9, "fat_per_100g": 0.2, "carbs_per_100g": 10.0},
    "carrots": {"kcal_per_100g": 41, "protein_per_100g": 0.9, "fat_per_100g": 0.2, "carbs_per_100g": 10.0},
    "pepper": {"kcal_per_100g": 31, "protein_per_100g": 1.0, "fat_per_100g": 0.3, "carbs_per_100g": 6.0},
    "bell pepper": {"kcal_per_100g": 31, "protein_per_100g": 1.0, "fat_per_100g": 0.3, "carbs_per_100g": 6.0},
    "mushroom": {"kcal_per_100g": 22, "protein_per_100g": 3.1, "fat_per_100g": 0.3, "carbs_per_100g": 3.3},
    "mushrooms": {"kcal_per_100g": 22, "protein_per_100g": 3.1, "fat_per_100g": 0.3, "carbs_per_100g": 3.3},
    "spinach": {"kcal_per_100g": 23, "protein_per_100g": 2.9, "fat_per_100g": 0.4, "carbs_per_100g": 3.6},
    "broccoli": {"kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7.0},
    "peas": {"kcal_per_100g": 81, "protein_per_100g": 5.4, "fat_per_100g": 0.4, "carbs_per_100g": 14.0},
    "corn": {"kcal_per_100g": 86, "protein_per_100g": 3.2, "fat_per_100g": 1.2, "carbs_per_100g": 19.0},

    # === Obst ===
    "banana": {"kcal_per_100g": 89, "protein_per_100g": 1.1, "fat_per_100g": 0.3, "carbs_per_100g": 22.8},
    "bananas": {"kcal_per_100g": 89, "protein_per_100g": 1.1, "fat_per_100g": 0.3, "carbs_per_100g": 22.8},

    # === Hülsenfrüchte ===
    "beans": {"kcal_per_100g": 127, "protein_per_100g": 8.7, "fat_per_100g": 0.5, "carbs_per_100g": 23.0},
    "lentils": {"kcal_per_100g": 116, "protein_per_100g": 9.0, "fat_per_100g": 0.4, "carbs_per_100g": 20.0},
    "chickpeas": {"kcal_per_100g": 164, "protein_per_100g": 8.9, "fat_per_100g": 2.6, "carbs_per_100g": 27.0},

    # === Öle & Fette ===
    "oil": {"kcal_per_100g": 884, "protein_per_100g": 0.0, "fat_per_100g": 100.0, "carbs_per_100g": 0.0},
    "olive oil": {"kcal_per_100g": 884, "protein_per_100g": 0.0, "fat_per_100g": 100.0, "carbs_per_100g": 0.0},
    "vegetable oil": {"kcal_per_100g": 884, "protein_per_100g": 0.0, "fat_per_100g": 100.0, "carbs_per_100g": 0.0},

    # === Würzmittel & Saucen (geringe Mengen, niedrige Macros) ===
    "soy sauce": {"kcal_per_100g": 53, "protein_per_100g": 8.1, "fat_per_100g": 0.0, "carbs_per_100g": 4.9},
    "sugar": {"kcal_per_100g": 387, "protein_per_100g": 0.0, "fat_per_100g": 0.0, "carbs_per_100g": 100.0},
    "honey": {"kcal_per_100g": 304, "protein_per_100g": 0.3, "fat_per_100g": 0.0, "carbs_per_100g": 82.0},
    "salt": {"kcal_per_100g": 0, "protein_per_100g": 0.0, "fat_per_100g": 0.0, "carbs_per_100g": 0.0},
}


def lookup_ingredient(name):
    """Schlägt eine Zutat in der kuratierten Datenbank nach.

    Nutzt Substring-Matching: "chicken breasts" findet "chicken breast"
    oder "chicken".

    Parameter:
        name (str): Name der Zutat (englisch)

    Returns:
        dict | None: Nährwerte pro 100g, oder None wenn nicht gefunden
    """
    if not name:
        return None

    name_lower = name.strip().lower()

    # Exakter Treffer
    if name_lower in INGREDIENT_DB:
        return dict(INGREDIENT_DB[name_lower])

    # Substring-Matching: Suche die spezifischste Übereinstimmung
    # (längster passender Key gewinnt, damit "chicken breast" vor "chicken")
    best_match = None
    best_length = 0

    for key in INGREDIENT_DB:
        # Prüfe ob der DB-Key im Zutat-Namen vorkommt ODER umgekehrt
        if key in name_lower or name_lower in key:
            if len(key) > best_length:
                best_match = key
                best_length = len(key)

    if best_match:
        return dict(INGREDIENT_DB[best_match])

    return None