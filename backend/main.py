"""
FastAPI stub (Phase 0).

API prefix: Vite on :5173 proxies `/api` → this server on :8000 and strips `/api`.
FastAPI routes are mounted at `/` (e.g. GET /documents, GET /health).
The browser only calls `/api/...`.

Track B fills upload, SQLite CRUD, and file serving.
"""

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from db import create_tables
from explain import MissingAPIKeyError, explain

app = FastAPI(title="Pinpoint prototype")
create_tables()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/documents")
def list_documents():
    return []


@app.get("/documents/{doc_id}")
def get_document(doc_id: str):
    raise HTTPException(status_code=404, detail="Document not found")


@app.get("/documents/{doc_id}/pins")
def get_pins(doc_id: str):
    raise HTTPException(status_code=404, detail="Document not found")


@app.get("/documents/{doc_id}/file")
def get_file(doc_id: str):
    raise HTTPException(status_code=404, detail="Document not found")


@app.post("/documents")
async def upload(file: UploadFile):
    _ = file
    return JSONResponse(
        status_code=501,
        content={"detail": "Track B implements upload"},
    )


class ExplainRequest(BaseModel):
    phrase: str
    context: str
    document_type: str = Field(default="unknown")


@app.post("/documents/{doc_id}/pins/{pin_id}/explain")
async def explain_pin(doc_id: str, pin_id: str, body: ExplainRequest):
    # Track D: body-driven explain for curl /docs. Glue looks up pin ids and
    # writes pins.explanation; 404 for unknown document/pin is Track B/glue.
    _ = (doc_id, pin_id)
    try:
        text = explain(body.phrase, body.context, body.document_type)
    except MissingAPIKeyError:
        raise HTTPException(
            status_code=503,
            detail="LLM API key is not configured",
        )
    return {"explanation": text}
