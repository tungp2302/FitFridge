"""Rezeptvorschlaege aus Kuehlschrank-Zutaten via Ollama."""
from .freestyle_recipe_support import (
    empty_fridge_recipe,
    has_term,
    invalid_recipe_warning,
    is_savory_category,
    is_sweet_category,
    is_supplement,
    MEAT_FISH,
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
    ranges = macro_target_ranges(daily_goal)
    range_parts = []
    for key in ("kcal", "protein", "fat", "carbs"):
        if key not in ranges:
            continue
        low, high = ranges[key]
        if high is None:
            range_parts.append(f"{key}>={low}")
        else:
            range_parts.append(f"{key}={low}-{high}")
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
    for item in numbered_items(fridge_items):
        name = item["name"]
        protein = safe_float(item.get("protein_per_100g")) or 0.0
        carbs = safe_float(item.get("carbs_per_100g")) or 0.0
        fat = safe_float(item.get("fat_per_100g")) or 0.0
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
        parts.append("fuer Fruehstueck, Nachspeise oder Snack KEIN Fleisch und keinen Fisch; Protein vor allem ueber magere, kcal-arme Quellen wie Joghurt/Quark (150-300g), Eier und Haferflocken (40-70g); fettreiche Zutaten wie Nuesse, Oel, Nutella nur sehr sparsam, sonst wird das kcal-Ziel gesprengt bevor das Protein-Ziel erreicht ist")
    protein_target = safe_float((daily_goal or {}).get("protein")) or 0.0
    if protein_target >= 50 and not sweet:
        parts.append("bei Protein-Ziel ab 50g ist 150g Hauptprotein meist zu wenig; fuer Rumpsteak, Haehnchen oder Hack eher ca. 200g verwenden")
    if protein_items and not sweet:
        parts.append(f"Protein eher ueber {names(protein_items)} erreichen, meist 180-260g")
    if starch_items:
        parts.append(f"fuer kcal/carbs eher {names(starch_items)} nutzen, bei Reis/Nudeln meist 100-130g trocken; nicht Kartoffeln oder Gemuese allein")
    if fat_items:
        parts.append(f"Fett bei Bedarf ueber 10-20g Oel und passende Fettquellen wie {names(fat_items)} erhoehen")
    else:
        parts.append("Fett bei Bedarf ueber 10-20g Oel erhoehen")
    return f" Makro-Strategie fuer diese Zutaten: {'; '.join(parts)}." if parts else ""


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

    f"Kuehlschrank-Zutaten, nur diese IDs erlaubt: {fridge_list}. "
    "Zusaetzlich erlaubt sind nur Wasser, Oel, Salz, Zucker, Süßungsmittel, Pfeffer, Gewuerze und Saucen wie Ketchup, Mayonnaise und Senf. "
    "Keine anderen Lebensmittel verwenden. "
    "Pantry-Zutaten nur auffuehren, wenn sie wirklich verwendet werden; nicht die erlaubte Pantry-Liste als Zutaten kopieren. "

    "REZEPTLOGIK: "
    "Waehle zuerst ein real existierendes, kulinarisch plausibles Gericht, das eine Person freiwillig essen wuerde. "
    "Geschmack, Textur und Kuechenlogik haben Vorrang vor kuenstlichen Makro-Konstruktionen. "
    "Vermeide kuenstliche Fitness-Rezepte, fragwuerdige Zutatenkombinationen und reine Makro-Konstruktionen. "
    "Verwende nur Zutaten, die sinnvoll zum gewaehlten Gericht beitragen. "
    "Verwende weder unnoetig viele noch unnoetig wenige Zutaten. "
    "Wenn Zielwerte angegeben sind, muss die berechnete Summe aus amount_g innerhalb der erlaubten Bereiche liegen. "
    "Kalorien duerfen das Ziel um hoechstens 5% ueberschreiten. "
    "Protein darf ueber dem Zielwert liegen, aber nicht deutlich darunter. "
    "Fett und Kohlenhydrate muessen innerhalb der angegebenen Toleranzen bleiben. "

    "GERICHTSART: "
    "Fuer Hauptspeise oder Abendessen bevorzuge herzhafte Gerichte. "
    "Diese sollten typischerweise Protein, Staerke und/oder Gemuese enthalten, sofern passende Zutaten vorhanden sind. "
    "Waehle genau EINE Hauptproteinquelle und genau EINE Haupt-Staerkebeilage pro Gericht. "
    "Kombiniere niemals mehrere Fleisch- oder Fischsorten (z.B. nicht Rind und Haehnchen zusammen) "
    "und niemals mehrere Staerkebeilagen (z.B. nicht Spaghetti und Kartoffeln, nicht Reis und Nudeln zusammen). "
    "Nutze nicht alle vorhandenen Zutaten, nur weil sie da sind; lass ueberzaehlige Protein- oder Staerkequellen weg. "
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
    "Typische Mengen sind 50-160g trockenes Getreide, Reis, Nudeln oder Mehl, 100-300g Kartoffeln oder Gemuese, "
    "120-300g Proteinquelle, ca. 30g Proteinpulver und 50-100g Ei. "
    "Kaese, Oliven und sehr fettreiche Toppings meist 15-50g verwenden; Oel meist 5-20g. "
    "Salz, Pfeffer und Gewuerze nur ohne Menge oder mit 1-2g angeben, niemals 10g. "
    "Broetchen, Buns, Wraps und Brot immer als realistische Grammmenge angeben, nicht als 1g. "
    "Reis und Nudeln als trockene Grammmenge passend zu den /100g-Naehrwerten angeben, nicht als gekocht deklarieren. "
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
    "Rechne vor der Ausgabe mit den angegebenen /100g-Werten nach. "
    "Wenn kcal oder Protein zu niedrig sind, erhoehe zuerst eine passende Proteinquelle und eine passende Staerke. "
    "Wenn Fett zu niedrig ist, erhoehe Oel, Oliven, Kaese, Hackfleisch oder andere passende Fettquellen. "
    "Prioritaet: kcal hoechstens 5% ueber Ziel, protein mindestens nahe Ziel, fat und carbs innerhalb Toleranz. "
    "estimated_macros nur plausibel fuellen und niemals schoenrechnen. "

    "AUSGABE: "
    "why_this_works soll auf Deutsch in genau einem kurzen Satz erklaeren, warum Geschmack, Textur und Zubereitung zusammenpassen. "
    "Kein Marketingtext und keine reine Makro-Begruendung. "
    "Schreibe so viele kurze instructions, wie das Gericht wirklich braucht: einfache Gerichte 3-4 Schritte, "
    "ein durchschnittliches Hauptgericht 5-8 klare Schritte. "
    "Jeder Schritt ist genau eine konkrete Koch-Handlung in der richtigen Reihenfolge "
    "(z.B. vorbereiten/schneiden, anbraten, koechen lassen, wuerzen, anrichten); "
    "fasse nicht mehrere Arbeitsschritte in einem Satz zusammen und erfinde keine Fuellschritte. "
    "Instructions duerfen keine Makroberechnung, Kalorienzeile, Anpassungsnotiz oder Erklaerung enthalten. "
    "Jedes Objekt muss vollstaendig valides JSON sein. "
    "Keine Kommentare. "
    "Keine Markdown-Formatierung. "
    "Keine Erklaerungen vor oder nach dem JSON. "

    f"Antworte ausschliesslich mit einem JSON-Array aus genau {count} Objekten dieser Form: [{_SCHEMA}]"
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

    # fehlt was, nachfordern und gefundene Titel ausschliessen
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
        detail = result.get("feedback") or "Die Antwort war leer, kein valides JSON oder hat die Rezept-/Makro-Regeln nicht eingehalten."
        recipes = [invalid_recipe_warning(
            "Kein valides Rezept",
            "Das Modell hat keinen Rezeptvorschlag erzeugt, dessen berechnete Naehrwerte und Zutaten die Regeln einhalten. "
            f"{detail}",
        )]
    return {"recipes": recipes, "prompt_used": result["prompt"], "raw_response": result["raw"]}
