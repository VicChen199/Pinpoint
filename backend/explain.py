"""Grounded LLM explanation. Track D implements this."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

_BACKEND_DIR = Path(__file__).resolve().parent

SYSTEM_PROMPT = """You explain a highlighted phrase from a document for a general reader.

Rules:
- Lead with a short general-reader definition of the phrase.
- If the surrounding text clearly shows how the word is used here, add at most one sentence of local application.
- Do not invent figures, names, or citations.
- If local use is unclear, still define the word. Do not apologize or say that context is missing.
- 2–4 short sentences.
- No legal, medical, financial, or other professional advice.
"""


class MissingAPIKeyError(Exception):
    """Raised when GEMINI_API_KEY is missing or empty."""


def get_gemini_api_key() -> str:
    load_dotenv(_BACKEND_DIR / ".env")
    return os.getenv("GEMINI_API_KEY", "").strip()


def explain(phrase: str, context: str, document_type: str) -> str:
    api_key = get_gemini_api_key()
    if not api_key:
        raise MissingAPIKeyError("GEMINI_API_KEY is not configured")

    doc_type = (document_type or "").strip() or "unknown"
    user_content = (
        f"Document type: {doc_type}\n"
        f"Phrase: {phrase}\n"
        f"Context:\n{context}"
    )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=user_content,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
        ),
    )
    return (response.text or "").strip()
