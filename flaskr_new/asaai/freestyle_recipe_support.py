"""Parsing, Validierung und Makro-Berechnung für Freestyle-Rezepte."""
import copy
import json
import re

from ..calculations import safe_float

NUTRITION_FIELDS = ("kcal_per_100g", "protein_per_100g", "fat_per_100g", "carbs_per_100g")
MACRO_FIELDS = (("kcal", "kcal_per_100g"), ("protein", "protein_per_100g"), ("fat", "fat_per_100g"), ("carbs", "carbs_per_100g"))
MACRO_TOLERANCES = {
    "kcal": lambda x: max(90.0, x * 0.15),
    "protein": lambda x: max(8.0, x * 0.15),
    "fat": lambda x: max(8.0, x * 0.30),
    "carbs": lambda x: max(18.0, x * 0.30),
}
SUPPLEMENT = ("whey", "protein powder", "proteinpulver", "eiweisspulver", "isolate", "casein", "kasein")
SWEET = ("banane", "banana", "apfel", "apple", "beere", "berry", "honig", "honey", "marmelade", "jam", "nutella", "schoko", "chocolate", "datteln", "dates", "ahorn", "maple")
VEG = ("spinat", "spinach", "karotte", "carrot", "brokkoli", "broccoli", "paprika", "tomate", "tomato", "zucchini", "zwiebel", "onion", "champignon", "pilz", "mushroom", "lauch", "sellerie", "gurke", "salat", "kohl", "bohne", "erbse", "spargel", "asparagus")
STARCH = ("reis", "rice", "kartoffel", "potato", "nudel", "noodle", "pasta", "bulgur", "couscous", "hafer", "oat", "mehl", "flour", "brot", "bread", "bun", "buns", "broetchen", "brötchen", "semmel", "wrap", "tortilla")
PROTEIN = ("ei", "egg", "eier", "tofu", "tempeh", "huhn", "chicken", "rind", "beef", "steak", "fisch", "fish", "lachs", "salmon", "linsen", "lentil", "bohnen", "beans", "hack", "hackfleisch", "kaese", "cheese", "frischkaese", "joghurt", "yogurt")
DAIRY = ("milch", "milk", "joghurt", "yogurt", "quark", "skyr")
FOOD = set(SWEET + VEG + STARCH + PROTEIN + DAIRY)
SAVORY = VEG + STARCH + PROTEIN
# erste passende Gruppe gewinnt; Eier/Käse/Joghurt sind kein Hauptprotein
MAIN_PROTEIN_GROUPS = (
    ("fisch", ("fisch", "fish", "lachs", "salmon", "thunfisch", "tuna", "forelle", "garnele", "shrimp")),
    ("gefluegel", ("huhn", "chicken", "haehnchen", "hähnchen", "pute", "turkey", "gefluegel", "geflügel")),
    ("rind", ("rind", "beef", "steak")),
    ("schwein", ("schwein", "pork", "schinken", "speck", "bacon", "kassler")),
    ("lamm", ("lamm", "lamb")),
    ("hack", ("hack", "hackfleisch", "mince")),
    ("tofu", ("tofu", "tempeh", "seitan")),
)
MAIN_STARCH_GROUPS = (
    ("pasta", ("nudel", "noodle", "pasta", "spaghetti", "makkaroni", "penne", "fusilli", "tagliatelle")),
    ("reis", ("reis", "rice")),
    ("kartoffel", ("kartoffel", "potato")),
    ("brot", ("brot", "bread", "broetchen", "brötchen", "bun", "buns", "semmel", "wrap", "tortilla", "toast")),
    ("getreide", ("bulgur", "couscous", "quinoa")),
)
SAVORY_CATS = ("hauptspeise", "abendessen", "mittag", "lunch", "dinner", "main")
# Kein-Fleisch-Kategorien: hier sind Fleisch/Fisch als Hauptprotein unpassend.
SWEET_CATS = ("fruehstueck", "frühstück", "breakfast", "nachspeise", "nachtisch", "dessert", "snack")
MEAT_FISH = tuple(t for label, terms in MAIN_PROTEIN_GROUPS if label != "tofu" for t in terms)
SWEET_DISH = ("porridge", "haferbrei", "muesli", "smoothie", "shake", "joghurtbowl", "yogurt bowl", "dessert", "nachspeise", "pfannkuchen", "pancake")
SUPP_BLOCK = VEG + ("reis", "rice", "kartoffel", "potato", "nudel", "noodle", "pasta", "brot", "bread", "huhn", "chicken", "haehnchen", "hähnchen", "rind", "beef", "steak", "fisch", "fish", "lachs", "salmon", "tofu", "tempeh", "pfanne", "brat", "auflauf", "curry", "suppe", "salat", "gemuese", "gemüse")
SUPP_OK = ("pfannkuchen", "pancake", "porridge", "haferbrei", "shake", "smoothie", "joghurt", "yogurt", "quark", "skyr", "bowl", "gebaeck", "gebäck", "muffin", "waffel", "waffle")
FILLER = {"mit", "und", "auf", "an", "in", "aus", "der", "die", "das"}
SKIP_TOKENS = {"fitfridge", "demo", "bio", "fresh", "frisch", "local", "farm", "natur", "neutral", "original", "classic", "klassisch", "protein", "powder", "pulver", "pure", "bulk"}
ALIASES = {"egg": ("ei", "eier"), "eggs": ("ei", "eier"), "ei": ("egg", "eggs", "eier"), "eier": ("egg", "eggs", "ei"), "cheese": ("kaese", "kase", "käse"), "kaese": ("cheese", "käse"), "frischkaese": ("frischkäse", "cream cheese"), "oats": ("hafer", "haferflocken"), "rice": ("reis",), "flour": ("mehl",)}
def normalize(value):
    text = (value or "").lower()
    return text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
def has_term(text, terms):
    text = normalize(text)
    words = re.findall(r"[a-zA-ZäöüÄÖÜß]+", text)
    for term in terms:
        term = normalize(term)
        if len(term) <= 3 and term.isalpha():
            if term in words:
                return True
        elif term in text:
            return True
    return False
def is_supplement(name):
    return has_term(name, SUPPLEMENT)
def is_savory_category(category):
    return has_term(category or "", SAVORY_CATS)
def is_sweet_category(category):
    return has_term(category or "", SWEET_CATS)
def _sweetish(name):
    return has_term(name, SWEET) or is_supplement(name)
def _tokens(value):
    words = re.findall(r"[a-zA-ZäöüÄÖÜß]+", normalize(value))
    return [word for word in words if len(word) >= 3 and word not in SKIP_TOKENS]
def _by_id(fridge_items):
    return {item["id"]: item for item in numbered_items(fridge_items)}
def _num(value):
    value = safe_float(value)
    if value is None:
        return ""
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")
def _grams(amount, name):
    amount = _num(amount)
    return f"{amount}g {name}" if amount else name
def _amount_g(raw):
    return safe_float(raw.get("amount_g", raw.get("grams", raw.get("g"))))
def limit_items(fridge_items, max_items):
    items = [item for item in fridge_items if (item.get("name") or "").strip()]
    return items[:max_items] if max_items else items
def numbered_items(fridge_items):
    out = []
    for item_id, item in enumerate(fridge_items, 1):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        row = {"id": item_id, "name": name}
        for field in ("amount", "current_amount", "unit"):
            if item.get(field) not in (None, ""):
                row[field] = item[field]
        row.update({field: item[field] for field in NUTRITION_FIELDS if item.get(field) not in (None, "")})
        out.append(row)
    return out
def item_label(item):
    fields = (("kcal_per_100g", "kcal"), ("protein_per_100g", "P"), ("fat_per_100g", "F"), ("carbs_per_100g", "C"))
    bits = [f"{round(float(item[field]))}{short}" for field, short in fields if item.get(field) not in (None, "")]
    label = f'{item["id"]} {item["name"]}'
    if bits:
        label += f' ({" ".join(bits)} /100g)'
        if not any((safe_float(item.get(field)) or 0) > 0 for field in NUTRITION_FIELDS):
            label += " [Nährwerte fehlen]"
    if is_supplement(item["name"]):
        label += " [Supplement]"
    return label
def string_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = [part.strip(" .;:-") for part in re.split(r"\n+|\d+\.\s*|[.;]", value) if part.strip(" .;:-")]
        return parts or [value.strip()]
    return []
def _raw_fridge(recipe):
    return next((recipe[key] for key in ("fridge_ingredients", "used_fridge_ingredients", "recipe_items") if isinstance(recipe.get(key), list)), [])
def structured_fridge_ingredients(recipe, fridge_items):
    out, by_id = [], _by_id(fridge_items)
    for raw in _raw_fridge(recipe):
        if not isinstance(raw, dict):
            continue
        amount = _amount_g(raw)
        try:
            item = by_id[int(raw.get("id", raw.get("fridge_item_id")))]
        except (KeyError, TypeError, ValueError):
            continue
        if amount is None:
            continue
        label = str(raw.get("label") or raw.get("ingredient") or raw.get("name") or "").strip()
        out.append({"id": item["id"], "name": item["name"], "amount_g": amount, "label": label if label and re.search(r"\d", label) else _grams(amount, label or item["name"])})
    return out
def _structured_pantry(recipe):
    out = []
    for raw in recipe.get("pantry_ingredients") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or raw.get("label") or "").strip()
        if not name:
            continue
        amount = _amount_g(raw)
        label = str(raw.get("label") or "").strip() or (_grams(amount, name) if amount else name)
        if normalize(name) not in normalize(label):
            label = f"{name} {label}" if normalize(label).startswith(("zum ", "nach ")) else f"{label} {name}"
        out.append({"name": name, "amount_g": amount, "label": label})
    return out
def computed_macros(recipe, fridge_items):
    used = structured_fridge_ingredients(recipe, fridge_items)
    if not used:
        return None
    totals, by_id, has_data = {key: 0.0 for key, _ in MACRO_FIELDS}, _by_id(fridge_items), False
    for row in used:
        item = by_id[row["id"]]
        for key, field in MACRO_FIELDS:
            value = safe_float(item.get(field)) or 0.0
            totals[key] += value * row["amount_g"] / 100.0
            has_data = has_data or value > 0
    for item in _structured_pantry(recipe):
        pantry_name = normalize(item["name"])
        if item["amount_g"] is not None and ("oil" in pantry_name or "oel" in pantry_name):
            totals["kcal"] += item["amount_g"] * 9
            totals["fat"] += item["amount_g"]
    return {key: round(value, 1) for key, value in totals.items()} if has_data else None
def _ingredient_text(recipe):
    parts = string_list(recipe.get("ingredients")) + string_list(recipe.get("used_fridge_items"))
    parts += [str(raw.get("label") or raw.get("name") or raw.get("ingredient") or "") for raw in _raw_fridge(recipe) if isinstance(raw, dict)]
    return " ".join(normalize(part) for part in parts if part)
def _mentions_item(text, name):
    text = normalize(text)
    if normalize(name) in text:
        return True
    for token in _tokens(name):
        if token in text or any(normalize(alias) in text for alias in ALIASES.get(token, ())):
            return True
        if token.endswith("mehl") and "mehl" in text:
            return True
        if token.endswith("kaese") and "kaese" in text:
            return True
    return False
def _used_ids(recipe):
    ids = []
    for raw_id in recipe.get("used_fridge_item_ids") or []:
        try:
            ids.append(int(raw_id))
        except (TypeError, ValueError):
            ids.append(None)
    for raw in _raw_fridge(recipe):
        if isinstance(raw, dict):
            try:
                ids.append(int(raw.get("id", raw.get("fridge_item_id"))))
            except (TypeError, ValueError):
                ids.append(None)
    return ids
def used_fridge_names(recipe, fridge_items):
    structured = [item["name"] for item in structured_fridge_ingredients(recipe, fridge_items)]
    if structured:
        return list(dict.fromkeys(structured))
    names_by_id = {item["id"]: item["name"] for item in numbered_items(fridge_items)}
    names = [names_by_id[item_id] for item_id in _used_ids(recipe) if item_id in names_by_id]
    if not names:
        text = _ingredient_text(recipe)
        names = [item["name"] for item in numbered_items(fridge_items) if normalize(item["name"]) in text]
    return list(dict.fromkeys(names))
def _food_words(text):
    return [term for term in FOOD if has_term(text, (term,))]
def _ids_ok(recipe, fridge_items):
    ids = _used_ids(recipe)
    return bool(ids) and all(item_id in _by_id(fridge_items) for item_id in ids)
def _amounts_ok(recipe, fridge_items):
    for item in structured_fridge_ingredients(recipe, fridge_items):
        amount = item["amount_g"]
        if not 0 < amount <= 1200:
            return False
        if is_supplement(item["name"]) and amount > 80:
            return False
    return True
def _pantry_amounts_ok(recipe):
    for item in _structured_pantry(recipe):
        amount = item["amount_g"]
        if amount is None:
            continue
        name = normalize(item["name"])
        if any(term in name for term in ("salz", "pfeffer", "gewuerz", "gewürz", "spice")) and amount > 5:
            return False
        if ("oil" in name or "oel" in name) and amount > 30:
            return False
    return True
def _legacy_names_ok(recipe, fridge_items):
    if structured_fridge_ingredients(recipe, fridge_items) or not recipe.get("used_fridge_item_ids"):
        return True
    text = _ingredient_text(recipe)
    return all(_mentions_item(text, name) for name in used_fridge_names(recipe, fridge_items))
def _distinct_main_groups(used_names, groups):
    found = set()
    for name in used_names:
        for label, terms in groups:
            if has_term(name, terms):
                found.add(label)
                break
    return found
def _recipe_conflicts(recipe, category, used_names):
    text = _ingredient_text(recipe)
    title = normalize(recipe.get("title") or "")
    full_text = " ".join([title, text, " ".join(normalize(name) for name in used_names)])
    if len(_distinct_main_groups(used_names, MAIN_PROTEIN_GROUPS)) > 1:
        return True
    if len(_distinct_main_groups(used_names, MAIN_STARCH_GROUPS)) > 1:
        return True
    if any(has_term(name, VEG) for name in used_names) and any(_sweetish(name) for name in used_names):
        return True
    if any(is_supplement(name) for name in used_names) and (has_term(full_text, SUPP_BLOCK) or not has_term(full_text, SUPP_OK)):
        return True
    if is_savory_category(category) and any(_sweetish(name) for name in used_names) and (not has_term(text, SAVORY) or has_term(title, SWEET_DISH) and not has_term(text, SAVORY)):
        return True
    if is_sweet_category(category) and any(has_term(name, MEAT_FISH) for name in used_names):
        return True
    title_foods = _food_words(title)
    if len(title_foods) >= 2:
        matched = [term for term in title_foods if term in text or any(normalize(alias) in text for alias in ALIASES.get(term, ()))]
        if len(matched) < max(1, len(title_foods) // 2):
            return True
    title_words = [word for word in re.findall(r"[a-zA-ZäöüÄÖÜß]+", title) if word not in FILLER]
    if has_term(title, SUPPLEMENT) or len(title_words) > 5 or len(title_foods) > 4 or len(title.split("-")) > 4:
        return True
    return (has_term(title, SAVORY) or "pfanne" in title or "bowl" in title) and any(_sweetish(name) for name in used_names) and not has_term(text, SAVORY)
def has_macro_targets(daily_goal):
    return isinstance(daily_goal, dict) and any(safe_float(daily_goal.get(key)) for key, _ in MACRO_FIELDS)
def macro_target_ranges(daily_goal):
    if not has_macro_targets(daily_goal):
        return {}
    ranges = {}
    for key, tolerance in MACRO_TOLERANCES.items():
        target = safe_float(daily_goal.get(key))
        if not target:
            continue
        low = max(0.0, target - tolerance(target))
        high = None if key == "protein" else target * 1.05 if key == "kcal" else target + tolerance(target)
        ranges[key] = (round(low, 1), None if high is None else round(high, 1))
    return ranges
def macros_within_targets(macros, daily_goal):
    if not has_macro_targets(daily_goal):
        return True
    if not macros:
        return False
    for key, tolerance in MACRO_TOLERANCES.items():
        target = safe_float(daily_goal.get(key))
        if not target:
            continue
        value = float(macros.get(key, 0.0) or 0.0)
        if key == "kcal":
            if value > target * 1.05 or target - value > tolerance(target):
                return False
        elif key == "protein":
            if target - value > tolerance(target):
                return False
        elif abs(value - target) > tolerance(target):
            return False
    return True
def _macros_fit(recipe, fridge_items, daily_goal):
    macros = computed_macros(recipe, fridge_items)
    if not has_macro_targets(daily_goal):
        return True
    return macros_within_targets(macros, daily_goal)
def _scale_fridge_amounts(recipe, factor):
    # Mengen mit Faktor skalieren; Labels leeren -> aus neuer Menge neu aufbauen
    scaled = copy.deepcopy(recipe)
    for raw in _raw_fridge(scaled):
        if not isinstance(raw, dict):
            continue
        amount = _amount_g(raw)
        if amount is None:
            continue
        raw["amount_g"] = round(amount * factor, 1)
        raw.pop("grams", None)
        raw.pop("g", None)
        raw["label"] = ""
    return scaled
def _repair_macros(recipe, fridge_items, daily_goal):
    # außerhalb der Ziele: Portion aufs kcal-Ziel skalieren, nur wenn danach alles passt
    if not has_macro_targets(daily_goal):
        return recipe
    macros = computed_macros(recipe, fridge_items)
    if not macros or macros_within_targets(macros, daily_goal):
        return recipe
    target_kcal = safe_float((daily_goal or {}).get("kcal"))
    current_kcal = macros.get("kcal") or 0.0
    if not target_kcal or current_kcal <= 0:
        return recipe
    factor = max(0.5, min(2.0, target_kcal / current_kcal))
    if abs(factor - 1.0) < 0.01:
        return recipe
    scaled = _scale_fridge_amounts(recipe, factor)
    if not _amounts_ok(scaled, fridge_items):
        return recipe
    if macros_within_targets(computed_macros(scaled, fridge_items), daily_goal):
        return scaled
    return recipe
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
            parsed = next((v for v in parsed.values() if isinstance(v, list) and any(isinstance(x, dict) for x in v)), [parsed])
    return [recipe for recipe in parsed if isinstance(recipe, dict)] if isinstance(parsed, list) else []
def _is_valid(recipe, fridge_items, category=None, daily_goal=None):
    if not recipe or not str(recipe.get("title") or "").strip() or not string_list(recipe.get("ingredients")):
        return False
    used_names = used_fridge_names(recipe, fridge_items)
    return (
        bool(used_names)
        and _ids_ok(recipe, fridge_items)
        and _legacy_names_ok(recipe, fridge_items)
        and _amounts_ok(recipe, fridge_items)
        and _pantry_amounts_ok(recipe)
        and not _recipe_conflicts(recipe, category, used_names)
        and _macros_fit(recipe, fridge_items, daily_goal)
        and len(string_list(recipe.get("instructions"))) >= 3
    )
def clean_recipe(recipe, fridge_items):
    macros = recipe.get("estimated_macros") if isinstance(recipe.get("estimated_macros"), dict) else {}
    structured, pantry = structured_fridge_ingredients(recipe, fridge_items), _structured_pantry(recipe)
    computed = computed_macros(recipe, fridge_items)
    ingredients = [item["label"] for item in structured] if structured else string_list(recipe.get("ingredients"))
    if structured and pantry:
        ingredients += [item["label"] for item in pantry]
    return {
        "title": str(recipe.get("title")).strip(),
        "why_this_works": str(recipe.get("why_this_works") or recipe.get("why") or "").strip(),
        "ingredients": ingredients,
        "instructions": string_list(recipe.get("instructions"))[:8],
        "estimated_macros": computed or {key: macros.get(key, 0) for key in ("kcal", "protein", "fat", "carbs")},
        "macro_source": "computed_from_fridge_amounts" if computed else "llm_estimate",
        "used_fridge_items": used_fridge_names(recipe, fridge_items),
        "pantry_assumptions": string_list(recipe.get("pantry_assumptions")) or [item["label"] for item in pantry],
    }
def valid_recipes(response, fridge_items, count, exclude=None, recipe_category=None, daily_goal=None):
    excluded, out, seen = {normalize(title) for title in (exclude or [])}, [], set()
    for raw in extract_recipes(response):
        raw = _repair_macros(raw, fridge_items, daily_goal)
        if not _is_valid(raw, fridge_items, recipe_category, daily_goal):
            continue
        recipe, key = clean_recipe(raw, fridge_items), normalize(str(raw.get("title") or ""))
        if key not in seen and key not in excluded:
            seen.add(key)
            out.append(recipe)
        if len(out) >= count:
            break
    return out
def validation_feedback(response, fridge_items, daily_goal=None):
    if not has_macro_targets(daily_goal):
        return ""
    ranges = macro_target_ranges(daily_goal)
    range_text = ", ".join(f"{key}>={low}" if high is None else f"{key}={low}-{high}" for key, (low, high) in ranges.items())
    for raw in extract_recipes(response):
        macros = computed_macros(raw, fridge_items)
        if not macros:
            return "Nährwerte konnten nicht berechnet werden, weil fridge_ingredients mit amount_g fehlen."
        if not macros_within_targets(macros, daily_goal):
            macro_text = ", ".join(f"{key}={macros.get(key, 0)}" for key in ("kcal", "protein", "fat", "carbs"))
            return f"Berechnete Nährwerte aus amount_g waren {macro_text}; erlaubt ist {range_text}."
    return ""
def _stub_recipe(title, message, instructions, warning=False):
    stub = {"title": title, "why_this_works": message, "ingredients": [], "instructions": instructions, "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0}, "macro_source": "none", "used_fridge_items": [], "pantry_assumptions": []}
    if warning:
        stub["warning"] = True
    return stub
def warning_recipe(title, message):
    return _stub_recipe(title, message, ["Prüfe, ob Ollama laeuft und das gewaehlte Modell installiert ist.", "Wähle in den Einstellungen bei Bedarf ein anderes Modell.", "Starte die Rezeptgenerierung danach erneut."], warning=True)
def invalid_recipe_warning(title, message):
    return _stub_recipe(title, message, [], warning=True)
def empty_fridge_recipe():
    return _stub_recipe("Keine Zutaten verfügbar", "Dein Kühlschrank ist leer.", ["Füge zuerst Lebensmittel zu deinem Kühlschrank hinzu."])
