"""Tests für shopping_advisor.py."""

from unittest.mock import patch

from flaskr_new.asaai.shopping_advisor import (
    find_low_stock_items,
    find_frequently_consumed,
    generate_shopping_list,
)


# === Tests für find_low_stock_items ===

def test_low_stock_empty_returns_empty():
    """Leere Liste → leere Liste."""
    assert find_low_stock_items([]) == []


def test_low_stock_below_threshold():
    """Item mit 50g (< 100g threshold) wird gefunden."""
    items = [
        {"name": "Butter", "current_amount": 50, "unit": "g"},
    ]
    result = find_low_stock_items(items)
    assert len(result) == 1
    assert result[0]["name"] == "Butter"


def test_low_stock_above_threshold_ignored():
    """Item mit 500g (> 100g threshold) wird ignoriert."""
    items = [
        {"name": "Reis", "current_amount": 500, "unit": "g"},
    ]
    result = find_low_stock_items(items)
    assert len(result) == 0


def test_low_stock_high_urgency():
    """Items unter Hälfte des Thresholds → urgency=high."""
    items = [
        {"name": "Butter", "current_amount": 30, "unit": "g"},
    ]
    result = find_low_stock_items(items)
    assert result[0]["urgency"] == "high"


def test_low_stock_volume_unit():
    """ml: 150ml < 200ml threshold."""
    items = [
        {"name": "Milch", "current_amount": 150, "unit": "ml"},
    ]
    result = find_low_stock_items(items)
    assert len(result) == 1


def test_low_stock_kg_conversion():
    """kg wird korrekt konvertiert."""
    items = [
        {"name": "Reis", "current_amount": 0.05, "unit": "kg"},  # 50g
    ]
    result = find_low_stock_items(items)
    assert len(result) == 1  # 50g < 100g threshold


# === Tests für find_frequently_consumed ===

def test_frequent_empty_returns_empty():
    """Leere Historie → leere Liste."""
    assert find_frequently_consumed([]) == []


def test_frequent_counts_correctly():
    """3+ Einträge → wird als häufig gewertet."""
    history = [
        {"product_id": 1, "amount": 10},
        {"product_id": 1, "amount": 10},
        {"product_id": 1, "amount": 10},
        {"product_id": 2, "amount": 5},
    ]
    result = find_frequently_consumed(history, min_count=3)
    assert len(result) == 1
    assert result[0]["product_id"] == 1
    assert result[0]["consumption_count"] == 3


def test_frequent_sorted_by_count():
    """Häufigstes Item kommt zuerst."""
    history = [
        {"product_id": 1, "amount": 10},
        {"product_id": 1, "amount": 10},
        {"product_id": 1, "amount": 10},
        {"product_id": 2, "amount": 5},
        {"product_id": 2, "amount": 5},
        {"product_id": 2, "amount": 5},
        {"product_id": 2, "amount": 5},
        {"product_id": 2, "amount": 5},
    ]
    result = find_frequently_consumed(history, min_count=3)
    assert result[0]["product_id"] == 2  # 5x ist mehr als 3x
    assert result[1]["product_id"] == 1


# === Tests für generate_shopping_list mit Mock ===

@patch("flaskr_new.asaai.shopping_advisor.generate_from_ollama")
def test_shopping_no_items_no_llm_call(mock_llm):
    """Leerer Kühlschrank → keine LLM-Calls."""
    result = generate_shopping_list(fridge_items=[])
    assert "gut gefüllt" in result["shopping_list_text"]
    mock_llm.assert_not_called()


@patch("flaskr_new.asaai.shopping_advisor.generate_from_ollama")
def test_shopping_with_low_stock_calls_llm(mock_llm):
    """Mit niedrigem Bestand wird LLM aufgerufen."""
    mock_llm.return_value = "Mock-Einkaufsliste"

    items = [
        {"name": "Butter", "current_amount": 30, "unit": "g"},
    ]
    result = generate_shopping_list(fridge_items=items)

    mock_llm.assert_called_once()
    assert result["shopping_list_text"] == "Mock-Einkaufsliste"


@patch("flaskr_new.asaai.shopping_advisor.generate_from_ollama")
def test_shopping_llm_exception_fallback(mock_llm):
    """LLM-Crash → Fallback mit roher Liste."""
    mock_llm.side_effect = Exception("Ollama down")

    items = [
        {"name": "Butter", "current_amount": 30, "unit": "g"},
    ]
    result = generate_shopping_list(fridge_items=items)
    assert "Butter" in result["shopping_list_text"]
    assert "LLM nicht verfügbar" in result["shopping_list_text"]