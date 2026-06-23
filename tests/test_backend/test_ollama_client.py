from types import SimpleNamespace
from flaskr_new.asaai.ollama_client import generate_from_ollama, resolve_ollama_model, test_ollama_model as check_ollama_model

_resp = lambda p: SimpleNamespace(raise_for_status=lambda: None, json=lambda: p)
_tags = lambda *names: _resp({"models": [{"name": n} for n in names]})

def test_resolve_ollama_model_accepts_profiles_and_raw_tags(monkeypatch):
    monkeypatch.delenv("ASAAI_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert resolve_ollama_model("desktop") == "qwen3.5:latest"
    assert resolve_ollama_model("laptop") == "qwen3:4b"
    assert resolve_ollama_model("fast") == "gemma3:1b"
    assert resolve_ollama_model("custom:latest") == "custom:latest"

def test_generate_from_ollama_parses_response(monkeypatch):
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.get", lambda url, timeout: _tags("qwen3.5:latest"))
    def fake_post(url, json, timeout):
        assert json["model"] == "qwen3.5:latest"
        assert json["options"]["num_predict"] == 160
        assert timeout == 12
        return _resp({"response": "Hallo von Ollama"})
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.post", fake_post)
    assert generate_from_ollama("Sag hallo", timeout=12) == "Hallo von Ollama"

def test_generate_from_ollama_uses_configured_model_without_local_fallback(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:latest")
    def fake_post(url, json, timeout):
        assert json["model"] == "qwen3.5:latest"
        return _resp({"response": "Configured model response"})
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.post", fake_post)
    assert generate_from_ollama("Sag hallo") == "Configured model response"

def test_test_ollama_model_checks_generation(monkeypatch):
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.get", lambda url, timeout: _tags("gemma3:1b"))
    def fake_post(url, json, timeout):
        assert json["model"] == "gemma3:1b"
        assert json["format"] == "json"
        assert json["options"]["num_predict"] == 120
        return _resp({"response": '{"ok": true, "title": "Planner Test"}'})
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.post", fake_post)
    result = check_ollama_model("gemma3:1b")
    assert result["ok"] is True
    assert result["installed"] is True
    assert result["generated"] is True
    assert result["response"] == '{"ok": true, "title": "Planner Test"}'

def test_test_ollama_model_rejects_non_json_response(monkeypatch):
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.get", lambda url, timeout: _tags("gemma3:1b"))
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.requests.post", lambda url, json, timeout: _resp({"response": "ok"}))
    result = check_ollama_model("gemma3:1b")
    assert result["ok"] is False
    assert result["installed"] is True
    assert result["generated"] is False
    assert "Planner-JSON" in result["error"]
