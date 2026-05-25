"""Ollama-backed local LLM client for ASaAI.

This module talks to a locally running Ollama server over HTTP.
It uses the standard `/api/generate` endpoint so the backend can be
used without extra Python dependencies beyond `requests`.
"""
from __future__ import annotations

import os
from typing import Any, Iterable, Optional

import requests


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:latest"


def _build_prompt(prompt: str, system: Optional[str] = None) -> str:
    if system:
        return f"{system.strip()}\n\n{prompt.strip()}"
    return prompt


def _detect_local_model(endpoint: str) -> str:
    """Pick the first locally installed Ollama model when no model is configured."""
    response = requests.get(f"{endpoint}/api/tags", timeout=10)
    response.raise_for_status()

    payload = response.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    if isinstance(models, list) and models:
        first = models[0]
        if isinstance(first, dict):
            name = first.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()

    return DEFAULT_OLLAMA_MODEL


def generate_from_ollama(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 30,
    system: Optional[str] = None,
    num_predict: Optional[int] = None,
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
    selected_model = model or os.getenv("OLLAMA_MODEL")
    if not selected_model:
        selected_model = _detect_local_model(endpoint)
    payload_prompt = _build_prompt(prompt, system=system)

    response = requests.post(
        f"{endpoint}/api/generate",
        json={
            "model": selected_model,
            "prompt": payload_prompt,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.3,
                "num_predict": int(num_predict or int(os.getenv("OLLAMA_NUM_PREDICT", "160"))),
            },
        },
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
