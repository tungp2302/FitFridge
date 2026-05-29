"""Repository für Verbrauchs- und Auffüll-Logs.

Bietet eine einfache, DB-gestützte API, die ASaAI und andere Services
für Verbrauchsanalysen nutzen können.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

from .db import get_db


def _row_to_dict(row) -> Dict:
    if row is None:
        return None
    return dict(row)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def log_consume(product_id: int, amount: float, unit: str, timestamp: Optional[datetime] = None, note: Optional[str] = None) -> int:
    """Loggt einen Verbrauchs-Eintrag und gibt die Log-ID zurück."""
    return _log_event(product_id, amount, unit, "consume", timestamp, note)


def log_refill(product_id: int, amount: float, unit: str, timestamp: Optional[datetime] = None, note: Optional[str] = None) -> int:
    """Loggt eine Auffüllung und gibt die Log-ID zurück."""
    return _log_event(product_id, amount, unit, "refill", timestamp, note)


def _log_event(product_id: int, amount: float, unit: str, event_type: str, timestamp: Optional[datetime], note: Optional[str]) -> int:
    db = get_db()
    ts = _iso(timestamp or _now())
    cur = db.execute(
        "INSERT INTO consumption_log (product_id, event_type, amount, unit, timestamp, note) VALUES (?, ?, ?, ?, ?, ?)",
        (product_id, event_type, float(amount), unit, ts, note),
    )
    db.commit()
    return cur.lastrowid


def get_consumption_history(product_id: int, days: int = 30) -> List[Dict]:
    """Gibt eine Liste von Log-Einträgen der letzten `days` Tage zurück (neueste zuerst)."""
    db = get_db()
    since = _now() - timedelta(days=days)
    rows = db.execute(
        "SELECT * FROM consumption_log WHERE product_id = ? AND timestamp >= ? ORDER BY timestamp DESC",
        (product_id, _iso(since)),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_consumption_for_products(product_ids: List[int], days: int = 30) -> Dict[int, List[Dict]]:
    """Für mehrere Produkte die History als Dict product_id -> [logs] liefern."""
    if not product_ids:
        return {}
    db = get_db()
    since = _now() - timedelta(days=days)
    placeholder = ",".join("?" for _ in product_ids)
    params = tuple(product_ids) + (_iso(since),)
    rows = db.execute(
        f"SELECT * FROM consumption_log WHERE product_id IN ({placeholder}) AND timestamp >= ? ORDER BY product_id, timestamp DESC",
        params,
    ).fetchall()
    out: Dict[int, List[Dict]] = {pid: [] for pid in product_ids}
    for r in rows:
        out[r["product_id"]].append(_row_to_dict(r))
    return out


def avg_daily_consumption(product_id: int, days: int = 30) -> float:
    """Berechnet durchschnittlichen Verbrauch pro Tag über die letzten `days` Tage.

    Falls keine Verbrauchs-Einträge vorhanden sind, wird 0.0 zurückgegeben.
    """
    rows = get_consumption_history(product_id, days)
    total = 0.0
    for r in rows:
        if r.get("event_type") == "consume":
            total += float(r.get("amount", 0.0))
    if total <= 0.0:
        return 0.0
    return total / float(days)


def days_until_empty(product_id: int, current_amount: float, days: int = 30) -> Optional[float]:
    """Schätzt die Tage bis leer basierend auf `avg_daily_consumption`.

    Gibt `None` zurück, wenn die Verbrauchsrate 0 ist (kein Verbrauch bekannt).
    """
    avg = avg_daily_consumption(product_id, days)
    if avg <= 0:
        return None
    return float(current_amount) / avg


def get_recent_purchases(product_id: int, months: int = 3) -> List[Dict]:
    """Gibt Auffüll-Ereignisse der letzten `months` Monate zurück."""
    db = get_db()
    since = _now() - timedelta(days=30 * months)
    rows = db.execute(
        "SELECT * FROM consumption_log WHERE product_id = ? AND event_type = 'refill' AND timestamp >= ? ORDER BY timestamp DESC",
        (product_id, _iso(since)),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_recent_events(days: int = 30, limit: int = 50) -> List[Dict]:
    """Gibt die neuesten Verbrauchs- und Auffuell-Events zurueck."""
    db = get_db()
    since = _now() - timedelta(days=days)
    rows = db.execute(
        "SELECT * FROM consumption_log WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?",
        (_iso(since), limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_consumption_log(days: int = 30, limit: int = 100) -> List[Dict]:
    """Convenience wrapper returning recent consumption/refill events.

    Returns up to `limit` recent events from the last `days` days.
    """
    return get_recent_events(days=days, limit=limit)


def get_consumption_for_product(product_id: int, days: int = 30) -> List[Dict]:
    """Convenience wrapper returning history for a single product."""
    return get_consumption_history(product_id, days=days)
