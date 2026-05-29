# flaskr/api_db/external/openfoodfacts_client.py
"""OpenFoodFacts-Client fuer Barcode-Lookups mit Mengen-Parsing und Fallbacks."""

from __future__ import annotations

import json
import re
import ssl
import time
import unicodedata
from typing import Optional, Tuple, Dict
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import certifi
except ModuleNotFoundError:  # pragma: no cover - depends on local environment
    certifi = None

OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
OFF_STAGING_API_URL = "https://world.openfoodfacts.net/api/v2/product/{barcode}.json"

DEFAULT_USER_AGENT = "FitFridge/1.0 (university project; contact: you@example.com)"


PROCESSED_FOOD_KEYWORDS = {
    "chorizo",
    "sausage",
    "salami",
    "pepperoni",
    "burger",
    "nugget",
    "patty",
    "snack",
    "cookie",
    "biscuit",
    "cake",
    "chocolate",
    "cereal",
    "bar",
    "drink",
    "soda",
    "juice",
    "sauce",
    "ready meal",
    "instant",
    "microwave",
    "processed",
    "mix",
}


PRIMARY_FOOD_KEYWORDS = {
    "banana",
    "apple",
    "orange",
    "grape",
    "pear",
    "berry",
    "berries",
    "fruit",
    "vegetable",
    "veg",
    "chicken",
    "beef",
    "pork",
    "turkey",
    "fish",
    "salmon",
    "tuna",
    "shrimp",
    "broccoli",
    "carrot",
    "onion",
    "garlic",
    "potato",
    "rice",
    "pasta",
    "egg",
    "lentil",
    "beans",
    "tomato",
    "cucumber",
    "spinach",
}


PRIMARY_FOOD_ALIASES = {
    # German -> English primary foods
    "banane": "banana",
    "bananen": "banana",
    "apfel": "apple",
    "birne": "pear",
    "orange": "orange",
    "traube": "grape",
    "trauben": "grape",
    "hahnchen": "chicken",
    "huhnchen": "chicken",
    "huhn": "chicken",
    "hahnchenschenkel": "chicken thigh",
    "huhnerschenkel": "chicken thigh",
    "rind": "beef",
    "rindfleisch": "beef",
    "schwein": "pork",
    "schweinefleisch": "pork",
    "lachs": "salmon",
    "thunfisch": "tuna",
    "garnelen": "shrimp",
    "garnele": "shrimp",
    "brokkoli": "broccoli",
    "karotte": "carrot",
    "mohre": "carrot",
    "zwiebel": "onion",
    "zwiebeln": "onion",
    "knoblauch": "garlic",
    "kartoffel": "potato",
    "kartoffeln": "potato",
    "reis": "rice",
    "nudeln": "pasta",
    "nudel": "pasta",
    "ei": "egg",
    "eier": "egg",
    "tomate": "tomato",
    "tomaten": "tomato",
    "gurke": "cucumber",
    "spinat": "spinach",
}


def _first_string(*values: Optional[str]) -> str:
    for v in values:
        if v:
            return str(v)
    return ""


def _float_value(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _canonical_primary_query(query: str) -> str:
    normalized = _normalize_text(query)
    if not normalized:
        return ""

    mapped = PRIMARY_FOOD_ALIASES.get(normalized)
    if mapped:
        return mapped

    tokens = normalized.split()
    mapped_tokens = [PRIMARY_FOOD_ALIASES.get(token, token) for token in tokens]
    return " ".join(mapped_tokens)


def _is_primary_food_query(query: str) -> bool:
    normalized = _canonical_primary_query(query)
    if not normalized:
        return False
    from .asaai.ingredient_macros import lookup_ingredient

    if lookup_ingredient(normalized) is not None:
        return True
    return any(keyword in normalized for keyword in PRIMARY_FOOD_KEYWORDS)


def _ingredient_display_name(query: str) -> str:
    normalized = _normalize_text(query)
    if not normalized:
        return ""
    return " ".join(part.capitalize() for part in normalized.split())


def _llm_ai_product_metadata(query: str, canonical_query: str) -> dict:
    """Use Ollama to label a primary ingredient as a friendly AI entry."""
    from .asaai.ollama_client import generate_from_ollama

    prompt = (
        "Du bist ein Produkt-Normalisierer für FitFridge. "
        "Nimm einen Lebensmittel-Suchbegriff und gib ein kurzes JSON-Objekt zurück. "
        "Das Produkt soll ein unverarbeitetes Grundnahrungsmittel beschreiben, nicht ein Snack oder Fertigprodukt. "
        "Wenn der Eingabetext deutsch ist, antworte deutsch; wenn englisch, antworte englisch. "
        "Antworte nur als JSON ohne Markdown oder Zusatztext.\n\n"
        "JSON-Schema:\n"
        "{\n"
        '  "display_name": "string",\n'
        '  "why": "string"\n'
        "}\n\n"
        f"Suchbegriff: {query}\n"
        f"Canonical ingredient: {canonical_query}"
    )

    try:
        response = generate_from_ollama(prompt=prompt, timeout=8, num_predict=140)
    except Exception:
        return {}

    try:
        parsed = json.loads(response.strip())
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


def _build_generic_ingredient_product(query: str) -> Optional[Dict]:
    from .asaai.ingredient_macros import lookup_ingredient

    normalized = _canonical_primary_query(query)
    if not normalized:
        return None

    nutrients = lookup_ingredient(normalized)
    if nutrients is None:
        return None

    llm_meta = _llm_ai_product_metadata(query, normalized)
    display_name = _ingredient_display_name(query) or _ingredient_display_name(normalized)
    if isinstance(llm_meta, dict):
        display_name = llm_meta.get("display_name") or display_name

    return {
        "name": display_name,
        "brand": "FitFridge AI",
        "barcode": f"ingredient:{normalized}",
        "kcal_per_100g": float(nutrients.get("kcal_per_100g", 0.0)),
        "protein_per_100g": float(nutrients.get("protein_per_100g", 0.0)),
        "fat_per_100g": float(nutrients.get("fat_per_100g", 0.0)),
        "carbs_per_100g": float(nutrients.get("carbs_per_100g", 0.0)),
        "sugar_per_100g": 0.0,
        "total_amount": 100.0,
        "unit": "g",
        "raw_quantity": "100 g",
        "raw_product": {
            "ingredient_source": True,
            "ai_generated": True,
            "query": _normalize_text(query),
            "canonical_query": normalized,
            "ai_note": llm_meta.get("why") if isinstance(llm_meta, dict) else "",
        },
    }


def _score_off_product(query: str, product: dict) -> float:
    """Prefer raw ingredients over branded/processed products for food queries."""
    normalized_query = _canonical_primary_query(query)
    name = _normalize_text(product.get("name", ""))
    brand = _normalize_text(product.get("brand", ""))
    raw = product.get("raw_product") or {}

    score = 0.0

    if normalized_query and normalized_query == name:
        score += 60
    elif normalized_query and normalized_query in name:
        score += 35
    elif name and any(token in name for token in normalized_query.split()):
        score += 15

    if _is_primary_food_query(normalized_query):
        if any(keyword in name for keyword in PRIMARY_FOOD_KEYWORDS):
            score += 20
        if brand:
            score -= 5
        ingredients_text = _normalize_text(
            raw.get("ingredients_text_en")
            or raw.get("ingredients_text")
            or raw.get("categories")
            or ""
        )
        if any(keyword in ingredients_text for keyword in PROCESSED_FOOD_KEYWORDS):
            score -= 25
        if any(keyword in name for keyword in PROCESSED_FOOD_KEYWORDS):
            score -= 35
    else:
        if any(keyword in name for keyword in PROCESSED_FOOD_KEYWORDS):
            score -= 10

    # Prefer generic items with no obvious brand when querying raw foods
    if _is_primary_food_query(normalized_query) and not brand:
        score += 10

    return score


def _rank_off_products(query: str, products: list) -> list:
    return sorted(
        products,
        key=lambda product: (
            _score_off_product(query, product),
            product.get("protein_per_100g", 0.0),
            -product.get("kcal_per_100g", 0.0),
        ),
        reverse=True,
    )


def _parse_total_quantity(product_data: dict) -> Tuple[Optional[float], Optional[str]]:
    """
    Versucht eine Gesamtmenge zu extrahieren. Behandelt z.B.:
      - "400 g", "500ml", "1.5 l"
      - "2 x 250 g" -> 500 g
      - "4x100g" -> 400 g
    Gibt (amount, unit) oder (None, None).
    """
    raw = _first_string(product_data.get("quantity", ""), product_data.get("serving_size", "")).strip()
    if not raw:
        raw = _first_string(
            product_data.get("quantity_imported", ""),
            product_data.get("serving_size_imported", ""),
        ).strip()
    if not raw:
        return None, None

    # vereinfachen: entferne Klammern und Zusatztexte
    raw = re.sub(r"[\(\)\[\]].*?[\)\]\)]", "", raw)
    raw = raw.replace(",", ".").lower().strip()

    # Pattern: multiplicator e.g. "4 x 100 g" or "4x100g"
    m = re.search(r"(?:(\d+(?:\.\d+)?)\s*[x×]\s*)?(\d+(?:\.\d+)?)(?:\s*)(mg|g|gramm|grams|ml|l|liter|litre|stk|stueck|piece|pieces)?", raw)
    if not m:
        return None, None

    mult = float(m.group(1)) if m.group(1) else 1.0
    amount = float(m.group(2))
    unit = (m.group(3) or "").strip()

    # Normalisierung
    unit_map = {
        "gramm": "g", "grams": "g", "g": "g",
        "milliliter": "ml", "ml": "ml",
        "l": "l", "liter": "l", "litre": "l",
        "mg": "mg",
        "stk": "stk", "stueck": "stk", "piece": "stk", "pieces": "stk",
    }
    unit_norm = unit_map.get(unit, unit) if unit else None

    total = mult * amount
    # Falls unit in Liter, konvertiere zu ml? (wir behalten l, frontend kann entscheiden)
    return total, unit_norm


def _kJ_to_kcal(kj: float) -> float:
    return kj / 4.184 if kj else 0.0


def _make_ssl_context():
    """Return an SSL context using certifi if available, else system defaults."""
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _kcal_from_nutriments(nutriments: dict) -> float:
    """Normalize energy value from the nutriments dict to kcal per 100g."""
    if nutriments.get("energy-kcal_100g") is not None:
        return _float_value(nutriments.get("energy-kcal_100g"))
    if nutriments.get("energy-kcal_value") is not None:
        return _float_value(nutriments.get("energy-kcal_value"))
    if nutriments.get("energy_100g") is not None:
        return _kJ_to_kcal(_float_value(nutriments.get("energy_100g")))
    return 0.0


def search_product(barcode: str, user_agent: str = DEFAULT_USER_AGENT, use_staging: bool = False) -> Optional[Dict]:
    """
    Holt ein Produkt von Open Food Facts via Barcode.

    Returns:
      dict mit Schluesseln:
        name, brand, barcode,
        kcal_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g,
        total_amount (optional), unit (optional), raw_quantity (raw field)
      oder None, wenn nicht gefunden.
    """
    if not barcode:
        raise ValueError("barcode is required")

    url = OFF_STAGING_API_URL.format(barcode=barcode) if use_staging else OFF_API_URL.format(barcode=barcode)
    req = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )
    https_context = _make_ssl_context()

    try:
        with urlopen(req, timeout=10, context=https_context) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError(f"Open Food Facts request failed: {e}") from e
    except URLError as e:
        raise RuntimeError(f"Open Food Facts request failed: {e}") from e

    if payload.get("status") != 1:
        return None

    product = payload.get("product", {}) or {}
    nutriments = product.get("nutriments", {}) or {}

    # parse total amount if available
    total_amount, unit = _parse_total_quantity(product)

    kcal = _kcal_from_nutriments(nutriments)

    result = {
        "name": _first_string(product.get("product_name"), product.get("generic_name")),
        "brand": _first_string(product.get("brands"), product.get("brand_owner")),
        "barcode": _first_string(product.get("code"), barcode),
        "kcal_per_100g": float(kcal),
        "protein_per_100g": _float_value(nutriments.get("proteins_100g")),
        "fat_per_100g": _float_value(nutriments.get("fat_100g")),
        "carbs_per_100g": _float_value(nutriments.get("carbohydrates_100g")),
        "sugar_per_100g": _float_value(nutriments.get("sugars_100g")),
        "total_amount": total_amount,
        "unit": unit,
        "raw_quantity": product.get("quantity"),
        "raw_product": product,  # optional: kompletten Roh-Datensatz für Debug/erweiterte Verwendung
    }

    return result


def lookup_product(query: str, user_agent: str = DEFAULT_USER_AGENT, use_staging: bool = False) -> Optional[Dict]:
    """
    Nimmt entweder einen Barcode oder einen Produktnamen.

    - Zahlen werden direkt als Barcode behandelt.
    - Alles andere wird ueber die Open Food Facts Suche aufgeloest.
    """
    if not query:
        raise ValueError("query is required")

    if query.isdigit():
        return search_product(query, user_agent=user_agent, use_staging=use_staging)

    generic = _build_generic_ingredient_product(query)

    products = search_products(query, user_agent=user_agent, use_staging=use_staging, limit=10)
    if not products:
        return generic

    ranked = _rank_off_products(query, products)
    if not ranked:
        return generic

    best = ranked[0]
    if generic is not None and _is_primary_food_query(query):
        if _score_off_product(query, best) < 70:
            return generic

    return best


def search_products(query: str, user_agent: str = DEFAULT_USER_AGENT, use_staging: bool = False, limit: int = 10) -> Optional[list]:
    """
    Search OpenFoodFacts for multiple products matching `query`.

    Returns a list of product dicts (same shape as `search_product` returns)
    or an empty list if nothing found.
    """
    if not query:
        raise ValueError("query is required")

    base_url = OFF_STAGING_API_URL.rsplit("/api/v2/product/{barcode}.json", 1)[0] if use_staging else OFF_API_URL.rsplit("/api/v2/product/{barcode}.json", 1)[0]
    # Request JSON results (json=1)
    search_url = (
        f"{base_url}/cgi/search.pl?"
        f"search_terms={quote(query)}&search_simple=1&action=process&json=1"
    )

    request = Request(
        search_url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )

    https_context = _make_ssl_context()

    body = None
    try:
        with urlopen(request, timeout=10, context=https_context) as response:
            body = response.read().decode("utf-8")
    except Exception:
        return []

    if not body:
        return []

    try:
        payload = json.loads(body)
    except Exception:
        return []

    products = payload.get("products") or []
    results = []
    seen = set()
    for prod in products:
        code = prod.get("code") or prod.get("_id")
        if not code or code in seen:
            continue
        seen.add(code)
        try:
            full = search_product(code, user_agent=user_agent, use_staging=use_staging)
        except Exception:
            full = None
        if full:
            results.append(full)

    generic = _build_generic_ingredient_product(query)
    if generic is not None and _is_primary_food_query(query):
        results.insert(0, generic)

    ranked = _rank_off_products(query, results)

    if limit:
        ranked = ranked[:limit]

    return ranked


def ai_estimate(query: str) -> Optional[dict]:
    """Return an AI-generated estimate for a primary ingredient.

    Always attempts to provide a generic ingredient entry. If a curated
    nutrient lookup exists, it will be returned. Otherwise the function
    will still return a minimal AI-labelled product object (with zeros)
    so the frontend can offer an "AI estimate" choice.
    """
    if not query:
        return None

    # Prefer the richer generic product when available
    try:
        generic = _build_generic_ingredient_product(query)
    except Exception:
        generic = None

    if generic is not None:
        return generic

    # Fallback: ask the LLM for a friendly display name and note
    try:
        canonical = _canonical_primary_query(query)
    except Exception:
        canonical = _normalize_text(query)

    try:
        llm_meta = _llm_ai_product_metadata(query, canonical) or {}
    except Exception:
        llm_meta = {}

    display_name = llm_meta.get("display_name") or _ingredient_display_name(query) or query

    return {
        "name": display_name,
        "brand": "FitFridge AI",
        "barcode": f"ingredient:{_normalize_text(query)}",
        "kcal_per_100g": 0.0,
        "protein_per_100g": 0.0,
        "fat_per_100g": 0.0,
        "carbs_per_100g": 0.0,
        "sugar_per_100g": 0.0,
        "total_amount": 100.0,
        "unit": "g",
        "raw_quantity": "100 g",
        "raw_product": {
            "ai_generated": True,
            "query": _normalize_text(query),
            "canonical_query": canonical,
            "ai_note": llm_meta.get("why") or "",
        },
    }