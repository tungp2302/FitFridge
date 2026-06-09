"""Ollama-backed local LLM client for ASaAI.

This module talks to a locally running Ollama server over HTTP.
It uses the standard `/api/generate` endpoint so the backend can be
used without extra Python dependencies beyond `requests`.
"""
from __future__ import annotations

import os
import json
from typing import Any, Optional

import requests
from flask import g, has_app_context


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:latest"

OLLAMA_MODEL_CHOICES = [
    {
        "id": "desktop",
        "name": "qwen3.5:latest",
        "label": "Qwen 3.5 latest (desktop, 9B)",
    },
    {
        "id": "laptop",
        "name": "qwen3:4b",
        "label": "Qwen 3 4B (laptop)",
    },
    {
        "id": "fast",
        "name": "gemma3:1b",
        "label": "Gemma 3 1B (fast)",
    },
]

_OLLAMA_MODEL_ALIASES = {
    choice["id"]: choice["name"]
    for choice in OLLAMA_MODEL_CHOICES
}


def _build_prompt(prompt: str, system: Optional[str] = None) -> str:
    if system:
        return f"{system.strip()}\n\n{prompt.strip()}"
    return prompt


def resolve_ollama_model(model: Optional[str] = None) -> Optional[str]:
    """Resolve a configured model alias to the Ollama model name.

    Accepts either one of the local profile IDs (`desktop`, `laptop`, `fast`)
    or a raw Ollama model tag such as `qwen3:4b`.
    """
    selected = (model or _stored_ollama_model() or os.getenv("ASAAI_OLLAMA_MODEL") or os.getenv("OLLAMA_MODEL") or "").strip()
    if not selected:
        return None
    return _OLLAMA_MODEL_ALIASES.get(selected, selected)


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


def _local_model_names(endpoint: str) -> list[str]:
    """Return locally installed Ollama model names."""
    response = requests.get(f"{endpoint}/api/tags", timeout=10)
    response.raise_for_status()

    payload = response.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    names = []
    if isinstance(models, list) and models:
        for model_info in models:
            if isinstance(model_info, dict):
                name = model_info.get("name")
            else:
                name = None
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return names


def _detect_local_model(endpoint: str) -> str:
    """Pick the first locally installed Ollama model when no model is configured."""
    names = _local_model_names(endpoint)
    if names:
        return names[0]

    return DEFAULT_OLLAMA_MODEL


def test_ollama_model(model: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 20) -> dict:
    """Check whether Ollama can handle the JSON mode used by the recipe planner."""
    endpoint = (base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    selected_model = resolve_ollama_model(model) or DEFAULT_OLLAMA_MODEL
    names = _local_model_names(endpoint)
    if selected_model not in names:
        return {
            "ok": False,
            "model": selected_model,
            "base_url": endpoint,
            "installed": False,
            "generated": False,
            "installed_models": names,
            "error": "Modell ist lokal nicht installiert.",
        }

    response = requests.post(
        f"{endpoint}/api/generate",
        json={
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
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
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
        "base_url": endpoint,
        "installed": True,
        "generated": generated,
        "installed_models": names,
        "response": text.strip() if isinstance(text, str) else "",
        "error": "" if generated else "Modell antwortet, aber nicht mit brauchbarem Planner-JSON.",
    }


def generate_from_ollama(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 30,
    system: Optional[str] = None,
    num_predict: Optional[int] = None,
    format_json: bool = False,
    **_: Any,
) -> str:
    """Generate a response via a locally running Ollama instance.

    Parameters
    ----------
    prompt:
        User prompt to send to Ollama.
    api_key:
        Unused placeholder for parity with remote backends.
    model:
        Ollama model name, defaults to `OLLAMA_MODEL` or `llama3.1`.
    base_url:
        Base URL of the local Ollama server, defaults to `OLLAMA_BASE_URL`
        or `http://127.0.0.1:11434`.
    timeout:
        HTTP timeout in seconds.
    system:
        Optional system prompt to prepend.
    """
    del api_key

    endpoint = (base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    selected_model = resolve_ollama_model(model)
    if not selected_model:
        selected_model = _detect_local_model(endpoint)
    payload_prompt = _build_prompt(prompt, system=system)

    payload = {
        "model": selected_model,
        "prompt": payload_prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.2,
            "num_predict": int(num_predict or int(os.getenv("OLLAMA_NUM_PREDICT", "160"))),
        },
    }
    if format_json:
        payload["format"] = "json"

    response = requests.post(
        f"{endpoint}/api/generate",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()
    if isinstance(data, dict):
        text = data.get("response")
        if isinstance(text, str):
            return text.strip()
        message = data.get("message") or {}
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
    return str(data).strip()
