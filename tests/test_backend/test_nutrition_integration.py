from flaskr_new.calculations import calculate_for_amount
from flaskr_new.fridge_service import calculate_total_nutrition


def test_calculate_for_amount_converts_units_and_handles_bad_input():
    product = {"kcal_per_100g": 200, "protein_per_100g": 10, "fat_per_100g": 5,
               "carbs_per_100g": 20, "grams_per_piece": 60}
    zero = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    assert calculate_for_amount(product, 1, "kg")["kcal"] == 2000.0    # kg -> 1000 g
    assert calculate_for_amount(product, 10, "cl")["kcal"] == 200.0    # cl -> 100 g
    assert calculate_for_amount(product, 2, "stk")["kcal"] == 240.0    # 2 * 60 g
    assert calculate_for_amount(product, 100, "lb") == zero            # unbekannte Einheit
    no_gpp = {k: v for k, v in product.items() if k != "grams_per_piece"}
    assert calculate_for_amount(no_gpp, 2, "stk") == zero              # stk ohne grams_per_piece


def test_calculate_total_nutrition_for_current_amount():
    item = {
        "current_amount": 50,
        "unit": "g",
        "kcal_per_100g": 200,
        "protein_per_100g": 10,
        "fat_per_100g": 5,
        "carbs_per_100g": 20,
    }

    assert calculate_total_nutrition(item) == {
        "total_kcal": 100.0,
        "total_protein": 5.0,
        "total_fat": 2.5,
        "total_carbs": 10.0,
    }


def test_calculate_total_nutrition_returns_zero_for_bad_amount():
    item = {
        "current_amount": 0,
        "unit": "g",
        "kcal_per_100g": 200,
        "protein_per_100g": 10,
        "fat_per_100g": 5,
        "carbs_per_100g": 20,
    }

    assert calculate_total_nutrition(item) == {
        "total_kcal": 0.0,
        "total_protein": 0.0,
        "total_fat": 0.0,
        "total_carbs": 0.0,
    }
