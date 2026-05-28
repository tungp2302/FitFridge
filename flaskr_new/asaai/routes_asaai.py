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
from .nutrition_insights import generate_nutrition_insight
from .consumption_forecast import (
    calculate_days_until_empty,
    average_daily_consumption,
    generate_forecast_insight,
)


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

@asaai_bp.route("/insights/nutrition", methods=("GET", "POST"))
def nutrition_insight():
    """Liefert KI-basierte Ernährungs-Insights für den Kühlschrank.

    GET: Standard-Analyse ohne Tagesziel
    POST: Body mit optional daily_goal {"protein": 120, "kcal": 2000}

    Returns:
        JSON mit insight_text und analysis
    """
    daily_goal = None
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        daily_goal = data.get("daily_goal")

    try:
        items = fridge_repo.list_items()
    except Exception as e:
        return jsonify({
            "error": f"Kühlschrank konnte nicht geladen werden: {e}",
            "insight_text": "",
        }), 500

    result = generate_nutrition_insight(
        fridge_items=items,
        daily_goal=daily_goal,
    )

    return jsonify(result)

@asaai_bp.route("/forecast", methods=("GET",))
def consumption_forecast():
    """Liefert Verbrauchsprognose für alle Kühlschrank-Items.

    Nutzt consumption_log um zu berechnen, wann jedes Item leer ist.
    LLM erklärt die Prognose in natürlicher Sprache.

    Returns:
        JSON mit forecasts und insight_text
    """
    try:
        items = fridge_repo.list_items()
    except Exception as e:
        return jsonify({
            "error": f"Kühlschrank konnte nicht geladen werden: {e}",
            "forecasts": [],
        }), 500

    if not items:
        return jsonify({
            "insight_text": "Dein Kühlschrank ist leer.",
            "forecasts": [],
        })

    # Berechnung pro Item
    forecasts = []
    for item in items:
        item_dict = dict(item)
        product_id = item_dict.get("product_id")
        current_amount = float(item_dict.get("current_amount", 0))

        # Versuche Verbrauchshistorie zu holen (falls Tungs Repo das hat)
        try:
            from flaskr_new.consumption_log_repo import get_consumption_for_product
            history = get_consumption_for_product(product_id)
        except Exception:
            # Fallback: leere Historie wenn Repo-Funktion nicht existiert
            history = []

        daily_rate = average_daily_consumption(history)
        days_until_empty = calculate_days_until_empty(current_amount, daily_rate)

        forecasts.append({
            "name": item_dict.get("name", "Unbekannt"),
            "current_amount": current_amount,
            "unit": item_dict.get("unit", "g"),
            "daily_consumption": daily_rate,
            "days_until_empty": days_until_empty,
        })

    # Sortiere nach „wann leer" (am dringendsten zuerst)
    forecasts.sort(key=lambda f: f["days_until_empty"])

    # LLM-Erklärung generieren
    result = generate_forecast_insight(forecasts)

    return jsonify(result)