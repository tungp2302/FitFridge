"""Repository-Funktionen fuer Produkte."""

from .db import get_db


_PRODUCT_COLUMNS = (
    "id, name, brand, barcode,"
    " kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g"
)


def get_by_barcode(barcode):
    """Produkt nach Barcode abrufen."""
    return get_db().execute(
        f"SELECT {_PRODUCT_COLUMNS} FROM product WHERE barcode = ?",
        (barcode,),
    ).fetchone()


def create_product(name, brand, barcode, kcal_per_100g, 
                   protein_per_100g, fat_per_100g, carbs_per_100g):
    """Ein neues Produkt anlegen (z.B. von OpenFoodFacts API)."""
    db = get_db()
    cursor = db.execute(
        "INSERT INTO product (name, brand, barcode,"
        " kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, brand, barcode, kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g),
    )
    db.commit()
    return cursor.lastrowid


def search_by_name(query: str, limit: int = 10):
    """Search local products by name (case-insensitive, simple LIKE)."""
    q = f"%{query}%"
    return get_db().execute(
        f"SELECT {_PRODUCT_COLUMNS} FROM product WHERE name LIKE ? OR brand LIKE ? ORDER BY name LIMIT ?",
        (q, q, limit),
    ).fetchall()


def update_product(product_id, name, brand):
    """Update name and brand for an existing product."""
    db = get_db()
    cursor = db.execute(
        "UPDATE product SET name = ?, brand = ? WHERE id = ?",
        (name, brand, product_id),
    )
    db.commit()
    return cursor.rowcount