"""Demo-Daten für FitFridge.

Im Uni-Setup wird die DB bei jedem Serverstart frisch aufgesetzt. Damit der
``demo``-Account (Login: demo / demo) inkl. Beispiel-Inhalten trotzdem immer
verfügbar ist, spielt ``seed_demo_data`` die Daten in die aktuelle DB ein.
Erwartet einen leeren, frisch initialisierten Datenbestand (siehe ``init_db``).
"""

from werkzeug.security import generate_password_hash

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
     "carbs_per_100g": 0.7, "current_amount": 6, "unit": "stk", "grams_per_piece": 60},
    {"name": "Steak", "brand": "FitFridge Demo", "barcode": "demo-steak-001",
     "kcal_per_100g": 217, "protein_per_100g": 26.0, "fat_per_100g": 12.0,
     "carbs_per_100g": 0.0, "current_amount": 250, "unit": "g"},
    {"name": "Kartoffeln", "brand": "FitFridge Demo", "barcode": "demo-potatoes-001",
     "kcal_per_100g": 77, "protein_per_100g": 2.0, "fat_per_100g": 0.1,
     "carbs_per_100g": 17.0, "current_amount": 500, "unit": "g"},
    {"name": "Brokkoli", "brand": "FitFridge Demo", "barcode": "demo-broccoli-001",
     "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4,
     "carbs_per_100g": 7.0, "current_amount": 300, "unit": "g"},
    # Herzhaft: Hauptspeise / Abendessen
    {"name": "Hähnchenbrust", "brand": "FitFridge Demo", "barcode": "demo-chicken-001",
     "kcal_per_100g": 165, "protein_per_100g": 31.0, "fat_per_100g": 3.6,
     "carbs_per_100g": 0.0, "current_amount": 400, "unit": "g"},
    {"name": "Reis", "brand": "FitFridge Demo", "barcode": "demo-rice-001",
     "kcal_per_100g": 360, "protein_per_100g": 7.0, "fat_per_100g": 0.9,
     "carbs_per_100g": 79.0, "current_amount": 500, "unit": "g"},
    {"name": "Spaghetti", "brand": "FitFridge Demo", "barcode": "demo-pasta-001",
     "kcal_per_100g": 358, "protein_per_100g": 12.0, "fat_per_100g": 1.5,
     "carbs_per_100g": 71.0, "current_amount": 500, "unit": "g"},
    {"name": "Tomaten", "brand": "FitFridge Demo", "barcode": "demo-tomato-001",
     "kcal_per_100g": 18, "protein_per_100g": 0.9, "fat_per_100g": 0.2,
     "carbs_per_100g": 3.9, "current_amount": 400, "unit": "g"},
    {"name": "Zwiebel", "brand": "FitFridge Demo", "barcode": "demo-onion-001",
     "kcal_per_100g": 40, "protein_per_100g": 1.1, "fat_per_100g": 0.1,
     "carbs_per_100g": 9.0, "current_amount": 200, "unit": "g"},
    {"name": "Paprika", "brand": "FitFridge Demo", "barcode": "demo-pepper-001",
     "kcal_per_100g": 31, "protein_per_100g": 1.0, "fat_per_100g": 0.3,
     "carbs_per_100g": 6.0, "current_amount": 300, "unit": "g"},
    {"name": "Olivenöl", "brand": "FitFridge Demo", "barcode": "demo-oil-001",
     "kcal_per_100g": 884, "protein_per_100g": 0.0, "fat_per_100g": 100.0,
     "carbs_per_100g": 0.0, "current_amount": 500, "unit": "ml"},
    # Süß: Frühstück / Nachspeise / Snack
    {"name": "Haferflocken", "brand": "FitFridge Demo", "barcode": "demo-oats-001",
     "kcal_per_100g": 372, "protein_per_100g": 13.5, "fat_per_100g": 7.0,
     "carbs_per_100g": 59.0, "current_amount": 500, "unit": "g"},
    {"name": "Milch", "brand": "FitFridge Demo", "barcode": "demo-milk-001",
     "kcal_per_100g": 64, "protein_per_100g": 3.4, "fat_per_100g": 3.6,
     "carbs_per_100g": 4.8, "current_amount": 1000, "unit": "ml"},
    {"name": "Banane", "brand": "FitFridge Demo", "barcode": "demo-banana-001",
     "kcal_per_100g": 89, "protein_per_100g": 1.1, "fat_per_100g": 0.3,
     "carbs_per_100g": 23.0, "current_amount": 5, "unit": "stk", "grams_per_piece": 120},
    {"name": "Heidelbeeren", "brand": "FitFridge Demo", "barcode": "demo-berries-001",
     "kcal_per_100g": 57, "protein_per_100g": 0.7, "fat_per_100g": 0.3,
     "carbs_per_100g": 14.0, "current_amount": 200, "unit": "g"},
    {"name": "Mehl", "brand": "FitFridge Demo", "barcode": "demo-flour-001",
     "kcal_per_100g": 364, "protein_per_100g": 10.0, "fat_per_100g": 1.0,
     "carbs_per_100g": 76.0, "current_amount": 1000, "unit": "g"},
    {"name": "Honig", "brand": "FitFridge Demo", "barcode": "demo-honey-001",
     "kcal_per_100g": 304, "protein_per_100g": 0.3, "fat_per_100g": 0.0,
     "carbs_per_100g": 82.0, "current_amount": 250, "unit": "g"},
    {"name": "Mandeln", "brand": "FitFridge Demo", "barcode": "demo-almonds-001",
     "kcal_per_100g": 579, "protein_per_100g": 21.0, "fat_per_100g": 50.0,
     "carbs_per_100g": 22.0, "current_amount": 200, "unit": "g"},
    {"name": "Apfel", "brand": "FitFridge Demo", "barcode": "demo-apple-001",
     "kcal_per_100g": 52, "protein_per_100g": 0.3, "fat_per_100g": 0.2,
     "carbs_per_100g": 14.0, "current_amount": 4, "unit": "stk", "grams_per_piece": 180},
    {"name": "Zucker", "brand": "FitFridge Demo", "barcode": "demo-sugar-001",
     "kcal_per_100g": 400, "protein_per_100g": 0.0, "fat_per_100g": 0.0,
     "carbs_per_100g": 100.0, "current_amount": 500, "unit": "g"},
    {"name": "Whey Proteinpulver", "brand": "FitFridge Demo", "barcode": "demo-whey-001",
     "kcal_per_100g": 380, "protein_per_100g": 80.0, "fat_per_100g": 6.0,
     "carbs_per_100g": 8.0, "current_amount": 1000, "unit": "g"},
]

_DEMO_MEALS = [
    {"name": "Nutella Toast", "kcal": 320, "protein_g": 8, "carbs_g": 40, "fat_g": 12, "amount": 30, "unit": "g"},
    {"name": "Greek Yogurt Bowl", "kcal": 220, "protein_g": 18, "carbs_g": 20, "fat_g": 6, "amount": 150, "unit": "g"},
    {"name": "Parmesan Pasta", "kcal": 540, "protein_g": 24, "carbs_g": 62, "fat_g": 18, "amount": 80, "unit": "g"},
]


def seed_demo_data():
    """Legt den demo-Account samt Beispiel-Kühlschrank und -Mahlzeiten an.

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

    for product in _DEMO_PRODUCTS:
        product_id = create_product(
            product["name"], product["brand"], product["barcode"],
            product["kcal_per_100g"], product["protein_per_100g"],
            product["fat_per_100g"], product["carbs_per_100g"],
            product.get("grams_per_piece"),
        )
        add_item(product_id, product["current_amount"], product["unit"], user_id=user_id)

    save_settings(user_id, daily_kcal=2200, protein_pct=30, carbs_pct=40, fat_pct=30)

    for meal in _DEMO_MEALS:
        add_meal_entry(
            user_id, meal["name"], kcal=meal["kcal"], protein_g=meal["protein_g"],
            carbs_g=meal["carbs_g"], fat_g=meal["fat_g"],
            amount=meal["amount"], unit=meal["unit"],
        )

    db.commit()
    return user_id
