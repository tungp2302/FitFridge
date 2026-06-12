from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from werkzeug.security import generate_password_hash

from flaskr_new import create_app
from flaskr_new.db import get_db, init_db
from flaskr_new.meal_tracker_repo import add_meal_entry, ensure_schema, save_settings
from flaskr_new.fridge_repo import add_item
from flaskr_new.product_repo import create_product
from flaskr_new.consumption_log_repo import log_consume, log_refill


def seed_demo_data() -> None:
    app = create_app({"TESTING": True})

    with app.app_context():
        init_db()
        ensure_schema()

        db = get_db()

        db.execute("DELETE FROM user")
        db.commit()

        user_id = db.execute(
            "INSERT INTO user (username, password) VALUES (?, ?)",
            ("demo", generate_password_hash("demo")),
        ).lastrowid

        products = [
            {
                "name": "Nutella",
                "brand": "Ferrero",
                "barcode": "demo-nutella-001",
                "kcal_per_100g": 539,
                "protein_per_100g": 6.3,
                "fat_per_100g": 30.9,
                "carbs_per_100g": 57.5,
                "expiry_date": "2026-12-31",
                "current_amount": 200,
                "unit": "g",
            },
            {
                "name": "Parmesan",
                "brand": "Grana Padano",
                "barcode": "demo-parmesan-001",
                "kcal_per_100g": 431,
                "protein_per_100g": 38.0,
                "fat_per_100g": 29.0,
                "carbs_per_100g": 4.1,
                "expiry_date": "2026-11-15",
                "current_amount": 150,
                "unit": "g",
            },
            {
                "name": "Greek Yogurt",
                "brand": "FitFridge Demo",
                "barcode": "demo-yogurt-001",
                "kcal_per_100g": 72,
                "protein_per_100g": 9.5,
                "fat_per_100g": 2.0,
                "carbs_per_100g": 3.5,
                "expiry_date": "2026-06-10",
                "current_amount": 300,
                "unit": "g",
            },
            {
                "name": "Eggs",
                "brand": "Local Farm",
                "barcode": "demo-eggs-001",
                "kcal_per_100g": 143,
                "protein_per_100g": 12.6,
                "fat_per_100g": 9.5,
                "carbs_per_100g": 0.7,
                "expiry_date": "2026-06-01",
                "current_amount": 6,
                "unit": "pcs",
            },
            {
                "name": "Steak",
                "brand": "FitFridge Demo",
                "barcode": "demo-steak-001",
                "kcal_per_100g": 217,
                "protein_per_100g": 26.0,
                "fat_per_100g": 12.0,
                "carbs_per_100g": 0.0,
                "expiry_date": "2026-06-12",
                "current_amount": 250,
                "unit": "g",
            },
            {
                "name": "Kartoffeln",
                "brand": "FitFridge Demo",
                "barcode": "demo-potatoes-001",
                "kcal_per_100g": 77,
                "protein_per_100g": 2.0,
                "fat_per_100g": 0.1,
                "carbs_per_100g": 17.0,
                "expiry_date": "2026-06-20",
                "current_amount": 500,
                "unit": "g",
            },
            {
                "name": "Brokkoli",
                "brand": "FitFridge Demo",
                "barcode": "demo-broccoli-001",
                "kcal_per_100g": 34,
                "protein_per_100g": 2.8,
                "fat_per_100g": 0.4,
                "carbs_per_100g": 7.0,
                "expiry_date": "2026-06-13",
                "current_amount": 300,
                "unit": "g",
            },
        ]

        product_ids: dict[str, int] = {}
        for product in products:
            product_id = create_product(
                product["name"],
                product["brand"],
                product["barcode"],
                product["kcal_per_100g"],
                product["protein_per_100g"],
                product["fat_per_100g"],
                product["carbs_per_100g"],
            )
            db.execute(
                "UPDATE product SET expiry_date = ? WHERE id = ?",
                (product["expiry_date"], product_id),
            )
            add_item(product_id, product["current_amount"], product["unit"], user_id=user_id)
            product_ids[product["name"]] = product_id

        log_consume(product_ids["Nutella"], 20, "g", note="demo consumption")
        log_refill(product_ids["Parmesan"], 150, "g", note="demo refill")

        save_settings(user_id, daily_kcal=2200, protein_pct=30, carbs_pct=40, fat_pct=30)

        add_meal_entry(
            user_id,
            "Nutella Toast",
            kcal=320,
            protein_g=8,
            carbs_g=40,
            fat_g=12,
            product_id=product_ids["Nutella"],
            barcode="demo-nutella-001",
            amount=30,
            unit="g",
            section="Breakfast",
        )
        add_meal_entry(
            user_id,
            "Greek Yogurt Bowl",
            kcal=220,
            protein_g=18,
            carbs_g=20,
            fat_g=6,
            product_id=product_ids["Greek Yogurt"],
            barcode="demo-yogurt-001",
            amount=150,
            unit="g",
            section="Lunch",
        )
        add_meal_entry(
            user_id,
            "Parmesan Pasta",
            kcal=540,
            protein_g=24,
            carbs_g=62,
            fat_g=18,
            product_id=product_ids["Parmesan"],
            barcode="demo-parmesan-001",
            amount=80,
            unit="g",
            section="Dinner",
        )

        db.commit()
        print("Demo data seeded. Login with demo / demo.")


if __name__ == "__main__":
    seed_demo_data()
