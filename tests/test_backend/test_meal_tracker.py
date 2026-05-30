import json

import pytest

from flaskr_new import create_app
from flaskr_new import db
from flaskr_new import fridge_repo, product_repo
from flaskr_new import meal_tracker_repo as repo
from flaskr_new import meal_tracker_service as service


@pytest.fixture()
def app(tmp_path):
    database_path = tmp_path / "meal_tracker.sqlite"
    app = create_app({"TESTING": True, "DATABASE": str(database_path)})

    with app.app_context():
        db.init_db()
        db.get_db().execute("INSERT INTO user (username, password) VALUES (?, ?)", ("testuser", "pw"))
        db.get_db().commit()

    yield app


@pytest.fixture()
def app_context(app):
    with app.app_context():
        yield


def test_schema_contains_meal_tracker_tables(app_context):
    rows = db.get_db().execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {row[0] for row in rows}

    assert {"meal_tracker_settings", "meal_tracker_entry"}.issubset(table_names)


def test_settings_roundtrip_and_normalization(app_context):
    settings = repo.get_settings(1)
    assert settings["daily_kcal"] == 2000.0

    normalized = service.normalize_macro_percentages(20, 30, 10)
    assert round(normalized["protein_pct"] + normalized["carbs_pct"] + normalized["fat_pct"], 1) == 100.0

    repo.save_settings(1, 2400, 25, 45, 30)
    saved = repo.get_settings(1)

    assert saved["daily_kcal"] == 2400.0
    assert saved["protein_pct"] == 25.0
    assert saved["carbs_pct"] == 45.0
    assert saved["fat_pct"] == 30.0


def test_meal_entry_analysis(app_context):
    repo.save_settings(1, 2000, 30, 40, 30)
    repo.add_meal_entry(1, "Breakfast", 550, 35, 50, 18)
    repo.add_meal_entry(1, "Lunch", 700, 40, 80, 20)

    consumed = repo.get_today_totals(1)
    summary = service.build_daily_summary(repo.get_settings(1), consumed)

    assert consumed["kcal"] == 1250.0
    assert summary["targets"]["kcal"] == 2000.0
    assert summary["remaining"]["kcal"] == 750.0
    assert "Noch 750.0 kcal offen" in summary["recommendation"]


def test_meal_logging_deducts_from_fridge(app_context):
    product_id = db.get_db().execute(
        "INSERT INTO product (name, brand, barcode, kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Nutella", "Ferrero", "3017620422003", 539.0, 6.3, 30.9, 57.5),
    ).lastrowid
    db.get_db().commit()
    fridge_item_id = db.get_db().execute(
        "INSERT INTO fridge_item (product_id, current_amount, unit) VALUES (?, ?, ?)",
        (product_id, 400.0, "g"),
    ).lastrowid
    db.get_db().commit()

    product = product_repo.get_by_id(product_id)
    result = service.log_meal_from_product(1, dict(product), 100.0, "g", fridge_item_id=fridge_item_id)

    fridge_item = fridge_repo.get_item(fridge_item_id)
    meal_row = db.get_db().execute(
        "SELECT * FROM meal_tracker_entry ORDER BY id DESC LIMIT 1"
    ).fetchone()

    assert result["deducted"] is True
    assert fridge_item["current_amount"] == 300.0
    assert meal_row["product_id"] == product_id
    assert meal_row["amount"] == 100.0
    assert meal_row["unit"] == "g"
    assert meal_row["meal_name"] == "Nutella"


def test_meal_entry_delete_requires_matching_user(app_context):
    entry_id = repo.add_meal_entry(1, "Snack", 120, 10, 12, 5)

    assert repo.delete_meal_entry(entry_id, 2) is False
    assert repo.delete_meal_entry(entry_id, 1) is True

    remaining = db.get_db().execute("SELECT COUNT(*) AS count FROM meal_tracker_entry WHERE id = ?", (entry_id,)).fetchone()
    assert remaining["count"] == 0


def test_meal_tracker_route_can_delete_meal(app):
    with app.app_context():
        entry_id = repo.add_meal_entry(1, "Snack", 120, 10, 12, 5)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.post(
            "/meal-tracker",
            data={"action": "delete_meal", "meal_entry_id": str(entry_id)},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"Mahlzeit geloescht." in response.data


def test_meal_entry_amount_update_scales_nutrition(app_context):
    entry_id = repo.add_meal_entry(1, "Pasta", 200, 10, 20, 5, amount=100, unit="g")

    assert repo.update_meal_entry_amount(entry_id, 1, 150) is True

    row = db.get_db().execute(
        "SELECT amount, kcal, protein_g, carbs_g, fat_g FROM meal_tracker_entry WHERE id = ?",
        (entry_id,),
    ).fetchone()

    assert row["amount"] == 150.0
    assert row["kcal"] == 300.0
    assert row["protein_g"] == 15.0
    assert row["carbs_g"] == 30.0
    assert row["fat_g"] == 7.5


def test_selected_payload_remaining_is_saved_to_fridge(app):
    payload = [
        {
            "name": "Mango",
            "brand": "FitFridge AI",
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

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1

        response = client.post(
            "/meal-tracker",
            data={"action": "track_meal", "selected_payload": json.dumps(payload)},
            follow_redirects=True,
        )

    assert response.status_code == 200

    with app.app_context():
        row = db.get_db().execute(
            "SELECT fi.current_amount, fi.unit, p.name FROM fridge_item fi JOIN product p ON p.id = fi.product_id WHERE fi.user_id = ? ORDER BY fi.id DESC LIMIT 1",
            (1,),
        ).fetchone()

    assert row is not None
    assert row["current_amount"] == 80.0
    assert row["unit"] == "g"
    assert row["name"] == "Mango"
