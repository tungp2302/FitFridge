"""Tests für recipe_matcher.py.

Diese Tests prüfen die deterministische Logik des Matchers.
LLM-Aufrufe werden hier NICHT getestet, das passiert in separaten Tests.
"""

from flaskr_new.asaai.recipe_matcher import (
    find_recipes_matching_fridge,
    calculate_match,
)


def test_empty_fridge_returns_empty_list():
    """Ein leerer Kühlschrank gibt eine leere Liste zurück."""
    result = find_recipes_matching_fridge([])
    assert result == []


def test_calculate_match_perfect():
    """Wenn alle Rezept-Zutaten im Kühlschrank sind, ist Score 1.0."""
    recipe = {
        "ingredients": [
            {"name": "chicken", "measure": "200 g"},
            {"name": "rice", "measure": "100 g"},
        ],
    }
    fridge_names = {"chicken", "rice"}

    result = calculate_match(recipe, fridge_names)

    assert result["match_score"] == 1.0
    assert len(result["available"]) == 2
    assert len(result["missing"]) == 0


def test_calculate_match_partial():
    """Wenn nur einige Zutaten da sind, ist Score < 1.0."""
    recipe = {
        "ingredients": [
            {"name": "chicken", "measure": "200 g"},
            {"name": "rice", "measure": "100 g"},
            {"name": "ginger", "measure": "1 clove"},
            {"name": "soy sauce", "measure": "2 tbsp"},
        ],
    }
    fridge_names = {"chicken", "rice"}

    result = calculate_match(recipe, fridge_names)

    assert result["match_score"] == 0.5  # 2 von 4 verfügbar
    assert "chicken" in result["available"]
    assert "soy sauce" in result["missing"]


def test_calculate_match_no_overlap():
    """Wenn keine Zutat im Kühlschrank ist, ist Score 0.0."""
    recipe = {
        "ingredients": [
            {"name": "fish", "measure": "200 g"},
            {"name": "lemon", "measure": "1"},
        ],
    }
    fridge_names = {"chicken", "rice"}

    result = calculate_match(recipe, fridge_names)

    assert result["match_score"] == 0.0
    assert len(result["available"]) == 0
    assert len(result["missing"]) == 2


def test_calculate_match_fuzzy_substring():
    """Fuzzy-Matching: 'chicken' matched 'chicken breasts'."""
    recipe = {
        "ingredients": [
            {"name": "chicken breasts", "measure": "2"},
        ],
    }
    fridge_names = {"chicken"}

    result = calculate_match(recipe, fridge_names)

    assert result["match_score"] == 1.0
    assert "chicken breasts" in result["available"]


def test_calculate_match_with_german_ingredient_name():
    """German fridge names should match English TheMealDB ingredients."""
    recipe = {
        "ingredients": [
            {"name": "chicken breasts", "measure": "2"},
            {"name": "garlic", "measure": "1 clove"},
        ],
    }
    fridge_names = {"Hähnchenbrust", "Knoblauch"}

    result = calculate_match(recipe, fridge_names)

    assert result["match_score"] == 1.0
    assert "chicken breasts" in result["available"]
    assert "garlic" in result["available_staples"]


def test_find_recipes_filters_out_zero_overlap(monkeypatch):
    """Only recipes with at least one real fridge overlap should be returned."""

    def fake_search_recipes_by_ingredient(ingredient):
        if ingredient == "chicken":
            return [{"id": "1", "name": "Chicken Bowl"}, {"id": "2", "name": "Cake"}]
        return []

    def fake_get_recipe_details(recipe_id):
        if recipe_id == "1":
            return {
                "id": "1",
                "name": "Chicken Bowl",
                "ingredients": [{"name": "chicken", "measure": "200 g"}],
            }
        return {
            "id": "2",
            "name": "Cake",
            "ingredients": [{"name": "cocoa", "measure": "50 g"}],
        }

    monkeypatch.setattr(
        "flaskr_new.asaai.recipe_matcher.search_recipes_by_ingredient",
        fake_search_recipes_by_ingredient,
    )
    monkeypatch.setattr(
        "flaskr_new.asaai.recipe_matcher.get_recipe_details",
        fake_get_recipe_details,
    )

    results = find_recipes_matching_fridge(
        [{"name": "Hähnchenbrust", "amount": 500}],
        max_recipes_per_ingredient=5,
    )

    assert len(results) == 1
    assert results[0]["recipe"]["id"] == "1"


def test_calculate_match_pantry_staples_are_low_priority():
    """Missing pantry staples should hurt less than missing core ingredients."""
    recipe = {
        "ingredients": [
            {"name": "chicken", "measure": "200 g"},
            {"name": "onion", "measure": "1"},
            {"name": "garlic", "measure": "2 cloves"},
            {"name": "salt", "measure": "to taste"},
            {"name": "pepper", "measure": "to taste"},
        ],
    }
    fridge_names = {"chicken"}

    result = calculate_match(recipe, fridge_names)

    assert result["available"] == ["chicken"]
    assert result["missing"] == []
    assert len(result["missing_staples"]) == 4
    assert result["match_score"] == 0.5


def test_find_recipes_ignores_staples_as_primary_search_terms(monkeypatch):
    """Pantry staples should not be used as primary recipe search terms."""
    searched_terms = []

    def fake_search_recipes_by_ingredient(ingredient):
        searched_terms.append(ingredient)
        return []

    monkeypatch.setattr(
        "flaskr_new.asaai.recipe_matcher.search_recipes_by_ingredient",
        fake_search_recipes_by_ingredient,
    )

    results = find_recipes_matching_fridge(
        [
            {"name": "Hähnchenbrust", "amount": 500},
            {"name": "Zwiebeln", "amount": 2},
            {"name": "Olivenöl", "amount": 50},
        ],
        max_recipes_per_ingredient=2,
    )

    assert results == []
    assert "chicken" in searched_terms
    assert "onion" not in searched_terms
    assert "olive oil" not in searched_terms


def test_hahnchenschenkel_maps_to_chicken_thigh(monkeypatch):
    """German 'Hähnchenschenkel' should match recipes with chicken thigh."""

    def fake_search_recipes_by_ingredient(ingredient):
        if ingredient == "chicken" or ingredient == "chicken thigh":
            return [{"id": "11", "name": "Roasted Chicken Thighs"}]
        return []

    def fake_get_recipe_details(recipe_id):
        return {
            "id": recipe_id,
            "name": "Roasted Chicken Thighs",
            "ingredients": [
                {"name": "chicken thigh", "measure": "2"},
                {"name": "salt", "measure": "to taste"},
            ],
        }

    monkeypatch.setattr(
        "flaskr_new.asaai.recipe_matcher.search_recipes_by_ingredient",
        fake_search_recipes_by_ingredient,
    )
    monkeypatch.setattr(
        "flaskr_new.asaai.recipe_matcher.get_recipe_details",
        fake_get_recipe_details,
    )

    results = find_recipes_matching_fridge(
        [{"name": "Hähnchenschenkel", "amount": 400}],
        max_recipes_per_ingredient=3,
    )

    assert len(results) == 1
    assert "chicken thigh" in results[0]["available"]


def test_protein_target_prioritizes_protein_source_matches(monkeypatch):
    """With protein target, recipe containing protein-source matches should rank first."""

    def fake_search_recipes_by_ingredient(ingredient):
        if ingredient == "chicken":
            return [{"id": "1", "name": "Chicken Bowl"}, {"id": "2", "name": "Tomato Rice"}]
        if ingredient == "rice":
            return [{"id": "1", "name": "Chicken Bowl"}, {"id": "2", "name": "Tomato Rice"}]
        return []

    def fake_get_recipe_details(recipe_id):
        if recipe_id == "1":
            return {
                "id": "1",
                "name": "Chicken Bowl",
                "ingredients": [
                    {"name": "chicken", "measure": "200 g"},
                    {"name": "rice", "measure": "100 g"},
                ],
            }
        return {
            "id": "2",
            "name": "Tomato Rice",
            "ingredients": [
                {"name": "tomato", "measure": "2"},
                {"name": "rice", "measure": "100 g"},
            ],
        }

    monkeypatch.setattr(
        "flaskr_new.asaai.recipe_matcher.search_recipes_by_ingredient",
        fake_search_recipes_by_ingredient,
    )
    monkeypatch.setattr(
        "flaskr_new.asaai.recipe_matcher.get_recipe_details",
        fake_get_recipe_details,
    )

    results = find_recipes_matching_fridge(
        [{"name": "Hähnchenbrust", "amount": 500}, {"name": "Reis", "amount": 200}],
        max_recipes_per_ingredient=5,
        daily_goal={"protein": 60, "kcal": 800},
    )

    assert len(results) == 2
    assert results[0]["recipe"]["id"] == "1"
    assert results[0]["protein_priority_score"] > results[1]["protein_priority_score"]