"""Tests für consume_amount und refill_amount aus fridge_service.

Diese Tests prüfen die Edge Cases der von Raam implementierten
Bestands-Tracking-Funktionen:
- Normale Operationen
- Negative/Zero/None-Mengen
- Schutz vor negativen Beständen
- Unbekannte Item-IDs

Tungs Tests für consumption_log-Logging sind separat in
test_fridge_service_logging.py.
"""

import os
import pytest

from flaskr_new import create_app
from flaskr_new import db
from flaskr_new import fridge_repo, product_repo
from flaskr_new.fridge_service import consume_amount, refill_amount


@pytest.fixture
def app():
    """Erstellt eine Test-App mit frischer DB für jeden Test."""
    test_db_path = "/tmp/test_raam_consume_refill.sqlite"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    app = create_app({"TESTING": True, "DATABASE": test_db_path})

    with app.app_context():
        db.init_db()
        yield app

    if os.path.exists(test_db_path):
        os.remove(test_db_path)


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