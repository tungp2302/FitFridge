# flaskr/api_db/external/openfoodfacts_client.py
"""OpenFoodFacts-Client fuer Barcode-Lookups mit Mengen-Parsing und Fallbacks."""

from __future__ import annotations

import json
import re
import ssl
import time
from typing import Optional, Tuple, Dict
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from . import product_repo
try:
    import certifi
except ModuleNotFoundError:  # pragma: no cover - depends on local environment
    certifi = None

OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
OFF_STAGING_API_URL = "https://world.openfoodfacts.net/api/v2/product/{barcode}.json"

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

def search_product_add_db(barcode: str, user_agent: str = DEFAULT_USER_AGENT, use_staging: bool = False) -> Optional[Dict]:
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

    product_repo.create_product(result["name"], result["brand"], result["barcode"], result["kcal_per_100g"], result["protein_per_100g"], result["fat_per_100g"], result["carbs_per_100g"])


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

    base_url = OFF_STAGING_API_URL.rsplit("/api/v2/product/{barcode}.json", 1)[0] if use_staging else OFF_API_URL.rsplit("/api/v2/product/{barcode}.json", 1)[0]
    search_url = (
        f"{base_url}/cgi/search.pl?"
        f"search_terms={quote(query)}&search_simple=1&action=process&json=0"
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
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            with urlopen(request, timeout=10, context=https_context) as response:
                body = response.read().decode("utf-8")
            break
        except HTTPError as error:
            if error.code == 404:
                return None
            # Retry on 503 Service Unavailable
            if error.code == 503 and attempt < max_attempts - 1:
                time.sleep(1 << attempt)
                continue
            raise RuntimeError(f"Open Food Facts search failed: {error}") from error
        except URLError as error:
            # transient network error -> retry a few times
            if attempt < max_attempts - 1:
                time.sleep(1 << attempt)
                continue
            raise RuntimeError(f"Open Food Facts search failed: {error}") from error

    if not body:
        return None

    match = re.search(r"/product/(\d{4,})/", body)
    if not match:
        return None

    return search_product(match.group(1), user_agent=user_agent, use_staging=use_staging)