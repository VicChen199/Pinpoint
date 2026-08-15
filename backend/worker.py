"""Background document processing.

Skip if status is already ready. Otherwise extract → persist words JSON →
detect → INSERT pins → status ready | failed. Does not call explain.py.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from context import write_words_doc
from db import ROOT, create_tables, get_connection
from detect import detect_pins
from extract import extract_words

log = logging.getLogger(__name__)

MAX_PER_PAGE = 12


def process_document(doc_id: str) -> None:
    create_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, storage_path, status FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        if row is None:
            log.error("process_document: unknown document %s", doc_id)
            return
        if row["status"] == "ready":
            return

        started_status = row["status"]
        pdf_path = _resolve_pdf_path(row["storage_path"])
        try:
            words_doc = extract_words(str(pdf_path))
            write_words_doc(doc_id, words_doc)
            pins = detect_pins(words_doc, max_per_page=MAX_PER_PAGE)
            _replace_pins(conn, doc_id, pins)
            conn.execute(
                "UPDATE documents SET status = 'ready' WHERE id = ?",
                (doc_id,),
            )
            conn.commit()
        except Exception:
            conn.execute(
                "UPDATE documents SET status = 'failed' WHERE id = ? AND status = ?",
                (doc_id, started_status),
            )
            conn.commit()
            log.exception("process_document failed for %s", doc_id)
    finally:
        conn.close()


def _resolve_pdf_path(storage_path: str) -> Path:
    path = Path(storage_path)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _replace_pins(conn, doc_id: str, pins: list[dict]) -> None:
    conn.execute("DELETE FROM pins WHERE document_id = ?", (doc_id,))
    for pin in pins:
        bbox = pin["bbox"]
        conn.execute(
            """
            INSERT INTO pins (
              id, document_id, page, text, bbox_json, x, y, is_visible, explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL)
            """,
            (
                pin["id"],
                doc_id,
                int(pin["page"]),
                pin["text"],
                json.dumps(bbox),
                float(pin["x"]),
                float(pin["y"]),
            ),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("usage: python worker.py <doc_id>", file=sys.stderr)
        sys.exit(2)
    process_document(sys.argv[1])
