"""Fachlogik fuer Produktdaten."""

from . import product_repo


def _to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def create_product(
    name,
    brand,
    barcode,
    kcal_per_100g=0.0,
    protein_per_100g=0.0,
    fat_per_100g=0.0,
    carbs_per_100g=0.0,
):
    """Create a new product if barcode is unknown, otherwise return existing product id."""
    if not barcode:
        raise ValueError("barcode is required")

    existing = product_repo.get_by_barcode(str(barcode))
    if existing is not None:
        return existing["id"]

    if not name:
        name = "Unnamed"

    return product_repo.create_product(
        name=str(name),
        brand=str(brand or ""),
        barcode=str(barcode),
        kcal_per_100g=_to_float(kcal_per_100g),
        protein_per_100g=_to_float(protein_per_100g),
        fat_per_100g=_to_float(fat_per_100g),
        carbs_per_100g=_to_float(carbs_per_100g),
    )


def get_product(product_id):
    return product_repo.get_by_id(product_id)


def get_product_by_barcode(barcode):
    if not barcode:
        return None
    return product_repo.get_by_barcode(str(barcode))


def list_products():
    return product_repo.list_all()