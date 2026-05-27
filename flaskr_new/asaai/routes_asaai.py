"""Flask-Routes für das ASaAI-Modul.

Stellt die KI-Features als HTTP-Endpoints zur Verfügung:
- GET /asaai/recipes/suggest: Rezeptvorschläge basierend auf Kühlschrank
- POST /asaai/recipes/suggest: Mit Body für daily_goal

Diese Routes nutzen die komplette ASaAI-Pipeline:
1. Recipe Matcher (TheMealDB)
2. Macro Calculator (OpenFoodFacts)
3. LLM Enricher (Ollama)
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .. import fridge_repo
from .recipe_matcher import find_recipes_matching_fridge
from .llm_enricher import enrich_with_full_pipeline


asaai_bp = Blueprint("asaai", __name__, url_prefix="/asaai")


@asaai_bp.route("/recipes/suggest", methods=("GET", "POST"))
def suggest_recipes():
    """Liefert KI-basierte Rezeptvorschläge.

    GET: Nutzt aktuelle Kühlschrank-Items aus DB
    POST: Body mit optional daily_goal {"protein": 30, "kcal": 600}

    Returns:
        JSON mit:
        - llm_recommendation: Textuelle Empfehlung vom LLM
        - enriched_matches: Liste der Top-Rezepte mit Macros
        - pipeline_stats: Statistiken über Pipeline-Performance
    """
    # Daily Goal aus Request-Body holen (falls POST)
    daily_goal = None
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        daily_goal = data.get("daily_goal")

    # Kühlschrank-Items aus DB holen
    try:
        items = fridge_repo.list_items()
    except Exception as e:
        return jsonify({
            "error": f"Kühlschrank konnte nicht geladen werden: {e}",
            "llm_recommendation": "",
            "enriched_matches": [],
        }), 500

    # Edge Case: Leerer Kühlschrank
    if not items:
        return jsonify({
            "llm_recommendation": "Dein Kühlschrank ist leer. Füge Produkte hinzu, um Rezepte vorgeschlagen zu bekommen.",
            "enriched_matches": [],
            "pipeline_stats": {"total_matches": 0},
        })

    # Items in das richtige Format für Recipe Matcher bringen
    fridge_items = [
    {"name": item["name"], "amount": item["current_amount"]}
    for item in items
    ]

    # Phase 0: Recipe Matcher
    matches = find_recipes_matching_fridge(
        fridge_items,
        max_recipes_per_ingredient=3,
    )

    # Phase 1-3: Volle Pipeline
    result = enrich_with_full_pipeline(
        matches=matches,
        fridge_items=fridge_items,
        daily_goal=daily_goal,
        top_n=5,
    )

    return jsonify(result)


@asaai_bp.route("/recipes/match-only", methods=("GET",))
def match_only():
    """Schnelle Version OHNE LLM: nur Recipe Matcher + Macros.

    Nützlich für Frontend wenn LLM zu langsam ist.
    Liefert nur deterministische Resultate.
    """
    try:
        items = fridge_repo.list_items()
    except Exception as e:
        return jsonify({"error": str(e), "matches": []}), 500

    if not items:
        return jsonify({"matches": []})

    fridge_items = [
        {"name": item["name"], "amount": item["current_amount"]}
        for item in items
    ]

    matches = find_recipes_matching_fridge(
        fridge_items,
        max_recipes_per_ingredient=3,
    )

    return jsonify({
        "matches": matches[:5],  # nur Top 5 zurückgeben
        "total_found": len(matches),
    })