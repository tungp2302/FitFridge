"""Fachlogik für den Fridge-Bereich."""

import sqlite3

from . import fridge_repo, product_repo
from .calculations import calculate_for_amount, safe_float
from .openfoodfacts_client import lookup_product


def _resolve_or_create_product(product_data, fallback_barcode):
    """Find an existing product by barcode or create it from the payload.

    Barcode-lose Items (z.B. KI-Schätzungen) werden unter ihrem Namen als
    Barcode gespeichert; ein erneutes Hinzufügen findet daher den bestehenden
    Eintrag wieder, statt an der UNIQUE-Bedingung zu scheitern.
    """
    barcode = product_data.get("barcode") or fallback_barcode
    product = product_repo.get_by_barcode(barcode)
    if product is not None:
        return product["id"]
    try:
        return product_repo.create_product(
            name=product_data.get("name") or "Unnamed",
            brand=product_data.get("brand") or "",
            barcode=barcode,
            kcal_per_100g=float(product_data.get("kcal_per_100g") or 0.0),
            protein_per_100g=float(product_data.get("protein_per_100g") or 0.0),
            fat_per_100g=float(product_data.get("fat_per_100g") or 0.0),
            carbs_per_100g=float(product_data.get("carbs_per_100g") or 0.0),
            grams_per_piece=safe_float(product_data.get("grams_per_piece")),
        )
    except sqlite3.IntegrityError:
        # Doppelter Barcode (gleiches Item zweimal) -> bestehenden Eintrag nutzen.
        existing = product_repo.get_by_barcode(barcode)
        if existing is None:
            raise
        return existing["id"]


def _add_item_from_product_data(product_data, fallback_barcode, author_id):
    product_id = _resolve_or_create_product(product_data, fallback_barcode)
    current_amount = float(product_data.get("total_amount") or 100.0)
    unit = product_data.get("unit") or "g"
    return fridge_repo.add_item(product_id, current_amount, unit, user_id=author_id)


def create_dashboard_item(query, author_id=None):
    """Look up per barcode/name add zu fridge.

    Produktdatrn und Nährwerte fetched von
    OpenFoodFacts. Fridge amount von parsed quantity
    (`total_amount` + `unit`) mit fallback zu `100 g`.
    """
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


def update_dashboard_item(item_id, current_amount=None, grams_per_piece=None, user_id=None):
    """Menge (und für stk: Gramm pro Stück) eines Fridge-Items aktualisieren.

    Die Suche ist auf den Nutzer gescoped (``user_id``), damit niemand
    über geratene IDs fremde Items ändert. Eine leere oder ungültige Menge
    ist ein No-op statt eines 500ers.
    """
    item = fridge_repo.get_item(item_id, user_id=user_id)
    if item is None:
        raise ValueError("No fridge item found for id")
    gpp = safe_float(grams_per_piece)
    if gpp is not None and gpp > 0:
        product_repo.update_grams_per_piece(item["product_id"], gpp)
    amount = safe_float(current_amount)
    if amount is None or amount < 0:
        return 0
    return fridge_repo.update_amount(item_id, amount)


def calculate_total_nutrition(item):
    """Rechnet per-100g-Werte auf current_amount um, Keys prefixed mit total_."""
    calc = calculate_for_amount(item, item.get("current_amount"), item.get("unit"))
    return {f"total_{k}": v for k, v in calc.items()}
