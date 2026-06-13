"""Tests fuer die Freestyle-Rezept-Logik (ein und mehrere Rezepte)."""
from flaskr_new.asaai.freestyle_recipe import (
    build_prompt,
    generate_freestyle_recipe,
    generate_freestyle_recipes,
)
from flaskr_new.asaai.freestyle_recipe_support import computed_macros, valid_recipes


def _patch_llm(monkeypatch, func):
    monkeypatch.setattr("flaskr_new.asaai.freestyle_recipe.generate_from_ollama", func)


def _assert_invalid_warning(recipe):
    assert recipe["warning"] is True
    assert recipe["title"] == "Kein valides Rezept"
    assert recipe["ingredients"] == []
    assert recipe["instructions"] == []
    assert "fallback" not in recipe


VALID_RESPONSE = """
{
  "title": "Protein-Pfannkuchen",
  "why_this_works": "Mehl und Eier ergeben einen Teig.",
  "ingredients": ["Dinkel Mehl", "Frische Eier", "Wasser"],
  "instructions": ["Mehl und Eier verruehren.", "Teig ruhen lassen.", "Pfannkuchen ausbacken."],
  "estimated_macros": {"kcal": 500, "protein": 35, "fat": 12, "carbs": 60},
  "used_fridge_item_ids": [1, 2],
  "pantry_assumptions": ["Wasser"]
}
"""

BASIC_FRIDGE = [
    {"name": "Dinkel Mehl", "amount": 120},
    {"name": "Frische Eier", "amount": 100},
]


def test_missing_llm_returns_warning(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Ollama is not running")

    _patch_llm(monkeypatch, boom)
    result = generate_freestyle_recipe(BASIC_FRIDGE)

    recipe = result["recipe"]
    assert recipe["warning"] is True
    assert recipe["title"] == "LLM nicht erreichbar"
    assert recipe["ingredients"] == []
    assert "Ollama is not running" in result["error"]


def test_empty_response_returns_clear_warning(monkeypatch):
    _patch_llm(monkeypatch, lambda **kwargs: "")
    result = generate_freestyle_recipe(BASIC_FRIDGE)

    _assert_invalid_warning(result["recipe"])
    assert "kein valides JSON" in result["recipe"]["why_this_works"]


def test_valid_recipe_is_returned_with_json_mode(monkeypatch):
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return VALID_RESPONSE

    _patch_llm(monkeypatch, fake)
    result = generate_freestyle_recipe(BASIC_FRIDGE)

    assert result["recipe"]["title"] == "Protein-Pfannkuchen"
    assert result["recipe"]["used_fridge_items"] == ["Dinkel Mehl", "Frische Eier"]
    assert captured["format_json"] is True
    assert captured["num_predict"] == 900


def test_structured_amounts_compute_macros_instead_of_trusting_llm(monkeypatch):
    response = """
    {
      "title": "Mehl-Ei-Pfannkuchen",
      "why_this_works": "Mehl und Eier ergeben einen einfachen Teig.",
      "ingredients": ["100g Dinkel Mehl", "100g Frische Eier", "Wasser"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 100, "label": "100g Dinkel Mehl"},
        {"id": 2, "amount_g": 100, "label": "100g Frische Eier"}
      ],
      "pantry_ingredients": [{"name": "Wasser", "label": "etwas Wasser"}],
      "instructions": ["Teig verruehren.", "Kurz ruhen lassen.", "Pfannkuchen ausbacken."],
      "estimated_macros": {"kcal": 999, "protein": 999, "fat": 999, "carbs": 999},
      "used_fridge_item_ids": [1, 2],
      "pantry_assumptions": ["Wasser"]
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe([
        {"name": "Dinkel Mehl", "amount": 500, "kcal_per_100g": 344, "protein_per_100g": 10, "fat_per_100g": 1, "carbs_per_100g": 72.3},
        {"name": "Frische Eier", "amount": 6, "kcal_per_100g": 143, "protein_per_100g": 12.6, "fat_per_100g": 9.5, "carbs_per_100g": 0.7},
    ])

    recipe = result["recipe"]
    assert recipe["macro_source"] == "computed_from_fridge_amounts"
    assert recipe["estimated_macros"] == {"kcal": 487.0, "protein": 22.6, "fat": 10.5, "carbs": 73.0}
    assert recipe["ingredients"] == ["100g Dinkel Mehl", "100g Frische Eier", "etwas Wasser"]


def test_pantry_olive_oil_counts_toward_computed_macros():
    recipe = {
        "fridge_ingredients": [{"id": 1, "amount_g": 100, "label": "100g Huhn"}],
        "pantry_ingredients": [{"name": "Olivenöl", "amount_g": 10, "label": "10g Olivenöl"}],
    }

    macros = computed_macros(
        recipe,
        [{"name": "Huhn", "kcal_per_100g": 100, "protein_per_100g": 20, "fat_per_100g": 2, "carbs_per_100g": 0}],
    )

    assert macros == {"kcal": 190.0, "protein": 20.0, "fat": 12.0, "carbs": 0.0}


def test_excessive_salt_or_spice_amounts_are_rejected():
    response = """
    {
      "title": "Huhn-Reis-Pfanne",
      "why_this_works": "Huhn und Reis passen als einfache Hauptspeise zusammen.",
      "ingredients": ["200g Huhn", "100g Reis", "10g Salz"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 200, "label": "200g Huhn"},
        {"id": 2, "amount_g": 100, "label": "100g Reis"}
      ],
      "pantry_ingredients": [{"name": "Salz", "amount_g": 10, "label": "10g Salz"}],
      "instructions": ["Reis garen.", "Huhn braten.", "Zusammen servieren."],
      "used_fridge_item_ids": [1, 2],
      "pantry_assumptions": ["Salz"]
    }
    """

    recipes = valid_recipes(
        response,
        [
            {"name": "Huhn", "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
            {"name": "Reis", "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
        ],
        count=1,
        recipe_category="hauptspeise",
    )

    assert recipes == []


def test_minor_kcal_overage_can_be_repaired_by_reducing_oil():
    response = """
    {
      "title": "Rumpsteak-Reis-Bowl",
      "why_this_works": "Steak, Reis und Brokkoli ergeben eine herzhafte Bowl.",
      "ingredients": ["200g Rumpsteak", "100g Reis", "150g Brokkoli", "10g Oel"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 200, "label": "200g Rumpsteak"},
        {"id": 2, "amount_g": 100, "label": "100g Reis"},
        {"id": 3, "amount_g": 150, "label": "150g Brokkoli"}
      ],
      "pantry_ingredients": [{"name": "Oel", "amount_g": 10, "label": "10g Oel"}],
      "instructions": ["Reis garen.", "Steak braten.", "Mit Brokkoli servieren."],
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": ["Oel"]
    }
    """

    recipes = valid_recipes(
        response,
        [
            {"name": "Rumpsteak", "kcal_per_100g": 120, "protein_per_100g": 21, "fat_per_100g": 4, "carbs_per_100g": 0},
            {"name": "Reis", "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
            {"name": "Brokkoli", "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7},
        ],
        count=1,
        recipe_category="hauptspeise",
        daily_goal={"kcal": 725, "protein": 50, "fat": 18, "carbs": 80},
    )

    assert recipes[0]["estimated_macros"]["kcal"] <= 725
    assert recipes[0]["estimated_macros"]["fat"] >= 10


def test_cleaned_recipe_keeps_only_three_instructions(monkeypatch):
    response = """
    {
      "title": "Huhn-Reis-Pfanne",
      "why_this_works": "Huhn und Reis passen als einfache Hauptspeise zusammen.",
      "ingredients": ["200g Huhn", "100g Reis"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 200, "label": "200g Huhn"},
        {"id": 2, "amount_g": 100, "label": "100g Reis"}
      ],
      "instructions": ["Reis garen.", "Huhn braten.", "Gemuese garen.", "Alles mischen.", "Servieren."],
      "used_fridge_item_ids": [1, 2],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe([
        {"name": "Huhn", "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
        {"name": "Reis", "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
    ])

    assert result["recipe"]["instructions"] == ["Reis garen.", "Huhn braten.", "Gemuese garen."]


def test_macro_targets_are_not_prompted_as_optional():
    prompt = build_prompt(BASIC_FRIDGE, daily_goal={"kcal": 800, "protein": 60}, recipe_category="hauptspeise")

    assert "harte Validierungsregeln" in prompt
    assert "Zielwerte duerfen verfehlt werden" not in prompt


def test_macro_strategy_hint_prefers_dense_starches_for_targets():
    prompt = build_prompt(
        [
            {"name": "Kartoffeln", "kcal_per_100g": 71, "protein_per_100g": 2, "fat_per_100g": 0.1, "carbs_per_100g": 15},
            {"name": "Jasmin Reis", "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
            {"name": "Rumpsteak", "kcal_per_100g": 120, "protein_per_100g": 21, "fat_per_100g": 4, "carbs_per_100g": 0},
            {"name": "Cheddar", "kcal_per_100g": 416, "protein_per_100g": 25, "fat_per_100g": 35, "carbs_per_100g": 0.5},
        ],
        daily_goal={"kcal": 800, "protein": 60, "carbs": 90, "fat": 25},
        recipe_category="hauptspeise",
    )

    assert "Makro-Strategie" in prompt
    assert "150g Hauptprotein meist zu wenig" in prompt
    assert "Jasmin Reis" in prompt
    assert "180-260g" in prompt
    assert "100-130g trocken" in prompt
    assert "nicht Kartoffeln oder Gemuese allein" in prompt


def test_legacy_used_ids_must_match_ingredient_text(monkeypatch):
    response = """
    {
      "title": "Haferbrei mit Banane",
      "why_this_works": "Hafer und Banane passen zusammen.",
      "ingredients": ["100g Haferflocken", "1 Banane", "250ml Milch"],
      "instructions": ["Kochen.", "Ruehren.", "Servieren."],
      "estimated_macros": {"kcal": 780, "protein": 62, "fat": 24, "carbs": 92},
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe([
        {"name": "Milch 1,5%", "amount": 1000},
        {"name": "Frischkäse", "amount": 100},
        {"name": "Banane", "amount": 200},
        {"name": "Haferflocken", "amount": 500},
    ])

    _assert_invalid_warning(result["recipe"])


def test_savory_title_with_sweet_structured_body_is_rejected(monkeypatch):
    response = """
    {
      "title": "Scharfe Spinat-Reis-Pfanne mit Ei",
      "why_this_works": "Ein suesses Fruehstueck mit Haferflocken, Whey und Banane.",
      "ingredients": ["60g Haferflocken", "30g Whey", "150ml Milch", "1 Banane"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 30, "label": "30g Whey"},
        {"id": 2, "amount_g": 60, "label": "60g Haferflocken"},
        {"id": 3, "amount_g": 120, "label": "1 Banane"},
        {"id": 4, "amount_g": 50, "label": "50g Frischkaese"}
      ],
      "instructions": ["Mischen.", "Erhitzen.", "Servieren."],
      "estimated_macros": {"kcal": 810, "protein": 62, "fat": 18, "carbs": 115},
      "used_fridge_item_ids": [1, 2, 3, 4],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe(
        [
            {"name": "ESN Whey Protein Cinnamon", "amount": 300, "kcal_per_100g": 375, "protein_per_100g": 73, "fat_per_100g": 5.2, "carbs_per_100g": 9.2},
            {"name": "Haferflocken", "amount": 500, "kcal_per_100g": 361, "protein_per_100g": 14, "fat_per_100g": 6.7, "carbs_per_100g": 56},
            {"name": "Banane", "amount": 200, "kcal_per_100g": 89, "protein_per_100g": 1.1, "fat_per_100g": 0.3, "carbs_per_100g": 23},
            {"name": "Frischkaese", "amount": 100, "kcal_per_100g": 252, "protein_per_100g": 4.5, "fat_per_100g": 24.5, "carbs_per_100g": 3},
            {"name": "Spinat", "amount": 300, "kcal_per_100g": 22, "protein_per_100g": 3.3, "fat_per_100g": 0.4, "carbs_per_100g": 0.3},
            {"name": "Jasmin Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
        ],
        daily_goal={"protein": 60, "kcal": 800},
        recipe_category="hauptspeise",
    )

    assert result["recipe"]["warning"] is True
    assert result["recipe"]["title"] == "Kein valides Rezept"


def test_supplement_name_in_title_is_rejected_even_when_recipe_matches(monkeypatch):
    response = """
    {
      "title": "Kraeuter-Hafer-Whey-Pfannkuchen mit Banane",
      "why_this_works": "Hafer, Banane und Ei ergeben einen weichen Teig, das Proteinpulver ergaenzt die Struktur.",
      "ingredients": ["100g Haferflocken", "30g Whey", "1 Ei", "150ml Milch", "1 Banane"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 100, "label": "100g Haferflocken"},
        {"id": 2, "amount_g": 30, "label": "30g Whey"},
        {"id": 3, "amount_g": 100, "label": "1 Ei"},
        {"id": 4, "amount_g": 150, "label": "150ml Milch"},
        {"id": 5, "amount_g": 120, "label": "1 Banane"}
      ],
      "instructions": ["Teig ruehren.", "Pfannkuchen ausbacken.", "Warm servieren."],
      "estimated_macros": {"kcal": 780, "protein": 62, "fat": 28, "carbs": 85},
      "used_fridge_item_ids": [1, 2, 3, 4, 5],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe(
        [
            {"name": "Haferflocken", "amount": 500, "kcal_per_100g": 361, "protein_per_100g": 14, "fat_per_100g": 6.7, "carbs_per_100g": 56},
            {"name": "ESN Whey Protein Cinnamon", "amount": 300, "kcal_per_100g": 375, "protein_per_100g": 73, "fat_per_100g": 5.2, "carbs_per_100g": 9.2},
            {"name": "Eier", "amount": 300, "kcal_per_100g": 143, "protein_per_100g": 12.6, "fat_per_100g": 9.5, "carbs_per_100g": 0.7},
            {"name": "Milch 1,5%", "amount": 1000, "kcal_per_100g": 47, "protein_per_100g": 3.4, "fat_per_100g": 1.5, "carbs_per_100g": 4.9},
            {"name": "Banane", "amount": 200, "kcal_per_100g": 89, "protein_per_100g": 1.1, "fat_per_100g": 0.3, "carbs_per_100g": 23},
        ],
        recipe_category="fruehstueck",
    )

    _assert_invalid_warning(result["recipe"])


def test_whey_oat_pancakes_with_carrot_are_rejected(monkeypatch):
    response = """
    {
      "title": "Protein-Pfannkuchen",
      "why_this_works": "Haferflocken, Whey, Ei und Karotte ergeben ein sättigendes Frühstück.",
      "ingredients": ["150g Haferflocken", "30g Whey", "2 Eier", "100ml Milch", "50g Karotte"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 150, "label": "150g Haferflocken"},
        {"id": 2, "amount_g": 30, "label": "30g Whey"},
        {"id": 3, "amount_g": 100, "label": "2 Eier"},
        {"id": 4, "amount_g": 100, "label": "100ml Milch"},
        {"id": 5, "amount_g": 50, "label": "50g Karotte"}
      ],
      "instructions": ["Teig ruehren.", "Pfannkuchen ausbacken.", "Warm servieren."],
      "estimated_macros": {"kcal": 785, "protein": 62, "fat": 18, "carbs": 95},
      "used_fridge_item_ids": [1, 2, 3, 4, 5],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe(
        [
            {"name": "Kölln Haferflocken Blütenzarte Haferflocken", "amount": 500, "kcal_per_100g": 361, "protein_per_100g": 14, "fat_per_100g": 6.7, "carbs_per_100g": 56},
            {"name": "ESN whey protein connamon", "amount": 300, "kcal_per_100g": 375, "protein_per_100g": 73, "fat_per_100g": 5.2, "carbs_per_100g": 9.2},
            {"name": "Eier", "amount": 300, "kcal_per_100g": 143, "protein_per_100g": 12.6, "fat_per_100g": 9.5, "carbs_per_100g": 0.7},
            {"name": "Milch 1,5%", "amount": 1000, "kcal_per_100g": 47, "protein_per_100g": 3.4, "fat_per_100g": 1.5, "carbs_per_100g": 4.9},
            {"name": "Karotte", "amount": 200, "kcal_per_100g": 35, "protein_per_100g": 0.9, "fat_per_100g": 0.2, "carbs_per_100g": 8},
        ],
        recipe_category="fruehstueck",
    )

    _assert_invalid_warning(result["recipe"])


def test_whey_in_savory_chicken_rice_dish_is_rejected(monkeypatch):
    response = """
    {
      "title": "Haehnchen-Reis-Pfanne",
      "why_this_works": "Haehnchen, Reis und Karotte werden mit Whey zu einer proteinreichen Hauptspeise.",
      "ingredients": ["150g Haehnchenbrust", "30g Whey", "80g Jasmin Reis", "80g Karotte"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 150, "label": "150g Haehnchenbrust"},
        {"id": 2, "amount_g": 30, "label": "30g Whey"},
        {"id": 3, "amount_g": 80, "label": "80g Jasmin Reis"},
        {"id": 4, "amount_g": 80, "label": "80g Karotte"}
      ],
      "instructions": ["Reis kochen.", "Haehnchen anbraten.", "Alles mit Whey mischen."],
      "estimated_macros": {"kcal": 650, "protein": 62, "fat": 12, "carbs": 85},
      "used_fridge_item_ids": [1, 2, 3, 4],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe(
        [
            {"name": "Haehnchenbrust", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
            {"name": "ESN whey protein connamon", "amount": 300, "kcal_per_100g": 375, "protein_per_100g": 73, "fat_per_100g": 5.2, "carbs_per_100g": 9.2},
            {"name": "Jasmin Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
            {"name": "Karotte", "amount": 200, "kcal_per_100g": 35, "protein_per_100g": 0.9, "fat_per_100g": 0.2, "carbs_per_100g": 8},
        ],
        daily_goal={"kcal": 650, "protein": 62, "fat": 12, "carbs": 85},
        recipe_category="hauptspeise",
    )

    _assert_invalid_warning(result["recipe"])
    assert result["recipe"]["title"] != "Haehnchen-Reis-Pfanne"


def test_computed_macros_too_far_from_target_are_retried(monkeypatch):
    responses = iter([
        """
        {
          "title": "Kleine Reis-Gemuese-Pfanne",
          "why_this_works": "Reis und Gemuese passen zusammen.",
          "ingredients": ["100g Reis", "100g Brokkoli"],
          "fridge_ingredients": [
            {"id": 1, "amount_g": 100, "label": "100g Reis"},
            {"id": 2, "amount_g": 100, "label": "100g Brokkoli"}
          ],
          "instructions": ["Reis garen.", "Brokkoli braten.", "Zusammen servieren."],
          "estimated_macros": {"kcal": 800, "protein": 60, "fat": 25, "carbs": 90},
          "used_fridge_item_ids": [1, 2],
          "pantry_assumptions": []
        }
        """,
        """
        {
          "title": "Huhn-Reis-Brokkoli-Pfanne",
          "why_this_works": "Huhn, Reis und Brokkoli ergeben eine stimmige Hauptspeise.",
          "ingredients": ["180g Huhn", "130g Reis", "100g Brokkoli"],
          "fridge_ingredients": [
            {"id": 3, "amount_g": 180, "label": "180g Huhn"},
            {"id": 1, "amount_g": 130, "label": "130g Reis"},
            {"id": 2, "amount_g": 100, "label": "100g Brokkoli"}
          ],
          "instructions": ["Reis garen.", "Huhn und Brokkoli braten.", "Alles zusammen servieren."],
          "estimated_macros": {"kcal": 800, "protein": 60, "fat": 25, "carbs": 90},
          "used_fridge_item_ids": [3, 1, 2],
          "pantry_assumptions": []
        }
        """,
    ])
    _patch_llm(monkeypatch, lambda **kwargs: next(responses))
    result = generate_freestyle_recipe(
        [
            {"name": "Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
            {"name": "Brokkoli", "amount": 300, "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7},
            {"name": "Huhn", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
        ],
        daily_goal={"protein": 60, "kcal": 800},
        recipe_category="hauptspeise",
    )

    assert result["recipe"]["title"] == "Huhn-Reis-Brokkoli-Pfanne"
    assert result["recipe"]["macro_source"] == "computed_from_fridge_amounts"
    assert "--- retry ---" in result["raw_response"]


def test_protein_may_exceed_target(monkeypatch):
    response = """
    {
      "title": "Huhn-Brokkoli-Teller",
      "why_this_works": "Huhn und Brokkoli ergeben eine einfache Hauptspeise.",
      "ingredients": ["170g Huhn", "100g Brokkoli"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 170, "label": "170g Huhn"},
        {"id": 2, "amount_g": 100, "label": "100g Brokkoli"}
      ],
      "instructions": ["Huhn braten.", "Brokkoli garen.", "Zusammen servieren."],
      "estimated_macros": {"kcal": 400, "protein": 30, "fat": 8, "carbs": 7},
      "used_fridge_item_ids": [1, 2],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe(
        [
            {"name": "Huhn", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
            {"name": "Brokkoli", "amount": 300, "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7},
        ],
        daily_goal={"protein": 30, "kcal": 400},
        recipe_category="hauptspeise",
    )

    assert result["recipe"]["title"] == "Huhn-Brokkoli-Teller"
    assert result["recipe"]["estimated_macros"]["protein"] > 30
    assert result["recipe"]["estimated_macros"]["kcal"] <= 400


def test_kcal_must_not_exceed_target(monkeypatch):
    over_target = """
    {
      "title": "Huhn-Reis-Teller",
      "why_this_works": "Huhn und Reis ergeben eine einfache Hauptspeise.",
      "ingredients": ["200g Huhn", "20g Reis"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 200, "label": "200g Huhn"},
        {"id": 2, "amount_g": 20, "label": "20g Reis"}
      ],
      "instructions": ["Reis garen.", "Huhn braten.", "Zusammen servieren."],
      "estimated_macros": {"kcal": 400, "protein": 30, "fat": 8, "carbs": 15},
      "used_fridge_item_ids": [1, 2],
      "pantry_assumptions": []
    }
    """
    responses = iter([over_target, over_target])
    _patch_llm(monkeypatch, lambda **kwargs: next(responses))
    result = generate_freestyle_recipe(
        [
            {"name": "Huhn", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
            {"name": "Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
        ],
        daily_goal={"protein": 30, "kcal": 400},
        recipe_category="hauptspeise",
    )

    _assert_invalid_warning(result["recipe"])
    assert result["recipe"]["title"] != "Huhn-Reis-Teller"


def test_targeted_recipe_requires_computed_macros(monkeypatch):
    no_amounts = """
    {
      "title": "Huhn-Reis-Teller",
      "why_this_works": "Huhn und Reis ergeben eine einfache Hauptspeise.",
      "ingredients": ["Huhn", "Reis"],
      "instructions": ["Reis garen.", "Huhn braten.", "Zusammen servieren."],
      "estimated_macros": {"kcal": 390, "protein": 45, "fat": 7, "carbs": 20},
      "used_fridge_item_ids": [1, 2],
      "pantry_assumptions": []
    }
    """
    responses = iter([no_amounts, no_amounts])
    _patch_llm(monkeypatch, lambda **kwargs: next(responses))
    result = generate_freestyle_recipe(
        [
            {"name": "Huhn", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
            {"name": "Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
        ],
        daily_goal={"protein": 30, "kcal": 400},
        recipe_category="hauptspeise",
    )

    _assert_invalid_warning(result["recipe"])
    assert result["recipe"]["title"] != "Huhn-Reis-Teller"


def test_first_suggestion_rejects_recipe_too_low_for_kcal_and_protein(monkeypatch):
    too_low = """
    {
      "title": "Kleine Huhn-Reis-Bowl",
      "why_this_works": "Huhn und Reis ergeben eine einfache Hauptspeise.",
      "ingredients": ["110g Huhn", "100g Reis", "80g Brokkoli"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 110, "label": "110g Huhn"},
        {"id": 2, "amount_g": 100, "label": "100g Reis"},
        {"id": 3, "amount_g": 80, "label": "80g Brokkoli"}
      ],
      "instructions": ["Reis garen.", "Huhn braten.", "Mit Brokkoli servieren."],
      "estimated_macros": {"kcal": 800, "protein": 60, "fat": 20, "carbs": 90},
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": []
    }
    """
    responses = iter([too_low, too_low])
    _patch_llm(monkeypatch, lambda **kwargs: next(responses))
    result = generate_freestyle_recipes(
        [
            {"name": "Huhn", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
            {"name": "Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
            {"name": "Brokkoli", "amount": 300, "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7},
        ],
        daily_goal={"protein": 60, "kcal": 800},
        recipe_category="hauptspeise",
        count=1,
    )

    assert len(result["recipes"]) == 1
    _assert_invalid_warning(result["recipes"][0])
    assert result["recipes"][0]["title"] != "Kleine Huhn-Reis-Bowl"


def test_retries_still_reject_recipes_far_from_primary_targets(monkeypatch):
    bad_response = """
    {
      "title": "Huhn-Reis-Pfanne",
      "why_this_works": "Huhn, Reis und Brokkoli ergeben eine einfache Hauptspeise.",
      "ingredients": ["110g Huhn", "100g Reis", "80g Brokkoli"],
      "fridge_ingredients": [
        {"id": 1, "amount_g": 110, "label": "110g Huhn"},
        {"id": 2, "amount_g": 100, "label": "100g Reis"},
        {"id": 3, "amount_g": 80, "label": "80g Brokkoli"}
      ],
      "instructions": ["Reis garen.", "Huhn und Brokkoli braten.", "Alles zusammen servieren."],
      "estimated_macros": {"kcal": 800, "protein": 60, "fat": 25, "carbs": 90},
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": []
    }
    """
    responses = iter([bad_response, bad_response])
    _patch_llm(monkeypatch, lambda **kwargs: next(responses))
    result = generate_freestyle_recipe(
        [
            {"name": "Huhn", "amount": 300, "kcal_per_100g": 165, "protein_per_100g": 31, "fat_per_100g": 3.6, "carbs_per_100g": 0},
            {"name": "Reis", "amount": 500, "kcal_per_100g": 351, "protein_per_100g": 7.3, "fat_per_100g": 1.3, "carbs_per_100g": 77},
            {"name": "Brokkoli", "amount": 300, "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7},
        ],
        daily_goal={"protein": 60, "kcal": 800, "fat": 25, "carbs": 90},
        recipe_category="hauptspeise",
    )

    _assert_invalid_warning(result["recipe"])
    assert result["recipe"]["title"] != "Huhn-Reis-Pfanne"
    assert "--- retry ---" in result["raw_response"]


def test_secondary_targets_are_enforced_for_all_suggestions(monkeypatch):
    responses = iter([
        """
        {
          "title": "Hackfleisch-Bananen-Bowl",
          "why_this_works": "Hackfleisch, Salat und Banane ergeben einen unpassenden suess-herzhaften Mix.",
          "ingredients": ["150g Rinderhackfleisch", "50g Banane", "100g Eisbergsalat"],
          "fridge_ingredients": [
            {"id": 1, "amount_g": 150, "label": "150g Rinderhackfleisch"},
            {"id": 4, "amount_g": 50, "label": "50g Banane"},
            {"id": 3, "amount_g": 100, "label": "100g Eisbergsalat"}
          ],
          "instructions": ["Hackfleisch braten.", "Salat schneiden.", "Mit Banane servieren."],
          "estimated_macros": {"kcal": 620, "protein": 58, "fat": 28, "carbs": 65},
          "used_fridge_item_ids": [1, 4, 3],
          "pantry_assumptions": []
        }
        """,
        """
        {
          "title": "Burger-Bowl mit Salat",
          "why_this_works": "Hackfleisch, Bun, Salat und etwas Cheddar ergeben eine einfache Burger-Bowl.",
          "ingredients": ["200g Rinderhackfleisch", "140g Burger Bun", "100g Eisbergsalat", "25g Cheddar"],
          "fridge_ingredients": [
            {"id": 1, "amount_g": 200, "label": "200g Rinderhackfleisch"},
            {"id": 2, "amount_g": 140, "label": "140g Burger Bun"},
            {"id": 3, "amount_g": 100, "label": "100g Eisbergsalat"},
            {"id": 5, "amount_g": 25, "label": "25g Cheddar"}
          ],
          "instructions": ["Hackfleisch mit Salz und Pfeffer anbraten.", "Bun wuerfeln und kurz anroesten.", "Mit Salat und Cheddar als Bowl servieren."],
          "estimated_macros": {"kcal": 800, "protein": 60, "fat": 25, "carbs": 90},
          "used_fridge_item_ids": [1, 2, 3, 5],
          "pantry_assumptions": []
        }
        """,
    ])
    _patch_llm(monkeypatch, lambda **kwargs: next(responses))
    result = generate_freestyle_recipe(
        [
            {"name": "Rinderhackfleisch", "amount": 600, "kcal_per_100g": 193, "protein_per_100g": 19, "fat_per_100g": 13, "carbs_per_100g": 0},
            {"name": "Lean Burger Buns Sesame Seeds", "amount": 200, "kcal_per_100g": 206, "protein_per_100g": 13, "fat_per_100g": 3.8, "carbs_per_100g": 27},
            {"name": "Eisbergsalat", "amount": 300, "kcal_per_100g": 14, "protein_per_100g": 1, "fat_per_100g": 0.5, "carbs_per_100g": 1.6},
            {"name": "Banane", "amount": 400, "kcal_per_100g": 89, "protein_per_100g": 1.1, "fat_per_100g": 0.3, "carbs_per_100g": 23},
            {"name": "Cheddar mild", "amount": 400, "kcal_per_100g": 416, "protein_per_100g": 25, "fat_per_100g": 35, "carbs_per_100g": 0.5},
        ],
        daily_goal={"kcal": 800, "protein": 60, "fat": 25, "carbs": 90},
        recipe_category="hauptspeise",
    )

    recipe = result["recipe"]
    assert recipe["warning"] is True
    assert recipe["title"] == "Kein valides Rezept"
    assert "--- retry ---" in result["raw_response"]


def test_hallucinated_ingredients_fall_back(monkeypatch):
    hallucinated = """
    {
      "title": "Gemuese-Pfanne",
      "why_this_works": "Eine einfache Mahlzeit.",
      "ingredients": ["Kartoffeln", "Brokkoli", "Karotten"],
      "instructions": ["Schneiden.", "Braten.", "Servieren."],
      "estimated_macros": {"kcal": 600, "protein": 25, "fat": 30, "carbs": 80},
      "used_fridge_item_ids": [99],
      "pantry_assumptions": ["Salz"]
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: hallucinated)
    result = generate_freestyle_recipe(BASIC_FRIDGE)

    _assert_invalid_warning(result["recipe"])


def test_translated_ingredient_names_are_accepted(monkeypatch):
    # Modell schreibt "3 Eier", obwohl das Kuehlschrank-Item "Eggs" heisst.
    response = """
    {
      "title": "Brokkoli-Ei-Omelett",
      "why_this_works": "Eier und Brokkoli ergeben ein einfaches Gericht.",
      "ingredients": ["3 Eier", "150g Brokkoli", "15g Parmesan", "1 TL Öl"],
      "instructions": ["Brokkoli duensten.", "Eier verquirlen und braten.", "Mit Parmesan servieren."],
      "estimated_macros": {"kcal": 400, "protein": 30, "fat": 22, "carbs": 8},
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": ["Öl"]
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: response)
    result = generate_freestyle_recipe([
        {"name": "Eggs", "amount": 6},
        {"name": "Brokkoli", "amount": 300},
        {"name": "Parmesan", "amount": 150},
    ])

    recipe = result["recipe"]
    assert "fallback" not in recipe
    assert recipe["title"] == "Brokkoli-Ei-Omelett"
    assert recipe["used_fridge_items"] == ["Eggs", "Brokkoli", "Parmesan"]


def test_bad_first_response_retries_and_accepts_second(monkeypatch):
    responses = iter([
        """
        {
          "title": "Falsches Rezept",
          "why_this_works": "Nutzt erfundene Zutaten.",
          "ingredients": ["Kartoffeln"],
          "instructions": ["Schneiden.", "Braten.", "Servieren."],
          "estimated_macros": {"kcal": 500, "protein": 20, "fat": 10, "carbs": 80},
          "used_fridge_item_ids": [99],
          "pantry_assumptions": []
        }
        """,
        VALID_RESPONSE,
    ])
    _patch_llm(monkeypatch, lambda **kwargs: next(responses))
    result = generate_freestyle_recipe(BASIC_FRIDGE)

    assert result["recipe"]["title"] == "Protein-Pfannkuchen"
    assert "--- retry ---" in result["raw_response"]


def test_tiny_model_uses_short_budget_and_warning(monkeypatch):
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return ""

    _patch_llm(monkeypatch, fake)
    result = generate_freestyle_recipe(
        [
            {"name": "Paprika", "amount": 100},
            {"name": "Tofu Natur", "amount": 200},
            {"name": "Tomaten", "amount": 150},
            {"name": "Jasmin Reis", "amount": 200},
            {"name": "Frische Eier", "amount": 100},
            {"name": "Haferflocken", "amount": 80},
        ],
        model="gemma3:1b",
    )

    assert captured["num_predict"] == 560
    assert captured["format_json"] is True
    # max_items=5 fuer das kleine Modell -> die 6. Zutat faellt raus.
    assert "Haferflocken" not in captured["prompt"]
    _assert_invalid_warning(result["recipe"])


def test_breakfast_invalid_response_returns_warning(monkeypatch):
    _patch_llm(monkeypatch, lambda **kwargs: "")
    result = generate_freestyle_recipe(
        [
            {"name": "Spinat", "amount": 300},
            {"name": "Jasmin Reis", "amount": 500},
            {"name": "Haferflocken", "amount": 500},
            {"name": "Milch 1,5%", "amount": 1000},
            {"name": "Banane", "amount": 200},
            {"name": "ESN Whey Protein Cinnamon", "amount": 300},
        ],
        recipe_category="fruehstueck",
    )

    _assert_invalid_warning(result["recipe"])


def test_laptop_model_uses_short_token_budget(monkeypatch):
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return VALID_RESPONSE

    _patch_llm(monkeypatch, fake)
    generate_freestyle_recipe(BASIC_FRIDGE, model="qwen3:4b")

    assert captured["num_predict"] == 520
    assert captured["format_json"] is True
    assert "Dinkel Mehl" in captured["prompt"]


def test_empty_fridge_returns_hint(monkeypatch):
    _patch_llm(monkeypatch, lambda **kwargs: VALID_RESPONSE)
    result = generate_freestyle_recipe([])

    assert result["recipe"]["title"] == "Keine Zutaten verfügbar"
    assert result["recipe"]["ingredients"] == []


# --- mehrere Rezepte (Vorschlagsliste) ------------------------------------

THREE_RECIPES = """
[
  {"title": "Rezept A", "why_this_works": "x", "ingredients": ["Dinkel Mehl", "Wasser"],
   "instructions": ["a", "b", "c"], "estimated_macros": {"kcal": 400, "protein": 20, "fat": 8, "carbs": 60},
   "used_fridge_item_ids": [1], "pantry_assumptions": ["Wasser"]},
  {"title": "Rezept B", "why_this_works": "x", "ingredients": ["Frische Eier"],
   "instructions": ["a", "b", "c"], "estimated_macros": {"kcal": 200, "protein": 18, "fat": 12, "carbs": 2},
   "used_fridge_item_ids": [2], "pantry_assumptions": []},
  {"title": "Rezept C", "why_this_works": "x", "ingredients": ["Dinkel Mehl", "Frische Eier"],
   "instructions": ["a", "b", "c"], "estimated_macros": {"kcal": 500, "protein": 30, "fat": 15, "carbs": 55},
   "used_fridge_item_ids": [1, 2], "pantry_assumptions": []}
]
"""


def test_generate_three_recipes_from_array(monkeypatch):
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return THREE_RECIPES

    _patch_llm(monkeypatch, fake)
    result = generate_freestyle_recipes(BASIC_FRIDGE, count=3)

    assert [r["title"] for r in result["recipes"]] == ["Rezept A", "Rezept B", "Rezept C"]
    assert captured["num_predict"] == 900 * 3
    assert captured["temperature"] == 0.7
    assert captured["format_json"] is True


def test_multi_prompt_requests_array_of_three(monkeypatch):
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return "[]"

    _patch_llm(monkeypatch, fake)
    generate_freestyle_recipes(BASIC_FRIDGE, count=3)

    assert "3" in captured["prompt"]
    assert "Array" in captured["prompt"]


def test_recipes_under_foreign_wrapper_key_are_found(monkeypatch):
    # Modell verpackt die Liste unter einem deutschen Schluessel "rezepte".
    wrapped = (
        '{"rezepte": ['
        '{"title": "Rezept A", "ingredients": ["Dinkel Mehl"], "instructions": ["a", "b", "c"], "used_fridge_item_ids": [1]},'
        '{"title": "Rezept B", "ingredients": ["Frische Eier"], "instructions": ["a", "b", "c"], "used_fridge_item_ids": [2]}'
        ']}'
    )
    _patch_llm(monkeypatch, lambda **kwargs: wrapped)
    result = generate_freestyle_recipes(BASIC_FRIDGE, count=3)

    assert [r["title"] for r in result["recipes"]] == ["Rezept A", "Rezept B"]


def test_duplicate_titles_are_deduped(monkeypatch):
    resp = (
        '[{"title": "Gleich", "ingredients": ["Dinkel Mehl"], "instructions": ["a", "b", "c"], "used_fridge_item_ids": [1]},'
        ' {"title": "Gleich", "ingredients": ["Frische Eier"], "instructions": ["a", "b", "c"], "used_fridge_item_ids": [2]}]'
    )
    _patch_llm(monkeypatch, lambda **kwargs: resp)
    result = generate_freestyle_recipes(BASIC_FRIDGE, count=3)

    assert len(result["recipes"]) == 1


def test_multi_invalid_response_returns_single_warning(monkeypatch):
    _patch_llm(monkeypatch, lambda **kwargs: "")
    result = generate_freestyle_recipes(BASIC_FRIDGE, count=3)

    assert len(result["recipes"]) == 1
    _assert_invalid_warning(result["recipes"][0])


def test_supplement_allowed_in_sensible_dish(monkeypatch):
    # Protein-Pfannkuchen mit Whey + Mehl + Ei -> sinnvoll, wird akzeptiert.
    pancakes = """
    {
      "title": "Protein-Pfannkuchen",
      "why_this_works": "Whey, Mehl und Ei ergeben einen proteinreichen Teig.",
      "ingredients": ["40g Whey", "120g Dinkel Mehl", "2 Eier"],
      "instructions": ["Zutaten verruehren.", "Teig ausbacken.", "Servieren."],
      "estimated_macros": {"kcal": 520, "protein": 45, "fat": 12, "carbs": 60},
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: pancakes)
    fridge = [
        {"name": "Bulk Pure Whey Protein Powder- neutral", "amount": 1000},
        {"name": "Dinkel Mehl", "amount": 500},
        {"name": "Frische Eier", "amount": 6},
    ]
    result = generate_freestyle_recipes(fridge, recipe_category="hauptspeise", count=3)

    assert result["recipes"][0]["title"] == "Protein-Pfannkuchen"
    assert "fallback" not in result["recipes"][0]
    assert result["recipes"][0]["used_fridge_items"] == ["Bulk Pure Whey Protein Powder- neutral", "Dinkel Mehl", "Frische Eier"]


def test_vegetable_with_supplement_is_rejected(monkeypatch):
    # Whey + Spinat/Karotte im selben Gericht -> inkohaerent -> abgelehnt.
    bad = """
    {
      "title": "Whey-Pfannkuchen mit Spinat und Karotten",
      "why_this_works": "Herzhaft-suess.",
      "ingredients": ["30g Whey", "Spinat", "Karotte"],
      "instructions": ["Mischen.", "Ausbacken.", "Servieren."],
      "estimated_macros": {"kcal": 500, "protein": 40, "fat": 10, "carbs": 50},
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: bad)
    fridge = [
        {"name": "ESN Whey Protein Cinnamon", "amount": 300},
        {"name": "Spinat", "amount": 200},
        {"name": "Karotte", "amount": 400},
    ]
    result = generate_freestyle_recipes(fridge, recipe_category="fruehstueck", count=3)

    _assert_invalid_warning(result["recipes"][0])


def test_vegetables_without_sweet_are_fine(monkeypatch):
    # Reines Gemuese-Gericht ohne Supplement/Suesses -> erlaubt.
    savory = """
    {
      "title": "Spinat-Karotten-Pfanne mit Ei",
      "why_this_works": "Einfaches herzhaftes Gericht.",
      "ingredients": ["100g Spinat", "100g Karotte", "2 Eier"],
      "instructions": ["Gemuese anbraten.", "Eier zugeben.", "Wuerzen und servieren."],
      "estimated_macros": {"kcal": 300, "protein": 18, "fat": 16, "carbs": 14},
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": []
    }
    """
    _patch_llm(monkeypatch, lambda **kwargs: savory)
    fridge = [
        {"name": "Spinat", "amount": 200},
        {"name": "Karotte", "amount": 400},
        {"name": "Frische Eier", "amount": 6},
    ]
    result = generate_freestyle_recipes(fridge, recipe_category="hauptspeise", count=3)

    assert result["recipes"][0]["title"] == "Spinat-Karotten-Pfanne mit Ei"
    assert "fallback" not in result["recipes"][0]


def test_multi_llm_error_returns_warning(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("ollama down")

    _patch_llm(monkeypatch, boom)
    result = generate_freestyle_recipes(BASIC_FRIDGE, count=3)

    assert result["recipes"][0]["warning"] is True
    assert "ollama down" in result["error"]
