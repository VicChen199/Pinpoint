"""
FastAPI routes (Track B).

API prefix: Vite on :5173 proxies `/api` → this server on :8000 and strips `/api`.
FastAPI routes are mounted at `/` (e.g. GET /documents, GET /health).
The browser only calls `/api/...`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from db import (
    ROOT,
    UPLOAD_DIR,
    create_tables,
    document_public,
    get_document,
    get_pin,
    insert_document,
    list_documents,
    list_visible_pins,
    set_pin_explanation,
)
from explain import MissingAPIKeyError, explain
from worker import process_document

app = FastAPI(title="Pinpoint prototype")
create_tables()

PDF_MAGIC = b"%PDF-"


class ExplainRequest(BaseModel):
    phrase: str
    context: str
    document_type: str = Field(default="unknown")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/documents")
def documents_list():
    return [document_public(row) for row in list_documents()]


@app.get("/documents/{doc_id}")
def document_get(doc_id: str):
    row = get_document(doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_public(row)


@app.get("/documents/{doc_id}/pins")
def pins_get(doc_id: str):
    row = get_document(doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if row["status"] != "ready":
        raise HTTPException(status_code=409, detail="Document is not ready")
    return {"pins": list_visible_pins(doc_id)}


@app.get("/documents/{doc_id}/file")
def file_get(doc_id: str):
    row = get_document(doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = _resolve_storage_path(row["storage_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=row["filename"],
        content_disposition_type="inline",
    )


@app.post("/documents", status_code=201)
async def upload(file: UploadFile, background_tasks: BackgroundTasks):
    raw = await file.read()
    filename = file.filename or "document.pdf"
    if not raw.startswith(PDF_MAGIC):
        raise HTTPException(status_code=400, detail="PDF only")

    doc_id = f"doc_{uuid.uuid4().hex}"
    dest = UPLOAD_DIR / f"{doc_id}.pdf"
    dest.write_bytes(raw)
    storage_path = f"data/uploads/{doc_id}.pdf"
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        insert_document(doc_id, filename, "processing", storage_path, created_at)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    background_tasks.add_task(process_document, doc_id)
    return {"id": doc_id, "status": "processing"}


@app.post("/documents/{doc_id}/pins/{pin_id}/explain")
async def explain_pin(doc_id: str, pin_id: str, body: ExplainRequest):
    if get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    pin = get_pin(doc_id, pin_id)
    if pin is None:
        raise HTTPException(status_code=404, detail="Pin not found")

    existing = pin.get("explanation")
    if existing:
        return {"explanation": existing}

    phrase = body.phrase.strip() or pin["text"]
    try:
        text = explain(phrase, body.context, body.document_type)
    except MissingAPIKeyError:
        raise HTTPException(
            status_code=503,
            detail="LLM API key is not configured",
        )
    set_pin_explanation(doc_id, pin_id, text)
    return {"explanation": text}


def _resolve_storage_path(storage_path: str) -> Path:
    path = Path(storage_path)
    if not path.is_absolute():
        path = ROOT / path
    return path
