"""Tests für macro_calculator.py.

Testet den Mengen-Parser und die Helper-Funktionen.
OpenFoodFacts-Lookups werden NICHT getestet (sind extern und langsam).
"""

from flaskr_new.asaai.macro_calculator import (
    parse_measure_string,
    rank_by_daily_goal,
)


# === Tests für parse_measure_string ===

def test_parse_simple_grams():
    assert parse_measure_string("200 g") == (200.0, "g")


def test_parse_simple_ml():
    assert parse_measure_string("500 ml") == (500.0, "ml")


def test_parse_kg_converted_to_g():
    assert parse_measure_string("1.5 kg") == (1500.0, "g")


def test_parse_liter_converted_to_ml():
    assert parse_measure_string("2 l") == (2000.0, "ml")


def test_parse_us_cup_to_ml():
    assert parse_measure_string("1 cup") == (240.0, "ml")


def test_parse_us_tablespoon():
    assert parse_measure_string("3 tablespoons") == (45.0, "ml")


def test_parse_fraction():
    result, unit = parse_measure_string("3/4 cup")
    assert result == 180.0
    assert unit == "ml"


def test_parse_half_teaspoon():
    result, unit = parse_measure_string("1/2 teaspoon")
    assert result == 2.5
    assert unit == "ml"


def test_parse_count_default_200g():
    """Zähleinheiten ohne klare Einheit → 200g Default pro Stück."""
    result, unit = parse_measure_string("2 chicken breasts")
    assert result == 400.0  # 2 * 200
    assert unit == "g"


def test_parse_to_taste_ignored():
    """'to taste' wird als 0 behandelt."""
    assert parse_measure_string("to taste") == (0.0, "g")


def test_parse_empty_string():
    assert parse_measure_string("") == (0.0, "g")


def test_parse_pound_to_grams():
    result, unit = parse_measure_string("1 lb")
    # 1 Pfund = 453.59g
    assert 450 < result < 460
    assert unit == "g"


# === Tests für rank_by_daily_goal ===

def test_rank_perfect_protein_match():
    """Rezept mit 30g Protein bei Ziel 30g → bester Score."""
    matches = [
        {"recipe": {"name": "A"}, "macros": {"protein": 30, "kcal": 500}},
        {"recipe": {"name": "B"}, "macros": {"protein": 60, "kcal": 500}},
    ]
    goal = {"protein": 30, "kcal": 600}

    result = rank_by_daily_goal(matches, goal)

    # A sollte ersten Platz haben
    assert result[0]["recipe"]["name"] == "A"
    assert result[0]["goal_score"] > result[1]["goal_score"]


def test_rank_kcal_penalty():
    """Rezept das kcal-Limit überschreitet bekommt Penalty."""
    matches = [
        {"recipe": {"name": "A"}, "macros": {"protein": 30, "kcal": 500}},
        {"recipe": {"name": "B"}, "macros": {"protein": 30, "kcal": 2000}},
    ]
    goal = {"protein": 30, "kcal": 600}

    result = rank_by_daily_goal(matches, goal)

    # A (innerhalb kcal-Limit) sollte besser sein als B (überschreitet)
    assert result[0]["recipe"]["name"] == "A"


def test_rank_without_goal_keeps_order():
    """Ohne Tagesziel bleibt die Reihenfolge erhalten."""
    matches = [
        {"recipe": {"name": "A"}, "macros": {}},
        {"recipe": {"name": "B"}, "macros": {}},
    ]
    result = rank_by_daily_goal(matches, None)
    assert result == matches