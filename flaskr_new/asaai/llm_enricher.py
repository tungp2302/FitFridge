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
from .recipe_matcher import _is_protein_source, _normalize_text

from .macro_calculator import (
    calculate_recipe_macros,
    rank_by_daily_goal,
)


def build_freestyle_recipe_prompt(fridge_items, daily_goal=None):
    """Build a strict JSON prompt for one realistic fridge-based recipe."""
    protein_items = [
        item.get("name", "") for item in fridge_items if _is_protein_source(item.get("name", ""))
    ]
    payload = {
        "fridge_items": [item.get("name", "") for item in fridge_items],
        "fridge_protein_items": protein_items,
        "daily_goal_remaining": daily_goal or {},
    }

    return (
        "Du bist ein realistischer Rezept-Generator für FitFridge. "
        "Erfinde GENAU EIN Rezept, das stark auf den vorhandenen Kühlschrank-Inhalt basiert. "
        "Bevorzuge Proteinquellen im Kühlschrank, dann Gemüse und Sättigungsbeilagen. "
        "Erfunde keine exotischen Zutaten, wenn eine einfachere Variante möglich ist. "
        "Nutze höchstens 3 Pantry-Staples wie Öl, Salz, Pfeffer, Zwiebel, Knoblauch. "
        "Wenn ein Proteinziel vorhanden ist, priorisiere proteinreiche Hauptzutaten und formuliere das Rezept entsprechend. "
        "Antworte ausschließlich als valides JSON-Objekt ohne Markdown, ohne Listen außerhalb des JSON und ohne Zusatztext.\n\n"
        "JSON-Schema:\n"
        "{\n"
        '  "title": "string",\n'
        '  "why_this_works": "string",\n'
        '  "ingredients": ["string"],\n'
        '  "instructions": ["string"],\n'
        '  "estimated_macros": {"kcal": number, "protein": number, "fat": number, "carbs": number},\n'
        '  "used_fridge_items": ["string"],\n'
        '  "pantry_assumptions": ["string"]\n'
        "}\n\n"
        f"Daten:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def generate_freestyle_recipe(
    fridge_items,
    daily_goal=None,
    model=None,
    base_url=None,
    timeout=120,
):
    """Generate one realistic recipe from fridge contents only."""
    if not fridge_items:
        return {
            "recipe": {
                "title": "No ingredients available",
                "why_this_works": "Dein Kühlschrank ist leer.",
                "ingredients": [],
                "instructions": ["Add ingredients to your fridge first."],
                "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
                "used_fridge_items": [],
                "pantry_assumptions": [],
            },
            "prompt_used": "",
            "raw_response": "",
        }

    prompt = build_freestyle_recipe_prompt(fridge_items, daily_goal)
    try:
        response = generate_from_ollama(
            prompt=prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
            num_predict=650,
        )
    except Exception as exc:
        return {
            "recipe": {
                "title": "LLM unavailable",
                "why_this_works": f"LLM error: {exc}",
                "ingredients": [],
                "instructions": ["Try again when Ollama is running."],
                "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
                "used_fridge_items": [item.get("name", "") for item in fridge_items],
                "pantry_assumptions": [],
            },
            "prompt_used": prompt,
            "raw_response": "",
        }

    parsed = _parse_json_response(response)
    if parsed is None:
        parsed = {
            "title": "Fridge freestyle recipe",
            "why_this_works": "The model returned unstructured text.",
            "ingredients": [],
            "instructions": [response.strip()],
            "estimated_macros": {"kcal": 0, "protein": 0, "fat": 0, "carbs": 0},
            "used_fridge_items": [item.get("name", "") for item in fridge_items],
            "pantry_assumptions": [],
        }

    return {
        "recipe": parsed,
        "prompt_used": prompt,
        "raw_response": response,
    }


def _parse_json_response(text):
    """Best-effort JSON parsing for LLM output."""
    if not text:
        return None
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(stripped[start : end + 1])
    except Exception:
        return None


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
    protein_items = [
        item.get("name") for item in fridge_items if _is_protein_source(item.get("name", ""))
    ]

    payload = {
        "fridge_items": [item.get("name", "") for item in fridge_items],
        "fridge_protein_items": protein_items,
        "matches": [
            {
                "name": m["recipe"]["name"],
                "score": m["match_score"],
                "available": m.get("available", []),
                "available_protein_sources": m.get("available_protein_sources", []),
                "missing": m.get("missing", []),
                "est_protein": m.get("est_protein"),
                "est_kcal": m.get("est_kcal"),
                "protein_per_100kcal": m.get("protein_per_100kcal"),
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

def enrich_with_full_pipeline(
    matches,
    fridge_items,
    daily_goal=None,
    top_n=5,
    model=None,
    base_url=None,
    timeout=120,
):
    """Komplette KI-Pipeline: Macros berechnen → Ranking → LLM-Re-Ranking.

    Das ist die "all-in-one" Funktion, die alle ASaAI-Bausteine verbindet.
    
    Pipeline:
    1. Macros pro Rezept berechnen (OpenFoodFacts + nutrition_service)
    2. Rezepte nach Daily Goal ranken (Protein/kcal-Passung)
    3. Top N ans LLM schicken für finale Re-Ranking + Erklärungen
    
    Beispiel:
        matches = find_recipes_matching_fridge(fridge)
        result = enrich_with_full_pipeline(
            matches=matches,
            fridge_items=fridge,
            daily_goal={"protein": 30, "kcal": 600},
            top_n=5,
        )
    
    Parameter:
        matches (list): Resultate von find_recipes_matching_fridge()
        fridge_items (list): Kühlschrank-Items
        daily_goal (dict): Verbleibendes Tagesziel
        top_n (int): Wie viele Top-Matches an LLM (default 5)
        model, base_url, timeout: Ollama-Konfiguration
    
    Returns:
        dict: {
            "llm_recommendation": str,
            "enriched_matches": list (mit Macros + Goal-Score),
            "pipeline_stats": dict (Statistik über Phasen)
        }
    """
    import time
    
    # Edge Case: Keine Matches
    if not matches:
        return {
            "llm_recommendation": "Keine Rezepte gefunden.",
            "enriched_matches": [],
            "pipeline_stats": {"total_matches": 0},
        }
    
    # Phase 1: Macros pro Rezept berechnen
    print("  [Pipeline] Phase 1: Berechne Macros pro Rezept...")
    start = time.time()
    
    enriched_matches = []
    for i, match in enumerate(matches[:top_n], 1):
        print(f"    Verarbeite Rezept {i}/{min(top_n, len(matches))}: {match['recipe']['name']}")
        macros = calculate_recipe_macros(match["recipe"])
        match["macros"] = macros
        enriched_matches.append(match)
    
    phase1_time = round(time.time() - start, 1)
    
    # Phase 2: Nach Daily Goal ranken
    print("  [Pipeline] Phase 2: Ranking nach Daily Goal...")
    if daily_goal:
        enriched_matches = rank_by_daily_goal(enriched_matches, daily_goal)
    
    # Phase 3: LLM-Re-Ranking mit allem Kontext
    print("  [Pipeline] Phase 3: LLM-Re-Ranking mit Macros...")
    start = time.time()
    
    prompt = build_full_pipeline_prompt(enriched_matches, fridge_items, daily_goal)
    
    try:
        llm_response = generate_from_ollama(
            prompt=prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
            num_predict=600,
        )
    except Exception as e:
        return {
            "llm_recommendation": f"LLM nicht verfügbar: {e}",
            "enriched_matches": enriched_matches,
            "pipeline_stats": {
                "total_matches": len(matches),
                "macros_calculated": len(enriched_matches),
                "phase1_seconds": phase1_time,
                "llm_failed": True,
            },
        }
    
    phase3_time = round(time.time() - start, 1)
    
    return {
        "llm_recommendation": llm_response,
        "enriched_matches": enriched_matches,
        "pipeline_stats": {
            "total_matches": len(matches),
            "macros_calculated": len(enriched_matches),
            "phase1_seconds": phase1_time,
            "phase3_seconds": phase3_time,
        },
    }


def build_full_pipeline_prompt(enriched_matches, fridge_items, daily_goal=None):
    """Baut den Prompt für die volle Pipeline mit Macros.
    
    Anders als build_enricher_prompt: enthält jetzt auch die berechneten
    Nährwerte pro Rezept, damit das LLM besser bewerten kann.
    """
    payload = {
        "fridge_items": [item.get("name", "") for item in fridge_items],
        "daily_goal_remaining": daily_goal or {},
        "matches": [
            {
                "name": m["recipe"]["name"],
                "match_score": m["match_score"],
                "goal_score": m.get("goal_score", 0),
                "macros": m.get("macros", {}),
                "available_ingredients": m["available"],
                "missing_ingredients": m["missing"],
            }
            for m in enriched_matches
        ],
    }
    
    return (
        "Du bist ein lokaler Rezept-Berater für die FitFridge-App. "
        "Antworte auf Deutsch, knapp und präzise.\n\n"
        "Du erhältst Rezept-Kandidaten mit:\n"
        "- match_score: Anteil verfügbarer Zutaten (0-1)\n"
        "- goal_score: Wie gut das Rezept zum Tagesziel passt (0-1, oder negativ bei Überschreitung)\n"
        "- macros: Berechnete Nährwerte des Rezepts (kcal, protein, fat, carbs)\n"
        "- available/missing_ingredients: Was da ist und was fehlt\n\n"
        "Wähle die 3 besten Rezepte aus und erkläre warum. Berücksichtige:\n"
        "- Verbleibendes Tagesziel (Protein-Lücke füllen, kcal-Limit einhalten)\n"
        "- Anzahl fehlender Zutaten (weniger = besser)\n"
        "- Nährwert-Passung\n\n"
        "Format pro Empfehlung:\n\n"
        "1. <Rezeptname>\n"
        "   Macros: <kcal> kcal, <protein>g Protein, <fat>g Fett, <carbs>g Carbs\n"
        "   Warum: <1-2 Sätze, beziehe dich auf Tagesziel falls relevant>\n"
        "   Substitution für fehlende Zutaten: <Vorschlag>\n\n"
        "2. ... (gleich)\n\n"
        "3. ... (gleich)\n\n"
        "Antworte nur mit den drei Empfehlungen.\n\n"
        f"Daten:\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
    )