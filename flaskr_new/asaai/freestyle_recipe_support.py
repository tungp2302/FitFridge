"""Support helpers for FitFridge freestyle recipe generation."""
from __future__ import annotations

import json
import re


NUTRITION_FIELDS = ("kcal_per_100g", "protein_per_100g", "fat_per_100g", "carbs_per_100g")
MACRO_FIELDS = (
    ("kcal", "kcal_per_100g"),
    ("protein", "protein_per_100g"),
    ("fat", "fat_per_100g"),
    ("carbs", "carbs_per_100g"),
)

SUPPLEMENT_TERMS = ("whey", "protein powder", "proteinpulver", "eiweisspulver", "isolate", "casein", "kasein")
SWEET_TERMS = (
    "banane", "banana", "apfel", "apple", "beere", "berry", "honig", "honey",
    "marmelade", "jam", "nutella", "schoko", "chocolate", "datteln", "dates", "ahorn", "maple",
)
VEGETABLE_TERMS = (
    "spinat", "spinach", "karotte", "carrot", "brokkoli", "broccoli", "paprika",
    "tomate", "tomato", "zucchini", "zwiebel", "onion", "champignon", "pilz", "mushroom",
    "lauch", "sellerie", "gurke", "salat", "kohl", "bohne", "erbse",
)
STARCH_TERMS = (
    "reis", "rice", "kartoffel", "potato", "nudel", "noodle", "pasta", "bulgur",
    "couscous", "hafer", "oat", "mehl", "flour", "brot", "bread", "bun", "buns",
    "broetchen", "brötchen", "semmel", "wrap", "tortilla",
)
BREAKFAST_STARCH_TERMS = ("hafer", "oat", "mehl", "flour", "brot", "bread")
PROTEIN_TERMS = (
    "ei", "egg", "eier", "tofu", "tempeh", "huhn", "chicken", "rind", "beef",
    "steak", "fisch", "fish", "lachs", "salmon", "linsen", "lentil", "bohnen",
    "beans", "hack", "hackfleisch", "kaese", "cheese", "frischkaese", "joghurt", "yogurt",
)
DAIRY_TERMS = ("milch", "milk", "joghurt", "yogurt", "quark", "skyr")
SAVORY_ANCHOR_TERMS = VEGETABLE_TERMS + STARCH_TERMS + PROTEIN_TERMS
SWEET_DISH_TERMS = ("porridge", "haferbrei", "muesli", "smoothie", "shake", "joghurtbowl", "yogurt bowl", "dessert", "nachspeise")
SAVORY_CATEGORIES = ("hauptspeise", "abendessen", "mittag", "lunch", "dinner", "main")
SUPPLEMENT_SAVORY_CONFLICT_TERMS = (
    VEGETABLE_TERMS
    + ("reis", "rice", "kartoffel", "potato", "nudel", "noodle", "pasta", "bulgur", "couscous", "brot", "bread")
    + (
        "huhn", "chicken", "haehnchen", "hähnchen", "rind", "beef", "steak", "fisch",
        "fish", "lachs", "salmon", "tofu", "tempeh",
    )
    + ("pfanne", "brat", "auflauf", "curry", "suppe", "salat", "gemuese", "gemüse")
)
SUPPLEMENT_SWEET_CONTEXT_TERMS = (
    "pfannkuchen", "pancake", "porridge", "haferbrei", "shake", "smoothie", "joghurt",
    "yogurt", "quark", "skyr", "bowl", "gebaeck", "gebäck", "muffin", "waffel", "waffle",
)
PANTRY_ALLOWED = ("wasser", "water", "oel", "öl", "oil", "salz", "salt", "pfeffer", "pepper", "gewuerz", "gewürz", "spice", "herb")
TITLE_FILLER_WORDS = {"mit", "und", "auf", "an", "in", "aus", "der", "die", "das"}
NAME_ALIASES = {
    "egg": ("ei", "eier"),
    "eggs": ("ei", "eier"),
    "ei": ("egg", "eggs", "eier"),
    "eier": ("egg", "eggs", "ei"),
    "cheese": ("kaese", "kase", "käse"),
    "kaese": ("cheese", "käse"),
    "frischkaese": ("frischkäse", "cream cheese"),
    "oats": ("hafer", "haferflocken"),
    "rice": ("reis",),
    "flour": ("mehl",),
}
GENERIC_NAME_TOKENS = {
    "fitfridge", "demo", "bio", "fresh", "frisch", "local", "farm", "natur", "neutral",
    "original", "classic", "klassisch", "protein", "powder", "pulver", "pure", "bulk",
}


def normalize(value):
    return (value or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def safe_float(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def has_term(name, terms):
    normalized = normalize(name)
    words = re.findall(r"[a-zA-ZäöüÄÖÜß]+", normalized)
    for term in terms:
        normalized_term = normalize(term)
        if len(normalized_term) <= 3 and normalized_term.isalpha():
            if normalized_term in words:
                return True
        elif normalized_term in normalized:
            return True
    return False


def is_supplement(name):
    return has_term(name, SUPPLEMENT_TERMS)


def is_savory_category(recipe_category):
    category = normalize(recipe_category or "")
    return any(term in category for term in SAVORY_CATEGORIES)


def limit_items(fridge_items, max_items):
    named = [item for item in fridge_items if (item.get("name") or "").strip()]
    return named[:max_items] if max_items else named


def numbered_items(fridge_items):
    numbered = []
    for index, item in enumerate(fridge_items, start=1):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        entry = {"id": index, "name": name}
        for field in NUTRITION_FIELDS:
            if item.get(field) not in (None, ""):
                entry[field] = item.get(field)
        numbered.append(entry)
    return numbered


def item_label(item):
    macro_bits = [
        f"{round(float(item[field]))}{short}"
        for field, short in (("kcal_per_100g", "kcal"), ("protein_per_100g", "P"), ("fat_per_100g", "F"), ("carbs_per_100g", "C"))
        if item.get(field) not in (None, "")
    ]
    label = f'{item["id"]} {item["name"]}'
    if macro_bits:
        label += f' ({" ".join(macro_bits)} /100g)'
        values = [safe_float(item.get(field)) or 0.0 for field in NUTRITION_FIELDS]
        if not any(value > 0 for value in values):
            label += " [Naehrwerte fehlen]"
    if is_supplement(item["name"]):
        label += " [Supplement]"
    return label


def string_list(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [p.strip(" .;:-") for p in re.split(r"\n+|\d+\.\s*|[.;]", value) if p.strip(" .;:-")]
        return parts or [value.strip()]
    return []


def _tokens(value):
    return [
        token
        for token in re.findall(r"[a-zA-ZäöüÄÖÜß]+", normalize(value))
        if len(token) >= 3 and token not in GENERIC_NAME_TOKENS
    ]


def _raw_structured_fridge(recipe):
    for key in ("fridge_ingredients", "used_fridge_ingredients", "recipe_items"):
        value = recipe.get(key)
        if isinstance(value, list):
            return value
    return []


def _by_id(fridge_items):
    return {item["id"]: item for item in numbered_items(fridge_items)}


def _format_number(value):
    number = safe_float(value)
    if number is None:
        return ""
    return str(int(number)) if number.is_integer() else f"{number:.1f}".rstrip("0").rstrip(".")


def _format_grams(amount_g, name):
    amount = _format_number(amount_g)
    return f"{amount}g {name}" if amount else name


def structured_fridge_ingredients(recipe, fridge_items):
    items_by_id = _by_id(fridge_items)
    structured = []
    for raw in _raw_structured_fridge(recipe):
        if not isinstance(raw, dict):
            continue
        amount = safe_float(raw.get("amount_g", raw.get("grams", raw.get("g"))))
        try:
            item_id = int(raw.get("id", raw.get("fridge_item_id")))
        except (TypeError, ValueError):
            continue
        item = items_by_id.get(item_id)
        if item is None or amount is None:
            continue
        label = str(raw.get("label") or raw.get("ingredient") or raw.get("name") or "").strip()
        if not label:
            label = _format_grams(amount, item["name"])
        elif not re.search(r"\d", label):
            label = _format_grams(amount, label)
        structured.append({"id": item_id, "name": item["name"], "amount_g": amount, "label": label})
    return structured


def _structured_pantry(recipe):
    value = recipe.get("pantry_ingredients")
    if not isinstance(value, list):
        return []
    out = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or raw.get("label") or "").strip()
        if not name:
            continue
        amount = safe_float(raw.get("amount_g", raw.get("grams", raw.get("g"))))
        label = str(raw.get("label") or "").strip() or (f"{_format_number(amount)}g {name}" if amount else name)
        if normalize(name) not in normalize(label):
            label = f"{name} {label}" if normalize(label).startswith(("zum ", "nach ")) else f"{label} {name}"
        out.append({"name": name, "amount_g": amount, "label": label})
    return out


def computed_macros(recipe, fridge_items):
    structured = structured_fridge_ingredients(recipe, fridge_items)
    if not structured:
        return None
    items_by_id = _by_id(fridge_items)
    totals = {key: 0.0 for key, _ in MACRO_FIELDS}
    has_nutrition = False
    for used in structured:
        item = items_by_id[used["id"]]
        factor = used["amount_g"] / 100.0
        for key, field in MACRO_FIELDS:
            value = safe_float(item.get(field)) or 0.0
            has_nutrition = has_nutrition or value > 0
            totals[key] += value * factor
    for pantry in _structured_pantry(recipe):
        amount = pantry.get("amount_g")
        if amount is not None and any(term in normalize(pantry["name"]) for term in ("oil", "oel", "öl")):
            totals["kcal"] += amount * 9
            totals["fat"] += amount
    return {key: round(float(value), 1) for key, value in totals.items()} if has_nutrition else None


def _ingredient_text(recipe):
    parts = string_list(recipe.get("ingredients")) + string_list(recipe.get("used_fridge_items"))
    for raw in _raw_structured_fridge(recipe):
        if isinstance(raw, dict):
            parts.append(str(raw.get("label") or raw.get("name") or raw.get("ingredient") or ""))
    return " ".join(normalize(part) for part in parts if part)


def _text_mentions_item(text, name):
    normalized_text = normalize(text)
    normalized_name = normalize(name)
    if normalized_name and normalized_name in normalized_text:
        return True
    for token in _tokens(name):
        aliases = NAME_ALIASES.get(token, ())
        if token in normalized_text or any(normalize(alias) in normalized_text for alias in aliases):
            return True
        if token.endswith("mehl") and "mehl" in normalized_text:
            return True
        if token.endswith("kaese") and ("kaese" in normalized_text or "käse" in normalized_text):
            return True
    return False


def _used_ids(recipe):
    ids = []
    for raw_id in recipe.get("used_fridge_item_ids") or []:
        try:
            ids.append(int(raw_id))
        except (TypeError, ValueError):
            ids.append(None)
    for raw in _raw_structured_fridge(recipe):
        if isinstance(raw, dict):
            try:
                ids.append(int(raw.get("id", raw.get("fridge_item_id"))))
            except (TypeError, ValueError):
                ids.append(None)
    return ids


def used_fridge_names(recipe, fridge_items):
    structured_names = [item["name"] for item in structured_fridge_ingredients(recipe, fridge_items)]
    if structured_names:
        return list(dict.fromkeys(structured_names))
    by_id = {item["id"]: item["name"] for item in numbered_items(fridge_items)}
    names = []
    for raw_id in recipe.get("used_fridge_item_ids") or []:
        try:
            name = by_id.get(int(raw_id))
        except (TypeError, ValueError):
            name = None
        if name and name not in names:
            names.append(name)
    if not names:
        text = _ingredient_text(recipe)
        names = [item["name"] for item in numbered_items(fridge_items) if normalize(item["name"]) in text]
    return names


def _ids_are_valid(recipe, fridge_items):
    valid_ids = set(_by_id(fridge_items))
    ids = _used_ids(recipe)
    return bool(ids) and all(item_id in valid_ids for item_id in ids)


def _legacy_ids_match_ingredients(recipe, fridge_items):
    if structured_fridge_ingredients(recipe, fridge_items):
        return True
    ids = recipe.get("used_fridge_item_ids") or []
    if not ids:
        return True
    text = _ingredient_text(recipe)
    return all(_text_mentions_item(text, name) for name in used_fridge_names(recipe, fridge_items))


def _structured_amounts_are_realistic(recipe, fridge_items):
    for item in structured_fridge_ingredients(recipe, fridge_items):
        amount = item["amount_g"]
        if amount <= 0 or amount > 1200:
            return False
        if is_supplement(item["name"]) and amount > 80:
            return False
    return True


def _sweet_savory_conflict(used_names):
    if not any(has_term(n, VEGETABLE_TERMS) for n in used_names):
        return False
    return any(is_supplement(n) or has_term(n, SWEET_TERMS) for n in used_names)


def _supplement_savory_conflict(recipe, used_names):
    if not any(is_supplement(name) for name in used_names):
        return False
    text = " ".join([
        normalize(recipe.get("title") or ""),
        _ingredient_text(recipe),
        " ".join(normalize(name) for name in used_names),
    ])
    has_savory_conflict = any(has_term(text, (term,)) for term in SUPPLEMENT_SAVORY_CONFLICT_TERMS)
    has_sweet_context = any(has_term(text, (term,)) for term in SUPPLEMENT_SWEET_CONTEXT_TERMS)
    return has_savory_conflict or not has_sweet_context


def _category_conflict(recipe, recipe_category, used_names):
    if not is_savory_category(recipe_category):
        return False
    text = _ingredient_text(recipe)
    title = normalize(recipe.get("title") or "")
    has_sweet_signal = any(has_term(name, SWEET_TERMS) or is_supplement(name) for name in used_names)
    if not has_sweet_signal:
        return False
    has_savory_anchor = any(term in text for term in SAVORY_ANCHOR_TERMS)
    if any(term in title for term in SWEET_DISH_TERMS) and not has_savory_anchor:
        return True
    return has_sweet_signal and not has_savory_anchor


def _title_ingredient_conflict(recipe, fridge_items):
    title = normalize(recipe.get("title") or "")
    if not title:
        return True
    text = _ingredient_text(recipe) + " " + " ".join(normalize(n) for n in used_fridge_names(recipe, fridge_items))
    food_terms = set(SWEET_TERMS + VEGETABLE_TERMS + STARCH_TERMS + PROTEIN_TERMS + DAIRY_TERMS)
    title_foods = [term for term in food_terms if has_term(title, (term,))]
    if len(title_foods) >= 2:
        matched = [term for term in title_foods if term in text or any(normalize(alias) in text for alias in NAME_ALIASES.get(term, ()))]
        if len(matched) < max(1, len(title_foods) // 2):
            return True
    title_is_savory = any(term in title for term in SAVORY_ANCHOR_TERMS) or "pfanne" in title or "bowl" in title
    body_is_sweet = any(has_term(name, SWEET_TERMS) or is_supplement(name) for name in used_fridge_names(recipe, fridge_items))
    body_has_savory = any(term in text for term in SAVORY_ANCHOR_TERMS)
    return title_is_savory and body_is_sweet and not body_has_savory


def _title_is_overstuffed(recipe):
    title = normalize(recipe.get("title") or "")
    words = [word for word in re.findall(r"[a-zA-ZäöüÄÖÜß]+", title) if word not in TITLE_FILLER_WORDS]
    if any(has_term(title, (term,)) for term in SUPPLEMENT_TERMS):
        return True
    food_terms = set(SWEET_TERMS + VEGETABLE_TERMS + STARCH_TERMS + PROTEIN_TERMS + DAIRY_TERMS)
    named_foods = [term for term in food_terms if has_term(title, (term,))]
    if len(words) > 5:
        return True
    if len(named_foods) > 4:
        return True
    return len(title.split("-")) > 4


def _macro_targets_fit(recipe, fridge_items, daily_goal):
    macros = computed_macros(recipe, fridge_items)
    if not macros or not isinstance(daily_goal, dict):
        return True
    tolerances = {
        "kcal": lambda target: max(180.0, target * 0.30),
        "protein": lambda target: max(12.0, target * 0.25),
        "fat": lambda target: max(8.0, target * 0.30),
        "carbs": lambda target: max(18.0, target * 0.30),
    }
    for key, tolerance_for in tolerances.items():
        target = safe_float(daily_goal.get(key))
        if target is not None and target > 0 and abs(float(macros.get(key, 0.0)) - target) > tolerance_for(target):
            return False
    return True


def extract_recipes(response):
    if not isinstance(response, str) or not response.strip():
        return []
    try:
        parsed = json.loads(response.strip())
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]|\{.*\}", response.strip(), flags=re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if isinstance(parsed, dict):
        if isinstance(parsed.get("recipe"), dict):
            parsed = [parsed["recipe"]]
        elif parsed.get("title") and (parsed.get("ingredients") or parsed.get("instructions")):
            parsed = [parsed]
        else:
            nested = next((v for v in parsed.values() if isinstance(v, list) and any(isinstance(x, dict) for x in v)), None)
            parsed = nested if nested is not None else [parsed]
    return [r for r in parsed if isinstance(r, dict)] if isinstance(parsed, list) else []


def clean_recipe(recipe, fridge_items):
    macros = recipe.get("estimated_macros") if isinstance(recipe.get("estimated_macros"), dict) else {}
    structured = structured_fridge_ingredients(recipe, fridge_items)
    computed = computed_macros(recipe, fridge_items)
    ingredients = [item["label"] for item in structured] if structured else string_list(recipe.get("ingredients"))
    pantry_structured = _structured_pantry(recipe)
    if structured and pantry_structured:
        ingredients += [item["label"] for item in pantry_structured]
    pantry = string_list(recipe.get("pantry_assumptions")) or [item["label"] for item in pantry_structured]
    return {
        "title": str(recipe.get("title")).strip(),
        "why_this_works": str(recipe.get("why_this_works") or recipe.get("why") or "").strip(),
        "ingredients": ingredients,
        "instructions": string_list(recipe.get("instructions"))[:5],
        "estimated_macros": computed or {key: macros.get(key, 0) for key in ("kcal", "protein", "fat", "carbs")},
        "macro_source": "computed_from_fridge_amounts" if computed else "llm_estimate",
        "used_fridge_items": used_fridge_names(recipe, fridge_items),
        "pantry_assumptions": pantry,
    }


def valid_recipes(response, fridge_items, count, exclude=None, recipe_category=None, daily_goal=None):
    excluded = {normalize(t) for t in (exclude or [])}
    out, seen = [], set()
    for raw in extract_recipes(response):
        if not _is_valid(raw, fridge_items, recipe_category, daily_goal):
            continue
        clean = clean_recipe(raw, fridge_items)
        key = normalize(clean["title"])
        if key in seen or key in excluded:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= count:
            break
    return out


def _is_valid(recipe, fridge_items, recipe_category=None, daily_goal=None):
    if not recipe or not str(recipe.get("title") or "").strip():
        return False
    if not _ids_are_valid(recipe, fridge_items):
        return False
    used_names = used_fridge_names(recipe, fridge_items)
    if not used_names or not string_list(recipe.get("ingredients")):
        return False
    if not _legacy_ids_match_ingredients(recipe, fridge_items):
        return False
    if not _structured_amounts_are_realistic(recipe, fridge_items):
        return False
    if (
        _sweet_savory_conflict(used_names)
        or _supplement_savory_conflict(recipe, used_names)
        or _category_conflict(recipe, recipe_category, used_names)
    ):
        return False
    if _title_ingredient_conflict(recipe, fridge_items):
        return False
    if _title_is_overstuffed(recipe):
        return False
    if not _macro_targets_fit(recipe, fridge_items, daily_goal):
        return False
    return len(string_list(recipe.get("instructions"))) >= 3


def warning_recipe(title, message):
    return {
        "title": title,
        "why_this_works": message,
        "ingredients": [],
        "instructions": [
            "Pruefe, ob Ollama laeuft und das gewaehlte Modell installiert ist.",
            "Waehle in den Einstellungen bei Bedarf ein anderes Modell.",
            "Starte die Rezeptgenerierung danach erneut.",
        ],
        "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
        "macro_source": "none",
        "used_fridge_items": [],
        "pantry_assumptions": [],
        "warning": True,
    }


def _item_has_any(item, terms):
    return has_term(item.get("name"), terms)


def _dedup_numbered_items(fridge_items):
    out, seen = [], set()
    for item in numbered_items(fridge_items):
        key = normalize(item["name"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _fallback_portion_g(item):
    name = item["name"]
    if is_supplement(name):
        return 30
    if _item_has_any(item, ("milch", "milk")):
        return 200
    if _item_has_any(item, ("joghurt", "yogurt", "quark", "skyr")):
        return 180
    if _item_has_any(item, ("ei", "egg", "eier")):
        return 100
    if _item_has_any(item, ("kartoffel", "potato")):
        return 250
    if _item_has_any(item, VEGETABLE_TERMS):
        return 150
    if _item_has_any(item, STARCH_TERMS):
        return 80
    if _item_has_any(item, SWEET_TERMS):
        return 120
    if _item_has_any(item, PROTEIN_TERMS):
        return 150
    return 100


def _select_fallback_items(fridge_items, recipe_category=None):
    items = _dedup_numbered_items(fridge_items)
    if not items:
        return []
    selected = []

    def add_first(candidates, limit=1):
        for item in candidates:
            if item not in selected:
                selected.append(item)
                if sum(1 for chosen in selected if chosen in candidates) >= limit:
                    break

    if is_savory_category(recipe_category) or (
        not recipe_category and any(_item_has_any(item, VEGETABLE_TERMS + STARCH_TERMS + PROTEIN_TERMS) for item in items)
    ):
        savory_pool = [item for item in items if not is_supplement(item["name"]) and not _item_has_any(item, SWEET_TERMS)]
        add_first([item for item in savory_pool if _item_has_any(item, PROTEIN_TERMS)])
        add_first([item for item in savory_pool if _item_has_any(item, STARCH_TERMS)])
        add_first([item for item in savory_pool if _item_has_any(item, VEGETABLE_TERMS)], limit=2)
        selected += [item for item in savory_pool if item not in selected][: max(0, 4 - len(selected))]
    else:
        add_first([item for item in items if _item_has_any(item, BREAKFAST_STARCH_TERMS)])
        add_first([item for item in items if _item_has_any(item, DAIRY_TERMS)])
        add_first([item for item in items if _item_has_any(item, SWEET_TERMS)])
        add_first([item for item in items if is_supplement(item["name"])])
        selected += [item for item in items if item not in selected and not _item_has_any(item, VEGETABLE_TERMS)][: max(0, 4 - len(selected))]
    return selected[:4] or items[:3]


def fallback_recipe(fridge_items, recipe_category=None):
    selected = _select_fallback_items(fridge_items, recipe_category)
    if not selected:
        return warning_recipe("Keine Zutaten verfuegbar", "Es waren keine nutzbaren Kuehlschrank-Zutaten vorhanden.")
    names = [item["name"] for item in selected]
    pantry_items = [{"name": "Öl", "amount_g": 5, "label": "5g Öl"}] if is_savory_category(recipe_category) else []
    recipe_for_macros = {
        "fridge_ingredients": [
            {"id": item["id"], "amount_g": _fallback_portion_g(item), "label": _format_grams(_fallback_portion_g(item), item["name"])}
            for item in selected
        ],
        "pantry_ingredients": pantry_items,
    }
    macros = computed_macros(recipe_for_macros, fridge_items)
    ingredients = [entry["label"] for entry in recipe_for_macros["fridge_ingredients"]] + [item["label"] for item in pantry_items]
    savory = is_savory_category(recipe_category) or any(_item_has_any(item, VEGETABLE_TERMS + PROTEIN_TERMS) for item in selected)
    pantry_assumptions = ["Öl", "Salz", "Pfeffer"] if savory else ["Gewürze"]
    return {
        "title": "Modell fehlgeschlagen - lokaler Fallback",
        "why_this_works": "Das lokale Modell hat kein brauchbares Rezept nahe der Zielwerte erzeugt; FitFridge nutzt eine einfache, kompatible Ersatzvariante.",
        "ingredients": ingredients + (["Salz", "Pfeffer"] if savory else ["Gewürze nach Geschmack"]),
        "instructions": (
            [
                "Feste Zutaten vorbereiten und groessere Stuecke gleichmaessig schneiden.",
                "Protein, Staerke und Gemuese nacheinander mit wenig Öl garen.",
                "Mit Salz, Pfeffer und Gewuerzen abschmecken und direkt servieren.",
            ]
            if savory else [
                "Trockene und fluessige Zutaten verruehren und kurz quellen lassen.",
                "Obst oder passende Toppings unterheben.",
                "Abschmecken und als Bowl, Brei oder Shake servieren.",
            ]
        ),
        "estimated_macros": macros or {"kcal": 180 * len(names), "protein": 10 * len(names), "fat": 6 * len(names), "carbs": 22 * len(names)},
        "macro_source": "computed_from_fridge_amounts" if macros else "fallback_estimate",
        "used_fridge_items": names,
        "pantry_assumptions": pantry_assumptions,
        "fallback": True,
    }


def empty_fridge_recipe():
    return {
        "title": "Keine Zutaten verfügbar",
        "why_this_works": "Dein Kühlschrank ist leer.",
        "ingredients": [],
        "instructions": ["Füge zuerst Lebensmittel zu deinem Kühlschrank hinzu."],
        "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
        "macro_source": "none",
        "used_fridge_items": [],
        "pantry_assumptions": [],
    }
