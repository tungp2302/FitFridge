from flaskr_new.fridge_service import calculate_total_nutrition

def test_calculate_total_nutrition_maps_keys():
    item = {
        "current_amount": 50,
        "unit": "g",
        "kcal_per_100g": 200,
        "protein_per_100g": 10,
        "fat_per_100g": 5,
        "carbs_per_100g": 20,
    }
    res = calculate_total_nutrition(item)
    assert res["total_kcal"] == 100.0
    assert round(res["total_protein"], 1) == 5.0