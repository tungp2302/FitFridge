from flaskr_new.asaai.ollama_client import (
    generate_from_ollama,
    resolve_ollama_model,
    test_ollama_model as check_ollama_model,
)


def test_resolve_ollama_model_accepts_profiles_and_raw_tags(monkeypatch):
    monkeypatch.delenv("ASAAI_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    assert resolve_ollama_model("desktop") == "qwen3.5:latest"
    assert resolve_ollama_model("laptop") == "qwen3:4b"
    assert resolve_ollama_model("fast") == "gemma3:1b"
    assert resolve_ollama_model("custom:latest") == "custom:latest"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_generate_from_ollama_parses_response(monkeypatch):
    def fake_get(url, timeout):
        assert url == "http://127.0.0.1:11434/api/tags"
        assert timeout == 10
        return _FakeResponse({"models": [{"name": "qwen3.5:latest"}]})

    def fake_post(url, json, timeout):
        assert url == "http://127.0.0.1:11434/api/generate"
        assert json["model"] == "qwen3.5:latest"
        assert json["stream"] is False
        assert json["think"] is False
        assert json["options"]["num_predict"] == 160
        assert timeout == 12
        return _FakeResponse({"response": "Hallo von Ollama"})

    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.get", fake_get)
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.post", fake_post)

    text = generate_from_ollama("Sag hallo", timeout=12)

    assert text == "Hallo von Ollama"


def test_generate_from_ollama_uses_configured_model_without_local_fallback(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:latest")

    def fake_post(url, json, timeout):
        assert json["model"] == "qwen3.5:latest"
        return _FakeResponse({"response": "Configured model response"})

    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.post", fake_post)

    text = generate_from_ollama("Sag hallo")

    assert text == "Configured model response"


def test_test_ollama_model_checks_generation(monkeypatch):
    calls = {"post": 0}

    def fake_get(url, timeout):
        assert url == "http://127.0.0.1:11434/api/tags"
        return _FakeResponse({"models": [{"name": "gemma3:1b"}]})

    def fake_post(url, json, timeout):
        calls["post"] += 1
        assert url == "http://127.0.0.1:11434/api/generate"
        assert json["model"] == "gemma3:1b"
        assert json["format"] == "json"
        assert json["options"]["num_predict"] == 120
        return _FakeResponse({"response": '{"ok": true, "title": "Planner Test"}'})

    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.get", fake_get)
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.post", fake_post)

    result = check_ollama_model("gemma3:1b")

    assert result["ok"] is True
    assert result["installed"] is True
    assert result["generated"] is True
    assert result["response"] == '{"ok": true, "title": "Planner Test"}'
    assert calls["post"] == 1


def test_test_ollama_model_rejects_non_json_response(monkeypatch):
    def fake_get(url, timeout):
        return _FakeResponse({"models": [{"name": "gemma3:1b"}]})

    def fake_post(url, json, timeout):
        return _FakeResponse({"response": "ok"})

    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.get", fake_get)
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.post", fake_post)

    result = check_ollama_model("gemma3:1b")

    assert result["ok"] is False
    assert result["installed"] is True
    assert result["generated"] is False
    assert "Planner-JSON" in result["error"]
