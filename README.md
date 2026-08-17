# RepoLens

RepoLens is a local-first RAG web application for exploring uploaded Python codebases.

## Phase 5 status

Phase 5 is complete. RepoLens now provides the complete local React flow from project upload to grounded answers and source inspection:

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
- Foundry Local chat completion behind a testable `ChatProvider` interface
- A version-controlled grounded prompt that treats repository snippets as untrusted data
- Grounded chat through `POST /api/projects/{project_id}/chat`
- Backend-owned citations built from retrieved SQLite chunk metadata
- Explicit `grounded`, `insufficient_context`, `indexing_incomplete`, and `error` answer states
- No chat-model call when retrieval does not find relevant context
- Responsive React dashboard with ZIP upload and selectable project cards
- Selected-project details, live indexing status polling, statistics, and retry/error states
- Grounded chat history with loading, empty, insufficient-context, and model-error states
- Backend-owned citation cards that open the exact stored chunk in a modal source viewer
- Desktop and mobile layouts with accessible form labels, dialogs, focus states, and reduced-motion support
- Deterministic fake-provider tests for indexing, retrieval, and chat without model downloads
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

### Verify grounded chat

After indexing a project, ask a question through the Phase 4 endpoint:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/projects/<project-id>/chat `
  -H "Content-Type: application/json" `
  -d '{"question":"Where is user registration implemented?","top_k":4}'
```

Answerable questions return `answer_status: "grounded"` and source objects whose `chunk_id` can be opened with `GET /api/projects/<project-id>/chunks/<chunk-id>`. If retrieval finds no relevant chunk, the API returns `insufficient_context` without calling the chat model.

## Project goals

- FastAPI backend as the source of truth for ingestion, retrieval, and local AI orchestration
- React + TypeScript + Vite frontend
- SQLite-backed local project metadata
- Foundry Local integration for embeddings and grounded local chat

## Notes

- Phase 5 intentionally does not provide authentication, Docker, evaluation metrics, or final portfolio documentation. Evaluation and presentation work is Phase 6.
- Projects indexed with Phase 2 placeholder vectors are marked `ready_to_index` and must be re-indexed once.
- Uploads are treated as untrusted input.
- Only Python and Markdown are supported in the MVP.
