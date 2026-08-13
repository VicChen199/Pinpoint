"""Grounded LLM explanation. Track D implements this."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

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
    """Raised when OPENAI_API_KEY is missing or empty."""


def explain(phrase: str, context: str, document_type: str) -> str:
    load_dotenv(_BACKEND_DIR / ".env")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise MissingAPIKeyError("OPENAI_API_KEY is not configured")

    doc_type = (document_type or "").strip() or "unknown"
    user_content = (
        f"Document type: {doc_type}\n"
        f"Phrase: {phrase}\n"
        f"Context:\n{context}"
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    return (response.choices[0].message.content or "").strip()
