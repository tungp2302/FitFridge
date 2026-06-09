"""Freestyle recipe generation for FitFridge."""
from __future__ import annotations

import json
import re

from .ollama_client import generate_from_ollama, resolve_ollama_model


ALLOWED_PANTRY_TERMS = (
    "zwiebel",
    "knoblauch",
    "oil",
    "salt",
    "pepper",
    "wasser",
    "milch",
    "oel",
    "öl",
    "salz",
    "pfeffer",
    "backpulver",
    "gewuerz",
    "gewürz",
    "gewuerze",
    "gewürze",
)

CORE_FOOD_TERM_GROUPS = (
    ("salmon", "lachs", "fish", "fisch"),
    ("chicken", "huhn"),
    ("beef", "rind", "steak"),
    ("pasta", "nudel", "noodle"),
    ("rice", "reis"),
    ("potato", "kartoffel"),
)

SWEET_SPREAD_TERMS = (
    "nutella",
    "chocolate spread",
    "schoko",
    "marmelade",
    "jam",
)

MAIN_DISH_ANCHOR_TERMS = (
    "steak",
    "beef",
    "rind",
    "potato",
    "kartoffel",
    "brokkoli",
    "broccoli",
    "vegetable",
    "gemuese",
    "gemüse",
    "parmesan",
)

MACRO_TARGET_TOLERANCE_GRAMS = 10
NUTRITION_FIELDS = ("kcal_per_100g", "protein_per_100g", "fat_per_100g", "carbs_per_100g")

DEFAULT_MODEL_PROFILE = {
    "id": "standard",
    "max_items": None,
    "num_predict": 900,
    "allow_retry": True,
    "compact_prompt": False,
    "prompt_style": "standard",
    "fallback_on_invalid": True,
    "repair_response": False,
}

SMALL_MODEL_PROFILES = {
    "qwen3:4b": {
        "id": "compact",
        "max_items": 7,
        "num_predict": 320,
        "allow_retry": False,
        "compact_prompt": True,
        "prompt_style": "compact",
        "fallback_on_invalid": True,
        "repair_response": True,
    },
    "gemma3:1b": {
        "id": "tiny",
        "max_items": 5,
        "num_predict": 420,
        "allow_retry": False,
        "compact_prompt": True,
        "prompt_style": "gemma",
        "fallback_on_invalid": True,
        "repair_response": True,
    },
}


def _normalize(value: str) -> str:
    return (value or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")


def _item_names(fridge_items):
    return [item.get("name", "").strip() for item in fridge_items if item.get("name")]


def _numbered_fridge_items(fridge_items, include_nutrition=True):
    numbered = []
    for index, item in enumerate(fridge_items, start=1):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        numbered_item = {
            "id": index,
            "name": name,
            "amount": item.get("amount"),
            "unit": item.get("unit"),
        }
        if include_nutrition:
            for field in NUTRITION_FIELDS:
                if item.get(field) not in (None, ""):
                    numbered_item[field] = item.get(field)
        numbered.append(numbered_item)
    return numbered


def _model_profile(model=None):
    selected_model = (resolve_ollama_model(model) or "").lower()
    profile = dict(DEFAULT_MODEL_PROFILE)
    profile.update(SMALL_MODEL_PROFILES.get(selected_model, {}))
    return profile


def _limit_fridge_items(fridge_items, max_items):
    if not max_items:
        return fridge_items
    return [item for item in fridge_items if item.get("name")][:max_items]


def _rank_recipe_item(item, recipe_category=None):
    name = _normalize(item.get("name", ""))
    category = _normalize(recipe_category or "")
    if category in ("hauptspeise", "abendessen"):
        if any(term in name for term in ("steak", "huhn", "chicken", "rind", "beef", "tofu", "fisch", "fish")):
            return 0
        if any(term in name for term in ("kartoffel", "potato", "reis", "rice", "pasta", "nudel")):
            return 1
        if any(term in name for term in ("brokkoli", "broccoli", "paprika", "tomate", "tomato", "gemuese", "gemüse", "vegetable")):
            return 2
        if any(term in name for term in ("egg", "ei", "parmesan", "kaese", "käse", "yogurt", "joghurt")):
            return 3
        if _is_sweet_spread(name):
            return 6
    return 4


def _rank_fridge_items_for_prompt(fridge_items, recipe_category=None):
    indexed = list(enumerate(fridge_items))
    ranked = sorted(indexed, key=lambda pair: (_rank_recipe_item(pair[1], recipe_category), pair[0]))
    return [item for _, item in ranked]


def _compact_daily_goal(daily_goal):
    if not isinstance(daily_goal, dict):
        return {}
    compact = {}
    for key in ("protein", "fat", "kcal"):
        value = daily_goal.get(key)
        if value not in (None, ""):
            compact[key] = value
    return compact


def build_freestyle_recipe_prompt(
    fridge_items,
    daily_goal=None,
    recipe_category=None,
    retry_reason=None,
    compact=False,
    prompt_style=None,
):
    """Build a strict JSON prompt for one realistic fridge-based recipe."""
    payload = {
        "fridge_items": _numbered_fridge_items(fridge_items, include_nutrition=not compact),
        "daily_goal_remaining": _compact_daily_goal(daily_goal) if compact else daily_goal or {},
        "recipe_category": recipe_category or "",
    }
    category_hint = f"Die Rezeptart soll {recipe_category} sein und Zutaten/Technik müssen dazu passen. " if recipe_category else ""
    retry_hint = f"Vorheriger Fehler: {retry_reason}. Erzeuge das JSON korrigiert neu. " if retry_reason else ""

    if prompt_style == "gemma":
        fridge_list = ", ".join(
            f'{item["id"]} {item["name"]}' for item in payload["fridge_items"]
        )
        target_parts = []
        for key, suffix in (("protein", "g protein"), ("fat", "g fat"), ("kcal", "kcal")):
            value = payload["daily_goal_remaining"].get(key)
            if value not in (None, ""):
                target_parts.append(f"{value}{suffix}")
        target_hint = f" Targets: {', '.join(target_parts)}." if target_parts else ""
        category = recipe_category or "simple meal"
        return (
            "Return ONLY one JSON object. "
            f"Make one {category} recipe using only these fridge foods: {fridge_list}. "
            "Use 1-3 fridge IDs. Combining foods is optional; choose the smallest coherent subset. "
            "For a main course, prefer protein + potato/rice/noodle if listed + vegetable if listed. "
            "If one fridge food already fits the request, use only that one. "
            "Pantry allowed: oil, salt, pepper, water. "
            "Do not mention or use salmon, fish, meat, chicken, steak, pasta, noodles, rice, or potatoes unless listed above. "
            "Do not combine dessert spreads like Nutella with steak, potatoes, vegetables, or cheese. "
            "Do not use any unlisted food. "
            "Ingredients max 5 strings. Instructions exactly 3 short strings. "
            f"{target_hint} Protein and fat may differ by max 10g. "
            "Keys: title, why_this_works, ingredients, instructions, estimated_macros, used_fridge_item_ids, pantry_assumptions."
        )

    if compact:
        fridge_parts = []
        for item in payload["fridge_items"]:
            amount = _format_amount(item.get("amount"))
            unit = item.get("unit") or ""
            amount_hint = f" ({amount}{unit})" if amount else ""
            fridge_parts.append(f'{item["id"]} {item["name"]}{amount_hint}')
        fridge_list = ", ".join(fridge_parts)
        target_parts = []
        for key, suffix in (("protein", "g protein"), ("fat", "g fat"), ("kcal", "kcal")):
            value = payload["daily_goal_remaining"].get(key)
            if value not in (None, ""):
                target_parts.append(f"{value}{suffix}")
        target_hint = f" Targets: {', '.join(target_parts)}." if target_parts else ""
        category = recipe_category or "meal"
        return (
            "Return ONLY JSON. "
            f"Make one {category} recipe from these fridge IDs: {fridge_list}. "
            "Use 1-3 fridge IDs; for a main dish prefer protein + potato/rice/noodle + vegetable. "
            "Pantry allowed: oil, salt, pepper, water. No unlisted foods. "
            "Do not combine Nutella or dessert spread with meat, potatoes, vegetables, or cheese. "
            f"{target_hint} Keep protein/fat near target. "
            "Use keys: title, why_this_works, ingredients, instructions, estimated_macros, used_fridge_item_ids, pantry_assumptions. "
            "Exactly 3 short instructions."
        )

    return (
        "Erzeuge genau ein einfaches, kochbares FitFridge-Rezept als JSON. "
        f"{retry_hint}"
        "Du darfst als Kühlschrank-Lebensmittel nur die IDs aus fridge_items verwenden. "
        "Erfinde weiterhin selbst ein Rezept, aber keine neuen Kühlschrank-Zutaten. "
        "Wähle so viele Kühlschrank-Zutaten wie sinnvoll sind, um Rezeptart und Makroziele zu erfüllen; "
        "nutze aber keine Zutat nur, weil sie verfügbar ist. "
        "Priorität: erst kulinarisch realistisches Gericht, dann Makroziele, dann Resteverwertung. "
        "ingredients darf nur Namen aus fridge_items plus erlaubte pantry_assumptions enthalten. "
        "used_fridge_item_ids darf nur Zahlen aus fridge_items enthalten. "
        "Erlaubte pantry_assumptions: Wasser, Milch, Öl, Salz, Pfeffer, Backpulver, Gewürze. "
        "Der title muss ein echter Gerichtname sein, keine Zutatenverkettung. "
        "Wähle Zubereitungsart und Technik passend zu den tatsächlich ausgewählten Zutaten. "
        f"{category_hint}"
        "Berücksichtige daily_goal_remaining: Protein und Fett dürfen höchstens 10g vom Ziel abweichen. "
        "Schreibe 3-5 konkrete instructions. Gib plausible estimated_macros an, nicht überall 0. "
        "Antworte nur mit diesem JSON-Objekt:\n"
        "{\n"
        '  "title": "string",\n'
        '  "why_this_works": "string",\n'
        '  "ingredients": ["string"],\n'
        '  "instructions": ["string"],\n'
        '  "estimated_macros": {"kcal": number, "protein": number, "fat": number, "carbs": number},\n'
        '  "used_fridge_item_ids": [number],\n'
        '  "pantry_assumptions": ["string"]\n'
        "}\n\n"
        f"Daten:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
    )


def _extract_json_object(response: str) -> dict:
    if not isinstance(response, str):
        return {}
    text = response.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _selected_fridge_item_names(recipe, fridge_items):
    by_id = {item["id"]: item["name"] for item in _numbered_fridge_items(fridge_items)}
    selected = []
    for item_id in recipe.get("used_fridge_item_ids") or []:
        try:
            name = by_id.get(int(item_id))
        except (TypeError, ValueError):
            name = None
        if name:
            selected.append(name)
    return selected


def _string_value(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "title", "text", "step"):
            text = _string_value(value.get(key))
            if text:
                return text
    return str(value).strip() if value not in (None, "") else ""


def _string_list(value):
    if isinstance(value, list):
        return [text for text in (_string_value(item) for item in value) if text]
    if isinstance(value, str):
        parts = [part.strip(" .;:-") for part in re.split(r"\n+|(?:\d+\.\s*)|[.;]", value) if part.strip(" .;:-")]
        return parts or [value.strip()]
    return []


def _format_amount(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}".rstrip("0").rstrip(".")


def _default_unit_for_item(name, amount=None):
    normalized = _normalize(name)
    try:
        number = float(amount)
    except (TypeError, ValueError):
        number = 0
    if "egg" in normalized or normalized in ("ei", "eier"):
        return "pcs" if 0 < number <= 12 else "g"
    return "g" if number > 20 else ""


def _format_ingredient_quantity(item):
    amount_value = item.get("display_amount", item.get("amount"))
    amount = _format_amount(amount_value)
    if not amount:
        return item["name"]
    unit = (
        item.get("display_unit")
        or item.get("unit")
        or _default_unit_for_item(item["name"], amount_value)
    ).strip()
    if unit:
        return f"{amount}{unit} {item['name']}"
    return f"{amount} {item['name']}"


def _pantry_ingredient_with_quantity(ingredient):
    normalized = _normalize(ingredient)
    if "oil" in normalized or "oel" in normalized or "öl" in normalized:
        return "1 tsp Öl"
    if "salt" in normalized or "salz" in normalized:
        return "Salz nach Geschmack"
    if "pepper" in normalized or "pfeffer" in normalized:
        return "Pfeffer nach Geschmack"
    if "wasser" in normalized or "water" in normalized:
        return "etwas Wasser"
    return ingredient


def _item_unit(item):
    return (item.get("unit") or _default_unit_for_item(item.get("name", ""), item.get("amount"))).strip().lower()


def _is_piece_unit(unit):
    normalized = _normalize(unit)
    return normalized in ("pcs", "pc", "stk", "stueck", "stuck", "stück")


def _piece_weight_grams(item):
    normalized = _normalize(item.get("name", ""))
    if "egg" in normalized or normalized in ("ei", "eier"):
        return 50.0
    return 100.0


def _macro_grams_from_display_amount(item, amount, unit):
    unit = (unit or "").strip().lower()
    if _is_piece_unit(unit):
        return amount * _piece_weight_grams(item)
    if unit == "kg":
        return amount * 1000
    if unit == "mg":
        return amount / 1000
    if unit == "l":
        return amount * 1000
    return amount


def _display_amount_from_macro_grams(item, grams, unit):
    unit = (unit or "").strip().lower()
    if _is_piece_unit(unit):
        return grams / _piece_weight_grams(item)
    if unit == "kg":
        return grams / 1000
    if unit == "mg":
        return grams * 1000
    if unit == "l":
        return grams / 1000
    return grams


def _nutrition_value(item, macro):
    return _safe_float(item.get(f"{macro}_per_100g"))


def _has_nutrition_data(item):
    return any(_nutrition_value(item, macro) > 0 for macro in ("kcal", "protein", "fat", "carbs"))


def _item_role(item):
    normalized = _normalize(item.get("name", ""))
    if _is_sweet_spread(normalized):
        return "sweet_spread"
    if any(term in normalized for term in ("kartoffel", "potato", "reis", "rice", "pasta", "nudel", "noodle")):
        return "starch"
    if any(term in normalized for term in ("brokkoli", "broccoli", "paprika", "tomate", "tomato", "gemuese", "gemüse", "vegetable")):
        return "vegetable"
    if any(term in normalized for term in ("parmesan", "kaese", "käse", "cheese")):
        return "cheese"
    if any(term in normalized for term in ("yogurt", "joghurt", "quark", "skyr")):
        return "dairy_protein"
    if any(term in normalized for term in ("egg", "ei", "eier")):
        return "egg"
    if any(term in normalized for term in ("steak", "huhn", "chicken", "rind", "beef", "tofu", "fisch", "fish", "lachs", "salmon", "whey")):
        return "protein"
    return "default"


def _is_primary_protein_source(item):
    return _item_role(item) in ("protein", "dairy_protein", "egg")


def _serving_limits_for_item(item, recipe_category=None):
    role = _item_role(item)
    unit = _item_unit(item)
    if _is_piece_unit(unit):
        if role == "egg":
            return 1.0, 3.0, 4.0
        return 1.0, 1.0, 2.0

    normalized = _normalize(item.get("name", ""))
    if role == "protein":
        if "tofu" in normalized:
            return 150.0, 200.0, 300.0
        if any(term in normalized for term in ("steak", "rind", "beef", "huhn", "chicken", "fisch", "fish", "lachs", "salmon")):
            return 120.0, 180.0, 250.0
        return 80.0, 120.0, 180.0
    if role == "dairy_protein":
        return 150.0, 250.0, 300.0
    if role == "egg":
        return 100.0, 150.0, 200.0
    if role == "starch":
        if any(term in normalized for term in ("kartoffel", "potato")):
            return 150.0, 300.0, 300.0
        return 60.0, 90.0, 120.0
    if role == "vegetable":
        return 100.0, 200.0, 250.0
    if role == "cheese":
        return 15.0, 30.0, 40.0
    if role == "sweet_spread":
        return 10.0, 20.0, 30.0
    return 50.0, 100.0, 200.0


def _round_serving_amount(amount, unit):
    if _is_piece_unit(unit):
        return max(1.0, round(amount))
    if amount >= 20:
        return max(5.0, round(amount / 5) * 5)
    return round(amount, 1)


def _default_quantity_entry(item, recipe_category=None):
    unit = _item_unit(item)
    available = _safe_float(item.get("amount"))
    if available <= 0:
        return None

    minimum, default, maximum = _serving_limits_for_item(item, recipe_category=recipe_category)
    maximum = min(maximum, available) if available > 0 else maximum
    if maximum <= 0:
        return None
    minimum = min(minimum, maximum)
    amount = min(default, maximum)
    amount = max(minimum, amount)
    amount = _round_serving_amount(amount, unit)
    amount = min(amount, maximum)

    macro_grams = _macro_grams_from_display_amount(item, amount, unit)
    entry = dict(item)
    entry.update({
        "display_amount": amount,
        "display_unit": unit,
        "macro_grams": macro_grams,
        "min_amount": minimum,
        "max_amount": maximum,
    })
    entry["ingredient"] = _format_ingredient_quantity(entry)
    return entry


def _set_entry_display_amount(entry, amount):
    unit = entry.get("display_unit") or _item_unit(entry)
    amount = max(entry["min_amount"], min(entry["max_amount"], amount))
    amount = _round_serving_amount(amount, unit)
    amount = max(entry["min_amount"], min(entry["max_amount"], amount))
    entry["display_amount"] = amount
    entry["display_unit"] = unit
    entry["macro_grams"] = _macro_grams_from_display_amount(entry, amount, unit)
    entry["ingredient"] = _format_ingredient_quantity(entry)


def _compute_macros_from_quantity_plan(quantity_plan, excluded_id=None):
    if not quantity_plan:
        return None
    entries = [
        entry
        for item_id, entry in quantity_plan.items()
        if item_id != excluded_id
    ]
    if not entries or any(not _has_nutrition_data(entry) for entry in entries):
        return None

    totals = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for entry in entries:
        multiplier = _safe_float(entry.get("macro_grams")) / 100
        totals["kcal"] += _nutrition_value(entry, "kcal") * multiplier
        totals["protein"] += _nutrition_value(entry, "protein") * multiplier
        totals["fat"] += _nutrition_value(entry, "fat") * multiplier
        totals["carbs"] += _nutrition_value(entry, "carbs") * multiplier

    return {key: round(value, 1) for key, value in totals.items()}


def _build_quantity_plan(used_ids, fridge_items, daily_goal=None, recipe_category=None):
    numbered_items = _numbered_fridge_items(fridge_items)
    by_id = {item["id"]: item for item in numbered_items}
    quantity_plan = {}
    for item_id in used_ids:
        item = by_id.get(item_id)
        if not item:
            continue
        entry = _default_quantity_entry(item, recipe_category=recipe_category)
        if entry:
            quantity_plan[item_id] = entry

    target_protein = _goal_float(daily_goal, "protein")
    protein_entries = [
        (item_id, entry)
        for item_id, entry in quantity_plan.items()
        if _is_primary_protein_source(entry) and _nutrition_value(entry, "protein") > 0
    ]
    if target_protein is not None and protein_entries:
        primary_id, primary_entry = max(
            protein_entries,
            key=lambda pair: _nutrition_value(pair[1], "protein"),
        )
        other_macros = _compute_macros_from_quantity_plan(quantity_plan, excluded_id=primary_id)
        other_protein = other_macros["protein"] if other_macros else 0
        protein_per_100g = _nutrition_value(primary_entry, "protein")
        if protein_per_100g > 0:
            desired_grams = max(0.0, (target_protein - other_protein) / protein_per_100g * 100)
            desired_amount = _display_amount_from_macro_grams(
                primary_entry,
                desired_grams,
                primary_entry.get("display_unit"),
            )
            _set_entry_display_amount(primary_entry, desired_amount)

    target_kcal = _goal_float(daily_goal, "kcal")
    starch_entries = [
        (item_id, entry)
        for item_id, entry in quantity_plan.items()
        if _item_role(entry) == "starch" and _nutrition_value(entry, "kcal") > 0
    ]
    if target_kcal is not None and starch_entries:
        for item_id, entry in starch_entries:
            other_macros = _compute_macros_from_quantity_plan(quantity_plan, excluded_id=item_id)
            other_kcal = other_macros["kcal"] if other_macros else 0
            kcal_per_100g = _nutrition_value(entry, "kcal")
            if kcal_per_100g <= 0:
                continue
            desired_grams = max(0.0, (target_kcal - other_kcal) / kcal_per_100g * 100)
            desired_amount = _display_amount_from_macro_grams(entry, desired_grams, entry.get("display_unit"))
            _set_entry_display_amount(entry, desired_amount)

    return quantity_plan


def _ingredient_list_with_quantities(used_ids, ingredients, fridge_items, quantity_plan=None):
    numbered_items = _numbered_fridge_items(fridge_items)
    by_id = quantity_plan or {item["id"]: item for item in numbered_items}
    result = []

    for item_id in used_ids:
        item = by_id.get(item_id)
        if item:
            result.append(item.get("ingredient") or _format_ingredient_quantity(item))

    for ingredient in ingredients:
        normalized = _normalize(ingredient)
        if any(_normalize(item["name"]) and _normalize(item["name"]) in normalized for item in numbered_items):
            continue
        if any(term in normalized for term in ALLOWED_PANTRY_TERMS):
            result.append(_pantry_ingredient_with_quantity(ingredient))

    if not result:
        result = [_pantry_ingredient_with_quantity(ingredient) for ingredient in ingredients]

    deduped = []
    seen = set()
    for ingredient in result:
        key = _normalize(ingredient)
        if key and key not in seen:
            seen.add(key)
            deduped.append(ingredient)
    return deduped


def _macro_value(macros, *keys):
    if not isinstance(macros, dict):
        return 0.0
    for key in keys:
        if key in macros:
            return _safe_float(macros.get(key))
    return 0.0


def _normalize_macros(macros, selected_names=None, daily_goal=None):
    rough = _rough_macro_estimate(selected_names or [])
    normalized = {
        "kcal": _macro_value(macros, "kcal", "calories", "energy") or rough["kcal"],
        "protein": _macro_value(macros, "protein", "protein_g", "proteins") or rough["protein"],
        "fat": _macro_value(macros, "fat", "fat_g", "fats") or rough["fat"],
        "carbs": _macro_value(macros, "carbs", "carbs_g", "carbohydrates") or rough["carbs"],
    }
    return _align_macro_estimate_to_goal(normalized, daily_goal)


def _coerce_used_ids(raw_ids):
    if not isinstance(raw_ids, list):
        raw_ids = [raw_ids]
    used_ids = []
    for raw_id in raw_ids:
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if item_id not in used_ids:
            used_ids.append(item_id)
    return used_ids


def _apply_quantity_plan_to_recipe(
    recipe,
    fridge_items,
    daily_goal=None,
    recipe_category=None,
    align_when_no_nutrition=False,
):
    used_ids = _coerce_used_ids(recipe.get("used_fridge_item_ids") or [])
    if not used_ids:
        return recipe

    quantity_plan = _build_quantity_plan(
        used_ids,
        fridge_items,
        daily_goal=daily_goal,
        recipe_category=recipe_category,
    )
    if not quantity_plan:
        return recipe

    recipe["ingredients"] = _ingredient_list_with_quantities(
        used_ids,
        _string_list(recipe.get("ingredients")),
        fridge_items,
        quantity_plan=quantity_plan,
    )
    computed_macros = _compute_macros_from_quantity_plan(quantity_plan)
    if computed_macros:
        recipe["estimated_macros"] = computed_macros
        recipe["macro_source"] = "computed_from_ingredient_quantities"
    elif align_when_no_nutrition:
        selected_names = _selected_fridge_item_names({"used_fridge_item_ids": used_ids}, fridge_items)
        recipe["estimated_macros"] = _normalize_macros(
            recipe.get("estimated_macros") or recipe.get("macros"),
            selected_names or recipe["ingredients"],
            daily_goal,
        )
    return recipe


def _ingredient_is_allowed(ingredient, fridge_items):
    normalized = _normalize(str(ingredient))
    fridge_names = [_normalize(item["name"]) for item in _numbered_fridge_items(fridge_items)]
    if any(fridge_name and fridge_name in normalized for fridge_name in fridge_names):
        return True
    return any(term in normalized for term in ALLOWED_PANTRY_TERMS)


def _is_sweet_spread(value):
    return any(term in _normalize(str(value)) for term in SWEET_SPREAD_TERMS)


def _has_main_dish_anchor(value):
    return any(term in _normalize(str(value)) for term in MAIN_DISH_ANCHOR_TERMS)


def _has_sweet_spread_conflict(value):
    text = str(value)
    return _is_sweet_spread(text) and _has_main_dish_anchor(text)


def _mentions_unlisted_core_food(value, fridge_items):
    normalized = _normalize(str(value))
    if not normalized:
        return False
    fridge_text = " ".join(_normalize(item["name"]) for item in _numbered_fridge_items(fridge_items))
    for group in CORE_FOOD_TERM_GROUPS:
        if any(term in normalized for term in group) and not any(term in fridge_text for term in group):
            return True
    return False


def _fallback_title_from_items(selected_names, recipe_category=None):
    names = [name for name in selected_names if name][:3]
    if not names:
        return "FitFridge-Rezept"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} mit {names[1]}"
    return f"{names[0]} mit {names[1]} und {names[2]}"


def _mentions_any_item(value, item_names):
    normalized = _normalize(str(value))
    return any(_normalize(name) and _normalize(name) in normalized for name in item_names)


def _preferred_main_course_core_ids(fridge_items, recipe_category=None):
    category = _normalize(recipe_category or "")
    if category not in ("hauptspeise", "abendessen"):
        return []

    numbered_items = _numbered_fridge_items(fridge_items)
    core_ids = []
    for target_rank in (0, 1, 2):
        match = next(
            (
                item
                for item in numbered_items
                if _rank_recipe_item(item, recipe_category) == target_rank
            ),
            None,
        )
        if match:
            core_ids.append(match["id"])
    return core_ids if len(core_ids) == 3 else []


def _has_item(selected_names, *terms):
    joined = " ".join(_normalize(name) for name in selected_names)
    return any(term in joined for term in terms)


def _detailed_instructions_for_items(selected_names, fridge_items, recipe_category=None):
    selected_text = ", ".join(selected_names)
    has_steak = _has_item(selected_names, "steak", "rind", "beef")
    has_potato = _has_item(selected_names, "kartoffel", "potato")
    has_broccoli = _has_item(selected_names, "brokkoli", "broccoli")
    has_yogurt = _has_item(selected_names, "yogurt", "joghurt")
    has_egg = _has_item(selected_names, "egg", "ei", "eier")

    if len(selected_names) == 1 and has_yogurt:
        return [
            f"{selected_names[0]} in eine Schüssel geben und kurz glatt rühren.",
            "Bei Bedarf mit einem kleinen Schuss Wasser cremiger rühren.",
            "Direkt kalt servieren oder bis zum Essen im Kühlschrank stehen lassen.",
        ]

    if has_steak and has_potato and has_broccoli:
        return [
            "Kartoffeln waschen, in mundgerechte Stücke schneiden und in Salzwasser 15-20 Minuten garen.",
            "Brokkoli in Röschen teilen und 5-7 Minuten dämpfen oder in wenig Wasser bissfest garen.",
            "Steak trocken tupfen, salzen und in einer sehr heißen Pfanne mit 1 tsp Öl 2-4 Minuten pro Seite braten; kurz ruhen lassen und mit Kartoffeln und Brokkoli anrichten.",
        ]

    if has_egg and len(selected_names) <= 3:
        return [
            f"{selected_text} vorbereiten; Eier in einer Schüssel verquirlen und leicht salzen.",
            "Eine Pfanne mit 1 tsp Öl erhitzen und die festen Zutaten kurz anbraten.",
            "Eier zugeben, bei mittlerer Hitze stocken lassen und direkt servieren.",
        ]

    return [
        f"{selected_text or 'Die Zutaten'} waschen, putzen und in passende Stücke schneiden.",
        "Eine Pfanne mit 1 tsp Öl erhitzen und die Zutaten nach Garzeit nacheinander garen.",
        "Mit Salz und Pfeffer abschmecken, kurz ziehen lassen und warm servieren.",
    ]


def _trim_main_course_subset(used_ids, ingredients, title, fridge_items, recipe_category=None):
    category = _normalize(recipe_category or "")
    if category not in ("hauptspeise", "abendessen"):
        return used_ids, ingredients, title, False

    selected_names = _selected_fridge_item_names({"used_fridge_item_ids": used_ids}, fridge_items)
    selected_items = [
        item for item in _numbered_fridge_items(fridge_items)
        if item["name"] in selected_names
    ]
    ranks = {_rank_recipe_item(item, recipe_category) for item in selected_items}
    core_ids = _preferred_main_course_core_ids(fridge_items, recipe_category=recipe_category)
    if core_ids and set(used_ids) != set(core_ids):
        core_names = _selected_fridge_item_names({"used_fridge_item_ids": core_ids}, fridge_items)
        if 0 in ranks or any(rank >= 3 for rank in ranks) or len(used_ids) > 3:
            return core_ids, core_names, _fallback_title_from_items(core_names, recipe_category=recipe_category), True

    if not {0, 1, 2}.issubset(ranks):
        return used_ids, ingredients, title, False

    keep_ids = [
        item["id"] for item in selected_items
        if _rank_recipe_item(item, recipe_category) <= 2
    ]
    keep_names = _selected_fridge_item_names({"used_fridge_item_ids": keep_ids}, fridge_items)
    dropped_names = [name for name in selected_names if name not in keep_names]
    trimmed_ingredients = [
        ingredient for ingredient in ingredients
        if not _mentions_any_item(ingredient, dropped_names)
    ]
    trimmed_title = title
    title_changed = False
    if _mentions_any_item(title, dropped_names):
        trimmed_title = _fallback_title_from_items(keep_names, recipe_category=recipe_category)
        title_changed = True
    return keep_ids, trimmed_ingredients, trimmed_title, title_changed


def _infer_used_ids(recipe, fridge_items):
    numbered_items = _numbered_fridge_items(fridge_items)
    by_id = {item["id"]: item for item in numbered_items}

    name_candidates = []
    name_candidates.extend(_string_list(recipe.get("used_fridge_items")))
    name_candidates.extend(_string_list(recipe.get("ingredients")))
    normalized_candidates = " ".join(_normalize(name) for name in name_candidates)
    inferred = []
    for item in numbered_items:
        normalized_name = _normalize(item["name"])
        if normalized_name and normalized_name in normalized_candidates and item["id"] not in inferred:
            inferred.append(item["id"])

    if inferred:
        return inferred

    raw_ids = recipe.get("used_fridge_item_ids") or recipe.get("fridge_item_ids") or []
    if not isinstance(raw_ids, list):
        raw_ids = [raw_ids]
    for item_id in raw_ids:
        try:
            normalized_id = int(item_id)
        except (TypeError, ValueError):
            continue
        if normalized_id in by_id and normalized_id not in inferred:
            inferred.append(normalized_id)

    return inferred


def _repair_recipe_response(parsed, fridge_items, daily_goal=None, recipe_category=None):
    if isinstance(parsed.get("recipe"), dict):
        parsed = parsed["recipe"]

    recipe = dict(parsed)
    title = _string_value(recipe.get("title") or recipe.get("name") or recipe.get("recipe_title"))
    used_ids = _infer_used_ids(recipe, fridge_items)
    selected_names = _selected_fridge_item_names({"used_fridge_item_ids": used_ids}, fridge_items)

    ingredients = _string_list(recipe.get("ingredients"))
    ingredients = [ingredient for ingredient in ingredients if _ingredient_is_allowed(ingredient, fridge_items)]
    if not ingredients:
        ingredients = selected_names[:]

    why = _string_value(recipe.get("why_this_works") or recipe.get("why"))
    instructions = _string_list(recipe.get("instructions") or recipe.get("steps"))
    combined_text = " ".join([title, why, " ".join(selected_names), " ".join(ingredients), " ".join(instructions)])
    if _has_sweet_spread_conflict(combined_text):
        kept_ids = []
        for item_id in used_ids:
            names = _selected_fridge_item_names({"used_fridge_item_ids": [item_id]}, fridge_items)
            if names and not _is_sweet_spread(names[0]):
                kept_ids.append(item_id)
        used_ids = kept_ids
        selected_names = _selected_fridge_item_names({"used_fridge_item_ids": used_ids}, fridge_items)
        ingredients = [ingredient for ingredient in ingredients if not _is_sweet_spread(ingredient)]
        title = _fallback_title_from_items(selected_names or ingredients, recipe_category=recipe_category)
        instructions = []

    used_ids, ingredients, title, title_trimmed = _trim_main_course_subset(
        used_ids,
        ingredients,
        title,
        fridge_items,
        recipe_category=recipe_category,
    )
    if title_trimmed:
        selected_names = _selected_fridge_item_names({"used_fridge_item_ids": used_ids}, fridge_items)
        instructions = []

    if _mentions_unlisted_core_food(title, fridge_items) or _has_sweet_spread_conflict(title):
        title = _fallback_title_from_items(selected_names or ingredients, recipe_category=recipe_category)

    if title_trimmed or not why or _mentions_unlisted_core_food(why, fridge_items) or _has_sweet_spread_conflict(why):
        why = "Das Rezept nutzt nur die erlaubten Kühlschrank-Zutaten und einfache Pantry-Basics."

    if len(instructions) < 3:
        instructions = _detailed_instructions_for_items(
            selected_names or ingredients[:3],
            fridge_items,
            recipe_category=recipe_category,
        )

    quantity_plan = _build_quantity_plan(
        used_ids,
        fridge_items,
        daily_goal=daily_goal,
        recipe_category=recipe_category,
    )
    ingredients = _ingredient_list_with_quantities(
        used_ids,
        ingredients,
        fridge_items,
        quantity_plan=quantity_plan,
    )
    computed_macros = _compute_macros_from_quantity_plan(quantity_plan)
    estimated_macros = computed_macros or _normalize_macros(
        recipe.get("estimated_macros") or recipe.get("macros"),
        selected_names or ingredients,
        daily_goal,
    )

    repaired = {
        "title": title or "FitFridge-Rezept",
        "why_this_works": why,
        "ingredients": ingredients,
        "instructions": instructions[:5],
        "estimated_macros": estimated_macros,
        "used_fridge_item_ids": used_ids,
        "pantry_assumptions": _string_list(recipe.get("pantry_assumptions")),
    }
    if computed_macros:
        repaired["macro_source"] = "computed_from_ingredient_quantities"

    return repaired


def _recipe_quality_is_low(recipe, fridge_items, daily_goal=None, recipe_category=None):
    title = str(recipe.get("title") or "").strip()
    if not title:
        return True

    names = _item_names(fridge_items)
    normalized_title = _normalize(title)
    joined_names = [name for name in names if _normalize(name) and _normalize(name) in normalized_title]
    if len(joined_names) >= 3 and ("+" in title or "," in title):
        return True

    instructions = recipe.get("instructions")
    if not isinstance(instructions, list) or len(instructions) < 3:
        return True

    if not _uses_only_allowed_foods(recipe, fridge_items):
        return True

    if not _recipe_category_is_coherent(recipe, fridge_items, recipe_category=recipe_category):
        return True

    macros = recipe.get("estimated_macros") or {}
    if all(_safe_float(macros.get(key)) == 0 for key in ("kcal", "protein", "fat", "carbs")):
        return True

    if not _macro_targets_are_close_enough(recipe, daily_goal):
        return True

    return False


def _recipe_category_is_coherent(recipe, fridge_items, recipe_category=None):
    text_parts = [
        recipe.get("title", ""),
        recipe.get("why_this_works", ""),
        " ".join(recipe.get("ingredients") or []),
        " ".join(recipe.get("instructions") or []),
        " ".join(_selected_fridge_item_names(recipe, fridge_items)),
    ]
    joined = " ".join(str(part) for part in text_parts)
    return not _mentions_unlisted_core_food(joined, fridge_items) and not _has_sweet_spread_conflict(joined)


def _uses_only_allowed_foods(recipe, fridge_items):
    numbered_items = _numbered_fridge_items(fridge_items)
    if not numbered_items:
        return False
    by_id = {item["id"]: item for item in numbered_items}
    fridge_names = [_normalize(item["name"]) for item in numbered_items]

    used_ids = recipe.get("used_fridge_item_ids") or []
    if not isinstance(used_ids, list) or not used_ids:
        return False
    for item_id in used_ids:
        try:
            normalized_id = int(item_id)
        except (TypeError, ValueError):
            return False
        if normalized_id not in by_id:
            return False

    ingredients = recipe.get("ingredients") or []
    if not isinstance(ingredients, list) or not ingredients:
        return False
    for ingredient in ingredients:
        normalized = _normalize(str(ingredient))
        if any(fridge_name and fridge_name in normalized for fridge_name in fridge_names):
            continue
        if any(term in normalized for term in ALLOWED_PANTRY_TERMS):
            continue
        return False

    return True


def _attach_used_fridge_item_names(recipe, fridge_items):
    by_id = {item["id"]: item["name"] for item in _numbered_fridge_items(fridge_items)}
    used_names = []
    for item_id in recipe.get("used_fridge_item_ids") or []:
        try:
            name = by_id.get(int(item_id))
        except (TypeError, ValueError):
            name = None
        if name and name not in used_names:
            used_names.append(name)
    recipe["used_fridge_items"] = used_names
    return recipe


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _goal_float(daily_goal, key):
    if not isinstance(daily_goal, dict):
        return None
    value = daily_goal.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _macro_targets_are_close_enough(recipe, daily_goal):
    macros = recipe.get("estimated_macros") or {}
    for key in ("protein", "fat"):
        target = _goal_float(daily_goal, key)
        if target is None:
            continue
        if abs(_safe_float(macros.get(key)) - target) > MACRO_TARGET_TOLERANCE_GRAMS:
            return False
    return True


def _align_macro_estimate_to_goal(macros, daily_goal):
    aligned = dict(macros)
    for key in ("protein", "fat"):
        target = _goal_float(daily_goal, key)
        if target is not None:
            aligned[key] = target
    return aligned


def _parse_recipe_response(response: str, fridge_items, daily_goal=None, recipe_category=None, repair=False):
    parsed = _extract_json_object(response)
    if not parsed:
        return None

    if isinstance(parsed.get("recipe"), dict):
        parsed = parsed["recipe"]

    recipe = {}
    recipe.update({key: value for key, value in parsed.items() if value})
    recipe.setdefault("estimated_macros", {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0})
    recipe.setdefault("used_fridge_item_ids", [])
    recipe.setdefault("pantry_assumptions", [])
    if repair:
        recipe = _repair_recipe_response(recipe, fridge_items, daily_goal=daily_goal, recipe_category=recipe_category)
    else:
        recipe = _apply_quantity_plan_to_recipe(
            recipe,
            fridge_items,
            daily_goal=daily_goal,
            recipe_category=recipe_category,
        )
    if _recipe_quality_is_low(recipe, fridge_items, daily_goal=daily_goal, recipe_category=recipe_category):
        return None
    return _attach_used_fridge_item_names(recipe, fridge_items)


def _warning_recipe(title, message):
    return {
        "title": title,
        "why_this_works": message,
        "ingredients": [],
        "instructions": [
            "Prüfe, ob Ollama läuft und das ausgewählte Modell installiert ist.",
            "Wähle in den Einstellungen bei Bedarf ein stärkeres LLM.",
            "Starte die Rezeptgenerierung danach erneut.",
        ],
        "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
        "used_fridge_items": [],
        "pantry_assumptions": [],
        "warning": True,
    }


def _rough_macro_estimate(selected_items):
    count = max(1, len(selected_items))
    return {
        "kcal": 180 * count,
        "protein": 10 * count,
        "fat": 6 * count,
        "carbs": 22 * count,
    }


def _fallback_recipe(fridge_items, daily_goal=None, recipe_category=None, reason=""):
    selected = [
        item
        for item in _limit_fridge_items(fridge_items, 3)
        if item.get("name")
    ]
    selected_names = [item.get("name", "").strip() for item in selected if item.get("name")]
    if not selected_names:
        return _warning_recipe("Keine Zutaten verfügbar", "Es waren keine nutzbaren Kühlschrank-Zutaten vorhanden.")

    title = "Modell fehlgeschlagen - lokaler Fallback"
    why = "Das ausgewählte lokale Modell hat kein brauchbares Rezept erzeugt; FitFridge nutzt deshalb eine einfache lokale Ersatzvariante."
    if reason:
        why = f"{why} Grund: {reason}"

    used_ids = list(range(1, len(selected) + 1))
    quantity_plan = _build_quantity_plan(
        used_ids,
        selected,
        daily_goal=daily_goal,
        recipe_category=recipe_category,
    )
    ingredients = _ingredient_list_with_quantities(
        used_ids,
        selected_names + ["Öl", "Salz", "Pfeffer"],
        selected,
        quantity_plan=quantity_plan,
    )
    computed_macros = _compute_macros_from_quantity_plan(quantity_plan)

    return {
        "title": title,
        "why_this_works": why,
        "ingredients": ingredients,
        "instructions": [
            f"{', '.join(selected_names)} vorbereiten und passend schneiden.",
            "Eine Pfanne mit wenig Öl erhitzen, die Zutaten nacheinander garen und würzen.",
            "Abschmecken und direkt servieren.",
        ],
        "estimated_macros": computed_macros or _align_macro_estimate_to_goal(_rough_macro_estimate(selected_names), daily_goal),
        "used_fridge_items": selected_names,
        "used_fridge_item_ids": used_ids,
        "pantry_assumptions": ["Öl", "Salz", "Pfeffer"],
        "fallback": True,
    }


def _generate_recipe_response(prompt, model, base_url, timeout, num_predict=900):
    return generate_from_ollama(
        prompt=prompt,
        model=model,
        base_url=base_url,
        timeout=timeout,
        num_predict=num_predict,
        format_json=True,
    )


def generate_freestyle_recipe(
    fridge_items,
    daily_goal=None,
    recipe_category=None,
    model=None,
    base_url=None,
    timeout=120,
):
    """Generate one realistic recipe from fridge contents only."""
    if not fridge_items:
        return {
            "recipe": {
                "title": "Keine Zutaten verfügbar",
                "why_this_works": "Dein Kühlschrank ist leer.",
                "ingredients": [],
                "instructions": ["Füge zuerst Lebensmittel zu deinem Kühlschrank hinzu."],
                "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
                "used_fridge_items": [],
                "pantry_assumptions": [],
            },
            "prompt_used": "",
            "raw_response": "",
        }

    profile = _model_profile(model)
    profile_fridge_items = fridge_items
    if profile["prompt_style"] in ("compact", "gemma"):
        profile_fridge_items = _rank_fridge_items_for_prompt(
            fridge_items,
            recipe_category=recipe_category,
        )
    prompt_fridge_items = _limit_fridge_items(profile_fridge_items, profile["max_items"])
    prompt = build_freestyle_recipe_prompt(
        prompt_fridge_items,
        daily_goal,
        recipe_category=recipe_category,
        compact=profile["compact_prompt"],
        prompt_style=profile["prompt_style"],
    )
    try:
        response = _generate_recipe_response(
            prompt,
            model,
            base_url,
            timeout,
            num_predict=profile["num_predict"],
        )
    except Exception as exc:
        return {
            "recipe": _warning_recipe(
                "LLM nicht erreichbar",
                f"Die lokale LLM-Anbindung konnte nicht genutzt werden: {exc}",
            ),
            "prompt_used": prompt,
            "raw_response": "",
            "error": str(exc),
        }

    recipe = _parse_recipe_response(
        response,
        prompt_fridge_items,
        daily_goal=daily_goal,
        recipe_category=recipe_category,
        repair=profile["repair_response"],
    )
    raw_responses = [response]
    if recipe is None and profile["allow_retry"]:
        retry_prompt = build_freestyle_recipe_prompt(
            prompt_fridge_items,
            daily_goal,
            recipe_category=recipe_category,
            retry_reason=(
                "Die Antwort enthielt erfundene Zutaten, falsche IDs, fehlende Schritte, keine brauchbaren Makros "
                "oder Protein/Fett lagen mehr als 10g neben dem Ziel. Wähle passende Zutaten für Rezeptart und Makroziele."
            ),
            compact=profile["compact_prompt"],
            prompt_style=profile["prompt_style"],
        )
        try:
            retry_response = _generate_recipe_response(
                retry_prompt,
                model,
                base_url,
                timeout,
                num_predict=profile["num_predict"],
            )
            raw_responses.append(retry_response)
            recipe = _parse_recipe_response(
                retry_response,
                prompt_fridge_items,
                daily_goal=daily_goal,
                recipe_category=recipe_category,
                repair=profile["repair_response"],
            )
        except Exception as exc:
            return {
                "recipe": _warning_recipe(
                    "LLM nicht erreichbar",
                    f"Die lokale LLM-Anbindung konnte beim zweiten Versuch nicht genutzt werden: {exc}",
                ),
                "prompt_used": retry_prompt,
                "raw_response": "\n\n--- retry ---\n\n".join(raw_responses),
                "error": str(exc),
            }

    if recipe is None and profile["fallback_on_invalid"]:
        return {
            "recipe": _fallback_recipe(
                prompt_fridge_items,
                daily_goal=daily_goal,
                recipe_category=recipe_category,
                reason="Die LLM-Antwort war leer oder nicht als Rezept verwendbar.",
            ),
            "prompt_used": prompt,
            "raw_response": "\n\n--- retry ---\n\n".join(raw_responses),
        }

    if recipe is None:
        return {
            "recipe": _warning_recipe(
                "LLM-Antwort nicht brauchbar",
                "Das lokale Modell hat auch nach einem zweiten Versuch kein sinnvoll kochbares Rezept erzeugt.",
            ),
            "prompt_used": prompt,
            "raw_response": "\n\n--- retry ---\n\n".join(raw_responses),
        }

    return {
        "recipe": recipe,
        "prompt_used": prompt,
        "raw_response": "\n\n--- retry ---\n\n".join(raw_responses),
    }
