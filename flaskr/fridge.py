from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db
from . import off_client
from . import product_repo

bp = Blueprint('fridge', __name__,)

@bp.route('/viewFridge')
def viewFridge():
    db = get_db()
    products = db.execute(
        "SELECT f.id, f.product_id, f.current_amount, f.unit, f.created,"
        " p.name, p.brand, p.barcode,"
        " p.kcal_per_100g, p.protein_per_100g, p.fat_per_100g, p.carbs_per_100g"
        " FROM fridge_item f JOIN product p ON f.product_id = p.barcode"
        " ORDER BY f.created DESC"
    ).fetchall()
    return render_template('fridge/viewFridge.html', products=products)

@bp.route('/addfood', methods=('GET', 'POST'))
@login_required
def addfood():
    if request.method == 'POST':
        product_id = request.form['product_id']
        current_amount = request.form['amount']
        unit = request.form['unit']
        error = None

        if not product_id:
            error = 'Product ID is required.'

        if error is not None:
            flash(error)
        else:
            off_client.search_product_add_db(product_id)
            db = get_db()
            db.execute(
            'INSERT INTO fridge_item (product_id, current_amount, unit)'
            ' VALUES (?, ?, ?)',
            (product_id, current_amount, unit)
            )
            db.commit()
            return redirect(url_for('fridge.viewFridge'))

    return render_template('fridge/addfood.html')

def get_item(item_id):
    """Ein spezifisches FridgeItem mit Produktdetails abrufen."""
    return get_db().execute(
        "SELECT f.id, f.product_id, f.current_amount, f.unit, f.created,"
        " p.name, p.brand, p.barcode,"
        " p.kcal_per_100g, p.protein_per_100g, p.fat_per_100g, p.carbs_per_100g"
        " FROM fridge_item f JOIN product p ON f.product_id = p.id"
        " WHERE f.id = ?",
        (item_id,),
    ).fetchone()


def add_item(product_id, current_amount, unit):
    """Ein neues FridgeItem zur Datenbank hinzufügen."""
    db = get_db()
    db.execute(
        "INSERT INTO fridge_item (product_id, current_amount, unit)"
        " VALUES (?, ?, ?)",
        (product_id, current_amount, unit),
    )
    db.commit()


def update_amount(item_id, current_amount):
    """Die Menge eines FridgeItems aktualisieren."""
    db = get_db()
    db.execute(
        "UPDATE fridge_item SET current_amount = ? WHERE id = ?",
        (current_amount, item_id),
    )
    db.commit()


def delete_item(item_id):
    """Ein FridgeItem aus dem Kühlschrank entfernen."""
    db = get_db()
    db.execute("DELETE FROM fridge_item WHERE id = ?", (item_id,))
    db.commit()