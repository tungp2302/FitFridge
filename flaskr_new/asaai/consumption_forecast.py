"""Verbrauchsprognose mit LLM-Erklärungen.

Analysiert Tungs consumption_log um vorherzusagen, wann Produkte
leer sein werden. LLM erklärt die Prognose in natürlicher Sprache.

Hauptfunktionen:
- calculate_days_until_empty(item, history): einfache Mathe-Prognose
- generate_forecast_insight(items, histories): LLM-Erklärung
"""

from __future__ import annotations

import json
from typing import Optional

from .ollama_client import generate_from_ollama


def calculate_days_until_empty(current_amount, daily_consumption_rate):
    """Berechnet wie viele Tage bis ein Item leer ist.

    Parameter:
        current_amount (float): Aktuelle Menge im Kühlschrank
        daily_consumption_rate (float): Durchschnittlicher Tagesverbrauch

    Returns:
        float: Anzahl Tage bis leer. Inf wenn rate <= 0.
    """
    if daily_consumption_rate <= 0:
        return float("inf")

    return current_amount / daily_consumption_rate


def average_daily_consumption(consumption_history, days_window=30):
    """Berechnet den durchschnittlichen Tagesverbrauch aus der Historie.

    Parameter:
        consumption_history (list): Liste von Log-Einträgen mit
                                    {amount, timestamp/date}
        days_window (int): Wieviele Tage betrachten (default 30)

    Returns:
        float: Durchschnittlicher Tagesverbrauch
    """
    if not consumption_history:
        return 0.0

    # Vereinfachung: Summe aller Verbräuche / Anzahl Tage
    total = sum(entry.get("amount", 0) for entry in consumption_history)
    return total / max(days_window, 1)


def build_forecast_prompt(forecasts):
    """Baut den Prompt für das LLM mit Verbrauchsprognosen.

    Parameter:
        forecasts (list): Liste von Dicts mit name, current_amount,
                          unit, days_until_empty

    Returns:
        str: Vollständiger Prompt für Ollama
    """
    payload = {
        "forecasts": [
            {
                "name": f["name"],
                "current_amount": f["current_amount"],
                "unit": f["unit"],
                "days_until_empty": (
                    round(f["days_until_empty"], 1)
                    if f["days_until_empty"] != float("inf")
                    else "unbegrenzt"
                ),
            }
            for f in forecasts
        ],
    }

    return (
        "Du bist ein Vorrats-Assistent für die FitFridge-App. "
        "Antworte auf Deutsch, knapp und nützlich.\n\n"
        "Du erhältst Verbrauchsprognosen für Kühlschrank-Items.\n\n"
        "Generiere einen kurzen Bericht in 2 Abschnitten:\n\n"
        "Bald leer:\n"
        "- 1-3 Items, die in <7 Tagen leer sein werden\n"
        "- Jeweils mit Anzahl Tage und Empfehlung\n\n"
        "Empfehlungen:\n"
        "- 1-2 Stichpunkte zum Einkaufsverhalten\n\n"
        "Antworte nur mit diesen zwei Abschnitten.\n\n"
        f"Daten:\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
    )


def generate_forecast_insight(
    forecasts,
    model=None,
    base_url=None,
    timeout=120,
):
    """Generiert eine KI-Erklärung für Verbrauchsprognosen.

    Parameter:
        forecasts (list): Liste von Forecast-Dicts (siehe build_forecast_prompt)
        model, base_url, timeout: Ollama-Konfiguration

    Returns:
        dict: {"insight_text": str, "forecasts": list}
    """
    if not forecasts:
        return {
            "insight_text": "Keine Verbrauchsdaten vorhanden.",
            "forecasts": [],
        }

    prompt = build_forecast_prompt(forecasts)

    try:
        insight_text = generate_from_ollama(
            prompt=prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
            num_predict=400,
        )
    except Exception as e:
        insight_text = f"LLM nicht verfügbar: {e}"

    return {
        "insight_text": insight_text,
        "forecasts": forecasts,
    }