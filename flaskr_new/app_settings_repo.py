"""Persistence for user-level app settings."""
from __future__ import annotations

from .db import get_db


DEFAULT_LLM_MODEL = "qwen3.5:latest"


def get_settings(user_id: int) -> dict:
    row = get_db().execute(
        "SELECT llm_model FROM app_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return {"llm_model": DEFAULT_LLM_MODEL}
    return {"llm_model": row["llm_model"] or DEFAULT_LLM_MODEL}


def save_settings(user_id: int, *, llm_model: str) -> dict:
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
