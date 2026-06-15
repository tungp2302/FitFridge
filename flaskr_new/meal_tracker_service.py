"""Fachlogik fuer den Meal Tracker (Tagesziel, Makros, Mahlzeiten loggen)."""

import json

from . import fridge_repo, product_repo
from .fridge_service import create_dashboard_item_from_data, list_dashboard_items, update_dashboard_item
from .meal_tracker_repo import (
    DEFAULT_SETTINGS,
    add_meal_entry,
    delete_meal_entry,
    get_today_meals,
    get_settings,
    get_today_totals,
    save_settings,
    update_meal_entry_amount,
)
from .nutrition_service import calculate_for_amount
from .openfoodfacts_client import lookup_product


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


def resolve_product_from_barcode(barcode, user_id=None):
    """Sucht ein Produkt per Barcode und gibt (Produkt, Fridge-Item) zurueck."""
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
    # Nur die Items des Nutzers durchsuchen - kein Fallback auf fremde Items.
    fridge_items = fridge_repo.list_items(user_id=user_id)
    for item in fridge_items:
        if item["product_id"] == product["id"]:
            fridge_item = dict(item)
            break

    return dict(product), fridge_item


def log_meal_from_product(user_id, product, amount, unit, fridge_item_id=None):
    """Loggt eine Mahlzeit und zieht die Menge optional vom Fridge-Item ab."""
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
                unit=fridge_item["unit"],
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


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _product_from_payload_item(item):
    return {
        "name": item.get("name") or "Product",
        "barcode": item.get("barcode") or item.get("name") or "selected-product",
        "kcal_per_100g": _safe_float(item.get("kcal_per_100g"), 0.0),
        "protein_per_100g": _safe_float(item.get("protein_per_100g"), 0.0),
        "fat_per_100g": _safe_float(item.get("fat_per_100g"), 0.0),
        "carbs_per_100g": _safe_float(item.get("carbs_per_100g"), 0.0),
    }


def save_settings_action(user_id, form):
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


def delete_meal_action(user_id, entry_id_raw):
    """Loescht einen Meal-Eintrag des Nutzers."""
    if not entry_id_raw:
        return "Mahlzeit konnte nicht geloescht werden."
    try:
        deleted = delete_meal_entry(int(entry_id_raw), user_id)
    except ValueError:
        deleted = False
    return "Mahlzeit geloescht." if deleted else "Mahlzeit konnte nicht geloescht werden."


def edit_meal_amount_action(user_id, entry_id_raw, new_amount_raw):
    """Skaliert einen Meal-Eintrag auf eine neue Menge."""
    if not entry_id_raw or not new_amount_raw:
        return "Neue Menge konnte nicht gespeichert werden."
    try:
        updated = update_meal_entry_amount(int(entry_id_raw), user_id, float(new_amount_raw))
    except ValueError:
        updated = False
    return "Menge aktualisiert." if updated else "Neue Menge konnte nicht gespeichert werden."


def track_meals_from_payload(user_id, selected_payload_raw):
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


def track_meal_from_form(user_id, form):
    """Loggt eine einzelne Mahlzeit aus Fridge-Item oder Barcode."""
    amount = _safe_float(form.get("amount"), 0.0)
    if amount <= 0:
        return "Bitte eine Menge groesser als 0 angeben."

    fridge_item_id = form.get("fridge_item_id")
    barcode = (form.get("barcode") or "").strip()
    selected_product = None
    selected_fridge_item_id = None
    unit = "g"

    if fridge_item_id:
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
        selected_fridge_item_id = fridge_item["id"]
        unit = fridge_item["unit"]
    elif barcode:
        selected_product, fridge_item = resolve_product_from_barcode(barcode, user_id)
        if selected_product is None:
            return "Barcode konnte keinem Produkt zugeordnet werden."
        if fridge_item is not None:
            selected_fridge_item_id = fridge_item["id"]
            unit = fridge_item["unit"]
    else:
        return "Bitte ein Barcode oder ein Fridge-Item auswaehlen."

    result = log_meal_from_product(
        user_id,
        selected_product,
        amount,
        unit,
        fridge_item_id=selected_fridge_item_id,
    )
    message = f"{selected_product['name']} mit {amount} {unit} gespeichert."
    if result["deducted"]:
        message += " Bestand im Kuehlschrank wurde reduziert."
    return message
