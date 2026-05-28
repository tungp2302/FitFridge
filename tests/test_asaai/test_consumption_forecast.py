"""Tests für consumption_forecast.py."""

from unittest.mock import patch

from flaskr_new.asaai.consumption_forecast import (
    calculate_days_until_empty,
    average_daily_consumption,
    generate_forecast_insight,
)


# === Tests für calculate_days_until_empty ===

def test_days_normal():
    """500g / 50g pro Tag = 10 Tage."""
    assert calculate_days_until_empty(500.0, 50.0) == 10.0


def test_days_zero_rate_is_infinite():
    """Wenn kein Verbrauch, dauert es ewig."""
    assert calculate_days_until_empty(100.0, 0) == float("inf")


def test_days_negative_rate_is_infinite():
    """Negative Rate macht keinen Sinn → unendlich."""
    assert calculate_days_until_empty(100.0, -10) == float("inf")


def test_days_no_amount_returns_zero():
    """Wenn nichts da ist, dauert es 0 Tage."""
    assert calculate_days_until_empty(0.0, 10.0) == 0.0


# === Tests für average_daily_consumption ===

def test_average_empty_history():
    """Leere Historie → 0 Verbrauch."""
    assert average_daily_consumption([]) == 0.0


def test_average_with_history():
    """3 Einträge mit zusammen 30g über 30 Tage → 1g/Tag."""
    history = [
        {"amount": 10},
        {"amount": 10},
        {"amount": 10},
    ]
    result = average_daily_consumption(history, days_window=30)
    assert result == 1.0


# === Tests für generate_forecast_insight mit Mock ===

@patch("flaskr_new.asaai.consumption_forecast.generate_from_ollama")
def test_forecast_empty_returns_message(mock_llm):
    """Leere Forecasts → Default-Nachricht, kein LLM-Call."""
    result = generate_forecast_insight([])
    assert "Keine" in result["insight_text"]
    mock_llm.assert_not_called()


@patch("flaskr_new.asaai.consumption_forecast.generate_from_ollama")
def test_forecast_calls_llm(mock_llm):
    """Mit Forecasts wird LLM aufgerufen."""
    mock_llm.return_value = "Mock-Antwort"

    forecasts = [
        {
            "name": "Milk",
            "current_amount": 200,
            "unit": "ml",
            "days_until_empty": 3.0,
        },
    ]
    result = generate_forecast_insight(forecasts)

    mock_llm.assert_called_once()
    assert result["insight_text"] == "Mock-Antwort"


@patch("flaskr_new.asaai.consumption_forecast.generate_from_ollama")
def test_forecast_handles_llm_exception(mock_llm):
    """LLM-Fehler → graceful Fallback."""
    mock_llm.side_effect = Exception("Ollama down")

    forecasts = [
        {"name": "X", "current_amount": 100, "unit": "g", "days_until_empty": 5.0},
    ]
    result = generate_forecast_insight(forecasts)
    assert "nicht verfügbar" in result["insight_text"].lower()