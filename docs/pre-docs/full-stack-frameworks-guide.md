# Full-stack frameworks & tools guide

A practical reference for building Pinpoint and similar full-stack apps. Covers what each tool does, when to use it, pros/cons vs alternatives, and syntax you need to know — especially around secrets, async, and database wiring (areas where copy-paste from AI often breaks).

---

## Table of contents

1. [How the pieces fit together](#how-the-pieces-fit-together)
2. [TypeScript](#typescript)
3. [Frontend](#frontend)
4. [Backend APIs](#backend-apis)
5. [Databases & ORMs](#databases--orms)
6. [File storage (S3)](#file-storage-s3)
7. [Authentication](#authentication)
8. [Background jobs & queues](#background-jobs--queues)
9. [Pinpoint-specific pipeline tools](#pinpoint-specific-pipeline-tools)
10. [LLM integration](#llm-integration)
11. [Hackathon staples](#hackathon-staples)
12. [API keys & secrets (read this carefully)](#api-keys--secrets-read-this-carefully)
13. [Syntax cheat sheet](#syntax-cheat-sheet)

---



## How the pieces fit together

A full-stack app splits work between the **browser** (frontend) and a **server** (backend). They talk over **HTTP** using **JSON**.

```mermaid
flowchart TB
  subgraph client [Browser]
    React[React + Vite]
    PDFjs[PDF.js viewer]
    React --> PDFjs
  end

  subgraph server [Backend]
    API[FastAPI or Express]
    Worker[Background worker]
    API --> Worker
  end

  subgraph data [Data layer]
  DB[(PostgreSQL / SQLite)]
  S3[(S3 / local files)]
  LLM[OpenAI / Anthropic]
  end

  React -->|fetch JSON| API
  API --> DB
  API --> S3
  Worker --> S3
  Worker --> LLM
  Worker --> DB
```



**Pinpoint's path:**


| Phase             | Stack                                                                        |
| ----------------- | ---------------------------------------------------------------------------- |
| Mini-projects 1–4 | React + Vite, FastAPI, SQLite, local `data/uploads/`                         |
| Production MVP    | + PostgreSQL, Prisma (or SQLAlchemy), S3, auth (Clerk/Supabase), Redis queue |


---



## TypeScript

**What it does:** A typed superset of JavaScript. You write `.ts` / `.tsx` files; the compiler (`tsc`) checks types at build time and emits plain JavaScript. Vite runs TypeScript through esbuild during dev (fast, no full type-check) — run `tsc --noEmit` or `npm run build` to catch type errors before deploy.

**Pinpoint use:** Type API responses (`Document`, `Pin`, `bbox`), React component props, Prisma query results, and coordinate math so scale/viewport bugs surface in the editor instead of at runtime.


| Pros                                                        | Cons                                           |
| ----------------------------------------------------------- | ---------------------------------------------- |
| Catches typos, wrong shapes, and missing `await` early      | Extra syntax to learn on top of JS             |
| Autocomplete in VS Code for API fields and Prisma models    | `any` and bad casts can defeat the purpose     |
| Same language for React frontend and Express/Prisma backend | Two runtimes if backend stays Python (FastAPI) |


**Alternatives:**


| Approach                   | Best for                      | Trade-off                              |
| -------------------------- | ----------------------------- | -------------------------------------- |
| **Plain JavaScript**       | Quick throwaway scripts       | No compile-time safety on API shapes   |
| **JSDoc +** `// @ts-check` | Gradual typing in `.js` files | Verbose; weaker inference than `.ts`   |
| **Python + Pydantic**      | FastAPI backend               | Types live on the server, not in React |


**Syntax you'll use:**

```ts
// Primitives and object shapes
type Bbox = { x: number; y: number; width: number; height: number };

type Pin = {
  id: string;
  page: number;
  text: string;
  bbox: Bbox;
  isVisible: boolean;
  explanation?: string; // optional field
};

// Union — status must be exactly one of these strings
type DocumentStatus = "processing" | "ready" | "failed";

type Document = {
  id: string;
  filename: string;
  status: DocumentStatus;
  pins: Pin[];
};
```

```ts
// Typing fetch responses (Pinpoint API)
async function getDocument(id: string): Promise<Document> {
  const res = await fetch(`/api/documents/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Document; // or use Zod to validate at runtime
}

// Nullable state in React
const [doc, setDoc] = useState<Document | null>(null);
const title = doc?.filename ?? "Loading…"; // optional chaining + nullish coalesce
```

```ts
// interface vs type — either works for object shapes; type is needed for unions
interface PinOverlayProps {
  pin: Pin;
  scale: number;
  onExplain: (pinId: string) => void;
}

function screenX(pin: Pin, scale: number): number {
  return pin.bbox.x * scale;
}
```

```ts
// Generics — reusable typed containers
type ApiResult<T> = { data: T } | { error: string };

function isError<T>(result: ApiResult<T>): result is { error: string } {
  return "error" in result;
}
```

**Project setup (Vite + React):**

```bash
npm create vite@latest pinpoint-ui -- --template react-ts
cd pinpoint-ui && npm install
npm run dev    # dev server with HMR
npm run build  # tsc + vite build — fails on type errors if configured
```

Minimal `tsconfig.json` flags worth knowing:


| Option                        | Effect                                                      |
| ----------------------------- | ----------------------------------------------------------- |
| `strict: true`                | Enables strict null checks and no implicit `any` — leave on |
| `moduleResolution: "bundler"` | Matches Vite/modern tooling                                 |
| `jsx: "react-jsx"`            | React 17+ JSX transform (no `import React` required)        |


**Common gotchas (AI often gets these wrong):**


| Mistake                                                     | Fix                                              |
| ----------------------------------------------------------- | ------------------------------------------------ |
| `JSON.parse` / `res.json()` assumed to match your type      | Validate with **Zod** or check fields before use |
| Using `any` everywhere                                      | Use `unknown` + narrow, or define a `type`       |
| `pin.bbox.x` when `pin` might be `null`                     | `pin?.bbox.x` or guard with `if (!pin) return`   |
| Putting secrets in `import.meta.env` without `VITE_` prefix | Only `VITE_*` vars are exposed to the browser    |
| Blocking on type errors in dev                              | Vite still serves; run `tsc --noEmit` in CI      |


**Further reading:** [TypeScript handbook](https://www.typescriptlang.org/docs/handbook/intro.html) · [Total TypeScript — React with TypeScript](https://www.totaltypescript.com/tutorials/react-with-typescript)

---



## Frontend



### React + Vite + TypeScript

**What it does:** React builds the UI as components. Vite is the dev server and bundler (fast hot reload). TypeScript adds types so props and API responses are checked at compile time.

**Pinpoint use:** PDF viewer, pin overlay, upload form, polling for document status, calling `/explain`.


| Pros                                           | Cons                                                       |
| ---------------------------------------------- | ---------------------------------------------------------- |
| Huge ecosystem; PDF.js integrates cleanly      | You assemble routing, data fetching, auth yourself         |
| Vite is fast and simple vs Create React App    | Not SEO-friendly out of the box (fine for a logged-in app) |
| TypeScript catches coordinate/scale bugs early | Steeper learning curve than plain JS                       |


**Alternatives:**


| Framework      | Best for                                        | Trade-off                                                |
| -------------- | ----------------------------------------------- | -------------------------------------------------------- |
| **Next.js**    | SEO, file-based routing, API routes in one repo | More opinionated; overkill if backend is separate Python |
| **Vue + Vite** | Gentler learning curve                          | Smaller job market; fewer PDF examples                   |
| **SvelteKit**  | Very fast, less boilerplate                     | Smaller ecosystem                                        |


**Syntax you'll use:**

```tsx
// State + effect (polling document status)
import { useState, useEffect } from "react";

type Document = { id: string; status: "processing" | "ready" | "failed" };

function DocumentStatus({ documentId }: { documentId: string }) {
  const [doc, setDoc] = useState<Document | null>(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await fetch(`/api/documents/${documentId}`);
      const data: Document = await res.json();
      setDoc(data);
      if (data.status === "ready" || data.status === "failed") {
        clearInterval(interval);
      }
    }, 2000);
    return () => clearInterval(interval); // cleanup on unmount
  }, [documentId]);

  return <p>Status: {doc?.status ?? "loading…"}</p>;
}
```

```tsx
// Calling an API on user action
async function explainPin(documentId: string, pinId: string) {
  const res = await fetch(
    `/api/documents/${documentId}/pins/${pinId}/explain`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const { explanation } = await res.json();
  return explanation;
}
```

**Vite env vars (frontend):** Only variables prefixed with `VITE_` are exposed to the browser. Never put secret API keys in frontend env vars — users can read them in DevTools.

```bash
# .env.local (frontend) — OK for public config only
VITE_API_BASE_URL=http://localhost:8000
```

```ts
const apiBase = import.meta.env.VITE_API_BASE_URL;
```



### PDF.js (`pdfjs-dist`)

**What it does:** Renders PDF pages to a `<canvas>` in the browser. Pinpoint stores pin coordinates in **unscaled page space** and multiplies by viewport scale at render time.


| Pros                                  | Cons                                   |
| ------------------------------------- | -------------------------------------- |
| Industry standard for in-browser PDFs | Worker setup in Vite is fiddly         |
| No server round-trip to view pages    | Large PDFs can be slow on weak devices |


**Critical syntax (worker — AI often gets this wrong):**

```ts
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;
```

---



## Backend APIs



### Backend APIs in plain English

Your **backend** is a program that runs on a server (your laptop in dev, a cloud machine in production). It **listens** for HTTP requests from the browser and **responds** with JSON (or files).

Think of it like a restaurant:


| Piece                | In a restaurant      | In Pinpoint                                                     |
| -------------------- | -------------------- | --------------------------------------------------------------- |
| **Client**           | Customer             | React app in the browser                                        |
| **Request**          | Order ("one burger") | `POST /documents` with a PDF file                               |
| **Route / endpoint** | Menu item            | `/documents`, `/documents/{id}/pins`                            |
| **Handler**          | Kitchen              | Your Python or Node function that saves the file and starts OCR |
| **Response**         | Plated food          | JSON like `{ "id": "abc", "status": "processing" }`             |


The frontend never talks to the database or OpenAI directly for Pinpoint — it calls **your** API, and your API talks to those services. That keeps secrets on the server.

### How a request travels

```mermaid
sequenceDiagram
  participant Browser as React (browser)
  participant API as FastAPI / Express
  participant DB as SQLite / Postgres
  participant Store as Local disk / S3

  Browser->>API: POST /documents (PDF file)
  API->>Store: Save PDF
  API->>DB: INSERT document row (status: processing)
  API-->>Browser: 200 JSON { id, status }
  Note over API: Background worker runs OCR later
  Browser->>API: GET /documents/{id}
  API->>DB: SELECT document + pins
  API-->>Browser: 200 JSON { id, status, pins: [...] }
```





### HTTP status codes (memorize these)


| Code    | Meaning      | When you use it                                          |
| ------- | ------------ | -------------------------------------------------------- |
| **200** | OK           | Successful read or action                                |
| **201** | Created      | New document or pin was saved                            |
| **400** | Bad request  | Client sent invalid data (missing file, bad JSON)        |
| **401** | Unauthorized | User is not logged in (production auth)                  |
| **404** | Not found    | Document ID does not exist                               |
| **500** | Server error | Unhandled bug — log it, don't leak stack traces to users |


**Beginner tip:** In your route handlers, return explicit status codes. Don't always return `200` when something failed.

```python
# FastAPI
from fastapi import HTTPException

@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = await fetch_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
```

```ts
// Express
app.get("/documents/:id", async (req, res) => {
  const doc = await fetchDocument(req.params.id);
  if (!doc) return res.status(404).json({ error: "Document not found" });
  res.json(doc);
});
```



### Your first FastAPI server (step by step)

**1. Create a virtual environment and install FastAPI:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install fastapi uvicorn python-multipart
```

`python-multipart` is required for file uploads — easy to forget.

**2. Create** `main.py`**:**

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}
```

**3. Run the server:**

```bash
uvicorn main:app --reload --port 8000
```

- `main:app` means "the `app` object inside `main.py`"
- `--reload` restarts when you save files (dev only)
- Open **[http://localhost:8000/docs](http://localhost:8000/docs)** — FastAPI's interactive API explorer (try endpoints without writing frontend code)

**4. Call it from React (later):**

```ts
const res = await fetch("http://localhost:8000/health");
const data = await res.json(); // { ok: true }
```

In dev, use a [Vite proxy](#frontend-proxy-pattern-avoid-cors--hide-backend-url) so the browser calls `/api/health` instead of a different port (avoids CORS headaches).

### FastAPI (Python) — Pinpoint's mini-project stack

**What it does:** Async HTTP API framework. Auto-generates OpenAPI docs at `/docs`. Great for file uploads, background tasks, and calling Python OCR libraries.


| Pros                                                 | Cons                                                    |
| ---------------------------------------------------- | ------------------------------------------------------- |
| Native fit for PyMuPDF, Tesseract, OpenAI Python SDK | Different language from React (two runtimes)            |
| `UploadFile`, `BackgroundTasks` built in             | Async Python has footguns (blocking OCR in async route) |
| Excellent validation with Pydantic                   | Smaller deploy surface on some PaaS vs Node             |


**Pinpoint routes you'll build:**


| Method | Path                                    | What it does                                   |
| ------ | --------------------------------------- | ---------------------------------------------- |
| `POST` | `/documents`                            | Upload PDF, save file, start processing        |
| `GET`  | `/documents/{id}`                       | Return status + metadata (frontend polls this) |
| `GET`  | `/documents/{id}/pins`                  | List pins for overlay                          |
| `POST` | `/documents/{id}/pins/{pin_id}/explain` | Call LLM, save explanation                     |


**Pydantic — validate request/response shapes (beginners):**

FastAPI uses Pydantic models like TypeScript types. If the client sends bad JSON, FastAPI returns **422** automatically.

```python
from pydantic import BaseModel

class ExplainRequest(BaseModel):
    phrase: str
    context: str
    document_type: str

class ExplainResponse(BaseModel):
    explanation: str

@app.post("/documents/{doc_id}/pins/{pin_id}/explain", response_model=ExplainResponse)
async def explain(doc_id: str, pin_id: str, body: ExplainRequest):
    text = await generate_explanation(body.phrase, body.context, body.document_type)
    return ExplainResponse(explanation=text)
```

**Saving an uploaded file (local disk — mini-project 4):**

```python
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, BackgroundTasks, HTTPException

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/documents")
async def upload(file: UploadFile, background_tasks: BackgroundTasks):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    doc_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{doc_id}.pdf"

    contents = await file.read()
    dest.write_bytes(contents)

    # Save row in DB + kick off OCR (see Databases & File storage sections)
    background_tasks.add_task(process_document, doc_id)
    return {"id": doc_id, "status": "processing"}
```

**Async footgun:** OCR and PyMuPDF are **CPU-bound**. Don't run them directly inside `async def` on the main server thread — use `BackgroundTasks`, a worker process, or `run_in_executor`. Otherwise one slow PDF blocks all other requests.

**Alternatives:**


| Framework        | Language | Best for                                    |
| ---------------- | -------- | ------------------------------------------- |
| **Express**      | Node.js  | JS everywhere; huge middleware ecosystem    |
| **NestJS**       | Node.js  | Large structured apps, DI, TypeScript-first |
| **Django + DRF** | Python   | Batteries-included admin, ORM, auth         |
| **Flask**        | Python   | Minimal; less structure than FastAPI        |




### Express (Node.js)

**What it does:** Minimal HTTP server for Node. You add middleware for JSON parsing, CORS, auth, etc. Very common in tutorials and hackathons.

**Your first Express server (step by step):**

```bash
mkdir backend && cd backend
npm init -y
npm install express cors dotenv
npm install -D typescript @types/express @types/node tsx
```

```ts
// src/index.ts
import "dotenv/config";
import express from "express";
import cors from "cors";

const app = express();
app.use(cors({ origin: "http://localhost:5173" }));
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.listen(3000, () => console.log("http://localhost:3000"));
```

```bash
npx tsx src/index.ts
```

Unlike FastAPI, Express has **no built-in** `/docs` **page** — use [Thunder Client](https://www.thunderclient.com/), [Postman](https://www.postman.com/), or `curl` to test:

```bash
curl http://localhost:3000/health
```


| Pros                                                | Cons                                              |
| --------------------------------------------------- | ------------------------------------------------- |
| Same language as React; one `package.json` possible | No built-in validation or OpenAPI (add Zod, etc.) |
| Massive middleware ecosystem                        | Callback/async style easy to get wrong            |
| Easy to deploy anywhere                             | Less structure — large apps need discipline       |


**Basic syntax:**

```js
import express from "express";
import cors from "cors";

const app = express();
app.use(cors({ origin: "http://localhost:5173" }));
app.use(express.json());

app.get("/documents/:id", async (req, res) => {
  const doc = await db.document.findUnique({ where: { id: req.params.id } });
  if (!doc) return res.status(404).json({ error: "not found" });
  res.json(doc);
});

app.listen(3000, () => console.log("listening on :3000"));
```

**FastAPI equivalent (Pinpoint-style upload):**

```python
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/documents")
async def upload(file: UploadFile, background_tasks: BackgroundTasks):
    doc_id = await save_file(file)
    background_tasks.add_task(process_document, doc_id)
    return {"id": doc_id, "status": "processing"}
```

**When to pick Express vs FastAPI for Pinpoint:** Use **FastAPI** when OCR and PDF parsing stay in Python (PyMuPDF, Tesseract). Use **Express** if you want a single TypeScript monorepo and move OCR to a separate Python microservice or external API.

### Testing your API without the frontend


| Tool                         | Best for                                                |
| ---------------------------- | ------------------------------------------------------- |
| **FastAPI** `/docs`          | Click "Try it out" on any route; upload files in the UI |
| **curl**                     | Quick terminal checks                                   |
| **Browser**                  | `GET` routes only (`http://localhost:8000/health`)      |
| **Postman / Thunder Client** | Express, saved collections, team sharing                |


```bash
# Upload a PDF with curl (FastAPI)
curl -X POST http://localhost:8000/documents \
  -F "file=@statement.pdf"
```

**Debugging checklist when fetch fails:**

1. Is the server running? (`uvicorn` or `node` process still up?)
2. Correct port? (8000 vs 3000)
3. CORS error in browser console? → Add CORS middleware or use Vite proxy
4. `404`? → Check path spelling (`/documents` vs `/document`)
5. `422`? → Request body doesn't match Pydantic model

---



## Databases & ORMs



### Databases in plain English

A **database** stores structured data that survives after your server restarts. For Pinpoint, that means document records, pin coordinates, and explanations — not the PDF files themselves (those live on disk or S3; see [File storage](#file-storage-s3)).

**Core vocabulary:**


| Term                       | Meaning                         | Pinpoint example                    |
| -------------------------- | ------------------------------- | ----------------------------------- |
| **Table**                  | A collection of similar records | `documents`, `pins`                 |
| **Row**                    | One record                      | One uploaded statement              |
| **Column**                 | One field on every row          | `status`, `filename`, `x`           |
| **Primary key (**`id`**)** | Unique identifier for a row     | `doc-a1b2c3`                        |
| **Foreign key**            | Links a row to another table    | `pins.document_id` → `documents.id` |
| **Relation**               | Connected tables                | One document has many pins          |


```mermaid
erDiagram
  documents ||--o{ pins : has
  documents {
    string id PK
    string filename
    string status
    string storage_path
  }
  pins {
    string id PK
    string document_id FK
    int page
    string text
    float x
    float y
    json bbox_json
  }
```



**ORM vs raw SQL:**


| Approach                     | Plain English                            | When to use                                |
| ---------------------------- | ---------------------------------------- | ------------------------------------------ |
| **Raw SQL**                  | You write `SELECT * FROM pins WHERE ...` | Mini-project 4, learning SQL, tiny scripts |
| **ORM** (Prisma, SQLAlchemy) | Python/TypeScript objects map to tables  | Production, fewer string typos, migrations |


You don't need to master SQL on day one — but knowing `SELECT`, `INSERT`, and `WHERE` helps you debug when an ORM does something surprising.

### SQLite (mini-project 4)

**What it does:** File-based SQL database. Zero setup — perfect for local pipeline glue.


| Pros                              | Cons                                                     |
| --------------------------------- | -------------------------------------------------------- |
| No server to install              | Not for concurrent writes at scale                       |
| Single file, easy to reset        | No network access (can't share across containers easily) |
| Same SQL as PostgreSQL for basics | Weaker JSON/query features                               |


**First-time setup:**

```bash
mkdir -p data
# SQLite creates the file automatically on first connect
```

```python
import sqlite3
from pathlib import Path

DB_PATH = Path("data/app.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets you access columns by name
    return conn
```

**Create tables once (run at app startup or in a setup script):**

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  status TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pins (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  page INTEGER NOT NULL,
  text TEXT NOT NULL,
  bbox_json TEXT NOT NULL,
  x REAL NOT NULL,
  y REAL NOT NULL,
  is_visible INTEGER DEFAULT 1,
  explanation TEXT,
  FOREIGN KEY (document_id) REFERENCES documents(id)
);
"""

def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
```

**Basic queries you'll write:**

```python
# Create
conn.execute(
    "INSERT INTO documents (id, filename, status, storage_path) VALUES (?, ?, ?, ?)",
    (doc_id, "statement.pdf", "processing", f"data/uploads/{doc_id}.pdf"),
)

# Read
row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()

# Update status after OCR finishes
conn.execute("UPDATE documents SET status = ? WHERE id = ?", ("ready", doc_id))

# List pins for a document
rows = conn.execute(
    "SELECT * FROM pins WHERE document_id = ? AND is_visible = 1",
    (doc_id,),
).fetchall()
```

The `?` placeholders prevent **SQL injection** — never build SQL with f-strings from user input.

### PostgreSQL (production)

**What it does:** Full-featured relational database. Handles concurrent users, JSON columns, full-text search, and scales with connection pooling.


| Pros                                          | Cons                                         |
| --------------------------------------------- | -------------------------------------------- |
| Industry standard for production apps         | Requires hosting (Supabase, Neon, RDS, etc.) |
| Strong JSON support (`jsonb`) for `bbox_json` | Migrations must be managed                   |
| Great with Prisma / SQLAlchemy                | Connection strings are secrets               |


**Connection string — what each part means:**

```
postgresql://USER:PASSWORD@HOST:5432/DATABASE_NAME
            │     │        │    │      │
            │     │        │    │      └── database name (e.g. pinpoint)
            │     │        │    └── port (5432 is Postgres default)
            │     │        └── hostname (localhost, or db.xxx.supabase.co)
            │     └── password (secret — lives in .env only)
            └── username
```

**Beginner-friendly hosted Postgres (free tiers):**


| Provider                          | Why beginners like it                                              |
| --------------------------------- | ------------------------------------------------------------------ |
| [Supabase](https://supabase.com/) | Dashboard, copy-paste connection string, pairs with auth + storage |
| [Neon](https://neon.tech/)        | Serverless Postgres, simple setup                                  |
| [Railway](https://railway.app/)   | Deploy FastAPI + Postgres in one project                           |


After creating a database, copy the connection string into `.env` as `DATABASE_URL`. Test with:

```bash
# Prisma
npx prisma db pull   # or: npx prisma migrate dev

# psql (optional)
psql "$DATABASE_URL" -c "SELECT 1;"
```

**Alternatives:**


| Database                | Use when                                                          |
| ----------------------- | ----------------------------------------------------------------- |
| **MySQL**               | Legacy hosting, WordPress-adjacent stacks                         |
| **MongoDB**             | Document-shaped data with no relations (Pinpoint fits SQL better) |
| **Supabase (Postgres)** | Want Postgres + auth + storage in one hackathon-friendly package  |




### Migrations in plain English

When you change your schema (add a column, new table), you don't edit the live database by hand in production. You write a **migration** — a versioned script that applies changes safely.

```bash
# What you do                          # What happens
# 1. Edit schema / models              # You add owner_id to Document
# 2. Generate migration                # Tool writes SQL file
# 3. Apply migration                   # Database structure updates
# 4. Deploy app code that uses column  # App and DB stay in sync
```

**Rule for beginners:** If your app crashes with "column does not exist", you probably forgot to run migrations after changing the schema.

### Prisma (Node/TypeScript ORM)

**What it does:** Schema-first ORM. You define models in `schema.prisma`, run migrations, get a type-safe client.


| Pros                                   | Cons                                       |
| -------------------------------------- | ------------------------------------------ |
| Excellent TypeScript types from schema | Node-only (not for FastAPI backend)        |
| Migrations built in                    | Another abstraction over raw SQL           |
| Great DX in VS Code                    | Complex queries sometimes need `$queryRaw` |


**First-time Prisma setup:**

```bash
npm install prisma @prisma/client
npx prisma init   # creates prisma/schema.prisma and .env
# Paste DATABASE_URL into .env, edit schema.prisma (see below)
npx prisma migrate dev --name init
npx prisma generate   # creates typed client — run after every schema change
```

**Alternatives:**


| ORM                | Stack                                         |
| ------------------ | --------------------------------------------- |
| **Drizzle**        | Lighter, SQL-like, growing fast in hackathons |
| **SQLAlchemy**     | Python/FastAPI standard                       |
| **Raw SQL +** `pg` | Maximum control, more boilerplate             |


**Prisma schema (Pinpoint-shaped):**

```prisma
// prisma/schema.prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model Document {
  id          String   @id @default(uuid())
  filename    String
  status      String   // processing | ready | failed
  storagePath String   @map("storage_path")
  createdAt   DateTime @default(now()) @map("created_at")
  pins        Pin[]
}

model Pin {
  id           String  @id @default(uuid())
  documentId   String  @map("document_id")
  page         Int
  text         String
  bboxJson     Json    @map("bbox_json")
  x            Float
  y            Float
  isVisible    Boolean @default(true) @map("is_visible")
  explanation  String?
  document     Document @relation(fields: [documentId], references: [id])
}
```

**Prisma client usage (Express):**

```ts
import { PrismaClient } from "@prisma/client";
const prisma = new PrismaClient();

const pins = await prisma.pin.findMany({
  where: { documentId: id, isVisible: true },
});
```

**SQLAlchemy equivalent (FastAPI + PostgreSQL):**

```python
# models.py
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    filename = Column(String)
    status = Column(String)
    storage_path = Column(String)
    pins = relationship("Pin", back_populates="document")

class Pin(Base):
    __tablename__ = "pins"
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    page = Column(Integer)
    text = Column(String)
    bbox_json = Column(JSON)
    x = Column(Float)
    y = Column(Float)
    is_visible = Column(Boolean, default=True)
    explanation = Column(String, nullable=True)
    document = relationship("Document", back_populates="pins")
```

**Using SQLAlchemy in a FastAPI route (session pattern):**

```python
# db.py — simplified for learning
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

engine = create_engine(os.environ["DATABASE_URL"])
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

```python
# main.py
from fastapi import Depends
from sqlalchemy.orm import Session

@app.get("/documents/{doc_id}/pins")
def list_pins(doc_id: str, db: Session = Depends(get_db)):
    return db.query(Pin).filter(Pin.document_id == doc_id, Pin.is_visible == True).all()
```

`Depends(get_db)` opens a database connection for the request and closes it when done — a pattern you'll see everywhere in FastAPI tutorials.

**Raw SQLite (mini-project 4 — no ORM):**

```python
import sqlite3
import json

conn = sqlite3.connect("data/app.db")
conn.execute(
    "INSERT INTO pins (id, document_id, page, text, bbox_json, x, y) VALUES (?, ?, ?, ?, ?, ?, ?)",
    (pin_id, doc_id, page, text, json.dumps(bbox), x, y),
)
conn.commit()
```

**Common database mistakes (beginners):**


| Mistake                                             | Fix                                                  |
| --------------------------------------------------- | ---------------------------------------------------- |
| SQLite file not found                               | `mkdir -p data` before first run                     |
| `FOREIGN KEY constraint failed`                     | Insert the parent `documents` row before `pins`      |
| Forgot `conn.commit()`                              | Changes never saved — call `commit()` after writes   |
| Storing entire PDF in a `BLOB` column               | Store file on disk/S3; DB holds path + metadata only |
| Sharing one global connection across async requests | Use per-request sessions (`Depends(get_db)`)         |


---



## File storage (S3)



### Why files live outside the database

PDFs can be **megabytes** each. Databases are optimized for small structured rows, not large blobs. Pinpoint stores:


| What                     | Where                                      |
| ------------------------ | ------------------------------------------ |
| PDF bytes                | `data/uploads/` (dev) or S3 (production)   |
| Path to file             | `storage_path` column in `documents` table |
| Pins, text, explanations | Database rows                              |


Think of the database as an **index card catalog** and the file system / S3 as the **warehouse** where the actual books sit.

### Local file storage (dev / mini-project 4)

Start here before touching S3. No accounts, no credentials.

**Folder layout:**

```
project/
  data/
    app.db              # SQLite database
    uploads/
      a1b2c3.pdf        # uploaded files named by document id
```

**Save on upload (FastAPI):**

```python
from pathlib import Path

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

storage_path = str(UPLOAD_DIR / f"{doc_id}.pdf")
Path(storage_path).write_bytes(pdf_bytes)

# In DB: storage_path = "data/uploads/a1b2c3.pdf"
```

**Read when processing OCR:**

```python
pdf_path = Path(doc["storage_path"])
if not pdf_path.exists():
    raise FileNotFoundError(f"Missing file: {pdf_path}")
doc = fitz.open(pdf_path)
```

**Serve to browser (simple dev option):** For mini-projects, you can expose uploaded PDFs via a static route or return a `file://` path only on the server side. The React app usually loads the PDF the user just selected locally (`URL.createObjectURL(file)`) before upload — you don't need to re-download it for the prototype.

**Add to** `.gitignore`**:**

```
data/uploads/
data/app.db
```



### Amazon S3 (or compatible: Cloudflare R2, MinIO)

**What it does:** Object storage for uploaded PDFs. The API stores a **key** (path-like string) in the database, not the file bytes.


| Pros                                        | Cons                                       |
| ------------------------------------------- | ------------------------------------------ |
| Scales to huge files and traffic            | IAM policies and CORS confuse beginners    |
| Pre-signed URLs let browser upload directly | Costs money at scale (usually cheap early) |
| Decouples app servers from disk             | Another service to configure               |


**S3 vocabulary:**


| Term       | Plain English                      | Example                        |
| ---------- | ---------------------------------- | ------------------------------ |
| **Bucket** | Top-level container (like a drive) | `pinpoint-uploads-dev`         |
| **Key**    | Path + filename inside the bucket  | `users/abc/documents/stmt.pdf` |
| **Object** | The file bytes at that key         | Your PDF                       |
| **Region** | AWS data center location           | `us-east-1`                    |


The database stores the **key** (or full `s3://bucket/key` URI), not the file content.

**Alternatives:**


| Service                   | Notes                                    |
| ------------------------- | ---------------------------------------- |
| **Local** `data/uploads/` | Fine for dev and mini-project 4          |
| **Supabase Storage**      | S3-like API + auth; great for hackathons |
| **Cloudflare R2**         | S3-compatible, no egress fees            |


**Two upload patterns:**

```mermaid
flowchart LR
  subgraph simple [Pattern 1 — Server upload]
    B1[Browser] -->|POST multipart| API1[Your API]
    API1 -->|write bytes| S3A[(S3)]
  end

  subgraph presigned [Pattern 2 — Pre-signed URL]
    B2[Browser] -->|1. ask for upload URL| API2[Your API]
    API2 -->|2. return signed URL| B2
    B2 -->|3. PUT file directly| S3B[(S3)]
  end
```



1. **Server upload** — browser POSTs file to your API; API writes to S3. **Start here.** One place to validate file type and size; simpler mental model.
2. **Pre-signed upload** — API returns a temporary URL; browser PUTs file straight to S3. **Production pattern** for large files (API doesn't proxy megabytes).

**S3 setup checklist (first time):**

1. Create an AWS account (or use Supabase Storage / Cloudflare R2 to skip IAM complexity).
2. Create a **bucket** (name must be globally unique).
3. Block **public** access (keep PDFs private).
4. Create an **IAM user** with programmatic access; attach a policy that allows `s3:PutObject`, `s3:GetObject` on that bucket only.
5. Copy `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET` into `.env`.
6. If using browser PUT uploads, add **CORS** on the bucket allowing your frontend origin and `PUT`.

**Python (boto3) — server-side upload:**

```python
import boto3
import os

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ["AWS_REGION"],
)

def upload_pdf(local_path: str, key: str) -> str:
    bucket = os.environ["S3_BUCKET"]
    s3.upload_file(local_path, bucket, key)
    return f"s3://{bucket}/{key}"
```

**Pre-signed URL (browser uploads directly):**

```python
url = s3.generate_presigned_url(
    "put_object",
    Params={"Bucket": bucket, "Key": key, "ContentType": "application/pdf"},
    ExpiresIn=3600,
)
# Return url to frontend; frontend does: fetch(url, { method: "PUT", body: file })
```

**Full server-upload flow (beginner — Pattern 1):**

```python
# 1. API receives file (see FastAPI upload example above)
# 2. Upload to S3
key = f"documents/{doc_id}.pdf"
upload_pdf(str(local_path), key)
# 3. Save key in database
# storage_path = key   (or full s3:// URI)
```

```ts
// Frontend — same as local dev; API hides S3 details
const form = new FormData();
form.append("file", pdfFile);
const res = await fetch("/api/documents", { method: "POST", body: form });
const { id, status } = await res.json();
```

**Downloading / viewing a private PDF (signed GET URL):**

Buckets are private, so the browser can't open `https://bucket.s3.amazonaws.com/...` directly. Your API generates a **time-limited signed URL**:

```python
download_url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=3600,  # 1 hour
)
return {"url": download_url}
```

The frontend opens that URL in PDF.js or a new tab. Link expires automatically.

**Node (@aws-sdk/client-s3):**

```ts
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";

const s3 = new S3Client({ region: process.env.AWS_REGION });

await s3.send(
  new PutObjectCommand({
    Bucket: process.env.S3_BUCKET,
    Key: `uploads/${docId}.pdf`,
    Body: fileBuffer,
    ContentType: "application/pdf",
  })
);
```

**Common AI mistakes with S3:**

- Putting credentials in frontend code (never).
- Forgetting bucket CORS for browser PUT uploads.
- Storing full PDF in PostgreSQL instead of S3.
- Using `public-read` ACL on sensitive financial documents — use private bucket + signed GET URLs instead.

**File storage mistakes (beginners):**


| Mistake                                      | Fix                                                              |
| -------------------------------------------- | ---------------------------------------------------------------- |
| Upload works locally but fails in production | Dev uses `data/uploads/`; prod needs S3 env vars set on the host |
| `AccessDenied` from boto3                    | IAM user lacks permission on that bucket/key                     |
| Browser PUT to S3 fails with CORS error      | Add CORS rule on bucket for your origin + `PUT` method           |
| Lost files after redeploy                    | Local disk on PaaS is ephemeral — use S3 for production          |
| Same filename overwrites previous upload     | Use UUID in key: `documents/{uuid}.pdf`                          |


---



## Authentication



### Authentication in plain English

**Authentication** answers: *Who is this user?*  
**Authorization** answers: *Are they allowed to do this?*

For Pinpoint, auth means:

- Alice uploads a statement → only Alice sees her documents and pins.
- Bob cannot call `GET /documents/{alice_doc_id}` and read Alice's financial PDF metadata.

Mini-projects 1–4 **skip auth** on purpose — one less moving part while you learn PDF + OCR + API wiring. Add auth when you deploy a multi-user MVP.

### Sessions vs JWT (don't overthink it)


| Approach                 | How it works                                                      | Who manages it                                         |
| ------------------------ | ----------------------------------------------------------------- | ------------------------------------------------------ |
| **Session cookie**       | Server stores session; browser sends cookie                       | Server-side session store                              |
| **JWT (JSON Web Token)** | Signed token in `Authorization` header; server verifies signature | Clerk, Supabase, Auth0 issue tokens; your API verifies |


Hosted providers (Clerk, Supabase) handle passwords, OAuth ("Sign in with Google"), and token signing. **You still must check auth on every API route** — a login UI alone doesn't protectcors

 your backend.

### How login flows work

```mermaid
sequenceDiagram
  participant User
  participant React
  participant Auth as Clerk / Supabase
  participant API as Your FastAPI / Express

  User->>React: Click Sign in
  React->>Auth: Show login UI
  Auth-->>React: JWT or session token
  React->>API: GET /documents + Authorization header
  API->>API: Verify token, extract user_id
  API-->>React: Only this user's documents
```



**The one rule that matters:** Every `documents` row needs `owner_id` (or `user_id`). Every query filters by it:

```python
# BAD — returns anyone's document
doc = db.query(Document).filter(Document.id == doc_id).first()

# GOOD
doc = db.query(Document).filter(
    Document.id == doc_id,
    Document.owner_id == current_user_id,
).first()
```



### Clerk

**What it does:** Hosted auth UI (sign-in, OAuth, MFA). Your API verifies JWTs.


| Pros                              | Cons                                      |
| --------------------------------- | ----------------------------------------- |
| Fastest to ship                   | Vendor lock-in; pricing at scale          |
| React components ready to drop in | JWT verification must be wired on backend |


**Clerk setup (outline):**

1. Create app at [clerk.com](https://clerk.com/) → get **publishable key** (frontend) and **secret key** (backend).
2. React: wrap app in `<ClerkProvider>`, add `<SignIn />` / `<UserButton />`.
3. Frontend env: `VITE_CLERK_PUBLISHABLE_KEY=pk_...` (safe in browser).
4. Backend: install `@clerk/express` or verify JWT in FastAPI with Clerk's JWKS URL.
5. Add `owner_id` column to `documents`; set it on upload from `user_id` in the token.



### Supabase Auth

**What it does:** Email/OAuth auth tied to Supabase Postgres.


| Pros                               | Cons                              |
| ---------------------------------- | --------------------------------- |
| Auth + DB + storage in one project | Less customizable UI than Clerk   |
| Great for hackathons               | Row-level security learning curve |


**Supabase setup (outline):**

1. Create project at [supabase.com](https://supabase.com/) — you get Postgres + Auth + Storage together.
2. React: `npm install @supabase/supabase-js`, create client with project URL + **anon key** (public).
3. `supabase.auth.signInWithPassword({ email, password })` or OAuth.
4. Pass `session.access_token` to your API: `Authorization: Bearer <token>`.
5. Backend verifies JWT with Supabase's JWT secret (in project settings).

**Optional:** [Row Level Security (RLS)](https://supabase.com/docs/guides/auth/row-level-security) lets Postgres enforce `owner_id` even if you forget a `WHERE` clause — powerful but learn basics first.

### DIY JWT + bcrypt


| Pros         | Cons                                             |
| ------------ | ------------------------------------------------ |
| Full control | Easy to get wrong (timing attacks, token expiry) |
| No vendor    | You build password reset, OAuth, etc.            |


**Recommendation for beginners:** Use **Clerk** or **Supabase Auth** for your first production deploy. Roll your own only if you have a specific reason and time to handle security details.

**Express — verify Clerk JWT (pattern):**

```ts
import { clerkMiddleware, getAuth } from "@clerk/express";

app.use(clerkMiddleware());

app.get("/documents", (req, res) => {
  const { userId } = getAuth(req);
  if (!userId) return res.status(401).json({ error: "unauthorized" });
  // return only this user's documents
});
```

**FastAPI — verify Bearer token (pattern):**

```python
from fastapi import Depends, HTTPException, Header

async def get_current_user_id(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.removeprefix("Bearer ")
    # Use Clerk/Supabase SDK or PyJWT + issuer's public keys to verify token
    user_id = verify_token_and_get_user_id(token)  # your provider's helper
    return user_id

@app.get("/documents")
async def list_documents(user_id: str = Depends(get_current_user_id)):
    return db.query(Document).filter(Document.owner_id == user_id).all()
```

**Protecting routes — checklist:**


| Layer        | What to do                                             |
| ------------ | ------------------------------------------------------ |
| **Frontend** | Hide upload UI when logged out; redirect to sign-in    |
| **API**      | Reject requests without valid token (`401`)            |
| **Database** | `owner_id` on every user-owned row; filter every query |
| **Storage**  | S3 keys include `user_id/` prefix; signed URLs expire  |


**Common auth mistakes (beginners):**


| Mistake                                     | Fix                                                                       |
| ------------------------------------------- | ------------------------------------------------------------------------- |
| Login works but API returns all users' data | Add `owner_id` filter on every query                                      |
| Secret key in `VITE_*` env var              | Only **publishable** keys in frontend; verify tokens on server            |
| Skipping auth on one "internal" route       | Attackers will find it — protect all document/pin routes                  |
| Trusting `user_id` from request body        | Read `user_id` from verified token only, never from JSON the client sends |


**Rule:** Every document row should have an `owner_id` (or `user_id`) and every query must filter by the authenticated user.

---



## Background jobs & queues

Document OCR is slow — don't block the HTTP response.


| Tool                          | When                                    |
| ----------------------------- | --------------------------------------- |
| **FastAPI** `BackgroundTasks` | Mini-project 4; single server, dev only |
| **Redis + Celery (Python)**   | Production Python workers               |
| **Redis + BullMQ (Node)**     | Production Node workers                 |
| **Inngest / Trigger.dev**     | Serverless-friendly job orchestration   |


```python
# FastAPI — fire and forget (mini-project 4)
background_tasks.add_task(process_document, doc_id)
```

**Production pattern:** API enqueues a job → worker process picks it up → updates DB status → frontend polls or uses WebSockets.

---



## Pinpoint-specific pipeline tools


| Tool                              | Role                                    | Language |
| --------------------------------- | --------------------------------------- | -------- |
| **pdfjs-dist**                    | Render PDF in browser                   | JS       |
| **PyMuPDF (**`fitz`**)**          | Extract text + bboxes from digital PDFs | Python   |
| **pdfplumber**                    | Alternative text extraction             | Python   |
| **Tesseract (**`pytesseract`**)** | OCR for scanned pages                   | Python   |
| **Pillow (PIL)**                  | Draw debug boxes on page images         | Python   |
| **OpenAI / Anthropic SDK**        | Plain-English explanations              | Python   |


**PyMuPDF word extraction (project 2):**

```python
import fitz  # PyMuPDF

doc = fitz.open("statement.pdf")
page = doc[0]
for word in page.get_text("words"):
    x0, y0, x1, y1, text, block_no, line_no, word_no = word
    # bbox: x0,y0 top-left; width = x1-x0; height = y1-y0
```

**Tesseract (scanned path):**

```python
import pytesseract
from PIL import Image

data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
for i, text in enumerate(data["text"]):
    if int(data["conf"][i]) < 60:
        continue
    # use data["left"][i], data["top"][i], etc.
```

---



## LLM integration

**Pinpoint flow:** `phrase` + `context` + `document_type` → 2–4 sentence explanation, grounded in context.


| Provider  | SDK              | Local?             |
| --------- | ---------------- | ------------------ |
| OpenAI    | `openai`         | No                 |
| Anthropic | `anthropic`      | No                 |
| Ollama    | HTTP to `:11434` | Yes (free, slower) |


See [API keys section](#api-keys--secrets-read-this-carefully) for correct env loading.

---



## Hackathon staples

Stacks teams reach for when speed matters more than long-term architecture:


| Category                  | Popular choices                      | Why                                                  |
| ------------------------- | ------------------------------------ | ---------------------------------------------------- |
| **Full-stack in one**     | Next.js + Vercel                     | Frontend + API routes + deploy in minutes            |
| **BaaS**                  | Supabase, Firebase                   | Auth, DB, storage without managing servers           |
| **UI**                    | shadcn/ui + Tailwind                 | Copy-paste polished components                       |
| **AI**                    | OpenAI API, Vercel AI SDK, LangChain | Fast LLM wiring                                      |
| **Deploy**                | Vercel, Railway, Render, Fly.io      | Free tiers, git push deploy                          |
| **Styling**               | Tailwind CSS                         | Utility classes, no CSS files                        |
| **ORM**                   | Prisma, Drizzle                      | Fast schema + migrations                             |
| **Real-time**             | Supabase realtime, Pusher            | Live updates without polling                         |
| **Hackathon AI builders** | v0, Bolt, Lovable                    | Generate UI scaffolding (still need to wire backend) |


**Typical 24h hackathon stack:**

```
Next.js (App Router) + Supabase + OpenAI + Vercel + shadcn/ui
```

**Pinpoint-style hackathon stack (PDF + Python OCR):**

```
React (Vite) + FastAPI on Railway + SQLite or Supabase Postgres + S3 or Supabase Storage + OpenAI
```

---



## API keys & secrets (read this carefully)

This is where tutorials and AI-generated code most often fail. Follow these rules every time.

### Golden rules

1. **Never commit secrets to git.** Add `.env` to `.gitignore` (Pinpoint already does).
2. **Never put secret keys in frontend code** or `VITE_`* env vars.
3. **Never log secrets** (`console.log(process.env.OPENAI_API_KEY)` in shared logs).
4. **Use different keys** for dev vs production.
5. **Rotate keys** immediately if one leaks (GitHub scans public repos and will email you).



### File layout

```
project/
  .env                 # local secrets — NOT committed
  .env.example         # committed template with fake values
  .gitignore           # must include .env
```

**.env.example (commit this):**

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/pinpoint
OPENAI_API_KEY=sk-your-key-here
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET=pinpoint-uploads-dev
```



### Python — `python-dotenv`

```python
# Load BEFORE reading os.environ — typically at top of main.py
from dotenv import load_dotenv
import os

load_dotenv()  # reads .env from cwd

api_key = os.environ["OPENAI_API_KEY"]  # raises KeyError if missing — good for dev
# Safer optional: os.getenv("OPENAI_API_KEY") with explicit error message
```

```python
# OpenAI — after load_dotenv()
from openai import OpenAI

client = OpenAI()  # automatically uses OPENAI_API_KEY env var
# Or explicitly: OpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

**AI mistake:** Calling the API without `load_dotenv()` in scripts run outside uvicorn, or hardcoding `api_key="sk-..."` in source.

### Node / Express — `dotenv`

```js
// Must be first import in entry file (index.js / server.ts)
import "dotenv/config";

const key = process.env.OPENAI_API_KEY;
if (!key) throw new Error("OPENAI_API_KEY is not set");
```

For ES modules, alternative:

```js
import dotenv from "dotenv";
dotenv.config();
```



### Prisma — `DATABASE_URL`

```bash
# .env
DATABASE_URL="postgresql://user:pass@localhost:5432/pinpoint?schema=public"
```

Prisma CLI and client read this automatically. **Never** embed the URL in `schema.prisma` as a literal string.

### Production — platform env vars

On Railway, Render, Vercel, etc., set env vars in the **dashboard**, not in files:

```bash
# You type these in the hosting UI — not in git
OPENAI_API_KEY=sk-live-...
DATABASE_URL=postgresql://...
```



### Passing keys to Docker

```dockerfile
# BAD — don't ARG/ENV secrets into image layers
# GOOD — pass at runtime:
# docker run -e OPENAI_API_KEY=... myapp
```

Use Docker secrets or platform env injection instead.

### Frontend proxy pattern (avoid CORS + hide backend URL)

In **Vite**, proxy API calls in dev so the browser only talks to `:5173`:

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
```

The OpenAI key stays on the Python/Node server; the React app only calls `/api/explain`.

---



## Syntax cheat sheet



### HTTP methods (REST conventions)


| Method   | Use             | Example                              |
| -------- | --------------- | ------------------------------------ |
| `GET`    | Read            | `GET /documents/{id}/pins`           |
| `POST`   | Create / action | `POST /documents` upload             |
| `PUT`    | Full replace    | `PUT /pins/{id}`                     |
| `PATCH`  | Partial update  | `PATCH /pins/{id}` toggle visibility |
| `DELETE` | Remove          | `DELETE /documents/{id}`             |




### `fetch` (browser)

```ts
// GET
const data = await fetch("/api/documents").then((r) => r.json());

// POST JSON
const res = await fetch("/api/explain", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ phrase, context, document_type }),
});

// POST multipart (file upload)
const form = new FormData();
form.append("file", fileInput.files[0]);
await fetch("/api/documents", { method: "POST", body: form });
```



### CORS (backend must allow frontend origin)

```python
# FastAPI
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
```

```js
// Express
import cors from "cors";
app.use(cors({ origin: "http://localhost:5173" }));
```



### Async gotchas


| Mistake                               | Fix                                                   |
| ------------------------------------- | ----------------------------------------------------- |
| Blocking OCR inside `async def` route | Run CPU work in `run_in_executor` or a worker process |
| Forgetting `await` on DB/API calls    | Always `await prisma.document.findMany()`             |
| Not handling `fetch` errors           | Check `res.ok` before `.json()`                       |




### JSON columns (bbox storage)

```ts
// Prisma returns typed object
const bbox = pin.bboxJson as { x: number; y: number; width: number; height: number };
```

```python
# SQLite — serialize manually
bbox_json = json.dumps({"x": 120.5, "y": 340.2, "width": 28, "height": 12})
```



### Migrations

```bash
# Prisma
npx prisma migrate dev --name init
npx prisma generate

# SQLAlchemy (Alembic)
alembic revision --autogenerate -m "init"
alembic upgrade head
```

---



## Suggested learning order for Pinpoint

1. **TypeScript basics + React + Vite + fetch** — mini-project 1
2. **Python CLI + PyMuPDF** — mini-project 2
3. **OpenAI +** `.env` — mini-project 3
4. **FastAPI + SQLite + background tasks** — mini-project 4
5. **PostgreSQL + Prisma or SQLAlchemy + S3 + auth** — production

---



## Further reading

- [Pinpoint mini-projects](./mini-projects/README.md)
- [TypeScript handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [MDN — Express/Node tutorial](https://developer.mozilla.org/en-US/docs/Learn/Server-side/Express_Nodejs)
- [FastAPI docs](https://fastapi.tiangolo.com/)
- [Prisma docs](https://www.prisma.io/docs)
- [AWS S3 presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)

