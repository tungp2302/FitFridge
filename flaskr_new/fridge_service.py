"""Fachlogik fuer den Fridge-Bereich von FitFridge."""

from . import fridge_repo, product_repo
from .consumption_log_repo import log_consume, log_refill
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

    current_item = None
    if current_amount is not None or unit is not None or name is not None or brand is not None:
        current_item = fridge_repo.get_item(item_id)
        if current_item is None:
            raise ValueError("No fridge item found for id")
        current_item = dict(current_item)

    if current_amount is not None:
        previous_amount = float(current_item["current_amount"]) if current_item else 0.0
        new_amount = float(current_amount)
        updated += fridge_repo.update_amount(item_id, new_amount)

        delta = new_amount - previous_amount
        item_unit = unit or (current_item["unit"] if current_item else None) or "g"

        if delta < 0:
            log_consume(
                current_item["product_id"],
                abs(delta),
                item_unit,
                note="update_dashboard_item consume delta",
            )
        elif delta > 0:
            log_refill(
                current_item["product_id"],
                delta,
                item_unit,
                note="update_dashboard_item refill delta",
            )

    # update product metadata if provided
    if name is not None or brand is not None:
        # Find linked product and update its metadata via product_repo
        product_id = current_item["product_id"]
        # Use existing values as fallback if name/brand not provided
        current_name = current_item.get("name") or ""
        current_brand = current_item.get("brand") or ""
        updated += product_repo.update_product(product_id, name or current_name, brand or current_brand)

    return updated


def delete_dashboard_item(item_id):
    return fridge_repo.delete_item(item_id)

def consume_amount(item_id, amount):
    """Reduziert die Restmenge eines Fridge-Items.

    Bei Erfolg wird zusätzlich Tungs consumption_log aktualisiert.

    Edge Cases:
    - amount <= 0 oder None: success=False
    - Item existiert nicht: success=False
    - Mehr verbrauchen als vorhanden: Bestand wird auf 0.0 begrenzt

    Parameter:
        item_id (int): ID des Fridge-Items
        amount (float): Verbrauchte Menge

    Returns:
        dict: {"success": bool, "new_amount": float, "message": str}
    """
    if amount is None or amount <= 0:
        return {
            "success": False,
            "new_amount": 0.0,
            "message": "Menge muss größer als 0 sein.",
        }

    item = fridge_repo.get_item(item_id)
    if item is None:
        return {
            "success": False,
            "new_amount": 0.0,
            "message": f"Produkt mit ID {item_id} nicht im Kühlschrank gefunden.",
        }

    item_dict = dict(item)
    current = float(item_dict["current_amount"])
    new_amount = max(0.0, current - float(amount))

    fridge_repo.update_amount(item_id, new_amount)

    # Tungs consumption_log mit füttern
    try:
        log_consume(
            item_dict["product_id"],
            float(amount),
            item_dict["unit"],
            note="consume_amount direkt",
        )
    except Exception:
        # Falls Logging fehlschlägt, soll trotzdem die Hauptaktion erfolgreich sein
        pass

    return {
        "success": True,
        "new_amount": new_amount,
        "message": f"{amount} {item_dict['unit']} {item_dict['name']} verbraucht. Rest: {new_amount} {item_dict['unit']}.",
    }


def refill_amount(item_id, amount):
    """Erhöht die Restmenge eines Fridge-Items.

    Bei Erfolg wird zusätzlich Tungs consumption_log aktualisiert.

    Edge Cases:
    - amount <= 0 oder None: success=False
    - Item existiert nicht: success=False

    Parameter:
        item_id (int): ID des Fridge-Items
        amount (float): Hinzugefügte Menge

    Returns:
        dict: {"success": bool, "new_amount": float, "message": str}
    """
    if amount is None or amount <= 0:
        return {
            "success": False,
            "new_amount": 0.0,
            "message": "Menge muss größer als 0 sein.",
        }

    item = fridge_repo.get_item(item_id)
    if item is None:
        return {
            "success": False,
            "new_amount": 0.0,
            "message": f"Produkt mit ID {item_id} nicht im Kühlschrank gefunden.",
        }

    item_dict = dict(item)
    current = float(item_dict["current_amount"])
    new_amount = current + float(amount)

    fridge_repo.update_amount(item_id, new_amount)

    # Tungs consumption_log mit füttern
    try:
        log_refill(
            item_dict["product_id"],
            float(amount),
            item_dict["unit"],
            note="refill_amount direkt",
        )
    except Exception:
        pass

    return {
        "success": True,
        "new_amount": new_amount,
        "message": f"{amount} {item_dict['unit']} {item_dict['name']} aufgefüllt. Neuer Stand: {new_amount} {item_dict['unit']}.",
    }

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
