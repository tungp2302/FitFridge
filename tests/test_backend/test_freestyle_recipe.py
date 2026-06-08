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


def test_empty_llm_response_returns_warning(monkeypatch):
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
    assert recipe["warning"] is True
    assert recipe["title"] == "LLM-Antwort nicht brauchbar"
    assert "zweiten Versuch" in recipe["why_this_works"]


def test_low_quality_llm_recipe_returns_warning(monkeypatch):
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
    assert recipe["warning"] is True
    assert recipe["title"] == "LLM-Antwort nicht brauchbar"


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


def test_hallucinated_ingredients_return_warning(monkeypatch):
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
    assert recipe["warning"] is True
    assert recipe["title"] == "LLM-Antwort nicht brauchbar"


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


def test_incoherent_sweet_savory_recipe_is_rejected(monkeypatch):
    incoherent_response = """
    {
      "title": "Apfel-Tofu-Pfannkuchen mit Milch und Salz",
      "why_this_works": "Fragwürdige Mischung.",
      "ingredients": ["Apfel", "Tofu Natur", "Dinkel Mehl", "Frische Eier", "Milch", "Salz"],
      "instructions": ["Teig rühren.", "Tofu und Apfel unterheben.", "Pfannkuchen ausbacken."],
      "estimated_macros": {"kcal": 600, "protein": 35, "fat": 15, "carbs": 80},
      "used_fridge_item_ids": [1, 2, 3, 4],
      "pantry_assumptions": ["Milch", "Salz"]
    }
    """
    monkeypatch.setattr(
        "flaskr_new.asaai.freestyle_recipe.generate_from_ollama",
        lambda **kwargs: incoherent_response,
    )

    result = generate_freestyle_recipe(
        [
            {"name": "Apfel", "amount": 100},
            {"name": "Tofu Natur", "amount": 200},
            {"name": "Dinkel Mehl", "amount": 120},
            {"name": "Frische Eier", "amount": 100},
        ],
        recipe_category="fruehstueck",
    )

    assert result["recipe"]["warning"] is True
    assert result["recipe"]["title"] == "LLM-Antwort nicht brauchbar"


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
