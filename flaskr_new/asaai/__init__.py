"""ASaAI package for FitFridge."""

from .local_insight import build_insight_prompt, generate_ai_insight
from .ollama_client import generate_from_ollama
from .recipe_matcher import find_recipes_matching_fridge, calculate_match
from .llm_enricher import enrich_recipes_with_llm, enrich_with_full_pipeline
from .macro_calculator import (
    calculate_recipe_macros,
    calculate_ingredient_macros,
    parse_measure_string,
    rank_by_daily_goal,
)