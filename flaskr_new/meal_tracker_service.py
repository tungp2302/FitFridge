"""Fachlogik für den Meal Tracker (Tagesziel, Makros, Mahlzeiten loggen)."""

from . import fridge_repo
from .calculations import calculate_for_amount, safe_float
from .fridge_service import create_dashboard_item_from_data, update_dashboard_item
from .meal_tracker_repo import (
    DEFAULT_SETTINGS,
    add_meal_entry,
    get_settings,
    save_settings,
)


def normalize_macro_percentages(protein_pct, carbs_pct, fat_pct):
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


def calculate_macro_targets(daily_kcal, protein_pct, carbs_pct, fat_pct):
    protein_kcal = float(daily_kcal) * float(protein_pct) / 100.0
    carbs_kcal = float(daily_kcal) * float(carbs_pct) / 100.0
    fat_kcal = float(daily_kcal) * float(fat_pct) / 100.0

    return {
        "kcal": round(float(daily_kcal), 1),
        "protein_g": round(protein_kcal / 4.0, 1),
        "carbs_g": round(carbs_kcal / 4.0, 1),
        "fat_g": round(fat_kcal / 9.0, 1),
    }


def build_daily_summary(settings, consumed):
    targets = calculate_macro_targets(
        settings["daily_kcal"],
        settings["protein_pct"],
        settings["carbs_pct"],
        settings["fat_pct"],
    )
    remaining = {k: round(targets[k] - consumed.get(k, 0.0), 1) for k in targets}

    return {"targets": targets, "remaining": remaining}


def log_meal_from_product(user_id, product, amount, unit, fridge_item_id=None):
    """Loggt eine Mahlzeit und zieht die Menge optional vom Fridge-Item ab."""
    nutrition = calculate_for_amount(product, amount, unit)
    meal_name = product.get("name") or "Meal"
    entry_id = add_meal_entry(
        user_id=user_id,
        meal_name=meal_name,
        amount=amount,
        unit=unit,
        kcal=nutrition["kcal"],
        protein_g=nutrition["protein"],
        carbs_g=nutrition["carbs"],
        fat_g=nutrition["fat"],
    )

    deducted = False
    if fridge_item_id is not None:
        fridge_item = fridge_repo.get_item(fridge_item_id, user_id=user_id)
        if fridge_item is not None:
            fridge_item_dict = dict(fridge_item)
            current_amount = float(fridge_item["current_amount"])
            remaining_amount = max(0.0, round(current_amount - float(amount), 1))
            update_dashboard_item(
                fridge_item_id,
                current_amount=remaining_amount,
                user_id=user_id if fridge_item_dict.get("user_id") is not None else None,
            )
            deducted = True

    return {
        "entry_id": entry_id,
        "nutrition": nutrition,
        "deducted": deducted,
    }


def save_settings_action(user_id, form):
    """Speichert Tagesziel + Makroverteilung aus dem Formular."""
    current = get_settings(user_id)
    daily_kcal = safe_float(form.get("daily_kcal"), current["daily_kcal"])
    protein_pct = safe_float(form.get("protein_pct"), current["protein_pct"])
    carbs_pct = safe_float(form.get("carbs_pct"), current["carbs_pct"])
    fat_pct = safe_float(form.get("fat_pct"), current["fat_pct"])
    normalized = normalize_macro_percentages(protein_pct, carbs_pct, fat_pct)
    save_settings(
        user_id,
        daily_kcal=daily_kcal,
        protein_pct=normalized["protein_pct"],
        carbs_pct=normalized["carbs_pct"],
        fat_pct=normalized["fat_pct"],
    )
    return "Tagesziel und Macroverteilung gespeichert."


def commit_meal_cart(user_id, cart):
    """Loggt alle Eintraege des Warenkorbs: Fridge-Items werden abgezogen,
    Produkt-Reste landen im Kühlschrank."""
    logged = 0
    fridge_saved = 0
    for item in cart:
        if not isinstance(item, dict):
            continue
        amount = safe_float(item.get("amount"), 0.0)
        if amount <= 0:
            continue

        if item.get("kind") == "fridge":
            fridge_item = fridge_repo.get_item(item.get("fridge_item_id"), user_id=user_id)
            if fridge_item is None:
                continue
            log_meal_from_product(
                user_id, dict(fridge_item), amount, fridge_item["unit"],
                fridge_item_id=fridge_item["id"],
            )
            logged += 1
        else:
            unit = item.get("unit") or "g"
            product = {
                "name": item.get("name") or "Product",
                "barcode": item.get("barcode") or item.get("name") or "selected-product",
                "kcal_per_100g": safe_float(item.get("kcal_per_100g"), 0.0),
                "protein_per_100g": safe_float(item.get("protein_per_100g"), 0.0),
                "fat_per_100g": safe_float(item.get("fat_per_100g"), 0.0),
                "carbs_per_100g": safe_float(item.get("carbs_per_100g"), 0.0),
            }
            log_meal_from_product(user_id, product, amount, unit, fridge_item_id=None)
            remaining = safe_float(item.get("remaining_amount"), 0.0)
            if remaining > 0:
                create_dashboard_item_from_data(
                    {**product, "brand": item.get("brand") or "", "unit": unit, "total_amount": remaining},
                    user_id,
                )
                fridge_saved += 1
            logged += 1

    if not logged:
        return "Der Warenkorb ist leer."
    message = f"{logged} Eintrag/Eintraege erfasst."
    if fridge_saved:
        message += f" {fridge_saved} Rest(e) in den Kühlschrank übernommen."
    return message
