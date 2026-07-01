"""Repository Meal Tracker (Tagesziele + Mahlzeiten)."""

from .db import get_db, _iso, _now


DEFAULT_SETTINGS = {
    "daily_kcal": 2000.0,
    "protein_pct": 30.0,
    "carbs_pct": 40.0,
    "fat_pct": 30.0,
}


def get_settings(user_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM meal_tracker_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return {"user_id": user_id, **DEFAULT_SETTINGS}
    return dict(row)


def save_settings(user_id, daily_kcal, protein_pct, carbs_pct, fat_pct):
    db = get_db()
    db.execute(
        "INSERT INTO meal_tracker_settings (user_id, daily_kcal, protein_pct, carbs_pct, fat_pct, updated)"
        " VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(user_id) DO UPDATE SET"
        " daily_kcal=excluded.daily_kcal, protein_pct=excluded.protein_pct,"
        " carbs_pct=excluded.carbs_pct, fat_pct=excluded.fat_pct, updated=excluded.updated",
        (user_id, float(daily_kcal), float(protein_pct), float(carbs_pct), float(fat_pct), _iso(_now())),
    )
    db.commit()


def delete_meal_entry(entry_id, user_id):
    db = get_db()
    result = db.execute(
        "DELETE FROM meal_tracker_entry WHERE id = ? AND user_id = ?",
        (entry_id, user_id),
    )
    db.commit()
    return result.rowcount > 0


def update_meal_entry_amount(entry_id, user_id, new_amount):
    db = get_db()
    row = db.execute(
        "SELECT amount, kcal, protein_g, carbs_g, fat_g FROM meal_tracker_entry WHERE id = ? AND user_id = ?",
        (entry_id, user_id),
    ).fetchone()
    if row is None:
        return False

    old_amount = float(row["amount"] or 0.0)
    new_amount = float(new_amount)
    if old_amount <= 0 or new_amount <= 0:
        return False

    factor = new_amount / old_amount
    result = db.execute(
        "UPDATE meal_tracker_entry SET amount = ?, kcal = ?, protein_g = ?, carbs_g = ?, fat_g = ? WHERE id = ? AND user_id = ?",
        (
            round(new_amount, 1),
            round(float(row["kcal"]) * factor, 1),
            round(float(row["protein_g"]) * factor, 1),
            round(float(row["carbs_g"]) * factor, 1),
            round(float(row["fat_g"]) * factor, 1),
            entry_id,
            user_id,
        ),
    )
    db.commit()
    return result.rowcount > 0


def add_meal_entry(
    user_id,
    meal_name,
    kcal,
    protein_g=0.0,
    carbs_g=0.0,
    fat_g=0.0,
    amount=None,
    unit=None,
    eaten_at=None,
):
    db = get_db()
    # eaten_at optional: sonst greift der CURRENT_TIMESTAMP-Default (heute).
    cur = db.execute(
        "INSERT INTO meal_tracker_entry (user_id, meal_name, amount, unit, kcal, protein_g, carbs_g, fat_g"
        + (", eaten_at" if eaten_at else "")
        + ") VALUES (?, ?, ?, ?, ?, ?, ?, ?" + (", ?" if eaten_at else "") + ")",
        (
            user_id,
            meal_name,
            float(amount) if amount is not None else None,
            unit,
            float(kcal),
            float(protein_g),
            float(carbs_g),
            float(fat_g),
        ) + ((eaten_at,) if eaten_at else ()),
    )
    db.commit()
    return cur.lastrowid




def get_tracked_days(user_id, year, month):
    """Tag-Nummern eines Monats mit mindestens einer Mahlzeit (fuer Kalender-Punkte)."""
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT CAST(strftime('%d', eaten_at, 'localtime') AS INTEGER) AS d"
        " FROM meal_tracker_entry WHERE user_id = ? AND strftime('%Y-%m', eaten_at, 'localtime') = ?",
        (user_id, f"{year:04d}-{month:02d}"),
    ).fetchall()
    return {row["d"] for row in rows}


def get_day_meals(user_id, date_str):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM meal_tracker_entry WHERE user_id = ? AND date(eaten_at, 'localtime') = ? ORDER BY eaten_at DESC",
        (user_id, date_str),
    ).fetchall()
    return [dict(row) for row in rows]


def get_day_totals(user_id, date_str):
    db = get_db()
    row = db.execute(
        "SELECT COALESCE(SUM(kcal),0) AS kcal, COALESCE(SUM(protein_g),0) AS protein_g,"
        " COALESCE(SUM(carbs_g),0) AS carbs_g, COALESCE(SUM(fat_g),0) AS fat_g"
        " FROM meal_tracker_entry WHERE user_id = ? AND date(eaten_at, 'localtime') = ?",
        (user_id, date_str),
    ).fetchone()
    return {k: round(float(row[k]), 1) for k in ("kcal", "protein_g", "carbs_g", "fat_g")}
