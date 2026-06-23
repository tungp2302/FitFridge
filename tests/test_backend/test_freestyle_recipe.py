"""Headline-Tests für die Freestyle-Rezept-Generierung."""
import json
from flaskr_new.asaai.freestyle_recipe import generate_freestyle_recipes

_patch_llm = lambda mp, f: mp.setattr("flaskr_new.asaai.freestyle_recipe.generate_from_ollama", f)
_first = lambda r: r["recipes"][0]
make_array = lambda *r: "[" + ",".join(r) + "]"
_item = lambda name, amount, kcal, p, f, c: {"name": name, "amount": amount, "kcal_per_100g": kcal, "protein_per_100g": p, "fat_per_100g": f, "carbs_per_100g": c}

def make_recipe(title, items, instructions=("Schritt eins.", "Schritt zwei.", "Schritt drei.")):
    return json.dumps({
        "title": title, "why_this_works": "Passt.",
        "ingredients": [f"{i['amount']}g {i['name']}" for i in items],
        "fridge_ingredients": [{"id": i["id"], "amount_g": i["amount"], "label": f"{i['amount']}g {i['name']}"} for i in items],
        "instructions": list(instructions), "estimated_macros": {"kcal": 999, "protein": 999, "fat": 999, "carbs": 999},
        "used_fridge_item_ids": [i["id"] for i in items], "pantry_assumptions": [],
    })

FRIDGE = [_item("Huhn", 300, 165, 31, 3.6, 0), _item("Reis", 500, 351, 7.3, 1.3, 77), _item("Brokkoli", 300, 34, 2.8, 0.4, 7)]

def test_valid_recipe_is_returned_and_macros_computed_from_amounts(monkeypatch):
    _patch_llm(monkeypatch, lambda **kw: make_recipe("Huhn-Reis-Pfanne", [
        {"id": 1, "name": "Huhn", "amount": 180},
        {"id": 2, "name": "Reis", "amount": 130},
        {"id": 3, "name": "Brokkoli", "amount": 100},
    ]))
    recipe = _first(generate_freestyle_recipes(FRIDGE, recipe_category="hauptspeise", count=1))
    assert recipe["title"] == "Huhn-Reis-Pfanne"
    assert recipe["used_fridge_items"] == ["Huhn", "Reis", "Brokkoli"]
    assert recipe["macro_source"] == "computed_from_fridge_amounts"
    assert recipe["estimated_macros"]["kcal"] == 787.3
    assert recipe["estimated_macros"]["protein"] == 68.1

def test_too_small_portion_is_scaled_up_to_kcal_target(monkeypatch):
    _patch_llm(monkeypatch, lambda **kw: make_recipe("Huhn-Reis-Bowl", [
        {"id": 1, "name": "Huhn", "amount": 110},
        {"id": 2, "name": "Reis", "amount": 100},
        {"id": 3, "name": "Brokkoli", "amount": 80},
    ]))
    recipe = _first(generate_freestyle_recipes(FRIDGE, daily_goal={"protein": 60, "kcal": 800}, recipe_category="hauptspeise", count=1))
    assert "warning" not in recipe
    assert recipe["macro_source"] == "computed_from_fridge_amounts"
    assert 680 <= recipe["estimated_macros"]["kcal"] <= 840
    assert recipe["estimated_macros"]["protein"] >= 51

def test_multiple_protein_and_starch_sources_are_rejected(monkeypatch):
    fridge = [_item("Rinderhackfleisch", 400, 250, 26, 17, 0), _item("Spaghetti", 500, 350, 12, 1.5, 72),
              _item("Hähnchenbrust", 300, 165, 31, 3.6, 0), _item("Kartoffeln", 500, 77, 2, 0.1, 17)]
    _patch_llm(monkeypatch, lambda **kw: make_recipe("Rinderhack-Spaghetti mit Tomatensosse", [
        {"id": 1, "name": "Rinderhackfleisch", "amount": 140}, {"id": 2, "name": "Spaghetti", "amount": 70},
        {"id": 3, "name": "Hähnchenbrust", "amount": 70}, {"id": 4, "name": "Kartoffeln", "amount": 70},
    ]))
    recipe = _first(generate_freestyle_recipes(fridge, recipe_category="hauptspeise", count=1))
    assert recipe.get("warning") is True
    assert recipe["title"] == "Kein valides Rezept"

def test_multiple_recipe_suggestions_from_array(monkeypatch):
    captured = {}
    three = make_array(
        make_recipe("Rezept A", [{"id": 1, "name": "Huhn", "amount": 150}]),
        make_recipe("Rezept B", [{"id": 2, "name": "Reis", "amount": 120}]),
        make_recipe("Rezept C", [{"id": 3, "name": "Brokkoli", "amount": 100}]),
    )
    _patch_llm(monkeypatch, lambda **kw: (captured.update(kw) or three))
    result = generate_freestyle_recipes(FRIDGE, count=3)
    assert [r["title"] for r in result["recipes"]] == ["Rezept A", "Rezept B", "Rezept C"]
    assert captured["temperature"] == 0.7
    assert "3" in captured["prompt"] and "Array" in captured["prompt"]

def test_partial_response_is_topped_up_with_retry(monkeypatch):
    responses = iter([
        make_array(make_recipe("Rezept A", [{"id": 1, "name": "Huhn", "amount": 150}])),
        make_array(make_recipe("Rezept B", [{"id": 2, "name": "Reis", "amount": 120}])),
    ])
    prompts = []
    _patch_llm(monkeypatch, lambda **kw: (prompts.append(kw["prompt"]) or next(responses)))
    result = generate_freestyle_recipes(FRIDGE, count=2)
    assert [r["title"] for r in result["recipes"]] == ["Rezept A", "Rezept B"]
    assert "Rezept A" in prompts[1]
    assert "--- retry ---" in result["raw_response"]

def test_empty_fridge_returns_hint():
    assert _first(generate_freestyle_recipes([], count=1))["title"] == "Keine Zutaten verfügbar"

def test_llm_unreachable_returns_warning(monkeypatch):
    def boom(**kw): raise RuntimeError("Ollama is not running")
    _patch_llm(monkeypatch, boom)
    result = generate_freestyle_recipes(FRIDGE, count=1)
    assert _first(result)["warning"] is True
    assert _first(result)["title"] == "LLM nicht erreichbar"
    assert "Ollama is not running" in result["error"]

def test_unusable_response_returns_warning(monkeypatch):
    _patch_llm(monkeypatch, lambda **kw: "")
    recipe = _first(generate_freestyle_recipes(FRIDGE, count=1))
    assert recipe["warning"] is True
    assert recipe["title"] == "Kein valides Rezept"