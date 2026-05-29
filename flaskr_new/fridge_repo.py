"""Repository-Funktionen fuer die Fridge-/Dashboard-Daten."""

from .db import get_db


_FRIDGE_ITEM_SELECT = (
    "SELECT f.id, f.user_id, f.product_id, f.current_amount, f.unit, f.created,"
    " p.name, p.brand, p.barcode,"
    " p.kcal_per_100g, p.protein_per_100g, p.fat_per_100g, p.carbs_per_100g"
    " FROM fridge_item f JOIN product p ON f.product_id = p.id"
)


def list_items(user_id=None):
    """Alle Produkte im Kühlschrank mit Produktdetails abrufen."""
    if user_id is None:
        return get_db().execute(f"{_FRIDGE_ITEM_SELECT} ORDER BY f.created DESC").fetchall()
    return get_db().execute(
        f"{_FRIDGE_ITEM_SELECT} WHERE f.user_id = ? ORDER BY f.created DESC",
        (user_id,),
    ).fetchall()


def ensure_schema():
    db = get_db()
    table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fridge_item'"
    ).fetchone()
    if table_exists is None:
        return
    existing_columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(fridge_item)").fetchall()
    }
    if "user_id" not in existing_columns:
        db.execute("ALTER TABLE fridge_item ADD COLUMN user_id INTEGER")
        db.commit()


def get_item(item_id, user_id=None):
    """Ein spezifisches FridgeItem mit Produktdetails abrufen."""
    if user_id is None:
        return get_db().execute(f"{_FRIDGE_ITEM_SELECT} WHERE f.id = ?", (item_id,)).fetchone()
    return get_db().execute(
        f"{_FRIDGE_ITEM_SELECT} WHERE f.id = ? AND f.user_id = ?",
        (item_id, user_id),
    ).fetchone()


def add_item(product_id, current_amount, unit, user_id=None):
    """Ein neues FridgeItem zur Datenbank hinzufügen."""
    db = get_db()
    if user_id is None:
        cursor = db.execute(
            "INSERT INTO fridge_item (product_id, current_amount, unit)"
            " VALUES (?, ?, ?)",
            (product_id, current_amount, unit),
        )
    else:
        cursor = db.execute(
            "INSERT INTO fridge_item (user_id, product_id, current_amount, unit)"
            " VALUES (?, ?, ?, ?)",
            (user_id, product_id, current_amount, unit),
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


def delete_item(item_id, user_id=None):
    """Ein FridgeItem aus dem Kühlschrank entfernen."""
    db = get_db()
    if user_id is None:
        cursor = db.execute("DELETE FROM fridge_item WHERE id = ?", (item_id,))
    else:
        cursor = db.execute("DELETE FROM fridge_item WHERE id = ? AND user_id = ?", (item_id, user_id))
    db.commit()
    return cursor.rowcount

