# Skip-if-ready implementation

## What shipped

`process_document` in `backend/worker.py` no longer re-runs extract → detect → replace when the document is already `ready`.

After loading the document row:

- Missing row: log and return (unchanged).
- `ready`: return immediately. No extract, detect, delete, or insert.
- `processing` or `failed`: same pipeline as before (`extract` → `detect` → `_replace_pins` → `ready` / `failed`).

`_replace_pins` is still delete-then-insert. There is no pin-content diff, no reprocess API, and `explain.py` is still unused.

A late or duplicate in-flight call cannot stamp `failed` over `ready`. The failure update is `WHERE id = ? AND status = ?` using the status this run started with (`processing` or `failed`). If another call already moved the row to `ready`, the `failed` update matches zero rows.

The CLI (`python worker.py <doc_id>`) is unchanged.

## Where it lives

Only `backend/worker.py` changed. That file is the background pipeline Track C owns: FastAPI glue (or the CLI) calls `process_document(doc_id)` after upload. Schema and CRUD stay in `backend/db.py`; this change only reads `documents.status` and writes it conditionally.

## Impact

Without the skip, a second successful run deleted existing pins and inserted new ones (`pin.id`s changed, `explanation` reset to NULL, OCR ran again). Skip-if-ready makes “already processed” idempotent so a double-queued task or a second CLI invocation leaves good pins and explanations in place. Failed documents still retry through the full replace path. Overlapping runs can still waste extract work if both start before the first finishes; they cannot demote a finished document from `ready` to `failed`.
