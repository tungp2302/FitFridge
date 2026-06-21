import pytest

from flaskr_new import create_app, db
from flaskr_new import consumption_log_repo as clr
from flaskr_new import product_repo


@pytest.fixture()
def app_context(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "clr.sqlite")})
    with app.app_context():
        db.init_db()
        yield


def test_log_consume_and_refill_write_rows(app_context):
    product_id = product_repo.create_product(
        name="Milch",
        brand="Demo",
        barcode="clr-milk-001",
        kcal_per_100g=64.0,
        protein_per_100g=3.3,
        fat_per_100g=3.5,
        carbs_per_100g=4.8,
    )

    consume_id = clr.log_consume(product_id, 50, "g", note="test consume")
    refill_id = clr.log_refill(product_id, 100, "g")

    rows = db.get_db().execute(
        "SELECT id, product_id, event_type, amount, unit, note FROM consumption_log ORDER BY id"
    ).fetchall()

    assert [row["event_type"] for row in rows] == ["consume", "refill"]
    assert rows[0]["id"] == consume_id
    assert rows[0]["amount"] == 50.0
    assert rows[0]["note"] == "test consume"
    assert rows[1]["id"] == refill_id
    assert rows[1]["amount"] == 100.0
    assert all(row["product_id"] == product_id for row in rows)
