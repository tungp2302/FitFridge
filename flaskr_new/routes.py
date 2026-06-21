"""Frontend-Routen"""

import functools
import json

from flask import (
    Blueprint,
    flash,
    g,
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
    commit_meal_cart,
    delete_meal_action,
    edit_meal_amount_action,
    get_today_meals,
    get_settings,
    get_today_totals,
    save_settings_action,
)
from .fridge_repo import delete_item as delete_dashboard_item, get_item, list_items
from .fridge_service import (
    calculate_total_nutrition,
    create_dashboard_item,
    create_dashboard_item_from_data,
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


@bp.route("/", methods=("GET", "POST"))
def dashboard():
    if g.user is not None and request.method == "POST":
        update_dashboard_item(
            request.form.get("item_id"),
            current_amount=request.form.get("current_amount"),
            user_id=g.user["id"],
        )
        return redirect(url_for("frontend.dashboard"))

    if g.user is None:
        posts = []
    else:
        posts = list_items(user_id=g.user["id"])
    posts_with_nutrition = []
    for post in posts:
        d = {**dict(post), **calculate_total_nutrition(dict(post))}
        posts_with_nutrition.append(d)

    totals = {key: round(sum(float(item.get(f"total_{key}", 0) or 0) for item in posts_with_nutrition), 1)
              for key in ("kcal", "protein", "carbs", "fat")}
    totals["item_count"] = len(posts_with_nutrition)
    overview = {"totals": totals}

    return render_template("fridge/dashboard.html", posts=posts_with_nutrition, overview=overview)


@bp.route("/meal-tracker", methods=("GET", "POST"))
@login_required
def meal_tracker():
    user_id = g.user["id"]
    cart = session.get("meal_cart", [])

    if request.method == "POST":
        action = request.form.get("action")
        tab = request.form.get("tab", "product")

        if action == "delete_meal":
            flash(delete_meal_action(user_id, request.form.get("meal_entry_id")))
            return redirect(url_for("frontend.meal_tracker"))
        elif action == "edit_meal_amount":
            flash(edit_meal_amount_action(user_id, request.form.get("meal_entry_id"), request.form.get("new_amount")))
            return redirect(url_for("frontend.meal_tracker"))
        elif action == "save_settings":
            flash(save_settings_action(user_id, request.form))
            return redirect(url_for("frontend.meal_tracker"))
        elif action == "cart_commit":
            flash(commit_meal_cart(user_id, cart))
            session["meal_cart"] = []
            return redirect(url_for("frontend.meal_tracker"))
        elif action == "cart_add_fridge":
            added = 0
            for key, value in request.form.items():
                if not key.startswith("amount_"):
                    continue
                amount = _cart_float(value)
                if amount <= 0:
                    continue
                fridge_item = get_item(key[len("amount_"):], user_id=user_id)
                if fridge_item is None:
                    continue
                cart.append({"kind": "fridge", "fridge_item_id": fridge_item["id"],
                             "name": fridge_item["name"], "unit": fridge_item["unit"], "amount": amount})
                added += 1
            if added == 0:
                flash("Bitte bei mindestens einem Produkt eine Menge groesser als 0 angeben.")
            session["meal_cart"] = cart
            return redirect(url_for("frontend.meal_tracker", modal="add", tab="fridge"))
        elif action == "cart_add_product":
            amount = _cart_float(request.form.get("amount"))
            try:
                product = json.loads(request.form.get("selected_payload", ""))
            except json.JSONDecodeError:
                product = None
            if not isinstance(product, dict):
                flash("Produkt konnte nicht gelesen werden.")
            elif amount <= 0:
                flash("Bitte eine Menge groesser als 0 angeben.")
            else:
                entry = {k: product.get(k) for k in _CART_PRODUCT_KEYS}
                entry.update(kind="product", unit=product.get("unit") or "g",
                             amount=amount, remaining_amount=_cart_float(request.form.get("remaining_amount")))
                cart.append(entry)
            session["meal_cart"] = cart
            return redirect(url_for("frontend.meal_tracker", modal="add", tab="product"))
        elif action == "cart_remove":
            try:
                idx = int(request.form.get("index", "-1"))
            except ValueError:
                idx = -1
            if 0 <= idx < len(cart):
                cart.pop(idx)
            session["meal_cart"] = cart
            return redirect(url_for("frontend.meal_tracker", modal="add", tab=tab))

    settings = get_settings(user_id)
    recent_meals = get_today_meals(user_id)
    consumed = get_today_totals(user_id)
    summary = build_daily_summary(settings, consumed)

    modal = request.args.get("modal")          # 'add' | 'settings' | None
    tab = request.args.get("tab", "product")   # 'product' | 'fridge'
    query = request.args.get("q", "").strip()
    results = unified_search(query) if (modal == "add" and tab == "product" and query) else None
    fridge_items = [dict(item) for item in list_items(user_id=user_id)] if modal == "add" else []

    return render_template(
        "fridge/meal_tracker.html",
        settings=settings,
        consumed=consumed,
        summary=summary,
        recent_meals=recent_meals,
        modal=modal,
        tab=tab,
        query=query,
        results=results,
        fridge_items=fridge_items,
        cart=cart,
    )


_CART_PRODUCT_KEYS = ("name", "brand", "barcode", "kcal_per_100g",
                      "protein_per_100g", "fat_per_100g", "carbs_per_100g", "unit")


def _cart_float(value):
    try:
        return float((value or "").replace(",", ".")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return 0.0


@bp.route("/fridge/add", methods=("GET", "POST"))
@login_required
def add_product():
    results = None
    query = ""

    if request.method == "POST":
        action = request.form.get("action")
        query = request.form.get("query", "").strip()
        selected_payload_raw = request.form.get("selected_payload", "").strip()

        if action == "search":
            if query:
                results = unified_search(query)
            else:
                flash("Barcode or product name is required.")
        elif not query and not selected_payload_raw:
            flash("Barcode or product name is required.")
        else:
            try:
                if selected_payload_raw:
                    create_dashboard_item_from_data(json.loads(selected_payload_raw), g.user["id"])
                else:
                    create_dashboard_item(query, g.user["id"])
                return redirect(url_for("frontend.dashboard"))
            except json.JSONDecodeError:
                flash("Selected product data could not be parsed.")
            except ValueError as exc:
                flash(str(exc))
            except RuntimeError:
                flash("OpenFoodFacts lookup failed. Please try again.")

    return render_template("fridge/add_product.html", results=results, query=query)


def unified_search(q):
    """Sucht Produkte (Barcode oder Text) und liefert eine Liste von Result-Dicts."""
    q = (q or "").strip()
    if not q:
        return []

    # Barcode (nur Ziffern): direkt die OFF-Barcode-API nutzen.
    if q.isdigit():
        try:
            product = search_product(q)
        except (RuntimeError, ValueError):
            product = None
        if not product or not product.get("name"):
            return []
        return [_to_result(product)]

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
        add(dict(r))

    for item in search_products(q):
        add(item)

    return results


_RESULT_KEYS = ("name", "brand", "barcode", "kcal_per_100g", "protein_per_100g",
                 "fat_per_100g", "carbs_per_100g", "total_amount", "unit")

def _to_result(item):
    """Vereinheitlicht ein Produkt-Dict zu den Feldern, die das Frontend nutzt."""
    r = {k: item.get(k) for k in _RESULT_KEYS}
    r["barcode"] = r["barcode"] or ""
    return r


@bp.route("/fridge/<int:item_id>/delete", methods=("POST",))
@login_required
def delete_product(item_id):
    post = get_item(item_id, user_id=g.user["id"])

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

