"""Repository-Funktionen fuer Produkte."""

from .db import get_db


def get_by_barcode(barcode):
    """Produkt nach Barcode abrufen."""
    return get_db().execute(
        "SELECT id, name, brand, barcode,"
        " kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g"
        " FROM product WHERE barcode = ?",
        (barcode,),
    ).fetchone()


def get_by_id(product_id):
    """Produkt nach ID abrufen."""
    return get_db().execute(
        "SELECT id, name, brand, barcode,"
        " kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g"
        " FROM product WHERE id = ?",
        (product_id,),
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


def list_all():
    """Alle Produkte abrufen."""
    return get_db().execute(
        "SELECT id, name, brand, barcode,"
        " kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g"
        " FROM product ORDER BY name"
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