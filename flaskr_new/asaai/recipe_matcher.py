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
import re
import unicodedata
from .macro_calculator import parse_measure_string


# Häufige deutsche Zutatenbegriffe auf TheMealDB-kompatible Suchbegriffe mappen.
GERMAN_INGREDIENT_ALIASES = {
    "hahnchen": ["chicken"],
    "hahhnchen": ["chicken"],
    "hahchen": ["chicken"],
    "huhn": ["chicken"],
    "huhnchen": ["chicken"],
    "hahnchenbrust": ["chicken"],
    "huhnerbrust": ["chicken"],
    "hahnchenschenkel": ["chicken", "chicken thigh"],
    "huhnerschenkel": ["chicken", "chicken thigh"],
    "huhnchenschenkel": ["chicken", "chicken thigh"],
    "haehnchenschenkel": ["chicken", "chicken thigh"],
    "rind": ["beef"],
    "rindfleisch": ["beef"],
    "schwein": ["pork"],
    "schweinefleisch": ["pork"],
    "kartoffel": ["potato"],
    "kartoffeln": ["potato"],
    "zwiebel": ["onion"],
    "zwiebeln": ["onion"],
    "knoblauch": ["garlic"],
    "tomate": ["tomato"],
    "tomaten": ["tomato"],
    "reis": ["rice"],
    "nudel": ["pasta"],
    "nudeln": ["pasta"],
    "kase": ["cheese"],
    "milch": ["milk"],
    "ei": ["egg"],
    "eier": ["egg"],
    "paprika": ["pepper"],
    "gurke": ["cucumber"],
    "karotte": ["carrot"],
    "mohre": ["carrot"],
    "brokkoli": ["broccoli"],
    "spinat": ["spinach"],
    "pilz": ["mushroom"],
    "champignon": ["mushroom"],
    "fisch": ["fish"],
    "lachs": ["salmon"],
    "thunfisch": ["tuna"],
    "garnele": ["shrimp"],
    "garnelen": ["shrimp"],
    "bohne": ["beans"],
    "bohnen": ["beans"],
    "linse": ["lentils"],
    "linsen": ["lentils"],
    "kichererbse": ["chickpeas"],
    "kichererbsen": ["chickpeas"],
}


# Pantry-Basics sollen Rezepte nicht dominieren: weniger Gewicht beim Matching.
PANTRY_STAPLES = {
    "oil",
    "olive oil",
    "vegetable oil",
    "sunflower oil",
    "onion",
    "onions",
    "garlic",
    "salt",
    "pepper",
    "black pepper",
}

STAPLE_WEIGHT = 0.25


PROTEIN_KEYWORDS = {
    "chicken",
    "chicken thigh",
    "turkey",
    "beef",
    "pork",
    "lamb",
    "fish",
    "salmon",
    "tuna",
    "shrimp",
    "egg",
    "eggs",
    "tofu",
    "tempeh",
    "beans",
    "lentils",
    "chickpeas",
    "quark",
    "cottage cheese",
    "yogurt",
    "skyr",
}


# Näherungswerte pro 100g (Protein g, kcal)
_PROTEIN_NUTRITION_DB = {
    "chicken": (27.0, 239.0),
    "chicken thigh": (26.0, 240.0),
    "beef": (26.0, 250.0),
    "pork": (25.0, 242.0),
    "lamb": (25.0, 294.0),
    "fish": (22.0, 206.0),
    "salmon": (20.0, 208.0),
    "tuna": (23.0, 132.0),
    "shrimp": (24.0, 99.0),
    "egg": (13.0, 155.0),
    "tofu": (8.0, 76.0),
    "beans": (9.0, 127.0),
    "lentils": (9.0, 116.0),
    "chickpeas": (19.0, 364.0),
    "cheese": (25.0, 400.0),
}


def _normalize_text(value):
    """Normalisiert Zutatennamen für robustes Matching."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _expand_aliases(name):
    """Erweitert einen Zutatennamen um Synonyme (z.B. Deutsch -> Englisch)."""
    normalized = _normalize_text(name)
    if not normalized:
        return set()

    tokens = normalized.split()
    aliases = {normalized, *tokens}

    for token in tokens:
        mapped = GERMAN_INGREDIENT_ALIASES.get(token, [])
        aliases.update(mapped)

    mapped_full = GERMAN_INGREDIENT_ALIASES.get(normalized, [])
    aliases.update(mapped_full)

    # Leere Tokens vermeiden.
    return {alias for alias in aliases if alias}


def _build_search_terms(fridge_items):
    """Baut API-Suchbegriffe aus Kühlschrankdaten (inkl. Aliasen)."""
    search_terms = set()
    for item in fridge_items:
        for alias in _expand_aliases(item.get("name", "")):
            # Sehr kurze Tokens verursachen oft Rauschen in filter.php
            if len(alias) >= 3 and not _is_staple(alias):
                search_terms.add(alias)
    return search_terms


def _build_fridge_alias_set(fridge_items):
    """Alias-Set aller Kühlschrank-Zutaten für den späteren Rezeptabgleich."""
    aliases = set()
    for item in fridge_items:
        aliases.update(_expand_aliases(item.get("name", "")))
    return aliases


def _is_staple(name):
    """True wenn die Zutat als Pantry-Basic gilt."""
    normalized = _normalize_text(name)
    if not normalized:
        return False

    if normalized in PANTRY_STAPLES:
        return True

    tokens = set(normalized.split())
    staple_tokens = set()
    for staple in PANTRY_STAPLES:
        staple_tokens.update(staple.split())

    # Token-basierter Fallback, damit z.B. "fresh garlic" erkannt wird.
    return bool(tokens & staple_tokens)


def find_recipes_matching_fridge(fridge_items, max_recipes_per_ingredient=5, daily_goal=None):
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
    search_terms = _build_search_terms(fridge_items)

    for ingredient_name in search_terms:
        recipes = search_recipes_by_ingredient(ingredient_name)

        # Limit pro Zutat (sonst dauert's ewig)
        for recipe in recipes[:max_recipes_per_ingredient]:
            candidate_recipe_ids.add(recipe["id"])

    # Edge Case: Keine Rezepte gefunden
    if not candidate_recipe_ids:
        return []

    # Schritt 2: Alias-Set aus Kühlschranknamen (inkl. DE->EN)
    fridge_names_lower = _build_fridge_alias_set(fridge_items)

    # Schritt 3: Details holen und matchen
    matches = []
    for recipe_id in candidate_recipe_ids:
        recipe = get_recipe_details(recipe_id)
        if not recipe:
            continue

        match_info = calculate_match(recipe, fridge_names_lower)
        # Estimate protein density for ranking (fast heuristic)
        est_protein, est_kcal = _estimate_recipe_protein_and_kcal(recipe)
        match_info["est_protein"] = round(est_protein, 1)
        match_info["est_kcal"] = round(est_kcal, 1)
        match_info["protein_per_100kcal"] = (
            round((est_protein * 100.0 / est_kcal), 2) if est_kcal > 0 else 0.0
        )
        # Boost protein priority score by density as well
        match_info["protein_priority_score"] = (
            match_info.get("protein_priority_score", 0) + match_info["protein_per_100kcal"]
        )
        # Nur echte Überschneidungen zurückgeben.
        if match_info["available"]:
            matches.append(match_info)

    # Schritt 4: Sortieren nach realem Nutzen.
    # Bei Proteinziel priorisieren wir Rezepte mit mehr Proteinquellen.
    protein_target = (daily_goal or {}).get("protein", 0) if isinstance(daily_goal, dict) else 0
    if protein_target and protein_target > 0:
        matches.sort(
            key=lambda m: (
                m.get("protein_priority_score", 0),
                len(m["available"]),
                m["match_score"],
                -len(m["missing"]),
            ),
            reverse=True,
        )
    else:
        matches.sort(
            key=lambda m: (len(m["available"]), m["match_score"], -len(m["missing"])),
            reverse=True,
        )

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
    available_staples = []
    missing_staples = []
    available_protein_sources = []

    expanded_fridge_names = set()
    for fridge_name in fridge_names_lower:
        expanded_fridge_names.update(_expand_aliases(fridge_name))

    for ingredient in recipe.get("ingredients", []):
        ing_raw = ingredient["name"]
        ing_name = _normalize_text(ing_raw)
        ing_tokens = set(ing_name.split())
        is_staple = _is_staple(ing_name)

        # Match-Logik: ist die Zutat in irgendeinem Kühlschrank-Item enthalten?
        # z.B. "chicken breasts" matched "chicken"
        found = False
        for fridge_name in expanded_fridge_names:
            fridge_norm = _normalize_text(fridge_name)
            if not fridge_norm:
                continue

            if fridge_norm in ing_name or ing_name in fridge_norm:
                found = True
                break

            # Token-Überlappung als Fallback (z.B. "chicken" vs "chicken breasts")
            if fridge_norm in ing_tokens:
                found = True
                break

        if found and is_staple:
            available_staples.append(ing_raw)
        elif found:
            available.append(ing_raw)
            if _is_protein_source(ing_name):
                available_protein_sources.append(ing_raw)
        elif is_staple:
            missing_staples.append(ing_raw)
        else:
            missing.append(ing_raw)

    matched_weight = len(available) + (len(available_staples) * STAPLE_WEIGHT)
    total_weight = (
        len(available)
        + len(missing)
        + ((len(available_staples) + len(missing_staples)) * STAPLE_WEIGHT)
    )

    if total_weight == 0:
        match_score = 0.0
    else:
        match_score = matched_weight / total_weight

    return {
        "recipe": recipe,
        "match_score": round(match_score, 2),
        "available": available,
        "missing": missing,
        "available_staples": available_staples,
        "missing_staples": missing_staples,
        "available_protein_sources": available_protein_sources,
        "protein_priority_score": len(available_protein_sources),
    }


def _is_protein_source(name):
    """Heuristik für proteinreiche Zutaten zur Ziel-Priorisierung."""
    normalized = _normalize_text(name)
    if not normalized:
        return False

    if normalized in PROTEIN_KEYWORDS:
        return True

    tokens = set(normalized.split())
    protein_tokens = set()
    for keyword in PROTEIN_KEYWORDS:
        protein_tokens.update(keyword.split())

    return bool(tokens & protein_tokens)


def _estimate_recipe_protein_and_kcal(recipe):
    """Rough estimate of total protein and kcal for a recipe using ingredient heuristics.

    Uses parse_measure_string to convert measures to grams and multiplies
    by approximate per-100g values in _PROTEIN_NUTRITION_DB.
    """
    total_protein = 0.0
    total_kcal = 0.0

    for ing in recipe.get("ingredients", []):
        name = _normalize_text(ing.get("name", ""))
        measure = ing.get("measure", "")
        amount, unit = parse_measure_string(measure)

        # If measure returned in ml (unit == 'ml'), try to treat as grams (approx)
        grams = amount if unit == "g" else amount if unit == "ml" else amount

        # Find a matching nutrition profile
        matched = False
        for key, (prot100, kcal100) in _PROTEIN_NUTRITION_DB.items():
            if key in name:
                matched = True
                total_protein += prot100 * (grams / 100.0)
                total_kcal += kcal100 * (grams / 100.0)
                break

        # If no specific match, skip (we avoid heavy lookups here)
        if not matched:
            continue

    return total_protein, total_kcal