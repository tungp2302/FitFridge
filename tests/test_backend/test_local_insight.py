import pytest

from flaskr_new.asaai.local_insight import build_insight_prompt, generate_ai_insight


def test_build_insight_prompt_contains_context():
    prompt = build_insight_prompt(
        [{"product_id": 1, "event_type": "refill", "amount": 20, "unit": "g"}],
        [{"name": "Milk", "current_amount": 200}],
    )

    assert "lokaler FitFridge-Analyseassistent fuer Zugaenge und Bestand" in prompt
    assert "addition_history" in prompt
    assert "fridge_items" in prompt
    assert "Verbrauch soll nicht prognostiziert oder bewertet werden" in prompt


def test_generate_ai_insight_uses_ollama(monkeypatch):
    captured = {}

    def fake_generate_from_ollama(prompt, model=None, base_url=None, timeout=30):
        captured["prompt"] = prompt
        captured["model"] = model
        captured["base_url"] = base_url
        captured["timeout"] = timeout
        return "Lokales Insight"

    monkeypatch.setattr("flaskr_new.asaai.local_insight.generate_from_ollama", fake_generate_from_ollama)

    text = generate_ai_insight([{"event_type": "refill", "amount": 10}], [{"name": "Milk"}], model="llama3.1", base_url="http://127.0.0.1:11434", timeout=11)

    assert text == "Lokales Insight"
    assert "FitFridge-Analyseassistent fuer Zugaenge und Bestand" in captured["prompt"]
    assert captured["model"] == "llama3.1"
    assert captured["base_url"] == "http://127.0.0.1:11434"
    assert captured["timeout"] == 11
