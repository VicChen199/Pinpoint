"""
FastAPI stub (Phase 0).

API prefix: Vite on :5173 proxies `/api` → this server on :8000 and strips `/api`.
FastAPI routes are mounted at `/` (e.g. GET /documents, GET /health).
The browser only calls `/api/...`.

Track B fills upload, SQLite CRUD, and file serving.
"""

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from db import create_tables

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


@app.post("/documents/{doc_id}/pins/{pin_id}/explain")
async def explain_pin(doc_id: str, pin_id: str):
    return JSONResponse(
        status_code=501,
        content={"detail": "Track D implements explain; glue wires this route"},
    )
