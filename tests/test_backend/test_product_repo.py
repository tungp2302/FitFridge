import pytest

from flaskr_new import create_app, db, product_repo as repo


@pytest.fixture()
def app_context(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "products.sqlite")})
    with app.app_context():
        db.init_db()
        yield


def make(name, brand="Demo", barcode=None, kcal=500.0):
    return repo.create_product(
        name=name,
        brand=brand,
        barcode=barcode or f"bc:{name.lower()}",
        kcal_per_100g=kcal,
        protein_per_100g=10.0,
        fat_per_100g=20.0,
        carbs_per_100g=60.0,
    )


def test_create_product_can_be_found_by_barcode(app_context):
    make("Nutella", barcode="3017620422003")

    product = repo.get_by_barcode("3017620422003")

    assert product["name"] == "Nutella"
    assert product["kcal_per_100g"] == 500.0
    assert repo.get_by_barcode("does-not-exist") is None


def test_search_results_are_ranked_alphabetically(app_context):
    make("Zucker")
    make("Apfel")
    make("Mango")

    names = [row["name"] for row in repo.search_by_name("e")]

    assert names == ["Apfel", "Mango", "Zucker"]


def test_search_matches_name_and_brand(app_context):
    make("Joghurt", brand="Alpenmilch")

    assert len(repo.search_by_name("jogh")) == 1
    assert len(repo.search_by_name("alpen")) == 1
    assert repo.search_by_name("pizza") == []


def test_update_product_changes_name_and_brand(app_context):
    pid = make("Altname", brand="Altmarke")

    assert repo.update_product(pid, "Neuname", "Neumarke") == 1
    assert repo.update_product(999, "X", "Y") == 0

    updated = repo.get_by_barcode("bc:altname")
    assert updated["name"] == "Neuname"
    assert updated["brand"] == "Neumarke"
