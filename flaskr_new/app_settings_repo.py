"""Persistence for user-level app settings."""
from __future__ import annotations

from .db import get_db


DEFAULT_LLM_MODEL = "qwen3.5:latest"


def ensure_schema():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            llm_model TEXT NOT NULL DEFAULT 'qwen3.5:latest',
            updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user (id)
        )
        """
    )
    db.commit()


def get_settings(user_id: int) -> dict:
    ensure_schema()
    row = get_db().execute(
        "SELECT llm_model FROM app_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return {"llm_model": DEFAULT_LLM_MODEL}
    return {"llm_model": row["llm_model"] or DEFAULT_LLM_MODEL}


def save_settings(user_id: int, *, llm_model: str) -> dict:
    ensure_schema()
    model = (llm_model or DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
    get_db().execute(
        """
        INSERT INTO app_settings (user_id, llm_model, updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            llm_model = excluded.llm_model,
            updated = CURRENT_TIMESTAMP
        """,
        (user_id, model),
    )
    get_db().commit()
    return {"llm_model": model}
