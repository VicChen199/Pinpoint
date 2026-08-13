# Pinpoint prototype — contract

Frozen interfaces for building the prototype in parallel. Product behavior lives in [prototype-plan.md](./prototype-plan.md). This file is the shared schema, API, folder layout, and file ownership. Do not change it without an explicit decision.

If a track needs a field or route that is not here, stop and ask. Do not invent a second pin shape.

---

## Problem

Several agents will implement viewer, API, extraction, and explain at the same time. If pin coordinates, JSON, or routes drift, the glue phase cannot connect them. This contract is the single source of truth for those boundaries.

---

## Frozen stack

| Layer | Choice | Do not use |
|-------|--------|------------|
| Frontend | React, Vite, TypeScript, `pdfjs-dist` | Next.js, `react-pdf`, `@react-pdf/renderer` |
| Backend | FastAPI on port 8000 | Express as the prototype API |
| Extraction | PyMuPDF (`fitz`) for digital PDFs; Tesseract (`pytesseract`) + Pillow for scans | OCR-only on digital PDFs |
| Digital alternative | pdfplumber only if PyMuPDF fails a layout; not a second required path | Running PyMuPDF and pdfplumber on every page |
| LLM | One provider via env: OpenAI, Anthropic, or Ollama | Calling the LLM from the browser; ensembling providers |
| Database | SQLite file under `data/` | Postgres, MongoDB |
| Files | `data/uploads/{id}.pdf` | PDF bytes in SQLite |
| Jobs | FastAPI `BackgroundTasks` or a thread | Redis, Celery |
| Auth | None | Clerk, Supabase |

Dev: Vite on 5173, proxy `/api` to `http://localhost:8000`. React calls `/api/...` only.

Secrets: backend `.env` only (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`). Never `VITE_*` for keys. `.env` is gitignored (`*.env`). Commit `backend/.env.example` with placeholders.

---

## Frozen types

### Pin (API and frontend)

Coordinates are PDF user space at scale = 1. Multiply by the current PDF.js viewport scale only when drawing. Never store screen pixels.

```ts
type Bbox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type Pin = {
  id: string;
  page: number; // 1-based
  x: number;
  y: number;
  text: string;
  bbox: Bbox;
  explanation?: string | null;
};
```

- `id` is per occurrence, not per word. Same term on two pages → two pins.
- `x`, `y` match `bbox.x`, `bbox.y` (top-left of the box in unscaled page space).
- `explanation` is omitted or null until `/explain` succeeds; then it is stored on the pin row.
- Overlay draws an underline along the bottom of `bbox`, not a pin icon.

### Document status

Exactly one of: `processing` | `ready` | `failed`.

```ts
type DocumentStatus = "processing" | "ready" | "failed";

type Document = {
  id: string;
  filename: string;
  status: DocumentStatus;
  created_at: string;
};
```

Do not add `pins` onto this object. Pins are only `GET /documents/{id}/pins`.

### Extraction word JSON (worker internal → then pins)

Worker output before term detection. Not a SQLite table. Pins are a subset of these words.

```json
{
  "source": "document.pdf",
  "pages": [
    {
      "page": 1,
      "width": 612,
      "height": 792,
      "words": [
        {
          "text": "indemnify",
          "bbox": { "x": 120.5, "y": 340.2, "width": 28.0, "height": 12.0 },
          "confidence": 95
        }
      ]
    }
  ]
}
```

`width` / `height` are unscaled page size (same space as pin `bbox`).

### SQLite

PDFs are not in the database. `storage_path` is a filesystem path string.

```sql
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  filename TEXT,
  status TEXT,
  storage_path TEXT,
  created_at TEXT
);

CREATE TABLE pins (
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
```

`bbox_json` is the `Bbox` object as JSON text. `GET .../pins` parses it into `bbox` on the Pin object. Do not send `bbox_json` to the frontend.

---

## Frozen API

Base path in the browser: `/api`. FastAPI may mount routes at `/` and let Vite strip `/api`, or mount at `/api`. Pick one in Phase 0 and document it in `backend` comments. JSON below assumes the FastAPI path without the proxy prefix.

### `POST /documents`

Multipart field name: `file`. PDF only.

Response 200 or 201:

```json
{ "id": "doc_...", "status": "processing" }
```

Saves `data/uploads/{id}.pdf`, inserts the documents row, schedules `process_document(id)`. Does not wait for extraction.

### `GET /documents`

Array of `Document` (no pins).

### `GET /documents/{id}`

One `Document`. 404 if missing. Frontend polls this until `ready` or `failed`.

### `GET /documents/{id}/pins`

When `status === "ready"`: `{ "pins": Pin[] }`.

When `processing` or `failed`: do not return a second pin JSON shape. UI uses `GET /documents/{id}` for the spinner/error. Pins endpoint: **404 if the document is missing; 409 if status is not `ready`.**

### `GET /documents/{id}/file`

Raw PDF bytes, `Content-Type: application/pdf`. This is what PDF.js loads. Not JSON.

### `POST /documents/{id}/pins/{pin_id}/explain`

Called only from underline click/tap, never from hover.

If the pin already has `explanation`, return it without calling the LLM.

Request body (server may also load phrase/context from the pin + page text if the client sends only the ids):

```json
{ "phrase": "indemnify", "context": "...surrounding paragraph...", "document_type": "lease" }
```

`document_type` may be `"unknown"` in the prototype.

Response:

```json
{ "explanation": "..." }
```

Write the text onto `pins.explanation`. Prompt rules: [prototype-plan.md](./prototype-plan.md) (plain English, grounded, 2–4 sentences, no professional advice, say when context is missing).

Errors: 404 unknown document/pin. Missing LLM key: 503 with a short message, not a stack trace.

---

## Frozen layout

One app, not four mini-project folders.

```
Pinpoint/
  frontend/                 # Vite + React + TypeScript
    public/
      sample.pdf            # fixture PDF for Track A
      pins.fixture.json     # fixture Pin[]
    src/
      viewer/               # Track A — PDF.js canvas
      overlay/              # Track A — underlines
      panel/                # Track A — current card + stack
      api.ts                # thin fetch helpers (Phase 0 stub ok)
      types.ts              # Pin, Document — copy from this contract
  backend/
    main.py                 # Track B — routes only; import other modules
    db.py                   # Track B — SQLite
    worker.py               # Track C — process_document
    extract.py              # Track C — PyMuPDF / Tesseract
    detect.py               # Track C — heuristic terms → Pin rows
    explain.py              # Track D — LLM call
    .env.example
  data/
    uploads/                # PDFs; not committed
    app.db                  # SQLite; not committed
  docs/
    prototype-plan.md
    prototype-contract.md   # this file
```

Phase 0 creates empty modules with the function signatures below so parallel tracks do not invent names.

---

## Module signatures (do not rename)

```python
# extract.py
def extract_words(pdf_path: str) -> dict: ...
# returns the word JSON object above

# detect.py
def detect_pins(words_doc: dict, *, max_per_page: int = 12) -> list[dict]: ...
# each dict is a Pin without document_id / explanation

# worker.py
def process_document(doc_id: str) -> None: ...
# extract → detect → INSERT pins → status ready | failed

# explain.py
def explain(phrase: str, context: str, document_type: str) -> str: ...

# db.py — documents and pins CRUD used by main.py and worker.py
```

Frontend overlay: `left = bbox.x * scale`. Underline at the bottom of the box (`bbox.y + bbox.height`). Hit target larger than the stroke.

---

## Mocks (so tracks do not wait)

**Track A** may load `public/sample.pdf` and `public/pins.fixture.json` until the API exists. Fixture pins must match the Pin type (unscaled bbox).

**Track B** may return fixture pins from `GET .../pins` and skip calling `process_document` until glue. Upload + `GET .../file` should still be real.

**Track C** may run as a CLI on a sample PDF and print word JSON / pin list. Must write the same shapes as the API.

**Track D** may be tested with curl or FastAPI `/docs` against `explain()` without the viewer.

Glue (not parallel): `BackgroundTasks` → real pins → UI polls → click → `explain.py` → panel.

---

## Parallel file ownership

Tracks may run as isolated git branches / worktrees off a committed Phase 0. Suggested names: `proto/viewer`, `proto/api`, `proto/extract`, `proto/explain`, then merge into `proto/glue`. Isolation does not replace this contract.

| Track | May edit | Must not edit |
|-------|----------|----------------|
| **0 — Scaffold** | Create the layout, `types.ts`, stub `main.py`, Vite proxy, empty modules | Product features |
| **A — Viewer + panel** | `frontend/src/viewer/`, `overlay/`, `panel/`, fixture files under `frontend/public/` | `backend/` except read-only API usage |
| **B — API + SQLite** | `backend/main.py`, `backend/db.py`, `data/` usage | `frontend/src/viewer|overlay|panel`, `extract.py`, `detect.py`, `explain.py` |
| **C — Extraction** | `backend/extract.py`, `detect.py`, `worker.py` | `frontend/`, `explain.py`, route list in `main.py` |
| **D — Explain** | `backend/explain.py` | Overlay, OCR, SQLite schema |
| **Glue** | Wire imports in `main.py`, polling in frontend `api.ts` / app shell, smoke-test | Changing Pin, bbox space, or routes |

`frontend/src/types.ts` and this contract are owned by Phase 0. Later tracks import them. Do not add fields.

`backend/main.py` in Track B: routes that call `process_document` and `explain` via import. Track C/D implement the functions; glue is the first time those imports must succeed end-to-end. Until then B may stub:

```python
def process_document(doc_id: str) -> None:
    raise NotImplementedError

def explain(phrase: str, context: str, document_type: str) -> str:
    return "stub"
```

Overwrite those stubs only in the owned modules, then glue switches the imports.

Do not run three local agents on the same dirty working tree. Use worktrees/branches, or one agent at a time.

---

## Product rules (pointer)

Do not weaken these. Full text: [prototype-plan.md](./prototype-plan.md).

- Click/tap underline → explain. Hover does not fetch.
- Panel: current card + stack; unique by `pin.id`; collapse-on-leave; stack expand in place; newest at top.
- Phone: same tap path; bottom sheet with the same two zones.
- Cap pins per page (`detect.py` default 12).
- No pin icons, no hover popups, no glossary of unopened pins.

---

## Phase order

1. **Phase 0 (serial)** — layout, types, stub routes, proxy, fixtures. Commit this before launching parallel agents. No parallel implementers before this.
2. **Tracks A, C, D in parallel** (B in parallel if it only fills `main.py` / `db.py` and leaves C/D modules as stubs), each on its own branch/worktree.
3. **Glue (serial)** — merge tracks, then worker, poll, live explain, document list, digital + scan smoke-test.

---

## Risks if this contract is ignored

- Screen-space boxes → underlines drift on zoom.
- Two pin JSON shapes → overlay and worker cannot meet.
- `react-pdf` text layer stealing clicks.
- LLM key in the frontend.
- Two agents editing `main.py` and `App.tsx` on the same checkout.
- Redis/Postgres “while we are here” — out of prototype scope.

---

## Further reading

- [prototype-plan.md](./prototype-plan.md) — product rules, steps, success criteria
- [technical-overview.md](./technical-overview.md) — architecture and later phases
