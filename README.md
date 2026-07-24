# RepoLens

RepoLens is a local-first RAG web application for exploring uploaded Python codebases.

## Phase 0 status

This repository now includes the initial Phase 0 backend and frontend bootstrap:

- FastAPI backend with a typed settings module and a `GET /api/health` endpoint
- React + TypeScript + Vite frontend that calls the health endpoint and displays the JSON response
- Shared environment template and repository ignore rules

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
- SQLite-backed local project metadata in later phases
- Foundry Local integration for embeddings and chat in later phases

## Notes

- Phase 0 intentionally does not implement ZIP upload, SQLite, RAG, Foundry Local, authentication, Docker, or advanced UI.
- Uploads are treated as untrusted input.
- Only Python and Markdown are supported in the MVP.
