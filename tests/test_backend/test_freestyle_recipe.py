from flaskr_new.asaai.freestyle_recipe import generate_freestyle_recipe


def test_missing_llm_returns_warning_instead_of_fake_recipe(monkeypatch):
    def fake_generate_from_ollama(**kwargs):
        raise RuntimeError("Ollama is not running")

    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        fake_generate_from_ollama,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Dinkel Mehl", "amount": 120},
            {"name": "Frische Eier", "amount": 100},
            {"name": "Bulk Pure Whey Protein Powder- neutral", "amount": 40},
        ]
    )

    recipe = result["recipe"]
    assert recipe["warning"] is True
    assert recipe["title"] == "LLM nicht erreichbar"
    assert recipe["ingredients"] == []
    assert "Ollama is not running" in result["error"]


def test_empty_llm_response_returns_model_failed_fallback(monkeypatch):
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: "",
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Dinkel Mehl", "amount": 120},
            {"name": "Frische Eier", "amount": 100},
            {"name": "Bulk Pure Whey Protein Powder- neutral", "amount": 40},
        ]
    )

    recipe = result["recipe"]
    assert recipe["fallback"] is True
    assert recipe["title"] == "Modell fehlgeschlagen - lokaler Fallback"
    assert "kein brauchbares Rezept" in recipe["why_this_works"]


def test_low_quality_llm_recipe_returns_model_failed_fallback(monkeypatch):
    bad_response = """
    {
      "title": "Dinkel Mehl + Frische Eier + Bulk Pure Whey Protein Powder- neutral",
      "why_this_works": "Dieses Rezept kombiniert die ersten passenden Kühlschrank-Zutaten zu einer einfachen Mahlzeit.",
      "ingredients": ["Dinkel Mehl", "Frische Eier", "Bulk Pure Whey Protein Powder- neutral"],
      "instructions": [
        "Zutaten vorbereiten und bei Bedarf klein schneiden.",
        "Pfanne erhitzen, würzen und die Zutaten nacheinander garen.",
        "Abschmecken und direkt servieren."
      ],
      "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
      "used_fridge_item_ids": [1, 2, 3],
      "pantry_assumptions": ["Öl", "Salz", "Pfeffer"]
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: bad_response,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Dinkel Mehl", "amount": 120},
            {"name": "Frische Eier", "amount": 100},
            {"name": "Bulk Pure Whey Protein Powder- neutral", "amount": 40},
        ]
    )

    recipe = result["recipe"]
    assert recipe["fallback"] is True
    assert recipe["title"] == "Modell fehlgeschlagen - lokaler Fallback"


def test_freestyle_requests_ollama_json_mode(monkeypatch):
    captured = {}

    def fake_generate_from_ollama(**kwargs):
        captured.update(kwargs)
        return """
        {
          "title": "Protein-Pfannkuchen",
          "why_this_works": "Mehl und Eier ergeben einen Teig.",
          "ingredients": ["Dinkel Mehl", "Frische Eier", "Wasser"],
          "instructions": ["Mehl und Eier verrühren.", "Teig kurz ruhen lassen.", "Pfannkuchen ausbacken."],
          "estimated_macros": {"kcal": 500, "protein": 35, "fat": 12, "carbs": 60},
          "used_fridge_item_ids": [1, 2],
          "pantry_assumptions": ["Wasser"]
        }
        """

    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        fake_generate_from_ollama,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Dinkel Mehl", "amount": 120},
            {"name": "Frische Eier", "amount": 100},
        ]
    )

    assert result["recipe"]["title"] == "Protein-Pfannkuchen"
    assert result["recipe"]["used_fridge_items"] == ["Dinkel Mehl", "Frische Eier"]
    assert captured["format_json"] is True
    assert captured["num_predict"] == 900


def test_tiny_model_uses_short_budget_and_local_fallback(monkeypatch):
    calls = []

    def fake_generate_from_ollama(**kwargs):
        calls.append(kwargs)
        return ""

    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        fake_generate_from_ollama,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Paprika", "amount": 100},
            {"name": "Tofu Natur", "amount": 200},
            {"name": "Tomaten", "amount": 150},
            {"name": "Jasmin Reis", "amount": 200},
            {"name": "Frische Eier", "amount": 100},
            {"name": "Dinkel Mehl", "amount": 120},
            {"name": "Magerquark", "amount": 250},
            {"name": "Haferflocken", "amount": 80},
        ],
        recipe_category="hauptspeise",
        model="gemma3:1b",
    )

    assert len(calls) == 1
    assert calls[0]["num_predict"] == 420
    assert calls[0]["format_json"] is True
    assert "Haferflocken" not in calls[0]["prompt"]
    assert "--- retry ---" not in result["raw_response"]
    assert result["recipe"]["fallback"] is True
    assert result["recipe"]["title"] == "Modell fehlgeschlagen - lokaler Fallback"
    assert result["recipe"]["used_fridge_items"] == ["Tofu Natur", "Jasmin Reis", "Paprika"]


def test_tiny_model_repairs_usable_sloppy_recipe_instead_of_fallback(monkeypatch):
    sloppy_response = """
    {
      "name": "Tofu-Reis-Pfanne",
      "why": "Tofu, Reis und Tomaten ergeben eine einfache Hauptspeise.",
      "ingredients": ["Tofu Natur", "Jasmin Reis", "Tomaten", "Olivenöl", "Salz"],
      "instructions": "Reis garen. Tofu und Tomaten in Öl braten. Alles würzen und servieren.",
      "macros": {"calories": 620, "protein_g": 31, "fat_g": 12, "carbohydrates": 82},
      "used_fridge_items": ["Tofu Natur", "Jasmin Reis", "Tomaten"]
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: sloppy_response,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Tofu Natur", "amount": 200},
            {"name": "Jasmin Reis", "amount": 200},
            {"name": "Tomaten", "amount": 150},
        ],
        daily_goal={"protein": 45, "fat": 20},
        recipe_category="hauptspeise",
        model="gemma3:1b",
    )

    recipe = result["recipe"]
    assert "fallback" not in recipe
    assert recipe["title"] == "Tofu-Reis-Pfanne"
    assert recipe["used_fridge_items"] == ["Tofu Natur", "Jasmin Reis", "Tomaten"]
    assert recipe["estimated_macros"]["protein"] == 45
    assert recipe["estimated_macros"]["fat"] == 20


def test_tiny_model_accepts_single_sensible_product(monkeypatch):
    yogurt_response = """
    {
      "title": "Greek Yogurt Snack",
      "why_this_works": "Greek Yogurt can be eaten directly as a simple protein snack.",
      "ingredients": ["Greek Yogurt"],
      "instructions": ["Spoon yogurt into a bowl.", "Stir until creamy.", "Serve chilled."],
      "estimated_macros": {"protein": 30, "fat": 6, "calories": 240, "carbs": 10},
      "used_fridge_item_ids": ["1"],
      "pantry_assumptions": []
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: yogurt_response,
    )

    result = generate_freestyle_recipe(
        [{"name": "Greek Yogurt", "amount": 300}],
        daily_goal={"protein": 30, "fat": 6},
        recipe_category="snack",
        model="gemma3:1b",
    )

    recipe = result["recipe"]
    assert "fallback" not in recipe
    assert recipe["title"] == "Greek Yogurt Snack"
    assert recipe["used_fridge_items"] == ["Greek Yogurt"]


def test_tiny_model_replaces_hallucinated_core_food_in_title(monkeypatch):
    hallucinated_title_response = """
    {
      "title": "Parmesan Greek Yogurt Salmon Bake",
      "why_this_works": "Salmon makes this high protein.",
      "ingredients": ["Parmesan", "Greek Yogurt", "Eggs", "Oil", "Salt", "Pepper"],
      "instructions": ["Whisk eggs.", "Mix yogurt and parmesan.", "Bake until set."],
      "estimated_macros": {"protein": 60, "fat": 25, "calories": 800},
      "used_fridge_item_ids": ["1", "2", "3"],
      "pantry_assumptions": "oil and salt"
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: hallucinated_title_response,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Parmesan", "amount": 150},
            {"name": "Greek Yogurt", "amount": 300},
            {"name": "Eggs", "amount": 6},
        ],
        daily_goal={"protein": 60, "fat": 25},
        recipe_category="hauptspeise",
        model="gemma3:1b",
    )

    recipe = result["recipe"]
    assert "fallback" not in recipe
    assert "Salmon" not in recipe["title"]
    assert "Salmon" not in recipe["why_this_works"]
    assert recipe["used_fridge_items"] == ["Parmesan", "Greek Yogurt", "Eggs"]


def test_laptop_model_uses_compact_profile(monkeypatch):
    captured = {}

    def fake_generate_from_ollama(**kwargs):
        captured.update(kwargs)
        return """
        {
          "title": "Tofu-Reis-Pfanne",
          "why_this_works": "Tofu und Reis passen als einfache Hauptspeise.",
          "ingredients": ["Tofu Natur", "Jasmin Reis", "Öl"],
          "instructions": ["Reis garen.", "Tofu anbraten.", "Alles würzen und servieren."],
          "estimated_macros": {"kcal": 520, "protein": 28, "fat": 16, "carbs": 65},
          "used_fridge_item_ids": [1, 2],
          "pantry_assumptions": ["Öl"]
        }
        """

    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        fake_generate_from_ollama,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Tofu Natur", "amount": 200},
            {"name": "Jasmin Reis", "amount": 200},
        ],
        recipe_category="hauptspeise",
        model="qwen3:4b",
    )

    assert result["recipe"]["title"] == "Tofu-Reis-Pfanne"
    assert captured["num_predict"] == 320
    assert "Return ONLY JSON" in captured["prompt"]
    assert "fridge IDs" in captured["prompt"]


def test_tiny_model_keeps_targeted_main_dish_items_in_prompt(monkeypatch):
    captured = {}

    def fake_generate_from_ollama(**kwargs):
        captured.update(kwargs)
        return """
        {
          "title": "Steak mit Kartoffeln und Gemüse",
          "why_this_works": "Steak, Kartoffeln und Gemüse ergeben ein klassisches Hauptgericht.",
          "ingredients": ["Steak", "Kartoffeln", "Brokkoli", "Öl", "Salz"],
          "instructions": ["Kartoffeln garen.", "Steak braten.", "Gemüse garen und alles servieren."],
          "estimated_macros": {"kcal": 760, "protein": 60, "fat": 25, "carbs": 65},
          "used_fridge_item_ids": [1, 2, 3],
          "pantry_assumptions": ["Öl", "Salz"]
        }
        """

    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        fake_generate_from_ollama,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Steak", "amount": 250},
            {"name": "Kartoffeln", "amount": 400},
            {"name": "Brokkoli", "amount": 250},
        ],
        daily_goal={"protein": 60, "fat": 25},
        recipe_category="hauptspeise",
        model="gemma3:1b",
    )

    assert "Steak" in captured["prompt"]
    assert "Kartoffeln" in captured["prompt"]
    assert "Brokkoli" in captured["prompt"]
    assert result["recipe"]["title"] == "Steak mit Kartoffeln und Gemüse"


def test_tiny_model_repair_adds_quantities_and_specific_cooking_steps(monkeypatch):
    messy_main_dish = """
    {
      "title": "Hearty Steak & Kartoffel with Parmesan & Yogurt",
      "why_this_works": "This dish combines a lean steak with hearty potatoes and broccoli.",
      "ingredients": ["Steak", "Kartoffeln", "Brokkoli", "Parmesan", "Greek Yogurt"],
      "instructions": ["Combine everything and serve.", "Season.", "Enjoy."],
      "estimated_macros": {"protein": 60, "fat": 25, "calories": 800},
      "used_fridge_item_ids": ["1"]
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: messy_main_dish,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Steak", "amount": 250, "unit": "g", "kcal_per_100g": 217, "protein_per_100g": 26.0, "fat_per_100g": 12.0, "carbs_per_100g": 0.0},
            {"name": "Kartoffeln", "amount": 500, "unit": "g", "kcal_per_100g": 77, "protein_per_100g": 2.0, "fat_per_100g": 0.1, "carbs_per_100g": 17.0},
            {"name": "Brokkoli", "amount": 300, "unit": "g", "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7.0},
            {"name": "Parmesan", "amount": 150, "unit": "g"},
            {"name": "Greek Yogurt", "amount": 300, "unit": "g"},
        ],
        daily_goal={"protein": 60, "fat": 25, "kcal": 800},
        recipe_category="hauptspeise",
        model="gemma3:1b",
    )

    recipe = result["recipe"]
    assert recipe["title"] == "Steak mit Kartoffeln und Brokkoli"
    assert recipe["ingredients"] == ["185g Steak", "300g Kartoffeln", "200g Brokkoli"]
    assert recipe["macro_source"] == "computed_from_ingredient_quantities"
    assert recipe["estimated_macros"] == {"kcal": 700.5, "protein": 59.7, "fat": 23.3, "carbs": 65.0}
    assert "15-20 Minuten" in recipe["instructions"][0]
    assert "5-7 Minuten" in recipe["instructions"][1]
    assert "2-4 Minuten pro Seite" in recipe["instructions"][2]


def test_quantity_plan_computes_macros_from_recipe_amounts_not_full_stock(monkeypatch):
    messy_main_dish = """
    {
      "title": "Steak Kartoffel Brokkoli",
      "why_this_works": "Steak, Kartoffeln und Brokkoli ergeben ein einfaches Hauptgericht.",
      "ingredients": ["500g Kartoffeln", "250g Steak", "300g Brokkoli"],
      "instructions": ["Kartoffeln kochen.", "Steak braten.", "Brokkoli garen."],
      "estimated_macros": {"kcal": 540, "protein": 80, "fat": 130, "carbs": 130},
      "used_fridge_item_ids": [1, 2, 3]
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: messy_main_dish,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Steak", "amount": 250, "unit": "g", "kcal_per_100g": 217, "protein_per_100g": 26.0, "fat_per_100g": 12.0, "carbs_per_100g": 0.0},
            {"name": "Kartoffeln", "amount": 500, "unit": "g", "kcal_per_100g": 77, "protein_per_100g": 2.0, "fat_per_100g": 0.1, "carbs_per_100g": 17.0},
            {"name": "Brokkoli", "amount": 300, "unit": "g", "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7.0},
        ],
        daily_goal={"protein": 80, "fat": 25, "kcal": 1300},
        recipe_category="hauptspeise",
        model="gemma3:1b",
    )

    recipe = result["recipe"]
    assert "fallback" not in recipe
    assert recipe["ingredients"] == ["250g Steak", "300g Kartoffeln", "200g Brokkoli"]
    assert "500g Kartoffeln" not in recipe["ingredients"]
    assert recipe["estimated_macros"] == {"kcal": 841.5, "protein": 76.6, "fat": 31.1, "carbs": 65.0}
    assert recipe["macro_source"] == "computed_from_ingredient_quantities"


def test_laptop_model_repair_prefers_main_course_core_over_extra_dairy(monkeypatch):
    qwen_response = """
    {
      "title": "Pan-Seared Steak with Broccoli and Yogurt",
      "why_this_works": "Uses steak, broccoli, yogurt and eggs for balanced macros.",
      "ingredients": ["1 Steak (250g)", "3 Brokkoli (300g)", "5 Greek Yogurt (300g)", "6 Eggs (6pcs)"],
      "instructions": [
        "Pan-sear steak.",
        "Sauté broccoli.",
        "Mix yogurt with eggs and serve over steak."
      ],
      "estimated_macros": {"protein": 82, "fat": 24, "kcal": 1305},
      "used_fridge_item_ids": ["1", "3", "5", "6"],
      "pantry_assumptions": ["Oil", "Salt"]
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: qwen_response,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Steak", "amount": 250, "unit": "g", "kcal_per_100g": 217, "protein_per_100g": 26.0, "fat_per_100g": 12.0, "carbs_per_100g": 0.0},
            {"name": "Kartoffeln", "amount": 500, "unit": "g", "kcal_per_100g": 77, "protein_per_100g": 2.0, "fat_per_100g": 0.1, "carbs_per_100g": 17.0},
            {"name": "Brokkoli", "amount": 300, "unit": "g", "kcal_per_100g": 34, "protein_per_100g": 2.8, "fat_per_100g": 0.4, "carbs_per_100g": 7.0},
            {"name": "Parmesan", "amount": 150, "unit": "g", "kcal_per_100g": 431, "protein_per_100g": 38.0, "fat_per_100g": 29.0, "carbs_per_100g": 4.1},
            {"name": "Greek Yogurt", "amount": 300, "unit": "g", "kcal_per_100g": 72, "protein_per_100g": 9.5, "fat_per_100g": 2.0, "carbs_per_100g": 3.5},
            {"name": "Eggs", "amount": 6, "unit": "pcs", "kcal_per_100g": 143, "protein_per_100g": 12.6, "fat_per_100g": 9.5, "carbs_per_100g": 0.7},
        ],
        daily_goal={"protein": 80, "fat": 25, "kcal": 1300},
        recipe_category="hauptspeise",
        model="qwen3:4b",
    )

    recipe = result["recipe"]
    assert recipe["title"] == "Steak mit Kartoffeln und Brokkoli"
    assert recipe["used_fridge_items"] == ["Steak", "Kartoffeln", "Brokkoli"]
    assert recipe["ingredients"] == ["250g Steak", "300g Kartoffeln", "200g Brokkoli"]
    assert recipe["estimated_macros"] == {"kcal": 841.5, "protein": 76.6, "fat": 31.1, "carbs": 65.0}


def test_macro_targets_reject_recipe_more_than_10g_off_and_retry(monkeypatch):
    responses = iter([
        """
        {
          "title": "Zu mageres Omelett",
          "why_this_works": "Passt fast.",
          "ingredients": ["Frische Eier", "Öl"],
          "instructions": ["Eier verquirlen.", "In Öl stocken lassen.", "Servieren."],
          "estimated_macros": {"kcal": 360, "protein": 20, "fat": 8, "carbs": 4},
          "used_fridge_item_ids": [1],
          "pantry_assumptions": ["Öl"]
        }
        """,
        """
        {
          "title": "Zielgenaues Eiergericht",
          "why_this_works": "Protein und Fett liegen im Zielbereich.",
          "ingredients": ["Frische Eier", "Öl"],
          "instructions": ["Eier verquirlen.", "In Öl stocken lassen.", "Servieren."],
          "estimated_macros": {"kcal": 520, "protein": 47, "fat": 23, "carbs": 4},
          "used_fridge_item_ids": [1],
          "pantry_assumptions": ["Öl"]
        }
        """,
    ])

    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: next(responses),
    )

    result = generate_freestyle_recipe(
        [{"name": "Frische Eier", "amount": 300}],
        daily_goal={"protein": 50, "fat": 25},
    )

    assert result["recipe"]["title"] == "Zielgenaues Eiergericht"
    assert result["recipe"]["estimated_macros"]["protein"] == 47
    assert result["recipe"]["estimated_macros"]["fat"] == 23
    assert "--- retry ---" in result["raw_response"]


def test_small_model_fallback_macros_stay_within_protein_and_fat_goal(monkeypatch):
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: "",
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Paprika", "amount": 100},
            {"name": "Tofu Natur", "amount": 200},
        ],
        daily_goal={"protein": 62, "fat": 18},
        model="gemma3:1b",
    )

    recipe = result["recipe"]
    assert recipe["title"] == "Modell fehlgeschlagen - lokaler Fallback"
    assert recipe["estimated_macros"]["protein"] == 62
    assert recipe["estimated_macros"]["fat"] == 18


def test_hallucinated_ingredients_return_model_failed_fallback(monkeypatch):
    hallucinated_response = """
    {
      "title": "Gemischte Kartoffel-Gemüse-Pfanne",
      "why_this_works": "Eine einfache Mahlzeit.",
      "ingredients": ["Kartoffeln", "Brokkoli", "Karotten", "Zwiebel", "Olivenöl"],
      "instructions": ["Kartoffeln schneiden.", "Gemüse braten.", "Würzen und servieren."],
      "estimated_macros": {"kcal": 600, "protein": 25, "fat": 30, "carbs": 80},
      "used_fridge_item_ids": [99],
      "pantry_assumptions": ["Wasser", "Salz", "Pfeffer"]
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: hallucinated_response,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Dinkel Mehl", "amount": 120},
            {"name": "Frische Eier", "amount": 100},
            {"name": "Bulk Pure Whey Protein Powder- neutral", "amount": 40},
        ]
    )

    recipe = result["recipe"]
    assert recipe["fallback"] is True
    assert recipe["title"] == "Modell fehlgeschlagen - lokaler Fallback"


def test_bad_first_response_retries_and_accepts_corrected_recipe(monkeypatch):
    responses = iter([
        """
        {
          "title": "Kartoffelpfanne",
          "why_this_works": "Passt.",
          "ingredients": ["Kartoffeln", "Brokkoli"],
          "instructions": ["Schneiden.", "Braten.", "Servieren."],
          "estimated_macros": {"kcal": 500, "protein": 20, "fat": 10, "carbs": 80},
          "used_fridge_item_ids": [99],
          "pantry_assumptions": ["Salz"]
        }
        """,
        """
        {
          "title": "Protein-Pfannkuchen",
          "why_this_works": "Mehl, Eier und Whey ergeben einen proteinreichen Teig.",
          "ingredients": ["Dinkel Mehl", "Frische Eier", "Bulk Pure Whey Protein Powder- neutral", "Wasser"],
          "instructions": ["Zutaten verrühren.", "Teig kurz ruhen lassen.", "Pfannkuchen ausbacken."],
          "estimated_macros": {"kcal": 620, "protein": 48, "fat": 16, "carbs": 70},
          "used_fridge_item_ids": [1, 2, 3],
          "pantry_assumptions": ["Wasser"]
        }
        """,
    ])

    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: next(responses),
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Dinkel Mehl", "amount": 120},
            {"name": "Frische Eier", "amount": 100},
            {"name": "Bulk Pure Whey Protein Powder- neutral", "amount": 40},
        ]
    )

    recipe = result["recipe"]
    assert recipe["title"] == "Protein-Pfannkuchen"
    assert recipe["used_fridge_items"] == [
        "Dinkel Mehl",
        "Frische Eier",
        "Bulk Pure Whey Protein Powder- neutral",
    ]
    assert "--- retry ---" in result["raw_response"]


def test_recipe_can_use_many_fridge_items_when_they_fit(monkeypatch):
    coherent_response = """
    {
      "title": "Tofu-Reis-Bowl mit Paprika und Tomaten",
      "why_this_works": "Reis, Tofu und Gemüse ergeben eine stimmige herzhafte Bowl.",
      "ingredients": ["Paprika", "Tofu Natur", "Tomaten", "Jasmin Reis", "Frische Eier"],
      "instructions": ["Reis garen.", "Tofu, Paprika und Tomaten anbraten.", "Ei stocken lassen und alles als Bowl servieren."],
      "estimated_macros": {"kcal": 720, "protein": 42, "fat": 18, "carbs": 90},
      "used_fridge_item_ids": [1, 2, 3, 4, 5],
      "pantry_assumptions": ["Salz", "Pfeffer"]
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: coherent_response,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Paprika", "amount": 100},
            {"name": "Tofu Natur", "amount": 200},
            {"name": "Tomaten", "amount": 150},
            {"name": "Jasmin Reis", "amount": 200},
            {"name": "Frische Eier", "amount": 100},
        ],
        recipe_category="hauptspeise",
    )

    assert result["recipe"]["title"] == "Tofu-Reis-Bowl mit Paprika und Tomaten"
    assert result["recipe"]["used_fridge_items"] == [
        "Paprika",
        "Tofu Natur",
        "Tomaten",
        "Jasmin Reis",
        "Frische Eier",
    ]
