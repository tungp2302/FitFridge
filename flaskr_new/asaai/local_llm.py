"""Local LLM adapter using llama.cpp / llama-cpp-python.

This module provides a thin wrapper that loads a ggml quantized model
via `llama_cpp.Llama` if available. It intentionally keeps the API
small so the rest of the app can call it without importing heavy
dependencies when not needed.
"""
from __future__ import annotations

import os
from typing import Optional


def _default_model_path() -> Optional[str]:
    # Allow overriding via env var ASAAI_LOCAL_MODEL_PATH
    return os.getenv("ASAAI_LOCAL_MODEL_PATH")


def generate_from_local(prompt: str, model_path: Optional[str] = None, max_tokens: int = 512, temperature: float = 0.2, timeout: int = 30) -> str:
    """Generate text from a local ggml model.

    Raises RuntimeError if the required dependency is missing or the model
    path cannot be found.
    """
    model = model_path or _default_model_path()
    if not model:
        raise RuntimeError("No local model path provided. Set ASAAI_LOCAL_MODEL_PATH to a ggml model file.")

    try:
        # Import lazily to avoid bringing heavy deps into test/CI when not used
        from llama_cpp import Llama
    except Exception as exc:  # pragma: no cover - env dependent
        raise RuntimeError(
            "llama_cpp is required for local LLM backend. Install with `pip install llama-cpp-python`."
        ) from exc

    # Create Llama instance and query
    llm = Llama(model_path=model)
    out = llm.create(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
    # Normalise output format
    if isinstance(out, dict):
        choices = out.get("choices") or []
        if choices:
            first = choices[0]
            # old/new formats differ, handle both
            text = first.get("text") or first.get("message", {}).get("content") or ""
            return text
    # Fallback: try string conversion
    return str(out)
