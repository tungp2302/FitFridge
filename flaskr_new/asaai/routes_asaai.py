"""Minimal AI routes kept for the current FitFridge scope."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, render_template, request

from .. import fridge_repo
from .freestyle_recipe import generate_freestyle_recipes
from .ollama_client import resolve_ollama_model


asaai_bp = Blueprint("asaai", __name__, url_prefix="/asaai")


def _current_fridge_items():
    user = getattr(g, "user", None)
    if user is None:
        return []
    try:
        return [dict(item) for item in fridge_repo.list_items(user["id"])]
    except Exception:
        return []


def _selected_ollama_model(data=None):
    if isinstance(data, dict):
        body_model = data.get("model") or data.get("ollama_model")
        if body_model:
            return resolve_ollama_model(str(body_model))
    query_model = request.args.get("model") or request.args.get("ollama_model")
    return resolve_ollama_model(query_model)


@asaai_bp.route("/recipes/freestyle", methods=("POST",))
def freestyle_recipe():
    """Generate several recipe suggestions directly from fridge contents."""
    data = request.get_json(silent=True) or {}
    daily_goal = data.get("daily_goal") if isinstance(data, dict) else None
    recipe_category = data.get("recipe_category") if isinstance(data, dict) else None
    selected_model = _selected_ollama_model(data)

    try:
        count = int(data.get("count", 3))
    except (TypeError, ValueError):
        count = 3
    count = max(1, min(count, 5))
    exclude = data.get("exclude") if isinstance(data.get("exclude"), list) else None

    try:
        items = _current_fridge_items()
    except Exception as exc:
        return jsonify({
            "error": f"Kühlschrank konnte nicht geladen werden: {exc}",
            "recipes": [],
        }), 500

    fridge_items = [
        {
            "name": item["name"],
            "amount": item["current_amount"],
            "unit": item.get("unit"),
            "kcal_per_100g": item.get("kcal_per_100g"),
            "protein_per_100g": item.get("protein_per_100g"),
            "fat_per_100g": item.get("fat_per_100g"),
            "carbs_per_100g": item.get("carbs_per_100g"),
        }
        for item in items
    ]
    result = generate_freestyle_recipes(
        fridge_items=fridge_items,
        daily_goal=daily_goal,
        recipe_category=recipe_category,
        model=selected_model,
        count=count,
        exclude=exclude,
    )
    return jsonify(result)


@asaai_bp.route("/ui/planner")
def planner_ui():
    return render_template("asaai/planner.html")
