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
