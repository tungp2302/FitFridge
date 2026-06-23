import json
from contextlib import contextmanager
from flaskr_new.asaai.ollama_client import generate_from_ollama, resolve_ollama_model, test_ollama_model as check_ollama_model


@contextmanager
def _resp(payload):
    class _R:
        def read(self): return json.dumps(payload).encode()
    yield _R()


def _fake_urlopen(routes):
    """routes: {url-suffix: payload}; asserts on POST body via the request's data."""
    def urlopen(req, timeout):
        body = json.loads(req.data) if req.data else None
        for suffix, payload in routes.items():
            if req.full_url.endswith(suffix):
                return _resp(payload(body, timeout) if callable(payload) else payload)
        raise AssertionError(f"unexpected url {req.full_url}")
    return urlopen


def _tags(*names):
    return {"models": [{"name": n} for n in names]}

def test_resolve_ollama_model_accepts_profiles_and_raw_tags(monkeypatch):
    monkeypatch.delenv("ASAAI_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert resolve_ollama_model("desktop") == "qwen3.5:latest"
    assert resolve_ollama_model("laptop") == "qwen3:4b"
    assert resolve_ollama_model("fast") == "gemma3:1b"
    assert resolve_ollama_model("custom:latest") == "custom:latest"

def test_generate_from_ollama_parses_response(monkeypatch):
    def gen(body, timeout):
        assert body["model"] == "qwen3.5:latest"
        assert body["options"]["num_predict"] == 160
        assert timeout == 12
        return {"response": "Hallo von Ollama"}
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.urlopen",
                        _fake_urlopen({"/api/tags": _tags("qwen3.5:latest"), "/api/generate": gen}))
    assert generate_from_ollama("Sag hallo", timeout=12) == "Hallo von Ollama"

def test_generate_from_ollama_uses_configured_model_without_local_fallback(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:latest")
    def gen(body, timeout):
        assert body["model"] == "qwen3.5:latest"
        return {"response": "Configured model response"}
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.urlopen",
                        _fake_urlopen({"/api/generate": gen}))
    assert generate_from_ollama("Sag hallo") == "Configured model response"

def test_test_ollama_model_checks_generation(monkeypatch):
    def gen(body, timeout):
        assert body["model"] == "gemma3:1b"
        assert body["format"] == "json"
        assert body["options"]["num_predict"] == 120
        return {"response": '{"ok": true, "title": "Planner Test"}'}
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.urlopen",
                        _fake_urlopen({"/api/tags": _tags("gemma3:1b"), "/api/generate": gen}))
    result = check_ollama_model("gemma3:1b")
    assert result["ok"] is True
    assert result["installed"] is True
    assert result["generated"] is True
    assert result["response"] == '{"ok": true, "title": "Planner Test"}'

def test_test_ollama_model_rejects_non_json_response(monkeypatch):
    monkeypatch.setattr("flaskr_new.asaai.ollama_client.urlopen",
                        _fake_urlopen({"/api/tags": _tags("gemma3:1b"), "/api/generate": {"response": "ok"}}))
    result = check_ollama_model("gemma3:1b")
    assert result["ok"] is False
    assert result["installed"] is True
    assert result["generated"] is False
    assert "Planner-JSON" in result["error"]
