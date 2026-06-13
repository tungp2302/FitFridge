"""Freestyle recipe generation from fridge items.

This module stays intentionally small: it builds the LLM prompt, calls Ollama,
and delegates parsing, validation, macro calculation, and fallback recipes to
``freestyle_recipe_support``.
"""
from __future__ import annotations

from .freestyle_recipe_support import (
    empty_fridge_recipe,
    fallback_recipe,
    item_label,
    limit_items,
    numbered_items,
    valid_recipes,
    warning_recipe,
)
from .ollama_client import generate_from_ollama, resolve_ollama_model


DEFAULT_PROFILE = {"num_predict": 900, "max_items": None}
MODEL_PROFILES = {
    "qwen3:4b": {"num_predict": 320, "max_items": 7},
    "gemma3:1b": {"num_predict": 420, "max_items": 5},
}

_SCHEMA = (
    '{"title":"string","why_this_works":"string","ingredients":["string"],'
    '"fridge_ingredients":[{"id":number,"amount_g":number,"label":"string"}],'
    '"pantry_ingredients":[{"name":"string","amount_g":number,"label":"string"}],'
    '"instructions":["string"],'
    '"estimated_macros":{"kcal":number,"protein":number,"fat":number,"carbs":number},'
    '"used_fridge_item_ids":[number],"pantry_assumptions":["string"]}'
)


def _profile(model):
    return MODEL_PROFILES.get((resolve_ollama_model(model) or "").lower(), DEFAULT_PROFILE)


def _goal_hint(daily_goal):
    parts = [f"{k}={v}" for k, v in (daily_goal or {}).items() if v not in (None, "")]
    return f" Zielwerte: {', '.join(parts)}." if parts else ""


def _exclude_hint(exclude):
    titles = ", ".join(str(title).strip() for title in (exclude or []) if str(title).strip())
    return f" Vermeide diese bereits vorgeschlagenen Gerichte: {titles}." if titles else ""


def build_prompt(fridge_items, daily_goal=None, recipe_category=None, retry_reason=None, count=1, exclude=None):
    """Build the prompt for ``count`` realistic JSON recipe objects."""
    fridge_list = ", ".join(item_label(item) for item in numbered_items(fridge_items))
    category = recipe_category or "Gericht"
    retry_hint = f"Vorheriger Versuch war unbrauchbar ({retry_reason}). " if retry_reason else ""

    return (
    f"Erzeuge genau {count} verschiedene, einfache und realistisch kochbare FitFridge-Rezepte als JSON-Array. "
    f"{retry_hint}"
    f"Rezeptart: {category}.{_goal_hint(daily_goal)}{_exclude_hint(exclude)} "

    f"Kuehlschrank-Zutaten, nur diese IDs erlaubt: {fridge_list}. "
    "Zusaetzlich erlaubt sind nur Wasser, Oel, Salz, Pfeffer, Gewuerze und Saucen wie Ketchup, Mayonnaise und Senf. "
    "Keine anderen Lebensmittel verwenden. "

    "REZEPTLOGIK: "
    "Waehle zuerst ein real existierendes, kulinarisch plausibles Gericht, das eine Person freiwillig essen wuerde. "
    "Geschmack, Textur und Kuechenlogik haben Vorrang vor Makrooptimierung; Zielwerte duerfen verfehlt werden, "
    "wenn sie nur durch unpassende Zutaten erreichbar waeren. "
    "Vermeide kuenstliche Fitness-Rezepte, fragwuerdige Zutatenkombinationen und reine Makro-Konstruktionen. "
    "Verwende nur Zutaten, die sinnvoll zum gewaehlten Gericht beitragen. "
    "Verwende weder unnoetig viele noch unnoetig wenige Zutaten. "
    "Makroziele sind zweitrangig, wenn sie mit den vorhandenen Lebensmitteln nicht sinnvoll erreichbar sind. "

    "GERICHTSART: "
    "Fuer Hauptspeise oder Abendessen bevorzuge herzhafte Gerichte. "
    "Diese sollten typischerweise Protein, Staerke und/oder Gemuese enthalten, sofern passende Zutaten vorhanden sind. "
    "Brot, Broetchen, Buns, Wraps, Reis, Kartoffeln, Nudeln und aehnliche Beilagen zaehlen als passende Staerke. "
    "Wenn solche Staerken fuer ein herzhaftes Gericht vorhanden sind, nutze sie lieber als suesse Zutaten. "
    "Keine Fruehstuecks-, Dessert-, Shake-, Porridge- oder suesse Bowl-Ideen, ausser die Rezeptart verlangt dies ausdruecklich. "
    "Suess und herzhaft nicht unnatuerlich vermischen. "

    "ZUTATENREGELN: "
    "Suesse Zutaten oder Supplements nicht mit Gemuese, Reis, Kartoffeln, Fleisch, Fisch, Tofu oder herzhaften Pfannengerichten kombinieren. "
    "Ei, Milch oder Frischkaese nur dann mit Supplements kombinieren, wenn das Gericht klar suess ist "
    "(z.B. Pfannkuchen, Porridge, Shake, Joghurt oder Gebaeck). "
    "Protein-Pulver/Whey niemals in herzhafte Hauptgerichte, Pfannen, Reisgerichte, Kartoffelgerichte oder Fleischgerichte geben; "
    "fuer Proteinziele lieber natuerliche Proteinquellen nutzen oder das Ziel verfehlen. "
    "Bei Hauptspeise oder Abendessen Supplements auslassen, sobald passende natuerliche Proteinquellen, Staerken oder Gemuese vorhanden sind. "
    "Gemuese nur in klar herzhaften Gerichten verwenden. "
    "Mit [Supplement] markierte Zutaten nur in Shakes, Porridge, Pfannkuchen, Gebaeck oder Joghurt verwenden. "
    "Mit [Naehrwerte fehlen] markierte Zutaten duerfen kulinarisch verwendet werden, zaehlen aber nicht zum Erreichen von Makrozielen. "

    "MENGEN: "
    "Waehle realistische Portionsgroessen fuer eine Person. "
    "Typische Mengen sind 50-100g Getreide oder Mehl, 100-250g Beilage oder Gemuese, "
    "80-220g Proteinquelle, ca. 30g Proteinpulver und 50-100g Ei. "
    "Kaese und sehr fettreiche Toppings meist nur 15-40g verwenden; Saucen meist 5-20g. "
    "Broetchen, Buns, Wraps und Brot immer als realistische Grammmenge angeben, nicht als 1g. "
    "Nicht den gesamten Vorrat verbrauchen. "

    "KONSISTENZREGELN: "
    "Jede verwendete Kuehlschrank-Zutat muss in fridge_ingredients stehen mit exakter id, amount_g pro Person und label. "
    "used_fridge_item_ids darf keine ID enthalten, die nicht in fridge_ingredients vorkommt. "
    "ingredients, fridge_ingredients, title, why_this_works und used_fridge_item_ids muessen exakt dieselbe Gerichtsidee beschreiben. "
    "ingredients muss einzelne Zutaten nennen, niemals den Rezepttitel als Zutatenzeile. "
    "Der title darf keine Lebensmittel nennen, die nicht in fridge_ingredients vorkommen. "
    "Der title soll ein kurzer deutscher Gerichtname sein, maximal 3-4 Woerter, keine Zutatenliste, keine Marken. "
    "Kein 'Whey' oder 'Protein Powder' im Titel; stattdessen z.B. 'Protein-Pfannkuchen'. "

    "QUALITAET: "
    "Bei mehreren Rezepten muessen sich Gerichtstyp, Zubereitungsart oder Hauptzutaten deutlich unterscheiden. "
    "Vermeide triviale Varianten desselben Rezepts. "

    "NAEHRWERTE: "
    "FitFridge berechnet Naehrwerte aus amount_g. "
    "estimated_macros nur plausibel fuellen und niemals schoenrechnen. "

    "AUSGABE: "
    "why_this_works soll auf Deutsch in genau einem kurzen Satz erklaeren, warum Geschmack, Textur und Zubereitung zusammenpassen. "
    "Kein Marketingtext und keine reine Makro-Begruendung. "
    "Schreibe genau 3 kurze instructions, keine vierte oder weitere Schritte. "
    "Jedes Objekt muss vollstaendig valides JSON sein. "
    "Keine Kommentare. "
    "Keine Markdown-Formatierung. "
    "Keine Erklaerungen vor oder nach dem JSON. "

    f"Antworte ausschliesslich mit einem JSON-Array aus genau {count} Objekten dieser Form: [{_SCHEMA}]"
)

def _run(fridge_items, daily_goal, recipe_category, model, base_url, timeout, count, exclude=None):
    """Common flow. Returns ``{recipes, error, prompt, raw, items}``."""
    profile = _profile(model)
    prompt_items = limit_items(fridge_items, profile["max_items"])
    temperature = 0.7 if count > 1 else 0.15

    def ask(retry_reason=None):
        prompt = build_prompt(
            prompt_items,
            daily_goal,
            recipe_category,
            retry_reason=retry_reason,
            count=count,
            exclude=exclude,
        )
        response = generate_from_ollama(
            prompt=prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
            num_predict=profile["num_predict"] * count,
            format_json=True,
            temperature=temperature,
        )
        return prompt, response

    try:
        prompt, response = ask()
    except Exception as exc:
        return {"recipes": None, "error": str(exc), "prompt": "", "raw": "", "items": prompt_items}

    raw_responses = [response]
    recipes = valid_recipes(
        response,
        prompt_items,
        count,
        exclude=exclude,
        recipe_category=recipe_category,
        daily_goal=daily_goal,
    )
    if not recipes:
        try:
            _, retry_response = ask(
                retry_reason=(
                    "Titel/Zutaten widersprechen sich, falsche IDs, unpassende Rezeptart, "
                    "unrealistische Mengen, Zielwerte stark verfehlt oder fehlende Schritte"
                )
            )
        except Exception:
            retry_response = ""
        if retry_response:
            raw_responses.append(retry_response)
            recipes = valid_recipes(
                retry_response,
                prompt_items,
                count,
                exclude=exclude,
                recipe_category=recipe_category,
                daily_goal=daily_goal,
            )

    if not recipes and daily_goal:
        for raw_response in reversed(raw_responses):
            recipes = valid_recipes(
                raw_response,
                prompt_items,
                count,
                exclude=exclude,
                recipe_category=recipe_category,
                daily_goal=None,
            )
            if recipes:
                break

    return {
        "recipes": recipes,
        "error": None,
        "prompt": prompt,
        "raw": "\n\n--- retry ---\n\n".join(raw_responses),
        "items": prompt_items,
    }


def generate_freestyle_recipes(fridge_items, daily_goal=None, recipe_category=None, model=None, base_url=None, timeout=180, count=3, exclude=None):
    """Generate up to ``count`` recipe suggestions from fridge contents."""
    if not fridge_items:
        return {"recipes": [empty_fridge_recipe()], "prompt_used": "", "raw_response": ""}

    result = _run(fridge_items, daily_goal, recipe_category, model, base_url, timeout, count=count, exclude=exclude)
    if result["recipes"] is None:
        message = f"Die lokale LLM-Anbindung konnte nicht genutzt werden: {result['error']}"
        return {"recipes": [warning_recipe("LLM nicht erreichbar", message)], "prompt_used": "", "raw_response": "", "error": result["error"]}
    recipes = result["recipes"] or [fallback_recipe(result["items"], recipe_category=recipe_category)]
    return {"recipes": recipes, "prompt_used": result["prompt"], "raw_response": result["raw"]}


def generate_freestyle_recipe(fridge_items, daily_goal=None, recipe_category=None, model=None, base_url=None, timeout=120):
    """Generate exactly one recipe as ``{"recipe": ...}``."""
    result = generate_freestyle_recipes(fridge_items, daily_goal, recipe_category, model, base_url, timeout, count=1)
    out = {"recipe": result["recipes"][0], "prompt_used": result["prompt_used"], "raw_response": result["raw_response"]}
    if "error" in result:
        out["error"] = result["error"]
    return out
