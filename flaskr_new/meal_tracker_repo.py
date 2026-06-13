"""Repository fuer den Meal Tracker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .db import get_db


DEFAULT_SETTINGS = {
    "daily_kcal": 2000.0,
    "protein_pct": 30.0,
    "carbs_pct": 40.0,
    "fat_pct": 30.0,
}


def _row_to_dict(row):
    return dict(row) if row is not None else None


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _start_of_today() -> datetime:
    now = _now()
    return datetime(now.year, now.month, now.day)


def ensure_schema() -> None:
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS meal_tracker_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            daily_kcal REAL NOT NULL DEFAULT 2000,
            protein_pct REAL NOT NULL DEFAULT 30,
            carbs_pct REAL NOT NULL DEFAULT 40,
            fat_pct REAL NOT NULL DEFAULT 30,
            updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user (id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS meal_tracker_entry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            meal_name TEXT NOT NULL,
            product_id INTEGER,
            barcode TEXT,
            amount REAL,
            unit TEXT,
            kcal REAL NOT NULL,
            protein_g REAL NOT NULL DEFAULT 0,
            carbs_g REAL NOT NULL DEFAULT 0,
            fat_g REAL NOT NULL DEFAULT 0,
            note TEXT,
            section TEXT,
            eaten_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user (id)
        )
        """
    )

    existing_columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(meal_tracker_entry)").fetchall()
    }
    for column_sql, column_name in (
        ("ALTER TABLE meal_tracker_entry ADD COLUMN product_id INTEGER", "product_id"),
        ("ALTER TABLE meal_tracker_entry ADD COLUMN barcode TEXT", "barcode"),
        ("ALTER TABLE meal_tracker_entry ADD COLUMN amount REAL", "amount"),
        ("ALTER TABLE meal_tracker_entry ADD COLUMN unit TEXT", "unit"),
        ("ALTER TABLE meal_tracker_entry ADD COLUMN section TEXT", "section"),
    ):
        if column_name not in existing_columns:
            try:
                db.execute(column_sql)
            except Exception:
                pass
    db.commit()


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
    note: Optional[str] = None,
    product_id: Optional[int] = None,
    barcode: Optional[str] = None,
    amount: Optional[float] = None,
    unit: Optional[str] = None,
    section: Optional[str] = None,
) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO meal_tracker_entry (user_id, meal_name, product_id, barcode, amount, unit, kcal, protein_g, carbs_g, fat_g, note, section, eaten_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            note,
            section,
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
    return [_row_to_dict(row) for row in rows]


def get_today_totals(user_id: int) -> Dict[str, float]:
    meals = get_recent_meals(user_id, days=1)
    totals = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for meal in meals:
        totals["kcal"] += float(meal.get("kcal", 0.0))
        totals["protein_g"] += float(meal.get("protein_g", 0.0))
        totals["carbs_g"] += float(meal.get("carbs_g", 0.0))
        totals["fat_g"] += float(meal.get("fat_g", 0.0))
    return {key: round(value, 1) for key, value in totals.items()}


__all__ = [
    "DEFAULT_SETTINGS",
    "ensure_schema",
    "get_settings",
    "save_settings",
    "delete_meal_entry",
    "update_meal_entry_amount",
    "add_meal_entry",
    "get_recent_meals",
    "get_today_totals",
]
