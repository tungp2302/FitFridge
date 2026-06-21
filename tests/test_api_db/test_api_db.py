import json

import pytest

from flaskr_new import create_app, db, fridge_repo
from flaskr_new import openfoodfacts_client as ofc
from flaskr_new import product_repo


@pytest.fixture()
def app_context(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})
    with app.app_context():
        db.init_db()
        yield


def product_payload(**overrides):
    payload = {
        "name": "Nutella",
        "brand": "Ferrero",
        "barcode": "3017620422003",
        "kcal_per_100g": 539.0,
        "protein_per_100g": 6.3,
        "fat_per_100g": 30.9,
        "carbs_per_100g": 57.5,
        "total_amount": 400.0,
        "unit": "g",
    }
    payload.update(overrides)
    return payload


def create_product(**overrides):
    payload = product_payload(**overrides)
    return product_repo.create_product(
        payload["name"],
        payload["brand"],
        payload["barcode"],
        payload["kcal_per_100g"],
        payload["protein_per_100g"],
        payload["fat_per_100g"],
        payload["carbs_per_100g"],
    )


def test_product_and_fridge_item_roundtrip(app_context):
    product_id = create_product()
    item_id = fridge_repo.add_item(product_id, 400.0, "g")

    assert product_repo.get_by_barcode("3017620422003")["name"] == "Nutella"
    assert fridge_repo.get_item(item_id)["current_amount"] == 400.0

    assert fridge_repo.update_amount(item_id, 250.0) == 1
    assert fridge_repo.get_item(item_id)["current_amount"] == 250.0

    assert fridge_repo.delete_item(item_id) == 1
    assert fridge_repo.get_item(item_id) is None


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_openfoodfacts_parsing(monkeypatch):
    payload = {
        "status": 1,
        "product": {
            "code": "3017620422003",
            "product_name": "Nutella",
            "brands": "Ferrero",
            "quantity": "400 g",
            "nutriments": {
                "energy-kcal_100g": "539",
                "proteins_100g": "6.3",
                "fat_100g": "30.9",
                "carbohydrates_100g": "57.5",
            },
        },
    }
    monkeypatch.setattr(ofc, "urlopen", lambda *args, **kwargs: FakeResponse(payload))

    result = ofc.search_product("3017620422003")

    assert result == product_payload()
