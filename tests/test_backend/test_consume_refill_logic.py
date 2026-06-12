"""Tests für consume_amount und refill_amount aus fridge_service.

Diese Tests prüfen die Edge Cases der Bestands-Tracking-Funktionen:
- Normale Operationen
- Negative/Zero/None-Mengen
- Schutz vor negativen Beständen
- Unbekannte Item-IDs

Das consumption_log-Logging wird separat in
test_fridge_service_logging.py geprüft.
"""

import pytest

from flaskr_new import create_app
from flaskr_new import db
from flaskr_new import fridge_repo, product_repo
from flaskr_new.fridge_service import consume_amount, refill_amount


@pytest.fixture
def app(tmp_path):
    """Erstellt eine Test-App mit frischer DB für jeden Test."""
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "consume_refill.sqlite")})

    with app.app_context():
        db.init_db()
        yield app


@pytest.fixture
def item_id(app):
    """Erstellt ein Test-Item und gibt die ID zurück."""
    with app.app_context():
        product_id = product_repo.create_product(
            name="Nutella",
            brand="Ferrero",
            barcode="3017620422003",
            kcal_per_100g=539.0,
            protein_per_100g=6.3,
            fat_per_100g=30.9,
            carbs_per_100g=57.5,
        )
        new_item_id = fridge_repo.add_item(product_id, 500.0, "g")
        return new_item_id


# === Tests für consume_amount ===

def test_consume_normal(app, item_id):
    """Normaler Verbrauch reduziert den Bestand."""
    with app.app_context():
        result = consume_amount(item_id, 30)
        assert result["success"] is True
        assert result["new_amount"] == 470.0

        item = fridge_repo.get_item(item_id)
        assert item["current_amount"] == 470.0


def test_consume_negative_amount_fails(app, item_id):
    """Negative Menge wird abgelehnt, Bestand unverändert."""
    with app.app_context():
        result = consume_amount(item_id, -10)
        assert result["success"] is False

        item = fridge_repo.get_item(item_id)
        assert item["current_amount"] == 500.0


def test_consume_zero_amount_fails(app, item_id):
    """Menge 0 wird abgelehnt."""
    with app.app_context():
        result = consume_amount(item_id, 0)
        assert result["success"] is False


def test_consume_none_amount_fails(app, item_id):
    """None als Menge wird abgelehnt."""
    with app.app_context():
        result = consume_amount(item_id, None)
        assert result["success"] is False


def test_consume_more_than_available_clamps_to_zero(app, item_id):
    """Mehr verbrauchen als vorhanden → Bestand wird auf 0 gesetzt."""
    with app.app_context():
        result = consume_amount(item_id, 9999)
        assert result["success"] is True
        assert result["new_amount"] == 0.0


def test_consume_unknown_item_fails(app):
    """Item das nicht existiert → Fehler."""
    with app.app_context():
        result = consume_amount(99999, 30)
        assert result["success"] is False


# === Tests für refill_amount ===

def test_refill_normal(app, item_id):
    """Normales Auffüllen erhöht den Bestand."""
    with app.app_context():
        result = refill_amount(item_id, 200)
        assert result["success"] is True
        assert result["new_amount"] == 700.0


def test_refill_negative_amount_fails(app, item_id):
    """Negative Menge zum Auffüllen wird abgelehnt."""
    with app.app_context():
        result = refill_amount(item_id, -50)
        assert result["success"] is False


def test_refill_zero_fails(app, item_id):
    """Menge 0 wird abgelehnt."""
    with app.app_context():
        result = refill_amount(item_id, 0)
        assert result["success"] is False


def test_refill_unknown_item_fails(app):
    """Item das nicht existiert → Fehler."""
    with app.app_context():
        result = refill_amount(99999, 100)
        assert result["success"] is False


# === Kombi-Tests ===

def test_consume_then_refill(app, item_id):
    """Erst verbrauchen, dann auffüllen."""
    with app.app_context():
        consume_amount(item_id, 100)
        result = refill_amount(item_id, 50)
        assert result["new_amount"] == 450.0  # 500 - 100 + 50


def test_multiple_consumes_accumulate(app, item_id):
    """Mehrere kleine Verbräuche addieren sich."""
    with app.app_context():
        consume_amount(item_id, 30)
        consume_amount(item_id, 20)
        consume_amount(item_id, 50)

        item = fridge_repo.get_item(item_id)
        assert item["current_amount"] == 400.0  # 500 - 100


# === Autorisierung (IDOR-Schutz) ===

def test_consume_foreign_item_is_rejected(app):
    """Ein Nutzer darf Items anderer Nutzer nicht verbrauchen/auffüllen."""
    with app.app_context():
        connection = db.get_db()
        connection.execute("INSERT INTO user (username, password) VALUES ('owner', 'x')")
        connection.execute("INSERT INTO user (username, password) VALUES ('attacker', 'x')")
        connection.commit()

        product_id = product_repo.create_product(
            name="Geheimer Joghurt",
            brand="Owner Brand",
            barcode="owner-item-001",
            kcal_per_100g=60.0,
            protein_per_100g=5.0,
            fat_per_100g=2.0,
            carbs_per_100g=4.0,
        )
        owned_item_id = fridge_repo.add_item(product_id, 500.0, "g", user_id=1)

        consume_result = consume_amount(owned_item_id, 30, user_id=2)
        refill_result = refill_amount(owned_item_id, 30, user_id=2)

        assert consume_result["success"] is False
        assert refill_result["success"] is False
        assert fridge_repo.get_item(owned_item_id)["current_amount"] == 500.0

        # Der Besitzer selbst darf weiterhin verbrauchen.
        owner_result = consume_amount(owned_item_id, 30, user_id=1)
        assert owner_result["success"] is True
        assert owner_result["new_amount"] == 470.0