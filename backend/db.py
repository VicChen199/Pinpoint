"""SQLite helpers. Schema is frozen in docs/prototype-contract.md. Track B owns CRUD."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  filename TEXT,
  status TEXT,
  storage_path TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS pins (
  id TEXT PRIMARY KEY,
  document_id TEXT,
  page INTEGER,
  text TEXT,
  bbox_json TEXT,
  x REAL,
  y REAL,
  is_visible INTEGER DEFAULT 1,
  explanation TEXT,
  FOREIGN KEY (document_id) REFERENCES documents(id)
);
"""


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def create_tables() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_document(
    doc_id: str,
    filename: str,
    status: str,
    storage_path: str,
    created_at: str,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO documents (id, filename, status, storage_path, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (doc_id, filename, status, storage_path, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_document(doc_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, filename, status, storage_path, created_at FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def list_documents() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, filename, status, created_at
            FROM documents
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_visible_pins(doc_id: str) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, page, text, bbox_json, x, y, explanation
            FROM pins
            WHERE document_id = ? AND is_visible = 1
            ORDER BY page, y, x
            """,
            (doc_id,),
        ).fetchall()
        return [_pin_from_row(row) for row in rows]
    finally:
        conn.close()


def get_pin(doc_id: str, pin_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, page, text, bbox_json, x, y, explanation
            FROM pins
            WHERE id = ? AND document_id = ?
            """,
            (pin_id, doc_id),
        ).fetchone()
        return _pin_from_row(row) if row is not None else None
    finally:
        conn.close()


def set_pin_explanation(doc_id: str, pin_id: str, explanation: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            UPDATE pins SET explanation = ?
            WHERE id = ? AND document_id = ?
            """,
            (explanation, pin_id, doc_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def document_public(row: dict[str, Any]) -> dict[str, str]:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _pin_from_row(row: sqlite3.Row) -> dict[str, Any]:
    pin: dict[str, Any] = {
        "id": row["id"],
        "page": int(row["page"]),
        "x": float(row["x"]),
        "y": float(row["y"]),
        "text": row["text"],
        "bbox": json.loads(row["bbox_json"]),
    }
    if row["explanation"] is not None:
        pin["explanation"] = row["explanation"]
    return pin
