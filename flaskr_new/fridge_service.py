"""Fachlogik fuer den Fridge-Bereich von FitFridge."""

from . import fridge_repo, product_repo
from .openfoodfacts_client import lookup_product


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
        # fridge_repo.update_item will find the linked product and update it
        updated += fridge_repo.update_item(item_id, name or "", brand or "")

    return updated


def delete_dashboard_item(item_id):
    return fridge_repo.delete_item(item_id)


def calculate_total_nutrition(item):
    """Calculate total nutrition values for the actual fridge amount.
    
    Takes a fridge item (with current_amount, unit, and per-100g nutrition values)
    and returns a dict with total_kcal, total_protein, total_fat, total_carbs
    based on the current amount. Assumes unit is 'g' (grams).
    """
    if item["unit"] != "g":
        # For non-gram units, return zero nutrition (could add conversion logic later)
        return {
            "total_kcal": 0.0,
            "total_protein": 0.0,
            "total_fat": 0.0,
            "total_carbs": 0.0,
        }
    
    multiplier = item["current_amount"] / 100.0
    return {
        "total_kcal": round(item["kcal_per_100g"] * multiplier, 1),
        "total_protein": round(item["protein_per_100g"] * multiplier, 1),
        "total_fat": round(item["fat_per_100g"] * multiplier, 1),
        "total_carbs": round(item["carbs_per_100g"] * multiplier, 1),
    }
