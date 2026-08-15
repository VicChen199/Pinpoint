"""Term detection → pin dicts.

Each dict is a Pin without document_id / explanation (prototype-contract.md).
Coordinates stay in unscaled PDF user space (scale = 1).
Gemini picks phrases from extracted page text; heuristics are the fallback.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from collections import Counter
from pathlib import Path

from google import genai

from explain import get_gemini_api_key

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

log = logging.getLogger(__name__)

DETECT_PROMPT = """You pick phrases a general reader would want explained from one page of a document.

Rules:
- Return a JSON array of strings only.
- Each string must be copied exactly from the page text (same words, same order).
- At most the requested number of phrases.
- Prefer jargon, abbreviations, and multi-word technical or legal terms.
- Skip personal names, titles, headers, page numbers, and common words.
"""


def detect_pins(words_doc: dict, *, max_per_page: int = 12) -> list[dict]:
    pages = words_doc.get("pages") or []
    frequencies = _term_frequencies(pages)
    pins: list[dict] = []
    for page in pages:
        page_pins = _llm_pins_for_page(page, max_per_page=max_per_page)
        if not page_pins:
            page_pins = _heuristic_pins_for_page(
                page, frequencies, max_per_page=max_per_page
            )
        pins.extend(page_pins)
    return pins


def _llm_pins_for_page(page: dict, *, max_per_page: int) -> list[dict]:
    words = list(page.get("words") or [])
    page_text = " ".join(
        (w.get("text") or "").strip() for w in words if (w.get("text") or "").strip()
    )
    if not page_text:
        return []
    try:
        phrases = _pick_phrases(page_text, max_per_page)
    except Exception:
        log.exception("LLM phrase pick failed for page %s", page.get("page"))
        return []
    if not phrases:
        return []

    page_no = int(page.get("page") or 0)
    chosen: list[dict] = []
    seen: set[str] = set()
    for phrase in phrases:
        key = " ".join(_normalize(token) for token in phrase.split() if _normalize(token))
        if not key or key in seen:
            continue
        span = _match_phrase_span(words, phrase)
        if span is None:
            continue
        seen.add(key)
        bbox = _union_bbox(span)
        cand = {
            "page": page_no,
            "text": " ".join(w["text"].strip() for w in span),
            "bbox": bbox,
            "x": bbox["x"],
            "y": bbox["y"],
        }
        if any(_overlaps(cand["bbox"], pin["bbox"]) for pin in chosen):
            continue
        chosen.append(_to_pin(cand))
        if len(chosen) >= max_per_page:
            break
    return chosen


def _pick_phrases(page_text: str, max_per_page: int) -> list[str]:
    api_key = get_gemini_api_key()
    if not api_key:
        return []
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"Pick at most {max_per_page} phrases.\n\nPage text:\n{page_text}",
        config=genai.types.GenerateContentConfig(
            system_instruction=DETECT_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    return _parse_phrase_list(response.text or "")


def _parse_phrase_list(raw: str) -> list[str]:
    text = raw.strip()
    if not text:
        return []
    data = _load_json_array(text)
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
            continue
        if isinstance(item, dict):
            phrase = item.get("phrase") or item.get("text")
            if isinstance(phrase, str) and phrase.strip():
                out.append(phrase.strip())
    return out


def _load_json_array(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


def _match_phrase_span(words: list[dict], phrase: str) -> list[dict] | None:
    keys = [_normalize(token) for token in phrase.split() if _normalize(token)]
    if not keys:
        return None
    page_keys = [_normalize(w.get("text") or "") for w in words]
    n = len(keys)
    for i in range(len(page_keys) - n + 1):
        if page_keys[i : i + n] == keys:
            return words[i : i + n]
    return None


def _heuristic_pins_for_page(page: dict, frequencies: Counter, *, max_per_page: int) -> list[dict]:
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
