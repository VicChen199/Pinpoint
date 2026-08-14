# Mini-project 3: Explanation API

**Goal:** Given a financial phrase and surrounding context, return a short plain-English explanation. Start as a Python script; optionally add an HTTP endpoint.

**Suggested code location:** `mini-projects/03-explanation-api/`

**Prerequisites:** Python basics, an API key for OpenAI or Anthropic (or Ollama for local).

**Previous:** [02-ocr-debugger.md](./02-ocr-debugger.md)  
**Next project:** [04-pipeline-glue.md](./04-pipeline-glue.md)

---

## Chat starter

Copy into a **new Cursor chat**:

```
@docs/mini-projects/03-explanation-api.md

Implement this mini-project in mini-projects/03-explanation-api/.
Start with a Python script + tests.json; optionally add FastAPI /explain endpoint.
Follow the plan step by step. Stop when the success criteria are met.
```

---

## What you'll learn

- Prompt design for Pinpoint's core UX
- Grounding answers in document context
- API shape the UI will call in project 4

---

## Architecture

```mermaid
flowchart LR
  Input[phrase + context + document_type] --> Prompt[Prompt template]
  Prompt --> LLM[OpenAI / Anthropic / Ollama]
  LLM --> Output[2-4 sentence explanation]
```

---

## Setup

```bash
mkdir -p mini-projects/03-explanation-api
cd mini-projects/03-explanation-api
python -m venv .venv
source .venv/bin/activate
pip install openai python-dotenv
# optional HTTP: pip install fastapi uvicorn
```

Create `.env` with `OPENAI_API_KEY=...` — add `.env` to `.gitignore`.

---

## Implementation steps

### 1. Core `explain_phrase()` function

**Inputs:**

- `phrase` — term to explain (e.g. `"APR"`)
- `context` — surrounding paragraph from the document
- `document_type` — e.g. `credit_card_statement`, `tax_form`, `insurance_eob`

**System prompt rules:**

- Plain English for someone with little finance background
- Use only provided context; do not invent dollar amounts
- Explain what the term means **and** how it applies in this document
- 2–4 short sentences
- No personalized investment or tax advice
- If context is insufficient, say what is missing

**Model:** `gpt-4o-mini` or similar for cheap iteration. Temperature ~0.3.

### 2. CLI test

```bash
python explain.py --phrase "APR" --context "..." --document-type credit_card_statement
```

### 3. Test suite — `tests.json`

At least 10 cases across document types: APR, escrow, deductible, AGI, minimum payment, copay, YTD, etc.

Run all cases; manually rate: accurate? plain? grounded?

### 4. Optional: FastAPI endpoint

```
POST /explain
Body: { "phrase", "context", "document_type" }
Response: { "explanation" }
```

```bash
uvicorn main:app --reload
```

### 5. Optional: local LLM via Ollama

Same interface; POST to `http://localhost:11434/api/generate` with `llama3.1` or similar.

---

## Prompt tips

- Pass **document type** — explanations differ for tax vs insurance
- Pass **only a paragraph** of context, not the full PDF
- Ask for **how it applies here** to avoid dictionary definitions

---

## Success criteria

- [ ] `explain_phrase()` works from CLI
- [ ] 10+ test cases in `tests.json`
- [ ] Explanations are 2–4 sentences, plain English, no invented numbers
- [ ] Optional: `POST /explain` returns JSON

---

## Becomes in Pinpoint

Explanation service — called when user clicks a pin (or on-demand if not cached).
