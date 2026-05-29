"""Frontend-Routen fuer FitFridge."""

import functools

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.exceptions import abort
from werkzeug.security import check_password_hash, generate_password_hash

from .asaai.local_insight import generate_ai_insight
from .consumption_log_repo import get_recent_events
from .db import get_db
from .meal_tracker_service import (
    add_meal_entry,
    build_daily_summary,
    get_recent_meals,
    get_settings,
    get_today_totals,
    log_meal_from_product,
    normalize_macro_percentages,
    resolve_product_from_barcode,
    save_settings,
)
from .fridge_service import (
    calculate_total_nutrition,
    create_dashboard_item,
    delete_dashboard_item,
    get_dashboard_item,
    list_dashboard_items,
    update_dashboard_item,
)
from .openfoodfacts_client import search_products
from .product_repo import search_by_name
from flask import jsonify

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
    return render_template("fridge/dashboard.html", posts=posts_with_nutrition)


def _build_insight_fallback(consumption_history, fridge_items):
    refill_count = sum(1 for entry in consumption_history if entry.get("event_type") == "refill")
    item_count = len(fridge_items)

    if not consumption_history and not fridge_items:
        return "Noch keine Zugaenge vorhanden. Sobald du etwas auffuellst oder neu in den Kuehlschrank legst, zeigt dir ASaAI hier ein lokales Insight an."

    return (
        "ASaAI konnte kein lokales Zugangs-Insight erzeugen oder der Ollama-Server antwortet nicht. "
        f"Aktuell sind {item_count} Fridge-Items und {refill_count} Zugaenge/Auffuellungen vorhanden. "
        "Verbrauch wird separat ausgewertet."
    )


@bp.route("/asaai/insight")
@login_required
def asaai_insight():
    fridge_items = [dict(item) for item in list_dashboard_items(g.user["id"])]
    recent_events = get_recent_events(days=30, limit=50)
    addition_history = [entry for entry in recent_events if entry.get("event_type") == "refill"]
    consumption_events = [entry for entry in recent_events if entry.get("event_type") == "consume"]
    debug_live = request.args.get("debug_live") == "1"

    source = "ollama"
    try:
        insight = generate_ai_insight(addition_history, fridge_items)
        if not insight:
            insight = _build_insight_fallback(addition_history, fridge_items)
            source = "fallback"
    except Exception as exc:
        if debug_live:
            return {
                "source": "error",
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                "addition_count": len(addition_history),
                "consumption_count": len(consumption_events),
                "fridge_item_count": len(fridge_items),
            }, 500
        insight = _build_insight_fallback(addition_history, fridge_items)
        source = "fallback"

    if request.args.get("format") == "json":
        return {
            "source": source,
            "insight": insight,
            "addition_count": len(addition_history),
            "consumption_count": len(consumption_events),
            "fridge_item_count": len(fridge_items),
        }

    return render_template(
        "fridge/insight.html",
        insight=insight,
        source=source,
        addition_history=addition_history,
        consumption_events=consumption_events,
        fridge_items=fridge_items,
    )


@bp.route("/meal-tracker", methods=("GET", "POST"))
@login_required
def meal_tracker():
    settings = get_settings(g.user["id"])
    flash_message = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_settings":
            daily_kcal = float(request.form.get("daily_kcal") or settings["daily_kcal"])
            protein_pct = float(request.form.get("protein_pct") or settings["protein_pct"])
            carbs_pct = float(request.form.get("carbs_pct") or settings["carbs_pct"])
            fat_pct = float(request.form.get("fat_pct") or settings["fat_pct"])
            normalized = normalize_macro_percentages(protein_pct, carbs_pct, fat_pct)
            save_settings(
                g.user["id"],
                daily_kcal=daily_kcal,
                protein_pct=normalized["protein_pct"],
                carbs_pct=normalized["carbs_pct"],
                fat_pct=normalized["fat_pct"],
            )
            flash_message = "Tagesziel und Macroverteilung gespeichert."

        elif action == "track_meal":
            amount = float(request.form.get("amount") or 0)
            if amount <= 0:
                flash_message = "Bitte eine Menge groesser als 0 angeben."
            else:
                fridge_item_id = request.form.get("fridge_item_id")
                barcode = request.form.get("barcode", "").strip()
                selected_product = None
                selected_fridge_item_id = None

                if fridge_item_id:
                    fridge_item = next((item for item in list_dashboard_items() if str(item["id"]) == str(fridge_item_id)), None)
                    if fridge_item is None:
                        flash_message = "Ausgewaehltes Fridge-Item wurde nicht gefunden."
                    else:
                        selected_product = {
                            "id": fridge_item["product_id"],
                            "name": fridge_item["name"],
                            "barcode": fridge_item["barcode"],
                            "kcal_per_100g": fridge_item["kcal_per_100g"],
                            "protein_per_100g": fridge_item["protein_per_100g"],
                            "fat_per_100g": fridge_item["fat_per_100g"],
                            "carbs_per_100g": fridge_item["carbs_per_100g"],
                        }
                        selected_fridge_item_id = fridge_item["id"]
                        unit = fridge_item["unit"]
                elif barcode:
                    selected_product, fridge_item = resolve_product_from_barcode(barcode, g.user["id"])
                    if selected_product is None:
                        flash_message = "Barcode konnte keinem Produkt zugeordnet werden."
                    else:
                        unit = "g"
                        if fridge_item is not None:
                            selected_fridge_item_id = fridge_item["id"]
                            unit = fridge_item["unit"]
                else:
                    flash_message = "Bitte ein Barcode oder ein Fridge-Item auswaehlen."

                if flash_message is None and selected_product is not None:
                    section = request.form.get("meal_section") or request.form.get("section")
                    result = log_meal_from_product(
                        g.user["id"],
                        selected_product,
                        amount,
                        unit,
                        fridge_item_id=selected_fridge_item_id,
                        section=section,
                    )
                    flash_message = (
                        f"{selected_product['name']} mit {amount} {unit} gespeichert."
                        + (" Bestand im Kuehlschrank wurde reduziert." if result["deducted"] else "")
                    )

        settings = get_settings(g.user["id"])

    recent_meals = get_recent_meals(g.user["id"], days=1)
    consumed = get_today_totals(g.user["id"])
    summary = build_daily_summary(settings, consumed)
    fridge_items = [dict(item) for item in list_dashboard_items(g.user["id"])]

    if flash_message:
        flash(flash_message)

    if request.args.get("format") == "json":
        return {
            "settings": settings,
            "consumed": consumed,
            "summary": summary,
            "meal_count": len(recent_meals),
        }

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
        barcode = request.form.get("barcode")
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
        error = None

        if not query:
            error = "Barcode or product name is required."

        if error is not None:
            flash(error)
        else:
            try:
                create_dashboard_item(query, g.user["id"])
                return redirect(url_for("frontend.dashboard"))
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
    # First try local DB matches
    local = []
    try:
        rows = search_by_name(q, limit=10)
        for r in rows:
            local.append(
                {
                    "name": r[1],
                    "brand": r[2],
                    "barcode": r[3],
                    "kcal_per_100g": r[4],
                }
            )
    except Exception:
        local = []

    if local:
        return jsonify(local)

    # Fallback to OpenFoodFacts search
    try:
        results = search_products(q)
    except Exception:
        results = []
    reduced = [
        {
            "name": r.get("name"),
            "brand": r.get("brand"),
            "barcode": r.get("barcode"),
            "kcal_per_100g": r.get("kcal_per_100g"),
        }
        for r in (results or [])
    ]
    return jsonify(reduced)


@bp.route("/api/products/ai")
@login_required
def api_products_ai():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({})

    try:
        from .openfoodfacts_client import ai_estimate

        prod = ai_estimate(q)
    except Exception:
        prod = None

    if not prod:
        return jsonify({})

    reduced = {
        "name": prod.get("name"),
        "brand": prod.get("brand"),
        "barcode": prod.get("barcode"),
        "kcal_per_100g": prod.get("kcal_per_100g"),
        "protein_per_100g": prod.get("protein_per_100g"),
        "fat_per_100g": prod.get("fat_per_100g"),
        "carbs_per_100g": prod.get("carbs_per_100g"),
        "ai": True,
    }
    return jsonify(reduced)


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

@bp.route("/fridge/<int:item_id>/consume", methods=("POST",))
@login_required
def consume_product(item_id):
    """Verbraucht eine Menge eines Fridge-Items.

    Validiert robust:
    - amount muss vorhanden sein
    - amount muss eine Zahl sein
    - amount muss > 0 sein
    - amount muss <= 10000 sein (Tippfehler-Schutz)
    """
    amount_raw = request.form.get("amount", "").strip()

    # Validierung 1: Leere Eingabe
    if not amount_raw:
        flash("Bitte gib eine Menge an.", "error")
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    # Validierung 2: Komma durch Punkt ersetzen (deutsche Eingabe)
    amount_raw = amount_raw.replace(",", ".")

    # Validierung 3: Muss eine Zahl sein
    try:
        amount = float(amount_raw)
    except ValueError:
        flash(f"'{amount_raw}' ist keine gültige Zahl.", "error")
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    # Validierung 4: Muss positiv sein
    if amount <= 0:
        flash("Die Menge muss größer als 0 sein.", "error")
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    # Validierung 5: Plausibilitäts-Check (Tippfehler-Schutz)
    if amount > 10000:
        flash(
            f"Die Menge {amount} scheint sehr hoch. "
            "Bitte prüfe deine Eingabe (max. 10000).",
            "warning"
        )
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    # Alles ok → Service aufrufen
    result = consume_amount(item_id, amount, user_id=g.user["id"])

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["message"], "error")

    return redirect(url_for("frontend.product_detail", item_id=item_id))


@bp.route("/fridge/<int:item_id>/refill", methods=("POST",))
@login_required
def refill_product(item_id):
    """Füllt eine Menge zu einem Fridge-Item hinzu.

    Validiert gleich wie consume_product.
    """
    amount_raw = request.form.get("amount", "").strip()

    if not amount_raw:
        flash("Bitte gib eine Menge an.", "error")
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    amount_raw = amount_raw.replace(",", ".")

    try:
        amount = float(amount_raw)
    except ValueError:
        flash(f"'{amount_raw}' ist keine gültige Zahl.", "error")
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    if amount <= 0:
        flash("Die Menge muss größer als 0 sein.", "error")
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    if amount > 10000:
        flash(
            f"Die Menge {amount} scheint sehr hoch. "
            "Bitte prüfe deine Eingabe (max. 10000).",
            "warning"
        )
        return redirect(url_for("frontend.product_detail", item_id=item_id))

    result = refill_amount(item_id, amount, user_id=g.user["id"])

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["message"], "error")

    return redirect(url_for("frontend.product_detail", item_id=item_id))