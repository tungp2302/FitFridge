"""Freestyle recipe generation for FitFridge.

The larger ASaAI experiment is archived for now. This module keeps only the
LLM feature that is still used in the recipe planner.
"""
from __future__ import annotations

import json

from .ollama_client import generate_from_ollama


PROTEIN_KEYWORDS = {
    "chicken",
    "beef",
    "pork",
    "fish",
    "salmon",
    "tuna",
    "egg",
    "eggs",
    "tofu",
    "quark",
    "yogurt",
    "yoghurt",
    "cheese",
    "lentil",
    "beans",
    "protein",
    "huhn",
    "rind",
    "fisch",
    "ei",
    "eier",
    "käse",
    "kaese",
    "linsen",
    "bohnen",
}


def _is_protein_source(name: str) -> bool:
    text = (name or "").lower()
    return any(keyword in text for keyword in PROTEIN_KEYWORDS)


def build_freestyle_recipe_prompt(fridge_items, daily_goal=None, recipe_category=None):
    """Build a strict JSON prompt for one realistic fridge-based recipe."""
    protein_items = [
        item.get("name", "") for item in fridge_items if _is_protein_source(item.get("name", ""))
    ]
    payload = {
        "fridge_items": [item.get("name", "") for item in fridge_items],
        "fridge_protein_items": protein_items,
        "daily_goal_remaining": daily_goal or {},
        "recipe_category": recipe_category or "",
    }

    category_hint = f"Die Rezeptart soll {recipe_category} sein. " if recipe_category else ""

    return (
        "Du bist ein realistischer Rezept-Generator für FitFridge. "
        "Erfinde genau ein Rezept, das stark auf dem vorhandenen Kühlschrank-Inhalt basiert. "
        f"{category_hint}"
        "Bevorzuge Proteinquellen im Kühlschrank, dann Gemüse und Sättigungsbeilagen. "
        "Nutze höchstens 3 Pantry-Staples wie Öl, Salz, Pfeffer, Zwiebel oder Knoblauch. "
        "Antworte ausschließlich als valides JSON-Objekt ohne Markdown und ohne Zusatztext.\n\n"
        "JSON-Schema:\n"
        "{\n"
        '  "title": "string",\n'
        '  "why_this_works": "string",\n'
        '  "ingredients": ["string"],\n'
        '  "instructions": ["string"],\n'
        '  "estimated_macros": {"kcal": number, "protein": number, "fat": number, "carbs": number},\n'
        '  "used_fridge_items": ["string"],\n'
        '  "pantry_assumptions": ["string"]\n'
        "}\n\n"
        f"Daten:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _fallback_recipe(fridge_items):
    selected = [item.get("name", "") for item in fridge_items if item.get("name")][:3]
    title = " + ".join(selected) or "Einfaches Kühlschrank-Rezept"
    return {
        "title": title,
        "why_this_works": "Dieses Rezept kombiniert die ersten passenden Kühlschrank-Zutaten zu einer einfachen Mahlzeit.",
        "ingredients": selected,
        "instructions": [
            "Zutaten vorbereiten und bei Bedarf klein schneiden.",
            "Pfanne erhitzen, würzen und die Zutaten nacheinander garen.",
            "Abschmecken und direkt servieren.",
        ],
        "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
        "used_fridge_items": selected,
        "pantry_assumptions": ["Öl", "Salz", "Pfeffer"],
    }


def _parse_recipe_response(response: str, fridge_items):
    try:
        parsed = json.loads(response)
    except (TypeError, json.JSONDecodeError):
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    recipe = _fallback_recipe(fridge_items)
    recipe.update({key: value for key, value in parsed.items() if value})
    recipe.setdefault("estimated_macros", {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0})
    recipe.setdefault("used_fridge_items", [])
    recipe.setdefault("pantry_assumptions", [])
    return recipe


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
        response = generate_from_ollama(
            prompt=prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
            num_predict=650,
        )
    except Exception:
        response = ""

    return {
        "recipe": _parse_recipe_response(response, fridge_items),
        "prompt_used": prompt,
        "raw_response": response,
    }
