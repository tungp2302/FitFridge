"""Tests für llm_enricher.py.

Wir mocken den Ollama-Client, um die Logik zu testen
ohne wirklich das LLM aufzurufen.

Mocking bedeutet: wir ersetzen eine echte Funktion durch eine "Fake"-Funktion,
die wir kontrollieren können. So können wir testen:
- Wie verhält sich der Code, wenn das LLM "X" zurückgibt?
- Was passiert, wenn das LLM crashed?
- Wird das LLM mit dem richtigen Prompt aufgerufen?
"""

from unittest.mock import patch

from flaskr_new.asaai.llm_enricher import (
    enrich_recipes_with_llm,
    build_enricher_prompt,
)


# === Tests für build_enricher_prompt ===

def test_prompt_contains_recipe_names():
    """Der Prompt enthält die Namen der Match-Rezepte."""
    matches = [
        {
            "recipe": {"name": "Spaghetti Bolognese"},
            "match_score": 0.8,
            "available": ["pasta", "tomato"],
            "missing": ["beef"],
        },
    ]
    fridge_items = [{"name": "pasta"}]

    prompt = build_enricher_prompt(matches, fridge_items)

    assert "Spaghetti Bolognese" in prompt
    assert "pasta" in prompt


def test_prompt_includes_daily_goal():
    """Wenn ein daily_goal gegeben ist, taucht es im Prompt auf."""
    daily_goal = {"protein": 30, "kcal": 600}

    prompt = build_enricher_prompt([], [], daily_goal)

    assert "30" in prompt   # protein value
    assert "600" in prompt  # kcal value


def test_prompt_works_without_daily_goal():
    """Auch ohne Tagesziel sollte ein Prompt entstehen."""
    prompt = build_enricher_prompt([], [])
    assert len(prompt) > 0  # nicht leer


# === Tests für enrich_recipes_with_llm (mit Mock) ===

@patch("flaskr_new.asaai.llm_enricher.generate_from_ollama")
def test_enrich_empty_matches_returns_message(mock_llm):
    """Bei leeren Matches kommt Default-Nachricht zurück.

    Wichtig: LLM darf in diesem Fall NICHT aufgerufen werden,
    weil das Verschwendung wäre.
    """
    result = enrich_recipes_with_llm(
        matches=[],
        fridge_items=[],
    )

    # Eine sinnvolle Nachricht kommt zurück
    assert "Keine" in result["llm_recommendation"] or "nicht" in result["llm_recommendation"].lower()

    # LLM wurde NICHT aufgerufen (Edge Case Optimization)
    mock_llm.assert_not_called()


@patch("flaskr_new.asaai.llm_enricher.generate_from_ollama")
def test_enrich_calls_llm_with_matches(mock_llm):
    """Mit Matches wird das LLM aufgerufen."""
    # Wir definieren, was unser Fake-LLM zurückgeben soll
    mock_llm.return_value = "Mock LLM Antwort"

    matches = [
        {
            "recipe": {"name": "Test Recipe"},
            "match_score": 0.5,
            "available": ["chicken"],
            "missing": ["rice"],
        },
    ]

    result = enrich_recipes_with_llm(
        matches=matches,
        fridge_items=[{"name": "chicken"}],
    )

    # LLM wurde aufgerufen
    mock_llm.assert_called_once()

    # Die Mock-Antwort wurde durchgereicht
    assert result["llm_recommendation"] == "Mock LLM Antwort"


@patch("flaskr_new.asaai.llm_enricher.generate_from_ollama")
def test_enrich_handles_llm_exception(mock_llm):
    """Wenn LLM crashed, kommt graceful Fallback statt Absturz.

    Das ist ein kritischer Robustheits-Test: User soll nie eine
    leere weiße Seite sehen, nur weil Ollama nicht läuft.
    """
    # Wir simulieren einen LLM-Crash
    mock_llm.side_effect = Exception("Ollama nicht erreichbar")

    matches = [
        {
            "recipe": {"name": "X"},
            "match_score": 0.5,
            "available": [],
            "missing": [],
        },
    ]

    result = enrich_recipes_with_llm(
        matches=matches,
        fridge_items=[],
    )

    # Crash wurde abgefangen, kein Absturz
    assert "nicht verfügbar" in result["llm_recommendation"].lower()

    # Original-Matches werden trotzdem zurückgegeben (kein Datenverlust)
    assert len(result["original_matches"]) == 1


@patch("flaskr_new.asaai.llm_enricher.generate_from_ollama")
def test_enrich_limits_to_top_5(mock_llm):
    """Maximal 5 Matches werden ans LLM geschickt.

    Performance-Optimization: nicht alle 50 Rezepte an LLM senden,
    sonst dauert es ewig + Token-Limit.
    """
    mock_llm.return_value = "OK"

    # 10 Matches als Input
    matches = [
        {
            "recipe": {"name": f"Recipe {i}"},
            "match_score": 0.5,
            "available": [],
            "missing": [],
        }
        for i in range(10)
    ]

    result = enrich_recipes_with_llm(
        matches=matches,
        fridge_items=[],
    )

    # Nur 5 wurden ans LLM gegeben
    assert len(result["original_matches"]) == 5