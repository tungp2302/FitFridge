"""Lokaler Insight-Client fuer ASaAI.

Dieses Modul baut den Insight-Prompt fuer Zugaenge / Bestand und ruft
ausschliesslich den lokalen Ollama-Backend-Adapter auf.
"""
from __future__ import annotations

import json
from typing import Iterable, Optional

from .ollama_client import generate_from_ollama


def build_insight_prompt(addition_history: Iterable[dict], fridge_items: Optional[Iterable[dict]] = None) -> str:
    """Erzeugt einen kompakten Prompt fuer lokale ASaAI-Insights.

    Der Prompt soll nur Zugaenge / Auffuellungen und den aktuellen Bestand
    analysieren. Verbrauch wird bewusst nicht interpretiert.
    """
    history = list(addition_history or [])
    fridge = list(fridge_items or [])

    payload = {
        "addition_history": history,
        "fridge_items": fridge,
        "output_format": {
            "summary": "one detailed paragraph",
            "bullets": ["addition pattern", "stock risk", "next restock action"],
        },
    }

    # Ask the local model for three explicit plain-text sections in short bullet form.
    # We *allow* simple bullet markers ('- ') because the UI expects concise bullets.
    return (
        "Du bist ein lokaler FitFridge-Analyseassistent fuer Zugaenge und Bestand. "
        "Antworte auf Deutsch, knapp und in Stichpunkten. "
        "Analysiere nur Zugaenge / Auffuellungen; Verbrauch soll nicht prognostiziert oder bewertet werden. "
        "Gib genau drei Abschnitte mit den folgenden Ueberschriften, jeweils gefolgt von 1–2 kurzen Bullets (je Bullet maximal 1 Satz, ca. 120 Zeichen):\n"
        "Zugaenge-Muster:\n- <stichpunkt 1>\n- <optional stichpunkt 2>\n\n"
        "Bestandsrisiko:\n- <stichpunkt 1>\n- <optional stichpunkt 2>\n\n"
        "naechste Nachfuell-Aktion:\n- <stichpunkt 1>\n- <optional stichpunkt 2>\n\n"
        "Antworte nur mit den Ueberschriften und den kurzen Bullets genau wie oben. Wenn Daten fehlen, schreibe 'Keine Daten' als Bullet.\n\n"
        f"Daten:{json.dumps(payload, ensure_ascii=False, separators=(',', ':'), default=str)}"
    )


def generate_ai_insight(
    addition_history: Iterable[dict],
    fridge_items: Optional[Iterable[dict]] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 600,
) -> str:
    """Ruft ausschliesslich den lokalen Ollama-Backend-Adapter auf."""
    prompt = build_insight_prompt(addition_history, fridge_items)
    # Request a larger generation budget from the local Ollama model to avoid truncation
    # Only pass `num_predict` if the underlying client supports it (keeps tests and monkeypatches happy)
    try:
        import inspect

        sig = inspect.signature(generate_from_ollama)
        if 'num_predict' in sig.parameters:
            return generate_from_ollama(prompt, model=model, base_url=base_url, timeout=timeout, num_predict=800)
    except Exception:
        # fallback to a plain call if introspection fails
        pass
    return generate_from_ollama(prompt, model=model, base_url=base_url, timeout=timeout)
