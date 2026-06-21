from flaskr_new.fridge_service import calculate_total_nutrition


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
