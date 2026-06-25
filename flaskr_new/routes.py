"""Frontend-Routen"""

import calendar as _calendar
import functools
import json
from datetime import date as _date

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

from .calculations import safe_float
from .db import get_db
from .meal_tracker_repo import (
    delete_meal_entry,
    get_day_meals,
    get_day_totals,
    get_settings,
    get_tracked_days,
    update_meal_entry_amount,
)
from .meal_tracker_service import (
    build_daily_summary,
    commit_meal_cart,
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
from .asaai.app_settings_repo import (
    get_settings as get_app_settings,
    save_settings as save_app_settings,
)
from .asaai.ollama_client import OLLAMA_MODEL_CHOICES, resolve_ollama_model, test_ollama_model
from .asaai.food_estimate import estimate_food

bp = Blueprint("frontend", __name__, template_folder="templates", static_folder="static")


def _form_value(name, cast):
    try:
        return cast(request.form[name])
    except (KeyError, TypeError, ValueError):
        return None


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
    g.user = (
        None
        if user_id is None
        else get_db().execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone()
    )


@bp.route("/", methods=("GET", "POST"))
def dashboard():
    if g.user is not None and request.method == "POST":
        try:
            update_dashboard_item(
                request.form.get("item_id"),
                current_amount=request.form.get("current_amount"),
                grams_per_piece=request.form.get("grams_per_piece"),
                user_id=g.user["id"],
            )
        except ValueError:
            flash("Eintrag wurde nicht gefunden.")
        return redirect(url_for("frontend.dashboard"))

    posts = [] if g.user is None else [dict(item) for item in list_items(g.user["id"])]
    posts = [{**item, **calculate_total_nutrition(item)} for item in posts]

    totals = {key: round(sum(float(item.get(f"total_{key}") or 0) for item in posts), 1)
              for key in ("kcal", "protein", "carbs", "fat")}
    totals["item_count"] = len(posts)

    return render_template("fridge/dashboard.html", posts=posts, overview={"totals": totals})


@bp.route("/settings", methods=("GET", "POST"))
@login_required
def settings():
    llm_test = None

    if request.method == "POST":
        selected_model = resolve_ollama_model(request.form.get("llm_model"))
        if selected_model not in {choice["name"] for choice in OLLAMA_MODEL_CHOICES}:
            flash("Unbekanntes LLM-Modell.")
        else:
            save_app_settings(g.user["id"], llm_model=selected_model)
            if request.form.get("action") == "test_llm":
                try:
                    llm_test = test_ollama_model(selected_model)
                    if llm_test["ok"]:
                        flash(f"LLM-Test erfolgreich: {selected_model} antwortet.")
                    else:
                        flash(f"LLM-Test fehlgeschlagen: {selected_model} antwortet nicht.")
                except Exception as exc:
                    llm_test = {
                        "ok": False,
                        "model": selected_model,
                        "error": str(exc),
                    }
                    flash(f"LLM-Test fehlgeschlagen: {exc}")
            else:
                flash("Einstellungen gespeichert.")

    return render_template(
        "settings.html",
        settings=get_app_settings(g.user["id"]),
        model_choices=OLLAMA_MODEL_CHOICES,
        llm_test=llm_test,
    )


@bp.route("/meal-tracker", methods=("GET", "POST"))
@login_required
def meal_tracker():
    user_id = g.user["id"]
    cart = session.get("meal_cart", [])

    if request.method == "POST":
        action = request.form.get("action")
        tab = request.form.get("tab", "product")

        if action == "delete_meal":
            entry_id = _form_value("meal_entry_id", int)
            deleted = entry_id is not None and delete_meal_entry(entry_id, user_id)
            flash("Mahlzeit geloescht." if deleted else "Mahlzeit konnte nicht geloescht werden.")
            return redirect(url_for("frontend.meal_tracker"))
        elif action == "edit_meal_amount":
            entry_id = _form_value("meal_entry_id", int)
            new_amount = _form_value("new_amount", float)
            updated = None not in (entry_id, new_amount) and update_meal_entry_amount(
                entry_id, user_id, new_amount
            )
            flash("Menge aktualisiert." if updated else "Neue Menge konnte nicht gespeichert werden.")
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
                amount = safe_float(value, 0.0)
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
            amount = safe_float(request.form.get("amount"), 0.0)
            try:
                product = json.loads(request.form.get("selected_payload", ""))
            except json.JSONDecodeError:
                product = None
            if not isinstance(product, dict):
                flash("Produkt konnte nicht gelesen werden.")
            elif amount <= 0:
                flash("Bitte eine Menge groesser als 0 angeben.")
            else:
                entry = {k: product.get(k) for k in _RESULT_KEYS}
                entry.update(kind="product", unit=product.get("unit") or "g",
                             amount=amount, remaining_amount=safe_float(request.form.get("remaining_amount"), 0.0))
                cart.append(entry)
            session["meal_cart"] = cart
            return redirect(url_for("frontend.meal_tracker", modal="add", tab="product"))
        elif action == "cart_remove":
            idx = _form_value("index", int)
            if idx is not None and 0 <= idx < len(cart):
                cart.pop(idx)
            session["meal_cart"] = cart
            return redirect(url_for("frontend.meal_tracker", modal="add", tab=tab))

    # Die ganze Seite zeigt einen Tag (Default heute); der Kalender waehlt ihn aus.
    today = _date.today()
    try:
        the_date = _date.fromisoformat(request.args.get("date") or "").isoformat()
    except ValueError:
        the_date = today.isoformat()
    settings = get_settings(user_id)
    recent_meals = get_day_meals(user_id, the_date)
    consumed = get_day_totals(user_id, the_date)
    summary = build_daily_summary(settings, consumed)

    modal = request.args.get("modal")          # 'add' | 'settings' | None
    tab = request.args.get("tab", "product")   # 'product' | 'fridge'
    query = request.args.get("q", "").strip()
    results = unified_search(query) if (modal == "add" and tab == "product" and query) else None
    fridge_items = [dict(item) for item in list_items(user_id=user_id)] if modal == "add" else []

    # Kalender-Monatsraster (stdlib), Default = Monat des gewaehlten Tags.
    try:
        cy = int(request.args.get("cal_year", the_date[:4]))
        cm = int(request.args.get("cal_month", the_date[5:7]))
    except ValueError:
        cy, cm = today.year, today.month
    first_weekday, days = _calendar.monthrange(cy, cm)  # Mo=0
    cal = {
        "year": cy, "month": cm, "first_weekday": first_weekday, "days": days,
        "tracked": get_tracked_days(user_id, cy, cm),
        "today": today.isoformat(), "selected": the_date,
        "open": bool(request.args.get("date") or request.args.get("cal_month")),
        "prev": (cy - 1, 12) if cm == 1 else (cy, cm - 1),
        "next": (cy + 1, 1) if cm == 12 else (cy, cm + 1),
    }

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
        cal=cal,
    )


@bp.route("/fridge/add", methods=("GET", "POST"))
@login_required
def add_product():
    results = None
    query = ""

    if request.method == "POST":
        action = request.form.get("action")
        query = request.form.get("query", "").strip()
        selected_payload_raw = request.form.get("selected_payload", "").strip()

        if action == "search" and query:
            results = unified_search(query)
        elif action == "search" or not (query or selected_payload_raw):
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

    if q.isdigit():
        try:
            product = search_product(q)
        except (RuntimeError, ValueError):
            return []
        return [_to_result(product)] if product and product.get("name") else []

    results, seen_barcodes = [], set()

    def add(item):
        result = _to_result(item)
        barcode = result["barcode"]
        if not barcode or barcode not in seen_barcodes:
            results.append(result)
            seen_barcodes.add(barcode)

    if estimate := estimate_food(q):
        results.append(_to_result(estimate))

    for item in map(dict, search_by_name(q, limit=10)):
        add(item)
    for item in search_products(q):
        add(item)

    return results


_RESULT_KEYS = ("name", "brand", "barcode", "kcal_per_100g", "protein_per_100g",
                 "fat_per_100g", "carbs_per_100g", "total_amount", "unit", "grams_per_piece")

def _to_result(item):
    """Vereinheitlicht ein Produkt-Dict zu den Feldern, die das Frontend nutzt."""
    r = {k: item.get(k) for k in _RESULT_KEYS}
    r["barcode"] = r["barcode"] or ""
    return r


@bp.route("/fridge/<int:item_id>/delete", methods=("POST",))
@login_required
def delete_product(item_id):
    if get_item(item_id, user_id=g.user["id"]) is None:
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
        user = get_db().execute(
            "SELECT * FROM user WHERE username = ?", (username,)
        ).fetchone()

        if user is None:
            flash("Incorrect username.")
        elif not check_password_hash(user["password"], password):
            flash("Incorrect password.")
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("frontend.dashboard"))

    return render_template("auth/login.html")


@bp.route("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("frontend.dashboard"))

