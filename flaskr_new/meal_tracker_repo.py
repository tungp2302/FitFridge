"""Repository fuer den Meal Tracker."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .db import get_db


DEFAULT_SETTINGS = {
    "daily_kcal": 2000.0,
    "protein_pct": 30.0,
    "carbs_pct": 40.0,
    "fat_pct": 30.0,
}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _start_of_today() -> datetime:
    now = _now()
    return datetime(now.year, now.month, now.day)


def get_settings(user_id: int) -> Dict:
    db = get_db()
    row = db.execute(
        "SELECT * FROM meal_tracker_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return {"user_id": user_id, **DEFAULT_SETTINGS}
    return dict(row)


def save_settings(user_id: int, daily_kcal: float, protein_pct: float, carbs_pct: float, fat_pct: float) -> None:
    db = get_db()
    existing = db.execute(
        "SELECT id FROM meal_tracker_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if existing is None:
        db.execute(
            "INSERT INTO meal_tracker_settings (user_id, daily_kcal, protein_pct, carbs_pct, fat_pct, updated) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, float(daily_kcal), float(protein_pct), float(carbs_pct), float(fat_pct), _iso(_now())),
        )
    else:
        db.execute(
            "UPDATE meal_tracker_settings SET daily_kcal = ?, protein_pct = ?, carbs_pct = ?, fat_pct = ?, updated = ? WHERE user_id = ?",
            (float(daily_kcal), float(protein_pct), float(carbs_pct), float(fat_pct), _iso(_now()), user_id),
        )
    db.commit()


def delete_meal_entry(entry_id: int, user_id: int) -> bool:
    db = get_db()
    result = db.execute(
        "DELETE FROM meal_tracker_entry WHERE id = ? AND user_id = ?",
        (entry_id, user_id),
    )
    db.commit()
    return result.rowcount > 0


def update_meal_entry_amount(entry_id: int, user_id: int, new_amount: float) -> bool:
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
    user_id: int,
    meal_name: str,
    kcal: float,
    protein_g: float = 0.0,
    carbs_g: float = 0.0,
    fat_g: float = 0.0,
    product_id: Optional[int] = None,
    barcode: Optional[str] = None,
    amount: Optional[float] = None,
    unit: Optional[str] = None,
) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO meal_tracker_entry (user_id, meal_name, product_id, barcode, amount, unit, kcal, protein_g, carbs_g, fat_g, eaten_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            meal_name,
            product_id,
            barcode,
            float(amount) if amount is not None else None,
            unit,
            float(kcal),
            float(protein_g),
            float(carbs_g),
            float(fat_g),
            _iso(_now()),
        ),
    )
    db.commit()
    return cur.lastrowid


def get_recent_meals(user_id: int, days: int = 1) -> List[Dict]:
    db = get_db()
    since = _start_of_today() if days == 1 else _now() - timedelta(days=days)
    rows = db.execute(
        "SELECT * FROM meal_tracker_entry WHERE user_id = ? AND eaten_at >= ? ORDER BY eaten_at DESC",
        (user_id, _iso(since)),
    ).fetchall()
    return [dict(row) for row in rows]


def get_tracked_days_in_month(user_id: int, year: int, month: int) -> List[int]:
    """Tage des Monats, an denen mindestens eine Mahlzeit getrackt wurde."""
    db = get_db()
    start = f"{year:04d}-{month:02d}-01 00:00:00"
    if month == 12:
        end = f"{year + 1:04d}-01-01 00:00:00"
    else:
        end = f"{year:04d}-{month + 1:02d}-01 00:00:00"
    rows = db.execute(
        "SELECT DISTINCT strftime('%d', eaten_at) AS day FROM meal_tracker_entry "
        "WHERE user_id = ? AND eaten_at >= ? AND eaten_at < ?",
        (user_id, start, end),
    ).fetchall()
    return [int(row["day"]) for row in rows]


def get_meals_for_date(user_id: int, date_str: str) -> List[Dict]:
    """Alle Mahlzeiten eines bestimmten Tages (date_str im Format YYYY-MM-DD)."""
    db = get_db()
    start = f"{date_str} 00:00:00"
    end = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
    rows = db.execute(
        "SELECT * FROM meal_tracker_entry WHERE user_id = ? AND eaten_at >= ? AND eaten_at < ? ORDER BY eaten_at ASC",
        (user_id, start, end),
    ).fetchall()
    return [dict(row) for row in rows]


_MEAL_MACRO_KEYS = ("kcal", "protein_g", "carbs_g", "fat_g")


def sum_meal_macros(meals: List[Dict]) -> Dict[str, float]:
    """Summiert kcal + Makros (in g) ueber Mahlzeiten und rundet auf 1."""
    totals = {key: 0.0 for key in _MEAL_MACRO_KEYS}
    for meal in meals:
        for key in _MEAL_MACRO_KEYS:
            totals[key] += float(meal.get(key, 0.0) or 0.0)
    return {key: round(value, 1) for key, value in totals.items()}


def get_today_totals(user_id: int) -> Dict[str, float]:
    return sum_meal_macros(get_recent_meals(user_id, days=1))
