"""Business logic fuer den Meal Tracker."""
from __future__ import annotations

import json
from typing import Dict

from . import fridge_repo
from .fridge_service import create_dashboard_item_from_data, list_dashboard_items, update_dashboard_item
from .meal_tracker_repo import (
    DEFAULT_SETTINGS,
    add_meal_entry,
    delete_meal_entry,
    get_recent_meals,
    get_settings,
    get_today_totals,
    save_settings,
    update_meal_entry_amount,
)
from .nutrition_service import calculate_for_amount


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


def build_daily_summary(settings: Dict) -> Dict:
    """Tagesziele (kcal + Makros in Gramm) fuer die Meal-Tracker-Anzeige."""
    targets = calculate_macro_targets(
        settings["daily_kcal"],
        settings["protein_pct"],
        settings["carbs_pct"],
        settings["fat_pct"],
    )
    return {"targets": targets}


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
        # Scoped lookup: eigene oder besitzerlose Items, nie fremde.
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


# ---------------------------------------------------------------------------
# Action-Handler fuer die /meal-tracker Route.
# Jeder Handler kapselt eine POST-Action und gibt die Flash-Nachricht zurueck.
# ---------------------------------------------------------------------------


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _product_from_payload_item(item: Dict) -> Dict:
    return {
        "name": item.get("name") or "Product",
        "barcode": item.get("barcode") or item.get("name") or "selected-product",
        "kcal_per_100g": _safe_float(item.get("kcal_per_100g"), 0.0),
        "protein_per_100g": _safe_float(item.get("protein_per_100g"), 0.0),
        "fat_per_100g": _safe_float(item.get("fat_per_100g"), 0.0),
        "carbs_per_100g": _safe_float(item.get("carbs_per_100g"), 0.0),
    }


def save_settings_action(user_id: int, form) -> str:
    """Speichert Tagesziel + Makroverteilung aus dem Formular."""
    current = get_settings(user_id)
    daily_kcal = _safe_float(form.get("daily_kcal"), current["daily_kcal"])
    protein_pct = _safe_float(form.get("protein_pct"), current["protein_pct"])
    carbs_pct = _safe_float(form.get("carbs_pct"), current["carbs_pct"])
    fat_pct = _safe_float(form.get("fat_pct"), current["fat_pct"])
    normalized = normalize_macro_percentages(protein_pct, carbs_pct, fat_pct)
    save_settings(
        user_id,
        daily_kcal=daily_kcal,
        protein_pct=normalized["protein_pct"],
        carbs_pct=normalized["carbs_pct"],
        fat_pct=normalized["fat_pct"],
    )
    return "Tagesziel und Macroverteilung gespeichert."


def delete_meal_action(user_id: int, entry_id_raw) -> str:
    """Loescht einen Meal-Eintrag des Nutzers."""
    if not entry_id_raw:
        return "Mahlzeit konnte nicht geloescht werden."
    try:
        deleted = delete_meal_entry(int(entry_id_raw), user_id)
    except ValueError:
        deleted = False
    return "Mahlzeit geloescht." if deleted else "Mahlzeit konnte nicht geloescht werden."


def edit_meal_amount_action(user_id: int, entry_id_raw, new_amount_raw) -> str:
    """Skaliert einen Meal-Eintrag auf eine neue Menge."""
    if not entry_id_raw or not new_amount_raw:
        return "Neue Menge konnte nicht gespeichert werden."
    try:
        updated = update_meal_entry_amount(int(entry_id_raw), user_id, float(new_amount_raw))
    except ValueError:
        updated = False
    return "Menge aktualisiert." if updated else "Neue Menge konnte nicht gespeichert werden."


def track_meals_from_payload(user_id: int, selected_payload_raw: str) -> str:
    """Loggt mehrere ausgewaehlte Produkte; Restmengen wandern in den Fridge."""
    try:
        selected_payload = json.loads(selected_payload_raw)
    except json.JSONDecodeError:
        selected_payload = None

    if not isinstance(selected_payload, list) or not selected_payload:
        return "Bitte mindestens ein Produkt in die Liste aufnehmen."

    logged_names = []
    fridge_saved = 0
    for item in selected_payload:
        if not isinstance(item, dict):
            continue
        amount = _safe_float(item.get("amount"), 0.0)
        if amount <= 0:
            continue
        unit = item.get("unit") or "g"
        selected_product = _product_from_payload_item(item)
        log_meal_from_product(
            user_id,
            selected_product,
            amount,
            unit,
            fridge_item_id=None,
            section=None,
        )
        remaining_amount = _safe_float(item.get("remaining_amount"), 0.0)
        if remaining_amount > 0:
            fridge_payload = {
                **selected_product,
                "brand": item.get("brand") or "",
                "unit": unit,
                "total_amount": remaining_amount,
            }
            create_dashboard_item_from_data(fridge_payload, user_id)
            fridge_saved += 1
        logged_names.append(selected_product["name"])

    if not logged_names:
        return "Bitte mindestens eine Menge groesser als 0 angeben."

    message = f"{len(logged_names)} Produkt(e) gespeichert."
    if fridge_saved:
        message += f" {fridge_saved} Produkt(e) als uebrig in den Kuehlschrank uebernommen."
    return message


def track_meal_from_form(user_id: int, form) -> str:
    """Loggt eine einzelne Mahlzeit aus einem ausgewaehlten Fridge-Item."""
    amount = _safe_float(form.get("amount"), 0.0)
    if amount <= 0:
        return "Bitte eine Menge groesser als 0 angeben."

    fridge_item_id = form.get("fridge_item_id")
    if not fridge_item_id:
        return "Bitte ein Fridge-Item auswaehlen."

    fridge_item = next(
        (item for item in list_dashboard_items(user_id) if str(item["id"]) == str(fridge_item_id)),
        None,
    )
    if fridge_item is None:
        return "Ausgewaehltes Fridge-Item wurde nicht gefunden."

    selected_product = {
        "id": fridge_item["product_id"],
        "name": fridge_item["name"],
        "barcode": fridge_item["barcode"],
        "kcal_per_100g": fridge_item["kcal_per_100g"],
        "protein_per_100g": fridge_item["protein_per_100g"],
        "fat_per_100g": fridge_item["fat_per_100g"],
        "carbs_per_100g": fridge_item["carbs_per_100g"],
    }
    unit = fridge_item["unit"]

    result = log_meal_from_product(
        user_id,
        selected_product,
        amount,
        unit,
        fridge_item_id=fridge_item["id"],
        section=None,
    )
    message = f"{selected_product['name']} mit {amount} {unit} gespeichert."
    if result["deducted"]:
        message += " Bestand im Kuehlschrank wurde reduziert."
    return message


__all__ = [
    "add_meal_entry",
    "delete_meal_entry",
    "build_daily_summary",
    "log_meal_from_product",
    "normalize_macro_percentages",
    "calculate_macro_targets",
    "get_recent_meals",
    "get_settings",
    "get_today_totals",
    "save_settings",
    "save_settings_action",
    "delete_meal_action",
    "edit_meal_amount_action",
    "track_meals_from_payload",
    "track_meal_from_form",
]
