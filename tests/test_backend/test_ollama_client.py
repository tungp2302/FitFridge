from flaskr_new.asaai.ollama_client import generate_from_ollama


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
