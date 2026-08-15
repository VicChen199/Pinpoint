"""Persisted word JSON and surrounding-text windows for explain."""

from __future__ import annotations

import json
from pathlib import Path

from db import UPLOAD_DIR
from extract import extract_words

WINDOW_WORDS = 100
OVERLAP_RATIO = 0.3


def words_json_path(doc_id: str) -> Path:
    return UPLOAD_DIR / f"{doc_id}.words.json"


def write_words_doc(doc_id: str, words_doc: dict) -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    words_json_path(doc_id).write_text(
        json.dumps(words_doc),
        encoding="utf-8",
    )


def load_words_doc(doc_id: str, pdf_path: str) -> dict:
    path = words_json_path(doc_id)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    words_doc = extract_words(pdf_path)
    write_words_doc(doc_id, words_doc)
    return words_doc


def surrounding_context(
    words_doc: dict,
    page_no: int,
    bbox: dict,
    phrase: str,
) -> str:
    page = _page_by_number(words_doc, page_no)
    words = _reading_order(page.get("words") or [])
    if not words:
        return (phrase or "").strip()

    span = _span_by_bbox(words, bbox)
    if span is None:
        span = _span_by_phrase(words, phrase)
    if span is None:
        return _join_words(words)

    start, end = _window_bounds(len(words), span[0], span[1])
    return _join_words(words[start:end])


def _page_by_number(words_doc: dict, page_no: int) -> dict:
    for page in words_doc.get("pages") or []:
        if int(page.get("page") or 0) == int(page_no):
            return page
    return {}


def _reading_order(words: list[dict]) -> list[dict]:
    return sorted(
        words,
        key=lambda w: (float(w["bbox"]["y"]), float(w["bbox"]["x"])),
    )


def _span_by_bbox(words: list[dict], pin_bbox: dict) -> tuple[int, int] | None:
    hits = [
        i
        for i, word in enumerate(words)
        if _overlap_ratio(word["bbox"], pin_bbox) >= OVERLAP_RATIO
    ]
    if not hits:
        return None
    return hits[0], hits[-1] + 1


def _span_by_phrase(words: list[dict], phrase: str) -> tuple[int, int] | None:
    keys = _phrase_keys(phrase)
    if not keys:
        return None
    page_keys = [_word_key(w.get("text") or "") for w in words]
    n = len(keys)
    for i in range(len(page_keys) - n + 1):
        if page_keys[i : i + n] == keys:
            return i, i + n
    return None


def _phrase_keys(phrase: str) -> list[str]:
    return [key for token in (phrase or "").split() if (key := _word_key(token))]


def _word_key(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _window_bounds(n_words: int, span_start: int, span_end: int) -> tuple[int, int]:
    if n_words <= WINDOW_WORDS:
        return 0, n_words
    half = WINDOW_WORDS // 2
    start = max(0, span_start - half)
    end = min(n_words, max(span_end, start + WINDOW_WORDS))
    if end - start < WINDOW_WORDS:
        start = max(0, end - WINDOW_WORDS)
    return start, end


def _overlap_ratio(a: dict, b: dict) -> float:
    ax2, ay2 = a["x"] + a["width"], a["y"] + a["height"]
    bx2, by2 = b["x"] + b["width"], b["y"] + b["height"]
    ix = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    area = max(a["width"] * a["height"], 1.0)
    return inter / area


def _join_words(words: list[dict]) -> str:
    return " ".join((w.get("text") or "").strip() for w in words if (w.get("text") or "").strip())
