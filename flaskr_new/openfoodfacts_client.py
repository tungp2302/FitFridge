nb  """OpenFoodFacts-Client fuer Barcode-Lookups mit Mengen-Parsing und Fallbacks."""

from __future__ import annotations

import json
import logging
import re
import ssl
import unicodedata
from typing import Optional, Tuple, Dict
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

try:
    import certifi
except ModuleNotFoundError:  # pragma: no cover - depends on local environment
    certifi = None

OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
# Text-Suche laeuft ueber die Search-a-licious-API (liefert nur Barcodes).
OFF_SEARCH_API_URL = "https://search.openfoodfacts.org/search"

DEFAULT_USER_AGENT = "FitFridge/1.0 (university project; contact: you@example.com)"


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


def _strip_ai_ingredient_prefix(query: str) -> str:
    normalized = str(query or "").strip()
    lowered = normalized.lower()
    if lowered.startswith("ingredient:") or lowered.startswith("ai:"):
        return normalized.split(":", 1)[1].strip()
    return normalized


def _ingredient_display_name(query: str) -> str:
    normalized = _normalize_text(query)
    if not normalized:
        return ""
    return " ".join(part.capitalize() for part in normalized.split())


def _parse_llm_json_object(response: str) -> dict:
    text = str(response or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}


def _llm_ai_macro_estimate(query: str, canonical_query: str, model: Optional[str] = None) -> dict:
    """Ask Ollama for a best-effort nutrition estimate for an arbitrary food.

    ``model`` erlaubt es Aufrufern (z.B. Worker-Threads ohne App-Kontext),
    das bereits aufgeloeste Nutzermodell durchzureichen.
    """
    from .asaai.ollama_client import generate_from_ollama

    prompt = (
        "Du bist ein zertifizierter Ernährungsberater und Nährwert-Schätzer für FitFridge. "
        "Schätze die Nährwerte pro 100g für das genannte Lebensmittel so präzise wie möglich. "
        "Wenn du unsicher bist, gib eine plausible Durchschnittsschätzung statt 0. "
        "Du kannst sowohl auf deutsche als auch auf englische Begriffe zurückgreifen. "
        "Antworte nur als JSON ohne Markdown oder Zusatztext.\n\n"
        "JSON-Schema:\n"
        "{\n"
        '  "display_name": "string",\n'
        '  "why": "string",\n'
        '  "estimated_macros": {"kcal": number, "protein": number, "fat": number, "carbs": number},\n'
        '  "confidence": number\n'
        "}\n\n"
        f"Suchbegriff: {query}\n"
        f"Canonical ingredient: {canonical_query}"
    )

    try:
        response = generate_from_ollama(prompt=prompt, model=model, timeout=10, num_predict=220, format_json=True)
    except Exception:
        logger.warning("Ollama-Makro-Schaetzung fehlgeschlagen fuer %r", query, exc_info=True)
        return {}

    return _parse_llm_json_object(response)


def _has_complete_macro_estimate(meta: dict) -> bool:
    macros = (meta or {}).get("estimated_macros") or {}
    if not isinstance(macros, dict):
        return False
    for key in ("kcal", "protein", "fat", "carbs"):
        try:
            float(macros[key])
        except (KeyError, TypeError, ValueError):
            return False
    return True


def _score_off_product(query: str, product: dict) -> float:
    """Rank OpenFoodFacts products by textual closeness to the query."""
    normalized_query = _normalize_text(query)
    name = _normalize_text(product.get("name", ""))

    score = 0.0

    if normalized_query and normalized_query == name:
        score += 60
    elif normalized_query and normalized_query in name:
        score += 35
    elif name and any(token in name for token in normalized_query.split()):
        score += 15

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


def search_product(barcode: str, user_agent: str = DEFAULT_USER_AGENT) -> Optional[Dict]:
    """Holt ein Produkt von Open Food Facts via Barcode.

    Liefert ein dict mit name, brand, barcode, den /100g-Naehrwerten und
    optional total_amount/unit - oder None, wenn nichts gefunden wurde.
    """
    if not barcode:
        raise ValueError("barcode is required")

    url = OFF_API_URL.format(barcode=barcode)
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
    }

    return result


def lookup_product(query: str, user_agent: str = DEFAULT_USER_AGENT) -> Optional[Dict]:
    """
    Nimmt entweder einen Barcode oder einen Produktnamen.

    - Zahlen werden direkt als Barcode behandelt.
    - Alles andere wird ueber die Open Food Facts Suche aufgeloest.
    """
    if not query:
        raise ValueError("query is required")

    stripped_query = _strip_ai_ingredient_prefix(query)
    if stripped_query != query:
        return ai_estimate(stripped_query)

    query = stripped_query

    if query.isdigit():
        return search_product(query, user_agent=user_agent)

    products = search_products(query, user_agent=user_agent, limit=10)
    if not products:
        return ai_estimate(query)

    ranked = _rank_off_products(query, products)
    if not ranked:
        return ai_estimate(query)

    return ranked[0]


def search_products(query: str, user_agent: str = DEFAULT_USER_AGENT, limit: int = 10) -> Optional[list]:
    """
    Sucht per Text bei Open Food Facts nach passenden Produkten.

    Nutzt die Search-a-licious-API (search.openfoodfacts.org), die nur
    Barcodes (`code`) liefert. Fuer jeden Treffer holen wir die vollen
    Naehrwerte ueber die Barcode-API (`search_product`).

    Returns: Liste von Produkt-Dicts (gleiche Form wie `search_product`)
    oder eine leere Liste, wenn nichts gefunden wurde.
    """
    if not query:
        raise ValueError("query is required")

    search_url = (
        f"{OFF_SEARCH_API_URL}?q={quote(query)}"
        f"&page_size={max(1, min(limit, 20))}"
        "&fields=code,product_name,brands"
    )
    request = Request(
        search_url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=10, context=_make_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        logger.warning("OFF-Textsuche fehlgeschlagen fuer %r", query, exc_info=True)
        return []

    hits = payload.get("hits") or []
    results = []
    seen = set()
    for hit in hits:
        code = hit.get("code")
        if not code or code in seen:
            continue
        seen.add(code)
        try:
            full = search_product(code, user_agent=user_agent)
        except Exception:
            logger.warning("OFF-Barcode-Detail fehlgeschlagen fuer %s", code, exc_info=True)
            full = None
        if full and full.get("name"):
            results.append(full)
        if len(results) >= limit:
            break

    return _rank_off_products(query, results)


def ai_estimate(query: str, model: Optional[str] = None) -> Optional[dict]:
    """Return an AI-generated estimate for any food query.

    This path is independent from OpenFoodFacts search results and is
    intended to stay visible as a separate selectable option in the UI.
    ``model`` kann ein vorab aufgeloestes Ollama-Modell sein (siehe
    ``_llm_ai_macro_estimate``).
    """
    if not query:
        return None

    query = _strip_ai_ingredient_prefix(query)

    canonical = _normalize_text(query)

    try:
        llm_meta = _llm_ai_macro_estimate(query, canonical, model=model) or {}
    except Exception:
        logger.warning("ai_estimate fehlgeschlagen fuer %r", query, exc_info=True)
        llm_meta = {}

    if not _has_complete_macro_estimate(llm_meta):
        return None

    display_name = _ingredient_display_name(llm_meta.get("display_name")) or _ingredient_display_name(query) or query
    estimated_macros = llm_meta.get("estimated_macros") or {}

    def _macro_value(key: str, default: float = 0.0) -> float:
        value = estimated_macros.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    return {
        "name": display_name,
        "brand": "FitFridge AI",
        "barcode": f"ingredient:{_normalize_text(query)}",
        "kcal_per_100g": _macro_value("kcal"),
        "protein_per_100g": _macro_value("protein"),
        "fat_per_100g": _macro_value("fat"),
        "carbs_per_100g": _macro_value("carbs"),
        "sugar_per_100g": 0.0,
        "total_amount": 100.0,
        "unit": "g",
        "raw_quantity": "100 g",
        "raw_product": {
            "ai_generated": True,
            "query": _normalize_text(query),
            "canonical_query": canonical,
            "ai_note": llm_meta.get("why") or "",
            "ai_confidence": llm_meta.get("confidence"),
        },
    }
