"""Verbrauchs-/Auffuell in die Tabelle consumption_log,
(viel von einem Produkt bewegt wurde)."""

from datetime import datetime, timezone

from .db import get_db


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _log_event(product_id, amount, unit, event_type, note):
    db = get_db()
    cur = db.execute(
        "INSERT INTO consumption_log (product_id, event_type, amount, unit, timestamp, note)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (product_id, event_type, float(amount), unit, _iso(_now()), note),
    )
    db.commit()
    return cur.lastrowid


def log_consume(product_id, amount, unit, note=None):
    """Loggt einen Verbrauchs-Eintrag und gibt die Log-ID zurueck."""
    return _log_event(product_id, amount, unit, "consume", note)


def log_refill(product_id, amount, unit, note=None):
    """Loggt eine Auffuellung und gibt die Log-ID zurueck."""
    return _log_event(product_id, amount, unit, "refill", note)
