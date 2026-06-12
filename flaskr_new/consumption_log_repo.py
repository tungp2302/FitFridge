"""Repository fuer Verbrauchs- und Auffuell-Logs.

Schreibt einfache Eintraege in die Tabelle ``consumption_log``, damit
nachvollziehbar bleibt, wie viel von einem Produkt verbraucht oder
aufgefuellt wurde.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .db import get_db


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _log_event(product_id: int, amount: float, unit: str, event_type: str, note: Optional[str]) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO consumption_log (product_id, event_type, amount, unit, timestamp, note)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (product_id, event_type, float(amount), unit, _iso(_now()), note),
    )
    db.commit()
    return cur.lastrowid


def log_consume(product_id: int, amount: float, unit: str, note: Optional[str] = None) -> int:
    """Loggt einen Verbrauchs-Eintrag und gibt die Log-ID zurueck."""
    return _log_event(product_id, amount, unit, "consume", note)


def log_refill(product_id: int, amount: float, unit: str, note: Optional[str] = None) -> int:
    """Loggt eine Auffuellung und gibt die Log-ID zurueck."""
    return _log_event(product_id, amount, unit, "refill", note)
