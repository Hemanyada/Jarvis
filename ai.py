"""
AI Assistant — Exa finds articles, Gemini synthesizes a clean answer.
"""

import os
import requests
from typing import Optional

import google.generativeai as genai


def _get_gemini_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    genai.configure(api_key=api_key)
    # Use the same Gemini model as the other helper flows to avoid model-specific quota issues.
    return genai.GenerativeModel("gemini-2.5-flash")


def _search_exa_for_context(question: str) -> str:
    """Use Exa to find relevant articles and return combined text for Gemini."""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ValueError("EXA_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": question,
        "numResults": 5,
        "type": "auto",
        "contents": {
            "text": {"maxCharacters": 3000},
            "highlights": {"numSentences": 5, "highlightsPerUrl": 3},
        },
    }

    resp = requests.post(
        "https://api.exa.ai/search", json=payload, headers=headers
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])

    # Build context from all results
    parts = []
    for r in results:
        title = r.get("title", "")
        url = r.get("url", "")
        text = r.get("text", "")[:2000]
        highlights = " ".join(r.get("highlights", []))
        parts.append(f"Source: {title} ({url})\n{text}\n{highlights}")

    return "\n\n---\n\n".join(parts)


def ask_assistant(question: str, search_context: Optional[str] = None) -> str:
    """Answer a phone recommendation question using Exa search + Gemini.

    1. Exa searches the web for relevant articles/reviews.
    2. Gemini reads that context and produces a clean, structured answer.
    """
    # Gather web context via Exa
    exa_context = _search_exa_for_context(question)

    # Optionally include current search results from the main app
    extra = ""
    if search_context:
        extra = f"\n\nThe user also has these current search results in the app:\n{search_context}"

    prompt = f"""You are a helpful phone buying advisor for the Indian market.
The user asked: "{question}"

Below is context gathered from recent web articles and reviews:

{exa_context}
{extra}

Based on this context, give a clear, concise answer. Format your response as:
- A brief 1-2 sentence intro
- A list of recommended phones with:
  - Phone name
  - Approximate price in INR
  - Key specs (processor, camera, battery, display)
  - Why it's recommended (1 line)

Keep it concise and actionable. Use markdown formatting.
Only recommend phones that are actually mentioned in the context above.
If the context doesn't have enough info, say so honestly."""

    model = _get_gemini_model()
    response = model.generate_content(prompt)
    return response.text.strip()