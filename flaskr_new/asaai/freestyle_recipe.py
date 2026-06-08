"""Freestyle recipe generation for FitFridge."""
from __future__ import annotations

import json
import re

from .ollama_client import generate_from_ollama


ALLOWED_PANTRY_TERMS = (
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

SWEET_FRIDGE_TERMS = (
    "apfel",
    "apple",
    "banane",
    "banana",
    "mango",
    "beere",
    "berry",
    "obst",
    "whey",
    "protein powder",
    "protein pulver",
)

SAVORY_FRIDGE_TERMS = (
    "tofu",
    "paprika",
    "tomate",
    "tomato",
    "reis",
    "rice",
    "huhn",
    "chicken",
    "rind",
    "beef",
    "fisch",
    "fish",
)

SAVORY_RECIPE_CATEGORIES = ("hauptspeise", "abendessen")
SWEET_RECIPE_CATEGORIES = ("fruehstueck", "frühstück", "nachspeise", "snack")


def _normalize(value: str) -> str:
    return (value or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")


def _item_names(fridge_items):
    return [item.get("name", "").strip() for item in fridge_items if item.get("name")]


def _numbered_fridge_items(fridge_items):
    numbered = []
    for index, item in enumerate(fridge_items, start=1):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        numbered.append({
            "id": index,
            "name": name,
            "amount": item.get("amount"),
        })
    return numbered


def build_freestyle_recipe_prompt(fridge_items, daily_goal=None, recipe_category=None, retry_reason=None):
    """Build a strict JSON prompt for one realistic fridge-based recipe."""
    payload = {
        "fridge_items": _numbered_fridge_items(fridge_items),
        "daily_goal_remaining": daily_goal or {},
        "recipe_category": recipe_category or "",
    }
    category_hint = f"Die Rezeptart soll {recipe_category} sein und Zutaten/Technik müssen dazu passen. " if recipe_category else ""
    retry_hint = f"Vorheriger Fehler: {retry_reason}. Erzeuge das JSON korrigiert neu. " if retry_reason else ""

    return (
        "Erzeuge genau ein einfaches, kochbares FitFridge-Rezept als JSON. "
        f"{retry_hint}"
        "Du darfst als Kühlschrank-Lebensmittel nur die IDs aus fridge_items verwenden. "
        "Erfinde weiterhin selbst ein Rezept, aber keine neuen Kühlschrank-Zutaten. "
        "Wähle so viele Kühlschrank-Zutaten wie sinnvoll sind, um Rezeptart und Makroziele zu erfüllen; "
        "nutze aber keine Zutat nur, weil sie verfügbar ist. "
        "Priorität: erst kulinarisch realistisches Gericht, dann Makroziele, dann Resteverwertung. "
        "Kombiniere keine süßen Zutaten wie Apfel/Banane/Whey mit herzhaften Zutaten wie Tofu/Paprika/Tomaten/Reis, außer es ist ein allgemein bekanntes Gericht. "
        "Für Hauptspeise oder Abendessen: keine Obst-/Whey-/Dessert-Kombinationen. "
        "Für Frühstück, Snack oder Nachspeise: keine Gemüse-Tofu-Reis-Pfannen als Pancake/Dessert tarnen. "
        "ingredients darf nur Namen aus fridge_items plus erlaubte pantry_assumptions enthalten. "
        "used_fridge_item_ids darf nur Zahlen aus fridge_items enthalten. "
        "Erlaubte pantry_assumptions: Wasser, Milch, Öl, Salz, Pfeffer, Backpulver, Gewürze. "
        "Der title muss ein echter Gerichtname sein, keine Zutatenverkettung. "
        "Nutze Pfannkuchen/Pancakes nur mit passenden süßen oder neutralen Zutaten wie Mehl, Eiern, Milch, Banane, Apfel oder Whey. "
        "Nutze Omelett/Frittata nur mit Eiern und passenden herzhaften Zutaten wie Gemüse oder Tofu. "
        "Nutze Bowl/Pfanne nur mit passenden herzhaften Zutaten wie Reis, Gemüse, Tofu, Fleisch oder Fisch. "
        f"{category_hint}"
        "Berücksichtige daily_goal_remaining: Das Rezept soll die Zielwerte möglichst gut treffen, ohne die Rezeptlogik zu zerstören. "
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


def _has_term(names, terms):
    normalized = " ".join(_normalize(name) for name in names)
    return any(term in normalized for term in terms)


def _recipe_is_coherent(recipe, fridge_items, recipe_category=None):
    used_names = _selected_fridge_item_names(recipe, fridge_items)
    normalized_title = _normalize(recipe.get("title") or "")
    category = _normalize(recipe_category or "")
    has_sweet = _has_term(used_names, SWEET_FRIDGE_TERMS)
    has_savory = _has_term(used_names, SAVORY_FRIDGE_TERMS)
    uses_tofu = _has_term(used_names, ("tofu",))
    uses_fruit = _has_term(used_names, ("apfel", "apple", "banane", "banana", "mango", "beere", "berry"))
    uses_whey = _has_term(used_names, ("whey", "protein powder", "protein pulver"))

    if uses_tofu and uses_fruit:
        return False

    if category in SAVORY_RECIPE_CATEGORIES and (uses_fruit or uses_whey):
        return False

    if category in SWEET_RECIPE_CATEGORIES and has_savory and (uses_fruit or uses_whey):
        return False

    if ("pfannkuchen" in normalized_title or "pancake" in normalized_title) and has_savory:
        return False

    if ("bowl" in normalized_title or "pfanne" in normalized_title) and has_sweet and has_savory:
        return False

    return True


def _recipe_quality_is_low(recipe, fridge_items, recipe_category=None):
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

    if not _recipe_is_coherent(recipe, fridge_items, recipe_category=recipe_category):
        return True

    macros = recipe.get("estimated_macros") or {}
    if all(_safe_float(macros.get(key)) == 0 for key in ("kcal", "protein", "fat", "carbs")):
        return True

    return False


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


def _parse_recipe_response(response: str, fridge_items, recipe_category=None):
    parsed = _extract_json_object(response)
    if not parsed:
        return None

    recipe = {}
    recipe.update({key: value for key, value in parsed.items() if value})
    recipe.setdefault("estimated_macros", {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0})
    recipe.setdefault("used_fridge_item_ids", [])
    recipe.setdefault("pantry_assumptions", [])
    if _recipe_quality_is_low(recipe, fridge_items, recipe_category=recipe_category):
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


def _generate_recipe_response(prompt, model, base_url, timeout):
    return generate_from_ollama(
        prompt=prompt,
        model=model,
        base_url=base_url,
        timeout=timeout,
        num_predict=900,
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

    prompt = build_freestyle_recipe_prompt(fridge_items, daily_goal, recipe_category=recipe_category)
    try:
        response = _generate_recipe_response(prompt, model, base_url, timeout)
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

    recipe = _parse_recipe_response(response, fridge_items, recipe_category=recipe_category)
    raw_responses = [response]
    if recipe is None:
        retry_prompt = build_freestyle_recipe_prompt(
            fridge_items,
            daily_goal,
            recipe_category=recipe_category,
            retry_reason=(
                "Die Antwort enthielt erfundene Zutaten, falsche IDs, fehlende Schritte, keine brauchbaren Makros "
                "oder eine unrealistische Zutatenkombination. Wähle passende Zutaten für Rezeptart und Makroziele."
            ),
        )
        try:
            retry_response = _generate_recipe_response(retry_prompt, model, base_url, timeout)
            raw_responses.append(retry_response)
            recipe = _parse_recipe_response(retry_response, fridge_items, recipe_category=recipe_category)
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
