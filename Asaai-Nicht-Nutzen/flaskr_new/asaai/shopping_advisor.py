"""KI-basierte intelligente Einkaufsliste für FitFridge.

Analysiert:
- Aktuelle Bestände (was wird bald leer?)
- Verbrauchshistorie (was wird oft gekauft?)
- Kühlschrank-Inhalt vs. typische Rezepte

LLM bewertet und sortiert die Empfehlungen nach Dringlichkeit.

Hauptfunktionen:
- find_low_stock_items: Items mit niedrigem Bestand identifizieren
- find_frequently_consumed: Items aus Verbrauchsdaten
- generate_shopping_list: LLM-basierte Priorisierung
"""

from __future__ import annotations

import json
from typing import Optional

from .ollama_client import generate_from_ollama


# Threshold: Wenn weniger als das vorhanden, gilt als "low stock"
LOW_STOCK_THRESHOLD_G = 100.0
LOW_STOCK_THRESHOLD_ML = 200.0
LOW_STOCK_THRESHOLD_PIECES = 2


def find_low_stock_items(fridge_items):
    """Findet Items, deren Bestand niedrig ist.

    Schwellwerte:
    - Gewichts-Items (g, kg): < 100g
    - Volumen-Items (ml, l): < 200ml
    - Zähl-Items (stk): < 2

    Parameter:
        fridge_items (list): Liste von Kühlschrank-Items

    Returns:
        list: Items mit niedrigem Bestand
    """
    if not fridge_items:
        return []

    low_stock = []
    for item in fridge_items:
        # sqlite3.Row → dict
        item_dict = dict(item) if hasattr(item, "keys") else dict(item)

        amount = float(item_dict.get("current_amount", 0))
        unit = item_dict.get("unit", "g").lower()

        # Konvertierung zu Standardeinheit
        if unit == "kg":
            amount_normalized = amount * 1000
            threshold = LOW_STOCK_THRESHOLD_G
        elif unit == "l":
            amount_normalized = amount * 1000
            threshold = LOW_STOCK_THRESHOLD_ML
        elif unit == "ml":
            amount_normalized = amount
            threshold = LOW_STOCK_THRESHOLD_ML
        elif unit == "stk":
            amount_normalized = amount
            threshold = LOW_STOCK_THRESHOLD_PIECES
        else:  # default g
            amount_normalized = amount
            threshold = LOW_STOCK_THRESHOLD_G

        if amount_normalized < threshold:
            low_stock.append({
                "name": item_dict.get("name", "Unbekannt"),
                "current_amount": amount,
                "unit": unit,
                "urgency": "high" if amount_normalized < threshold / 2 else "medium",
            })

    return low_stock


def find_frequently_consumed(consumption_history, min_count=3):
    """Findet häufig verbrauchte Produkte aus der Historie.

    Parameter:
        consumption_history (list): Liste von Log-Einträgen mit
                                    {product_id, amount, ...}
        min_count (int): Mindest-Anzahl Einträge um als "häufig" zu zählen

    Returns:
        list: Produkte mit Anzahl Verbräuche, sortiert nach Häufigkeit
    """
    if not consumption_history:
        return []

    # Zähle pro product_id
    counts = {}
    for entry in consumption_history:
        product_id = entry.get("product_id")
        if product_id is None:
            continue
        counts[product_id] = counts.get(product_id, 0) + 1

    # Filtere nach min_count
    frequent = [
        {"product_id": pid, "consumption_count": count}
        for pid, count in counts.items()
        if count >= min_count
    ]

    # Sortiere nach Häufigkeit (höchste zuerst)
    frequent.sort(key=lambda f: f["consumption_count"], reverse=True)
    return frequent


def build_shopping_prompt(low_stock_items, frequent_items=None):
    """Baut den Prompt für das LLM mit Shopping-Vorschlägen.

    Parameter:
        low_stock_items (list): Items mit niedrigem Bestand
        frequent_items (list, optional): Häufig verbrauchte Items

    Returns:
        str: Vollständiger Prompt für Ollama
    """
    payload = {
        "low_stock": low_stock_items,
        "frequently_consumed": frequent_items or [],
    }

    return (
        "Du bist ein Einkaufs-Assistent für die FitFridge-App. "
        "Antworte auf Deutsch, knapp und praktisch.\n\n"
        "Du erhältst:\n"
        "- Items mit niedrigem Bestand (urgency: high/medium)\n"
        "- Häufig verbrauchte Items (optional)\n\n"
        "Generiere eine sortierte Einkaufsliste mit folgendem Format:\n\n"
        "🔴 Dringend (heute kaufen):\n"
        "- Item: <Name> (<Menge> <Einheit>)\n"
        "  Grund: <warum dringend>\n\n"
        "🟡 Bald nötig (diese Woche):\n"
        "- Item: <Name>\n"
        "  Grund: <warum bald>\n\n"
        "💡 Vorschläge (basierend auf Gewohnheiten):\n"
        "- <Vorschlag mit Begründung>\n\n"
        "Antworte nur mit dieser Struktur, ohne Vorwort.\n\n"
        f"Daten:\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
    )


def generate_shopping_list(
    fridge_items,
    consumption_history=None,
    model=None,
    base_url=None,
    timeout=120,
):
    """Generiert eine KI-basierte Einkaufsliste.

    Pipeline:
    1. Niedrige Bestände identifizieren (lokal, schnell)
    2. Häufig verbrauchte Items identifizieren (aus History)
    3. LLM priorisiert und erklärt

    Parameter:
        fridge_items (list): Aktuelle Kühlschrank-Items
        consumption_history (list, optional): Tungs consumption_log
        model, base_url, timeout: Ollama-Konfiguration

    Returns:
        dict: {
            "shopping_list_text": str,
            "low_stock_items": list,
            "frequent_items": list,
        }
    """
    # Phase 1: Lokale Analyse (deterministisch)
    low_stock = find_low_stock_items(fridge_items)
    frequent = find_frequently_consumed(consumption_history or [])

    # Edge Case: Nichts zu empfehlen
    if not low_stock and not frequent:
        return {
            "shopping_list_text": "Dein Kühlschrank ist gut gefüllt. Keine dringenden Einkäufe nötig.",
            "low_stock_items": [],
            "frequent_items": [],
        }

    # Phase 2: LLM-basierte Priorisierung
    prompt = build_shopping_prompt(low_stock, frequent)

    try:
        shopping_list_text = generate_from_ollama(
            prompt=prompt,
            model=model,
            base_url=base_url,
            timeout=timeout,
            num_predict=600,
        )
    except Exception as e:
        # Graceful fallback ohne LLM
        fallback = "EINKAUFSLISTE (ohne KI):\n\n"
        if low_stock:
            fallback += "🔴 Niedriger Bestand:\n"
            for item in low_stock:
                fallback += f"- {item['name']} (nur noch {item['current_amount']} {item['unit']})\n"
        if frequent:
            fallback += "\n📊 Häufig verbraucht:\n"
            for item in frequent[:5]:
                fallback += f"- Product-ID {item['product_id']} ({item['consumption_count']}x)\n"
        shopping_list_text = fallback + f"\n[LLM nicht verfügbar: {e}]"

    return {
        "shopping_list_text": shopping_list_text,
        "low_stock_items": low_stock,
        "frequent_items": frequent,
    }