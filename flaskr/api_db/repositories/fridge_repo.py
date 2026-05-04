"""Repository-Funktionen fuer die Fridge-/Dashboard-Daten."""

from ..db import get_db


def list_items():
    """Alle Produkte im Kühlschrank mit Produktdetails abrufen."""
    return get_db().execute(
        "SELECT f.id, f.product_id, f.current_amount, f.unit, f.created,"
        " p.name, p.brand, p.barcode,"
        " p.kcal_per_100g, p.protein_per_100g, p.fat_per_100g, p.carbs_per_100g"
        " FROM fridge_item f JOIN product p ON f.product_id = p.id"
        " ORDER BY f.created DESC"
    ).fetchall()


def get_item(item_id):
    """Ein spezifisches FridgeItem mit Produktdetails abrufen."""
    return get_db().execute(
        "SELECT f.id, f.product_id, f.current_amount, f.unit, f.created,"
        " p.name, p.brand, p.barcode,"
        " p.kcal_per_100g, p.protein_per_100g, p.fat_per_100g, p.carbs_per_100g"
        " FROM fridge_item f JOIN product p ON f.product_id = p.id"
        " WHERE f.id = ?",
        (item_id,),
    ).fetchone()


def add_item(product_id, current_amount, unit):
    """Ein neues FridgeItem zur Datenbank hinzufügen."""
    db = get_db()
    db.execute(
        "INSERT INTO fridge_item (product_id, current_amount, unit)"
        " VALUES (?, ?, ?)",
        (product_id, current_amount, unit),
    )
    db.commit()


def update_amount(item_id, current_amount):
    """Die Menge eines FridgeItems aktualisieren."""
    db = get_db()
    db.execute(
        "UPDATE fridge_item SET current_amount = ? WHERE id = ?",
        (current_amount, item_id),
    )
    db.commit()


def delete_item(item_id):
    """Ein FridgeItem aus dem Kühlschrank entfernen."""
    db = get_db()
    db.execute("DELETE FROM fridge_item WHERE id = ?", (item_id,))
    db.commit()