"""Rezeptvorschläge aus Kühlschrank-Zutaten via Ollama."""
from .freestyle_recipe_support import (
    empty_fridge_recipe,
    has_term,
    invalid_recipe_warning,
    is_savory_category,
    is_sweet_category,
    is_supplement,
    MEAT_FISH,
    format_ranges,
    item_label,
    limit_items,
    macro_target_ranges,
    macros_within_targets,
    numbered_items,
    safe_float,
    validation_feedback,
    valid_recipes,
    warning_recipe,
)
from .ollama_client import generate_from_ollama, resolve_ollama_model


DEFAULT_PROFILE = {"num_predict": 1200, "max_items": None}
MODEL_PROFILES = {
    "qwen3:4b": {"num_predict": 720, "max_items": 7},
    "gemma3:1b": {"num_predict": 760, "max_items": 5},
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
    if not parts:
        return ""
    range_parts = format_ranges(macro_target_ranges(daily_goal))
    range_hint = f" Erlaubte berechnete Bereiche: {', '.join(range_parts)}." if range_parts else ""
    return f" Zielwerte: {', '.join(parts)}.{range_hint} Diese Zielbereiche sind harte Validierungsregeln."


def _exclude_hint(exclude):
    titles = ", ".join(str(title).strip() for title in (exclude or []) if str(title).strip())
    return f" Vermeide diese bereits vorgeschlagenen Gerichte: {titles}." if titles else ""


def _macro_strategy_hint(fridge_items, daily_goal, recipe_category=None):
    if not macro_target_ranges(daily_goal):
        return ""
    savory = is_savory_category(recipe_category)
    sweet = is_sweet_category(recipe_category)
    starch_terms = ("reis", "rice", "nudel", "noodle", "pasta", "spaghetti", "bun", "buns", "broetchen", "brötchen", "brot", "bread", "wrap", "tortilla")
    secondary_protein_terms = ("kaese", "käse", "cheddar", "parmesan", "acciughe", "sardelle", "anchovy", "olive", "oliven")
    protein_items, starch_items, fat_items = [], [], []
    has_supplement = False
    for item in numbered_items(fridge_items):
        name = item["name"]
        protein = safe_float(item.get("protein_per_100g")) or 0.0
        carbs = safe_float(item.get("carbs_per_100g")) or 0.0
        fat = safe_float(item.get("fat_per_100g")) or 0.0
        has_supplement = has_supplement or is_supplement(name)
        if protein >= 15 and (not savory or not is_supplement(name)) and not has_term(name, secondary_protein_terms) and not (sweet and has_term(name, MEAT_FISH)):
            protein_items.append((protein, name))
        if carbs >= 20 and has_term(name, starch_terms):
            starch_items.append((carbs, name))
        if fat >= 10 and not is_supplement(name):
            fat_items.append((fat, name))

    def names(rows, limit=3):
        return ", ".join(name for _, name in sorted(rows, reverse=True)[:limit])

    parts = []
    if sweet:
        parts.append("für Frühstück, Nachspeise oder Snack KEIN Fleisch und keinen Fisch; Protein vor allem über magere, kcal-arme Quellen wie Joghurt/Quark (150-300g), Eier und Haferflocken (40-70g), Käse (20-100g), Proteinpulver oder Whey (5-60g); " \
        "fettreiche Zutaten wie Nüsse, Öl, Nutella nur sehr sparsam, sonst wird das kcal-Ziel gesprengt bevor das Protein-Ziel erreicht ist")
    protein_target = safe_float((daily_goal or {}).get("protein")) or 0.0
    carbs_target = safe_float((daily_goal or {}).get("carbs")) or 0.0
    low_carb = bool(carbs_target) and carbs_target <= 40
    if sweet and protein_target >= 40 and has_supplement:
        parts.append("bei diesem Protein-Ziel ist Whey/Proteinpulver (30-60g) im Shake, Porridge oder Protein-Pfannkuchen die kcal-effizienteste Proteinquelle und sollte priorisiert werden, weil magere Quellen wie Joghurt das kcal-Ziel sprengen, bevor das Protein-Ziel erreicht ist")
    if protein_target >= 50 and not sweet:
        parts.append("bei Protein-Ziel ab 50g ist 150g Hauptprotein meist zu wenig; für Rumpsteak, Hähnchen oder Hack eher ca. 200-300g verwenden")
    if protein_items and not sweet:
        parts.append(f"Protein eher über {names(protein_items)} erreichen, meist 180-300g")
    if low_carb:
        parts.append("Kohlenhydrat-Ziel ist niedrig: Stärkebeilagen wie Reis, Nudeln oder Brot stark reduzieren (höchstens ca. 30g trocken) oder weglassen und die Kalorien stattdessen über Protein und Fett (Öl, Käse, fettreicheres Fleisch) decken")
    elif starch_items:
        parts.append(f"für kcal/carbs eher {names(starch_items)} nutzen, bei Reis/Nudeln meist 100-150g trocken; nicht Kartoffeln oder Gemüse allein")
    if fat_items:
        parts.append(f"Fett bei Bedarf über 10-20g Öl und passende Fettquellen wie {names(fat_items)} erhöhen")
    else:
        parts.append("Fett bei Bedarf über 10-20g Öl erhöhen")
    return f" Makro-Strategie für diese Zutaten: {'; '.join(parts)}." if parts else ""


def _target_fit_recipes(recipes, daily_goal):
    return [recipe for recipe in (recipes or []) if macros_within_targets(recipe.get("estimated_macros"), daily_goal)]


def build_prompt(fridge_items, daily_goal=None, recipe_category=None, retry_reason=None, count=1, exclude=None):
    """Build the prompt for ``count`` realistic JSON recipe objects."""
    fridge_list = ", ".join(item_label(item) for item in numbered_items(fridge_items))
    category = recipe_category or "Gericht"
    retry_hint = f"Vorheriger Versuch war unbrauchbar ({retry_reason}). " if retry_reason else ""

    return (
    f"Erzeuge genau {count} verschiedene, einfache und realistisch kochbare FitFridge-Rezepte als JSON-Array. "
    f"{retry_hint}"
    f"Rezeptart: {category}.{_goal_hint(daily_goal)}{_macro_strategy_hint(fridge_items, daily_goal, recipe_category)}{_exclude_hint(exclude)} "

    f"Kühlschrank-Zutaten, nur diese IDs erlaubt: {fridge_list}. "
    "Zusätzlich erlaubt sind nur Wasser, Öl, Salz, Zucker, Süßungsmittel, Pfeffer, Gewürze und Saucen wie Ketchup, Mayonnaise und Senf. "
    "Keine anderen Lebensmittel verwenden. "
    "Pantry-Zutaten nur aufführen, wenn sie wirklich verwendet werden; nicht die erlaubte Pantry-Liste als Zutaten kopieren. "

    "REZEPTLOGIK: "
    "Wähle zuerst ein real existierendes, kulinarisch plausibles Gericht, das eine Person freiwillig essen würde. "
    "Geschmack, Textur und Küchenlogik haben Vorrang vor künstlichen Makro-Konstruktionen. "
    "Vermeide künstliche Fitness-Rezepte, fragwürdige Zutatenkombinationen und reine Makro-Konstruktionen. "
    "Verwende nur Zutaten, die sinnvoll zum gewählten Gericht beitragen. "
    "Verwende weder unnoetig viele noch unnoetig wenige Zutaten. "
    "Wenn Zielwerte angegeben sind, muss die berechnete Summe aus amount_g innerhalb der erlaubten Bereiche liegen. "
    "Kalorien dürfen das Ziel um höchstens 10% überschreiten. "
    "Protein darf über dem Zielwert liegen, aber nicht deutlich darunter. "
    "Fett und Kohlenhydrate müssen innerhalb der angegebenen Toleranzen bleiben. "

    "GERICHTSART: "
    "Für Hauptspeise oder Abendessen bevorzuge herzhafte Gerichte. "
    "Diese sollten typischerweise Protein, Stärke und/oder Gemüse enthalten, sofern passende Zutaten vorhanden sind. "
    "Wähle genau EINE Hauptproteinquelle und genau EINE Haupt-Stärkebeilage pro Gericht. "
    "Kombiniere niemals mehrere Fleisch- oder Fischsorten (z.B. nicht Rind und Hähnchen zusammen) "
    "und niemals mehrere Stärkebeilagen (z.B. nicht Spaghetti und Kartoffeln, nicht Reis und Nudeln zusammen). "
    "Nutze nicht alle vorhandenen Zutaten, nur weil sie da sind; lass überzählige Protein- oder Stärkequellen weg. "
    "Brot, Brötchen, Buns, Wraps, Reis, Kartoffeln, Nudeln und ähnliche Beilagen zählen als passende Stärke. "
    "Wenn solche Stärken für ein herzhaftes Gericht vorhanden sind, nutze sie lieber als süße Zutaten. "
    "Keine Frühstücks-, Dessert-, Shake-, Porridge- oder süße Bowl-Ideen, außer die Rezeptart verlangt dies ausdrücklich. "
    "Süß und herzhaft nicht unnatürlich vermischen. "

    "ZUTATENREGELN: "
    "Süße Zutaten oder Supplements nicht mit Gemüse, Reis, Kartoffeln, Fleisch, Fisch, Tofu oder herzhaften Pfannengerichten kombinieren. "
    "Ei, Milch oder Frischkäse nur dann mit Supplements kombinieren, wenn das Gericht klar süß ist "
    "(z.B. Pfannkuchen, Porridge, Shake, Joghurt oder Gebäck). "
    "Protein-Pulver/Whey niemals in herzhafte Hauptgerichte, Pfannen, Reisgerichte, Kartoffelgerichte oder Fleischgerichte geben; "
    "für Proteinziele lieber natürliche Proteinquellen nutzen oder das Ziel verfehlen. "
    "Bei Hauptspeise oder Abendessen Supplements auslassen, sobald passende natürliche Proteinquellen, Stärken oder Gemüse vorhanden sind. "
    "Gemüse nur in klar herzhaften Gerichten verwenden. "
    "Mit [Supplement] markierte Zutaten nur in Shakes, Porridge, Pfannkuchen, Gebäck oder Joghurt verwenden. "
    "Mit [Nährwerte fehlen] markierte Zutaten dürfen kulinarisch verwendet werden, zählen aber nicht zum Erreichen von Makrozielen. "

    "MENGEN: "
    "Wähle realistische Portionsgrößen für eine Person. "
    "Typische Mengen sind 50-160g trockenes Getreide, Reis, Nudeln oder Mehl, 100-300g Kartoffeln oder Gemüse, "
    "120-300g Proteinquelle, ca. 30g Proteinpulver und 50-100g Ei. "
    "Käse, Oliven und sehr fettreiche Toppings meist 15-50g verwenden; Öl meist 5-20g. "
    "Salz, Pfeffer und Gewürze nur ohne Menge oder mit 1-2g angeben, niemals 10g. "
    "Brötchen, Buns, Wraps und Brot immer als realistische Grammmenge angeben, nicht als 1g. "
    "Reis und Nudeln als trockene Grammmenge passend zu den /100g-Nährwerten angeben, nicht als gekocht deklarieren. "
    "Nicht den gesamten Vorrat verbrauchen. "

    "KONSISTENZREGELN: "
    "Jede verwendete Kühlschrank-Zutat muss in fridge_ingredients stehen mit exakter id, amount_g pro Person und label. "
    "used_fridge_item_ids darf keine ID enthalten, die nicht in fridge_ingredients vorkommt. "
    "ingredients, fridge_ingredients, title, why_this_works und used_fridge_item_ids müssen exakt dieselbe Gerichtsidee beschreiben. "
    "ingredients muss einzelne Zutaten nennen, niemals den Rezepttitel als Zutatenzeile. "
    "Der title darf keine Lebensmittel nennen, die nicht in fridge_ingredients vorkommen. "
    "Der title soll ein kurzer deutscher Gerichtname sein, maximal 3-4 Wörter, keine Zutatenliste, keine Marken. "
    "Kein 'Whey' oder 'Protein Powder' im Titel; stattdessen z.B. 'Protein-Pfannkuchen'. "

    "QUALITÄT: "
    "Bei mehreren Rezepten müssen sich Gerichtstyp, Zubereitungsart oder Hauptzutaten deutlich unterscheiden. "
    "Vermeide triviale Varianten desselben Rezepts. "

    "NÄHRWERTE: "
    "FitFridge berechnet Nährwerte aus amount_g. "
    "Rechne vor der Ausgabe mit den angegebenen /100g-Werten nach. "
    "Wenn kcal oder Protein zu niedrig sind, erhöhe zuerst eine passende Proteinquelle und eine passende Stärke. "
    "Wenn Fett zu niedrig ist, erhöhe Öl, Oliven, Käse, Hackfleisch oder andere passende Fettquellen. "
    "Priorität: kcal höchstens 10% über Ziel, protein mindestens nahe Ziel, fat und carbs innerhalb Toleranz. "
    "estimated_macros nur plausibel füllen und niemals schönrechnen. "

    "AUSGABE: "
    "why_this_works soll auf Deutsch in genau einem kurzen Satz erklären, warum Geschmack, Textur und Zubereitung zusammenpassen. "
    "Kein Marketingtext und keine reine Makro-Begruendung. "
    "Schreibe so viele kurze instructions, wie das Gericht wirklich braucht: einfache Gerichte 3-4 Schritte, "
    "ein durchschnittliches Hauptgericht 5-8 klare Schritte. "
    "Jeder Schritt ist genau eine konkrete Koch-Handlung in der richtigen Reihenfolge "
    "(z.B. vorbereiten/schneiden, anbraten, kochen lassen, würzen, anrichten); "
    "fasse nicht mehrere Arbeitsschritte in einem Satz zusammen und erfinde keine Füllschritte. "
    "Instructions dürfen keine Makroberechnung, Kalorienzeile, Anpassungsnotiz oder Erklärung enthalten. "
    "Jedes Objekt muss vollständig valides JSON sein. "
    "Keine Kommentare. "
    "Keine Markdown-Formatierung. "
    "Keine Erklärungen vor oder nach dem JSON. "

    f"Antworte ausschließlich mit einem JSON-Array aus genau {count} Objekten dieser Form: [{_SCHEMA}]"
)

def _run(fridge_items, daily_goal, recipe_category, model, base_url, timeout, count, exclude=None):
    """Common flow. Returns ``{recipes, error, prompt, raw, items, feedback}``."""
    profile = _profile(model)
    prompt_items = limit_items(fridge_items, profile["max_items"])
    temperature = 0.7 if count > 1 else 0.15
    max_attempts = 3 if count <= 1 else count + 1

    def ask(retry_reason=None, extra_exclude=None):
        prompt = build_prompt(
            prompt_items,
            daily_goal,
            recipe_category,
            retry_reason=retry_reason,
            count=count,
            exclude=(list(exclude or []) + list(extra_exclude or [])) or None,
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
        return {"recipes": None, "error": str(exc), "prompt": "", "raw": "", "items": prompt_items, "feedback": ""}

    raw_responses = [response]
    recipes = valid_recipes(
        response,
        prompt_items,
        count,
        exclude=exclude,
        recipe_category=recipe_category,
        daily_goal=daily_goal,
    )

    # fehlt was, nachfordern und gefundene Titel ausschließen
    attempt = 1
    while len(recipes) < count and attempt < max_attempts:
        attempt += 1
        found_titles = [recipe["title"] for recipe in recipes]
        retry_reason = (
            "Titel/Zutaten widersprechen sich, falsche IDs, unpassende Rezeptart, "
            "unrealistische Mengen, Zielwerte stark verfehlt oder fehlende Schritte"
            if not recipes
            else "Es fehlen noch valide, deutlich unterschiedliche Rezepte"
        )
        feedback = validation_feedback(raw_responses[-1], prompt_items, daily_goal)
        if feedback:
            retry_reason += f"; {feedback}"
        try:
            _, retry_response = ask(retry_reason=retry_reason, extra_exclude=found_titles)
        except Exception:
            break
        if not retry_response:
            break
        raw_responses.append(retry_response)
        more = valid_recipes(
            retry_response,
            prompt_items,
            count,
            exclude=list(exclude or []) + found_titles,
            recipe_category=recipe_category,
            daily_goal=daily_goal,
        )
        recipes = (recipes + more)[:count]

    return {
        "recipes": recipes,
        "error": None,
        "prompt": prompt,
        "raw": "\n\n--- retry ---\n\n".join(raw_responses),
        "items": prompt_items,
        "feedback": validation_feedback(raw_responses[-1], prompt_items, daily_goal) if not recipes else "",
    }


def generate_freestyle_recipes(fridge_items, daily_goal=None, recipe_category=None, model=None, base_url=None, timeout=180, count=3, exclude=None):
    """Generate up to ``count`` recipe suggestions from fridge contents."""
    if not fridge_items:
        return {"recipes": [empty_fridge_recipe()], "prompt_used": "", "raw_response": ""}

    result = _run(fridge_items, daily_goal, recipe_category, model, base_url, timeout, count=count, exclude=exclude)
    if result["recipes"] is None:
        message = f"Die lokale LLM-Anbindung konnte nicht genutzt werden: {result['error']}"
        return {"recipes": [warning_recipe("LLM nicht erreichbar", message)], "prompt_used": "", "raw_response": "", "error": result["error"]}
    recipes = _target_fit_recipes(result["recipes"], daily_goal)
    if not recipes:
        if macro_target_ranges(daily_goal):
            # Makro-Kombinations-Fehler: Ziel mit diesen Zutaten nicht erreichbar
            recipes = [invalid_recipe_warning(
                "Makro-Kombination nicht erreichbar",
                "Mit dieser Makro-Kombination und deinen Zutaten ließ sich kein passendes Rezept erstellen. "
                "Passe die Makro-Kombination an, z. B. mehr Kalorien fürs Protein-Ziel oder ein niedrigeres Protein-Ziel.",
            )]
        else:
            recipes = [invalid_recipe_warning(
                "Kein valides Rezept",
                "Das Modell hat keinen brauchbaren Rezeptvorschlag erzeugt. Bitte versuche es erneut.",
            )]
    return {"recipes": recipes, "prompt_used": result["prompt"], "raw_response": result["raw"]}
