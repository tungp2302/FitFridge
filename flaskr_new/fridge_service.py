"""Fachlogik fuer den Fridge-Bereich von FitFridge.

This module exposes clear, explicit service functions that operate on
products and fridge items using `product_id`, `current_amount` and
`unit` as canonical parameters. It adapts to existing DB helpers in
`fridge_repo` and `product_repo`.
"""

from . import fridge_repo, product_repo


def list_dashboard_items():
    return fridge_repo.list_items()


def get_dashboard_item(item_id):
    return fridge_repo.get_item(item_id)


def create_dashboard_item(name, brand, barcode, current_amount, unit, author_id=None):
    """Neues Produkt erstellen oder wiederverwenden und es dem Kühlschrank hinzufügen."""
    product = None
    if barcode:
        product = product_repo.get_by_barcode(barcode)

    if product is None:
        product_id = product_repo.create_product(
            name=name or "Unnamed",
            brand=brand or "",
            barcode=barcode or "",
            kcal_per_100g=0.0,
            protein_per_100g=0.0,
            fat_per_100g=0.0,
            carbs_per_100g=0.0,
        )
    else:
        product_id = product["id"]

    return fridge_repo.add_item(product_id, float(current_amount), unit)


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
