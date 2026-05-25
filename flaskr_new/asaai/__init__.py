"""ASaAI package for FitFridge."""

from .local_insight import build_insight_prompt, generate_ai_insight
from .ollama_client import generate_from_ollama
from .recipe_matcher import find_recipes_matching_fridge, calculate_match
