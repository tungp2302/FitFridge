"""Frontend-Routen fuer FitFridge."""

import functools

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.exceptions import abort
from werkzeug.security import check_password_hash, generate_password_hash

from flaskr.api_db.db import get_db
from flaskr.backend.services.fridge_service import (
    create_dashboard_item,
    delete_dashboard_item,
    get_dashboard_item,
    list_dashboard_items,
    update_dashboard_item,
)

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
    posts = list_dashboard_items()
    return render_template("fridge/dashboard.html", posts=posts)


@bp.route("/fridge/<int:item_id>", methods=("GET", "POST"))
@login_required
def product_detail(item_id):
    post = get_dashboard_item(item_id)

    if post is None:
        abort(404, f"Item id {item_id} doesn't exist.")

    if g.user["id"] != post["author_id"]:
        abort(403)

    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        error = None

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            update_dashboard_item(item_id, title, body)
            return redirect(url_for("frontend.dashboard"))

    return render_template("fridge/product_detail.html", post=post)


@bp.route("/fridge/add", methods=("GET", "POST"))
@login_required
def add_product():
    if request.method == "POST":
        title = request.form["title"]
        body = request.form["body"]
        error = None

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            create_dashboard_item(title, body, g.user["id"])
            return redirect(url_for("frontend.dashboard"))

    return render_template("fridge/add_product.html")


@bp.route("/fridge/<int:item_id>/delete", methods=("POST",))
@login_required
def delete_product(item_id):
    post = get_dashboard_item(item_id)

    if post is None:
        abort(404, f"Item id {item_id} doesn't exist.")

    if g.user["id"] != post["author_id"]:
        abort(403)

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
