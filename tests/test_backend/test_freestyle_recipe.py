"""Headline-Tests fuer die Freestyle-Rezept-Generierung.

Bewusst knapp: deckt die Kernfluesse ab statt jeder einzelnen
Validierungsregel:
- ein valides Rezept wird zurueckgegeben und die Makros aus den
  amount_g-Mengen berechnet (nicht den LLM-Schaetzwerten vertraut)
- eine zu kleine Portion wird auf das kcal-Ziel hochskaliert
- eine kulinarisch inkohaerente Kombination wird abgelehnt
- mehrere Vorschlaege werden aus einem JSON-Array gelesen und bei
  Teilantworten nachgefordert
- leerer Kuehlschrank, nicht erreichbares LLM und unbrauchbare Antwort
  liefern klare Hinweis-/Warn-Rezepte
"""
import json

from flaskr_new.asaai.freestyle_recipe import generate_freestyle_recipes


def _patch_llm(monkeypatch, func):
    monkeypatch.setattr("flaskr_new.asaai.freestyle_recipe.generate_from_ollama", func)


def _first(result):
    return result["recipes"][0]


def make_recipe(
    title,
    items,
    why="Passt geschmacklich und von der Zubereitung gut zusammen.",
    instructions=("Schritt eins.", "Schritt zwei.", "Schritt drei."),
):
    """Baut eine LLM-JSON-Antwort aus (id, name, amount)-Zutaten.

    ``estimated_macros`` wird absichtlich auf 999 gesetzt, damit Tests
    pruefen koennen, dass FitFridge die Makros selbst aus amount_g berechnet.
    """
    recipe = {
        "title": title,
        "why_this_works": why,
        "ingredients": [f"{it['amount']}g {it['name']}" for it in items],
        "fridge_ingredients": [
            {"id": it["id"], "amount_g": it["amount"], "label": f"{it['amount']}g {it['name']}"}
            for it in items
        ],
        "instructions": list(instructions),
        "estimated_macros": {"kcal": 999, "protein": 999, "fat": 999, "carbs": 999},
        "used_fridge_item_ids": [it["id"] for it in items],
        "pantry_assumptions": [],
    }
    return json.dumps(recipe)


def make_array(*recipes):
    return "[" + ",".join(recipes) + "]"


# Reihenfolge bestimmt die id (numbered_items zaehlt ab 1): Huhn=1, Reis=2, Brokkoli=3.
FRIDGE = [
    {"name": "Huhn", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
    {"name": "Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
    {"name": "Brokkoli", "amount": 300, "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7},
]


def test_valid_recipe_is_returned_and_macros_computed_from_amounts(monkeypatch):
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return make_recipe(
            "Huhn-Reis-Pfanne",
            [
                {"id": 1, "name": "Huhn", "amount": 180},
                {"id": 2, "name": "Reis", "amount": 130},
                {"id": 3, "name": "Brokkoli", "amount": 100},
            ],
        )

    _patch_llm(monkeypatch, fake)
    result = generate_freestyle_recipes(FRIDGE, recipe_category="hauptspeise", count=1)
    recipe = _first(result)

    assert recipe["title"] == "Huhn-Reis-Pfanne"
    assert recipe["used_fridge_items"] == ["Huhn", "Reis", "Brokkoli"]
    # Makros stammen aus amount_g, nicht aus den 999-Werten des Modells.
    assert recipe["macro_source"] == "computed_from_fridge_amounts"
    assert recipe["estimated_macros"]["kcal"] == 787.3
    assert recipe["estimated_macros"]["protein"] == 68.1
    assert captured["format_json"] is True


def test_too_small_portion_is_scaled_up_to_kcal_target(monkeypatch):
    too_low = make_recipe(
        "Huhn-Reis-Bowl",
        [
            {"id": 1, "name": "Huhn", "amount": 110},
            {"id": 2, "name": "Reis", "amount": 100},
            {"id": 3, "name": "Brokkoli", "amount": 80},
        ],
    )
    _patch_llm(monkeypatch, lambda **kwargs: too_low)
    result = generate_freestyle_recipes(
        FRIDGE,
        daily_goal={"protein": 60, "kcal": 800},
        recipe_category="hauptspeise",
        count=1,
    )
    recipe = _first(result)

    assert "warning" not in recipe
    assert recipe["macro_source"] == "computed_from_fridge_amounts"
    assert 680 <= recipe["estimated_macros"]["kcal"] <= 840
    assert recipe["estimated_macros"]["protein"] >= 51


def test_incoherent_combination_is_rejected(monkeypatch):
    # Whey in einem herzhaften Huhn-Reis-Gericht ist kulinarisch inkohaerent.
    fridge = [
        {"name": "Haehnchenbrust", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
        {"name": "ESN Whey Protein", "amount": 300, "kcal_per_100g": 375, "protein_per_100g": 73, "fat_per_100g": 5.2, "carbs_per_100g": 9.2},
        {"name": "Jasmin Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
    ]
    response = make_recipe(
        "Haehnchen-Reis-Pfanne",
        [
            {"id": 1, "name": "Haehnchenbrust", "amount": 150},
            {"id": 2, "name": "Whey", "amount": 30},
            {"id": 3, "name": "Jasmin Reis", "amount": 100},
        ],
    )
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipes(fridge, recipe_category="hauptspeise", count=1)
    recipe = _first(result)

    assert recipe.get("warning") is True
    assert recipe["title"] == "Kein valides Rezept"


def test_multiple_recipe_suggestions_from_array(monkeypatch):
    captured = {}
    three = make_array(
        make_recipe("Rezept A", [{"id": 1, "name": "Huhn", "amount": 150}]),
        make_recipe("Rezept B", [{"id": 2, "name": "Reis", "amount": 120}]),
        make_recipe("Rezept C", [{"id": 3, "name": "Brokkoli", "amount": 100}]),
    )

    def fake(**kwargs):
        captured.update(kwargs)
        return three

    _patch_llm(monkeypatch, fake)
    result = generate_freestyle_recipes(FRIDGE, count=3)

    assert [r["title"] for r in result["recipes"]] == ["Rezept A", "Rezept B", "Rezept C"]
    assert captured["temperature"] == 0.7
    assert "3" in captured["prompt"] and "Array" in captured["prompt"]


def test_partial_response_is_topped_up_with_retry(monkeypatch):
    first = make_array(make_recipe("Rezept A", [{"id": 1, "name": "Huhn", "amount": 150}]))
    second = make_array(make_recipe("Rezept B", [{"id": 2, "name": "Reis", "amount": 120}]))
    responses = iter([first, second])
    prompts = []

    def fake(**kwargs):
        prompts.append(kwargs["prompt"])
        return next(responses)

    _patch_llm(monkeypatch, fake)
    result = generate_freestyle_recipes(FRIDGE, count=2)

    assert [r["title"] for r in result["recipes"]] == ["Rezept A", "Rezept B"]
    # Die Nachforderung schliesst das bereits gefundene Gericht aus.
    assert "Rezept A" in prompts[1]
    assert "--- retry ---" in result["raw_response"]


def test_empty_fridge_returns_hint(monkeypatch):
    _patch_llm(monkeypatch, lambda **kwargs: make_recipe("ignoriert", [{"id": 1, "name": "Huhn", "amount": 100}]))
    recipe = _first(generate_freestyle_recipes([], count=1))

    assert recipe["title"] == "Keine Zutaten verfügbar"
    assert recipe["ingredients"] == []


def test_llm_unreachable_returns_warning(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Ollama is not running")

    _patch_llm(monkeypatch, boom)
    result = generate_freestyle_recipes(FRIDGE, count=1)
    recipe = _first(result)

    assert recipe["warning"] is True
    assert recipe["title"] == "LLM nicht erreichbar"
    assert "Ollama is not running" in result["error"]


def test_unusable_response_returns_warning(monkeypatch):
    _patch_llm(monkeypatch, lambda **kwargs: "")
    recipe = _first(generate_freestyle_recipes(FRIDGE, count=1))

    assert recipe["warning"] is True
    assert recipe["title"] == "Kein valides Rezept"
