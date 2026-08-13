"""Digital PDF + OCR word extraction.

Returns the frozen word JSON from docs/prototype-contract.md.
Bboxes are unscaled PDF user space (origin top-left, scale = 1), matching
PDF.js viewport coordinates at scale 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf as fitz

# Skip Tesseract tokens below this confidence (mini-project / prototype guidance).
OCR_MIN_CONFIDENCE = 60
OCR_ZOOM = 2.0


def extract_words(pdf_path: str) -> dict:
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(path)
    try:
        pages = [_extract_page(page) for page in doc]
    finally:
        doc.close()

    return {"source": path.name, "pages": pages}


def _extract_page(page: fitz.Page) -> dict:
    rect = page.rect
    payload = {
        "page": page.number + 1,
        "width": _round(rect.width),
        "height": _round(rect.height),
        "words": [],
    }
    if _page_has_text_layer(page):
        payload["words"] = _digital_words(page)
    else:
        payload["words"] = _ocr_words(page)
    return payload


def _page_has_text_layer(page: fitz.Page) -> bool:
    text = page.get_text("text").strip()
    words = page.get_text("words")
    return bool(text) and bool(words)


def _digital_words(page: fitz.Page) -> list[dict]:
    rect = page.rect
    out: list[dict] = []
    for word in page.get_text("words"):
        x0, y0, x1, y1, text, *_ = word
        text = (text or "").strip()
        if not text:
            continue
        out.append(
            {
                "text": text,
                "bbox": _bbox(x0 - rect.x0, y0 - rect.y0, x1 - x0, y1 - y0),
                "confidence": 100,
            }
        )
    return out


def _ocr_words(page: fitz.Page) -> list[dict]:
    import pytesseract
    from PIL import Image

    mat = fitz.Matrix(OCR_ZOOM, OCR_ZOOM)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    out: list[dict] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = int(float(data["conf"][i]))
        except (TypeError, ValueError):
            continue
        if conf < OCR_MIN_CONFIDENCE:
            continue
        left = float(data["left"][i])
        top = float(data["top"][i])
        width = float(data["width"][i])
        height = float(data["height"][i])
        out.append(
            {
                "text": text,
                "bbox": _bbox(
                    left / OCR_ZOOM,
                    top / OCR_ZOOM,
                    width / OCR_ZOOM,
                    height / OCR_ZOOM,
                ),
                "confidence": conf,
            }
        )
    return out


def _bbox(x: float, y: float, width: float, height: float) -> dict:
    return {
        "x": _round(x),
        "y": _round(y),
        "width": _round(width),
        "height": _round(height),
    }


def _round(value: float) -> float:
    return round(float(value), 2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python extract.py <pdf> [--out words.json]", file=sys.stderr)
        sys.exit(2)
    pdf = sys.argv[1]
    result = extract_words(pdf)
    out_path = None
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]
    text = json.dumps(result, indent=2)
    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")
    else:
        print(text)
