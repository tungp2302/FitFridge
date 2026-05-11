"""JSON API endpoints for FitFridge MVP."""

import functools

from flask import Blueprint, g, jsonify, request

from .fridge_service import (
    calculate_total_nutrition,
    create_dashboard_item,
    delete_dashboard_item,
    get_dashboard_item,
    list_dashboard_items,
    update_dashboard_item,
)

bp = Blueprint("api", __name__, url_prefix="/api")


def api_login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return jsonify({"error": "authentication required"}), 401
        return view(**kwargs)

    return wrapped_view


@bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@bp.get("/fridge")
def list_fridge_items():
    rows = list_dashboard_items()
    result = []
    for row in rows:
        item = dict(row)
        item.update(calculate_total_nutrition(item))
        result.append(item)
    return jsonify(result), 200


@bp.get("/fridge/<int:item_id>")
def fridge_item_detail(item_id):
    row = get_dashboard_item(item_id)
    if row is None:
        return jsonify({"error": "item not found"}), 404

    item = dict(row)
    item.update(calculate_total_nutrition(item))
    return jsonify(item), 200


@bp.post("/fridge")
@api_login_required
def add_fridge_item():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()

    if not query:
        return jsonify({"error": "query is required"}), 400

    try:
        item_id = create_dashboard_item(query, g.user["id"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError:
        return jsonify({"error": "OpenFoodFacts lookup failed"}), 502

    row = get_dashboard_item(item_id)
    item = dict(row)
    item.update(calculate_total_nutrition(item))
    return jsonify(item), 201


@bp.put("/fridge/<int:item_id>")
@api_login_required
def update_fridge_item(item_id):
    if get_dashboard_item(item_id) is None:
        return jsonify({"error": "item not found"}), 404

    payload = request.get_json(silent=True) or {}

    current_amount = payload.get("current_amount")
    unit = payload.get("unit")
    name = payload.get("name")
    brand = payload.get("brand")

    if current_amount is not None:
        try:
            current_amount = float(current_amount)
        except (TypeError, ValueError):
            return jsonify({"error": "current_amount must be a number"}), 400
        if current_amount < 0:
            return jsonify({"error": "current_amount must be >= 0"}), 400

    update_dashboard_item(
        item_id=item_id,
        current_amount=current_amount,
        unit=unit,
        name=name,
        brand=brand,
    )

    row = get_dashboard_item(item_id)
    item = dict(row)
    item.update(calculate_total_nutrition(item))
    return jsonify(item), 200


@bp.delete("/fridge/<int:item_id>")
@api_login_required
def remove_fridge_item(item_id):
    if get_dashboard_item(item_id) is None:
        return jsonify({"error": "item not found"}), 404

    delete_dashboard_item(item_id)
    return jsonify({"deleted": True, "id": item_id}), 200