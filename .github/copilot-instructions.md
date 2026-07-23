# RepoLens - Repository Instructions

RepoLens is a local-first RAG web application for exploring uploaded Python codebases.

Before making significant changes, read `docs/RepoLens_Copilot_Context.md`. Treat it as the source of truth for the project architecture, scope, API contracts, security constraints, directory structure, and implementation phases.

Core stack:

- Frontend: React + TypeScript + Vite
- Backend: Python 3.11+ + FastAPI
- Database: SQLite
- Local AI: Microsoft Foundry Local
- Retrieval: local embeddings + cosine similarity
- Parsing: Python AST and Markdown heading parser

Important rules:

- Keep all RAG, indexing, database, and Foundry Local logic in the FastAPI backend.
- React must call the backend API; it must not contain AI or database logic.
- Do not execute uploaded code.
- Handle ZIP extraction securely and prevent path traversal.
- Support only Python and Markdown in the MVP.
- Preserve file path, symbol name, and line ranges for every indexed chunk.
- Generate source citations in backend code from stored metadata; never trust the model to invent citations.
- Do not add cloud LLM APIs, external vector databases, authentication, Docker, or unrelated frameworks unless explicitly requested.
- Work in small phases. Do not implement the complete project in one change.
- Add or update tests for non-trivial parsing, retrieval, archive security, and API behavior.