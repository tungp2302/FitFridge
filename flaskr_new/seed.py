"""Demo-Daten fuer FitFridge.

Im Uni-Setup wird die DB bei jedem Serverstart frisch aufgesetzt. Damit der
``demo``-Account (Login: demo / demo) inkl. Beispiel-Inhalten trotzdem immer
verfuegbar ist, spielt ``seed_demo_data`` die Daten in die aktuelle DB ein.
Erwartet einen leeren, frisch initialisierten Datenbestand (siehe ``init_db``).
"""

from werkzeug.security import generate_password_hash

from .consumption_log_repo import log_consume, log_refill
from .db import get_db
from .fridge_repo import add_item
from .meal_tracker_repo import add_meal_entry, save_settings
from .product_repo import create_product


_DEMO_PRODUCTS = [
    {"name": "Nutella", "brand": "Ferrero", "barcode": "demo-nutella-001",
     "kcal_per_100g": 539, "protein_per_100g": 6.3, "fat_per_100g": 30.9,
     "carbs_per_100g": 57.5, "current_amount": 200, "unit": "g"},
    {"name": "Parmesan", "brand": "Grana Padano", "barcode": "demo-parmesan-001",
     "kcal_per_100g": 431, "protein_per_100g": 38.0, "fat_per_100g": 29.0,
     "carbs_per_100g": 4.1, "current_amount": 150, "unit": "g"},
    {"name": "Greek Yogurt", "brand": "FitFridge Demo", "barcode": "demo-yogurt-001",
     "kcal_per_100g": 72, "protein_per_100g": 9.5, "fat_per_100g": 2.0,
     "carbs_per_100g": 3.5, "current_amount": 300, "unit": "g"},
    {"name": "Eggs", "brand": "Local Farm", "barcode": "demo-eggs-001",
     "kcal_per_100g": 143, "protein_per_100g": 12.6, "fat_per_100g": 9.5,
     "carbs_per_100g": 0.7, "current_amount": 6, "unit": "stk"},
    {"name": "Steak", "brand": "FitFridge Demo", "barcode": "demo-steak-001",
     "kcal_per_100g": 217, "protein_per_100g": 26.0, "fat_per_100g": 12.0,
     "carbs_per_100g": 0.0, "current_amount": 250, "unit": "g"},
    {"name": "Kartoffeln", "brand": "FitFridge Demo", "barcode": "demo-potatoes-001",
     "kcal_per_100g": 77, "protein_per_100g": 2.0, "fat_per_100g": 0.1,
     "carbs_per_100g": 17.0, "current_amount": 500, "unit": "g"},
    {"name": "Brokkoli", "brand": "FitFridge Demo", "barcode": "demo-broccoli-001",
     "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4,
     "carbs_per_100g": 7.0, "current_amount": 300, "unit": "g"},
]

_DEMO_MEALS = [
    {"name": "Nutella Toast", "product": "Nutella", "barcode": "demo-nutella-001",
     "kcal": 320, "protein_g": 8, "carbs_g": 40, "fat_g": 12, "amount": 30, "unit": "g"},
    {"name": "Greek Yogurt Bowl", "product": "Greek Yogurt", "barcode": "demo-yogurt-001",
     "kcal": 220, "protein_g": 18, "carbs_g": 20, "fat_g": 6, "amount": 150, "unit": "g"},
    {"name": "Parmesan Pasta", "product": "Parmesan", "barcode": "demo-parmesan-001",
     "kcal": 540, "protein_g": 24, "carbs_g": 62, "fat_g": 18, "amount": 80, "unit": "g"},
]


def seed_demo_data():
    """Legt den demo-Account samt Beispiel-Kuehlschrank und -Mahlzeiten an.

    Idempotent: existiert der demo-Account bereits (z.B. weil der Dev-Reloader
    ``create_app`` mehrfach aufruft), passiert nichts.
    """
    db = get_db()

    if db.execute("SELECT 1 FROM user WHERE username = ?", ("demo",)).fetchone():
        return None

    user_id = db.execute(
        "INSERT INTO user (username, password) VALUES (?, ?)",
        ("demo", generate_password_hash("demo")),
    ).lastrowid

    product_ids = {}
    for product in _DEMO_PRODUCTS:
        product_id = create_product(
            product["name"], product["brand"], product["barcode"],
            product["kcal_per_100g"], product["protein_per_100g"],
            product["fat_per_100g"], product["carbs_per_100g"],
        )
        add_item(product_id, product["current_amount"], product["unit"], user_id=user_id)
        product_ids[product["name"]] = product_id

    log_consume(product_ids["Nutella"], 20, "g", note="demo consumption")
    log_refill(product_ids["Parmesan"], 150, "g", note="demo refill")

    save_settings(user_id, daily_kcal=2200, protein_pct=30, carbs_pct=40, fat_pct=30)

    for meal in _DEMO_MEALS:
        add_meal_entry(
            user_id, meal["name"], kcal=meal["kcal"], protein_g=meal["protein_g"],
            carbs_g=meal["carbs_g"], fat_g=meal["fat_g"],
            product_id=product_ids[meal["product"]], barcode=meal["barcode"],
            amount=meal["amount"], unit=meal["unit"],
        )

    db.commit()
    return user_id
