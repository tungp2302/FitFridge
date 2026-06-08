"""Nutrition Insights Generator für FitFridge.

Analysiert die Macro-Verteilung im Kühlschrank und generiert
natürlich-sprachliche Insights via LLM.

Funktionen:
- analyze_fridge_macros(fridge_items): Aggregierte Macro-Übersicht
- generate_nutrition_insight(fridge_items, daily_goal): LLM-Bericht
"""

from __future__ import annotations

import json
from typing import Optional

from .ollama_client import generate_from_ollama
from ..nutrition_service import calculate_for_amount


def analyze_fridge_macros(fridge_items):
    """Berechnet die Gesamt-Macros des aktuellen Kühlschrank-Inhalts.

    Geht durch alle Items, berechnet pro Item die Macros mit der
    aktuellen Menge, summiert auf.

    Parameter:
        fridge_items (list): Liste von Items mit name, current_amount,
                             unit, *_per_100g Feldern

    Returns:
        dict: {
            "total_macros": {"kcal": ..., "protein": ..., ...},
            "items_count": int,
            "items_breakdown": list (pro Item: name, macros)
        }
    """
    if not fridge_items:
        return {
            "total_macros": {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0},
            "items_count": 0,
            "items_breakdown": [],
        }

    total = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    breakdown = []

    for item in fridge_items:
        # sqlite3.Row -> dict
        if hasattr(item, "keys"):
            item_data = {key: item[key] for key in item.keys()}
        else:
            item_data = dict(item)

        amount = item_data.get("current_amount", 0)
        unit = item_data.get("unit", "g")

        # Macros pro Item berechnen (nutzt nutrition_service aus SE!)
        macros = calculate_for_amount(item_data, amount, unit)

        total["kcal"] += macros["kcal"]
        total["protein"] += macros["protein"]
        total["fat"] += macros["fat"]
        total["carbs"] += macros["carbs"]

        breakdown.append({
            "name": item_data.get("name", "Unbekannt"),
            "amount": amount,
            "unit": unit,
            "macros": macros,
        })

    # Runden
    total = {k: round(v, 1) for k, v in total.items()}

    return {
        "total_macros": total,
        "items_count": len(fridge_items),
        "items_breakdown": breakdown,
    }


def build_insight_prompt(analysis, daily_goal=None):
    """Baut den Prompt für das LLM mit Macro-Analyse.

    Das LLM soll:
    - Den Macro-Mix bewerten
    - Mängel oder Überschüsse identifizieren
    - Konkrete Empfehlungen geben (in natürlicher Sprache)

    Parameter:
        analysis (dict): Resultat von analyze_fridge_macros()
        daily_goal (dict, optional): Tagesziele {"protein": 120, ...}

    Returns:
        str: Vollständiger Prompt für Ollama
    """
    payload = {
        "fridge_total_macros": analysis["total_macros"],
        "items_count": analysis["items_count"],
        "items": [
            {
                "name": item["name"],
                "amount": f"{item['amount']} {item['unit']}",
                "macros": item["macros"],
            }
            for item in analysis["items_breakdown"]
        ],
        "daily_goal": daily_goal or {},
    }

    return (
        "Du bist ein Ernährungs-Berater für die FitFridge-App. "
        "Antworte auf Deutsch, knapp und konstruktiv.\n\n"
        "Du erhältst:\n"
        "- Die Gesamt-Nährwerte aller Produkte im Kühlschrank\n"
        "- Eine Liste aller Items mit Mengen und Macros\n"
        "- Das Tagesziel (falls angegeben)\n\n"
        "Generiere einen kurzen, hilfreichen Bericht in 3 Abschnitten:\n\n"
        "Macro-Übersicht:\n"
        "- 1-2 Sätze zur aktuellen Macro-Verteilung im Kühlschrank\n\n"
        "Stärken & Lücken:\n"
        "- 2-3 Stichpunkte: Was ist gut vorrätig, was fehlt?\n\n"
        "Empfehlungen:\n"
        "- 2-3 konkrete Vorschläge (Nachkaufen, Gerichte planen, etc.)\n\n"
        "Antworte nur mit diesen drei Abschnitten, knapp und auf Deutsch.\n\n"
        f"Daten:\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
    )


def generate_nutrition_insight(
    fridge_items,
    daily_goal=None,
    model=None,
    base_url=None,
    timeout=120,
):
    """Hauptfunktion: Generiert einen Ernährungs-Insight für den Kühlschrank.

    Pipeline:
    1. Macros analysieren (analyze_fridge_macros)
    2. Prompt bauen
    3. LLM aufrufen
    4. Antwort zurückgeben

    Beispiel:
        items = fridge_repo.list_items()
        insight = generate_nutrition_insight(items, daily_goal={"protein": 120})
        print(insight["insight_text"])

    Parameter:
        fridge_items (list): Items aus fridge_repo.list_items()
        daily_goal (dict, optional): Tagesziele
        model, base_url, timeout: Ollama-Konfiguration

    Returns:
        dict: {
            "insight_text": str (LLM-Antwort),
            "analysis": dict (die Macro-Analyse),
        }
    """
    # Edge Case: Leerer Kühlschrank
    if not fridge_items:
        return {
            "insight_text": "Dein Kühlschrank ist leer. Füge Produkte hinzu, um einen Bericht zu erhalten.",
            "analysis": analyze_fridge_macros([]),
        }

    # Phase 1: Macros analysieren
    analysis = analyze_fridge_macros(fridge_items)

    # Phase 2: Prompt + LLM
    prompt = build_insight_prompt(analysis, daily_goal)

    try:
        insight_text = generate_from_ollama(
            prompt=prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
            num_predict=500,
        )
    except Exception as e:
        insight_text = f"LLM nicht verfügbar: {e}"

    return {
        "insight_text": insight_text,
        "analysis": analysis,
    }