"""Unit-Tests für den Open-Food-Facts-Client (reine Funktionen, kein Netz)."""
import json

from flaskr_new import openfoodfacts_client as ofc


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

    assert ofc.search_product("3017620422003") == product_payload()


# --- Mengen-Parser: Multiplikatoren, Einheiten-Normalisierung, Fallback ---

def test_parse_total_quantity_handles_multipliers_units_and_fallback():
    parse = ofc._parse_total_quantity
    assert parse({"quantity": "2 x 250 g"}) == (500.0, "g")   # Multiplikator
    assert parse({"quantity": "4x100g"}) == (400.0, "g")      # ohne Leerzeichen
    assert parse({"quantity": "1,5 kg"}) == (1.5, "kg")       # Komma-Dezimal
    assert parse({"quantity": "6 x 1 stueck"}) == (6.0, "stk")  # Einheit normalisiert
    assert parse({"quantity": "", "serving_size": "30 g"}) == (30.0, "g")  # Fallback
    assert parse({"quantity": ""}) == (None, None)            # nichts angegeben


# --- Energie-Normalisierung: kcal bevorzugt, sonst kJ/4.184 ---

def test_kcal_from_nutriments_prefers_kcal_then_kj():
    kcal = ofc._kcal_from_nutriments
    assert kcal({"energy-kcal_100g": "250"}) == 250.0
    assert kcal({"energy-kcal_value": "240"}) == 240.0
    assert round(kcal({"energy_100g": "2000"}), 1) == round(2000 / 4.184, 1)
    assert kcal({}) == 0.0


# --- Ranking: exakt (60) > Teilstring (35) > Token (15) > nichts (0) ---

def test_off_score_tiers():
    score = ofc._score_off_product
    assert score("Apfel", {"name": "Apfel"}) == 60.0              # exakt
    assert score("Apfel", {"name": "Roter Apfel"}) == 35.0        # Teilstring
    assert score("Apfel Saft", {"name": "Bananen Saft"}) == 15.0  # nur Token "saft"
    assert score("Apfel", {"name": "Banane"}) == 0.0              # kein Treffer
    assert score("", {"name": "Apfel"}) == 0.0                    # leere Anfrage
