"""Fachlogik fuer den Fridge-Bereich von FitFridge."""

from . import fridge_repo, product_repo
from .openfoodfacts_client import lookup_product
from flaskr_new.nutrition_service import calculate_for_amount


def _resolve_or_create_product(product_data, fallback_barcode):
    """Find an existing product by barcode or create it from the payload."""
    barcode = product_data.get("barcode") or ""
    product = product_repo.get_by_barcode(barcode) if barcode else None
    if product is not None:
        return product["id"]
    return product_repo.create_product(
        name=product_data.get("name") or "Unnamed",
        brand=product_data.get("brand") or "",
        barcode=barcode or fallback_barcode,
        kcal_per_100g=float(product_data.get("kcal_per_100g") or 0.0),
        protein_per_100g=float(product_data.get("protein_per_100g") or 0.0),
        fat_per_100g=float(product_data.get("fat_per_100g") or 0.0),
        carbs_per_100g=float(product_data.get("carbs_per_100g") or 0.0),
    )


def _add_item_from_product_data(product_data, fallback_barcode, author_id):
    product_id = _resolve_or_create_product(product_data, fallback_barcode)
    current_amount = float(product_data.get("total_amount") or 100.0)
    unit = product_data.get("unit") or "g"
    return fridge_repo.add_item(product_id, current_amount, unit, user_id=author_id)


def create_dashboard_item(query, author_id=None):
    """Produkt per Barcode/Name bei OpenFoodFacts suchen und einlagern."""
    if not query:
        raise ValueError("query is required")

    product_data = lookup_product(query)
    if not product_data:
        raise ValueError("No product found for query")

    return _add_item_from_product_data(product_data, fallback_barcode=query, author_id=author_id)


def create_dashboard_item_from_data(product_data, author_id=None):
    """Create a fridge item directly from an already selected product payload."""
    if not product_data:
        raise ValueError("product_data is required")

    fallback_barcode = product_data.get("name") or "selected-product"
    return _add_item_from_product_data(product_data, fallback_barcode=fallback_barcode, author_id=author_id)


def update_dashboard_item(item_id, current_amount=None, name=None, brand=None, user_id=None):
    """Menge und optional Name/Marke eines Fridge-Items aktualisieren."""
    current_item = fridge_repo.get_item(item_id, user_id=user_id)
    if current_item is None:
        raise ValueError("No fridge item found for id")
    current_item = dict(current_item)

    updated = 0
    if current_amount is not None:
        updated += fridge_repo.update_amount(item_id, float(current_amount))

    if name is not None or brand is not None:
        current_name = current_item.get("name") or ""
        current_brand = current_item.get("brand") or ""
        updated += product_repo.update_product(
            current_item["product_id"], name or current_name, brand or current_brand
        )

    return updated


def calculate_total_nutrition(item):
    """Naehrwerte fuer die aktuelle Menge, als total_*-Keys fuer die Routen."""
    calc = calculate_for_amount(item, item.get("current_amount"), item.get("unit"))
    return {
        "total_kcal": calc.get("kcal", 0.0),
        "total_protein": calc.get("protein", 0.0),
        "total_fat": calc.get("fat", 0.0),
        "total_carbs": calc.get("carbs", 0.0),
    }
