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
            {"name": "garlic", "measure": "1 clove"},
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