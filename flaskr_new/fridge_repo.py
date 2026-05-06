"""Repository-Funktionen fuer die Fridge-/Dashboard-Daten."""

from .db import get_db
from . import product_repo
import time


_FRIDGE_ITEM_SELECT = (
    "SELECT f.id, f.product_id, f.current_amount, f.unit, f.created,"
    " p.name, p.brand, p.barcode,"
    " p.kcal_per_100g, p.protein_per_100g, p.fat_per_100g, p.carbs_per_100g"
    " FROM fridge_item f JOIN product p ON f.product_id = p.id"
)


def list_items():
    """Alle Produkte im Kühlschrank mit Produktdetails abrufen."""
    return get_db().execute(f"{_FRIDGE_ITEM_SELECT} ORDER BY f.created DESC").fetchall()


def get_item(item_id):
    """Ein spezifisches FridgeItem mit Produktdetails abrufen."""
    return get_db().execute(f"{_FRIDGE_ITEM_SELECT} WHERE f.id = ?", (item_id,)).fetchone()


def add_item(product_id, current_amount, unit):
    """Ein neues FridgeItem zur Datenbank hinzufügen."""
    db = get_db()
    cursor = db.execute(
        "INSERT INTO fridge_item (product_id, current_amount, unit)"
        " VALUES (?, ?, ?)",
        (product_id, current_amount, unit),
    )
    db.commit()
    return cursor.lastrowid


def update_amount(item_id, current_amount):
    """Die Menge eines FridgeItems aktualisieren."""
    db = get_db()
    cursor = db.execute(
        "UPDATE fridge_item SET current_amount = ? WHERE id = ?",
        (current_amount, item_id),
    )
    db.commit()
    return cursor.rowcount


def delete_item(item_id):
    """Ein FridgeItem aus dem Kühlschrank entfernen."""
    db = get_db()
    cursor = db.execute("DELETE FROM fridge_item WHERE id = ?", (item_id,))
    db.commit()
    return cursor.rowcount


def create_item(title, body, author_id=None):
    """Compatibility wrapper: create a product and add a fridge_item.

    This adapts the legacy frontend "title/body" inputs to the
    current product/fridge_item schema. It creates a new product with
    zeroed nutrition values and inserts a fridge_item with a default
    amount (100 g). Returns the new fridge_item id.
    """
    # create a simple barcode using a timestamp to keep it unique
    barcode = str(int(time.time() * 1000))
    product_id = product_repo.create_product(
        name=title or "Unnamed",
        brand=body or "",
        barcode=barcode,
        kcal_per_100g=0.0,
        protein_per_100g=0.0,
        fat_per_100g=0.0,
        carbs_per_100g=0.0,
    )
    return add_item(product_id, 100.0, "g")


def update_item(item_id, title=None, body=None):
    """Compatibility wrapper: update product metadata for a fridge_item.

    Updates the linked product's name/brand based on title/body.
    Returns number of affected product rows (1 if successful).
    """
    db = get_db()
    # find product_id for the fridge_item
    row = db.execute("SELECT product_id FROM fridge_item WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return 0
    product_id = row[0]
    db.execute(
        "UPDATE product SET name = ?, brand = ? WHERE id = ?",
        (title or "", body or "", product_id),
    )
    db.commit()
    return 1