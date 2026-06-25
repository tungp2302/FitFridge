"""HTTP-Routen für den Rezeptplaner."""
import functools
import json

from flask import Blueprint, g, jsonify, render_template, request

from .. import fridge_repo
from ..db import get_db
from .freestyle_recipe import generate_freestyle_recipes
from .ollama_client import resolve_ollama_model


asaai_bp = Blueprint("asaai", __name__, url_prefix="/asaai")


def require_user(view):
    """JSON-401 statt Redirect, wenn kein Nutzer angemeldet ist."""
    @functools.wraps(view)
    def wrapped(**kwargs):
        if getattr(g, "user", None) is None:
            return jsonify({"error": "Anmeldung erforderlich.", "recipes": []}), 401
        return view(**kwargs)
    return wrapped


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
@require_user
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

    items = _current_fridge_items()  # swallows DB errors -> [] selbst
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


@asaai_bp.route("/recipes/saved", methods=("GET", "POST"))
@require_user
def saved_recipes():
    """List the user's saved recipes (GET) or store one (POST)."""
    user = g.user
    db = get_db()

    if request.method == "POST":
        recipe = request.get_json(silent=True)
        if not isinstance(recipe, dict):
            return jsonify({"error": "Ungültiges Rezept."}), 400
        db.execute(
            "INSERT INTO saved_recipe (user_id, title, data) VALUES (?, ?, ?)",
            (user["id"], recipe.get("title") or "Freestyle-Rezept", json.dumps(recipe)),
        )
        db.commit()

    rows = db.execute(
        "SELECT id, title, data FROM saved_recipe WHERE user_id = ? ORDER BY created DESC",
        (user["id"],),
    ).fetchall()
    # title-Spalte ist maßgeblich (erlaubt Umbenennen ohne den JSON-Blob anzufassen).
    return jsonify({"recipes": [
        {**json.loads(row["data"]), "id": row["id"], "title": row["title"]} for row in rows
    ]})


@asaai_bp.route("/recipes/saved/<int:rid>", methods=("DELETE", "PATCH"))
@require_user
def saved_recipe(rid):
    """Delete a saved recipe or rename it (PATCH with {"title": ...})."""
    user = g.user
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM saved_recipe WHERE id = ? AND user_id = ?", (rid, user["id"]))
    else:
        title = ((request.get_json(silent=True) or {}).get("title") or "").strip()
        if not title:
            return jsonify({"error": "Titel fehlt."}), 400
        db.execute(
            "UPDATE saved_recipe SET title = ? WHERE id = ? AND user_id = ?",
            (title, rid, user["id"]),
        )
    db.commit()
    return jsonify({"ok": True})


@asaai_bp.route("/ui/planner")
def planner_ui():
    return render_template("asaai/planner.html")
