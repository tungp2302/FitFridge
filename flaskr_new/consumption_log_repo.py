"""Schreibt Verbrauchs-/Auffuell-Eintraege in die Tabelle consumption_log,
damit nachvollziehbar bleibt, wie viel von einem Produkt bewegt wurde."""

from .db import get_db, _iso, _now


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
