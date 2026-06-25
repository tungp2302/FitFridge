"""Headline-Tests für die Freestyle-Rezept-Generierung."""
import json

import pytest

from flaskr_new import create_app, db
from flaskr_new.asaai.freestyle_recipe import generate_freestyle_recipes
from flaskr_new.asaai.freestyle_recipe_support import macros_within_targets
from flaskr_new.db import get_db


def test_tolerance_floors_enforce_low_fat_and_low_carb_targets():
    # Floors fat>=5 / carbs>=10: kleine Per-Mahlzeit-Ziele werden jetzt durchgesetzt.
    assert not macros_within_targets({"fat": 12}, {"fat": 4})    # 12g Fett für 4g-Ziel -> raus
    assert not macros_within_targets({"carbs": 33}, {"carbs": 19})  # 33g Carbs für 19g-Ziel -> raus
    assert macros_within_targets({"fat": 9}, {"fat": 4})         # 9g innerhalb des 5er-Floors -> ok
    # Wo der 0.30-Anteil > Floor ist, aendert sich nichts.
    assert macros_within_targets({"fat": 38}, {"fat": 30})       # |38-30|=8 <= 0.30*30=9 -> weiter ok

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

def test_low_carb_recipe_repaired_by_per_macro_fit(monkeypatch):
    # Modell liefert ein carb-lastiges Gericht fuer ein Low-Carb-Ziel; reines
    # kcal-Skalieren kann das nicht retten, der Pro-Makro-Fit schon.
    fridge = [_item("Huhn", 300, 165, 31, 3.6, 0), _item("Reis", 500, 360, 7, 0.9, 79),
              _item("Olivenoel", 500, 884, 0, 100, 0), _item("Brokkoli", 300, 34, 2.8, 0.4, 7)]
    _patch_llm(monkeypatch, lambda **kw: make_recipe("Haehnchen mit Reis", [
        {"id": 1, "name": "Huhn", "amount": 150}, {"id": 2, "name": "Reis", "amount": 120},
        {"id": 3, "name": "Olivenoel", "amount": 10}, {"id": 4, "name": "Brokkoli", "amount": 100},
    ]))
    goal = {"kcal": 700, "protein": 61, "carbs": 26, "fat": 39}
    recipe = _first(generate_freestyle_recipes(fridge, daily_goal=goal, recipe_category="hauptspeise", count=1))
    assert "warning" not in recipe
    assert 16 <= recipe["estimated_macros"]["carbs"] <= 36   # Carbs jetzt im Low-Carb-Band
    assert recipe["estimated_macros"]["protein"] >= 51

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


# --- Routen für gespeicherte Rezepte (/asaai/recipes/saved) ---

@pytest.fixture()
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "saved.sqlite")})
    with app.app_context():
        db.init_db()
        get_db().execute("INSERT INTO user (username, password) VALUES ('u', 'x')")
        get_db().commit()
    return app

@pytest.fixture()
def client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 1
    return c

def test_saved_requires_login(app):
    assert app.test_client().get("/asaai/recipes/saved").status_code == 401

def test_save_list_rename_delete_roundtrip(client):
    saved = client.post("/asaai/recipes/saved", json={"title": "Bowl", "estimated_macros": {"kcal": 500}})
    recipes = saved.get_json()["recipes"]
    assert saved.status_code == 200 and recipes[0]["title"] == "Bowl"
    rid = recipes[0]["id"]

    client.patch(f"/asaai/recipes/saved/{rid}", json={"title": "Neue Bowl"})
    assert client.get("/asaai/recipes/saved").get_json()["recipes"][0]["title"] == "Neue Bowl"

    assert client.delete(f"/asaai/recipes/saved/{rid}").status_code == 200
    assert client.get("/asaai/recipes/saved").get_json()["recipes"] == []

def test_save_rejects_non_object_body(client):
    assert client.post("/asaai/recipes/saved", json=["nope"]).status_code == 400

def test_rename_requires_title(client):
    rid = client.post("/asaai/recipes/saved", json={"title": "A"}).get_json()["recipes"][0]["id"]
    assert client.patch(f"/asaai/recipes/saved/{rid}", json={"title": "  "}).status_code == 400