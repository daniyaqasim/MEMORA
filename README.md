# MEMORA

MEMORA is an AI-powered personal memory system that helps people recover information from the digital things they save—screenshots, PDFs, images, and notes—using meaning and context rather than filenames or folders.

## The Problem

People save useful information across screenshots, documents, notes, receipts, and other digital sources. Later, they often remember what they saw but not where they saved it. Traditional storage systems organize information by location and file structure; MEMORA is designed to make it retrievable through meaning and context instead.

## What MEMORA Does

1. Add a memory from a PDF, TXT file, PNG, JPG, or JPEG.
2. Extract or understand its content, including image understanding for screenshots.
3. Chunk and embed usable content for semantic retrieval.
4. Ask a natural-language question about something you vaguely remember.
5. Retrieve relevant memory evidence and generate a grounded answer.
6. Show the original supporting source, a short summary, and a cautious inference about why it may have been saved.

### Example

A user saves a screenshot containing several scholarship names. Weeks later, they ask: “What were the scholarships I was looking at?” MEMORA retrieves the screenshot by meaning, answers from its understood content, and points back to the original memory.

## Current Features

- TXT and text-based PDF ingestion and extraction
- PNG, JPG, and JPEG screenshot/image understanding
- Persistent memory and chunk metadata
- Semantic retrieval across saved memories
- Grounded natural-language Q&A with original-source attribution
- AI-generated summary and cautious likely-context inference
- Anonymous browser-session isolation for the public MVP
- Responsive React web interface

## Architecture

```text
React + Vite frontend
        ↓
FastAPI API
        ↓
Ingestion / extraction / image understanding
        ↓
Deterministic chunking
        ↓
Hugging Face embedding inference
        ↓
FAISS vector search + SQLite metadata
        ↓
Session-scoped semantic retrieval
        ↓
Groq-hosted LLM
        ↓
Grounded answer + source + likely context
```

TXT and PDF content is extracted with PyMuPDF where applicable. Images are understood through the configured Groq vision model, then represented as text before entering the same chunking, embedding, and FAISS retrieval path. Embeddings are generated remotely through Hugging Face `InferenceClient`; the backend does not load sentence-transformers or PyTorch locally. The configured default embedding model is `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).

## Tech Stack

| Area | Technology |
| --- | --- |
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| Metadata | SQLite, SQLAlchemy |
| Vector search | FAISS |
| PDF extraction | PyMuPDF |
| Embeddings | Hugging Face `InferenceClient` with the configured embedding model |
| Grounded answering | Groq-hosted configured language model |
| Image understanding | Configured Groq vision model |

## Privacy / Session Model

The public MVP does not require accounts. Each browser receives a locally stored anonymous session identifier, and upload, list, detail, image, deletion, and retrieval operations are scoped to that identifier. This is lightweight MVP isolation, not production-grade authentication or a replacement for authenticated multi-user storage.

## Running Locally

### Backend

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

The API runs at `http://127.0.0.1:8000`; health is available at `http://127.0.0.1:8000/api/health` and API docs at `http://127.0.0.1:8000/docs`.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`).

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and provide the required server-side values. Never commit real keys or tokens.

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Groq API credential for configured language and vision inference |
| `GROQ_MODEL` | Grounded-answering and text-analysis model |
| `GROQ_VISION_MODEL` | Image-understanding model |
| `HF_TOKEN` | Hugging Face inference credential for embeddings |
| `HF_EMBEDDING_MODEL` | Remote embedding model identifier |
| `VITE_API_BASE_URL` | Frontend build-time API origin; leave blank for local Vite proxy |

`VITE_API_BASE_URL` is documented in `frontend/.env.example`; backend variables are documented in `backend/.env.example`.

## Deployment

- Frontend: Vercel
- Backend: Render
- Live demo: https://memora-six-psi.vercel.app

The free backend may take a short moment to wake after inactivity.

## Project Structure

```text
backend/
  app/
    routes/
      memories.py
      search.py
    services/
      analysis.py
      answering.py
      chunking.py
      embeddings.py
      extraction.py
      image_processing.py
      indexing.py
      llm.py
      search.py
      sessions.py
      vector_store.py
    database.py
    main.py
    models.py
  data/
  uploads/
  .env.example
  requirements.txt
frontend/
  src/
    App.jsx
    session.js
    styles.css
  .env.example
  vite.config.js
README.md
```

## MVP Scope / Roadmap

The current MVP focuses on two capabilities:

- **Find:** retrieve saved information by meaning.
- **Understand:** extract or interpret what a memory contains and infer likely context.

Potential future directions include remembering deadlines or commitments, connecting related memories, user-approved actions and integrations, authenticated accounts, stronger multi-user storage, and additional data-source integrations. These are not implemented in the current MVP.

## Status

MEMORA is a working MVP/prototype that is actively being developed.
