# Frontend glue implementation

## What shipped

The React shell now talks to the live API instead of `public/sample.pdf` and `pins.fixture.json`. Upload, document list, status polling, pin overlay, and click-to-explain are wired in `frontend/src/App.tsx`.

`Open craft-que.pdf` fetches the local copy at `frontend/public/craft-que.pdf` (copied from the Desktop ELA file) and `POST`s it as `file`. A generic PDF file input remains. The list is `GET /documents`. Selecting a row polls `GET /documents/{id}` until `ready` or `failed`, then loads `GET .../pins` and `GET .../file` into the existing PDF.js viewer. Underline click calls `POST .../explain` (phrase = pin text; context = other terms on that page). Hover still does not fetch. Cached `pin.explanation` skips a second LLM call.

`craft-que.pdf` is gitignored so the worksheet is not committed. The button needs that file in `frontend/public/` locally.

## Where it lives

- `frontend/src/api.ts` — `uploadDocument` plus the existing fetch helpers
- `frontend/src/App.tsx` / `App.css` — document column, poll, click → explain
- `frontend/src/panel/useExplanationSession.ts` — `applyExplanation`, `reset` when switching documents
- `frontend/src/panel/ExplanationPanel.tsx` — loading text on the current card

Viewer overlay math, Pin type, and backend routes are unchanged.

## Impact

Tracks A–D meet in the browser: upload this PDF (or another), wait for the worker, draw contract-shaped underlines, explain on click. Smoke-test is the next step (backend + Vite running, digital PDF and a scan). Do not start Phase 2.
