"""Frontend-Routen"""

import functools
import json

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.exceptions import abort
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .meal_tracker_service import (
    build_daily_summary,
    delete_meal_action,
    edit_meal_amount_action,
    get_today_meals,
    get_settings,
    get_today_totals,
    save_settings_action,
    track_meal_from_form,
    track_meals_from_payload,
)
from .fridge_service import (
    calculate_total_nutrition,
    consume_amount,
    create_dashboard_item,
    create_dashboard_item_from_data,
    delete_dashboard_item,
    get_dashboard_item,
    list_dashboard_items,
    refill_amount,
    update_dashboard_item,
)
from .openfoodfacts_client import search_product, search_products
from .product_repo import search_by_name

bp = Blueprint("frontend", __name__, template_folder="templates", static_folder="static")


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("frontend.login"))

        return view(**kwargs)

    return wrapped_view


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone()


@bp.route("/")
def dashboard():
    if g.user is None:
        posts = []
    else:
        posts = list_dashboard_items(g.user["id"])
    # Calculate total nutrition for each item based on current_amount
    posts_with_nutrition = []
    for post in posts:
        post_dict = dict(post)
        nutrition = calculate_total_nutrition(post_dict)
        post_dict.update(nutrition)
        posts_with_nutrition.append(post_dict)

    totals = {
        "kcal": round(sum(float(item.get("total_kcal", 0.0) or 0.0) for item in posts_with_nutrition), 1),
        "protein": round(sum(float(item.get("total_protein", 0.0) or 0.0) for item in posts_with_nutrition), 1),
        "carbs": round(sum(float(item.get("total_carbs", 0.0) or 0.0) for item in posts_with_nutrition), 1),
        "fat": round(sum(float(item.get("total_fat", 0.0) or 0.0) for item in posts_with_nutrition), 1),
        "item_count": len(posts_with_nutrition),
    }

    # Keine Zielvorgaben im Kuehlschrank -> die Ringe werden im Template voll
    # gezeichnet, hier brauchen wir nur die Gesamtsummen.
    overview = {"totals": totals}

    return render_template("fridge/dashboard.html", posts=posts_with_nutrition, overview=overview)


@bp.route("/meal-tracker", methods=("GET", "POST"))
@login_required
def meal_tracker():
    flash_message = None

    if request.method == "POST":
        user_id = g.user["id"]
        action = request.form.get("action")

        if action == "save_settings":
            flash_message = save_settings_action(user_id, request.form)
        elif action == "delete_meal":
            flash_message = delete_meal_action(user_id, request.form.get("meal_entry_id"))
        elif action == "edit_meal_amount":
            flash_message = edit_meal_amount_action(
                user_id,
                request.form.get("meal_entry_id"),
                request.form.get("new_amount"),
            )
        elif action == "track_meal":
            selected_payload_raw = request.form.get("selected_payload", "").strip()
            if selected_payload_raw:
                flash_message = track_meals_from_payload(user_id, selected_payload_raw)
            else:
                flash_message = track_meal_from_form(user_id, request.form)

    settings = get_settings(g.user["id"])
    recent_meals = get_today_meals(g.user["id"])
    consumed = get_today_totals(g.user["id"])
    summary = build_daily_summary(settings, consumed)
    fridge_items = [dict(item) for item in list_dashboard_items(g.user["id"])]

    if flash_message:
        flash(flash_message)

    return render_template(
        "fridge/meal_tracker.html",
        settings=settings,
        consumed=consumed,
        summary=summary,
        recent_meals=recent_meals,
        fridge_items=fridge_items,
    )


@bp.route("/fridge/<int:item_id>", methods=("GET", "POST"))
@login_required
def product_detail(item_id):
    post = get_dashboard_item(item_id, g.user["id"])

    if post is None:
        abort(404, f"Item id {item_id} doesn't exist.")

    # Calculate total nutrition based on current_amount
    post = dict(post)
    nutrition = calculate_total_nutrition(post)
    post.update(nutrition)

    if request.method == "POST":
        name = request.form.get("name")
        brand = request.form.get("brand")
        current_amount = request.form.get("current_amount")
        unit = request.form.get("unit")
        error = None

        if not name:
            error = "Name is required."

        if error is not None:
            flash(error)
        else:
            # update amount and optional product metadata
            update_dashboard_item(
                item_id,
                current_amount=current_amount,
                unit=unit,
                name=name,
                brand=brand,
                user_id=g.user["id"],
            )
            return redirect(url_for("frontend.dashboard"))

    return render_template("fridge/product_detail.html", post=post)


@bp.route("/fridge/add", methods=("GET", "POST"))
@login_required
def add_product():
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        selected_payload_raw = request.form.get("selected_payload", "").strip()
        error = None

        if not query and not selected_payload_raw:
            error = "Barcode or product name is required."

        if error is not None:
            flash(error)
        else:
            try:
                if selected_payload_raw:
                    selected_payload = json.loads(selected_payload_raw)
                    create_dashboard_item_from_data(selected_payload, g.user["id"])
                else:
                    create_dashboard_item(query, g.user["id"])
                return redirect(url_for("frontend.dashboard"))
            except json.JSONDecodeError:
                flash("Selected product data could not be parsed.")
            except ValueError as exc:
                flash(str(exc))
            except RuntimeError:
                flash("OpenFoodFacts lookup failed. Please try again.")

    return render_template("fridge/add_product.html")


@bp.route("/api/products/search")
@login_required
def api_products_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    # Barcode (nur Ziffern): direkt die OFF-Barcode-API nutzen.
    if q.isdigit():
        try:
            product = search_product(q)
        except (RuntimeError, ValueError) as exc:
            current_app.logger.warning("OFF-Barcode-Lookup fehlgeschlagen: %s", exc)
            product = None
        if not product or not product.get("name"):
            return jsonify([])
        return jsonify([_to_result(product)])

    # Text-Suche: erst lokale Treffer aus der DB, dann die OFF-Textsuche.
    # search_products faengt Netzfehler selbst ab und liefert dann [].
    results = []
    seen_barcodes = set()

    def add(item):
        barcode = item.get("barcode") or ""
        if barcode and barcode in seen_barcodes:
            return
        if barcode:
            seen_barcodes.add(barcode)
        results.append(_to_result(item))

    for r in search_by_name(q, limit=10):
        add({"name": r[1], "brand": r[2], "barcode": r[3], "kcal_per_100g": r[4]})

    for item in search_products(q):
        add(item)

    return jsonify(results)


def _to_result(item):
    """Vereinheitlicht ein Produkt-Dict zu den Feldern, die das Frontend nutzt."""
    return {
        "name": item.get("name"),
        "brand": item.get("brand"),
        "barcode": item.get("barcode") or "",
        "kcal_per_100g": item.get("kcal_per_100g"),
        "protein_per_100g": item.get("protein_per_100g"),
        "fat_per_100g": item.get("fat_per_100g"),
        "carbs_per_100g": item.get("carbs_per_100g"),
        "total_amount": item.get("total_amount"),
        "unit": item.get("unit"),
    }


@bp.route("/fridge/<int:item_id>/delete", methods=("POST",))
@login_required
def delete_product(item_id):
    post = get_dashboard_item(item_id, g.user["id"])

    if post is None:
        abort(404, f"Item id {item_id} doesn't exist.")

    delete_dashboard_item(item_id)
    return redirect(url_for("frontend.dashboard"))


@bp.route("/auth/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."

        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                return redirect(url_for("frontend.login"))

        flash(error)

    return render_template("auth/register.html")


@bp.route("/auth/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        error = None
        user = db.execute(
            "SELECT * FROM user WHERE username = ?", (username,)
        ).fetchone()

        if user is None:
            error = "Incorrect username."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("frontend.dashboard"))

        flash(error)

    return render_template("auth/login.html")


@bp.route("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("frontend.dashboard"))

def _parse_amount_input(amount_raw):
    """Prueft eine Mengen-Eingabe (Zahl > 0, max 10000, Komma erlaubt).

    Liefert (amount, None, None) oder (None, fehlermeldung, flash_kategorie).
    """
    amount_raw = (amount_raw or "").strip()

    if not amount_raw:
        return None, "Bitte gib eine Menge an.", "error"

    # Komma durch Punkt ersetzen (deutsche Eingabe)
    amount_raw = amount_raw.replace(",", ".")

    try:
        amount = float(amount_raw)
    except ValueError:
        return None, f"'{amount_raw}' ist keine gültige Zahl.", "error"

    if amount <= 0:
        return None, "Die Menge muss größer als 0 sein.", "error"

    if amount > 10000:
        return (
            None,
            f"Die Menge {amount} scheint sehr hoch. Bitte prüfe deine Eingabe (max. 10000).",
            "warning",
        )

    return amount, None, None


def _handle_amount_change(item_id, service_fn):
    """Gemeinsamer Ablauf fuer consume/refill: validieren, Service, Flash."""
    amount, error, category = _parse_amount_input(request.form.get("amount", ""))
    if error is not None:
        flash(error, category)
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    result = service_fn(item_id, amount, user_id=g.user["id"])
    flash(result["message"], "success" if result["success"] else "error")
    return redirect(url_for("frontend.product_detail", item_id=item_id))


@bp.route("/fridge/<int:item_id>/consume", methods=("POST",))
@login_required
def consume_product(item_id):
    """Verbraucht eine Menge eines Fridge-Items."""
    return _handle_amount_change(item_id, consume_amount)


@bp.route("/fridge/<int:item_id>/refill", methods=("POST",))
@login_required
def refill_product(item_id):
    """Füllt eine Menge zu einem Fridge-Item hinzu."""
    return _handle_amount_change(item_id, refill_amount)
