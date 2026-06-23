"""Open-Food-Facts-Client"""

import json
import logging
import re
import ssl
import unicodedata
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

logger = logging.getLogger(__name__)

OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"

OFF_SEARCH_API_URL = "https://search.openfoodfacts.org/search"


def _first_string(*values):
    return next((str(v) for v in values if v), "")


def _float_value(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _score_off_product(query, product):
    """Ranking OpenFoodFacts products by text closeness."""
    q = _normalize_text(query)
    name = _normalize_text(product.get("name", ""))
    if not q or not name:
        return 0.0
    if q == name:
        return 60.0
    if q in name:
        return 35.0
    return 15.0 if any(t in name for t in q.split()) else 0.0


def _rank_off_products(query, products):
    return sorted(
        products,
        key=lambda product: (
            _score_off_product(query, product),
            product.get("protein_per_100g", 0.0),
            -product.get("kcal_per_100g", 0.0),
        ),
        reverse=True,
    )


def _parse_total_quantity(product_data):
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
    m = re.search(r"(?:(\d+(?:\.\d+)?)\s*[x×]\s*)?(\d+(?:\.\d+)?)(?:\s*)(mg|kg|kilogramm|gramm|grams|g|ml|cl|liter|litre|l|stk|stueck|piece|pieces)?", raw)
    if not m:
        return None, None

    mult = float(m.group(1)) if m.group(1) else 1.0
    amount = float(m.group(2))
    unit = (m.group(3) or "").strip()

    # Normalisierung
    unit_map = {
        "gramm": "g", "grams": "g", "g": "g",
        "kg": "kg", "kilogramm": "kg",
        "ml": "ml", "cl": "cl",
        "l": "l", "liter": "l", "litre": "l",
        "mg": "mg",
        "stk": "stk", "stueck": "stk", "piece": "stk", "pieces": "stk",
    }
    unit_norm = unit_map.get(unit, unit) if unit else None

    return mult * amount, unit_norm


def _kJ_to_kcal(kj):
    return kj / 4.184 if kj else 0.0


def _make_ssl_context():
    """Return an SSL context using certifi's CA bundle."""
    return ssl.create_default_context(cafile=certifi.where())


def _kcal_from_nutriments(nutriments):
    """Normalize energy value from the nutriments dict to kcal per 100g."""
    if nutriments.get("energy-kcal_100g") is not None:
        return _float_value(nutriments.get("energy-kcal_100g"))
    if nutriments.get("energy-kcal_value") is not None:
        return _float_value(nutriments.get("energy-kcal_value"))
    if nutriments.get("energy_100g") is not None:
        return _kJ_to_kcal(_float_value(nutriments.get("energy_100g")))
    return 0.0


def search_product(barcode):
    """Holt ein Produkt per Barcode von Open Food Facts.

    Gibt ein Dict mit Name, Marke, Nährwerten (pro 100g) und - falls
    erkennbar - der Packungsmenge zurück, oder None wenn nicht gefunden.
    """
    if not barcode:
        raise ValueError("barcode is required")

    req = Request(
        OFF_API_URL.format(barcode=barcode),
        headers={"User-Agent": "FitFridge/1.0", "Accept": "application/json"},
    )

    try:
        with urlopen(req, timeout=10, context=_make_ssl_context()) as resp:
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
    total_amount, unit = _parse_total_quantity(product)

    return {
        "name": _first_string(product.get("product_name"), product.get("generic_name")),
        "brand": _first_string(product.get("brands"), product.get("brand_owner")),
        "barcode": _first_string(product.get("code"), barcode),
        "kcal_per_100g": _kcal_from_nutriments(nutriments),
        "protein_per_100g": _float_value(nutriments.get("proteins_100g")),
        "fat_per_100g": _float_value(nutriments.get("fat_100g")),
        "carbs_per_100g": _float_value(nutriments.get("carbohydrates_100g")),
        "total_amount": total_amount,
        "unit": unit,
    }


def lookup_product(query):
    """Loest einen Barcode (nur Ziffern) oder einen Produktnamen auf.

    Gibt den besten Treffer zurück oder None, wenn nichts gefunden wurde.
    """
    if not query:
        raise ValueError("query is required")

    if query.isdigit():
        return search_product(query)

    ranked = _rank_off_products(query, search_products(query) or [])
    return ranked[0] if ranked else None


def search_products(query, limit=10):
    """Textsuche bei Open Food Facts.

    Die Such-API liefert nur Barcodes; für jeden Treffer laden wir die
    vollen Nährwerte über ``search_product`` nach. Sortiert nach
    Namensähnlichkeit. Leere Liste, wenn nichts gefunden wurde.
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
        headers={"User-Agent": "FitFridge/1.0", "Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=10, context=_make_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        logger.warning("OFF-Textsuche fehlgeschlagen für %r", query, exc_info=True)
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
            full = search_product(code)
        except Exception:
            logger.warning("OFF-Barcode-Detail fehlgeschlagen für %s", code, exc_info=True)
            full = None
        if full and full.get("name"):
            results.append(full)
        if len(results) >= limit:
            break

    return _rank_off_products(query, results)
