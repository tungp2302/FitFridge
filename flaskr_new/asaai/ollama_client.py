"""Client für eine lokale Ollama-Instanz (HTTP /api/generate)."""
import os
import json
from typing import Optional
from urllib.request import Request, urlopen

from flask import g, has_app_context


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:latest"

OLLAMA_MODEL_CHOICES = [
    {"name": "qwen3.5:latest", "label": "Qwen 3.5 latest (desktop, 9B)"},
    {"name": "qwen3:4b", "label": "Qwen 3 4B (laptop)"},
    {"name": "gemma3:1b", "label": "Gemma 3 1B (fast)"},
]


def resolve_ollama_model(model: Optional[str] = None) -> Optional[str]:
    """Return the configured Ollama model tag (explicit arg, stored setting,
    or env OLLAMA_MODEL), or None if nothing is set."""
    return (model or _stored_ollama_model() or os.getenv("OLLAMA_MODEL") or "").strip() or None


def _stored_ollama_model() -> Optional[str]:
    if not has_app_context():
        return None
    user = getattr(g, "user", None)
    if user is None:
        return None
    try:
        from ..app_settings_repo import get_settings

        return get_settings(user["id"]).get("llm_model")
    except Exception:
        return None


def _http_json(url: str, payload: Optional[dict], timeout: int) -> dict:
    """GET (payload=None) oder POST JSON; urlopen wirft bei HTTP-Fehlern."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _local_model_names(endpoint: str) -> list[str]:
    """Return locally installed Ollama model names."""
    payload = _http_json(f"{endpoint}/api/tags", None, 10)
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    return [s for m in models
            if isinstance(m, dict) and isinstance(m.get("name"), str) and (s := m["name"].strip())]


def _resolve_endpoint(base_url: Optional[str] = None) -> str:
    return (base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def test_ollama_model(model: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 20) -> dict:
    """Check whether Ollama can handle the JSON mode used by the recipe planner."""
    endpoint = _resolve_endpoint(base_url)
    selected_model = resolve_ollama_model(model) or DEFAULT_OLLAMA_MODEL
    names = _local_model_names(endpoint)
    if selected_model not in names:
        return {
            "ok": False,
            "model": selected_model,
            "installed": False,
            "generated": False,
            "installed_models": names,
            "error": "Modell ist lokal nicht installiert.",
        }

    data = _http_json(
        f"{endpoint}/api/generate",
        {
            "model": selected_model,
            "prompt": (
                "Antworte nur mit einem JSON-Objekt: "
                '{"ok":true,"title":"Planner Test","estimated_macros":{"protein":60,"fat":25}}'
            ),
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_predict": 120,
            },
        },
        timeout,
    )
    text = data.get("response") if isinstance(data, dict) else ""
    parsed = {}
    if isinstance(text, str) and text.strip():
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {}
    generated = isinstance(parsed, dict) and parsed.get("ok") is True
    return {
        "ok": generated,
        "model": selected_model,
        "installed": True,
        "generated": generated,
        "installed_models": names,
        "response": text.strip() if isinstance(text, str) else "",
        "error": "" if generated else "Modell antwortet, aber nicht mit brauchbarem Planner-JSON.",
    }


def generate_from_ollama(
    prompt: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 30,
    num_predict: Optional[int] = None,
    format_json: bool = False,
    temperature: float = 0.2,
) -> str:
    """Schickt Prompt an lokale Ollama-Instanz und gibt den Text zurück.

    ``base_url`` fällt auf OLLAMA_BASE_URL bzw. http://127.0.0.1:11434 zurück,
    das Modell auf das konfigurierte oder erste lokal installierte Modell.
    """
    endpoint = _resolve_endpoint(base_url)
    selected_model = resolve_ollama_model(model)
    if not selected_model:
        # erstes lokal installiertes Modell, sonst Default
        names = _local_model_names(endpoint)
        selected_model = names[0] if names else DEFAULT_OLLAMA_MODEL

    payload = {
        "model": selected_model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": int(num_predict or int(os.getenv("OLLAMA_NUM_PREDICT", "160"))),
        },
    }
    if format_json:
        payload["format"] = "json"

    data = _http_json(f"{endpoint}/api/generate", payload, timeout)
    text = data.get("response") if isinstance(data, dict) else None
    return text.strip() if isinstance(text, str) else str(data).strip()
