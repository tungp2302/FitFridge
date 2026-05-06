import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_flat_package():
    """Load the space-named package folder as importable module flaskr_new."""
    repo_root = Path(__file__).resolve().parents[2]
    package_dir = repo_root / "flaskr new"

    if "flaskr_new" in sys.modules:
        return sys.modules["flaskr_new"]

    spec = importlib.util.spec_from_file_location(
        "flaskr_new",
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["flaskr_new"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def flat_modules():
    pkg = _load_flat_package()
    db = importlib.import_module("flaskr_new.db")
    fridge_repo = importlib.import_module("flaskr_new.fridge_repo")
    product_repo = importlib.import_module("flaskr_new.product_repo")
    ofc = importlib.import_module("flaskr_new.openfoodfacts_client")
    return pkg, db, fridge_repo, product_repo, ofc


@pytest.fixture()
def app(tmp_path, flat_modules):
    pkg, db, _, _, _ = flat_modules
    database_path = tmp_path / "test_flat.sqlite"
    app = pkg.create_app({"TESTING": True, "DATABASE": str(database_path)})

    with app.app_context():
        db.init_db()

    yield app


@pytest.fixture()
def app_context(app):
    with app.app_context():
        yield


def test_flat_schema_creation(app_context, flat_modules):
    _, db, _, _, _ = flat_modules
    connection = db.get_db()
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {row[0] for row in rows}

    assert {"user", "product", "fridge_item"}.issubset(table_names)


def test_flat_product_insert_lookup(app_context, flat_modules):
    _, _, _, product_repo, _ = flat_modules
    product_id = product_repo.create_product(
        name="Nutella",
        brand="Ferrero",
        barcode="3017620422003",
        kcal_per_100g=539.0,
        protein_per_100g=6.3,
        fat_per_100g=30.9,
        carbs_per_100g=57.5,
    )

    by_id = product_repo.get_by_id(product_id)
    by_barcode = product_repo.get_by_barcode("3017620422003")
    all_products = product_repo.list_all()

    assert by_id["name"] == "Nutella"
    assert by_barcode["brand"] == "Ferrero"
    assert len(all_products) == 1


def test_flat_fridge_item_crud(app_context, flat_modules):
    _, _, fridge_repo, product_repo, _ = flat_modules
    product_id = product_repo.create_product(
        name="Nutella",
        brand="Ferrero",
        barcode="3017620422003",
        kcal_per_100g=539.0,
        protein_per_100g=6.3,
        fat_per_100g=30.9,
        carbs_per_100g=57.5,
    )

    fridge_item_id = fridge_repo.add_item(product_id, 400.0, "g")

    items = fridge_repo.list_items()
    item = fridge_repo.get_item(fridge_item_id)

    assert len(items) == 1
    assert item["name"] == "Nutella"
    assert item["current_amount"] == 400.0
    assert item["unit"] == "g"

    updated_rows = fridge_repo.update_amount(fridge_item_id, 250.0)
    updated = fridge_repo.get_item(fridge_item_id)
    deleted_rows = fridge_repo.delete_item(fridge_item_id)

    assert updated_rows == 1
    assert updated["current_amount"] == 250.0
    assert deleted_rows == 1
    assert fridge_repo.get_item(fridge_item_id) is None


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_flat_openfoodfacts_parsing(monkeypatch, flat_modules):
    _, _, _, _, ofc = flat_modules
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
                "sugars_100g": "56.3",
            },
        },
    }

    monkeypatch.setattr(ofc, "urlopen", lambda *args, **kwargs: _FakeResponse(payload))

    result = ofc.search_product("3017620422003")

    assert result["name"] == "Nutella"
    assert result["brand"] == "Ferrero"
    assert result["total_amount"] == 400.0
    assert result["unit"] == "g"
    assert result["kcal_per_100g"] == 539.0
    assert result["protein_per_100g"] == 6.3
    assert result["fat_per_100g"] == 30.9
    assert result["carbs_per_100g"] == 57.5
    assert result["sugar_per_100g"] == 56.3
