from datetime import date

import pytest

from flaskr_new import create_app, db, fridge_repo, product_repo
from flaskr_new import meal_tracker_repo as repo
from flaskr_new import meal_tracker_service as service


@pytest.fixture()
def app_context(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "meal_tracker.sqlite")})
    with app.app_context():
        db.init_db()
        db.get_db().execute(
            "INSERT INTO user (username, password) VALUES (?, ?)",
            ("testuser", "pw"),
        )
        db.get_db().commit()
        yield


def add_product(name="Nutella", barcode="3017620422003"):
    return product_repo.create_product(
        name=name,
        brand="Demo",
        barcode=barcode,
        kcal_per_100g=500.0,
        protein_per_100g=10.0,
        fat_per_100g=20.0,
        carbs_per_100g=60.0,
    )


def test_settings_are_saved_and_percentages_can_be_normalized(app_context):
    normalized = service.normalize_macro_percentages(20, 30, 10)
    repo.save_settings(1, 2400, normalized["protein_pct"], normalized["carbs_pct"], normalized["fat_pct"])

    saved = repo.get_settings(1)

    assert saved["daily_kcal"] == 2400.0
    assert normalized == {"protein_pct": 33.3, "carbs_pct": 50.0, "fat_pct": 16.7}
    assert service.normalize_macro_percentages(0, 0, 0) == repo.DEFAULT_SETTINGS


def test_daily_totals_and_remaining_values(app_context):
    repo.save_settings(1, 2000, 30, 40, 30)
    repo.add_meal_entry(1, "Breakfast", 550, 35, 50, 18)
    repo.add_meal_entry(1, "Lunch", 700, 40, 80, 20)

    consumed = repo.get_day_totals(1, date.today().isoformat())
    summary = service.build_daily_summary(repo.get_settings(1), consumed)

    assert consumed["kcal"] == 1250.0
    assert consumed["protein_g"] == 75.0
    assert summary["targets"]["kcal"] == 2000.0
    assert summary["remaining"]["kcal"] == 750.0


def test_log_meal_from_fridge_item_deducts_stock(app_context):
    add_product()
    product = dict(product_repo.get_by_barcode("3017620422003"))
    item_id = fridge_repo.add_item(product["id"], 400.0, "g")

    result = service.log_meal_from_product(1, product, 100.0, "g", fridge_item_id=item_id)
    meal = db.get_db().execute("SELECT * FROM meal_tracker_entry").fetchone()

    assert result["deducted"] is True
    assert fridge_repo.get_item(item_id)["current_amount"] == 300.0
    assert meal["meal_name"] == "Nutella"
    assert meal["amount"] == 100.0


def test_meal_entries_belong_to_their_user(app_context):
    entry_id = repo.add_meal_entry(1, "Snack", 120, 10, 12, 5)

    assert repo.delete_meal_entry(entry_id, 2) is False
    assert repo.delete_meal_entry(entry_id, 1) is True
    assert db.get_db().execute("SELECT COUNT(*) FROM meal_tracker_entry").fetchone()[0] == 0


def test_update_meal_amount_scales_nutrition(app_context):
    entry_id = repo.add_meal_entry(1, "Pasta", 200, 10, 20, 5, amount=100, unit="g")

    assert repo.update_meal_entry_amount(entry_id, 1, 150) is True
    assert repo.update_meal_entry_amount(entry_id, 1, 0) is False

    row = db.get_db().execute(
        "SELECT amount, kcal, protein_g, carbs_g, fat_g FROM meal_tracker_entry WHERE id = ?",
        (entry_id,),
    ).fetchone()

    assert dict(row) == {
        "amount": 150.0,
        "kcal": 300.0,
        "protein_g": 15.0,
        "carbs_g": 30.0,
        "fat_g": 7.5,
    }


def test_cart_product_leftovers_go_to_fridge(app_context):
    cart = [
        {
            "kind": "product",
            "name": "Mango",
            "brand": "FitFridge",
            "barcode": "ingredient:mango",
            "kcal_per_100g": 60,
            "protein_per_100g": 1,
            "fat_per_100g": 0.5,
            "carbs_per_100g": 14,
            "unit": "g",
            "amount": 120,
            "remaining_amount": 80,
        }
    ]

    message = service.commit_meal_cart(1, cart)
    fridge_item = db.get_db().execute(
        "SELECT fi.current_amount, p.name FROM fridge_item fi JOIN product p ON p.id = fi.product_id"
    ).fetchone()

    assert message.startswith("1 Eintrag")
    assert fridge_item["name"] == "Mango"
    assert fridge_item["current_amount"] == 80.0
