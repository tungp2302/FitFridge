"""Minimal AI helpers kept for FitFridge."""

from .freestyle_recipe import build_freestyle_recipe_prompt, generate_freestyle_recipe
from .ollama_client import generate_from_ollama, resolve_ollama_model

__all__ = [
    "build_freestyle_recipe_prompt",
    "generate_freestyle_recipe",
    "generate_from_ollama",
    "resolve_ollama_model",
]
