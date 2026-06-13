"""Minimal AI helpers kept for FitFridge."""

from .freestyle_recipe import build_prompt, generate_freestyle_recipe, generate_freestyle_recipes
from .ollama_client import generate_from_ollama, resolve_ollama_model

__all__ = [
    "build_prompt",
    "generate_freestyle_recipe",
    "generate_freestyle_recipes",
    "generate_from_ollama",
    "resolve_ollama_model",
]
