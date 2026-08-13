"""Heuristic term detection → pin dicts.

Each dict is a Pin without document_id / explanation (prototype-contract.md).
Coordinates stay in unscaled PDF user space (scale = 1).
No domain dictionary: score abbreviations, uncommon words, and multi-word terms.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from collections import Counter
from pathlib import Path

# Function words only — not a domain jargon list.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "onto",
        "to",
        "with",
        "without",
        "within",
        "over",
        "under",
        "above",
        "below",
        "between",
        "through",
        "during",
        "before",
        "after",
        "is",
        "am",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "doing",
        "have",
        "has",
        "had",
        "having",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "itself",
        "he",
        "she",
        "they",
        "them",
        "their",
        "we",
        "us",
        "our",
        "you",
        "your",
        "i",
        "me",
        "my",
        "not",
        "no",
        "nor",
        "so",
        "than",
        "too",
        "very",
        "can",
        "could",
        "should",
        "would",
        "may",
        "might",
        "must",
        "shall",
        "will",
        "just",
        "also",
        "then",
        "there",
        "here",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "what",
        "how",
        "why",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "than",
        "too",
        "s",
        "t",
        "don",
        "now",
        "page",
        "see",
        "per",
    }
)

LATINATE_SUFFIXES = (
    "tion",
    "sion",
    "ment",
    "ance",
    "ence",
    "ity",
    "ize",
    "ise",
    "ive",
    "ure",
    "ory",
    "ary",
    "ous",
    "ium",
    "ual",
)

# OCR tokens below this are too noisy to underline.
PIN_MIN_CONFIDENCE = 60
MAX_PHRASE_WORDS = 3


def detect_pins(words_doc: dict, *, max_per_page: int = 12) -> list[dict]:
    pages = words_doc.get("pages") or []
    frequencies = _term_frequencies(pages)
    pins: list[dict] = []
    for page in pages:
        pins.extend(_pins_for_page(page, frequencies, max_per_page=max_per_page))
    return pins


def _pins_for_page(page: dict, frequencies: Counter, *, max_per_page: int) -> list[dict]:
    page_no = int(page.get("page") or 0)
    indexed = []
    for word in page.get("words") or []:
        if not _usable_word(word):
            continue
        indexed.append(word)

    candidates: list[dict] = []
    used: set[int] = set()
    for i, word in enumerate(indexed):
        if i in used:
            continue
        phrase = _phrase_from(indexed, i)
        used.update(range(i, i + len(phrase)))
        candidates.append(_candidate(page_no, phrase, frequencies))

    candidates.sort(key=lambda c: c["_score"], reverse=True)
    chosen: list[dict] = []
    for cand in candidates:
        if len(chosen) >= max_per_page:
            break
        if cand["_score"] <= 0:
            continue
        if any(_overlaps(cand["bbox"], pin["bbox"]) for pin in chosen):
            continue
        chosen.append(_to_pin(cand))
    return chosen


def _usable_word(word: dict) -> bool:
    text = (word.get("text") or "").strip()
    if _is_skippable(text):
        return False
    try:
        conf = int(word.get("confidence", 100))
    except (TypeError, ValueError):
        conf = 100
    return conf >= PIN_MIN_CONFIDENCE


def _is_skippable(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) <= 1:
        return True
    if re.fullmatch(r"[\d,.$%€£¥+\-:/()]+", stripped):
        return True
    key = _normalize(stripped)
    if not key:
        return True
    if key in STOPWORDS:
        return True
    return False


def _normalize(text: str) -> str:
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE).lower()


def _term_frequencies(pages: list) -> Counter:
    counts: Counter = Counter()
    for page in pages:
        for word in page.get("words") or []:
            text = (word.get("text") or "").strip()
            if _is_skippable(text):
                continue
            counts[_normalize(text)] += 1
    return counts


def _score(text: str, frequencies: Counter) -> float:
    score = 0.0
    if re.fullmatch(r"[A-Z]{2,6}", text) or re.fullmatch(r"(?:[A-Z]\.){2,}", text):
        score += 5.0
    if re.search(r"[A-Za-z]", text) and re.search(r"\d", text):
        score += 4.0
    if "-" in text and re.search(r"[A-Za-z]", text):
        score += 3.0
    if re.search(r"[a-z][A-Z]", text):
        score += 3.0
    letters = re.sub(r"[^A-Za-z]", "", text)
    if len(letters) >= 12:
        score += 3.0
    elif len(letters) >= 8:
        score += 2.0
    elif len(letters) >= 6:
        score += 1.0
    lower = letters.lower()
    if any(lower.endswith(suf) for suf in LATINATE_SUFFIXES):
        score += 2.0
    freq = frequencies.get(_normalize(text), 1)
    if freq == 1:
        score += 2.0
    elif freq == 2:
        score += 1.0
    elif freq >= 8:
        score -= 1.5
    if text[:1].isupper() and text[1:].islower() and len(letters) >= 5:
        score += 0.5
    return score


def _phrase_from(words: list[dict], start: int) -> list[dict]:
    first = words[start]
    if not _phrase_token(first["text"]):
        return [first]
    phrase = [first]
    for nxt in words[start + 1 : start + MAX_PHRASE_WORDS]:
        if not _adjacent(phrase[-1], nxt):
            break
        if not _phrase_token(nxt["text"]):
            break
        phrase.append(nxt)
    return phrase


def _phrase_token(text: str) -> bool:
    stripped = text.strip()
    if _is_skippable(stripped):
        return False
    if re.fullmatch(r"[A-Z]{2,6}", stripped):
        return True
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    return bool(letters) and stripped[:1].isupper() and len(letters) >= 4


def _adjacent(left: dict, right: dict) -> bool:
    a = left["bbox"]
    b = right["bbox"]
    same_line = abs((a["y"] + a["height"] / 2) - (b["y"] + b["height"] / 2)) <= max(
        a["height"], b["height"], 8.0
    ) * 0.6
    gap = b["x"] - (a["x"] + a["width"])
    max_gap = max(a["height"], b["height"], 10.0) * 1.8
    return same_line and 0 <= gap <= max_gap


def _union_bbox(words: list[dict]) -> dict:
    xs = [w["bbox"]["x"] for w in words]
    ys = [w["bbox"]["y"] for w in words]
    rights = [w["bbox"]["x"] + w["bbox"]["width"] for w in words]
    bottoms = [w["bbox"]["y"] + w["bbox"]["height"] for w in words]
    x = min(xs)
    y = min(ys)
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "width": round(max(rights) - x, 2),
        "height": round(max(bottoms) - y, 2),
    }


def _candidate(page: int, words: list[dict], frequencies: Counter) -> dict:
    text = " ".join(w["text"].strip() for w in words)
    scores = [_score(w["text"].strip(), frequencies) for w in words]
    score = max(scores) + (1.5 if len(words) > 1 else 0.0)
    bbox = _union_bbox(words)
    return {
        "_score": score,
        "page": page,
        "text": text,
        "bbox": bbox,
        "x": bbox["x"],
        "y": bbox["y"],
    }


def _overlaps(a: dict, b: dict) -> bool:
    ax2, ay2 = a["x"] + a["width"], a["y"] + a["height"]
    bx2, by2 = b["x"] + b["width"], b["y"] + b["height"]
    ix = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    if inter <= 0:
        return False
    area_a = max(a["width"] * a["height"], 1.0)
    area_b = max(b["width"] * b["height"], 1.0)
    return inter / min(area_a, area_b) >= 0.3


def _to_pin(candidate: dict) -> dict:
    bbox = candidate["bbox"]
    return {
        "id": f"pin_{uuid.uuid4().hex[:12]}",
        "page": candidate["page"],
        "x": bbox["x"],
        "y": bbox["y"],
        "text": candidate["text"],
        "bbox": bbox,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python detect.py <pdf-or-words.json>", file=sys.stderr)
        sys.exit(2)
    src = Path(sys.argv[1])
    if src.suffix.lower() == ".json":
        words_doc = json.loads(src.read_text(encoding="utf-8"))
    else:
        from extract import extract_words

        words_doc = extract_words(str(src))
    pins = detect_pins(words_doc, max_per_page=12)
    print(json.dumps(pins, indent=2))
