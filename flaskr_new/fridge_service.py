"""Fachlogik fuer den Fridge-Bereich von FitFridge."""

from . import fridge_repo, product_repo
from .openfoodfacts_client import lookup_product
from flaskr_new.nutrition_service import calculate_for_amount

def list_dashboard_items():
    return fridge_repo.list_items()


def get_dashboard_item(item_id):
    return fridge_repo.get_item(item_id)


def create_dashboard_item(query, author_id=None):
    """Look up product by barcode/name and add it to the fridge.

    The product metadata and nutrition values are fetched from
    OpenFoodFacts. The fridge amount is derived from parsed quantity
    (`total_amount` + `unit`) with a fallback to `100 g`.
    """
    if not query:
        raise ValueError("query is required")

    product_data = lookup_product(query)
    if not product_data:
        raise ValueError("No product found for query")

    barcode = product_data.get("barcode")
    product = product_repo.get_by_barcode(barcode) if barcode else None

    if product is None:
        product_id = product_repo.create_product(
            name=product_data.get("name") or "Unnamed",
            brand=product_data.get("brand") or "",
            barcode=barcode or query,
            kcal_per_100g=float(product_data.get("kcal_per_100g") or 0.0),
            protein_per_100g=float(product_data.get("protein_per_100g") or 0.0),
            fat_per_100g=float(product_data.get("fat_per_100g") or 0.0),
            carbs_per_100g=float(product_data.get("carbs_per_100g") or 0.0),
        )
    else:
        product_id = product["id"]

    current_amount = float(product_data.get("total_amount") or 100.0)
    unit = product_data.get("unit") or "g"
    return fridge_repo.add_item(product_id, current_amount, unit)


def update_dashboard_item(item_id, current_amount=None, unit=None, name=None, brand=None):
    """Update fridge item amount and optionally product metadata."""
    updated = 0
    if current_amount is not None:
        updated += fridge_repo.update_amount(item_id, float(current_amount))

    # update product metadata if provided
    if name is not None or brand is not None:
        # Find linked product and update its metadata via product_repo
        item = fridge_repo.get_item(item_id)
        if not item:
            raise ValueError("No fridge item found for id")
        product_id = item["product_id"]
        # Use existing values as fallback if name/brand not provided
        current_name = item.get("name") or ""
        current_brand = item.get("brand") or ""
        updated += product_repo.update_product(product_id, name or current_name, brand or current_brand)

    return updated


def delete_dashboard_item(item_id):
    return fridge_repo.delete_item(item_id)


def calculate_total_nutrition(item):
    """
    Thin wrapper: nutzt nutrition_service.calculate_for_amount und
    mapped das Ergebnis zu den legacy-Routen-Keys.
    Erwartetes item: enthält current_amount, unit und die per-100g-Felder.
    Defensive Defaults werden benutzt, falls Felder fehlen.
    """
    # Defensive reads, fallbacks zu 0 / leerer Einheit falls nötig
    amount = item.get("current_amount")
    unit = item.get("unit")

    product_nutrients = {
        "kcal_per_100g": item.get("kcal_per_100g", 0.0),
        "protein_per_100g": item.get("protein_per_100g", 0.0),
        "fat_per_100g": item.get("fat_per_100g", 0.0),
        "carbs_per_100g": item.get("carbs_per_100g", 0.0),
    }

    # Delegation an Raams Funktion (handle edge-cases dort)
    calc = calculate_for_amount(product_nutrients, amount, unit)

    # Mappe auf die bisherigen Keys, die routes.py erwartet
    return {
        "total_kcal": calc.get("kcal", 0.0),
        "total_protein": calc.get("protein", 0.0),
        "total_fat": calc.get("fat", 0.0),
        "total_carbs": calc.get("carbs", 0.0),
    }

def consume_amount(item_id, amount):
    """
    Reduziert die Restmenge eines Fridge-Items um die verbrauchte Menge.

    Wird aufgerufen, wenn ein User sagt: "Ich habe X verbraucht".
    Wenn die zu verbrauchende Menge größer ist als der aktuelle Bestand,
    wird die Menge auf 0 gesetzt (statt negativ zu werden).

    Beispiel:
        Item hat current_amount = 480
        consume_amount(item_id, 30)
        → neuer Bestand: 450

    Parameter:
        item_id (int): ID des Fridge-Items in der Datenbank
        amount (float): Menge, die verbraucht wurde

    Returns:
        dict: {"success": bool, "new_amount": float, "message": str}
              success=False bei ungültigen Eingaben oder unbekanntem Item.
    """
    # Edge Case 1: Ungültige Menge
    if amount is None or amount <= 0:
        return {
            "success": False,
            "new_amount": 0.0,
            "message": "Menge muss größer als 0 sein.",
        }

    # Edge Case 2: Item existiert nicht
    item = fridge_repo.get_item(item_id)
    if item is None:
        return {
            "success": False,
            "new_amount": 0.0,
            "message": f"Produkt mit ID {item_id} nicht im Kühlschrank gefunden.",
        }

    # Neue Menge berechnen, nicht unter 0 gehen
    current = float(item["current_amount"])
    new_amount = max(0.0, current - float(amount))

    # In DB speichern
    fridge_repo.update_amount(item_id, new_amount)

    return {
        "success": True,
        "new_amount": new_amount,
        "message": f"{amount} {item['unit']} {item['name']} verbraucht. Rest: {new_amount} {item['unit']}.",
    }


def refill_amount(item_id, amount):
    """
    Erhöht die Restmenge eines Fridge-Items (z.B. neue Packung gekauft).

    Beispiel:
        Item hat current_amount = 50
        refill_amount(item_id, 500)
        → neuer Bestand: 550

    Parameter:
        item_id (int): ID des Fridge-Items in der Datenbank
        amount (float): Menge, die hinzugefügt wird

    Returns:
        dict: {"success": bool, "new_amount": float, "message": str}
    """
    # Edge Case 1: Ungültige Menge
    if amount is None or amount <= 0:
        return {
            "success": False,
            "new_amount": 0.0,
            "message": "Menge muss größer als 0 sein.",
        }

    # Edge Case 2: Item existiert nicht
    item = fridge_repo.get_item(item_id)
    if item is None:
        return {
            "success": False,
            "new_amount": 0.0,
            "message": f"Produkt mit ID {item_id} nicht im Kühlschrank gefunden.",
        }

    # Neue Menge berechnen
    current = float(item["current_amount"])
    new_amount = current + float(amount)

    # In DB speichern
    fridge_repo.update_amount(item_id, new_amount)

    return {
        "success": True,
        "new_amount": new_amount,
        "message": f"{amount} {item['unit']} {item['name']} aufgefüllt. Neuer Stand: {new_amount} {item['unit']}.",
    }

