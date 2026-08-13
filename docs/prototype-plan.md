# Pinpoint prototype — plan

Planning document for the prototype only (Phase 1 — Foundation in [technical-overview.md](./technical-overview.md)). Production upgrades, auth, cloud storage, and later features are out of scope.

There is no application code in the repo yet. This plan is the implementation brief for standing up the core product as one full-stack app.

---

## Problem

People upload dense PDFs (contracts, forms, papers, policies) and need confusing terms explained in context, on the page, without leaving the document. Generic search and chatbots drift off the text or invent facts.

The prototype must prove the whole loop in one app: upload a PDF, extract words and boxes, mark likely-confusing terms with underlines, and explain a clicked term in a side panel using surrounding document text. If that loop is wrong, later infra (Postgres, S3, auth) will not fix it.

---

## In scope

- React + Vite + TypeScript viewer with PDF.js
- Underline overlay aligned in unscaled PDF coordinates
- Explanation side panel (current card + stack) with the interaction rules below
- FastAPI: upload, document status, pins, PDF file, on-demand explain
- Background processing (FastAPI `BackgroundTasks` or a thread)
- Digital PDF text + bbox extraction, with OCR fallback for scans
- Domain-agnostic term detection (heuristic is enough; LLM pass optional)
- Grounded explanation endpoint (OpenAI, Anthropic, or Ollama)
- SQLite + local `data/uploads/`
- No auth

## Out of scope

- PostgreSQL, S3, pre-signed uploads, Clerk/Supabase
- Redis-backed workers
- Explanation caching as a product requirement (storing on the pin row after first generate is fine)
- Underline visibility toggle, RAG Q&A, extra file types
- Pin icons, hover-only popups, or a glossary of every detected term
- The four learning mini-projects as separate apps (this plan is the single prototype app)

---

## Product rules the prototype must follow

### Pins

A pin is one marked occurrence of a term, not an on-page icon. The page shows an underline; explanations open in the side panel.

Each pin stores page number, unscaled coordinates, term text, bounding box, and an optional explanation. Identity is per occurrence: `indemnify` on page 1 and page 8 are two pins.

Positions are stored at scale = 1. Multiply by the current viewport scale only when rendering.

```ts
type Pin = {
  id: string;
  page: number;
  x: number;   // PDF user space, scale = 1
  y: number;
  text: string;
  bbox: { x: number; y: number; width: number; height: number };
  explanation?: string;
};
```

### Underlines

Draw a clickable underline along the bottom of `pin.bbox`, with a hit target large enough to tap. Cap underlines per page.

- Click or tap loads the explanation. That is the only way to call `/explain`.
- Hover may restyle the underline. Hover does not open the panel and does not call `/explain`.
- Underlines live in the page overlay so they scroll and zoom with the PDF.
- Phones use the same click path (tap). No hover-only interaction.

### Explanation panel

The panel is a session log of pins the user has opened, not a chatbot and not a glossary. It stays empty until the first underline click. Closing the panel must not discard session history for that document.

Layout, top to bottom:

1. Current card — last page-clicked pin, always expanded, sized to content with a max height (internal scroll if long).
2. Stack — previously opened pins, newest at the top, independent scroll filling remaining height.

On a phone, use a bottom sheet with the same two zones. Cards are unique by `pin.id`. Stack rows show term, page, and a short snippet when the same word appears more than once.

**Page click:** that pin becomes current; fetch or show its explanation. The previous current card collapses and is inserted at the top of the stack. If this pin is already in the stack, move it to current (no duplicate). If it is already current, leave it. After a stack insert, scroll the stack to the top.

**Same word, different place:** new `pin.id`, new current card. Do not merge by term text.

**Stack click:** expand or collapse that row in place. Do not replace current, do not reorder the stack. Optionally scroll the PDF to that underline.

**Collapse:** auto-collapse only when a card leaves the current slot. A manually expanded stack row stays expanded while it remains in the stack. If that pin becomes current again and later leaves, collapse-on-leave still applies.

**Stack scrolling:** current card does not scroll with the stack. Expanded older cards may scroll out of view; do not pin them or auto-follow them.

---

## Data model (SQLite)

```sql
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  filename TEXT,
  status TEXT,  -- processing | ready | failed
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

PDFs live under `data/uploads/`. The browser never talks to SQLite, the filesystem, or the LLM.

---

## API

```
POST   /documents                              multipart upload → { id, status }
GET    /documents                              list
GET    /documents/{id}                         metadata + status
GET    /documents/{id}/pins                    pin array when ready
GET    /documents/{id}/file                    serve PDF for PDF.js
POST   /documents/{id}/pins/{pin_id}/explain   on-demand explanation
```

Explain request body conceptually: `{ phrase, context, document_type }`. Response: `{ explanation }`.

Processing flow:

1. `POST /documents` saves the PDF, inserts `status = processing`, returns `document_id`, kicks the worker.
2. Worker reads the file, extracts words and boxes (digital PDF, OCR if needed), scores terms, inserts pins, sets `status = ready` (or `failed`).
3. UI polls or refetches until ready, then `GET .../pins` and draws underlines.
4. Underline click calls `POST .../explain`. A new card may show loading, then fill.

---

## Extraction and explanations

Digital PDFs: extract words and bounding boxes (PyMuPDF or pdfplumber). Scanned PDFs: Tesseract, then boxes from OCR output.

Worker output shape (per page): page number, page width/height, words with `text`, `bbox`, and `confidence`.

Term detection: no fixed domain dictionary. Score candidates (abbreviations, uncommon words, multi-word terms) with heuristics; an LLM pass over extracted text is optional. Cap pins per page.

Explanation inputs: `phrase`, surrounding `context`, and `document_type` (inferred or user-supplied). Prompt rules:

- Plain English for a general reader
- Use only provided context; do not invent facts, figures, or citations
- Explain the term and how it applies in this document
- 2–4 short sentences
- No legal, medical, financial, or other professional advice
- If context is insufficient, say what is missing

---

## Stack (prototype)

| Layer | Choice |
|-------|--------|
| Frontend | React, Vite, TypeScript, pdfjs-dist |
| Backend | FastAPI |
| Extraction | PyMuPDF or pdfplumber; Tesseract + Pillow for scans |
| LLM | OpenAI, Anthropic, or Ollama |
| Database | SQLite |
| Storage | Local `data/uploads/` |
| Jobs | `BackgroundTasks` or a thread |

---

## Concrete steps

1. Scaffold the app: Vite React TypeScript frontend and FastAPI backend. Confirm a PDF can be uploaded and served back to PDF.js.
2. Persist documents in SQLite (`processing` / `ready` / `failed`) and store files under `data/uploads/`.
3. Render the PDF in the browser. Overlay underlines from pin `bbox` values stored at scale = 1; re-render the canvas on zoom so underlines do not drift.
4. Extraction worker: digital text + boxes; OCR fallback for pages with no selectable text. Write word JSON in the schema above.
5. Term detection: heuristic scoring, per-page cap, insert pin rows, mark the document ready.
6. Side panel: current card + stack, including move-to-latest, no duplicate `pin.id`, collapse-on-leave, independent stack scroll. Phone: bottom sheet with the same zones.
7. Explain endpoint: load phrase + local context from the pin’s page, call the model with the prompt rules, store the text on the pin, return it. Click/tap only; hover restyle only.
8. Document list so more than one upload can be reopened. Closing the panel keeps that document’s session history in the client for the session.
9. Smoke-test with one digital PDF and one scan: upload → ready → underlines stay put on zoom → click explains in the panel → stack behaves per the rules.

---

## Success criteria

- Upload a digital PDF and a scanned PDF; both reach `ready` or a clear `failed` state.
- Underlines appear on detected terms and stay aligned from roughly 50%–200% zoom and while scrolling.
- Click/tap an underline opens or updates the current card; hover does not fetch an explanation.
- Panel rules hold: unique cards, collapse-on-leave, stack expand-in-place, newest-at-top, no glossary of unopened pins.
- Explanations are short, grounded in surrounding text, and refuse to invent facts when context is thin.
- Secrets stay on the server. No auth, Postgres, S3, or Redis required to run locally.

---

## Risks

- Coordinate mismatch (PDF user space vs canvas vs CSS) will make underlines drift; store unscaled boxes and scale only at render time.
- OCR on poor scans will produce bad boxes and bad terms; surface `failed` or low-confidence pages rather than drawing junk.
- Heuristic term detection will over- or under-mark; the per-page cap is the usability backstop until an LLM pass exists.
- LLM latency and cost: explain is on-demand and click-gated so the worker is not generating every term up front.
- BackgroundTasks die with the process; acceptable for the prototype, not for production.
- Panel edge cases (duplicates, same word twice, expand-then-reclick) are easy to get wrong; treat the interaction rules as test cases, not polish.

---

## Further reading

- [technical-overview.md](./technical-overview.md) — full architecture, production upgrades, and later phases
- [README](../README.md) — product vision and user-facing behavior
- [full-stack-frameworks-guide.md](./full-stack-frameworks-guide.md) — tool reference
