# RepoLens

RepoLens is a local-first RAG web application for exploring uploaded Python codebases.

## Phase 2 status

Phase 2 is complete. The application now supports local project upload, parsing, chunk persistence, and source inspection before AI features are added:

- FastAPI backend with typed settings, SQLite-backed project records, and a `GET /api/health` endpoint
- Safe ZIP uploads through `POST /api/projects`, including size limits, Zip Slip protection, symbolic-link rejection, and excluded-directory handling
- Project list, detail, and status endpoints
- Supported-file discovery for Python, Markdown, and MDX with generated, oversized, binary, and secret-like file exclusion
- Python AST chunking with function, class, method, module, and syntax-error fallback chunks
- Markdown heading chunking with heading hierarchy and exact line ranges
- SQLite-backed chunk storage with source metadata and placeholder embedding vectors
- Indexing and source chunk API endpoints
- React dashboard with upload, indexing, chunk listing, and a basic source viewer
- Root and frontend environment templates, plus backend API, parser, and archive-security tests

## Local setup

### Backend

Run the backend from the repository root so Python resolves the `app` package from the `backend/` directory:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### Verify health endpoint

```powershell
curl http://127.0.0.1:8000/api/health
```

## Project goals

- FastAPI backend as the source of truth for ingestion, retrieval, and local AI orchestration
- React + TypeScript + Vite frontend
- SQLite-backed local project metadata
- Foundry Local integration for embeddings and chat in later phases

## Notes

- Phase 2 intentionally does not generate embeddings or provide retrieval, chat, Foundry Local inference, authentication, Docker, or polished UI.
- Uploads are treated as untrusted input.
- Only Python and Markdown are supported in the MVP.
