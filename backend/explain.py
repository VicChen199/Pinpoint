"""Grounded LLM explanation. Track D implements this."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

_BACKEND_DIR = Path(__file__).resolve().parent

SYSTEM_PROMPT = """You explain a highlighted phrase from a document for a general reader.

Rules:
- Plain English for a general reader.
- Use only the provided context; do not invent facts, figures, or citations.
- Explain the term and how it applies in this document.
- 2–4 short sentences.
- No legal, medical, financial, or other professional advice.
- If context is insufficient, say what is missing.
"""


class MissingAPIKeyError(Exception):
    """Raised when GEMINI_API_KEY is missing or empty."""


def explain(phrase: str, context: str, document_type: str) -> str:
    load_dotenv(_BACKEND_DIR / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
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
        model="gemini-2.5-flash-lite",
        contents=user_content,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
        ),
    )
    return (response.text or "").strip()
