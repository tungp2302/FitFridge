"""LLM-Enricher für Recipe Matcher.

Erweitert die deterministischen Matcher-Resultate mit LLM-Insights.
Nutzt den lokalen Ollama-Adapter (Tungs ollama_client) um Re-Ranking,
Erklärungen und Substitutions-Vorschläge zu generieren.

Hauptfunktion:
- enrich_recipes_with_llm(matches, fridge_items, daily_goal=None)

Architektur:
- Recipe Matcher liefert deterministische Kandidaten (TheMealDB)
- LLM-Enricher bewertet sie kontextuell und fügt natürliche Sprache hinzu
- Trennung von Logik (this file) und LLM-Verbindung (ollama_client.py)
"""

from __future__ import annotations

import json
from typing import Optional

from .ollama_client import generate_from_ollama


def build_enricher_prompt(matches, fridge_items, daily_goal=None):
    """Baut den Prompt für das LLM aus Matcher-Resultaten.

    Der Prompt fordert das LLM auf:
    1. Die Top-Rezepte zu identifizieren (basierend auf Match-Score + Macros)
    2. Eine kurze Erklärung pro Empfehlung
    3. Substitutions-Vorschläge für fehlende Zutaten

    Parameter:
        matches (list): Resultate von find_recipes_matching_fridge()
        fridge_items (list): Liste von Kühlschrank-Items
        daily_goal (dict, optional): Verbleibendes Tagesziel pro Macro,
            z.B. {"protein": 30, "carbs": 100, "fat": 20}

    Returns:
        str: Vollständiger Prompt für Ollama
    """
    # Daten kompakt zusammenfassen (LLM mag knappe Inputs)
    payload = {
        "fridge_items": [item.get("name", "") for item in fridge_items],
        "matches": [
            {
                "name": m["recipe"]["name"],
                "score": m["match_score"],
                "available": m["available"],
                "missing": m["missing"],
            }
            for m in matches
        ],
        "daily_goal_remaining": daily_goal or {},
    }

    # System-Prompt: was soll das LLM tun?
    return (
        "Du bist ein lokaler Rezept-Berater für die FitFridge-App. "
        "Antworte auf Deutsch, knapp und präzise. "
        "Deine Aufgabe: Analysiere die Liste von Rezept-Kandidaten und "
        "wähle die 3 besten Empfehlungen für den Nutzer aus.\n\n"
        "Berücksichtige:\n"
        "- Match-Score (mehr verfügbare Zutaten = besser)\n"
        "- Anzahl fehlender Zutaten (weniger = besser)\n"
        "- Verbleibendes Tagesziel (falls angegeben)\n\n"
        "Gib genau drei Empfehlungen im folgenden Format zurück, "
        "jeweils mit Erklärung und Substitutions-Vorschlag:\n\n"
        "1. <Rezeptname>\n"
        "   Warum: <1-2 Sätze>\n"
        "   Substitution für fehlende Zutaten: <Vorschlag>\n\n"
        "2. <Rezeptname>\n"
        "   Warum: <1-2 Sätze>\n"
        "   Substitution: <Vorschlag>\n\n"
        "3. <Rezeptname>\n"
        "   Warum: <1-2 Sätze>\n"
        "   Substitution: <Vorschlag>\n\n"
        "Antworte nur mit den drei Empfehlungen, ohne weiteren Text.\n\n"
        f"Daten:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def enrich_recipes_with_llm(
    matches,
    fridge_items,
    daily_goal=None,
    model=None,
    base_url=None,
    timeout=120,
):
    """Erweitert Matcher-Resultate mit LLM-Insights.

    Schickt die Top-Matches an das lokale LLM (Ollama) und bekommt
    eine re-rankte Liste mit Erklärungen und Substitutions-Vorschlägen.

    Beispiel:
        from .recipe_matcher import find_recipes_matching_fridge

        fridge = [{"name": "chicken"}, {"name": "rice"}]
        matches = find_recipes_matching_fridge(fridge)
        result = enrich_recipes_with_llm(matches, fridge)
        print(result["llm_recommendation"])

    Parameter:
        matches (list): Resultate von find_recipes_matching_fridge()
        fridge_items (list): Liste von Kühlschrank-Items
        daily_goal (dict, optional): Verbleibendes Tagesziel
        model (str, optional): Ollama-Modell, default qwen3.5:latest
        base_url (str, optional): Ollama-Endpoint
        timeout (int): HTTP-Timeout in Sekunden

    Returns:
        dict: {
            "llm_recommendation": str (Text vom LLM),
            "original_matches": list (die ursprünglichen Matcher-Resultate),
            "prompt_used": str (für Debugging)
        }
    """
    # Edge Case: Keine Matches
    if not matches:
        return {
            "llm_recommendation": "Keine passenden Rezepte gefunden.",
            "original_matches": [],
            "prompt_used": "",
        }

    # Nur Top 5 ans LLM schicken (sonst zu viel Text)
    top_matches = matches[:5]

    # Prompt bauen
    prompt = build_enricher_prompt(top_matches, fridge_items, daily_goal)

    # LLM-Aufruf
    try:
        llm_response = generate_from_ollama(
            prompt=prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
            num_predict=500,  # genug für 3 Empfehlungen
        )
    except Exception as e:
        # Falls Ollama nicht läuft oder timeout: graceful fallback
        return {
            "llm_recommendation": f"LLM nicht verfügbar: {e}",
            "original_matches": top_matches,
            "prompt_used": prompt,
        }

    return {
        "llm_recommendation": llm_response,
        "original_matches": top_matches,
        "prompt_used": prompt,
    }