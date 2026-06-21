import pytest

from flaskr_new import create_app, db, fridge_repo, product_repo
from flaskr_new.fridge_service import consume_amount, refill_amount


@pytest.fixture()
def app_context(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "fridge.sqlite")})
    with app.app_context():
        db.init_db()
        yield


def add_test_item(amount=500.0, user_id=None):
    product_id = product_repo.create_product(
        name="Nutella",
        brand="Ferrero",
        barcode=f"nutella-{user_id or 'shared'}-{amount}",
        kcal_per_100g=539.0,
        protein_per_100g=6.3,
        fat_per_100g=30.9,
        carbs_per_100g=57.5,
    )
    return fridge_repo.add_item(product_id, amount, "g", user_id=user_id)


def test_consume_and_refill_change_amount(app_context):
    item_id = add_test_item()

    consume_result = consume_amount(item_id, 125)
    refill_result = refill_amount(item_id, 50)
    item = fridge_repo.get_item(item_id)

    assert consume_result["success"] is True
    assert consume_result["new_amount"] == 375.0
    assert refill_result["success"] is True
    assert refill_result["new_amount"] == 425.0
    assert item["current_amount"] == 425.0


def test_consume_more_than_available_sets_amount_to_zero(app_context):
    item_id = add_test_item(amount=40.0)

    result = consume_amount(item_id, 100)

    assert result["success"] is True
    assert result["new_amount"] == 0.0
    assert fridge_repo.get_item(item_id)["current_amount"] == 0.0


def test_invalid_amounts_are_rejected(app_context):
    item_id = add_test_item()

    assert consume_amount(item_id, 0)["success"] is False
    assert consume_amount(item_id, -10)["success"] is False
    assert consume_amount(item_id, None)["success"] is False
    assert refill_amount(item_id, 0)["success"] is False
    assert refill_amount(item_id, -10)["success"] is False
    assert fridge_repo.get_item(item_id)["current_amount"] == 500.0


def test_missing_item_is_rejected(app_context):
    assert consume_amount(99999, 30)["success"] is False
    assert refill_amount(99999, 30)["success"] is False


def test_user_cannot_change_someone_elses_item(app_context):
    connection = db.get_db()
    connection.execute("INSERT INTO user (username, password) VALUES ('owner', 'x')")
    connection.execute("INSERT INTO user (username, password) VALUES ('other', 'x')")
    connection.commit()

    item_id = add_test_item(user_id=1)

    assert consume_amount(item_id, 30, user_id=2)["success"] is False
    assert refill_amount(item_id, 30, user_id=2)["success"] is False
    assert fridge_repo.get_item(item_id)["current_amount"] == 500.0

    owner_result = consume_amount(item_id, 30, user_id=1)
    assert owner_result["success"] is True
    assert owner_result["new_amount"] == 470.0
