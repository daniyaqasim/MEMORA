# MEMORA

MEMORA is an AI-powered personal memory system in development. Its eventual purpose is to help people save scattered digital information and find it again through natural-language questions.

## Stage 5: AI memory intelligence

This stage provides a clean dashboard, a FastAPI health endpoint, and local memory-file ingestion. The **Add Memory** control accepts PDF, PNG, JPEG, and TXT files up to 10 MB. Every new upload is stored under a generated filename and saved as a persistent SQLite memory record in `backend/data/memora.db`.

TXT and text-based PDF files have their text extracted; image files are persisted without OCR. Extracted TXT/PDF text is split into chunks, embedded locally with `all-MiniLM-L6-v2`, and indexed in `backend/data/memora.faiss`. With configured Groq hosted inference, MEMORA generates grounded answers from retrieved memory evidence and saves a factual summary plus a cautious likely-context inference for extracted memories.

## Project structure

```text
backend/
  app/
    __init__.py
    database.py
    main.py
    models.py
    routes/
      memories.py
      search.py
    services/
      analysis.py
      answering.py
      chunking.py
      embeddings.py
      extraction.py
      indexing.py
      llm.py
      search.py
      vector_store.py
  data/
  requirements.txt
  uploads/
frontend/
  src/
    App.jsx
    main.jsx
    styles.css
  .env.example
  index.html
  package.json
  vite.config.js
demo-data/
```

## Run locally

### Backend

From the project root, create and activate a virtual environment (optional but recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```powershell
python -m pip install -r backend\requirements.txt
```

Start FastAPI:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload
```

The health endpoint is available at http://127.0.0.1:8000/api/health and FastAPI's interactive docs are at http://127.0.0.1:8000/docs.

### Frontend

In a second terminal, install and start the Vite app:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (normally http://localhost:5173).

## API configuration

For local development, Vite proxies `/api` calls to the FastAPI server at `http://127.0.0.1:8000`. For a later deployment, set `VITE_API_BASE_URL` to the deployed API origin during the frontend build. See `frontend/.env.example`.

## Hosted inference configuration

Copy `backend/.env.example` to `backend/.env`, then set `GROQ_API_KEY` and a supported `GROQ_MODEL`. The key remains server-side and is never sent to the frontend.

## Earlier-stage upgrade note

Stage 2 uploads already in `backend/uploads/` are intentionally not imported into SQLite because they have no reliable metadata records. Upload new files after installing the dependencies to create persistent memories. To reset all local Stage 3/4 metadata and vectors during development, stop the API and remove both `backend/data/memora.db` and `backend/data/memora.faiss`; this does not delete uploaded files.
