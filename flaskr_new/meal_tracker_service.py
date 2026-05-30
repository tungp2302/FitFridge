"""Business logic fuer den Meal Tracker."""
from __future__ import annotations

from typing import Dict

from . import fridge_repo, product_repo
from .fridge_service import update_dashboard_item
from .meal_tracker_repo import DEFAULT_SETTINGS, add_meal_entry, delete_meal_entry, get_recent_meals, get_settings, get_today_totals, save_settings
from .nutrition_service import calculate_for_amount
from .openfoodfacts_client import lookup_product


def normalize_macro_percentages(protein_pct: float, carbs_pct: float, fat_pct: float) -> Dict[str, float]:
    values = {
        "protein_pct": max(0.0, float(protein_pct)),
        "carbs_pct": max(0.0, float(carbs_pct)),
        "fat_pct": max(0.0, float(fat_pct)),
    }
    total = values["protein_pct"] + values["carbs_pct"] + values["fat_pct"]
    if total <= 0:
        return DEFAULT_SETTINGS.copy()
    scale = 100.0 / total
    normalized = {key: round(value * scale, 1) for key, value in values.items()}
    diff = round(100.0 - sum(normalized.values()), 1)
    normalized["fat_pct"] = round(normalized["fat_pct"] + diff, 1)
    return normalized


def calculate_macro_targets(daily_kcal: float, protein_pct: float, carbs_pct: float, fat_pct: float) -> Dict[str, float]:
    protein_kcal = float(daily_kcal) * float(protein_pct) / 100.0
    carbs_kcal = float(daily_kcal) * float(carbs_pct) / 100.0
    fat_kcal = float(daily_kcal) * float(fat_pct) / 100.0

    return {
        "kcal": round(float(daily_kcal), 1),
        "protein_g": round(protein_kcal / 4.0, 1),
        "carbs_g": round(carbs_kcal / 4.0, 1),
        "fat_g": round(fat_kcal / 9.0, 1),
    }


def calculate_open_targets(settings: Dict, consumed: Dict) -> Dict[str, float]:
    targets = calculate_macro_targets(
        settings["daily_kcal"],
        settings["protein_pct"],
        settings["carbs_pct"],
        settings["fat_pct"],
    )
    open_targets = {
        "kcal": round(targets["kcal"] - consumed.get("kcal", 0.0), 1),
        "protein_g": round(targets["protein_g"] - consumed.get("protein_g", 0.0), 1),
        "carbs_g": round(targets["carbs_g"] - consumed.get("carbs_g", 0.0), 1),
        "fat_g": round(targets["fat_g"] - consumed.get("fat_g", 0.0), 1),
    }
    return {**targets, **{f"remaining_{key}": value for key, value in open_targets.items()}}


def build_daily_summary(settings: Dict, consumed: Dict) -> Dict:
    targets = calculate_macro_targets(
        settings["daily_kcal"],
        settings["protein_pct"],
        settings["carbs_pct"],
        settings["fat_pct"],
    )
    remaining = {
        "kcal": round(targets["kcal"] - consumed.get("kcal", 0.0), 1),
        "protein_g": round(targets["protein_g"] - consumed.get("protein_g", 0.0), 1),
        "carbs_g": round(targets["carbs_g"] - consumed.get("carbs_g", 0.0), 1),
        "fat_g": round(targets["fat_g"] - consumed.get("fat_g", 0.0), 1),
    }

    recommendation_parts = []
    if remaining["kcal"] > 0:
        recommendation_parts.append(f"Noch {remaining['kcal']} kcal offen")
    else:
        recommendation_parts.append(f"{abs(remaining['kcal'])} kcal ueber dem Ziel")

    for key, label in (("protein_g", "Protein"), ("carbs_g", "Kohlenhydrate"), ("fat_g", "Fett")):
        if remaining[key] > 0:
            recommendation_parts.append(f"{label}: {remaining[key]} g offen")
        else:
            recommendation_parts.append(f"{label}: {abs(remaining[key])} g ueberschritten")

    return {
        "targets": targets,
        "remaining": remaining,
        "recommendation": "; ".join(recommendation_parts),
    }


def resolve_product_from_barcode(barcode: str, user_id: int | None = None):
    """Resolve a product by barcode and return product row + fridge item if available."""
    barcode = (barcode or "").strip()
    if not barcode:
        return None, None

    product = product_repo.get_by_barcode(barcode)
    if product is None:
        product_data = lookup_product(barcode)
        if not product_data:
            return None, None
        product_id = product_repo.create_product(
            name=product_data.get("name") or "Unnamed",
            brand=product_data.get("brand") or "",
            barcode=product_data.get("barcode") or barcode,
            kcal_per_100g=float(product_data.get("kcal_per_100g") or 0.0),
            protein_per_100g=float(product_data.get("protein_per_100g") or 0.0),
            fat_per_100g=float(product_data.get("fat_per_100g") or 0.0),
            carbs_per_100g=float(product_data.get("carbs_per_100g") or 0.0),
        )
        product = product_repo.get_by_id(product_id)

    fridge_item = None
    fridge_items = fridge_repo.list_items(user_id=user_id)
    if not fridge_items and user_id is not None:
        fridge_items = fridge_repo.list_items()
    for item in fridge_items:
        if item["product_id"] == product["id"]:
            fridge_item = dict(item)
            break

    return dict(product), fridge_item


def log_meal_from_product(user_id: int, product: Dict, amount: float, unit: str, fridge_item_id: int | None = None, section: str | None = None):
    """Log a meal entry and optionally deduct the same amount from the fridge."""
    nutrition = calculate_for_amount(product, amount, unit)
    meal_name = product.get("name") or "Meal"
    entry_id = add_meal_entry(
        user_id=user_id,
        meal_name=meal_name,
        product_id=product.get("id"),
        barcode=product.get("barcode"),
        amount=amount,
        unit=unit,
        kcal=nutrition["kcal"],
        protein_g=nutrition["protein"],
        carbs_g=nutrition["carbs"],
        fat_g=nutrition["fat"],
        note="meal tracker meal",
        section=section,
    )

    deducted = False
    if fridge_item_id is not None:
        fridge_item = fridge_repo.get_item(fridge_item_id, user_id=user_id)
        if fridge_item is None:
            fridge_item = fridge_repo.get_item(fridge_item_id)
        if fridge_item is not None:
            fridge_item_dict = dict(fridge_item)
            current_amount = float(fridge_item["current_amount"])
            remaining_amount = max(0.0, round(current_amount - float(amount), 1))
            update_dashboard_item(
                fridge_item_id,
                current_amount=remaining_amount,
                unit=fridge_item["unit"],
                user_id=user_id if fridge_item_dict.get("user_id") is not None else None,
            )
            deducted = True

    return {
        "entry_id": entry_id,
        "nutrition": nutrition,
        "deducted": deducted,
    }


__all__ = [
    "add_meal_entry",
    "delete_meal_entry",
    "build_daily_summary",
    "log_meal_from_product",
    "normalize_macro_percentages",
    "calculate_macro_targets",
    "calculate_open_targets",
    "resolve_product_from_barcode",
    "get_recent_meals",
    "get_settings",
    "get_today_totals",
    "save_settings",
]
