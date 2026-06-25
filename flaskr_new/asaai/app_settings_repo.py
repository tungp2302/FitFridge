"""Speichert App-Einstellungen pro Nutzer (aktuell das LLM-Modell)."""
from ..db import get_db
from .ollama_client import DEFAULT_OLLAMA_MODEL as DEFAULT_LLM_MODEL


def get_settings(user_id: int) -> dict:
    row = get_db().execute(
        "SELECT llm_model FROM app_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return {"llm_model": DEFAULT_LLM_MODEL}
    return {"llm_model": row["llm_model"] or DEFAULT_LLM_MODEL}


def save_settings(user_id: int, *, llm_model: str) -> None:
    model = (llm_model or DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
    db = get_db()
    db.execute(
        """
        INSERT INTO app_settings (user_id, llm_model, updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            llm_model = excluded.llm_model,
            updated = CURRENT_TIMESTAMP
        """,
        (user_id, model),
    )
    db.commit()
