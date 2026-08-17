# RepoLens

RepoLens is a local-first RAG web application for exploring uploaded Python codebases.

## Phase 3 status

Phase 3 is complete. The application now supports local project upload, parsing, semantic indexing, retrieval, and source inspection before grounded chat is added:

- FastAPI backend with typed settings, SQLite-backed project records, and a `GET /api/health` endpoint
- Safe ZIP uploads through `POST /api/projects`, including size limits, Zip Slip protection, symbolic-link rejection, and excluded-directory handling
- Project list, detail, and status endpoints
- Supported-file discovery for Python, Markdown, and MDX with generated, oversized, binary, and secret-like file exclusion
- Python AST chunking with function, class, method, module, and syntax-error fallback chunks
- Markdown heading chunking with heading hierarchy and exact line ranges
- Foundry Local document and query embeddings behind a testable provider interface
- Batched embedding generation during indexing with JSON vector persistence in SQLite
- NumPy cosine-similarity ranking with configurable `top_k` and minimum similarity
- Controlled `insufficient_context` search results when no chunk meets the threshold
- Indexing, source chunk, and temporary semantic search API endpoints
- React dashboard with upload, indexing, chunk listing, and a basic source viewer
- Deterministic fake-provider tests for indexing and retrieval without model downloads
- Root and frontend environment templates, plus backend API, parser, archive-security, provider, and retrieval tests

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

### Verify semantic search

After uploading and indexing a project, call the temporary Phase 3 search endpoint:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/projects/<project-id>/search `
  -H "Content-Type: application/json" `
  -d '{"query":"Where is user registration implemented?","top_k":4}'
```

The first real indexing request prepares the configured Foundry Local embedding model. If the model is not already cached, Foundry Local downloads it before generating vectors.

## Project goals

- FastAPI backend as the source of truth for ingestion, retrieval, and local AI orchestration
- React + TypeScript + Vite frontend
- SQLite-backed local project metadata
- Foundry Local integration for embeddings, with grounded chat planned for Phase 4

## Notes

- Phase 3 intentionally does not provide grounded chat, authentication, Docker, or polished UI.
- Projects indexed with Phase 2 placeholder vectors are marked `ready_to_index` and must be re-indexed once.
- Uploads are treated as untrusted input.
- Only Python and Markdown are supported in the MVP.
