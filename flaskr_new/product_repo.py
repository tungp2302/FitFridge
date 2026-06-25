"""Repo-Funktionen."""

from .db import get_db

_PRODUCT_SELECT = "SELECT id, name, brand, barcode, kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g, grams_per_piece FROM product"


def get_by_barcode(barcode):
    """Produkt nach Barcode abrufen."""
    return get_db().execute(f"{_PRODUCT_SELECT} WHERE barcode = ?", (barcode,)).fetchone()


def create_product(name, brand, barcode, kcal_per_100g,
                   protein_per_100g, fat_per_100g, carbs_per_100g, grams_per_piece=None):
    """Ein neues Produkt anlegen (z.B. von OpenFoodFacts API)."""
    db = get_db()
    cursor = db.execute(
        "INSERT INTO product (name, brand, barcode,"
        " kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g, grams_per_piece)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, brand, barcode, kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g, grams_per_piece),
    )
    db.commit()
    return cursor.lastrowid


def search_by_name(query, limit=10):
    """Search local products by name (case-insensitive, simple LIKE)."""
    q = f"%{query}%"
    return get_db().execute(
        f"{_PRODUCT_SELECT} WHERE name LIKE ? OR brand LIKE ? ORDER BY name LIMIT ?",
        (q, q, limit),
    ).fetchall()