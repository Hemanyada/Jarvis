import os
import json
import requests
from typing import List, Dict, Any, Optional, Tuple

import google.generativeai as genai

PLATFORMS = {
    "Amazon": ["amazon.in"],
    "Flipkart": ["flipkart.com"],
    "Croma": ["croma.com"],
}

BRAND_STORES = {
    "samsung": {"label": "Samsung Store", "domain": "samsung.com"},
    "apple": {"label": "Apple Store", "domain": "apple.com"},
    "iphone": {"label": "Apple Store", "domain": "apple.com"},
    "ipad": {"label": "Apple Store", "domain": "apple.com"},
    "xiaomi": {"label": "Xiaomi Store", "domain": "mi.com"},
    "redmi": {"label": "Xiaomi Store", "domain": "mi.com"},
    "poco": {"label": "Xiaomi Store", "domain": "mi.com"},
    "mi ": {"label": "Xiaomi Store", "domain": "mi.com"},
    "oneplus": {"label": "OnePlus Store", "domain": "oneplus.in"},
    "oppo": {"label": "Oppo Store", "domain": "oppo.com"},
    "vivo": {"label": "Vivo Store", "domain": "vivo.com"},
    "realme": {"label": "Realme Store", "domain": "realme.com"},
    "nothing": {"label": "Nothing Store", "domain": "nothing.tech"},
    "google pixel": {"label": "Google Store", "domain": "store.google.com"},
    "pixel": {"label": "Google Store", "domain": "store.google.com"},
    "motorola": {"label": "Motorola Store", "domain": "motorola.in"},
    "moto": {"label": "Motorola Store", "domain": "motorola.in"},
    "iqoo": {"label": "iQOO Store", "domain": "iqoo.com"},
}


def _get_gemini_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")


def search_exa(query: str, num_results: int = 5, domains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """POST to Exa search API and return the results list."""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ValueError("EXA_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "query": query,
        "numResults": num_results,
        "contents": {
            "text": {"maxCharacters": 5000},
            "highlights": {"numSentences": 5, "highlightsPerUrl": 3},
        },
    }
    if domains:
        payload["includeDomains"] = domains

    resp = requests.post("https://api.exa.ai/search", json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json().get("results", [])


def _detect_brand_store(phone_name: str) -> Optional[Dict[str, str]]:
    """Return the matching brand store entry for a phone name, or None."""
    name_lower = phone_name.lower()
    for keyword, store in BRAND_STORES.items():
        if keyword in name_lower:
            return store
    return None


def _build_search_targets(phone_name: str) -> List[Tuple[str, List[str]]]:
    """Build list of (platform_label, domains) to search."""
    searches: List[Tuple[str, List[str]]] = [(label, domains) for label, domains in PLATFORMS.items()]
    brand = _detect_brand_store(phone_name)
    if brand:
        already = {label for label, _ in searches}
        if brand["label"] not in already:
            searches.append((brand["label"], [brand["domain"]]))
    return searches


def _fetch_raw_results(phone_name: str) -> List[Dict[str, Any]]:
    """Search Exa across all platforms and collect raw results with platform labels."""
    searches = _build_search_targets(phone_name)
    raw_results = []

    for platform_label, domains in searches:
        try:
            results = search_exa(
                f'"{phone_name}" price buy India',
                num_results=3,
                domains=domains,
            )
        except Exception:
            continue

        for res in results:
            text = res.get("text", "")
            highlights = res.get("highlights", [])
            raw_results.append({
                "platform": platform_label,
                "url": res.get("url", ""),
                "title": res.get("title", ""),
                "snippet": (text[:2000] + " " + " ".join(highlights))[:3000],
            })

    return raw_results


def _strip_gemini_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _extract_prices_with_gemini(phone_name: str, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use Gemini to extract structured price data from raw Exa results.

    Returns a list of dicts: {platform, price, url} where price is an int (INR).
    """
    if not raw_results:
        return []

    # Build the context for Gemini
    context_parts = []
    for i, r in enumerate(raw_results):
        context_parts.append(
            f"--- Result {i+1} ---\n"
            f"Platform: {r['platform']}\n"
            f"URL: {r['url']}\n"
            f"Title: {r['title']}\n"
            f"Page text:\n{r['snippet']}\n"
        )
    context = "\n".join(context_parts)

    prompt = f"""You are a price extraction assistant. The user is searching for: "{phone_name}"

Below are search results from various Indian e-commerce platforms. For each result, determine:
1. Is this result ACTUALLY for the exact phone model "{phone_name}"? (not a different variant/model)
2. What is the current SELLING PRICE in Indian Rupees (INR)? Ignore EMI amounts, exchange values, cashback, bank discounts — only the actual listed selling price.

Return ONLY a JSON array. Each element should have:
- "platform": the platform name (string)
- "price": the selling price as an integer in INR (no commas, no currency symbol), or null if the price cannot be determined
- "url": the URL of the product page (string)
- "is_exact_model": true if this is the exact model the user searched for, false if it's a different model

Only include results where is_exact_model is true and price is not null.

If a result is for a different phone model (e.g., user searched "Edge 70 Fusion" but result is for "Edge 20 Fusion"), set is_exact_model to false.

Return ONLY the JSON array, no markdown fences, no explanation.

{context}"""

    model = _get_gemini_model()
    response = model.generate_content(prompt)
    text = _strip_gemini_json(response.text or "")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    offers = []
    for item in parsed:
        if not item.get("is_exact_model", False):
            continue
        price = item.get("price")
        if price is None:
            continue
        try:
            price = int(price)
        except (ValueError, TypeError):
            continue
        if price < 1000 or price > 500000:
            continue
        offers.append({
            "platform": item.get("platform", "Unknown"),
            "price": price,
            "url": item.get("url", ""),
        })

    return offers


def search_phone_prices(phone_name: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Search for phone prices: Exa fetches pages, Gemini extracts prices.

    Returns (offers, out_of_stock_platforms).
    """
    searches = _build_search_targets(phone_name)
    searched_labels = [label for label, _ in searches]

    raw_results = _fetch_raw_results(phone_name)

    if not raw_results:
        return [], searched_labels

    offers = _extract_prices_with_gemini(phone_name, raw_results)

    platforms_with_price = {o["platform"] for o in offers}
    out_of_stock = [p for p in searched_labels if p not in platforms_with_price]

    return offers, out_of_stock


def dedupe_best_per_platform(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only the lowest-priced offer per platform."""
    best: Dict[str, Dict[str, Any]] = {}
    for o in offers:
        p = o["platform"]
        if p not in best or o["price"] < best[p]["price"]:
            best[p] = o
    return list(best.values())


def get_best_deal(offers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the offer with the lowest price."""
    return min(offers, key=lambda o: o["price"]) if offers else None


def _empty_specs_row(display_name: str) -> Dict[str, str]:
    return {
        "Name": display_name.strip(),
        "Display": "Unknown",
        "Processor": "Unknown",
        "Camera": "Unknown",
        "Battery": "Unknown",
    }


def _fetch_specs_raw_results(phone_name: str) -> List[Dict[str, Any]]:
    """Search Exa across the same platforms as price search, for spec-focused snippets."""
    searches = _build_search_targets(phone_name)
    raw_results: List[Dict[str, Any]] = []

    for platform_label, domains in searches:
        try:
            results = search_exa(
                f'"{phone_name}" smartphone full specifications India display processor camera battery',
                num_results=3,
                domains=domains,
            )
        except Exception:
            continue

        for res in results:
            text = res.get("text", "")
            highlights = res.get("highlights", [])
            raw_results.append({
                "platform": platform_label,
                "url": res.get("url", ""),
                "title": res.get("title", ""),
                "snippet": (text[:2000] + " " + " ".join(highlights))[:3000],
            })

    return raw_results


def _extract_specs_with_gemini(phone_name: str, raw_results: List[Dict[str, Any]]) -> Dict[str, str]:
    """Use Gemini to extract structured specs from Exa snippets (same pattern as price extraction)."""
    if not raw_results:
        return _empty_specs_row(phone_name)

    context_parts = []
    for i, r in enumerate(raw_results):
        context_parts.append(
            f"--- Result {i+1} ---\n"
            f"Platform: {r['platform']}\n"
            f"URL: {r['url']}\n"
            f"Title: {r['title']}\n"
            f"Page text:\n{r['snippet']}\n"
        )
    context = "\n".join(context_parts)

    prompt = f"""You extract smartphone specifications from Indian e-commerce / brand page snippets.

The user wants specs for this exact model: "{phone_name}"

Snippets may include wrong models — only fill fields when the snippet clearly refers to "{phone_name}".

Return ONLY a JSON object with these keys:
- "name": product title as listed for the correct model (string)
- "display": screen size and panel type, short (e.g. 6.1 inch OLED)
- "processor": chipset / SoC name, short
- "camera": rear camera summary, short
- "battery": capacity (e.g. 4000 mAh), short
- "is_exact_model": true if snippets clearly describe "{phone_name}"; false if they describe another model or are too vague

If is_exact_model is false, set name to "{phone_name}" and set display, processor, camera, battery to "Unknown".

If is_exact_model is true but a field is missing in the text, use "Unknown" for that field.

Return ONLY the JSON object, no markdown fences, no explanation.

{context}"""

    model = _get_gemini_model()
    response = model.generate_content(prompt)
    text = _strip_gemini_json(response.text or "")

    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        return _empty_specs_row(phone_name)

    if isinstance(parsed, list) and parsed:
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        return _empty_specs_row(phone_name)

    def pick(*keys: str) -> str:
        for k in keys:
            v = parsed.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return "Unknown"

    if not parsed.get("is_exact_model", True):
        return _empty_specs_row(phone_name)

    return {
        "Name": pick("name", "Name") or phone_name.strip(),
        "Display": pick("display", "Display"),
        "Processor": pick("processor", "Processor"),
        "Camera": pick("camera", "Camera"),
        "Battery": pick("battery", "Battery"),
    }


def compare_phones_specs(names: List[str]) -> List[Dict[str, str]]:
    """For each phone: Exa fetch across the same stores as price search, then Gemini extracts specs."""
    out: List[Dict[str, str]] = []
    for name in names:
        raw = _fetch_specs_raw_results(name)
        if not raw:
            out.append(_empty_specs_row(name))
            continue
        out.append(_extract_specs_with_gemini(name, raw))
    return out


def tag_phone(specs_dict: Dict[str, str], name: str) -> str:
    """Tag phone based on specs and name heuristics."""
    name_lower = name.lower()
    camera = specs_dict.get("Camera", "").lower()
    processor = specs_dict.get("Processor", "").lower()

    if "pixel" in name_lower or "48mp" in camera or "50mp" in camera or "108mp" in camera or "200mp" in camera:
        return "Camera Focused"

    if any(kw in processor for kw in ("snapdragon 8", "a15", "a16", "a17")) or \
       any(kw in name_lower for kw in ("pro", "max", "ultra")):
        return "Performance Focused"

    return "All Rounder"