# Pinpoint

Pinpoint explains confusing terms in dense PDFs — contracts, forms, papers, policies — without leaving the page.

Upload a document and Pinpoint finds likely-unfamiliar words and phrases, then underlines them on the PDF. Click an underline and a side panel explains that term in plain English, using the surrounding text so the meaning stays grounded in *this* document. The same word on two pages gets two explanations: each one is tied to its local context.

The panel is a session log of terms you have opened, not a chatbot and not a glossary of every detected word. Explanations are written for a general reader and are not legal, medical, or financial advice.

Developer details live in [docs/technical-overview.md](docs/technical-overview.md).

## Run locally

Run the backend and frontend in two terminals. The Vite app on port 5173 proxies `/api` to FastAPI on port 8000.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Set `GEMINI_API_KEY` in `backend/.env`. Then:

```bash
uvicorn main:app --reload --port 8000
```

Health check: [http://localhost:8000/health](http://localhost:8000/health).

Scanned PDFs also need [Tesseract](https://github.com/tesseract-ocr/tesseract) installed on the machine. Digital (text-selectable) PDFs do not.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).
